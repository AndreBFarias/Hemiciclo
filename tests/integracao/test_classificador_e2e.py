"""Testes e2e do pipeline de classificação (S27).

Cobrem o ciclo `db init -> popular -> classificar` ponta a ponta, o
encadeamento de camadas C1+C2, e a desligabilidade de cada camada.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
from typer.testing import CliRunner

from hemiciclo.cli import app
from hemiciclo.etl.migrations import aplicar_migrations
from hemiciclo.modelos.classificador import classificar

RAIZ = Path(__file__).resolve().parents[2]
TOPICOS_DIR = RAIZ / "topicos"


def _seed_db_completo(db_path: Path) -> None:
    """DB com schema v2 (S27.1), proposições casando 'aborto' e votações com ``proposicao_id``."""
    conn = duckdb.connect(str(db_path))
    try:
        aplicar_migrations(conn)
        # Pós-S27.1: M002 já adicionou `proposicao_id` em `votacoes`.
        # ALTER explícito anterior virou redundante.

        conn.executemany(
            "INSERT INTO proposicoes (id, casa, sigla, numero, ano, ementa, tema_oficial) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    1,
                    "camara",
                    "PL",
                    1904,
                    2024,
                    "Dispoe sobre o aborto legal em casos de estupro.",
                    "Saúde",
                ),
                (
                    2,
                    "senado",
                    "PEC",
                    29,
                    2015,
                    "Estatuto do nascituro -- direito ao nascimento desde a concepcao.",
                    "Direitos Humanos",
                ),
                (
                    3,
                    "camara",
                    "PL",
                    7,
                    2020,
                    "Lei sobre transporte rodoviario interestadual.",
                    "Transporte",
                ),
            ],
        )
        conn.execute(
            "INSERT INTO votacoes (id, casa, descricao, proposicao_id) VALUES "
            "('v1', 'camara', 'votacao 1', 1), "
            "('v2', 'camara', 'votacao 2', 1), "
            "('v3', 'senado', 'votacao A', 2)"
        )
        conn.executemany(
            "INSERT INTO votos (votacao_id, parlamentar_id, casa, voto) VALUES (?, ?, ?, ?)",
            [
                ("v1", 100, "camara", "SIM"),
                ("v1", 200, "camara", "NAO"),
                ("v2", 100, "camara", "SIM"),
                ("v2", 200, "camara", "NAO"),
                ("v3", 500, "senado", "NAO"),
            ],
        )
    finally:
        conn.close()


def test_classificar_aborto_em_db_seed(tmp_path: Path) -> None:
    """Workflow C1+C2 completo no aborto.yaml gera resultado coerente."""
    db = tmp_path / "hemi.duckdb"
    _seed_db_completo(db)
    home = tmp_path / "home"
    resultado = classificar(
        topico_yaml=TOPICOS_DIR / "aborto.yaml",
        db_path=db,
        camadas=["regex", "votos", "tfidf"],
        home=home,
    )
    assert resultado["topico"] == "aborto"
    assert resultado["n_props"] >= 2
    assert resultado["n_parlamentares"] == 3
    a_favor_ids = {p["parlamentar_id"] for p in resultado["top_a_favor"]}
    contra_ids = {p["parlamentar_id"] for p in resultado["top_contra"]}
    assert 100 in a_favor_ids
    assert 200 in contra_ids
    assert 500 in contra_ids
    cache = Path(resultado["cache_parquet"])
    assert cache.exists()


def test_workflow_db_init_consolidar_classificar_via_cli(tmp_path: Path) -> None:
    """Cobre `hemiciclo db init` + popular dados + `hemiciclo classificar`."""
    runner = CliRunner()
    db = tmp_path / "hemi.duckdb"
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)

    env = {
        **os.environ,
        "COLUMNS": "200",
        "TERM": "dumb",
        "NO_COLOR": "1",
        "HEMICICLO_HOME": str(home),
    }

    # 1. db init
    r1 = runner.invoke(app, ["db", "init", "--db-path", str(db)], env=env)
    assert r1.exit_code == 0, r1.stdout
    assert "schema v" in r1.stdout

    # 2. popular DB com seed (em vez de coletar APIs reais -- isolado)
    _seed_db_completo(db)

    # 3. classificar via CLI
    out = tmp_path / "resultado.json"
    r2 = runner.invoke(
        app,
        [
            "classificar",
            "--topico",
            str(TOPICOS_DIR / "aborto.yaml"),
            "--db-path",
            str(db),
            "--camadas",
            "regex,votos,tfidf",
            "--output",
            str(out),
        ],
        env=env,
    )
    assert r2.exit_code == 0, r2.stdout
    assert "aborto" in r2.stdout
    assert out.exists()
    import json

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["topico"] == "aborto"
    assert payload["n_props"] >= 2
    assert payload["n_parlamentares"] == 3


def test_join_apos_consolidacao_real_de_parquets_s27_1(tmp_path: Path) -> None:
    """Pipeline real S27.1: parquets de votações com ``proposicao_id`` -> consolidador -> C1.

    Prova que após :func:`consolidar_parquets_em_duckdb`, a coluna
    ``proposicao_id`` chega populada na tabela ``votacoes`` e o JOIN do
    classificador C1 retorna agregação não-vazia. Substitui a simulação
    via ``ALTER TABLE`` dos testes anteriores por fluxo ponta a ponta.
    """
    import polars as pl

    from hemiciclo.etl.consolidador import consolidar_parquets_em_duckdb
    from hemiciclo.etl.topicos import carregar_topico
    from hemiciclo.modelos.classificador_c1 import (
        agregar_voto_por_parlamentar,
        proposicoes_relevantes,
    )

    dir_p = tmp_path / "parquets"
    dir_p.mkdir(parents=True)

    # 1. Parquet de proposições casando "aborto"
    pl.DataFrame(
        {
            "id": [1],
            "sigla": ["PL"],
            "numero": [1904],
            "ano": [2024],
            "ementa": ["Dispoe sobre o aborto legal."],
            "tema_oficial": ["Saúde"],
            "autor_principal": ["Autor"],
            "data_apresentacao": ["2024-01-01"],
            "status": ["Em tramitacao"],
            "url_inteiro_teor": [""],
            "casa": ["camara"],
            "hash_conteudo": ["h1"],
        }
    ).write_parquet(dir_p / "proposicoes.parquet")

    # 2. Parquet de votações com proposicao_id apontando para a proposição 1
    pl.DataFrame(
        {
            "id": ["v1", "v2"],
            "data": ["2024-03-01", "2024-03-15"],
            "descricao": ["votacao 1", "votacao 2"],
            "proposicao_id": [1, 1],
            "resultado": ["Aprovado", "Aprovado"],
            "casa": ["camara", "camara"],
        }
    ).write_parquet(dir_p / "votacoes.parquet")

    # 3. Parquet de votos
    pl.DataFrame(
        {
            "votacao_id": ["v1", "v1", "v2", "v2"],
            "deputado_id": [100, 200, 100, 200],
            "voto": ["Sim", "Nao", "Sim", "Nao"],
            "partido": ["X", "Y", "X", "Y"],
            "uf": ["SP", "RJ", "SP", "RJ"],
        }
    ).write_parquet(dir_p / "votos.parquet")

    # 4. Consolida tudo no DuckDB
    db = tmp_path / "hemi.duckdb"
    contagens = consolidar_parquets_em_duckdb(dir_p, db)
    assert contagens == {"proposicoes": 1, "votacoes": 2, "votos": 4}

    # 5. Classifica usando JOIN real (sem fallback nem ALTER TABLE manual)
    aborto = carregar_topico(TOPICOS_DIR / "aborto.yaml")
    conn = duckdb.connect(str(db))
    try:
        props = proposicoes_relevantes(aborto, conn)
        assert len(props) >= 1
        df_agg = agregar_voto_por_parlamentar(props, conn)
        assert len(df_agg) == 2  # parlamentares 100 e 200
        registros = {row["parlamentar_id"]: row for row in df_agg.iter_rows(named=True)}
        assert registros[100]["proporcao_sim"] == 1.0
        assert registros[100]["posicao_agregada"] == "A_FAVOR"
        assert registros[200]["proporcao_sim"] == 0.0
        assert registros[200]["posicao_agregada"] == "CONTRA"
    finally:
        conn.close()


def test_camadas_desligaveis(tmp_path: Path) -> None:
    """Cada camada pode ser desligada individualmente sem quebrar o pipeline."""
    db = tmp_path / "hemi.duckdb"
    _seed_db_completo(db)
    home = tmp_path / "home"

    # Só regex -- sem voto, sem tfidf
    r1 = classificar(
        topico_yaml=TOPICOS_DIR / "aborto.yaml",
        db_path=db,
        camadas=["regex"],
        home=home,
    )
    assert r1["camadas"] == ["regex"]
    assert r1["n_props"] >= 2
    assert r1["n_parlamentares"] == 0

    # Só regex+tfidf
    r2 = classificar(
        topico_yaml=TOPICOS_DIR / "aborto.yaml",
        db_path=db,
        camadas=["regex", "tfidf"],
        home=home,
    )
    assert "tfidf" in r2["camadas"]
    assert r2["n_parlamentares"] == 0

    # regex+votos sem tfidf
    r3 = classificar(
        topico_yaml=TOPICOS_DIR / "aborto.yaml",
        db_path=db,
        camadas=["regex", "votos"],
        home=home,
    )
    assert "tfidf" not in r3["camadas"]
    assert r3["n_parlamentares"] == 3
