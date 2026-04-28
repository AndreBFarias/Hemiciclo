"""Timeline interativa de conversão por parlamentar (S33).

Substitui o stub da S31. Renderiza um Plotly line chart com:

- Eixo X: bucket temporal (ano ou número de legislatura).
- Eixo Y: ``proporcao_sim`` em [0, 1] (formatado como % no tooltip).
- Cor do marcador: depende da posição dominante no bucket
  (verde-folha = a_favor, vermelho-argila = contra, cinza-pedra = neutro).
- Anotações com ``delta_pp`` em cada mudança detectada (>= 30pp default).

Esta é a entrega visual do eixo ``volatilidade`` da assinatura
multidimensional (D4 / ADR-004), alimentada pelos modelos em
:mod:`hemiciclo.modelos.historico`.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from hemiciclo.dashboard import tema

# Mapa de posição -> cor da paleta institucional (mantém coerência visual
# com top a-favor/contra e radar).
_COR_POR_POSICAO: dict[str, str] = {
    "a_favor": tema.VERDE_FOLHA,
    "contra": tema.VERMELHO_ARGILA,
    "neutro": tema.CINZA_PEDRA,
}


def _cor_posicao(posicao: str) -> str:
    """Resolve cor da paleta institucional para uma posição rotulada.

    Default seguro: cinza-pedra (mesma cor do ``neutro``).
    """
    return _COR_POR_POSICAO.get(posicao, tema.CINZA_PEDRA)


def renderizar_timeline_conversao(
    historico_dict: dict[str, Any] | None,
    parlamentar_id: int | str,
    titulo: str | None = None,
) -> None:
    """Renderiza a timeline de conversão de um parlamentar.

    Args:
        historico_dict: Dict carregado de ``historico_conversao.json``
            (estrutura ``{"parlamentares": {...}, "metadata": {...}}``).
            Pode ser ``None`` quando o arquivo ainda não foi gerado.
        parlamentar_id: Id do parlamentar a renderizar (chave em
            ``historico_dict["parlamentares"]``).
        titulo: Título customizado. Default: ``"Histórico de conversão
            #<id>"``.

    Comportamento:

    - ``historico_dict`` ``None`` ou sem chave ``parlamentares`` -> ``st.info``
      neutro.
    - Parlamentar não encontrado -> ``st.info``.
    - Histórico com < 2 buckets -> ``st.info`` explicando dados
      insuficientes (skip graceful).
    - Caso contrário, ``st.plotly_chart`` com line + markers.
    """
    if not historico_dict or "parlamentares" not in historico_dict:
        st.info("Histórico de conversão ainda não foi calculado para esta sessão.")
        return

    parlamentares = historico_dict.get("parlamentares") or {}
    chave = str(parlamentar_id)
    bloco = parlamentares.get(chave)
    if not isinstance(bloco, dict):
        st.info(f"Sem histórico disponível para o parlamentar #{parlamentar_id}.")
        return

    historico = bloco.get("historico") or []
    if not isinstance(historico, list) or len(historico) < 2:  # noqa: PLR2004
        st.info(
            f"Parlamentar #{parlamentar_id} tem dados insuficientes (menos de 2 buckets temporais)."
        )
        return

    nome = str(bloco.get("nome", parlamentar_id))
    mudancas = bloco.get("mudancas_detectadas") or []
    volatilidade = float(bloco.get("indice_volatilidade", 0.0) or 0.0)

    titulo_final = titulo or f"Histórico de conversão -- {nome}"
    _desenhar_chart(historico, mudancas, titulo_final, volatilidade)


def _desenhar_chart(
    historico: list[dict[str, Any]],
    mudancas: list[dict[str, Any]],
    titulo: str,
    volatilidade: float,
) -> None:
    """Desenha figura Plotly com line + markers + anotações de mudança."""
    import plotly.graph_objects as go  # noqa: PLC0415 -- lazy

    buckets: list[float] = [float(p.get("bucket", 0)) for p in historico]
    prop_sim: list[float] = [float(p.get("proporcao_sim", 0.0) or 0.0) for p in historico]
    posicoes: list[str] = [str(p.get("posicao", "neutro")) for p in historico]
    n_votos: list[int] = [int(p.get("n_votos", 0) or 0) for p in historico]
    cores_markers = [_cor_posicao(p) for p in posicoes]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=buckets,
            y=prop_sim,
            mode="lines+markers",
            line={"color": tema.AZUL_HEMICICLO, "width": 2.0},
            marker={
                "color": cores_markers,
                "size": 12,
                "line": {"color": tema.AZUL_HEMICICLO, "width": 1.0},
            },
            name="proporcao_sim",
            customdata=list(zip(posicoes, n_votos, strict=True)),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "%{y:.0%} SIM<br>"
                "%{customdata[1]} votos<br>"
                "posição: %{customdata[0]}"
                "<extra></extra>"
            ),
        )
    )

    # Anotações de mudança detectada -- seta apontando para o bucket posterior.
    for evento in mudancas:
        try:
            x_post = float(evento["bucket_posterior"])
            y_post = float(evento["proporcao_sim_posterior"])
            delta = float(evento["delta_pp"])
        except (KeyError, TypeError, ValueError):
            continue
        sinal = "+" if delta >= 0 else ""
        fig.add_annotation(
            x=x_post,
            y=y_post,
            text=f"{sinal}{delta:.0f}pp",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1.5,
            arrowcolor=tema.AMARELO_OURO,
            ax=0,
            ay=-40,
            bgcolor=tema.BRANCO_OSSO,
            bordercolor=tema.AMARELO_OURO,
            borderwidth=1,
            font={"size": 11, "color": tema.CINZA_PEDRA},
        )

    fig.update_layout(
        title=titulo,
        paper_bgcolor=tema.BRANCO_OSSO,
        plot_bgcolor=tema.BRANCO_OSSO,
        xaxis={
            "title": "Período (ano ou legislatura)",
            "showgrid": True,
            "gridcolor": tema.CINZA_AREIA,
            "tickmode": "array",
            "tickvals": buckets,
        },
        yaxis={
            "title": "% SIM",
            "range": [0.0, 1.0],
            "tickformat": ".0%",
            "showgrid": True,
            "gridcolor": tema.CINZA_AREIA,
        },
        height=380,
        margin={"l": 60, "r": 40, "t": 70, "b": 50},
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"Índice de volatilidade: **{volatilidade:.2f}** (0 = consistente, "
        f"1 = errático). {len(mudancas)} mudança(s) detectada(s)."
    )
