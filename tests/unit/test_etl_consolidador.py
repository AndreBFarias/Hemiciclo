"""Testes do consolidador parquets -> DuckDB (S26)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl
import pytest

from hemiciclo.etl.consolidador import consolidar_parquets_em_duckdb


def _parquet_proposicoes_camara(dir_saida: Path, n: int = 10) -> Path:
    """Cria um proposicoes.parquet de Câmara (12 colunas) com ``n`` linhas."""
    df = pl.DataFrame(
        {
            "id": [1000 + i for i in range(n)],
            "sigla": ["PL"] * n,
            "numero": [i for i in range(n)],
            "ano": [2024] * n,
            "ementa": [f"ementa fake {i} sobre tema X" for i in range(n)],
            "tema_oficial": ["Tema A"] * n,
            "autor_principal": ["Autor"] * n,
            "data_apresentacao": ["2024-01-01"] * n,
            "status": ["Em tramitação"] * n,
            "url_inteiro_teor": ["http://x"] * n,
            "casa": ["camara"] * n,
            "hash_conteudo": [f"hash{i:012d}" for i in range(n)],
        }
    )
    arq = dir_saida / "proposicoes.parquet"
    arq.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(arq)
    return arq


def _parquet_materias_senado(dir_saida: Path, n: int = 10) -> Path:
    """Cria materias.parquet do Senado (mesmo schema 12-col, casa='senado')."""
    df = pl.DataFrame(
        {
            "id": [9000 + i for i in range(n)],
            "sigla": ["PLS"] * n,
            "numero": [i for i in range(n)],
            "ano": [2024] * n,
            "ementa": [f"materia senado {i} sobre aborto" for i in range(n)],
            "tema_oficial": ["Tema B"] * n,
            "autor_principal": ["Autor S"] * n,
            "data_apresentacao": ["2024-01-02"] * n,
            "status": ["Em tramitação"] * n,
            "url_inteiro_teor": ["http://y"] * n,
            "casa": ["senado"] * n,
            "hash_conteudo": [f"sh{i:014d}" for i in range(n)],
        }
    )
    arq = dir_saida / "materias.parquet"
    arq.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(arq)
    return arq


def test_consolidar_proposicoes_camara(tmp_path: Path) -> None:
    """Consolidar proposicoes.parquet com 10 linhas insere 10 rows na tabela."""
    dir_p = tmp_path / "parquets"
    _parquet_proposicoes_camara(dir_p, n=10)
    db = tmp_path / "hemi.duckdb"
    contagens = consolidar_parquets_em_duckdb(dir_p, db)
    assert contagens == {"proposicoes": 10}

    conn = duckdb.connect(str(db))
    try:
        total_row = conn.execute("SELECT COUNT(*) FROM proposicoes WHERE casa='camara'").fetchone()
        assert total_row is not None
        assert total_row[0] == 10
    finally:
        conn.close()


def test_consolidar_materias_senado(tmp_path: Path) -> None:
    """Consolidar materias.parquet vai para a mesma tabela proposicoes com casa='senado'."""
    dir_p = tmp_path / "parquets"
    _parquet_materias_senado(dir_p, n=10)
    db = tmp_path / "hemi.duckdb"
    contagens = consolidar_parquets_em_duckdb(dir_p, db)
    assert contagens == {"proposicoes": 10}

    conn = duckdb.connect(str(db))
    try:
        total_row = conn.execute("SELECT COUNT(*) FROM proposicoes WHERE casa='senado'").fetchone()
        assert total_row is not None
        assert total_row[0] == 10
    finally:
        conn.close()


def test_consolidar_idempotente(tmp_path: Path) -> None:
    """Rodar duas vezes não duplica linhas (INSERT OR IGNORE)."""
    dir_p = tmp_path / "parquets"
    _parquet_proposicoes_camara(dir_p, n=5)
    db = tmp_path / "hemi.duckdb"

    c1 = consolidar_parquets_em_duckdb(dir_p, db)
    c2 = consolidar_parquets_em_duckdb(dir_p, db)
    assert c1 == {"proposicoes": 5}
    assert c2 == {}  # nada novo

    conn = duckdb.connect(str(db))
    try:
        total_row = conn.execute("SELECT COUNT(*) FROM proposicoes").fetchone()
        assert total_row is not None
        assert total_row[0] == 5
    finally:
        conn.close()


def test_dir_vazio_nao_falha(tmp_path: Path) -> None:
    """Diretório vazio (sem parquets reconhecidos) retorna dict vazio sem erro."""
    dir_p = tmp_path / "vazio"
    dir_p.mkdir()
    db = tmp_path / "hemi.duckdb"
    contagens = consolidar_parquets_em_duckdb(dir_p, db)
    assert contagens == {}

    # Mesmo assim o DB foi criado e migrations aplicadas.
    conn = duckdb.connect(str(db))
    try:
        nomes = {
            linha[0]
            for linha in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        assert "proposicoes" in nomes
    finally:
        conn.close()


def test_arquivo_corrompido_loga_e_continua(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Parquet corrompido é logado e ignorado; outros arquivos válidos continuam."""
    dir_p = tmp_path / "parquets"
    dir_p.mkdir()
    # Arquivo "proposicoes.parquet" com bytes inválidos.
    (dir_p / "proposicoes.parquet").write_bytes(b"corrompido nao parquet")
    # E um materias.parquet válido.
    _parquet_materias_senado(dir_p, n=3)

    db = tmp_path / "hemi.duckdb"
    contagens = consolidar_parquets_em_duckdb(dir_p, db)
    # proposicoes.parquet falhou (0); materias.parquet inseriu 3 em proposicoes.
    assert contagens == {"proposicoes": 3}


