"""Utilitário CLI: aplica a Migration M002 em um DB DuckDB existente (S27.1).

Uso típico::

    python scripts/migracao_m002.py --db-path ~/hemiciclo/sessoes/<id>/dados.duckdb

A M002 adiciona a coluna ``votacoes.proposicao_id BIGINT`` em DBs que
ainda estão no schema v1 (criados antes da S27.1). A coluna é populada
com ``NULL`` para todas as linhas existentes -- recall completo só vem
após reconsolidar parquets coletados pós-S27.1.

Idempotente: rodar duas vezes seguidas no mesmo DB não falha. Quando o
DB já está em v2, reporta "nada a fazer" e termina com exit 0.

Não toca em parquets -- ETL é fora do escopo deste script. Para repopular
``proposicao_id`` use ``hemiciclo coletar camara/senado --tipos votacoes``
seguido de ``hemiciclo db consolidar``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

from hemiciclo.etl.migrations import aplicar_migrations, versao_atual


def aplicar_em(db_path: Path) -> int:
    """Aplica migrations pendentes em ``db_path``.

    Args:
        db_path: Caminho do arquivo DuckDB.

    Returns:
        Quantidade de migrations efetivamente aplicadas (0 se já atualizado).
    """
    if not db_path.exists():
        print(f"[migracao_m002] erro: DB não encontrado em {db_path}", file=sys.stderr)
        return -1
    conn = duckdb.connect(str(db_path))
    try:
        antes = versao_atual(conn)
        aplicadas = aplicar_migrations(conn)
        depois = versao_atual(conn)
        print(
            f"[migracao_m002] {db_path.name}: "
            f"versao {antes} -> {depois} "
            f"({aplicadas} migration(s) aplicada(s))"
        )
        return aplicadas
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    """Entrypoint CLI.

    Args:
        argv: Argumentos de linha de comando (default ``sys.argv[1:]``).

    Returns:
        Exit code: 0 sucesso, 1 erro de I/O, 2 args invalidos.
    """
    parser = argparse.ArgumentParser(
        prog="migracao_m002",
        description=(
            "Aplica a Migration M002 (S27.1) em um DB DuckDB existente. "
            "Idempotente: re-rodar não causa erro."
        ),
    )
    parser.add_argument(
        "--db-path",
        required=True,
        type=Path,
        help="Caminho do arquivo .duckdb (ex.: ~/hemiciclo/sessoes/<id>/dados.duckdb).",
    )
    args = parser.parse_args(argv)
    db_path: Path = args.db_path.expanduser().resolve()
    resultado = aplicar_em(db_path)
    if resultado < 0:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
