"""Camada 2 do classificador (S27, ADR-011 -- D11).

Estatística leve, sem GPU, sem ML pesado. Duas funções:

- :func:`tfidf_relevancia` -- calcula score TF-IDF agregado por proposição,
  útil para ranquear ementas de C1 por densidade de termos. ``sklearn`` é
  importado lazy: só é carregado quando essa função é chamada.

- :func:`intensidade_discursiva` -- conta discursos do parlamentar que
  casam keywords/regex do tópico, normaliza pelo total de discursos do
  parlamentar (frequência relativa). Sinal complementar à agregação de
  voto da camada 1.

Determinismo: ``TfidfVectorizer`` em si não tem ``random_state`` -- mas
quando o ``input`` está ordenado (Polars devolve ordem estável de
leitura) e ``max_features`` é fixo, o vocabulário é determinístico. Para
garantir reprodutibilidade absoluta, ordenamos a entrada por ementa
antes de vetorizar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl
from loguru import logger

from hemiciclo.config import Configuracao

if TYPE_CHECKING:
    import duckdb

    from hemiciclo.etl.topicos import Topico


_MAX_FEATURES_TFIDF = 100
"""Tamanho do vocabulário TF-IDF. Fixo -- determinismo + corpus pequeno."""


def tfidf_relevancia(
    props_relevantes: pl.DataFrame, max_features: int = _MAX_FEATURES_TFIDF
) -> pl.DataFrame:
    """Adiciona coluna ``score_tfidf`` com soma dos pesos TF-IDF por proposição.

    Args:
        props_relevantes: Saída de C1 (precisa coluna ``ementa``).
        max_features: Limite de vocabulário TF-IDF; default 100.

    Returns:
        Mesmo DataFrame com nova coluna ``score_tfidf`` (float). Quando
        ``len(props) < 2`` (TF-IDF precisa de pelo menos 2 docs para fit
        razoável), preenche com 0.0.
    """
    if len(props_relevantes) == 0:
        return props_relevantes.with_columns(pl.lit(0.0).alias("score_tfidf"))
    if "ementa" not in props_relevantes.columns:
        raise ValueError("DataFrame precisa coluna 'ementa' para TF-IDF")

    # Ordem estável: ordena por id+casa antes de vetorizar (determinismo).
    df_ordenado = props_relevantes.sort(["casa", "id"])

    if len(df_ordenado) < 2:
        return df_ordenado.with_columns(pl.lit(0.0).alias("score_tfidf"))

    # Lazy import para não onerar boot do CLI/tests que não usam C2.
    from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: PLC0415

    ementas = df_ordenado["ementa"].fill_null("").to_list()
    vectorizer = TfidfVectorizer(max_features=max_features, lowercase=True)
    matriz = vectorizer.fit_transform(ementas)
    # Soma de pesos por documento -- vetor 1D de tamanho len(ementas).
    scores = matriz.sum(axis=1).A1.tolist()

    return df_ordenado.with_columns(pl.Series("score_tfidf", scores))


def intensidade_discursiva(
    parlamentar_id: int,
    casa: str,
    topico: Topico,
    conn: duckdb.DuckDBPyConnection,
) -> float:
    """Calcula frequência relativa de discursos do parlamentar que casam o tópico.

    Args:
        parlamentar_id: ID do parlamentar na sua casa.
        casa: ``"camara"`` ou ``"senado"``.
        topico: Tópico já compilado.
        conn: Conexão DuckDB com tabela ``discursos`` populada.

    Returns:
        Frequência ``casados / total`` em [0.0, 1.0]. Zero se o
        parlamentar não tem discursos no DB.
    """
    linha_total = conn.execute(
        "SELECT COUNT(*) FROM discursos WHERE parlamentar_id = ? AND casa = ?",
        [parlamentar_id, casa],
    ).fetchone()
    total = int(linha_total[0]) if linha_total else 0
    if total == 0:
        return 0.0

    # Em vez de filtrar via SQL (regex DuckDB é POSIX), trazemos os
    # conteúdos e aplicamos `Topico.casa_keywords` localmente.
    conteudos = (
        conn.execute(
            "SELECT conteudo FROM discursos WHERE parlamentar_id = ? AND casa = ?",
            [parlamentar_id, casa],
        )
        .pl()["conteudo"]
        .fill_null("")
        .to_list()
    )
    casados = sum(1 for c in conteudos if topico.casa_keywords(c))
    return casados / total


def _config_random_state() -> int:
    """Random state canônico do projeto (I3 do BRIEF)."""
    return Configuracao().random_state


def _aviso_determinismo() -> None:
    """Loga uma única vez que TF-IDF é determinístico via input ordenado."""
    logger.debug(
        "[c2][tfidf] Determinismo via input ordenado (sort por casa,id) + "
        "max_features fixo. random_state global = {rs}.",
        rs=_config_random_state(),
    )