def _parquet_votacoes_camara(dir_saida: Path, n: int = 3) -> Path:
    df = pl.DataFrame(
        {
            "id": [f"v{i}" for i in range(n)],
            "data": ["2024-01-01"] * n,
            "descricao": [f"vot {i}" for i in range(n)],
            "proposicao_id": list(range(n)),
            "resultado": ["Aprovado"] * n,
            "casa": ["camara"] * n,
        }
    )
    arq = dir_saida / "votacoes.parquet"
    arq.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(arq)
    return arq


def _parquet_votacoes_senado(dir_saida: Path, n: int = 3) -> Path:
    """Cria parquet de votações do Senado no schema v2 (S27.1, ``proposicao_id``).

    Antes de S27.1 a coluna chamava ``materia_id`` -- compatibilidade legada
    é coberta por outro teste dedicado (``test_consolidar_votacoes_senado_legado``).
    """
    df = pl.DataFrame(
        {
            "id": list(range(100, 100 + n)),
            "data": ["2024-02-01"] * n,
            "descricao": [f"vot s {i}" for i in range(n)],
            "proposicao_id": list(range(n)),
            "resultado": ["Aprovado"] * n,
            "casa": ["senado"] * n,
        }
    )
    arq = dir_saida / "votacoes_senado.parquet"
    arq.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(arq)
    return arq


def _parquet_votos_camara(dir_saida: Path, n: int = 3) -> Path:
    df = pl.DataFrame(
        {
            "votacao_id": ["v0"] * n,
            "deputado_id": list(range(n)),
            "voto": ["Sim"] * n,
            "partido": ["X"] * n,
            "uf": ["SP"] * n,
        }
    )
    arq = dir_saida / "votos.parquet"
    arq.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(arq)
    return arq


def _parquet_votos_senado(dir_saida: Path, n: int = 3) -> Path:
    df = pl.DataFrame(
        {
            "votacao_id": [100] * n,
            "senador_id": list(range(n)),
            "voto": ["Sim"] * n,
            "partido": ["Y"] * n,
            "uf": ["RJ"] * n,
        }
    )
    arq = dir_saida / "votos_senado.parquet"
    arq.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(arq)
    return arq


