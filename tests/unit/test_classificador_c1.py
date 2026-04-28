"""Testes da camada 1 do classificador (S27)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl

from hemiciclo.etl.migrations import aplicar_migrations
from hemiciclo.etl.topicos import carregar_topico
from hemiciclo.modelos.classificador_c1 import (
    PosicaoAgregada,
    _categorizar,
    agregar_voto_por_parlamentar,
    proposicoes_relevantes,
)

RAIZ = Path(__file__).resolve().parents[2]
TOPICOS_DIR = RAIZ / "topicos"


def _conn_seed() -> duckdb.DuckDBPyConnection:
    """Conexão DuckDB em memória com schema v1 + dados sintéticos minimos."""
    conn = duckdb.connect(":memory:")
    aplicar_migrations(conn)
    # Insere proposições didáticas que casam diferentes facetas do tópico
    # 'aborto' (keyword direta, regex de interrupção da gravidez, categoria
    # oficial 'Saúde', exclusão 'aborto espontâneo' e 'aborto da emenda').
    proposicoes = [
        (
            1,
            "camara",
            "PL",
            1904,
            2024,
            "Dispoe sobre o aborto legal em casos de estupro.",
            "Direitos Humanos, Minorias e Cidadania",
        ),
        (
            2,
            "camara",
            "PL",
            5069,
            2013,
            "Trata da interrupção voluntária da gravidez por anencefalia.",
            "Saúde",
        ),
        (
            3,
            "camara",
            "PL",
            1,
            2020,
            "Lei sobre transporte rodoviario interestadual.",
            "Transporte",
        ),
        (
            4,
            "senado",
            "PEC",
            29,
            2015,
            "Estatuto do nascituro e direito ao nascimento.",
            "Direitos Humanos",
        ),
        (5, "camara", "PL", 999, 2024, "Estatisticas de aborto espontaneo no SUS.", "Saúde"),
        (
            6,
            "camara",
            "REQ",
            7,
            2021,
            "Aborto da emenda apresentada na votacao anterior.",
            "Trabalho",
        ),
        # Categoria 'Saúde' sem keyword -- deve casar via categoria oficial
        (7, "senado", "PLS", 88, 2024, "Reforma do sistema unico para gestantes.", "Saúde"),
    ]
    conn.executemany(
        "INSERT INTO proposicoes (id, casa, sigla, numero, ano, ementa, tema_oficial) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        proposicoes,
    )
    return conn


def test_proposicoes_relevantes_via_keyword() -> None:
    aborto = carregar_topico(TOPICOS_DIR / "aborto.yaml")
    conn = _conn_seed()
    try:
        df = proposicoes_relevantes(aborto, conn)
        ids = set(df["id"].to_list())
        assert 1 in ids  # 'aborto legal'
        assert 4 in ids  # 'estatuto do nascituro' bate keyword + categoria
        # Lei de transporte (3) NÃO entra
        assert 3 not in ids
    finally:
        conn.close()


def test_proposicoes_relevantes_via_categoria_oficial() -> None:
    aborto = carregar_topico(TOPICOS_DIR / "aborto.yaml")
    conn = _conn_seed()
    try:
        df = proposicoes_relevantes(aborto, conn)
        ids = set(df["id"].to_list())
        # PLS 88/2024: ementa não tem keyword direta de aborto, mas
        # categoria 'Saúde' está nas categorias_oficiais_camara/senado.
        assert 7 in ids
    finally:
        conn.close()


def test_exclusoes_filtram_falsos_positivos() -> None:
    aborto = carregar_topico(TOPICOS_DIR / "aborto.yaml")
    conn = _conn_seed()
    try:
        df = proposicoes_relevantes(aborto, conn)
        ids = set(df["id"].to_list())
        # 5 = 'aborto espontâneo' -> excluído
        assert 5 not in ids
        # 6 = 'aborto da emenda' -> excluído pelo regex metafórico
        assert 6 not in ids
    finally:
        conn.close()


def test_agregar_voto_em_db_v1_aplica_m002_automaticamente() -> None:
    """DB v1 antigo (sem ``proposicao_id``) é auto-migrado e retorna agg vazia.

    Substitui o legado ``test_agregar_voto_sem_proposicao_id_retorna_vazio`` --
    pós-S27.1 a função :func:`agregar_voto_por_parlamentar` chama
    :func:`aplicar_migrations` antes do JOIN, garantindo compat retroativa.
    Em DB v1 cru com tabela ``votacoes`` vazia, a agregação é vazia (não
    porque a coluna falta, mas porque não há votos).
    """
    aborto = carregar_topico(TOPICOS_DIR / "aborto.yaml")
    # Cria DB v1 *sem* M002, simulando schema antigo da S26.
    conn = duckdb.connect(":memory:")
    try:
        from hemiciclo.etl.schema import criar_schema_v1

        criar_schema_v1(conn)
        # Marca v1 manualmente para forçar caminho de upgrade.
        conn.execute("INSERT INTO _migrations (versao, descricao) VALUES (1, 'manual v1')")
        # Confirma que `proposicao_id` ainda não existe.
        cols_pre = {
            linha[0]
            for linha in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='votacoes'"
            ).fetchall()
        }
        assert "proposicao_id" not in cols_pre

        # Insere proposições (sem votos -- foco no auto-upgrade do schema).
        conn.executemany(
            "INSERT INTO proposicoes (id, casa, sigla, numero, ano, ementa, tema_oficial) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(1, "camara", "PL", 1904, 2024, "Dispoe sobre aborto legal.", "Saúde")],
        )
        props = proposicoes_relevantes(aborto, conn)
        df_agg = agregar_voto_por_parlamentar(props, conn)

        # Pós-chamada: M002 foi aplicada automaticamente.
        cols_pos = {
            linha[0]
            for linha in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='votacoes'"
            ).fetchall()
        }
        assert "proposicao_id" in cols_pos
        assert len(df_agg) == 0  # sem votos populados
        assert "parlamentar_id" in df_agg.columns
    finally:
        conn.close()


def test_agregar_voto_com_proposicao_id_funciona() -> None:
    """Com proposicao_id populado, JOIN agrega corretamente por parlamentar."""
    aborto = carregar_topico(TOPICOS_DIR / "aborto.yaml")
    conn = _conn_seed()
    try:
        # M002 já criou a coluna -- só inserimos dados.
        # 3 votações ligadas à proposição 1 (aborto legal):
        conn.execute(
            "INSERT INTO votacoes (id, casa, descricao, proposicao_id) VALUES "
            "('v1', 'camara', 'votacao 1', 1), "
            "('v2', 'camara', 'votacao 2', 1), "
            "('v3', 'camara', 'votacao 3', 1)"
        )
        # 2 parlamentares: 100 (vota SIM nas 3) e 200 (vota NAO nas 3)
        conn.executemany(
            "INSERT INTO votos (votacao_id, parlamentar_id, casa, voto) VALUES (?, ?, ?, ?)",
            [
                ("v1", 100, "camara", "SIM"),
                ("v2", 100, "camara", "SIM"),
                ("v3", 100, "camara", "SIM"),
                ("v1", 200, "camara", "NAO"),
                ("v2", 200, "camara", "NAO"),
                ("v3", 200, "camara", "NAO"),
            ],
        )
        props = proposicoes_relevantes(aborto, conn)
        df_agg = agregar_voto_por_parlamentar(props, conn)
        assert len(df_agg) == 2
        registros = {row["parlamentar_id"]: row for row in df_agg.iter_rows(named=True)}
        assert registros[100]["proporcao_sim"] == 1.0
        assert registros[100]["posicao_agregada"] == "A_FAVOR"
        assert registros[200]["proporcao_sim"] == 0.0
        assert registros[200]["posicao_agregada"] == "CONTRA"
    finally:
        conn.close()


def test_agregar_voto_sem_proposicoes_relevantes() -> None:
    """Se props_relevantes vazio, agregação retorna vazia sem tocar DB."""
    conn = _conn_seed()
    try:
        df_agg = agregar_voto_por_parlamentar(pl.DataFrame(), conn)
        assert len(df_agg) == 0
    finally:
        conn.close()


def test_posicao_agregada_a_favor_contra_neutro() -> None:
    assert _categorizar(0.85) == PosicaoAgregada.A_FAVOR
    assert _categorizar(0.70) == PosicaoAgregada.A_FAVOR
    assert _categorizar(0.69) == PosicaoAgregada.NEUTRO
    assert _categorizar(0.50) == PosicaoAgregada.NEUTRO
    assert _categorizar(0.31) == PosicaoAgregada.NEUTRO
    assert _categorizar(0.30) == PosicaoAgregada.CONTRA
    assert _categorizar(0.10) == PosicaoAgregada.CONTRA


def test_keyword_com_apostrofe_nao_quebra(tmp_path: Path) -> None:
    """Smoke: SQL escapa aspas simples corretamente para keywords ricas."""
    yaml_apostrofo = tmp_path / "ap.yaml"
    yaml_apostrofo.write_text(
        "nome: ap\n"
        "versao: 1\n"
        'descricao_curta: "Topico para teste de aspas simples no SQL."\n'
        "keywords:\n"
        '  - "d\'agua"\n'
        "regex:\n"
        '  - "(?i)d\'agua"\n',
        encoding="utf-8",
    )
    topico = carregar_topico(yaml_apostrofo, schema_path=TOPICOS_DIR / "_schema.yaml")
    conn = _conn_seed()
    try:
        df = proposicoes_relevantes(topico, conn)
        # Não pode levantar -- esse era o bug a evitar.
        assert isinstance(df, pl.DataFrame)
    finally:
        conn.close()


def test_agregar_voto_com_subset_filtra_join() -> None:
    """S30.2: ``parlamentares_subset`` restringe a agregação ao recorte.

    Cenário: 3 parlamentares votam em proposições relevantes; subset
    contém apenas 2 deles. A agregação deve devolver apenas linhas dos
    parlamentares listados no subset, não dos demais.
    """
    aborto = carregar_topico(TOPICOS_DIR / "aborto.yaml")
    conn = _conn_seed()
    try:
        conn.execute(
            "INSERT INTO votacoes (id, casa, descricao, proposicao_id) VALUES "
            "('v1', 'camara', 'votacao 1', 1), "
            "('v2', 'camara', 'votacao 2', 1)"
        )
        conn.executemany(
            "INSERT INTO votos (votacao_id, parlamentar_id, casa, voto) VALUES (?, ?, ?, ?)",
            [
                ("v1", 100, "camara", "SIM"),
                ("v2", 100, "camara", "SIM"),
                ("v1", 200, "camara", "NAO"),
                ("v2", 200, "camara", "NAO"),
                ("v1", 300, "camara", "SIM"),
                ("v2", 300, "camara", "NAO"),
            ],
        )
        props = proposicoes_relevantes(aborto, conn)
        subset = {(100, "camara"), (200, "camara")}
        df_agg = agregar_voto_por_parlamentar(props, conn, parlamentares_subset=subset)
        ids = set(df_agg["parlamentar_id"].to_list())
        assert ids == {100, 200}
        assert 300 not in ids
    finally:
        conn.close()


def test_agregar_voto_com_subset_vazio_retorna_schema_vazio() -> None:
    """S30.2: subset explicitamente vazio = curto-circuito imediato.

    Recorte ``set()`` significa "filtro casou ninguém"; a função deve
    devolver o schema vazio canônico sem tocar nas tabelas temp.
    """
    aborto = carregar_topico(TOPICOS_DIR / "aborto.yaml")
    conn = _conn_seed()
    try:
        props = proposicoes_relevantes(aborto, conn)
        df_agg = agregar_voto_por_parlamentar(props, conn, parlamentares_subset=set())
        assert len(df_agg) == 0
        # Schema canônico preservado mesmo no curto-circuito.
        assert "parlamentar_id" in df_agg.columns
        assert "casa" in df_agg.columns
        assert "n_votos" in df_agg.columns
        assert "proporcao_sim" in df_agg.columns
        assert "posicao_agregada" in df_agg.columns
    finally:
        conn.close()
