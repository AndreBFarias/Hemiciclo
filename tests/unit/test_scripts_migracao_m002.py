"""Testes do utilitário CLI ``scripts/migracao_m002.py`` (S27.1)."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pytest

# Adiciona scripts/ ao sys.path -- spec utilitário, não shipado como pacote.
_RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RAIZ / "scripts"))

import migracao_m002  # noqa: E402

from hemiciclo.etl.schema import criar_schema_v1  # noqa: E402


def test_aplicar_em_db_v1_atualiza_para_v2(tmp_path: Path) -> None:
    """Em DB v1 cru o script aplica M002 e reporta 1 migration (a M002)."""
    db = tmp_path / "v1.duckdb"
    conn = duckdb.connect(str(db))
    try:
        criar_schema_v1(conn)
        conn.execute("INSERT INTO _migrations (versao, descricao) VALUES (1, 'manual v1')")
    finally:
        conn.close()

    aplicadas = migracao_m002.aplicar_em(db)
    assert aplicadas == 1

    conn = duckdb.connect(str(db))
    try:
        cols = {
            linha[0]
            for linha in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='votacoes'"
            ).fetchall()
        }
        assert "proposicao_id" in cols
    finally:
        conn.close()


def test_aplicar_em_db_v2_nao_faz_nada(tmp_path: Path) -> None:
    """Em DB já em v2 o script reporta 0 migrations aplicadas."""
    db = tmp_path / "v2.duckdb"
    conn = duckdb.connect(str(db))
    try:
        from hemiciclo.etl.migrations import aplicar_migrations

        aplicar_migrations(conn)
    finally:
        conn.close()

    aplicadas = migracao_m002.aplicar_em(db)
    assert aplicadas == 0


def test_main_db_inexistente_retorna_codigo_1(tmp_path: Path) -> None:
    """Path inexistente termina com exit code 1 (erro)."""
    inexistente = tmp_path / "nao_existe.duckdb"
    assert migracao_m002.main(["--db-path", str(inexistente)]) == 1


def test_main_caminho_feliz_retorna_zero(tmp_path: Path) -> None:
    """Path válido (DB v1 cru) termina com exit 0 e DB já em v2."""
    db = tmp_path / "v1.duckdb"
    conn = duckdb.connect(str(db))
    try:
        criar_schema_v1(conn)
    finally:
        conn.close()

    assert migracao_m002.main(["--db-path", str(db)]) == 0

    conn = duckdb.connect(str(db))
    try:
        from hemiciclo.etl.migrations import versao_atual

        assert versao_atual(conn) == 2
    finally:
        conn.close()


def test_main_argumento_obrigatorio() -> None:
    """Sem ``--db-path`` o argparse termina com SystemExit (exit 2)."""
    with pytest.raises(SystemExit):
        migracao_m002.main([])
