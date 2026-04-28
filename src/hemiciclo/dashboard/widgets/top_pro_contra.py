"""Tabelas de Top a-favor / Top contra do tópico da sessão (S31).

Renderiza duas colunas Streamlit, cada uma com uma tabela ranqueada de
parlamentares. As linhas trazem ranking, nome, partido, UF e ``Score``
em escala percentual ``[0, 100]`` (``proporcao_sim * 100``). A escala
``[0, 100]`` é exigida pelo ``st.column_config.ProgressColumn`` quando
combinado com ``format="%.0f%%"`` -- caso contrário o ``printf`` renderiza
``0.99`` como ``"1%"`` (S38.7). Click em nome abre detalhes em sprint
futura (S33 -- página parlamentar individual). Aqui usamos apenas
``st.dataframe`` para evitar dependência prematura de roteamento por
parlamentar.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from hemiciclo.dashboard import tema


def _normalizar_linha(rank: int, parl: dict[str, Any]) -> dict[str, Any]:
    """Extrai colunas canônicas para exibição em tabela.

    ``Score`` é escalado para ``[0, 100]`` (``proporcao_sim * 100``) para
    que o ``ProgressColumn`` com ``format="%.0f%%"`` formate corretamente
    (S38.7).
    """
    proporcao = float(parl.get("proporcao_sim", parl.get("score", 0.0)) or 0.0)
    return {
        "#": rank,
        "Nome": str(parl.get("nome", parl.get("id", "?"))),
        "Partido": str(parl.get("partido", "")),
        "UF": str(parl.get("uf", "")),
        "Score": proporcao * 100.0,
    }


def _renderizar_tabela(
    titulo: str,
    cor_borda: str,
    parlamentares: list[dict[str, Any]],
    top_n: int,
) -> None:
    """Renderiza um cabeçalho colorido + tabela de top_n linhas."""
    st.markdown(
        f'<div style="border-left:4px solid {cor_borda}; padding-left:0.75rem; '
        f'margin-bottom:0.5rem;">'
        f'<h4 style="margin:0; color:{tema.AZUL_HEMICICLO};">{titulo}</h4>'
        f"</div>",
        unsafe_allow_html=True,
    )
    if not parlamentares:
        st.info(f"Sem dados para {titulo}")
        return
    selecionados = parlamentares[:top_n]
    linhas = [_normalizar_linha(i + 1, p) for i, p in enumerate(selecionados)]
    st.dataframe(
        linhas,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.ProgressColumn(
                "Score",
                help="Proporção de votos sim no tópico (0-100%).",
                min_value=0.0,
                max_value=100.0,
                format="%.0f%%",
            ),
        },
    )


def renderizar_top(
    top_a_favor: list[dict[str, Any]],
    top_contra: list[dict[str, Any]],
    top_n: int = 100,
) -> None:
    """Renderiza duas colunas com Top a-favor (esq) e Top contra (dir).

    Args:
        top_a_favor: Lista ranqueada do mais a favor para o menos.
        top_contra: Lista ranqueada do mais contra para o menos.
        top_n: Limite de linhas em cada tabela.
    """
    col_esq, col_dir = st.columns(2)
    with col_esq:
        _renderizar_tabela("Top a-favor", tema.VERDE_FOLHA, top_a_favor, top_n)
    with col_dir:
        _renderizar_tabela("Top contra", tema.VERMELHO_ARGILA, top_contra, top_n)
