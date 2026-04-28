"""Testes unit do módulo ``hemiciclo.modelos.convertibilidade`` (S34).

Cobre:

- :class:`ExtratorFeatures` -- artefatos completos, sem histórico, sem grafo.
- :class:`ModeloConvertibilidade` -- treino com ``random_state=42``,
  prever_proba em [0, 1], métricas, coeficientes, salvar/carregar
  round-trip + integridade violada.
- Skip graceful: amostra mínima 30 levanta :class:`AmostraInsuficiente`,
  monoclasse idem, colunas ausentes idem.

Política de fixtures: criamos JSONs sintéticos cobrindo o schema real
produzido por S33/S32/S27 -- nunca inventamos chaves fora do contrato.
Isso garante que mudança em qualquer um dos artefatos quebre este
teste primeiro (sentinela de contrato).
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from hemiciclo.modelos.convertibilidade import (
    FEATURE_NAMES_PADRAO,
    MIN_AMOSTRA,
    AmostraInsuficiente,
    ExtratorFeatures,
    IntegridadeViolada,
    ModeloConvertibilidade,
    treinar_convertibilidade_sessao,
)

# ---------------------------------------------------------------------------
# Helpers de fixtures (montam artefatos no formato S33/S32/S27 reais)
# ---------------------------------------------------------------------------


def _historico_sintetico(n_parlamentares: int = 40, n_com_mudancas: int = 20) -> dict[str, object]:
    """JSON no formato de :func:`hemiciclo.modelos.historico.calcular_historico_top`.

    Os primeiros ``n_com_mudancas`` parlamentares têm 1 evento em
    ``mudancas_detectadas`` (target=1); os demais ficam estáveis (target=0).
    Volatilidade varia entre 0.1 e 0.9 pra não saturar.
    """
    parlamentares: dict[str, object] = {}
    for idx in range(1, n_parlamentares + 1):
        pid = str(100 + idx)
        eh_mudou = idx <= n_com_mudancas
        volat = 0.6 if eh_mudou else 0.1 + (idx % 5) * 0.02  # diversifica baixo
        bloco: dict[str, object] = {
            "casa": "camara",
            "nome": f"Parlamentar {pid}",
            "historico": [
                {
                    "bucket": 2018,
                    "n_votos": 10,
                    "proporcao_sim": 0.8 if eh_mudou else 0.5,
                    "proporcao_nao": 0.2 if eh_mudou else 0.5,
                    "posicao": "a_favor" if eh_mudou else "neutro",
                },
                {
                    "bucket": 2024,
                    "n_votos": 12,
                    "proporcao_sim": 0.2 if eh_mudou else 0.55,
                    "proporcao_nao": 0.8 if eh_mudou else 0.45,
                    "posicao": "contra" if eh_mudou else "neutro",
                },
            ],
            "mudancas_detectadas": (
                [
                    {
                        "bucket_anterior": 2018,
                        "bucket_posterior": 2024,
                        "proporcao_sim_anterior": 0.8,
                        "proporcao_sim_posterior": 0.2,
                        "delta_pp": -60.0,
                        "posicao_anterior": "a_favor",
                        "posicao_posterior": "contra",
                    }
                ]
                if eh_mudou
                else []
            ),
            "indice_volatilidade": float(volat),
        }
        parlamentares[pid] = bloco
    return {
        "parlamentares": parlamentares,
        "metadata": {
            "granularidade": "ano",
            "threshold_pp": 30.0,
            "n_parlamentares": n_parlamentares,
            "n_com_mudancas": n_com_mudancas,
            "skipped": False,
        },
    }


def _metricas_rede_sinteticas(n_top: int = 30) -> dict[str, object]:
    """JSON no formato de ``_persistir_metricas_rede`` (S32)."""
    top_centrais: list[dict[str, object]] = []
    for idx in range(1, n_top + 1):
        top_centrais.append(
            {
                "parlamentar_id": 100 + idx,
                "centralidade_grau": 0.1 + (idx % 5) * 0.05,
                "centralidade_intermediacao": 0.05 + (idx % 7) * 0.02,
                "comunidade_voto": idx % 4,
            }
        )
    return {
        "coautoria": {"skipped": True, "motivo": "irrelevante para S34"},
        "voto": {
            "skipped": False,
            "n_nos": 50,
            "n_arestas": 200,
            "maior_componente": 50,
            "n_comunidades": 4,
            "top_centrais": top_centrais,
        },
    }


def _classificacao_sintetica(n: int = 40) -> dict[str, object]:
    """JSON no formato de ``classificar`` (S27)."""
    top_a_favor: list[dict[str, object]] = []
    top_contra: list[dict[str, object]] = []
    for idx in range(1, n + 1):
        registro = {
            "parlamentar_id": 100 + idx,
            "nome": f"Parlamentar {100 + idx}",
            "proporcao_sim": 0.7 if idx <= n // 2 else 0.2,
            "n_votos": 15 + idx,
        }
        if idx <= n // 2:
            top_a_favor.append(registro)
        else:
            top_contra.append(registro)
    return {
        "topico": "aborto",
        "n_props": 50,
        "n_parlamentares": n,
        "camadas": ["regex", "votos", "tfidf"],
        "top_a_favor": top_a_favor,
        "top_contra": top_contra,
    }


def _gravar_artefatos(
    sessao_dir: Path,
    historico: dict[str, object] | None = None,
    rede: dict[str, object] | None = None,
    classif: dict[str, object] | None = None,
) -> None:
    """Grava artefatos sintéticos na pasta da sessão."""
    sessao_dir.mkdir(parents=True, exist_ok=True)
    if historico is not None:
        (sessao_dir / "historico_conversao.json").write_text(
            json.dumps(historico, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if rede is not None:
        (sessao_dir / "metricas_rede.json").write_text(
            json.dumps(rede, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if classif is not None:
        (sessao_dir / "classificacao_c1_c2.json").write_text(
            json.dumps(classif, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# ExtratorFeatures
# ---------------------------------------------------------------------------


def test_extrator_combina_3_artefatos(tmp_path: Path) -> None:
    """Lê histórico + rede + classificação e retorna DataFrame coeso."""
    sessao_dir = tmp_path / "sessao_completa"
    _gravar_artefatos(
        sessao_dir,
        historico=_historico_sintetico(n_parlamentares=40),
        rede=_metricas_rede_sinteticas(n_top=30),
        classif=_classificacao_sintetica(n=40),
    )
    df = ExtratorFeatures.extrair(sessao_dir)
    assert df.shape[0] == 40  # noqa: PLR2004
    # Schema canônico
    for col in (
        "parlamentar_id",
        "casa",
        "nome",
        "indice_volatilidade",
        "centralidade_grau",
        "centralidade_intermediacao",
        "proporcao_sim_topico",
        "n_votos_topico",
        "mudou_recentemente",
    ):
        assert col in df.columns, f"coluna ausente: {col}"
    # Target equilibrado: 20 mudaram, 20 não
    target_counts = df["mudou_recentemente"].value_counts().sort("mudou_recentemente")
    assert target_counts.shape[0] == 2  # noqa: PLR2004


def test_extrator_sem_historico_devolve_vazio(tmp_path: Path) -> None:
    """Sem ``historico_conversao.json`` -> DataFrame vazio + aviso."""
    sessao_dir = tmp_path / "sem_historico"
    sessao_dir.mkdir()
    df = ExtratorFeatures.extrair(sessao_dir)
    assert df.shape[0] == 0
    # Schema preservado mesmo vazio
    assert "indice_volatilidade" in df.columns


def test_extrator_sem_grafo_zera_centralidade(tmp_path: Path) -> None:
    """Sem ``metricas_rede.json`` -> centralidade=0.0 mas mantém features de S33."""
    sessao_dir = tmp_path / "sem_grafo"
    _gravar_artefatos(
        sessao_dir,
        historico=_historico_sintetico(n_parlamentares=10),
        # rede e classif omitidos
    )
    df = ExtratorFeatures.extrair(sessao_dir)
    assert df.shape[0] == 10  # noqa: PLR2004
    # Centralidades zeradas
    assert float(df["centralidade_grau"].sum() or 0.0) == pytest.approx(0.0)
    assert float(df["centralidade_intermediacao"].sum() or 0.0) == pytest.approx(0.0)
    # proporcao_sim_topico zerada (sem classificação)
    assert float(df["proporcao_sim_topico"].sum() or 0.0) == pytest.approx(0.0)
    # Mas indice_volatilidade preservado
    assert float(df["indice_volatilidade"].sum() or 0.0) > 0.0


def test_extrator_grafo_skipped_zera_centralidade(tmp_path: Path) -> None:
    """``metricas_rede.json`` com ``voto.skipped=True`` -> centralidade=0."""
    sessao_dir = tmp_path / "grafo_skipped"
    rede_skipped: dict[str, object] = {
        "coautoria": {"skipped": True, "motivo": "x"},
        "voto": {"skipped": True, "motivo": "amostra insuficiente"},
    }
    _gravar_artefatos(
        sessao_dir,
        historico=_historico_sintetico(n_parlamentares=5),
        rede=rede_skipped,
    )
    df = ExtratorFeatures.extrair(sessao_dir)
    assert df.shape[0] == 5  # noqa: PLR2004
    assert float(df["centralidade_grau"].sum() or 0.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# ModeloConvertibilidade -- treino
# ---------------------------------------------------------------------------


def _criar_dataset_balanceado(n: int = 40) -> tuple[pl.DataFrame, pl.Series]:
    """Constrói X + y sintético com sinal aprendível e duas classes."""
    linhas: list[dict[str, float]] = []
    targets: list[int] = []
    for idx in range(n):
        eh_mudou = idx % 2 == 0
        # Quem mudou tem volatilidade alta e proporção_sim baixa.
        linhas.append(
            {
                "indice_volatilidade": 0.7 + (idx % 3) * 0.05 if eh_mudou else 0.1,
                "centralidade_grau": 0.4 if eh_mudou else 0.1,
                "centralidade_intermediacao": 0.2 if eh_mudou else 0.05,
                "proporcao_sim_topico": 0.3 if eh_mudou else 0.8,
                "n_votos_topico": 20.0 if eh_mudou else 25.0,
            }
        )
        targets.append(1 if eh_mudou else 0)
    return pl.DataFrame(linhas), pl.Series("y", targets, dtype=pl.Int64)


def test_treinar_random_state_42_deterministico() -> None:
    """Dois treinos sucessivos com mesmo X/y produzem coeficientes idênticos.

    Sentinela de I3 (random_state fixo) -- se alguém remover o
    ``random_state=42`` em algum dos pontos, o teste quebra com
    valores ligeiramente diferentes.
    """
    x, y = _criar_dataset_balanceado(n=60)
    m1 = ModeloConvertibilidade.treinar(x, y)
    m2 = ModeloConvertibilidade.treinar(x, y)
    assert m1.coeficientes() == m2.coeficientes()
    assert m1.metricas == m2.metricas


def test_treinar_metricas_no_intervalo() -> None:
    """accuracy/precision/recall/f1/roc_auc estão em [0, 1]; n_treino+n_teste = n."""
    x, y = _criar_dataset_balanceado(n=50)
    modelo = ModeloConvertibilidade.treinar(x, y)
    for chave in ("accuracy", "precision", "recall", "f1", "roc_auc"):
        valor = modelo.metricas[chave]
        assert 0.0 <= valor <= 1.0, f"{chave}={valor} fora de [0, 1]"
    assert modelo.metricas["n_treino"] + modelo.metricas["n_teste"] == 50  # noqa: PLR2004
    # Sinal forte no dataset sintético -> accuracy alta esperada
    assert modelo.metricas["accuracy"] >= 0.7  # noqa: PLR2004


def test_prever_proba_no_intervalo_zero_um() -> None:
    """``prever_proba`` retorna pl.Series com valores em [0, 1]."""
    x, y = _criar_dataset_balanceado(n=50)
    modelo = ModeloConvertibilidade.treinar(x, y)
    proba = modelo.prever_proba(x)
    assert isinstance(proba, pl.Series)
    assert proba.dtype == pl.Float64
    assert len(proba) == 50  # noqa: PLR2004
    valores = [float(v) for v in proba.to_list() if v is not None]
    assert min(valores) >= 0.0
    assert max(valores) <= 1.0


def test_treinar_amostra_insuficiente() -> None:
    """``len(X) < MIN_AMOSTRA`` levanta :class:`AmostraInsuficiente`."""
    x, y = _criar_dataset_balanceado(n=MIN_AMOSTRA - 1)
    with pytest.raises(AmostraInsuficiente, match="amostra insuficiente"):
        ModeloConvertibilidade.treinar(x, y)


def test_treinar_monoclasse_levanta() -> None:
    """y com 1 só classe levanta :class:`AmostraInsuficiente`."""
    x, _ = _criar_dataset_balanceado(n=50)
    y_monoclasse = pl.Series("y", [0] * 50, dtype=pl.Int64)
    with pytest.raises(AmostraInsuficiente, match="apenas 1 classe"):
        ModeloConvertibilidade.treinar(x, y_monoclasse)


def test_coeficientes_dict_com_feature_names() -> None:
    """``coeficientes()`` retorna dict {feature: float} na ordem de feature_names."""
    x, y = _criar_dataset_balanceado(n=50)
    modelo = ModeloConvertibilidade.treinar(x, y)
    coefs = modelo.coeficientes()
    assert set(coefs.keys()) == set(FEATURE_NAMES_PADRAO)
    for v in coefs.values():
        assert isinstance(v, float)


# ---------------------------------------------------------------------------
# Persistência (joblib + meta.json + SHA256)
# ---------------------------------------------------------------------------


def test_salvar_carregar_round_trip(tmp_path: Path) -> None:
    """Salvar + carregar produz modelo equivalente; predict_proba idêntico."""
    x, y = _criar_dataset_balanceado(n=50)
    modelo = ModeloConvertibilidade.treinar(x, y)
    proba_orig = modelo.prever_proba(x).to_list()

    dir_destino = tmp_path / "modelo"
    meta = modelo.salvar(dir_destino)
    assert (dir_destino / "convertibilidade.joblib").is_file()
    assert (dir_destino / "convertibilidade.meta.json").is_file()
    assert "hash_sha256" in meta
    assert len(str(meta["hash_sha256"])) == 64  # noqa: PLR2004 -- SHA256 hex

    modelo_re = ModeloConvertibilidade.carregar(dir_destino)
    proba_re = modelo_re.prever_proba(x).to_list()
    assert proba_re == proba_orig
    assert modelo_re.feature_names == modelo.feature_names


def test_carregar_integridade_violada_hash(tmp_path: Path) -> None:
    """Adulterar o joblib após salvar -> :class:`IntegridadeViolada`."""
    x, y = _criar_dataset_balanceado(n=40)
    modelo = ModeloConvertibilidade.treinar(x, y)
    dir_destino = tmp_path / "modelo_corrompido"
    modelo.salvar(dir_destino)

    bin_path = dir_destino / "convertibilidade.joblib"
    # Adultera 1 byte no fim
    conteudo = bin_path.read_bytes()
    bin_path.write_bytes(conteudo + b"\x00")

    with pytest.raises(IntegridadeViolada, match="Hash divergente"):
        ModeloConvertibilidade.carregar(dir_destino)


def test_carregar_arquivo_ausente(tmp_path: Path) -> None:
    """``carregar`` em diretório vazio levanta FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="ausente"):
        ModeloConvertibilidade.carregar(tmp_path)


