"""Sistema de migrations sequenciais idempotentes (S26).

Cada migration é uma instância de :class:`Migration` com:

- ``versao`` -- inteiro monotônico crescente (1, 2, 3, ...);
- ``descricao`` -- texto curto registrado em ``_migrations.descricao``;
- ``aplicar(conn)`` -- callable que executa o DDL/DML necessário.

A função :func:`aplicar_migrations` lê a versão atual em ``_migrations`` e
aplica todas as pendentes em ordem, registrando-as ao final dentro de uma
transação por migration. Idempotente: re-execução em base já atualizada não
faz nada.

Política de versionamento:

- M001 -- cria schema v1 (delega para :func:`hemiciclo.etl.schema.criar_schema_v1`).
- M002 -- adiciona ``votacoes.proposicao_id BIGINT`` (S27.1, destrava JOIN
  votos × votações × proposições no classificador C1).
- M003+ -- adicionadas em sprints futuras quando o schema evoluir
  (ex.: nova coluna, nova tabela). Migrations *nunca* são editadas após
  publicação; sempre nova migration.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import duckdb
from loguru import logger

from hemiciclo.etl.schema import criar_schema_v1


@dataclass(frozen=True)
class Migration:
    """Migration declarativa.

    Atributos:
        versao: Número da migration (1-based, monotônico).
        descricao: Texto curto registrado em ``_migrations.descricao``.
        aplicar: Callable invocada com a conexão DuckDB.
    """

    versao: int
    descricao: str
    aplicar: Callable[[duckdb.DuckDBPyConnection], None]


def _aplicar_m002(conn: duckdb.DuckDBPyConnection) -> None:
    """M002 -- adiciona ``votacoes.proposicao_id BIGINT`` (S27.1).

    Idempotente via ``ADD COLUMN IF NOT EXISTS`` (DuckDB ≥ 0.9). Em DBs
    v1 a coluna entra com valor ``NULL`` para todas as linhas existentes;
    coletas e consolidações futuras populam normalmente. Não migra dados
    históricos -- backfill (opcional) é recoleta dos parquets via
    :mod:`scripts.migracao_m002`.
    """
    conn.execute("ALTER TABLE votacoes ADD COLUMN IF NOT EXISTS proposicao_id BIGINT")


M001 = Migration(
    versao=1,
    descricao="Schema v1: 5 tabelas de domínio + meta _migrations.",
    aplicar=criar_schema_v1,
)


M002 = Migration(
    versao=2,
    descricao="votacoes.proposicao_id BIGINT (S27.1, destrava JOIN do C1).",
    aplicar=_aplicar_m002,
)


MIGRATIONS: list[Migration] = [M001, M002]
"""Lista canônica de migrations, ordenada por versão crescente."""


def _garantir_tabela_migrations(conn: duckdb.DuckDBPyConnection) -> None:
    """Garante que ``_migrations`` existe antes de consultar versão.

    Permite chamar :func:`aplicar_migrations` em DB recém-criado, sem precisar
    rodar `criar_schema_v1` antes.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _migrations (
            versao INTEGER PRIMARY KEY,
            descricao VARCHAR NOT NULL,
            aplicada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def versao_atual(conn: duckdb.DuckDBPyConnection) -> int:
    """Retorna a maior versão registrada em ``_migrations``, ou 0 se vazio.

    Args:
        conn: Conexão DuckDB ativa.

    Returns:
        Inteiro >= 0. Zero significa "nenhuma migration aplicada".
    """
    _garantir_tabela_migrations(conn)
    linha = conn.execute("SELECT COALESCE(MAX(versao), 0) FROM _migrations").fetchone()
    if linha is None:
        return 0
    return int(linha[0])


def aplicar_migrations(conn: duckdb.DuckDBPyConnection) -> int:
    """Aplica todas as migrations pendentes em ordem.

    Idempotente: se ``versao_atual >= max(MIGRATIONS.versao)``, retorna 0
    sem tocar no DB.

    Args:
        conn: Conexão DuckDB ativa.

    Returns:
        Quantidade de migrations efetivamente aplicadas nesta chamada.
    """
    _garantir_tabela_migrations(conn)
    atual = versao_atual(conn)
    pendentes = [m for m in MIGRATIONS if m.versao > atual]
    aplicadas = 0
    for migration in sorted(pendentes, key=lambda m: m.versao):
        logger.info(
            "[etl][migrations] aplicando M{n:03d}: {d}",
            n=migration.versao,
            d=migration.descricao,
        )
        migration.aplicar(conn)
        conn.execute(
            "INSERT INTO _migrations (versao, descricao) VALUES (?, ?)",
            [migration.versao, migration.descricao],
        )
        aplicadas += 1
    if aplicadas == 0:
        logger.debug("[etl][migrations] nenhuma migration pendente (versao={v})", v=atual)
    return aplicadas
