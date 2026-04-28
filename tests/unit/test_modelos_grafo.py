"""Testes unit do módulo ``hemiciclo.modelos.grafo`` (S32).

Cobre as três classes públicas (GrafoCoautoria, GrafoVoto, MetricasGrafo)
em isolamento, usando DuckDB em memória populado por fixtures locais.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb
import networkx as nx
import pytest

from hemiciclo.etl.migrations import aplicar_migrations
from hemiciclo.modelos.grafo import (
    MIN_NOS_GRAFO,
    AmostraInsuficiente,
    GrafoCoautoria,
    GrafoVoto,
    MetricasGrafo,
)

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _criar_db_com_votos(
    n_parlamentares: int = 8, n_votacoes: int = 10
) -> duckdb.DuckDBPyConnection:
    """Cria DB em memória com votos plausíveis pra exercitar grafos.

    Constrói matriz determinística onde:
    - Metade dos parlamentares vota SIM, metade vota NAO (a maioria das vezes)
    - Cada parlamentar participa de todas as ``n_votacoes``

    Isso garante grafos com arestas suficientes para passar dos cortes
    mínimos.
    """
    conn = duckdb.connect(":memory:")
    aplicar_migrations(conn)

    # parlamentares
    for pid in range(1, n_parlamentares + 1):
        partido = "PT" if pid <= n_parlamentares // 2 else "PL"
        conn.execute(
            "INSERT INTO parlamentares (id, casa, nome, partido, uf, ativo) "
            "VALUES (?, 'camara', ?, ?, 'SP', TRUE)",
            [pid, f"Parlamentar {pid}", partido],
        )

    # votacoes
    for vid in range(1, n_votacoes + 1):
        conn.execute(
            "INSERT INTO votacoes (id, casa, data, descricao, resultado) "
            "VALUES (?, 'camara', '2024-01-01', ?, 'aprovado')",
            [f"v{vid}", f"Votacao {vid}"],
        )

    # votos: cada parlamentar participa de todas as votacoes
    for vid in range(1, n_votacoes + 1):
        for pid in range(1, n_parlamentares + 1):
            voto = "Sim" if pid <= n_parlamentares // 2 else "Nao"
            conn.execute(
                "INSERT INTO votos (votacao_id, parlamentar_id, casa, voto, data) "
                "VALUES (?, ?, 'camara', ?, '2024-01-01')",
                [f"v{vid}", pid, voto],
            )

    return conn


def _criar_db_vazio() -> duckdb.DuckDBPyConnection:
    """Cria DB com schema mas sem dados de votos."""
    conn = duckdb.connect(":memory:")
    aplicar_migrations(conn)
    return conn


# ---------------------------------------------------------------------------
# GrafoCoautoria
# ---------------------------------------------------------------------------


def test_grafo_coautoria_constroi() -> None:
    """Com 8 parlamentares votando juntos em 10 votações, grafo tem 8 nós."""
    conn = _criar_db_com_votos(n_parlamentares=8, n_votacoes=10)
    try:
        g = GrafoCoautoria.construir(conn)
        assert isinstance(g, nx.Graph)
        assert len(g.nodes()) == 8
        # Todos votaram em 10 votacoes -> peso minimo (5) garantido
        assert len(g.edges()) > 0
        # Atributos enriquecidos
        primeiro = next(iter(g.nodes()))
        assert "nome" in g.nodes[primeiro]
        assert "partido" in g.nodes[primeiro]
    finally:
        conn.close()


def test_grafo_coautoria_dados_vazios() -> None:
    """Sem dados de voto, GrafoCoautoria levanta AmostraInsuficiente."""
    conn = _criar_db_vazio()
    try:
        with pytest.raises(AmostraInsuficiente):
            GrafoCoautoria.construir(conn)
    finally:
        conn.close()


def test_grafo_coautoria_amostra_insuficiente_levanta() -> None:
    """Com apenas 3 parlamentares (< MIN_NOS_GRAFO=5), levanta."""
    conn = _criar_db_com_votos(n_parlamentares=3, n_votacoes=10)
    try:
        with pytest.raises(AmostraInsuficiente, match="3 nós"):
            GrafoCoautoria.construir(conn)
    finally:
        conn.close()


def test_grafo_coautoria_tabela_ausente_levanta() -> None:
    """Sem tabela ``votos`` levanta AmostraInsuficiente com mensagem clara."""
    conn = duckdb.connect(":memory:")
    try:
        with pytest.raises(AmostraInsuficiente, match="tabela votos ausente"):
            GrafoCoautoria.construir(conn)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# GrafoVoto
# ---------------------------------------------------------------------------


def test_grafo_voto_constroi() -> None:
    """GrafoVoto produz arestas com peso = afinidade [0, 1]."""
    conn = _criar_db_com_votos(n_parlamentares=8, n_votacoes=10)
    try:
        g = GrafoVoto.construir(conn)
        assert isinstance(g, nx.Graph)
        assert len(g.nodes()) >= MIN_NOS_GRAFO
        # Todos os pesos no intervalo unitario
        for _, _, atributos in g.edges(data=True):
            assert 0.0 <= atributos["weight"] <= 1.0
    finally:
        conn.close()


def test_grafo_voto_calcula_coincidencia() -> None:
    """Parlamentares do mesmo partido (mesmo voto sempre) -> afinidade 1.0."""
    conn = _criar_db_com_votos(n_parlamentares=8, n_votacoes=10)
    try:
        g = GrafoVoto.construir(conn)
        # Pares (1,2), (1,3), (1,4) sao todos PT votando Sim sempre -> 1.0
        if g.has_edge(1, 2):
            assert g[1][2]["weight"] == pytest.approx(1.0)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# MetricasGrafo
# ---------------------------------------------------------------------------


def test_centralidade_grau() -> None:
    """Centralidade retorna dict com valores em [0, 1]."""
    g = nx.path_graph(5)
    cent = MetricasGrafo.calcular_centralidade(g)
    assert len(cent) == 5
    for valor in cent.values():
        assert 0.0 <= valor <= 1.0
    # Vazio
    assert MetricasGrafo.calcular_centralidade(nx.Graph()) == {}


def test_comunidades_louvain() -> None:
    """Detecta comunidades em grafo simples (Louvain ou fallback).

    Em grafo de duas cliques disjuntas conectadas por uma única aresta,
    Louvain deve identificar pelo menos 2 comunidades.
    """
    g = nx.Graph()
    # clique A
    g.add_edges_from([(1, 2), (2, 3), (1, 3)])
    # clique B
    g.add_edges_from([(4, 5), (5, 6), (4, 6)])
    # ponte
    g.add_edge(3, 4)

    com = MetricasGrafo.detectar_comunidades(g)
    assert len(com) == 6
    # Pelo menos 2 comunidades distintas
    assert len(set(com.values())) >= 2


def test_comunidades_grafo_vazio() -> None:
    """Grafo vazio retorna mapa vazio."""
    assert MetricasGrafo.detectar_comunidades(nx.Graph()) == {}


def test_tamanho_maior_componente() -> None:
    """Maior componente conta os nós da maior CC."""
    g = nx.Graph()
    g.add_edges_from([(1, 2), (2, 3)])  # CC com 3 nos
    g.add_edges_from([(4, 5)])  # CC com 2 nos
    g.add_node(99)  # isolado: CC com 1 no
    assert MetricasGrafo.tamanho_maior_componente(g) == 3
    # Vazio
    assert MetricasGrafo.tamanho_maior_componente(nx.Graph()) == 0


def test_aplicar_atributos_anota_in_place() -> None:
    """``aplicar_atributos`` adiciona ``centralidade`` e ``comunidade`` em cada nó."""
    g = nx.path_graph(5)
    MetricasGrafo.aplicar_atributos(g)
    for node in g.nodes():
        assert "centralidade" in g.nodes[node]
        assert "comunidade" in g.nodes[node]


def test_top_centrais_retorna_top_n() -> None:
    """``top_centrais`` retorna até N itens ordenados desc."""
    g = nx.star_graph(6)  # hub no centro, 6 satélites
    g.nodes[0]["nome"] = "Hub"
    top = MetricasGrafo.top_centrais(g, top_n=3)
    assert len(top) == 3
    # Ordem desc por centralidade
    assert top[0]["centralidade"] >= top[1]["centralidade"]
    assert top[0]["id"] == 0  # hub é o mais central


def test_grafo_voto_tabela_ausente_levanta() -> None:
    """Sem tabela ``votos`` GrafoVoto levanta AmostraInsuficiente."""
    conn = duckdb.connect(":memory:")
    try:
        with pytest.raises(AmostraInsuficiente, match="tabela votos ausente"):
            GrafoVoto.construir(conn)
    finally:
        conn.close()


def test_grafo_voto_amostra_insuficiente_levanta() -> None:
    """Com 3 parlamentares, GrafoVoto também levanta."""
    conn = _criar_db_com_votos(n_parlamentares=3, n_votacoes=10)
    try:
        with pytest.raises(AmostraInsuficiente):
            GrafoVoto.construir(conn)
    finally:
        conn.close()


def test_comunidades_fallback_quando_community_ausente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ImportError em ``community`` cai no fallback greedy modularity."""
    import builtins

    real_import = builtins.__import__

    def _fake_import(nome: str, *args: object, **kwargs: object) -> object:
        if nome == "community":
            raise ImportError("simulando ausencia de python-louvain")
        return real_import(nome, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    g = nx.Graph()
    g.add_edges_from([(1, 2), (2, 3), (4, 5), (5, 6), (3, 4)])
    com = MetricasGrafo.detectar_comunidades(g)
    # Fallback funciona e retorna mapa não-vazio
    assert len(com) == 6
    assert len(set(com.values())) >= 1


def test_tamanho_maior_componente_grafo_so_isolados() -> None:
    """Grafo só com nós isolados (sem arestas) -> componentes = 1 cada."""
    g = nx.Graph()
    g.add_nodes_from([1, 2, 3])
    # Cada nó é uma componente de tamanho 1
    assert MetricasGrafo.tamanho_maior_componente(g) == 1


def test_filtrar_top_reduz_grafo() -> None:
    """``filtrar_top`` corta o grafo para max_nos nós."""
    g = nx.complete_graph(20)
    pequeno = MetricasGrafo.filtrar_top(g, max_nos=10)
    assert len(pequeno.nodes()) == 10
    # Quando já está abaixo do limite, retorna original
    pequeno2 = MetricasGrafo.filtrar_top(g, max_nos=50)
    assert len(pequeno2.nodes()) == 20
