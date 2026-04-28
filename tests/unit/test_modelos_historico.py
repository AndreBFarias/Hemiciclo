"""Testes unit do módulo ``hemiciclo.modelos.historico`` (S33).

Cobre:

- :class:`HistoricoConversao` -- granularidades ano/legislatura, posição
  dominante, skip graceful, validação de granularidade inválida.
- :class:`DetectorMudancas` -- threshold padrão (30 pp), threshold
  customizado, < 2 buckets retorna lista vazia.
- :class:`IndiceVolatilidade` -- série constante = 0.0, série binária
  alternada = 1.0 saturada, < 2 buckets = 0.0.
- :func:`calcular_historico_top` -- batch sobre top N e skip graceful
  por DB sem votos.
"""

from __future__ import annotations

import duckdb
import polars as pl
import pytest

from hemiciclo.etl.migrations import aplicar_migrations
from hemiciclo.modelos.historico import (
    THRESHOLD_PP_PADRAO,
    AmostraInsuficiente,
    DetectorMudancas,
    HistoricoConversao,
    IndiceVolatilidade,
    calcular_historico_top,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _criar_db_com_votos_temporais() -> duckdb.DuckDBPyConnection:
    """DB em memória com 3 parlamentares votando em 4 anos distintos.

    Layout determinístico:

    - Parlamentar 1 (PT/SP) em 2018-2019-2022-2024: 80% SIM em 2018,
      80% SIM em 2019 (consistente), 20% SIM em 2022 (mudou), 20% SIM em
      2024 (consistente). Volatilidade alta entre 2019 e 2022.
    - Parlamentar 2 (PL/RJ) em 2018-2019-2022-2024: 100% SIM sempre
      (volatilidade 0).
    - Parlamentar 3 (PSOL/SP) em 2018: só 1 ano (skip por < 2 buckets).
    """
    conn = duckdb.connect(":memory:")
    aplicar_migrations(conn)

    for pid, partido, uf in (
        (101, "PT", "SP"),
        (102, "PL", "RJ"),
        (103, "PSOL", "SP"),
    ):
        conn.execute(
            "INSERT INTO parlamentares (id, casa, nome, partido, uf, ativo) "
            "VALUES (?, 'camara', ?, ?, ?, TRUE)",
            [pid, f"Parlamentar {pid}", partido, uf],
        )

    # 4 anos x 10 votações cada
    anos_votacoes = (
        ("2018", "2018-03-15"),
        ("2019", "2019-04-20"),
        ("2022", "2022-09-10"),
        ("2024", "2024-05-05"),
    )
    votacao_id = 1
    for ano_label, data_iso in anos_votacoes:
        for _ in range(10):
            conn.execute(
                "INSERT INTO votacoes (id, casa, data, descricao, resultado) "
                "VALUES (?, 'camara', ?, ?, 'aprovado')",
                [f"v{votacao_id}", data_iso, f"Votacao {ano_label} #{votacao_id}"],
            )
            # P101: 80% SIM em 2018-2019, 20% SIM em 2022-2024
            indice_no_ano = (votacao_id - 1) % 10
            if ano_label in {"2018", "2019"}:
                voto_p101 = "Sim" if indice_no_ano < 8 else "Nao"  # noqa: PLR2004
            else:
                voto_p101 = "Sim" if indice_no_ano < 2 else "Nao"  # noqa: PLR2004
            conn.execute(
                "INSERT INTO votos (votacao_id, parlamentar_id, casa, voto, data) "
                "VALUES (?, 101, 'camara', ?, ?)",
                [f"v{votacao_id}", voto_p101, data_iso],
            )
            # P102: sempre SIM
            conn.execute(
                "INSERT INTO votos (votacao_id, parlamentar_id, casa, voto, data) "
                "VALUES (?, 102, 'camara', 'Sim', ?)",
                [f"v{votacao_id}", data_iso],
            )
            # P103: só vota em 2018
            if ano_label == "2018":
                conn.execute(
                    "INSERT INTO votos (votacao_id, parlamentar_id, casa, voto, data) "
                    "VALUES (?, 103, 'camara', 'Nao', ?)",
                    [f"v{votacao_id}", data_iso],
                )
            votacao_id += 1
    return conn


def _criar_db_vazio() -> duckdb.DuckDBPyConnection:
    """DB com schema mas sem votos."""
    conn = duckdb.connect(":memory:")
    aplicar_migrations(conn)
    return conn


# ---------------------------------------------------------------------------
# HistoricoConversao
# ---------------------------------------------------------------------------


def test_historico_conversao_agrupa_por_ano() -> None:
    """Granularidade ``ano`` retorna 4 buckets pra parlamentar com votos
    em 4 anos distintos."""
    conn = _criar_db_com_votos_temporais()
    try:
        df = HistoricoConversao.calcular(conn, 101, "camara", granularidade="ano")
        assert isinstance(df, pl.DataFrame)
        assert df.shape[0] == 4
        assert df["bucket"].to_list() == [2018, 2019, 2022, 2024]
        # 80% SIM em 2018-2019, 20% em 2022-2024
        assert df["proporcao_sim"][0] == pytest.approx(0.8)
        assert df["proporcao_sim"][2] == pytest.approx(0.2)
        # Coluna posicao_dominante presente
        assert "posicao_dominante" in df.columns
    finally:
        conn.close()


def test_historico_conversao_agrupa_por_legislatura() -> None:
    """Granularidade ``legislatura`` mapeia 2018->55, 2019/2022->56, 2024->57."""
    conn = _criar_db_com_votos_temporais()
    try:
        df = HistoricoConversao.calcular(conn, 101, "camara", granularidade="legislatura")
        # 4 anos x 10 votos = 40; cai em legislaturas 55 (2018: 10 votos),
        # 56 (2019+2022: 20 votos), 57 (2024: 10 votos)
        assert df.shape[0] == 3
        assert df["bucket"].to_list() == [55, 56, 57]
        # n_votos: 10, 20, 10
        assert df["n_votos"].to_list() == [10, 20, 10]
    finally:
        conn.close()


def test_posicao_dominante_a_favor_contra_neutro() -> None:
    """Limiares 0.70/0.30 produzem ``a_favor``, ``contra`` e ``neutro``."""
    conn = _criar_db_com_votos_temporais()
    try:
        # P101 ano 2018: 0.80 -> a_favor
        df_p101 = HistoricoConversao.calcular(conn, 101, "camara")
        assert df_p101.filter(pl.col("bucket") == 2018)["posicao_dominante"][0] == "a_favor"
        # P101 ano 2022: 0.20 -> contra
        assert df_p101.filter(pl.col("bucket") == 2022)["posicao_dominante"][0] == "contra"
        # P102: 1.0 -> sempre a_favor
        df_p102 = HistoricoConversao.calcular(conn, 102, "camara")
        for posicao in df_p102["posicao_dominante"].to_list():
            assert posicao == "a_favor"
    finally:
        conn.close()


def test_historico_granularidade_invalida_levanta() -> None:
    """``granularidade='mes'`` levanta ``ValueError``."""
    conn = _criar_db_vazio()
    try:
        with pytest.raises(ValueError, match="granularidade"):
            HistoricoConversao.calcular(conn, 1, "camara", granularidade="mes")
    finally:
        conn.close()


def test_historico_tabela_votos_ausente_levanta() -> None:
    """Sem tabela ``votos`` levanta :class:`AmostraInsuficiente`."""
    conn = duckdb.connect(":memory:")
    try:
        with pytest.raises(AmostraInsuficiente, match="tabela votos ausente"):
            HistoricoConversao.calcular(conn, 1, "camara")
    finally:
        conn.close()


def test_historico_parlamentar_sem_votos_devolve_vazio() -> None:
    """Parlamentar inexistente retorna DataFrame vazio (não levanta)."""
    conn = _criar_db_com_votos_temporais()
    try:
        df = HistoricoConversao.calcular(conn, 999, "camara")
        assert df.shape[0] == 0
        # Schema preservado
        assert set(df.columns) == {
            "bucket",
            "n_votos",
            "proporcao_sim",
            "proporcao_nao",
            "posicao_dominante",
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# DetectorMudancas
# ---------------------------------------------------------------------------


def _df_historico(prop_sim: list[float]) -> pl.DataFrame:
    """Constrói DataFrame de histórico ad-hoc para testes do detector."""
    n = len(prop_sim)
    return pl.DataFrame(
        {
            "bucket": list(range(2020, 2020 + n)),
            "n_votos": [10] * n,
            "proporcao_sim": prop_sim,
            "proporcao_nao": [1.0 - p for p in prop_sim],
            "posicao_dominante": [
                "a_favor" if p >= 0.70 else "contra" if p <= 0.30 else "neutro"  # noqa: PLR2004
                for p in prop_sim
            ],
        }
    )


def test_detector_mudancas_threshold_padrao() -> None:
    """Mudança de 0.80 -> 0.20 (delta -60pp) é detectada com threshold padrão."""
    df = _df_historico([0.8, 0.8, 0.2, 0.2])
    eventos = DetectorMudancas.detectar(df)
    assert len(eventos) == 1
    e = eventos[0]
    assert e["bucket_anterior"] == 2021
    assert e["bucket_posterior"] == 2022
    assert e["delta_pp"] == pytest.approx(-60.0)
    assert e["posicao_anterior"] == "a_favor"
    assert e["posicao_posterior"] == "contra"


def test_detector_mudancas_threshold_customizado() -> None:
    """Threshold 10pp captura mudança que padrão (30pp) ignoraria."""
    df = _df_historico([0.5, 0.65])  # delta = +15pp
    eventos_padrao = DetectorMudancas.detectar(df, threshold_pp=THRESHOLD_PP_PADRAO)
    eventos_relax = DetectorMudancas.detectar(df, threshold_pp=10.0)
    assert len(eventos_padrao) == 0
    assert len(eventos_relax) == 1
    assert eventos_relax[0]["delta_pp"] == pytest.approx(15.0)


def test_detector_menos_de_2_buckets_retorna_vazio() -> None:
    """Histórico com 0 ou 1 bucket -> lista vazia, nunca falha."""
    assert DetectorMudancas.detectar(_df_historico([])) == []
    assert DetectorMudancas.detectar(_df_historico([0.5])) == []


# ---------------------------------------------------------------------------
# IndiceVolatilidade
# ---------------------------------------------------------------------------


def test_indice_volatilidade_consistente_zero() -> None:
    """Série constante 1.0 -> volatilidade 0."""
    df = _df_historico([1.0, 1.0, 1.0])
    assert IndiceVolatilidade.calcular(df) == pytest.approx(0.0)


def test_indice_volatilidade_erratico_alto() -> None:
    """Série alternando 0/1 -> volatilidade próxima de 1 (saturada)."""
    df = _df_historico([0.0, 1.0, 0.0, 1.0])
    valor = IndiceVolatilidade.calcular(df)
    # std populacional de [0,1,0,1] = 0.5; normalizado por 0.5 = 1.0
    assert valor == pytest.approx(1.0)


def test_indice_volatilidade_menos_de_2_buckets_zero() -> None:
    """< 2 buckets retorna 0 (não há variação possível)."""
    assert IndiceVolatilidade.calcular(_df_historico([])) == 0.0
    assert IndiceVolatilidade.calcular(_df_historico([0.5])) == 0.0


# ---------------------------------------------------------------------------
# calcular_historico_top (batch helper)
# ---------------------------------------------------------------------------


def test_calcular_historico_top_em_db_realista() -> None:
    """Batch sobre os top 5: retorna parlamentares com 2+ buckets."""
    conn = _criar_db_com_votos_temporais()
    try:
        resultado = calcular_historico_top(conn, top_n=5, granularidade="ano")
        meta = resultado["metadata"]
        parls = resultado["parlamentares"]
        assert isinstance(meta, dict)
        assert isinstance(parls, dict)
        # P101 e P102 têm 4 buckets cada; P103 só 1 bucket -> skip
        assert "101" in parls
        assert "102" in parls
        assert "103" not in parls
        # P101 deve ter alta volatilidade; P102 baixa
        bloco_p101 = parls["101"]
        bloco_p102 = parls["102"]
        assert isinstance(bloco_p101, dict)
        assert isinstance(bloco_p102, dict)
        assert float(bloco_p101["indice_volatilidade"]) > 0.5  # noqa: PLR2004
        assert float(bloco_p102["indice_volatilidade"]) == pytest.approx(0.0)
        # P101 deve ter ao menos 1 mudança detectada
        mudancas = bloco_p101["mudancas_detectadas"]
        assert isinstance(mudancas, list)
        assert len(mudancas) >= 1
        # metadata coerente
        assert meta["skipped"] is False
        assert meta["granularidade"] == "ano"
    finally:
        conn.close()


def test_calcular_historico_top_db_sem_votos_skipped() -> None:
    """DB sem dados de voto -> skip graceful, nunca levanta."""
    conn = _criar_db_vazio()
    try:
        resultado = calcular_historico_top(conn, top_n=10)
        meta = resultado["metadata"]
        assert isinstance(meta, dict)
        assert resultado["parlamentares"] == {}
        assert meta["skipped"] is True
        assert "motivo" in meta
    finally:
        conn.close()


def test_calcular_historico_top_tabela_ausente_skipped() -> None:
    """DB sem schema -> skip graceful com motivo 'tabela votos ausente'."""
    conn = duckdb.connect(":memory:")
    try:
        resultado = calcular_historico_top(conn, top_n=10)
        meta = resultado["metadata"]
        assert isinstance(meta, dict)
        assert meta["skipped"] is True
        assert "tabela votos ausente" in str(meta["motivo"])
    finally:
        conn.close()
