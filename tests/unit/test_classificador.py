"""Testes do orquestrador `classificar()` (S27)."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from hemiciclo.etl.migrations import aplicar_migrations
from hemiciclo.modelos.classificador import (
    CAMADAS_VALIDAS,
    classificar,
    salvar_resultado_json,
)

RAIZ = Path(__file__).resolve().parents[2]
TOPICOS_DIR = RAIZ / "topicos"


def _db_seed(path: Path, *, com_proposicao_id: bool = False) -> None:
    """Cria DuckDB seed com proposições+votações+votos para testes.

    Pós-S27.1: ``proposicao_id`` já existe em ``votacoes`` por padrão (M002
    aplicada por :func:`aplicar_migrations`). O parâmetro ``com_proposicao_id``
    apenas controla se inserimos linhas populadas (para exercitar o JOIN
    real do C1) ou deixamos a tabela vazia.
    """
    conn = duckdb.connect(str(path))
    try:
        aplicar_migrations(conn)
        proposicoes = [
            (
                1,
                "camara",
                "PL",
                1904,
                2024,
                "Dispoe sobre o aborto legal.",
                "Direitos Humanos, Minorias e Cidadania",
            ),
            (
                2,
                "camara",
                "PL",
                5069,
                2013,
                "Trata da interrupção voluntária da gravidez.",
                "Saúde",
            ),
            (3, "camara", "PL", 1, 2020, "Lei sobre transporte rodoviario.", "Transporte"),
        ]
        conn.executemany(
            "INSERT INTO proposicoes (id, casa, sigla, numero, ano, ementa, tema_oficial) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            proposicoes,
        )
        if com_proposicao_id:
            # M002 já criou a coluna; só populamos.
            conn.execute(
                "INSERT INTO votacoes (id, casa, descricao, proposicao_id) VALUES "
                "('v1', 'camara', 'votacao 1', 1)"
            )
            conn.executemany(
                "INSERT INTO votos (votacao_id, parlamentar_id, casa, voto) VALUES (?, ?, ?, ?)",
                [
                    ("v1", 100, "camara", "SIM"),
                    ("v1", 200, "camara", "NAO"),
                ],
            )
    finally:
        conn.close()


def test_classificar_camada_1_apenas(tmp_path: Path) -> None:
    db = tmp_path / "hemi.duckdb"
    _db_seed(db)
    home = tmp_path / "home"
    resultado = classificar(TOPICOS_DIR / "aborto.yaml", db, camadas=["regex"], home=home)
    assert resultado["topico"] == "aborto"
    assert resultado["camadas"] == ["regex"]
    assert resultado["n_props"] >= 2
    assert resultado["n_parlamentares"] == 0  # camada de voto não rodou
    assert resultado["top_a_favor"] == []


def test_classificar_camada_1_e_2(tmp_path: Path) -> None:
    db = tmp_path / "hemi.duckdb"
    _db_seed(db)
    home = tmp_path / "home"
    resultado = classificar(TOPICOS_DIR / "aborto.yaml", db, camadas=["regex", "tfidf"], home=home)
    assert "tfidf" in resultado["camadas"]
    assert resultado["n_props"] >= 2


def test_classificar_com_voto_real(tmp_path: Path) -> None:
    """Cenário completo: votos populados e proposicao_id presente -> agg funciona."""
    db = tmp_path / "hemi.duckdb"
    _db_seed(db, com_proposicao_id=True)
    home = tmp_path / "home"
    resultado = classificar(TOPICOS_DIR / "aborto.yaml", db, camadas=["regex", "votos"], home=home)
    assert resultado["n_parlamentares"] == 2
    a_favor_ids = {p["parlamentar_id"] for p in resultado["top_a_favor"]}
    contra_ids = {p["parlamentar_id"] for p in resultado["top_contra"]}
    assert 100 in a_favor_ids
    assert 200 in contra_ids


def test_persiste_resultado_em_cache(tmp_path: Path) -> None:
    db = tmp_path / "hemi.duckdb"
    _db_seed(db)
    home = tmp_path / "home"
    resultado = classificar(TOPICOS_DIR / "aborto.yaml", db, camadas=["regex"], home=home)
    cache_parquet = Path(resultado["cache_parquet"])
    assert cache_parquet.exists()
    assert cache_parquet.parent.name == "classificacoes"


def test_camadas_invalidas_falha(tmp_path: Path) -> None:
    db = tmp_path / "hemi.duckdb"
    _db_seed(db)
    with pytest.raises(ValueError, match="camadas invalidas"):
        classificar(
            TOPICOS_DIR / "aborto.yaml",
            db,
            camadas=["embeddings"],
            home=tmp_path / "home",
        )


def test_db_inexistente_falha(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        classificar(
            TOPICOS_DIR / "aborto.yaml",
            tmp_path / "nao_existe.duckdb",
            home=tmp_path / "home",
        )


def test_camadas_validas_inclui_regex_votos_tfidf() -> None:
    assert {"regex", "votos", "tfidf"} == CAMADAS_VALIDAS


def test_salvar_resultado_json(tmp_path: Path) -> None:
    db = tmp_path / "hemi.duckdb"
    _db_seed(db)
    home = tmp_path / "home"
    resultado = classificar(TOPICOS_DIR / "aborto.yaml", db, camadas=["regex"], home=home)
    destino = tmp_path / "out.json"
    salvar_resultado_json(resultado, destino)
    assert destino.exists()
    deserializado = json.loads(destino.read_text(encoding="utf-8"))
    assert deserializado["topico"] == "aborto"
