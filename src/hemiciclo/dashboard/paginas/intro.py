"""Página de introdução narrativa do Hemiciclo (S23).

Exibida na primeira execução. Manifesto curto + CTA grande.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

from hemiciclo.dashboard import componentes, tema

if TYPE_CHECKING:
    from hemiciclo.config import Configuracao


def render(cfg: Configuracao) -> None:  # noqa: ARG001 -- assinatura padrão das páginas
    """Renderiza a página inicial (intro narrativo)."""
    st.markdown(
        f"""
        <h1 style="color:{tema.AZUL_HEMICICLO}; font-weight:800;
                   letter-spacing:-1px; margin-bottom:0.5rem;">
            Bem-vindo ao Hemiciclo
        </h1>
        """,
        unsafe_allow_html=True,
    )
    componentes.storytelling("intro")

    st.markdown(
        """
        Quem vota a favor do quê. Quem mudou de lado. Quem fala uma coisa
        e vota outra. Quem é central na rede de coautoria. Quem responde
        a tópicos morais que dividem o país.

        O Hemiciclo coleta esses dados das APIs oficiais da Câmara e do
        Senado, processa tudo na sua máquina e devolve perfis multidimensionais
        auditáveis -- sem servidor central, sem rastreio, sem custo.
        """,
    )

    col_a, col_b, _ = st.columns([2, 1, 2])
    with col_a:
        if st.button(
            "Fazer minha primeira pesquisa",
            key="intro_cta_pesquisa",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["pagina_ativa"] = "nova_pesquisa"
            st.rerun()
    with col_b:
        if st.button(
            "Ler manifesto",
            key="intro_cta_manifesto",
            use_container_width=True,
        ):
            st.session_state["pagina_ativa"] = "sobre"
            st.rerun()
