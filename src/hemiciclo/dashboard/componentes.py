"""Componentes reutilizáveis do dashboard Hemiciclo (S23).

Funções pequenas que renderizam pedaços de UI via Streamlit. Toda formatação
visual delega para CSS injetado em ``style.css``; lógica de cor delega para
``tema.py``. Sem chamadas de rede; sem leitura de disco fora do necessário.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import streamlit as st

from hemiciclo.dashboard import tema

if TYPE_CHECKING:
    from collections.abc import Callable


def header_global(versao: str) -> None:
    """Renderiza o header fixo do dashboard (logo textual + versão)."""
    st.markdown(
        f"""
        <div class="hemiciclo-header">
            <div>
                <span class="hemiciclo-titulo">Hemiciclo</span>
                <span class="hemiciclo-tagline">
                    inteligência política aberta, soberana, local
                </span>
            </div>
            <div class="hemiciclo-versao">v{versao}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def navegacao_principal(
    paginas: dict[str, tuple[str, Callable[[Any], None]]],
) -> str:
    """Renderiza a navegação principal e retorna a aba ativa.

    Lê e atualiza ``st.session_state["pagina_ativa"]``. Cada aba é um botão
    Streamlit cujo clique grava o id da aba no session_state e força rerun.
    """
    if "pagina_ativa" not in st.session_state:
        st.session_state["pagina_ativa"] = "intro"

    cols = st.columns(len(paginas))
    for col, (chave, (rotulo, _render)) in zip(cols, paginas.items(), strict=True):
        with col:
            ativa = st.session_state["pagina_ativa"] == chave
            cor = tema.COR_POR_ABA.get(chave, tema.AZUL_HEMICICLO)
            opacidade = "1" if ativa else "0.78"
            borda = f"3px solid {tema.AMARELO_OURO}" if ativa else "3px solid transparent"
            st.markdown(
                f"""
                <style>
                div[data-testid="stHorizontalBlock"]
                    > div:nth-child({list(paginas).index(chave) + 1})
                    > div > .stButton > button {{
                    background-color: {cor};
                    color: white;
                    opacity: {opacidade};
                    border-bottom: {borda};
                }}
                </style>
                """,
                unsafe_allow_html=True,
            )
            if st.button(rotulo, key=f"nav_{chave}", use_container_width=True):
                st.session_state["pagina_ativa"] = chave
                st.rerun()

    pagina_ativa = st.session_state["pagina_ativa"]
    return str(pagina_ativa)


def storytelling(chave_aba: str) -> None:
    """Renderiza o parágrafo de storytelling da aba indicada."""
    texto = tema.STORYTELLING.get(chave_aba, "")
    if texto:
        st.markdown(
            f'<p class="hemiciclo-storytelling">{texto}</p>',
            unsafe_allow_html=True,
        )


def card_sessao(sessao_meta: dict[str, Any]) -> None:
    """Renderiza um card de sessão na lista.

    ``sessao_meta`` espera as chaves: ``topico``, ``casas``, ``ufs``,
    ``estado``, ``progresso_pct``, ``iniciada_em``.
    """
    topico = str(sessao_meta.get("topico", "(sem tópico)"))
    casas_iter = sessao_meta.get("casas") or []
    casas_str = ", ".join(str(c) for c in casas_iter)
    ufs_iter = sessao_meta.get("ufs") or []
    ufs_str = ", ".join(str(u) for u in ufs_iter) if ufs_iter else "todas"
    estado = str(sessao_meta.get("estado", "criada")).lower()
    progresso = float(sessao_meta.get("progresso_pct", 0.0))
    iniciada = str(sessao_meta.get("iniciada_em", ""))

    badge_html = f'<span class="hemiciclo-badge hemiciclo-badge-{estado}">{estado}</span>'

    progresso_html = ""
    if estado not in {"concluida", "criada", "erro"}:
        progresso_html = (
            f'<div style="margin-top:0.4rem; font-size:0.82rem; '
            f'color:#4A4A4A; opacity:0.7;">progresso: {progresso:.0f}%</div>'
        )

    st.markdown(
        f"""
        <div class="hemiciclo-card-sessao">
            <div class="hemiciclo-card-titulo">{topico}</div>
            <div class="hemiciclo-card-meta">
                {casas_str} &middot; UFs: {ufs_str} &middot; iniciada em {iniciada}
            </div>
            {badge_html}
            {progresso_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def cta_primeira_pesquisa() -> None:
    """Renderiza o call-to-action exibido quando a lista de sessões está vazia."""
    st.markdown(
        """
        <div class="hemiciclo-cta-vazio">
            <div class="hemiciclo-cta-titulo">
                Você ainda não fez nenhuma pesquisa
            </div>
            <div class="hemiciclo-cta-subtitulo">
                Cada pesquisa é uma análise autocontida que fica salva
                localmente, com seus dados, modelos e relatório.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button(
        "Começar minha primeira pesquisa",
        key="cta_nova_pesquisa",
        type="primary",
        use_container_width=False,
    ):
        st.session_state["pagina_ativa"] = "nova_pesquisa"
        st.rerun()


def footer_global(stats: dict[str, str | int]) -> None:
    """Renderiza o footer global com versão, contagem de sessões e modelo base."""
    versao = stats.get("versao", "?")
    n_sessoes = stats.get("n_sessoes", 0)
    modelo = stats.get("modelo_base", "nenhum")

    st.markdown(
        f"""
        <div class="hemiciclo-footer">
            <div>Hemiciclo v{versao} &middot; GPL v3 &middot; tudo local</div>
            <div>
                {n_sessoes} sessão(ões) &middot; modelo base: {modelo}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