# ---------------------------------------------------------------------------
# treinar_convertibilidade_sessao -- helper end-to-end
# ---------------------------------------------------------------------------


def test_treinar_sessao_amostra_insuficiente_skipped(tmp_path: Path) -> None:
    """Sessão com < 30 parlamentares -> SKIPPED graceful (não levanta)."""
    sessao_dir = tmp_path / "small"
    _gravar_artefatos(
        sessao_dir,
        historico=_historico_sintetico(n_parlamentares=10, n_com_mudancas=5),
        rede=_metricas_rede_sinteticas(n_top=10),
        classif=_classificacao_sintetica(n=10),
    )
    resultado = treinar_convertibilidade_sessao(sessao_dir, top_n=10)
    assert resultado["skipped"] is True
    assert "amostra insuficiente" in str(resultado["motivo"]).lower()
    assert resultado["scores"] == []


def test_treinar_sessao_sem_artefatos_skipped(tmp_path: Path) -> None:
    """Sessão sem nenhum artefato -> SKIPPED graceful com motivo claro."""
    sessao_dir = tmp_path / "sem_nada"
    sessao_dir.mkdir()
    resultado = treinar_convertibilidade_sessao(sessao_dir)
    assert resultado["skipped"] is True
    assert "features vazias" in str(resultado["motivo"]).lower()


