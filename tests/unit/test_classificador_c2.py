"""Testes da camada 2 do classificador (S27)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl

from hemiciclo.etl.migrations import aplicar_migrations
from hemiciclo.etl.topicos import carregar_topico
from hemiciclo.modelos.classificador_c2 import (
    intensidade_discursiva,
    tfidf_relevancia,
)

RAIZ = Path(__file__).resolve().parents[2]
TOPICOS_DIR = RAIZ / "topicos"


def _props_seed() -> pl.DataFrame:
    """DataFrame minimal: 4 proposições com ementas distintas para TF-IDF."""
    return pl.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "casa": ["camara", "camara", "senado", "senado"],
            "ementa": [
                "Aborto legal em casos de estupro consentido pela vitima.",
                "Direitos reprodutivos da mulher e planejamento familiar no SUS.",
                "Estatuto do nascituro e direito ao nascimento desde a concepcao.",
                "Saude reprodutiva e atendimento em servicos publicos de saude.",
            ],
            "score_match": [1, 1, 1, 1],
        }
    )


def test_tfidf_relevancia_ordena() -> None:
    df = tfidf_relevancia(_props_seed())
    assert "score_tfidf" in df.columns
    assert len(df) == 4
    # Todos scores > 0 (corpus tem termos).
    assert all(s > 0 for s in df["score_tfidf"].to_list())
    # Ordem estável: foi sorted por casa,id internamente.
    assert df["casa"].to_list() == ["camara", "camara", "senado", "senado"]
    assert df["id"].to_list() == [1, 2, 3, 4]


def test_tfidf_lista_vazia_nao_falha() -> None:
    vazio = pl.DataFrame(
        {
            "id": pl.Series([], dtype=pl.Int64),
            "casa": pl.Series([], dtype=pl.Utf8),
            "ementa": pl.Series([], dtype=pl.Utf8),
        }
    )
    df = tfidf_relevancia(vazio)
    assert "score_tfidf" in df.columns
    assert len(df) == 0


def test_tfidf_um_documento_vira_zero() -> None:
    """Com apenas 1 doc, TF-IDF é degenerado -- preenche 0.0."""
    df_um = pl.DataFrame(
        {
            "id": [1],
            "casa": ["camara"],
            "ementa": ["Aborto legal em casos de estupro."],
        }
    )
    df = tfidf_relevancia(df_um)
    assert df["score_tfidf"].to_list() == [0.0]


def test_intensidade_discursiva_normalizada() -> None:
    aborto = carregar_topico(TOPICOS_DIR / "aborto.yaml")
    conn = duckdb.connect(":memory:")
    try:
        aplicar_migrations(conn)
        # Parlamentar 100 (Câmara): 4 discursos, 2 casam aborto
        registros = [
            ("h1", 100, "camara", "Defendo o aborto legal em casos de estupro.", "2024-01-01"),
            ("h2", 100, "camara", "Apoio direitos reprodutivos da mulher.", "2024-01-02"),
            ("h3", 100, "camara", "Reforma tributaria e crescimento.", "2024-01-03"),
            ("h4", 100, "camara", "Educacao basica precisa de mais investimento.", "2024-01-04"),
            # Parlamentar 200 (Câmara): 2 discursos, nenhum casa
            ("h5", 200, "camara", "Energia solar para o pais.", "2024-01-05"),
            ("h6", 200, "camara", "Reducao de emissoes de CO2.", "2024-01-06"),
        ]
        conn.executemany(
            "INSERT INTO discursos (hash_conteudo, parlamentar_id, casa, conteudo, data) "
            "VALUES (?, ?, ?, ?, ?)",
            registros,
        )
        intensidade_100 = intensidade_discursiva(100, "camara", aborto, conn)
        intensidade_200 = intensidade_discursiva(200, "camara", aborto, conn)
        assert intensidade_100 == 0.5  # 2/4
        assert intensidade_200 == 0.0
        # Parlamentar inexistente -> 0.0 sem erro
        assert intensidade_discursiva(999, "camara", aborto, conn) == 0.0
    finally:
        conn.close()


def test_random_state_determinismo() -> None:
    """TF-IDF é determinístico: rodar 2x produz mesmos scores."""
    df1 = tfidf_relevancia(_props_seed())
    df2 = tfidf_relevancia(_props_seed())
    assert df1["score_tfidf"].to_list() == df2["score_tfidf"].to_list()


def test_tfidf_levanta_se_sem_ementa() -> None:
    """Validação de schema do DataFrame de entrada."""
    import pytest

    df_sem_ementa = pl.DataFrame({"id": [1, 2], "casa": ["camara", "senado"]})
    with pytest.raises(ValueError, match="ementa"):
        tfidf_relevancia(df_sem_ementa)
