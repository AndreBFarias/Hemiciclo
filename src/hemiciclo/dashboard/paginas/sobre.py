"""Página 'Sobre' do Hemiciclo (S23).

Renderiza o manifesto curto vindo de ``docs/manifesto.md``, lista as
tecnologias do projeto, link de repositório e licença GPLv3.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import streamlit as st

from hemiciclo import __version__
from hemiciclo.dashboard import componentes

if TYPE_CHECKING:
    from hemiciclo.config import Configuracao


_REPO_RAIZ = Path(__file__).resolve().parents[4]
_MANIFESTO_PATH = _REPO_RAIZ / "docs" / "manifesto.md"


def _carregar_manifesto() -> str:
    """Carrega manifesto curto de docs/manifesto.md (com fallback)."""
    if _MANIFESTO_PATH.is_file():
        return _MANIFESTO_PATH.read_text(encoding="utf-8")
    return (
        "## Manifesto\n\n"
        "O Hemiciclo é uma ferramenta cidadã de inteligência política aberta.\n\n"
        "_Documento completo será adicionado em docs/manifesto.md._"
    )


def render(cfg: Configuracao) -> None:  # noqa: ARG001
    """Renderiza a página 'Sobre' com manifesto, stack e licença."""
    st.markdown("## Sobre o Hemiciclo")
    componentes.storytelling("sobre")

    st.markdown(
        f"""<div class="hemiciclo-manifesto">{_carregar_manifesto()}</div>""",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("### Stack técnico")
    st.markdown(
        """
        - **Python 3.11+** com tipagem estrita (mypy --strict).
        - **Streamlit** para a interface cidadã.
        - **DuckDB + Polars** para análise local de alto desempenho.
        - **Pydantic v2** para todos os modelos de dados.
        - **scikit-learn**, **BERTopic** e **bge-m3** para classificação semântica.
        - **NetworkX + Pyvis** para grafos de coautoria.
        - **uv** para gerenciamento determinístico de dependências.
        """
    )

    st.markdown("### Licença e código-fonte")
    st.markdown(
        f"""
        - Versão: **{__version__}**
        - Licença: **GPL v3** -- livre para usar, modificar e redistribuir.
        - Repositório: [github.com/AndreBFarias/Hemiciclo](https://github.com/AndreBFarias/Hemiciclo)
        - Plano técnico: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md`
        - Decisões arquiteturais: `docs/adr/`
        """
    )
