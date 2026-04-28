"""Entry-point do dashboard Streamlit do Hemiciclo (S23).

Estrutura:

- ``set_page_config`` com layout wide + sidebar collapsed.
- CSS de ``style.css`` injetado em runtime.
- 4 páginas (intro, lista_sessoes, nova_pesquisa, sobre) selecionadas via
  ``st.session_state["pagina_ativa"]``.
- ``Configuracao().garantir_diretorios()`` chamado na carga.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import streamlit as st

from hemiciclo import __version__
from hemiciclo.config import Configuracao
from hemiciclo.dashboard import componentes
from hemiciclo.dashboard.paginas import (
    importar,
    intro,
    lista_sessoes,
    nova_pesquisa,
    sessao_detalhe,
    sobre,
)

# Páginas exibidas na navegação principal (4 abas top).
PAGINAS: dict[str, tuple[str, Callable[[Configuracao], None]]] = {
    "intro": ("Início", intro.render),
    "lista_sessoes": ("Pesquisas", lista_sessoes.render),
    "nova_pesquisa": ("Nova pesquisa", nova_pesquisa.render),
    "sobre": ("Sobre", sobre.render),
}

# Páginas internas alcançadas via ``session_state["pagina_ativa"]`` mas
# que NÃO aparecem na navegação principal (rotas filhas).
PAGINAS_INTERNAS: dict[str, tuple[str, Callable[[Configuracao], None]]] = {
    "sessao_detalhe": ("Detalhe da pesquisa", sessao_detalhe.render),
    "importar": ("Importar sessão", importar.render),
}


def _carregar_css() -> None:
    css_path = Path(__file__).parent / "style.css"
    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


@st.cache_resource
def _carregar_fontes_inline() -> str:
    """Inline base64 dos TTFs locais (Inter + JetBrains Mono).

    Zero rede em runtime (I1 do BRIEF -- tudo local). Cache de recurso
    Streamlit garante que o overhead de leitura+base64 só acontece uma vez
    por sessão.
    """
    import base64

    fontes_dir = Path(__file__).parent / "static" / "fonts"
    if not fontes_dir.exists():
        return "<style>/* fontes não encontradas em static/fonts/ */</style>"

    mapa = {
        "Inter": [("Regular", 400), ("Medium", 500), ("SemiBold", 600), ("Bold", 700)],
        "JetBrainsMono": [("Regular", 400), ("Bold", 700)],
    }

    declaracoes = []
    for familia, pesos in mapa.items():
        for nome, peso in pesos:
            ttf_path = fontes_dir / f"{familia}-{nome}.ttf"
            if not ttf_path.exists():
                continue
            ttf_b64 = base64.b64encode(ttf_path.read_bytes()).decode("ascii")
            family_css = "Inter" if familia == "Inter" else "JetBrains Mono"
            declaracoes.append(
                f"@font-face {{ "
                f"font-family: '{family_css}'; "
                f"src: url('data:font/ttf;base64,{ttf_b64}') format('truetype'); "
                f"font-weight: {peso}; "
                f"font-style: normal; "
                f"font-display: swap; "
                f"}}"
            )
    return "<style>" + "\n".join(declaracoes) + "</style>"


def _coletar_stats(cfg: Configuracao) -> dict[str, str | int]:
    """Coleta as estatísticas exibidas no rodapé global."""
    sessoes = (
        sorted(p for p in cfg.sessoes_dir.iterdir() if p.is_dir())
        if cfg.sessoes_dir.exists()
        else []
    )
    modelo_base_path = cfg.modelos_dir / "base_v1.pkl"
    modelo_base = "base_v1" if modelo_base_path.exists() else "nenhum"
    return {
        "versao": __version__,
        "n_sessoes": len(sessoes),
        "modelo_base": modelo_base,
    }


def main() -> None:
    """Função principal -- ponto de entrada do Streamlit."""
    st.set_page_config(
        page_title="Hemiciclo -- inteligência política aberta",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(_carregar_fontes_inline(), unsafe_allow_html=True)
    _carregar_css()

    cfg = Configuracao()
    cfg.garantir_diretorios()

    if "pagina_ativa" not in st.session_state:
        st.session_state["pagina_ativa"] = "intro"

    componentes.header_global(__version__)

    paginas_para_navegacao: dict[str, tuple[str, Callable[[Any], None]]] = {
        chave: (rotulo, render) for chave, (rotulo, render) in PAGINAS.items()
    }
    pagina_ativa = componentes.navegacao_principal(paginas_para_navegacao)

    # Resolve a página: páginas top primeiro; depois rotas internas.
    if pagina_ativa in PAGINAS:
        _rotulo, render_fn = PAGINAS[pagina_ativa]
    elif pagina_ativa in PAGINAS_INTERNAS:
        _rotulo, render_fn = PAGINAS_INTERNAS[pagina_ativa]
    else:
        # Rota desconhecida: cai pra intro como fallback seguro.
        st.session_state["pagina_ativa"] = "intro"
        _rotulo, render_fn = PAGINAS["intro"]
    render_fn(cfg)

    componentes.footer_global(_coletar_stats(cfg))


# Streamlit chama o módulo no nível do top-level. Não usamos
# ``if __name__ == "__main__"`` aqui porque o Streamlit injeta o módulo
# no contexto de execução próprio dele.
main()
