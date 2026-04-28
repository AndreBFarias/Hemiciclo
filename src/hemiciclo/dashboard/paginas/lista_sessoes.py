"""Página de lista de sessões persistidas (S23).

Em S23 a página apenas lê metadados de ``~/hemiciclo/sessoes/<id>/params.json``
e ``status.json``. Pipeline real (que de fato preenche essas pastas) chega
em S30; até lá a maioria dos usuários verá apenas o CTA de lista vazia ou
rascunhos criados pelo form de Nova Pesquisa.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import streamlit as st
from loguru import logger

from hemiciclo.dashboard import componentes

if TYPE_CHECKING:
    from pathlib import Path

    from hemiciclo.config import Configuracao


def _ler_metadados_sessao(pasta: Path) -> dict[str, Any] | None:
    """Lê params.json e status.json de uma pasta de sessão.

    Tolerante a ausência de status.json (rascunhos da S23 ainda não
    têm pipeline rodando). Retorna ``None`` se nem params.json existe.
    """
    params_path = pasta / "params.json"
    if not params_path.is_file():
        return None

    meta: dict[str, Any] = {"id": pasta.name}
    try:
        params_data = json.loads(params_path.read_text(encoding="utf-8"))
        meta.update(
            {
                "topico": params_data.get("topico", pasta.name),
                "casas": params_data.get("casas") or [],
                "ufs": params_data.get("ufs") or [],
            }
        )
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("params.json inválido em {pasta}: {erro}", pasta=pasta, erro=exc)
        return None

    status_path = pasta / "status.json"
    if status_path.is_file():
        try:
            status_data = json.loads(status_path.read_text(encoding="utf-8"))
            meta.update(
                {
                    "estado": status_data.get("estado", "criada"),
                    "progresso_pct": status_data.get("progresso_pct", 0.0),
                    "iniciada_em": status_data.get("iniciada_em", ""),
                }
            )
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("status.json inválido em {pasta}: {erro}", pasta=pasta, erro=exc)
            meta["estado"] = "criada"
    else:
        # Rascunho da S23 ou sessão recém-criada -- ainda sem status.
        meta["estado"] = "criada"
        meta["progresso_pct"] = 0.0
        meta["iniciada_em"] = "(rascunho)"

    return meta


def _coletar_sessoes(cfg: Configuracao) -> list[dict[str, Any]]:
    """Lista sessões existentes, ordenadas por nome (proxy de criação)."""
    if not cfg.sessoes_dir.exists():
        return []

    pastas = sorted(
        (p for p in cfg.sessoes_dir.iterdir() if p.is_dir()),
        reverse=True,
    )
    sessoes: list[dict[str, Any]] = []
    for pasta in pastas:
        meta = _ler_metadados_sessao(pasta)
        if meta is not None:
            sessoes.append(meta)
    return sessoes


def render(cfg: Configuracao) -> None:
    """Renderiza a página de lista de sessões."""
    st.markdown("## Pesquisas")
    componentes.storytelling("lista_sessoes")

    col_topo_a, _, col_topo_b = st.columns([1, 4, 1])
    with col_topo_b:
        if st.button(
            "+ Nova pesquisa",
            key="lista_cta_nova",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["pagina_ativa"] = "nova_pesquisa"
            st.rerun()

    sessoes = _coletar_sessoes(cfg)
    if not sessoes:
        componentes.cta_primeira_pesquisa()
        return

    for sessao in sessoes:
        componentes.card_sessao(sessao)
        sessao_id = str(sessao.get("id", "")).strip()
        if not sessao_id:
            continue
        if st.button(
            "Abrir relatório",
            key=f"abrir_sessao_{sessao_id}",
            use_container_width=False,
        ):
            st.session_state["sessao_id"] = sessao_id
            st.session_state["pagina_ativa"] = "sessao_detalhe"
            st.rerun()
