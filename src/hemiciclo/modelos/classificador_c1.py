"""Camada 1 do classificador (S27 + S27.1, ADR-011 -- D11).

Determinística, offline, sem dependência ML pesada. Combina:

- **Match em ementa** -- keywords (ILIKE) + regex Python aplicado em Polars.
- **Categoria oficial** -- ``proposicoes.tema_oficial`` casando alguma das
  ``categorias_oficiais_camara`` / ``categorias_oficiais_senado`` do tópico.
- **Exclusões** -- regex que desclassifica falsos positivos (ex.: "aborto
  espontâneo").
- **Agregação por parlamentar** -- ``votos`` JOIN ``votacoes`` filtrando
  pelas proposições relevantes via ``votacoes.proposicao_id``; calcula
  ``proporcao_sim`` e categoriza em ``A_FAVOR`` / ``CONTRA`` / ``NEUTRO``.

Compatibilidade retroativa (S27.1): :func:`agregar_voto_por_parlamentar`
chama :func:`hemiciclo.etl.migrations.aplicar_migrations` antes do JOIN.
DBs criados antes da M002 (schema v1) ganham automaticamente a coluna
``votacoes.proposicao_id`` no primeiro acesso, sem dados (``NULL``).
Recall completo só vem após recoletar/reconsolidar os parquets pós-S27.1
(ou rodar ``scripts/migracao_m002.py`` para aplicar a migration sem
reconsolidar).
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

import polars as pl

from hemiciclo.etl.migrations import aplicar_migrations

if TYPE_CHECKING:
    import duckdb

    from hemiciclo.etl.topicos import Topico


class PosicaoAgregada(StrEnum):
    """Posição inferida a partir de ``proporcao_sim`` em votos relevantes."""

    A_FAVOR = "A_FAVOR"
    CONTRA = "CONTRA"
    NEUTRO = "NEUTRO"


_LIMIAR_FAVOR = 0.70
_LIMIAR_CONTRA = 0.30


def _categorizar(proporcao: float) -> PosicaoAgregada:
    """Mapeia proporção SIM -> posição agregada conforme limiares fixos."""
    if proporcao >= _LIMIAR_FAVOR:
        return PosicaoAgregada.A_FAVOR
    if proporcao <= _LIMIAR_CONTRA:
        return PosicaoAgregada.CONTRA
    return PosicaoAgregada.NEUTRO


def proposicoes_relevantes(topico: Topico, conn: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """Retorna proposições da DB que casam o tópico em camada 1.

    Estratégia (filtragem em duas etapas):

    1. SQL com ``ILIKE`` em ementa (keywords) ``OR`` ``tema_oficial`` em
       categorias oficiais. DuckDB regex tem sintaxe diferente da Python
       (POSIX ERE), então pulamos regex no SQL.
    2. Polars filtra por regex Python (lição S27 §8 do spec) e aplica
       exclusões (também regex Python).

    Args:
        topico: Modelo já validado (regex compiláveis).
        conn: Conexão DuckDB ativa apontando para schema v1+.

    Returns:
        DataFrame com colunas ``id, casa, sigla, numero, ano, ementa,
        tema_oficial, score_match`` (``score_match`` = 1 -- placeholder
        para versões futuras pesarem keyword vs categoria).
    """
    where_keywords = " OR ".join(
        f"LOWER(ementa) LIKE '%{kw.lower().replace(chr(39), chr(39) * 2)}%'"
        for kw in topico.keywords
    )
    categorias_todas = list(topico.categorias_oficiais_camara) + list(
        topico.categorias_oficiais_senado
    )
    if categorias_todas:
        cats_escapadas = ",".join(f"'{c.replace(chr(39), chr(39) * 2)}'" for c in categorias_todas)
        where_cat = f"tema_oficial IN ({cats_escapadas})"
    else:
        where_cat = "FALSE"
    sql = (
        "SELECT id, casa, sigla, numero, ano, ementa, tema_oficial "
        "FROM proposicoes "
        f"WHERE ({where_keywords}) OR ({where_cat})"
    )
    df = conn.execute(sql).pl()

    # Match adicional via regex Python (alguns padrões só batem aqui).
    if len(df) == 0:
        # Mesmo vazio, aplica regex contra DB inteiro? Não: SQL acima já
        # cobre keywords. Regex é refinamento, não fonte primária.
        return df.with_columns(pl.lit(1).alias("score_match"))

    # Aplica exclusões via Polars (DuckDB regex é POSIX ERE, evita).
    if topico.exclusoes:
        for excl in topico.exclusoes:
            df = df.filter(~pl.col("ementa").fill_null("").str.contains(excl.regex))

    df = df.with_columns(pl.lit(1).alias("score_match"))
    return df


def agregar_voto_por_parlamentar(
    props_relevantes: pl.DataFrame,
    conn: duckdb.DuckDBPyConnection,
    parlamentares_subset: set[tuple[int, str]] | None = None,
) -> pl.DataFrame:
    """Agrega votos × proposições relevantes em proporção_sim por parlamentar.

    Aplica :func:`hemiciclo.etl.migrations.aplicar_migrations` antes do JOIN
    -- garante compatibilidade com DBs v1 antigos (que ganham a coluna
    ``votacoes.proposicao_id`` automaticamente, com valores ``NULL``).
    O JOIN é direto; a coluna sempre existe pós-aplicação. DBs sem dados
    populados em ``proposicao_id`` simplesmente retornam DataFrame vazio
    pelo filtro ``IS NOT NULL`` implícito do JOIN.

    Args:
        props_relevantes: Saída de :func:`proposicoes_relevantes`.
        conn: Conexão DuckDB.
        parlamentares_subset: Filtro opcional (S30.2) com pares
            ``(parlamentar_id, casa)`` aceitos. ``None`` = sem filtro
            (default). Set vazio = curto-circuito imediato para
            ``schema_vazio`` (recorte casou ninguém).

    Returns:
        DataFrame com ``parlamentar_id, casa, n_votos, proporcao_sim,
        posicao_agregada`` (string).
    """
    schema_vazio = pl.DataFrame(
        schema={
            "parlamentar_id": pl.Int64,
            "casa": pl.Utf8,
            "n_votos": pl.Int64,
            "proporcao_sim": pl.Float64,
            "posicao_agregada": pl.Utf8,
        }
    )

    if len(props_relevantes) == 0:
        return schema_vazio

    # Curto-circuito: subset explicitamente vazio = ninguém no recorte.
    if parlamentares_subset is not None and len(parlamentares_subset) == 0:
        return schema_vazio

    # Garante schema atualizado (M002+) em DBs antigos -- idempotente.
    aplicar_migrations(conn)

    # Constrói lista de tuplas (id, casa) das proposições relevantes para
    # filtrar votações via JOIN seguro.
    ids_casas = list(
        zip(
            props_relevantes["id"].to_list(),
            props_relevantes["casa"].to_list(),
            strict=True,
        )
    )
    if not ids_casas:
        return schema_vazio

    # Cria tabela temp (in-memory) com os pares (id, casa) -- DuckDB lida
    # com VALUES de forma robusta para qualquer N.
    conn.execute("DROP TABLE IF EXISTS _props_relevantes_tmp")
    conn.execute("CREATE TEMP TABLE _props_relevantes_tmp (id BIGINT, casa VARCHAR)")
    conn.executemany(
        "INSERT INTO _props_relevantes_tmp VALUES (?, ?)",
        ids_casas,
    )

    # Tabela temp adicional para o subset de parlamentares (S30.2).
    join_subset_clause = ""
    if parlamentares_subset is not None:
        conn.execute("DROP TABLE IF EXISTS _parlamentares_subset_tmp")
        conn.execute(
            "CREATE TEMP TABLE _parlamentares_subset_tmp (parlamentar_id BIGINT, casa VARCHAR)"
        )
        conn.executemany(
            "INSERT INTO _parlamentares_subset_tmp VALUES (?, ?)",
            list(parlamentares_subset),
        )
        join_subset_clause = (
            "JOIN _parlamentares_subset_tmp ps "
            "ON ps.parlamentar_id = v.parlamentar_id AND ps.casa = v.casa"
        )

    sql = f"""
        SELECT
            v.parlamentar_id,
            v.casa,
            COUNT(*) AS n_votos,
            CAST(SUM(CASE WHEN UPPER(v.voto) = 'SIM' THEN 1 ELSE 0 END) AS DOUBLE)
                / NULLIF(COUNT(*), 0) AS proporcao_sim
        FROM votos v
        JOIN votacoes vt ON vt.id = v.votacao_id AND vt.casa = v.casa
        JOIN _props_relevantes_tmp pr
            ON pr.id = vt.proposicao_id AND pr.casa = vt.casa
        {join_subset_clause}
        GROUP BY v.parlamentar_id, v.casa
    """
    df_agg = conn.execute(sql).pl()
    conn.execute("DROP TABLE IF EXISTS _props_relevantes_tmp")
    if parlamentares_subset is not None:
        conn.execute("DROP TABLE IF EXISTS _parlamentares_subset_tmp")

    if len(df_agg) == 0:
        return schema_vazio

    df_agg = df_agg.with_columns(
        pl.col("proporcao_sim")
        .map_elements(lambda p: _categorizar(p).value, return_dtype=pl.Utf8)
        .alias("posicao_agregada")
    )
    return df_agg
