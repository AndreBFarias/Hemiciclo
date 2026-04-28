"""Renderização pyvis dos grafos (S32) -- HTML standalone interativo.

Wrapper fino sobre :class:`pyvis.network.Network` que aplica a paleta
institucional do Hemiciclo (tema.py) e garante determinismo via
``random_state`` no layout. Cada nó recebe:

- ``label``: nome do parlamentar (ou id como fallback)
- ``title``: tooltip com partido / UF
- ``color``: cor da comunidade (Louvain) -- ciclo na paleta institucional
- ``size``: 10 + 30 * centralidade

Para grafos grandes (acima de :data:`hemiciclo.modelos.grafo.LIMITE_NOS_PYVIS`),
o caller deve usar :meth:`MetricasGrafo.filtrar_top` antes.

Skip graceful: grafo vazio gera HTML placeholder (não levanta).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from hemiciclo.dashboard.tema import (
    AMARELO_OURO,
    AZUL_HEMICICLO,
    BRANCO_OSSO,
    VERDE_FOLHA,
    VERMELHO_ARGILA,
)
from hemiciclo.modelos.grafo import MetricasGrafo

if TYPE_CHECKING:
    from pathlib import Path

    import networkx as nx


# ---------------------------------------------------------------------------
# Paleta cíclica para comunidades
# ---------------------------------------------------------------------------

PALETA_COMUNIDADES: tuple[str, ...] = (
    AZUL_HEMICICLO,
    AMARELO_OURO,
    VERDE_FOLHA,
    VERMELHO_ARGILA,
    "#8B5A3C",  # marrom terra
    "#4A7BAB",  # azul claro
)


def renderizar_pyvis(
    grafo: nx.Graph,
    html_path: Path,
    titulo: str = "",
) -> Path:
    """Renderiza ``grafo`` como HTML interativo em ``html_path``.

    Args:
        grafo: Grafo networkx (já com atributos ``nome``, ``partido``, ``uf``
            preferencialmente). Pode estar vazio.
        html_path: Destino do HTML. A pasta deve existir.
        titulo: Heading opcional renderizado acima do canvas.

    Returns:
        O ``html_path`` recebido (para encadeamento).
    """
    from pyvis.network import Network  # noqa: PLC0415 -- lazy

    # Aplica atributos in-place (centralidade + comunidade) caso ausentes
    if grafo.nodes() and "centralidade" not in next(iter(grafo.nodes(data=True)))[1]:
        MetricasGrafo.aplicar_atributos(grafo)

    rede = Network(
        height="600px",
        width="100%",
        bgcolor=BRANCO_OSSO,
        font_color=AZUL_HEMICICLO,
        notebook=False,
        cdn_resources="in_line",  # HTML standalone, sem CDN externa
        heading=titulo,
    )
    # Layout determinístico
    rede.barnes_hut(
        gravity=-2000,
        central_gravity=0.1,
        spring_length=120,
        spring_strength=0.05,
        damping=0.4,
    )

    if not grafo.nodes():
        # Placeholder: HTML válido com aviso
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(
            _html_placeholder(titulo or "Grafo"),
            encoding="utf-8",
        )
        logger.warning("[grafo_pyvis] grafo vazio; placeholder em {p}", p=html_path)
        return html_path

    for node in grafo.nodes():
        atrs = grafo.nodes[node]
        comunidade = int(atrs.get("comunidade", 0))
        cor = PALETA_COMUNIDADES[comunidade % len(PALETA_COMUNIDADES)]
        nome = str(atrs.get("nome", str(node)))
        partido = str(atrs.get("partido", ""))
        uf = str(atrs.get("uf", ""))
        rotulo_titulo = f"{nome} ({partido}/{uf})" if partido or uf else nome
        rede.add_node(
            int(node),
            label=nome,
            title=rotulo_titulo,
            color=cor,
            size=10 + 30 * float(atrs.get("centralidade", 0.0)),
        )

    for u, v, dados in grafo.edges(data=True):
        peso = float(dados.get("weight", 1.0))
        rede.add_edge(int(u), int(v), value=peso)

    html_path.parent.mkdir(parents=True, exist_ok=True)
    # pyvis.save_graph() abre arquivo com encoding default do sistema (cp1252 no
    # Windows), causando UnicodeEncodeError no template HTML que tem chars
    # unicode. Workaround: gerar HTML como string e escrever com utf-8 explícito.
    html = rede.generate_html(notebook=False)
    html_path.write_text(html, encoding="utf-8")
    logger.info("[grafo_pyvis] HTML gerado em {p}", p=html_path)
    return html_path


def _html_placeholder(titulo: str) -> str:
    """Gera HTML mínimo coerente com a paleta para grafos vazios."""
    return (
        "<!doctype html>\n"
        "<html lang='pt-BR'>\n"
        "<head><meta charset='utf-8'>\n"
        f"<title>{titulo}</title>\n"
        f"<style>body{{background:{BRANCO_OSSO};color:{AZUL_HEMICICLO};"
        "font-family:Inter,system-ui,sans-serif;padding:2rem;text-align:center;}}"
        "</style></head>\n"
        f"<body><h2>{titulo}</h2>\n"
        "<p>Amostra insuficiente para gerar o grafo (menos de 5 nós com "
        "vínculos suficientes). Aumente o recorte temporal ou o número "
        "de votações para ver a rede.</p>\n"
        "</body></html>\n"
    )
