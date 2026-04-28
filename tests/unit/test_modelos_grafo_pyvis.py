"""Testes unit do wrapper pyvis (S32)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx
import pytest

from hemiciclo.modelos.grafo_pyvis import PALETA_COMUNIDADES, renderizar_pyvis

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def grafo_pequeno() -> nx.Graph:
    """Grafo de 6 nós com 2 cliques conectados (gera ao menos 2 comunidades)."""
    g = nx.Graph()
    g.add_edges_from([(1, 2), (2, 3), (1, 3)])  # clique A
    g.add_edges_from([(4, 5), (5, 6), (4, 6)])  # clique B
    g.add_edge(3, 4)
    for node in g.nodes():
        g.nodes[node]["nome"] = f"Parlamentar {node}"
        g.nodes[node]["partido"] = "PT" if node <= 3 else "PL"
        g.nodes[node]["uf"] = "SP"
    return g


def test_renderizar_pyvis_gera_html(tmp_path: Path, grafo_pequeno: nx.Graph) -> None:
    """``renderizar_pyvis`` cria arquivo HTML não-vazio."""
    destino = tmp_path / "grafo.html"
    saida = renderizar_pyvis(grafo_pequeno, destino, titulo="Coautoria")
    assert saida == destino
    assert destino.is_file()
    assert destino.stat().st_size > 1000  # pyvis gera ao menos alguns KB


def test_html_contem_nodes(tmp_path: Path, grafo_pequeno: nx.Graph) -> None:
    """O HTML gerado contém os labels dos parlamentares."""
    destino = tmp_path / "grafo.html"
    renderizar_pyvis(grafo_pequeno, destino)
    conteudo = destino.read_text(encoding="utf-8")
    assert "Parlamentar 1" in conteudo
    assert "Parlamentar 6" in conteudo


def test_html_contem_paleta_institucional(tmp_path: Path, grafo_pequeno: nx.Graph) -> None:
    """O HTML usa ao menos uma cor da paleta institucional."""
    destino = tmp_path / "grafo.html"
    renderizar_pyvis(grafo_pequeno, destino)
    conteudo = destino.read_text(encoding="utf-8")
    # Pelo menos uma das cores da paleta aparece nas opções da rede
    assert any(cor.lower() in conteudo.lower() for cor in PALETA_COMUNIDADES)


def test_grafo_vazio_gera_html_placeholder(tmp_path: Path) -> None:
    """Grafo vazio gera placeholder HTML válido (sem levantar)."""
    destino = tmp_path / "vazio.html"
    saida = renderizar_pyvis(nx.Graph(), destino, titulo="Voto")
    assert saida.is_file()
    conteudo = destino.read_text(encoding="utf-8")
    assert "<html" in conteudo.lower()
    assert "Voto" in conteudo
    assert "amostra insuficiente" in conteudo.lower()