def _parquet_discursos_camara(dir_saida: Path, n: int = 3) -> Path:
    df = pl.DataFrame(
        {
            "id": [f"d{i}" for i in range(n)],
            "deputado_id": list(range(n)),
            "data": ["2024-01-10"] * n,
            "tipo": ["Discurso"] * n,
            "sumario": [f"sumario {i}" for i in range(n)],
            "url_audio": [""] * n,
            "url_video": [""] * n,
            "transcricao": [f"texto {i}" for i in range(n)],
            "hash_conteudo": [f"hd{i:014d}" for i in range(n)],
        }
    )
    arq = dir_saida / "discursos.parquet"
    arq.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(arq)
    return arq


def _parquet_discursos_senado(dir_saida: Path, n: int = 3) -> Path:
    df = pl.DataFrame(
        {
            "id": [f"ds{i}" for i in range(n)],
            "senador_id": list(range(n)),
            "data": ["2024-02-10"] * n,
            "tipo": ["Discurso"] * n,
            "sumario": [f"sum s {i}" for i in range(n)],
            "url_audio": [""] * n,
            "url_video": [""] * n,
            "transcricao": [f"texto s {i}" for i in range(n)],
            "hash_conteudo": [f"hs{i:014d}" for i in range(n)],
        }
    )
    arq = dir_saida / "discursos_senado.parquet"
    arq.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(arq)
    return arq


def _parquet_deputados(dir_saida: Path, n: int = 3) -> Path:
    df = pl.DataFrame(
        {
            "id": list(range(n)),
            "nome": [f"Dep {i}" for i in range(n)],
            "nome_eleitoral": [f"Dep{i}" for i in range(n)],
            "partido": ["X"] * n,
            "uf": ["SP"] * n,
            "legislatura": [57] * n,
            "email": [""] * n,
        }
    )
    arq = dir_saida / "deputados.parquet"
    arq.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(arq)
    return arq


def _parquet_senadores(dir_saida: Path, n: int = 3) -> Path:
    df = pl.DataFrame(
        {
            "id": list(range(100, 100 + n)),
            "nome": [f"Sen {i}" for i in range(n)],
            "nome_eleitoral": [f"Sen{i}" for i in range(n)],
            "partido": ["Y"] * n,
            "uf": ["RJ"] * n,
            "legislatura": [56] * n,
            "email": [""] * n,
        }
    )
    arq = dir_saida / "senadores.parquet"
    arq.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(arq)
    return arq


def test_consolidar_todos_os_tipos(tmp_path: Path) -> None:
    """Consolida todos os 10 nomes de parquet (Câmara + Senado) num único call."""
    dir_p = tmp_path / "parquets"
    _parquet_proposicoes_camara(dir_p, n=2)
    _parquet_materias_senado(dir_p, n=2)
    _parquet_votacoes_camara(dir_p, n=2)
    _parquet_votacoes_senado(dir_p, n=2)
    _parquet_votos_camara(dir_p, n=2)
    _parquet_votos_senado(dir_p, n=2)
    _parquet_discursos_camara(dir_p, n=2)
    _parquet_discursos_senado(dir_p, n=2)
    _parquet_deputados(dir_p, n=2)
    _parquet_senadores(dir_p, n=2)

    db = tmp_path / "hemi.duckdb"
    contagens = consolidar_parquets_em_duckdb(dir_p, db)
    assert contagens == {
        "proposicoes": 4,
        "votacoes": 4,
        "votos": 4,
        "discursos": 4,
        "parlamentares": 4,
    }

    conn = duckdb.connect(str(db))
    try:
        for tabela, esperado in [
            ("proposicoes", 4),
            ("votacoes", 4),
            ("votos", 4),
            ("discursos", 4),
            ("parlamentares", 4),
        ]:
            linha = conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()
            assert linha is not None
            assert linha[0] == esperado, f"tabela {tabela} esperava {esperado}, viu {linha[0]}"
    finally:
        conn.close()


def test_dir_inexistente_retorna_dict_vazio(tmp_path: Path) -> None:
    """Diretório inexistente apenas loga warning e retorna dict vazio (sem raise)."""
    db = tmp_path / "hemi.duckdb"
    contagens = consolidar_parquets_em_duckdb(tmp_path / "naoexiste", db)
    assert contagens == {}


