"""Página "Importar sessão" do dashboard (S35).

Aceita upload de zip exportado por :func:`hemiciclo.sessao.exportador.exportar_zip`,
valida integridade via ``manifesto.json`` e extrai pra ``~/hemiciclo/sessoes/<id>/``.
Em caso de colisão de id, sufixa ``_2``, ``_3`` etc automaticamente.

Página interna -- alcançada via ``st.session_state["pagina_ativa"] = "importar"``.
"""

from __future__ import annotations

import contextlib
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import streamlit as st
from loguru import logger

from hemiciclo.dashboard import componentes
from hemiciclo.sessao import IntegridadeImportadaInvalida, importar_zip

if TYPE_CHECKING:
    from hemiciclo.config import Configuracao


def render(cfg: Configuracao) -> None:
    """Renderiza a página de importação de sessão."""
    componentes.storytelling("importar")

    st.markdown("## Importar sessão de pesquisa")
    st.markdown(
        "Cole um zip exportado por outro pesquisador. O Hemiciclo verifica "
        "a integridade dos artefatos contra o `manifesto.json` antes de "
        "abrir a sessão no seu dashboard."
    )

    arquivo = st.file_uploader(
        "Arquivo .zip da sessão",
        type=["zip"],
        accept_multiple_files=False,
        key="importar_uploader",
        help="Zip gerado por `hemiciclo sessao exportar` ou pelo botão Exportar zip.",
    )
    sem_validar = st.checkbox(
        "Pular validação de integridade",
        key="importar_sem_validar",
        help="Útil para sessões antigas (anteriores ao manifesto.json) ou debug.",
    )

    if arquivo is None:
        return

    col_a, col_b = st.columns([1, 5])
    with col_a:
        botao_clicado = st.button("Importar", key="importar_botao", type="primary")
    with col_b:
        st.caption(f"Arquivo selecionado: `{arquivo.name}`")

    if not botao_clicado:
        return

    # Streamlit entrega o upload em memória; serializa em tempfile pra
    # passar como Path para a função de importação.
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(arquivo.getbuffer())
        zip_path = Path(tmp.name)

    try:
        id_final = importar_zip(zip_path, cfg.home, validar=not sem_validar)
    except zipfile.BadZipFile as exc:
        st.error(f"Arquivo zip inválido: {exc}")
        logger.warning("upload zip invalido: {e}", e=exc)
        return
    except IntegridadeImportadaInvalida as exc:
        st.error(
            "Falha na verificação de integridade. Algum artefato do zip foi "
            "alterado em relação ao manifesto original. Detalhe técnico: "
            f"`{exc}`."
        )
        return
    except OSError as exc:
        st.error(f"Erro ao gravar a sessão importada: {exc}")
        return
    finally:
        with contextlib.suppress(OSError):
            zip_path.unlink(missing_ok=True)

    estado_validacao = "pulada" if sem_validar else "OK"
    st.success(
        f"Sessão importada com sucesso. ID final: `{id_final}` (validação: {estado_validacao})."
    )
    st.markdown("Use o botão abaixo para abrir o relatório completo.")
    if st.button("Abrir relatório", key="importar_abrir_relatorio"):
        st.session_state["sessao_id"] = id_final
        st.session_state["pagina_ativa"] = "sessao_detalhe"
        st.rerun()
