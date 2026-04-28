"""Widget Streamlit para embedar HTML pyvis na página da sessão (S32).

Usa ``st.components.v1.html`` que recebe a string HTML diretamente, não
um path. Isso significa que precisamos ler o arquivo gerado pelo pipeline
e injetar o conteúdo no iframe interno do Streamlit.

Tolerante a arquivo ausente: mostra aviso amigável em vez de quebrar a
página inteira.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st
from loguru import logger

if TYPE_CHECKING:
    from pathlib import Path


def renderizar_rede(html_path: Path, altura: int = 600) -> None:
    """Renderiza o HTML pyvis salvo em ``html_path`` dentro do Streamlit.

    Args:
        html_path: Caminho do HTML gerado por
            :func:`hemiciclo.modelos.grafo_pyvis.renderizar_pyvis`.
        altura: Altura em pixels do iframe interno (default 600).

    Comportamento:
    - Arquivo presente -> ``st.components.v1.html(conteudo, height=altura)``
    - Arquivo ausente -> ``st.info`` com mensagem clara
    - Falha de leitura -> ``st.warning``
    """
    if not html_path.is_file():
        st.info("Os grafos de articulação política aparecerão aqui assim que a análise terminar.")
        return
    try:
        conteudo = html_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("renderizar_rede: leitura falhou em {p}: {e}", p=html_path, e=exc)
        st.warning(f"Não foi possível ler o grafo em `{html_path.name}`: {exc}")
        return
    st.components.v1.html(conteudo, height=altura, scrolling=False)
