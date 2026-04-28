"""Testes do sistema de migrations (S26)."""

from __future__ import annotations

import duckdb
import pytest

from hemiciclo.etl.migrations import MIGRATIONS, aplicar_migrations, versao_atual


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    """Conexão DuckDB em memória, isolada por teste."""
    return duckdb.connect(":memory:")


def test_aplicar_migrations_em_db_vazio_aplica_todas(conn: duckdb.DuckDBPyConnection) -> None:
    """Em DB vazio, aplicar_migrations executa todas e retorna a quantidade."""
    aplicadas = aplicar_migrations(conn)
    assert aplicadas == len(MIGRATIONS)
    # Verifica que as 5 tabelas existem (M001 delega para criar_schema_v1)
    nomes = {
        linha[0]
        for linha in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()
    }
    assert {"proposicoes", "votacoes", "votos", "discursos", "parlamentares"}.issubset(nomes)


def test_aplicar_migrations_em_db_atualizado_nao_faz_nada(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Re-rodar aplicar_migrations em DB já atualizado retorna 0 e não duplica."""
    aplicar_migrations(conn)
    aplicadas = aplicar_migrations(conn)
    assert aplicadas == 0
    total = conn.execute("SELECT COUNT(*) FROM _migrations").fetchone()
    assert total is not None
    assert total[0] == len(MIGRATIONS)


def test_aplicar_migrations_em_db_parcial_aplica_pendentes(
    conn: duckdb.DuckDBPyConnection,
) -> None:
    """Se versão atual < max, aplica apenas as pendentes (simulação com M001 já aplicada)."""
    # Simula "M001 já aplicada manualmente" sem usar a função.
    conn.execute(
        """
        CREATE TABLE _migrations (
            versao INTEGER PRIMARY KEY,
            descricao VARCHAR NOT NULL,
            aplicada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Cria as tabelas de domínio também (porque M001 fez isso).
    from hemiciclo.etl.schema import criar_schema_v1

    criar_schema_v1(conn)
    conn.execute("INSERT INTO _migrations (versao, descricao) VALUES (1, 'Schema v1 manual')")

    # Agora aplicar_migrations deve detectar que M001 já está aplicada e
    # rodar apenas M002+ (pós-S27.1). Esperamos len(MIGRATIONS) - 1 aplicações.
    aplicadas = aplicar_migrations(conn)
    assert aplicadas == len(MIGRATIONS) - 1


def test_versao_atual_lida_corretamente(conn: duckdb.DuckDBPyConnection) -> None:
    """versao_atual retorna 0 em DB vazio e maior versão após aplicar."""
    assert versao_atual(conn) == 0
    aplicar_migrations(conn)
    esperado = max(m.versao for m in MIGRATIONS)
    assert versao_atual(conn) == esperado


def test_migrations_ordenadas_e_unicas() -> None:
    """A lista MIGRATIONS está ordenada por versão e não tem duplicatas."""
    versoes = [m.versao for m in MIGRATIONS]
    assert versoes == sorted(versoes)
    assert len(set(versoes)) == len(versoes)


# ---------------------------------------------------------------------------
# S27.1 -- M002 adiciona votacoes.proposicao_id BIGINT (idempotente).
# ---------------------------------------------------------------------------


def test_m002_adiciona_proposicao_id(conn: duckdb.DuckDBPyConnection) -> None:
    """Após M002 a tabela votacoes tem coluna ``proposicao_id`` BIGINT."""
    aplicar_migrations(conn)
    cols = {
        linha[0]: linha[1]
        for linha in conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name='votacoes'"
        ).fetchall()
    }
    assert "proposicao_id" in cols
    assert "BIGINT" in cols["proposicao_id"].upper()


def test_m002_idempotente_aplicada_duas_vezes(conn: duckdb.DuckDBPyConnection) -> None:
    """Re-rodar aplicar_migrations em DB já em v2 não falha nem duplica linhas."""
    aplicar_migrations(conn)
    aplicar_migrations(conn)  # segunda chamada não deve levantar
    total = conn.execute("SELECT COUNT(*) FROM _migrations").fetchone()
    assert total is not None
    assert total[0] == len(MIGRATIONS)


def test_m002_em_db_v1_existente_preserva_dados(conn: duckdb.DuckDBPyConnection) -> None:
    """Aplicar M002 em DB v1 com dados não perde linhas existentes."""
    from hemiciclo.etl.schema import criar_schema_v1

    criar_schema_v1(conn)
    conn.execute("INSERT INTO _migrations (versao, descricao) VALUES (1, 'manual v1')")
    conn.execute(
        "INSERT INTO votacoes (id, casa, descricao) VALUES "
        "('v1', 'camara', 'antes de M002'), "
        "('v2', 'senado', 'tambem antes')"
    )
    aplicar_migrations(conn)

    rows = conn.execute(
        "SELECT id, casa, descricao, proposicao_id FROM votacoes ORDER BY id"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0] == ("v1", "camara", "antes de M002", None)
    assert rows[1] == ("v2", "senado", "tambem antes", None)