def test_extrator_ignora_entradas_invalidas(tmp_path: Path) -> None:
    """Entradas com tipo errado em qualquer artefato são ignoradas sem quebrar."""
    sessao_dir = tmp_path / "garbage"
    sessao_dir.mkdir()
    historico = {
        "parlamentares": {
            "abc": {"casa": "camara", "indice_volatilidade": 0.5, "mudancas_detectadas": []},
            "999": "string em vez de dict",
            "200": {
                "casa": "senado",
                "nome": "Sen",
                "indice_volatilidade": 0.3,
                "mudancas_detectadas": [],
            },
        },
        "metadata": {"skipped": False},
    }
    rede: dict[str, object] = {
        "voto": {
            "skipped": False,
            "top_centrais": [
                "string solta",  # ignorado
                {"id": 200, "centralidade_grau": 0.4},  # usa "id" como fallback
                {"sem_id": True},  # ignorado
            ],
        }
    }
    classif: dict[str, object] = {
        "top_a_favor": ["nao-dict", {"id": 200, "pct_a_favor": 0.6, "n_votos": 5}],
        "top_contra": [{"sem_id": 1}],
    }
    _gravar_artefatos(sessao_dir, historico=historico, rede=rede, classif=classif)
    df = ExtratorFeatures.extrair(sessao_dir)
    # 1 parlamentar válido (200); abc não é int, 999 não é dict
    assert df.shape[0] == 1
    assert df["parlamentar_id"][0] == 200  # noqa: PLR2004
    # Centralidade resgatada via "id" fallback
    assert float(df["centralidade_grau"][0]) == pytest.approx(0.4)
    # proporcao via pct_a_favor
    assert float(df["proporcao_sim_topico"][0]) == pytest.approx(0.6)


