"""Progress bar + lista de etapas para sessões em andamento (S31).

Recebe ``StatusSessao`` e renderiza:

- Barra de progresso global (0-100%)
- Etapa atual em destaque
- Lista vertical das etapas concluídas/atual/pendentes (mockup §10.3 do
  plano R2 -- Tela 4)
- ETA opcional em segundos

Compatível com o polling 2s do ``sessao_detalhe.py`` via ``st.empty()`` +
``placeholder.container()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

from hemiciclo.dashboard import tema
from hemiciclo.sessao.modelo import EstadoSessao

if TYPE_CHECKING:
    from hemiciclo.sessao.modelo import StatusSessao


# Ordem canônica das etapas que o pipeline percorre. Vem das transições
# do ``pipeline_real`` da S30: COLETANDO -> ETL -> EMBEDDINGS -> MODELANDO
# -> CONCLUIDA. Estados terminais ERRO/INTERROMPIDA/PAUSADA não fazem
# parte da sequência linear.
ETAPAS_CANONICAS: tuple[tuple[EstadoSessao, str], ...] = (
    (EstadoSessao.CRIADA, "Criando sessão"),
    (EstadoSessao.COLETANDO, "Coletando dados oficiais"),
    (EstadoSessao.ETL, "Consolidando em DuckDB"),
    (EstadoSessao.EMBEDDINGS, "Projetando em modelo base"),
    (EstadoSessao.MODELANDO, "Gerando relatório"),
    (EstadoSessao.CONCLUIDA, "Concluída"),
)


def _formatar_eta(eta_segundos: int | None) -> str:
    """Formata ETA em texto humano. ``None`` retorna ``"--"``."""
    if eta_segundos is None or eta_segundos <= 0:
        return "--"
    if eta_segundos < 60:
        return f"~{eta_segundos}s"
    minutos = eta_segundos // 60
    if minutos < 60:
        return f"~{minutos}min"
    horas = minutos // 60
    return f"~{horas}h{minutos % 60:02d}min"


def renderizar_progresso(
    status: StatusSessao,
    etapa_atual: str,
    mensagem: str,
    eta_segundos: int | None = None,
) -> None:
    """Renderiza progresso da sessão: barra + etapa atual + lista de etapas.

    Args:
        status: ``StatusSessao`` carregado do disco.
        etapa_atual: Texto curto da etapa atual (vem de ``status.etapa_atual``).
        mensagem: Mensagem auxiliar exibida abaixo da barra.
        eta_segundos: Tempo estimado restante. ``None`` exibe ``--``.
    """
    pct = max(0.0, min(100.0, status.progresso_pct)) / 100.0
    st.progress(pct, text=f"{status.progresso_pct:.0f}% -- {etapa_atual}")
    if mensagem:
        st.caption(mensagem)

    estado_atual = status.estado
    indice_atual = next(
        (i for i, (e, _) in enumerate(ETAPAS_CANONICAS) if e == estado_atual),
        0,
    )

    linhas: list[str] = []
    for i, (estado_etapa, rotulo) in enumerate(ETAPAS_CANONICAS):
        if i < indice_atual:
            simbolo = "[OK]"
            cor = tema.VERDE_FOLHA
        elif i == indice_atual:
            simbolo = "[em andamento]"
            cor = tema.AMARELO_OURO
        else:
            simbolo = "[pendente]"
            cor = tema.CINZA_PEDRA
        linhas.append(
            f'<li style="color:{cor}; margin:0.25rem 0;">'
            f"<strong>{simbolo}</strong> {rotulo} ({estado_etapa.value})"
            f"</li>"
        )
    eta_txt = _formatar_eta(eta_segundos)
    st.markdown(
        f'<ul style="list-style:none; padding-left:0;">{"".join(linhas)}</ul>'
        f'<div style="font-size:0.85rem; color:{tema.CINZA_PEDRA}; opacity:0.75;">'
        f"Tempo estimado restante: <strong>{eta_txt}</strong></div>",
        unsafe_allow_html=True,
    )
