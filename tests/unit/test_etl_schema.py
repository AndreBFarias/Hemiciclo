"""Testes do schema DuckDB v1 (S26)."""

from __future__ import annotations

import duckdb
import pytest

from hemiciclo.etl.schema import (
    SCHEMA_VERSAO,
    SCHEMA_VERSAO_ATUAL,
    criar_schema,
    criar_schema_v1,
)


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    """Conexão DuckDB em memória, isolada por teste."""
    return duckdb.connect(":memory:")


def test_criar_schema_v1_cria_5_tabelas(conn: duckdb.DuckDBPyConnection) -> None:
    """As 5 tabelas de domínio existem após criar_schema_v1."""
    criar_schema_v1(conn)
    nomes = {
        linha[0]
        for linha in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
    }
    esperadas = {"proposicoes", "votacoes", "votos", "discursos", "parlamentares"}
    assert esperadas.issubset(nomes), f"faltou tabela: {esperadas - nomes}"


def test_criar_schema_v1_cria_tabela_migrations(conn: duckdb.DuckDBPyConnection) -> None:
    """A tabela meta `_migrations` existe e tem PK em `versao`."""
    criar_schema_v1(conn)
    nomes = {
        linha[0]
        for linha in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
    }
    assert "_migrations" in nomes
    cols = {
        linha[0]
        for linha in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='_migrations'"
        ).fetchall()
    }
    assert {"versao", "descricao", "aplicada_em"}.issubset(cols)


def test_pks_definidas_corretamente(conn: duckdb.DuckDBPyConnection) -> None:
    """PKs compostas funcionam: inserir o mesmo (id, casa) duas vezes falha sem OR IGNORE."""
    criar_schema_v1(conn)
    conn.execute("INSERT INTO proposicoes (id, casa, ementa) VALUES (1, 'camara', 'a')")
    with pytest.raises(duckdb.ConstraintException):
        conn.execute("INSERT INTO proposicoes (id, casa, ementa) VALUES (1, 'camara', 'b')")
    # Mesmo id em casa diferente é permitido -- discriminador funciona.
    conn.execute("INSERT INTO proposicoes (id, casa, ementa) VALUES (1, 'senado', 'c')")
    total = conn.execute("SELECT COUNT(*) FROM proposicoes").fetchone()
    assert total is not None
    assert total[0] == 2


def test_indices_criados(conn: duckdb.DuckDBPyConnection) -> None:
    """Indexes em ementa, parlamentar_id (discursos) e parlamentar_id (votos) existem."""
    criar_schema_v1(conn)
    indices = {
        linha[0]
        for linha in conn.execute(
            "SELECT index_name FROM duckdb_indexes() WHERE schema_name='main'"
        ).fetchall()
    }
    assert "idx_proposicoes_ementa" in indices
    assert "idx_discursos_parlamentar" in indices
    assert "idx_votos_parlamentar" in indices


def test_idempotente(conn: duckdb.DuckDBPyConnection) -> None:
    """Chamar criar_schema_v1 duas vezes não falha (todos DDLs usam IF NOT EXISTS)."""
    criar_schema_v1(conn)
    criar_schema_v1(conn)  # não levanta
    total_tabelas = conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='main'"
    ).fetchone()
    assert total_tabelas is not None
    # 5 tabelas de domínio + 1 meta = 6
    assert total_tabelas[0] == 6


def test_schema_versao_constante() -> None:
    """SCHEMA_VERSAO declara a versão criada por ``criar_schema_v1`` (M001 -> v1)."""
    assert SCHEMA_VERSAO == 1


def test_schema_versao_atual_constante() -> None:
    """SCHEMA_VERSAO_ATUAL reflete o alvo após todas as migrations canônicas (S27.1 -> v2)."""
    assert SCHEMA_VERSAO_ATUAL == 2


def test_votacoes_tem_proposicao_id_em_v2(conn: duckdb.DuckDBPyConnection) -> None:
    """Schema v2 (S27.1) tem ``votacoes.proposicao_id BIGINT``."""
    criar_schema(conn)
    cols = {
        linha[0]
        for linha in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='votacoes'"
        ).fetchall()
    }
    assert "proposicao_id" in cols


def test_criar_schema_aplica_todas_as_migrations(conn: duckdb.DuckDBPyConnection) -> None:
    """``criar_schema`` (S27.1) deixa o DB pronto em v2 sem chamadas extras."""
    from hemiciclo.etl.migrations import versao_atual

    criar_schema(conn)
    assert versao_atual(conn) == SCHEMA_VERSAO_ATUAL