def test_extrator_json_corrompido_skip(tmp_path: Path) -> None:
    """JSON malformado em qualquer artefato vira skip graceful."""
    sessao_dir = tmp_path / "json_quebrado"
    sessao_dir.mkdir()
    (sessao_dir / "historico_conversao.json").write_text("{ json invalido", encoding="utf-8")
    df = ExtratorFeatures.extrair(sessao_dir)
    assert df.shape[0] == 0


def test_carregar_versao_incompativel(tmp_path: Path) -> None:
    """Meta com ``versao`` diferente -> :class:`IntegridadeViolada`."""
    x, y = _criar_dataset_balanceado(n=40)
    modelo = ModeloConvertibilidade.treinar(x, y)
    dir_destino = tmp_path / "modelo_v0"
    modelo.salvar(dir_destino)

    # Adultera meta.json para versão antiga
    meta_path = dir_destino / "convertibilidade.meta.json"
    import json as _json

    meta = _json.loads(meta_path.read_text(encoding="utf-8"))
    meta["versao"] = "0"
    meta_path.write_text(_json.dumps(meta), encoding="utf-8")

    with pytest.raises(IntegridadeViolada, match="Versão incompatível"):
        ModeloConvertibilidade.carregar(dir_destino)


def test_prever_proba_dataframe_vazio() -> None:
    """``prever_proba`` em DataFrame vazio retorna Series vazio sem erro."""
    x, y = _criar_dataset_balanceado(n=40)
    modelo = ModeloConvertibilidade.treinar(x, y)
    df_vazio = pl.DataFrame(
        schema={
            "indice_volatilidade": pl.Float64,
            "centralidade_grau": pl.Float64,
            "centralidade_intermediacao": pl.Float64,
            "proporcao_sim_topico": pl.Float64,
            "n_votos_topico": pl.Int64,
        }
    )
    proba = modelo.prever_proba(df_vazio)
    assert len(proba) == 0


