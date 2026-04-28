"""Testes unit do :mod:`hemiciclo.sessao.pipeline` (S30).

Mocks AGRESSIVOS dos 5 subsistemas (coleta Câmara, coleta Senado,
consolidador ETL, classificador C1+C2 e modelo base C3) para garantir
que o orquestrador integra corretamente sem chamar rede ou modelo
pesado em CI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hemiciclo.sessao.modelo import (
    Camada,
    Casa,
    EstadoSessao,
    ParametrosBusca,
)
from hemiciclo.sessao.persistencia import carregar_status
from hemiciclo.sessao.pipeline import (
    LIMITACOES_CONHECIDAS,
    _gerar_manifesto,
    _resolver_topico,
    pipeline_real,
)
from hemiciclo.sessao.runner import SessaoRunner


def _params(
    camadas: list[Camada] | None = None,
    casas: list[Casa] | None = None,
    max_itens: int | None = None,
) -> ParametrosBusca:
    """Builder reutilizável de ParametrosBusca para os testes."""
    return ParametrosBusca(
        topico="aborto",
        casas=casas if casas is not None else [Casa.CAMARA],
        legislaturas=[57],
        camadas=camadas if camadas is not None else [Camada.REGEX, Camada.VOTOS],
        max_itens=max_itens,
    )


def _mocks_padrao(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Aplica os 5 mocks centrais e retorna referência a cada um."""
    mocks: dict[str, MagicMock] = {
        "camara": MagicMock(),
        "senado": MagicMock(),
        "etl": MagicMock(return_value={"proposicoes": 10}),
        "classificar": MagicMock(
            return_value={
                "topico": "aborto",
                "n_props": 5,
                "n_parlamentares": 3,
                "top_a_favor": [{"nome": "X"}],
                "top_contra": [{"nome": "Y"}],
            }
        ),
        "embeddings_disponivel": MagicMock(return_value=False),
        "carregar_modelo_base": MagicMock(),
    }
    monkeypatch.setattr("hemiciclo.coleta.camara.executar_coleta", mocks["camara"])
    monkeypatch.setattr("hemiciclo.coleta.senado.executar_coleta", mocks["senado"])
    monkeypatch.setattr(
        "hemiciclo.etl.consolidador.consolidar_parquets_em_duckdb",
        mocks["etl"],
    )
    monkeypatch.setattr("hemiciclo.modelos.classificador.classificar", mocks["classificar"])
    monkeypatch.setattr(
        "hemiciclo.modelos.embeddings.embeddings_disponivel",
        mocks["embeddings_disponivel"],
    )
    monkeypatch.setattr(
        "hemiciclo.modelos.persistencia_modelo.carregar_modelo_base",
        mocks["carregar_modelo_base"],
    )
    return mocks


def test_pipeline_real_atualiza_status_em_cada_etapa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_hemiciclo_home: Path
) -> None:
    """Pipeline atravessa estados COLETANDO -> ETL -> EMBEDDINGS -> CONCLUIDA."""
    _mocks_padrao(monkeypatch)
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    runner = SessaoRunner(
        tmp_hemiciclo_home,
        _params([Camada.REGEX, Camada.VOTOS, Camada.EMBEDDINGS]),
    )
    pipeline_real(runner.params, runner.dir, runner._spawn_updater())  # type: ignore[attr-defined] # noqa: SLF001

    status = carregar_status(runner.dir / "status.json")
    assert status is not None
    assert status.estado == EstadoSessao.CONCLUIDA
    assert status.progresso_pct == 100.0


def test_etapa_coleta_chama_coletor_correto_por_casa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_hemiciclo_home: Path
) -> None:
    """Câmara em params -> só executar_coleta da Câmara é chamado."""
    mocks = _mocks_padrao(monkeypatch)
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    runner = SessaoRunner(tmp_hemiciclo_home, _params(casas=[Casa.CAMARA]))
    pipeline_real(runner.params, runner.dir, runner._spawn_updater())  # type: ignore[attr-defined] # noqa: SLF001

    assert mocks["camara"].call_count == 1
    assert mocks["senado"].call_count == 0


