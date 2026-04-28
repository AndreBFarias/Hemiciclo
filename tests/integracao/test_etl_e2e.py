"""Testes e2e do ETL S26: workflow CLI completo init -> consolidar -> info.

Estes testes não chamam APIs externas; geram parquets fixturizados em
``tmp_path`` que respeitam o schema produzido por S24/S25 (12 colunas em
proposições/matérias).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl
import pytest
from typer.testing import CliRunner

from hemiciclo.cli import app


@pytest.fixture
def runner() -> CliRunner:
    """CliRunner Typer reutilizável."""
    return CliRunner()


def _criar_parquet_camara(dir_saida: Path, n: int = 10) -> None:
    """Cria proposicoes.parquet (Câmara) em ``dir_saida``."""
    df = pl.DataFrame(
        {
            "id": [1000 + i for i in range(n)],
            "sigla": ["PL"] * n,
            "numero": list(range(n)),
            "ano": [2024] * n,
            "ementa": [f"ementa camara {i} sobre aborto" for i in range(n)],
            "tema_oficial": ["Tema A"] * n,
            "autor_principal": ["Autor C"] * n,
            "data_apresentacao": ["2024-01-01"] * n,
            "status": ["Em tramitação"] * n,
            "url_inteiro_teor": ["http://x"] * n,
            "casa": ["camara"] * n,
            "hash_conteudo": [f"hcam{i:012d}" for i in range(n)],
        }
    )
    dir_saida.mkdir(parents=True, exist_ok=True)
    df.write_parquet(dir_saida / "proposicoes.parquet")


def _criar_parquet_senado(dir_saida: Path, n: int = 10) -> None:
    """Cria materias.parquet (Senado) em ``dir_saida``."""
    df = pl.DataFrame(
        {
            "id": [9000 + i for i in range(n)],
            "sigla": ["PLS"] * n,
            "numero": list(range(n)),
            "ano": [2024] * n,
            "ementa": [f"ementa senado {i} sobre aborto" for i in range(n)],
            "tema_oficial": ["Tema B"] * n,
            "autor_principal": ["Autor S"] * n,
            "data_apresentacao": ["2024-01-02"] * n,
            "status": ["Em tramitação"] * n,
            "url_inteiro_teor": ["http://y"] * n,
            "casa": ["senado"] * n,
            "hash_conteudo": [f"hsen{i:012d}" for i in range(n)],
        }
    )
    dir_saida.mkdir(parents=True, exist_ok=True)
    df.write_parquet(dir_saida / "materias.parquet")


def test_init_consolidar_info_workflow(
    runner: CliRunner, tmp_hemiciclo_home: Path, tmp_path: Path
) -> None:
    """Ciclo CLI completo: init -> consolidar (Câmara + Senado) -> info."""
    db = tmp_path / "hemi.duckdb"
    parquets_c = tmp_path / "camara"
    parquets_s = tmp_path / "senado"
    _criar_parquet_camara(parquets_c, n=10)
    _criar_parquet_senado(parquets_s, n=10)

    # init
    r1 = runner.invoke(app, ["db", "init", "--db-path", str(db)])
    assert r1.exit_code == 0, r1.stdout
    # Pós-S27.1: schema v2 ativo. Mantemos teste tolerante a futuras migrations.
    assert "schema v" in r1.stdout

    # consolidar Câmara
    r2 = runner.invoke(
        app, ["db", "consolidar", "--parquets", str(parquets_c), "--db-path", str(db)]
    )
    assert r2.exit_code == 0, r2.stdout
    assert "proposicoes: +10" in r2.stdout

    # consolidar Senado
    r3 = runner.invoke(
        app, ["db", "consolidar", "--parquets", str(parquets_s), "--db-path", str(db)]
    )
    assert r3.exit_code == 0, r3.stdout
    assert "proposicoes: +10" in r3.stdout

    # info final
    r4 = runner.invoke(app, ["db", "info", "--db-path", str(db)])
    assert r4.exit_code == 0, r4.stdout
    assert "proposicoes: 20" in r4.stdout
    assert "votacoes: 0" in r4.stdout


def test_consolidar_camara_e_senado_juntos(
    runner: CliRunner, tmp_hemiciclo_home: Path, tmp_path: Path
) -> None:
    """Câmara e Senado coexistem na mesma tabela `proposicoes` discriminados por casa."""
    db = tmp_path / "hemi.duckdb"
    dir_misto = tmp_path / "misto"
    _criar_parquet_camara(dir_misto, n=10)
    _criar_parquet_senado(dir_misto, n=10)

    runner.invoke(app, ["db", "init", "--db-path", str(db)])
    runner.invoke(app, ["db", "consolidar", "--parquets", str(dir_misto), "--db-path", str(db)])

    conn = duckdb.connect(str(db))
    try:
        contagem = conn.execute(
            "SELECT casa, COUNT(*) FROM proposicoes GROUP BY casa ORDER BY casa"
        ).fetchall()
    finally:
        conn.close()
    assert contagem == [("camara", 10), ("senado", 10)]


def test_query_cross_casa(runner: CliRunner, tmp_hemiciclo_home: Path, tmp_path: Path) -> None:
    """SELECT WHERE ementa LIKE retorna proposições de ambas as casas."""
    db = tmp_path / "hemi.duckdb"
    dir_misto = tmp_path / "misto"
    _criar_parquet_camara(dir_misto, n=5)
    _criar_parquet_senado(dir_misto, n=5)

    runner.invoke(app, ["db", "init", "--db-path", str(db)])
    runner.invoke(app, ["db", "consolidar", "--parquets", str(dir_misto), "--db-path", str(db)])

    conn = duckdb.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT casa, COUNT(*) FROM proposicoes "
            "WHERE ementa LIKE '%aborto%' GROUP BY casa ORDER BY casa"
        ).fetchall()
    finally:
        conn.close()
    # Ambos parquets contém "aborto" na ementa.
    assert rows == [("camara", 5), ("senado", 5)]
