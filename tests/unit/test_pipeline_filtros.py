"""Testes do helper de filtro UF/partido do pipeline real (S30.2).

Cobre :func:`hemiciclo.sessao.pipeline._montar_clausula_subset_parlamentares`:

- Sentinela ``None`` quando ambos ufs/partidos são ``None``.
- Cláusulas SQL parametrizadas (defesa em profundidade vs injeção).
- ``UPPER(partido)`` defensivo para o histórico do Senado.
- Combinação ``ufs`` + ``partidos`` aplicando AND lógico.
- Logs ``WARNING`` em recortes vazios e estreitos.
- Curto-circuito do classificador quando subset é vazio.
"""

from __future__ import annotations

import duckdb
import polars as pl
import pytest

from hemiciclo.etl.migrations import aplicar_migrations
from hemiciclo.modelos.classificador_c1 import agregar_voto_por_parlamentar
from hemiciclo.sessao.pipeline import _montar_clausula_subset_parlamentares


def _conn_com_parlamentares() -> duckdb.DuckDBPyConnection:
    """Conexão DuckDB em memória com cadastro sintético de parlamentares.

    15 parlamentares cobrindo combinações:
    - SP/PT (3), SP/PSOL (2), RJ/PT (2), RJ/PSOL (1), MG/PT (2),
      MG/PL (2), DF/PT (1), DF/PL (2 -- inclui caixa mista 'pl').
    """
    conn = duckdb.connect(":memory:")
    aplicar_migrations(conn)
    cadastro = [
        (1, "camara", "Alice", "PT", "SP"),
        (2, "camara", "Bruno", "PT", "SP"),
        (3, "camara", "Carla", "PT", "SP"),
        (4, "camara", "Diana", "PSOL", "SP"),
        (5, "camara", "Egas", "PSOL", "SP"),
        (6, "camara", "Fabio", "PT", "RJ"),
        (7, "camara", "Gilda", "PT", "RJ"),
        (8, "camara", "Hugo", "PSOL", "RJ"),
        (9, "camara", "Iara", "PT", "MG"),
        (10, "camara", "Joao", "PT", "MG"),
        (11, "camara", "Karla", "PL", "MG"),
        (12, "camara", "Lia", "PL", "MG"),
        (13, "senado", "Mario", "PT", "DF"),
        (14, "senado", "Nadia", "PL", "DF"),
        # Caixa mista intencional: 'pl' minúsculo (precedente histórico Senado)
        (15, "senado", "Otavio", "pl", "DF"),
    ]
    conn.executemany(
        "INSERT INTO parlamentares (id, casa, nome, partido, uf) VALUES (?, ?, ?, ?, ?)",
        cadastro,
    )
    return conn


def test_filtro_ambos_none_retorna_sentinela_sem_filtro() -> None:
    """``ufs=None`` e ``partidos=None`` -> sentinela ``None`` (sem filtro).

    Não invoca a DB: a verificação é puramente pelo retorno do helper.
    """
    conn = _conn_com_parlamentares()
    try:
        resultado = _montar_clausula_subset_parlamentares(conn, ufs=None, partidos=None)
        assert resultado is None
    finally:
        conn.close()


def test_filtro_uf_apenas_aplica_clausula_uf() -> None:
    """``ufs=['SP']`` -> retorna apenas pares ``(id, casa)`` de SP."""
    conn = _conn_com_parlamentares()
    try:
        resultado = _montar_clausula_subset_parlamentares(conn, ufs=["SP"], partidos=None)
        assert resultado is not None
        ids_sp = {par[0] for par in resultado}
        # SP tem 5 parlamentares (PT 1-3 + PSOL 4-5)
        assert ids_sp == {1, 2, 3, 4, 5}
        assert all(par[1] == "camara" for par in resultado)
    finally:
        conn.close()


def test_filtro_partido_apenas_uppercase_defensivo() -> None:
    """``partidos=['pl']`` casa também ``'PL'`` e ``'pl'`` na DB.

    Defesa em profundidade contra histórico do Senado, que mistura
    caixa em ``partido``.
    """
    conn = _conn_com_parlamentares()
    try:
        resultado = _montar_clausula_subset_parlamentares(conn, ufs=None, partidos=["pl"])
        assert resultado is not None
        ids_pl = {par[0] for par in resultado}
        # Otavio (15) tem partido 'pl' minúsculo. Karla (11), Lia (12) e
        # Nadia (14) têm 'PL' maiúsculo. Todos devem casar.
        assert ids_pl == {11, 12, 14, 15}
    finally:
        conn.close()


def test_filtro_ambos_combinados_aplica_and() -> None:
    """``ufs + partidos`` aplicam AND lógico no recorte."""
    conn = _conn_com_parlamentares()
    try:
        resultado = _montar_clausula_subset_parlamentares(conn, ufs=["SP", "RJ"], partidos=["PT"])
        assert resultado is not None
        ids = {par[0] for par in resultado}
        # SP+PT: 1, 2, 3 / RJ+PT: 6, 7. PSOL e demais excluídos.
        assert ids == {1, 2, 3, 6, 7}
    finally:
        conn.close()


def test_filtro_resultado_menor_que_10_emite_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Recorte com 0 < n < 10 -> ``WARNING`` 'recorte muito estreito'.

    Captura via ``loguru`` -> ``caplog`` pelo handler ``InterceptHandler``
    embutido nos testes (configuração já existente em ``conftest.py``).
    """
    import logging

    from loguru import logger

    handler_id = logger.add(
        lambda msg: logging.getLogger("loguru").warning(msg.record["message"]),
        level="WARNING",
    )
    try:
        conn = _conn_com_parlamentares()
        try:
            with caplog.at_level(logging.WARNING, logger="loguru"):
                resultado = _montar_clausula_subset_parlamentares(conn, ufs=["SP"], partidos=["PT"])
            assert resultado is not None
            assert 0 < len(resultado) < 10
            mensagens = " ".join(rec.message for rec in caplog.records)
            assert "recorte muito estreito" in mensagens
        finally:
            conn.close()
    finally:
        logger.remove(handler_id)


def test_filtro_set_vazio_propaga_para_classificador() -> None:
    """Subset vazio devolvido pelo helper curto-circuita o classificador.

    Filtro ``ufs=['AC']`` em DB sem ninguém de AC retorna ``set()``;
    repassado a :func:`agregar_voto_por_parlamentar`, devolve schema
    vazio canônico (não levanta).
    """
    conn = _conn_com_parlamentares()
    try:
        # Insere proposição + votação para garantir que props_relevantes
        # nunca seja vazio (caso contrário curto-circuito ocorre antes).
        conn.execute(
            "INSERT INTO proposicoes (id, casa, sigla, numero, ano, ementa, "
            "tema_oficial) VALUES "
            "(1, 'camara', 'PL', 1, 2024, 'aborto legal smoke', 'Saúde')"
        )
        subset = _montar_clausula_subset_parlamentares(conn, ufs=["AC"], partidos=None)
        assert subset == set()
        props = pl.DataFrame({"id": [1], "casa": ["camara"]})
        df_agg = agregar_voto_por_parlamentar(props, conn, parlamentares_subset=subset)
        assert len(df_agg) == 0
        assert "parlamentar_id" in df_agg.columns
    finally:
        conn.close()