def test_etapa_coleta_chama_camara_e_senado_quando_ambas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_hemiciclo_home: Path
) -> None:
    """Ambas as casas -> dois coletores chamados."""
    mocks = _mocks_padrao(monkeypatch)
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    runner = SessaoRunner(tmp_hemiciclo_home, _params(casas=[Casa.CAMARA, Casa.SENADO]))
    pipeline_real(runner.params, runner.dir, runner._spawn_updater())  # type: ignore[attr-defined] # noqa: SLF001

    assert mocks["camara"].call_count == 1
    assert mocks["senado"].call_count == 1


# ---------------------------------------------------------------------------
# S30.1 -- propagação de max_itens da CLI para os coletores
# ---------------------------------------------------------------------------


def test_max_itens_default_none_preserva_comportamento_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_hemiciclo_home: Path
) -> None:
    """Sem ``--max-itens`` o coletor recebe ``params_coleta.max_itens is None``."""
    mocks = _mocks_padrao(monkeypatch)
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    runner = SessaoRunner(tmp_hemiciclo_home, _params(casas=[Casa.CAMARA]))
    assert runner.params.max_itens is None
    pipeline_real(runner.params, runner.dir, runner._spawn_updater())  # type: ignore[attr-defined] # noqa: SLF001

    assert mocks["camara"].call_count == 1
    args, _kwargs = mocks["camara"].call_args
    params_coleta = args[0]
    assert params_coleta.max_itens is None


def test_max_itens_valor_propaga_em_camara_e_senado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_hemiciclo_home: Path
) -> None:
    """``max_itens=10`` chega aos dois coletores reais com valor 10."""
    mocks = _mocks_padrao(monkeypatch)
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    runner = SessaoRunner(
        tmp_hemiciclo_home,
        _params(casas=[Casa.CAMARA, Casa.SENADO], max_itens=10),
    )
    pipeline_real(runner.params, runner.dir, runner._spawn_updater())  # type: ignore[attr-defined] # noqa: SLF001

    assert mocks["camara"].call_count == 1
    assert mocks["senado"].call_count == 1
    params_camara = mocks["camara"].call_args[0][0]
    params_senado = mocks["senado"].call_args[0][0]
    assert params_camara.max_itens == 10
    assert params_senado.max_itens == 10


def test_max_itens_zero_rejeitado_pydantic() -> None:
    """``max_itens=0`` é absurdo (use ``None`` para sem limite)."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ParametrosBusca(
            topico="aborto",
            casas=[Casa.CAMARA],
            legislaturas=[57],
            max_itens=0,
        )


def test_max_itens_negativo_rejeitado_pydantic() -> None:
    """``max_itens=-5`` rejeitado pelo validador ``ge=1``."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ParametrosBusca(
            topico="aborto",
            casas=[Casa.CAMARA],
            legislaturas=[57],
            max_itens=-5,
        )


def test_etapa_etl_e_classificacao_nao_recebem_max_itens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_hemiciclo_home: Path
) -> None:
    """Out-of-scope §3.2: ETL e C1+C2 nunca recebem kwarg ``max_itens``."""
    mocks = _mocks_padrao(monkeypatch)
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    runner = SessaoRunner(tmp_hemiciclo_home, _params(max_itens=42))
    pipeline_real(runner.params, runner.dir, runner._spawn_updater())  # type: ignore[attr-defined] # noqa: SLF001

    # ETL: assinatura posicional; nenhum kwarg ``max_itens`` aceitável
    assert mocks["etl"].call_count == 1
    _etl_args, etl_kwargs = mocks["etl"].call_args
    assert "max_itens" not in etl_kwargs

    # Classificador: kwargs cheios, mas sem ``max_itens``
    assert mocks["classificar"].call_count == 1
    _cls_args, cls_kwargs = mocks["classificar"].call_args
    assert "max_itens" not in cls_kwargs


def test_etapa_etl_consolida_parquets_em_duckdb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_hemiciclo_home: Path
) -> None:
    """ETL é chamado com (sessao_dir/raw, sessao_dir/dados.duckdb)."""
    mocks = _mocks_padrao(monkeypatch)
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    runner = SessaoRunner(tmp_hemiciclo_home, _params())
    pipeline_real(runner.params, runner.dir, runner._spawn_updater())  # type: ignore[attr-defined] # noqa: SLF001

    assert mocks["etl"].call_count == 1
    args, _kwargs = mocks["etl"].call_args
    raw_arg, db_arg = args
    assert raw_arg == runner.dir / "raw"
    assert db_arg == runner.dir / "dados.duckdb"