# ---------------------------------------------------------------------------
# S27.1 -- proposicao_id propagado e compat retroativa de parquets antigos.
# ---------------------------------------------------------------------------


def test_proposicao_id_persiste_camara(tmp_path: Path) -> None:
    """Parquet de votações Câmara com ``proposicao_id`` chega ao DuckDB intacto."""
    dir_p = tmp_path / "parquets"
    _parquet_votacoes_camara(dir_p, n=4)
    db = tmp_path / "hemi.duckdb"
    contagens = consolidar_parquets_em_duckdb(dir_p, db)
    assert contagens == {"votacoes": 4}

    conn = duckdb.connect(str(db))
    try:
        ids = sorted(
            row[0]
            for row in conn.execute(
                "SELECT proposicao_id FROM votacoes WHERE casa='camara' ORDER BY id"
            ).fetchall()
        )
        assert ids == [0, 1, 2, 3]
    finally:
        conn.close()


def test_proposicao_id_persiste_senado(tmp_path: Path) -> None:
    """Parquet de votações Senado v2 (``proposicao_id``) é consolidado igual à Câmara."""
    dir_p = tmp_path / "parquets"
    _parquet_votacoes_senado(dir_p, n=3)
    db = tmp_path / "hemi.duckdb"
    contagens = consolidar_parquets_em_duckdb(dir_p, db)
    assert contagens == {"votacoes": 3}

    conn = duckdb.connect(str(db))
    try:
        rows = conn.execute(
            "SELECT id, proposicao_id FROM votacoes WHERE casa='senado' ORDER BY id"
        ).fetchall()
        assert [r[1] for r in rows] == [0, 1, 2]
    finally:
        conn.close()


def test_consolidar_votacoes_senado_legado_materia_id(tmp_path: Path) -> None:
    """Compat: parquet com coluna antiga ``materia_id`` é mapeado para ``proposicao_id``."""
    dir_p = tmp_path / "parquets"
    dir_p.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(
        {
            "id": [200, 201, 202],
            "data": ["2020-01-01"] * 3,
            "descricao": ["a", "b", "c"],
            "materia_id": [10, 20, 30],  # schema legado pré-S27.1
            "resultado": ["Aprovado"] * 3,
            "casa": ["senado"] * 3,
        }
    )
    df.write_parquet(dir_p / "votacoes_senado.parquet")

    db = tmp_path / "hemi.duckdb"
    contagens = consolidar_parquets_em_duckdb(dir_p, db)
    assert contagens == {"votacoes": 3}

    conn = duckdb.connect(str(db))
    try:
        rows = sorted(
            conn.execute("SELECT proposicao_id FROM votacoes WHERE casa='senado'").fetchall()
        )
        assert [r[0] for r in rows] == [10, 20, 30]
    finally:
        conn.close()


def test_consolidar_votacoes_legado_sem_proposicao_id(tmp_path: Path) -> None:
    """Compat: parquet sem ``proposicao_id`` nem ``materia_id`` resulta em NULL."""
    dir_p = tmp_path / "parquets"
    dir_p.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(
        {
            "id": ["v_legado_1", "v_legado_2"],
            "data": ["2020-01-01"] * 2,
            "descricao": ["x", "y"],
            "resultado": ["Aprovado"] * 2,
            "casa": ["camara"] * 2,
        }
    )
    df.write_parquet(dir_p / "votacoes.parquet")

    db = tmp_path / "hemi.duckdb"
    contagens = consolidar_parquets_em_duckdb(dir_p, db)
    assert contagens == {"votacoes": 2}

    conn = duckdb.connect(str(db))
    try:
        rows = conn.execute("SELECT proposicao_id FROM votacoes WHERE casa='camara'").fetchall()
        assert all(r[0] is None for r in rows)
    finally:
        conn.close()


