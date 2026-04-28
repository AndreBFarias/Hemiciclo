"""Heatmap parlamentar x tópico com cor = ``proporcao_sim`` (S31).

Stub funcional: na S31 a sessão tem só um tópico (recorte da pesquisa).
O heatmap renderiza esse tópico único como uma faixa colorida cobrindo os
parlamentares ranqueados, com escala divergente (verde a-favor, vermelho
contra). Em sprints futuras (S33/S38) ganha múltiplos tópicos cruzados.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import streamlit as st

from hemiciclo.dashboard import tema

if TYPE_CHECKING:
    pass


def renderizar_heatmap(
    parlamentares: list[dict[str, Any]],
    topico: str = "tópico atual",
    top_n: int = 50,
    titulo: str = "Heatmap parlamentar × tópico",
) -> None:
    """Renderiza heatmap Plotly do recorte da sessão.

    Args:
        parlamentares: Lista de dicts com ``nome`` e ``proporcao_sim``.
        topico: Nome do tópico (eixo X único na S31).
        top_n: Limite de linhas plotadas.
        titulo: Título do gráfico.
    """
    if not parlamentares:
        st.info(f"Sem dados para o heatmap: {titulo}")
        return

    selecionados = parlamentares[:top_n]
    nomes = [str(p.get("nome", p.get("id", "?"))) for p in selecionados]
    valores = [[float(p.get("proporcao_sim", 0.0) or 0.0)] for p in selecionados]

    import plotly.graph_objects as go  # noqa: PLC0415 -- lazy

    fig = go.Figure(
        data=go.Heatmap(
            z=valores,
            x=[topico],
            y=nomes,
            colorscale=[
                (0.0, tema.VERMELHO_ARGILA),
                (0.5, tema.CINZA_AREIA),
                (1.0, tema.VERDE_FOLHA),
            ],
            zmin=0.0,
            zmax=1.0,
            colorbar={"title": "% sim"},
            hovertemplate="%{y}: %{z:.0%}<extra></extra>",
        )
    )
    fig.update_layout(
        title=titulo,
        paper_bgcolor=tema.BRANCO_OSSO,
        plot_bgcolor=tema.BRANCO_OSSO,
        height=max(320, 18 * len(selecionados)),
        margin={"l": 160, "r": 40, "t": 60, "b": 40},
        yaxis={"autorange": "reversed"},
    )
    st.plotly_chart(fig, use_container_width=True)