def test_etapa_classificacao_chama_c1_c2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_hemiciclo_home: Path
) -> None:
    """classificar() recebe topico_yaml resolvido + db_path da sessão."""
    mocks = _mocks_padrao(monkeypatch)
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    runner = SessaoRunner(tmp_hemiciclo_home, _params())
    pipeline_real(runner.params, runner.dir, runner._spawn_updater())  # type: ignore[attr-defined] # noqa: SLF001

    assert mocks["classificar"].call_count == 1
    _, kwargs = mocks["classificar"].call_args
    assert kwargs["topico_yaml"].name == "aborto.yaml"
    assert kwargs["db_path"] == runner.dir / "dados.duckdb"
    assert kwargs["camadas"] == ["regex", "votos", "tfidf"]
    # Persistência intermediária criada
    assert (runner.dir / "classificacao_c1_c2.json").exists()


def test_etapa_embeddings_skipped_se_modelo_ausente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_hemiciclo_home: Path
) -> None:
    """Sem bge-m3 disponível, etapa C3 marca SKIPPED + sessão segue concluindo."""
    mocks = _mocks_padrao(monkeypatch)
    mocks["embeddings_disponivel"].return_value = False
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    runner = SessaoRunner(
        tmp_hemiciclo_home,
        _params([Camada.REGEX, Camada.VOTOS, Camada.EMBEDDINGS]),
    )
    pipeline_real(runner.params, runner.dir, runner._spawn_updater())  # type: ignore[attr-defined] # noqa: SLF001

    c3_status = json.loads((runner.dir / "c3_status.json").read_text(encoding="utf-8"))
    assert c3_status["skipped"] is True
    assert "bge-m3" in c3_status["motivo"]

    status = carregar_status(runner.dir / "status.json")
    assert status is not None
    assert status.estado == EstadoSessao.CONCLUIDA


def test_etapa_embeddings_skipped_se_base_nao_treinado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_hemiciclo_home: Path
) -> None:
    """bge-m3 disponível mas modelo base ausente -> SKIPPED com motivo claro."""
    mocks = _mocks_padrao(monkeypatch)
    mocks["embeddings_disponivel"].return_value = True
    mocks["carregar_modelo_base"].side_effect = FileNotFoundError("nada")
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    runner = SessaoRunner(
        tmp_hemiciclo_home,
        _params([Camada.REGEX, Camada.VOTOS, Camada.EMBEDDINGS]),
    )
    pipeline_real(runner.params, runner.dir, runner._spawn_updater())  # type: ignore[attr-defined] # noqa: SLF001

    c3_status = json.loads((runner.dir / "c3_status.json").read_text(encoding="utf-8"))
    assert c3_status["skipped"] is True
    assert "modelo base" in c3_status["motivo"].lower()


def test_etapa_persiste_relatorio_e_manifesto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_hemiciclo_home: Path
) -> None:
    """relatorio_state.json + manifesto.json gerados com SHA256 16-char + limitacoes."""
    _mocks_padrao(monkeypatch)
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    runner = SessaoRunner(tmp_hemiciclo_home, _params())
    pipeline_real(runner.params, runner.dir, runner._spawn_updater())  # type: ignore[attr-defined] # noqa: SLF001

    relatorio = json.loads((runner.dir / "relatorio_state.json").read_text(encoding="utf-8"))
    assert relatorio["topico"] == "aborto"
    assert relatorio["n_props"] == 5
    assert relatorio["n_parlamentares"] == 3

    manifesto = json.loads((runner.dir / "manifesto.json").read_text(encoding="utf-8"))
    assert manifesto["versao_pipeline"] == "1"
    assert sorted(manifesto["limitacoes_conhecidas"]) == sorted(list(LIMITACOES_CONHECIDAS))
    # Hashes têm 16 chars (precedente S24/S25 confirmado em S25.1)
    for sha in manifesto["artefatos"].values():
        assert len(sha) == 16
        assert all(c in "0123456789abcdef" for c in sha)