def test_inserir_proposicoes_detalhe_atualiza_4_colunas(tmp_path: Path) -> None:
    """S24b: parquet de detalhe atualiza 4 colunas de ``proposicoes`` via UPDATE.

    Cenário:
    1. Insere proposições da Câmara COM colunas vazias.
    2. Roda consolidador também com ``proposicoes_detalhe.parquet``.
    3. SELECT confirma que tema_oficial/autor_principal/status/url_inteiro_teor
       foram preenchidos.
    4. ``COALESCE`` preserva valor existente quando detalhe vem NULL.
    """
    dir_p = tmp_path / "parquets"
    dir_p.mkdir(parents=True, exist_ok=True)

    # Listagem com 4 campos vazios (estado pré-S24b).
    df_list = pl.DataFrame(
        {
            "id": [1, 2, 3],
            "sigla": ["PL"] * 3,
            "numero": [1, 2, 3],
            "ano": [2024] * 3,
            "ementa": ["e1", "e2", "e3"],
            "tema_oficial": ["", "", ""],
            "autor_principal": ["", "", ""],
            "data_apresentacao": ["2024-01-01"] * 3,
            "status": ["", "", ""],
            "url_inteiro_teor": ["", "", ""],
            "casa": ["camara"] * 3,
            "hash_conteudo": [f"h{i:014d}" for i in range(3)],
        }
    )
    df_list.write_parquet(dir_p / "proposicoes.parquet")

    # Detalhe com valores reais nas 3 proposições; id=2 propositadamente
    # mantém ``autor_principal = None`` (testa COALESCE preservar).
    df_det = pl.DataFrame(
        {
            "id": [1, 2, 3],
            "casa": ["camara"] * 3,
            "tema_oficial": ["Saúde", "Educação", "Economia"],
            "autor_principal": ["Deputado A", None, "Deputado C"],
            "status": ["Em tramitação", "Arquivada", "Sancionada"],
            "url_inteiro_teor": [
                "https://x/1.pdf",
                "https://x/2.pdf",
                "https://x/3.pdf",
            ],
            "enriquecido_em": ["2026-04-28T12:00:00+00:00"] * 3,
        },
        schema={
            "id": pl.Int64(),
            "casa": pl.Utf8(),
            "tema_oficial": pl.Utf8(),
            "autor_principal": pl.Utf8(),
            "status": pl.Utf8(),
            "url_inteiro_teor": pl.Utf8(),
            "enriquecido_em": pl.Utf8(),
        },
    )
    df_det.write_parquet(dir_p / "proposicoes_detalhe.parquet")

    db = tmp_path / "hemi.duckdb"
    contagens = consolidar_parquets_em_duckdb(dir_p, db)
    # Listagem inseriu 3; detalhe atualizou 3 (delta tema_oficial não-vazio).
    assert contagens.get("proposicoes", 0) >= 3

    conn = duckdb.connect(str(db))
    try:
        # Total Câmara presente.
        total_row = conn.execute("SELECT COUNT(*) FROM proposicoes WHERE casa='camara'").fetchone()
        assert total_row is not None
        assert total_row[0] == 3

        # tema_oficial preenchido em todas (3/3).
        com_tema_row = conn.execute(
            "SELECT COUNT(*) FROM proposicoes "
            "WHERE casa='camara' AND tema_oficial IS NOT NULL "
            "AND tema_oficial <> ''"
        ).fetchone()
        assert com_tema_row is not None
        assert com_tema_row[0] == 3

        # autor_principal: 2 preenchidos (id=2 ficou COALESCE com '' original).
        autor_id1_row = conn.execute(
            "SELECT autor_principal FROM proposicoes WHERE id=1 AND casa='camara'"
        ).fetchone()
        assert autor_id1_row is not None
        assert autor_id1_row[0] == "Deputado A"

        # status preenchido em 3.
        status_row = conn.execute(
            "SELECT status FROM proposicoes WHERE id=2 AND casa='camara'"
        ).fetchone()
        assert status_row is not None
        assert status_row[0] == "Arquivada"

        # url preenchido em 3.
        url_row = conn.execute(
            "SELECT url_inteiro_teor FROM proposicoes WHERE id=3 AND casa='camara'"
        ).fetchone()
        assert url_row is not None
        assert url_row[0] == "https://x/3.pdf"
    finally:
        conn.close()