def test_prever_proba_colunas_ausentes_levanta() -> None:
    """``prever_proba`` com colunas faltantes levanta ValueError."""
    x, y = _criar_dataset_balanceado(n=40)
    modelo = ModeloConvertibilidade.treinar(x, y)
    df_incompleto = x.drop("indice_volatilidade")
    with pytest.raises(ValueError, match="colunas ausentes"):
        modelo.prever_proba(df_incompleto)


def test_treinar_colunas_ausentes_levanta() -> None:
    """``treinar`` com X sem coluna esperada levanta AmostraInsuficiente."""
    x_falta = pl.DataFrame(
        {
            "indice_volatilidade": [0.5] * 40,
            "centralidade_grau": [0.1] * 40,
            # faltam: centralidade_intermediacao, proporcao_sim_topico, n_votos_topico
        }
    )
    y = pl.Series("y", [0, 1] * 20, dtype=pl.Int64)
    with pytest.raises(AmostraInsuficiente, match="colunas ausentes"):
        ModeloConvertibilidade.treinar(x_falta, y)


def test_treinar_sessao_sucesso_persiste_artefatos(tmp_path: Path) -> None:
    """Sessão com features suficientes -> treina, persiste e ranqueia."""
    sessao_dir = tmp_path / "ok"
    _gravar_artefatos(
        sessao_dir,
        historico=_historico_sintetico(n_parlamentares=40, n_com_mudancas=20),
        rede=_metricas_rede_sinteticas(n_top=30),
        classif=_classificacao_sintetica(n=40),
    )
    resultado = treinar_convertibilidade_sessao(sessao_dir, top_n=15)
    assert resultado["skipped"] is False
    assert resultado["n_amostra"] == 40  # noqa: PLR2004
    scores = resultado["scores"]
    assert isinstance(scores, list)
    assert len(scores) == 15  # noqa: PLR2004 -- top_n
    # Ordenado por proba desc
    probas = [float(s["proba"]) for s in scores if isinstance(s, dict)]
    assert probas == sorted(probas, reverse=True)
    # Artefatos persistidos
    assert (sessao_dir / "convertibilidade_scores.json").is_file()
    assert (sessao_dir / "modelo_convertibilidade" / "convertibilidade.joblib").is_file()
    assert (sessao_dir / "modelo_convertibilidade" / "convertibilidade.meta.json").is_file()