def test_falha_api_marca_erro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_hemiciclo_home: Path
) -> None:
    """API offline (RuntimeError no coletor) -> sessão fica em ERRO."""
    mocks = _mocks_padrao(monkeypatch)
    mocks["camara"].side_effect = RuntimeError("API offline")
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    runner = SessaoRunner(tmp_hemiciclo_home, _params())
    with pytest.raises(RuntimeError, match="API offline"):
        pipeline_real(runner.params, runner.dir, runner._spawn_updater())  # type: ignore[attr-defined] # noqa: SLF001

    status = carregar_status(runner.dir / "status.json")
    assert status is not None
    assert status.estado == EstadoSessao.ERRO
    assert status.erro is not None
    assert "RuntimeError" in status.erro


def test_topico_inexistente_falha_antes_de_coleta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_hemiciclo_home: Path
) -> None:
    """Tópico ausente -> ERRO sem chamar nenhum coletor."""
    mocks = _mocks_padrao(monkeypatch)
    monkeypatch.chdir(tmp_path)  # cwd sem topicos/aborto.yaml

    params = ParametrosBusca(
        topico="aborto_inexistente_xyz",
        casas=[Casa.CAMARA],
        legislaturas=[57],
    )
    runner = SessaoRunner(tmp_hemiciclo_home, params)
    with pytest.raises(FileNotFoundError):
        pipeline_real(runner.params, runner.dir, runner._spawn_updater())  # type: ignore[attr-defined] # noqa: SLF001

    assert mocks["camara"].call_count == 0
    assert mocks["senado"].call_count == 0
    status = carregar_status(runner.dir / "status.json")
    assert status is not None
    assert status.estado == EstadoSessao.ERRO


def test_resolver_topico_aceita_path_absoluto(tmp_path: Path) -> None:
    """``_resolver_topico`` aceita path absoluto pra YAML existente."""
    arq = tmp_path / "x.yaml"
    arq.write_text("nome: x\n", encoding="utf-8")
    assert _resolver_topico(str(arq)) == arq


def test_resolver_topico_aceita_slug_em_topicos_repo() -> None:
    """``_resolver_topico`` resolve slug ``aborto`` para ``topicos/aborto.yaml``."""
    raiz = Path(__file__).resolve().parents[2]
    import os

    cwd_orig = Path.cwd()
    os.chdir(raiz)
    try:
        resolvido = _resolver_topico("aborto")
    finally:
        os.chdir(cwd_orig)
    assert resolvido.name == "aborto.yaml"


def test_resolver_topico_levanta_se_inexistente(tmp_path: Path) -> None:
    """``_resolver_topico`` levanta FileNotFoundError para slug ausente."""
    import os

    cwd_orig = Path.cwd()
    os.chdir(tmp_path)
    try:
        with pytest.raises(FileNotFoundError):
            _resolver_topico("topico_que_nao_existe_xyz")
    finally:
        os.chdir(cwd_orig)


def test_gerar_manifesto_ignora_self(tmp_path: Path) -> None:
    """``manifesto.json`` não inclui o próprio arquivo nos artefatos."""
    (tmp_path / "x.parquet").write_bytes(b"abc")
    (tmp_path / "manifesto.json").write_text("{}", encoding="utf-8")
    manifesto = _gerar_manifesto(tmp_path)
    assert "x.parquet" in manifesto["artefatos"]
    assert "manifesto.json" not in manifesto["artefatos"]


def test_gerar_manifesto_inclui_apenas_extensoes_alvo(tmp_path: Path) -> None:
    """Apenas .parquet, .duckdb e .json entram em ``artefatos``."""
    (tmp_path / "a.parquet").write_bytes(b"a")
    (tmp_path / "b.duckdb").write_bytes(b"b")
    (tmp_path / "c.json").write_text("{}", encoding="utf-8")
    (tmp_path / "ignorar.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "log.log").write_text("hi", encoding="utf-8")
    manifesto = _gerar_manifesto(tmp_path)
    chaves = set(manifesto["artefatos"].keys())
    assert chaves == {"a.parquet", "b.duckdb", "c.json"}


# ---------------------------------------------------------------------------
# Helper interno para os testes -- adiciona método utilitário ao runner.
# ---------------------------------------------------------------------------


def _spawn_updater(self) -> Any:  # noqa: ANN001 -- monkey-patch helper
    """Cria StatusUpdater compatível com o runner desta sessão."""
    from hemiciclo.sessao.runner import StatusUpdater

    return StatusUpdater(self.dir, self.id_sessao)


# Patcheia o método nos testes (não altera a classe em produção).
SessaoRunner._spawn_updater = _spawn_updater  # type: ignore[attr-defined]
