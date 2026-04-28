"""Schema DuckDB unificado para Câmara + Senado (S26 v1, S27.1 v2).

Contém a definição declarativa do schema analítico do Hemiciclo:
cinco tabelas de domínio (``proposicoes``, ``votacoes``, ``votos``,
``discursos``, ``parlamentares``) mais a tabela meta ``_migrations`` usada
pelo controlador em :mod:`hemiciclo.etl.migrations`.

Decisões registradas no ADR-012:

- **Tabela única `proposicoes` com `casa` discriminador.** Em vez de
  `proposicoes_camara` + `materias_senado`, mantemos *uma* tabela com
  PK composta ``(id, casa)``. Queries cross-casa que S27/S30 farão ficam
  triviais (``WHERE casa IN ('camara','senado')``).
- **`hash_conteudo` como `VARCHAR`** -- aceita tanto a versão 16-char
  truncada (S24/S25) quanto a versão 64-char hex completa que pode vir
  futuramente, sem migração. A discriminação fica para S25.1.
- **Sem `FOREIGN KEY` declarado.** DuckDB ainda não fornece enforcement
  pleno de FK em todos cenários; mantemos consistência via ETL.
- **Indexes mínimos.** `proposicoes(ementa)`, `discursos(parlamentar_id)`
  e `votos(parlamentar_id)`. Otimizações finas ficam para sprints
  posteriores.

Histórico de versões:

- **v1 (S26 / M001)** -- 5 tabelas de domínio + meta ``_migrations``.
- **v2 (S27.1 / M002)** -- ``votacoes`` ganha coluna ``proposicao_id BIGINT``
  para destravar JOIN votos × votações × proposições no classificador C1.
"""

from __future__ import annotations

import duckdb

SCHEMA_VERSAO = 1
"""Versão do schema canônico criado por :func:`criar_schema_v1`.

Mantida em 1 por compatibilidade com testes legados. A versão "viva" do
schema (após todas as migrations canônicas aplicadas) é dada por
:data:`SCHEMA_VERSAO_ATUAL`.
"""

SCHEMA_VERSAO_ATUAL = 2
"""Versão alvo do schema após aplicar todas as :data:`MIGRATIONS` registradas.

Incrementada toda vez que uma nova migration M00X é adicionada à lista
canônica em :mod:`hemiciclo.etl.migrations`.
"""


def criar_schema_v1(conn: duckdb.DuckDBPyConnection) -> None:
    """Cria as 5 tabelas de domínio + meta ``_migrations`` no formato v1.

    Idempotente: chamadas repetidas não causam erro porque todas as DDLs usam
    ``IF NOT EXISTS``. Não popula a tabela ``_migrations`` -- isso é
    responsabilidade do controlador em :mod:`hemiciclo.etl.migrations`.

    Schema v1 não inclui ``votacoes.proposicao_id`` -- isso vem na M002
    (S27.1) via :func:`hemiciclo.etl.migrations.M002`. Para criar um DB já
    no schema v2, prefira :func:`criar_schema` (que delega para
    ``aplicar_migrations``).

    Args:
        conn: Conexão DuckDB ativa (memória ou arquivo).
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS proposicoes (
            id BIGINT NOT NULL,
            casa VARCHAR NOT NULL,
            sigla VARCHAR,
            numero BIGINT,
            ano BIGINT,
            ementa VARCHAR,
            tema_oficial VARCHAR,
            autor_principal VARCHAR,
            data_apresentacao VARCHAR,
            status VARCHAR,
            url_inteiro_teor VARCHAR,
            hash_conteudo VARCHAR,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id, casa)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS votacoes (
            id VARCHAR NOT NULL,
            casa VARCHAR NOT NULL,
            data VARCHAR,
            hora VARCHAR,
            descricao VARCHAR,
            resultado VARCHAR,
            total_sim INTEGER,
            total_nao INTEGER,
            total_abstencao INTEGER,
            total_obstrucao INTEGER,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id, casa)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS votos (
            votacao_id VARCHAR NOT NULL,
            parlamentar_id BIGINT NOT NULL,
            casa VARCHAR NOT NULL,
            voto VARCHAR,
            data VARCHAR,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (votacao_id, parlamentar_id, casa)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS discursos (
            hash_conteudo VARCHAR PRIMARY KEY,
            parlamentar_id BIGINT,
            casa VARCHAR NOT NULL,
            data VARCHAR,
            hora VARCHAR,
            conteudo VARCHAR,
            fase_sessao VARCHAR,
            sumario VARCHAR,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS parlamentares (
            id BIGINT NOT NULL,
            casa VARCHAR NOT NULL,
            nome VARCHAR,
            partido VARCHAR,
            uf VARCHAR,
            ativo BOOLEAN,
            foto_url VARCHAR,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id, casa)
        )
        """
    )

    # Indexes -- DuckDB não aceita "USING (col)"; sintaxe simples basta.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_proposicoes_ementa ON proposicoes (ementa)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_discursos_parlamentar ON discursos (parlamentar_id)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_votos_parlamentar ON votos (parlamentar_id)")


def criar_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Cria o schema canônico atual aplicando todas as migrations.

    Atalho equivalente a :func:`hemiciclo.etl.migrations.aplicar_migrations`,
    útil em scripts de smoke e fixtures de teste que querem o schema
    "vivo" (v2 após S27.1) sem importar dois módulos.

    Args:
        conn: Conexão DuckDB ativa.
    """
    # Import local para evitar ciclo (migrations importa schema).
    from hemiciclo.etl.migrations import aplicar_migrations

    aplicar_migrations(conn)
