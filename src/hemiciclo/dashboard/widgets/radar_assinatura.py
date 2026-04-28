"""Radar polar com a assinatura multidimensional do parlamentar (S31).

Plotly ``Scatterpolar`` com até 7 eixos (D4 do plano R2):

- ``posicao`` -- ``proporcao_sim`` (já em [0, 1])
- ``intensidade`` -- frequência relativa de discursos no tópico
- ``hipocrisia`` -- ``None`` até S33 (gap discurso x voto)
- ``volatilidade`` -- ``None`` até S33 (mudança ao longo do tempo)
- ``centralidade`` -- ``None`` até S32 (grau no grafo de coautoria)
- ``convertibilidade`` -- ``None`` até S34 (probabilidade de conversão)
- ``enquadramento`` -- ``None`` até S34b (LLM opcional)

Eixos com ``None`` viram zero no traço polar e são marcados com indicador
``(em breve)`` no rótulo. Limite default ``top_n=20`` para performance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import streamlit as st

from hemiciclo.dashboard import tema

if TYPE_CHECKING:
    pass

EIXOS_DEFAULT: tuple[str, ...] = tema.EIXOS_ASSINATURA

# Eixos ainda não disponíveis recebem rótulo "(em breve)". Eixos disponíveis
# (posicao e intensidade na S31) ficam sem sufixo.
EIXOS_PENDENTES: frozenset[str] = frozenset(
    {
        "hipocrisia",
        "volatilidade",
        "centralidade",
        "convertibilidade",
        "enquadramento",
    }
)


def _rotulo_eixo(eixo: str) -> str:
    """Retorna rótulo do eixo. Se ainda não disponível, anota '(em breve)'."""
    if eixo in EIXOS_PENDENTES:
        return f"{eixo} (em breve)"
    return eixo


def _valor_eixo(parlamentar: dict[str, Any], eixo: str) -> float:
    """Extrai valor numérico do eixo. Trata ``None`` como zero."""
    valor = parlamentar.get(eixo)
    if valor is None:
        return 0.0
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def renderizar_radar(
    parlamentares: list[dict[str, Any]],
    eixos: list[str] | None = None,
    top_n: int = 20,
    titulo: str = "Assinatura multidimensional",
) -> None:
    """Renderiza radar polar Plotly com até ``top_n`` parlamentares.

    Args:
        parlamentares: Lista de dicts com chaves ``id``, ``nome`` e os
            valores de cada eixo. Eixos ausentes/``None`` viram zero.
        eixos: Lista de eixos a desenhar. Default = 7 eixos do D4.
        top_n: Limite de parlamentares plotados (performance Plotly).
        titulo: Título exibido acima do radar.
    """
    if not parlamentares:
        st.info(f"Sem dados para {titulo}")
        return

    eixos_finais = list(eixos) if eixos else list(EIXOS_DEFAULT)
    selecionados = parlamentares[:top_n]

    import plotly.graph_objects as go  # noqa: PLC0415 -- lazy

    fig = go.Figure()
    rotulos_eixos = [_rotulo_eixo(e) for e in eixos_finais]
    # Fecha o polígono repetindo o primeiro rótulo no fim.
    rotulos_fechados = [*rotulos_eixos, rotulos_eixos[0]]

    for i, parl in enumerate(selecionados):
        valores = [_valor_eixo(parl, e) for e in eixos_finais]
        valores_fechados = [*valores, valores[0]]
        nome = str(parl.get("nome", parl.get("id", f"#{i + 1}")))
        partido = str(parl.get("partido", "")).strip()
        rotulo = f"{nome} ({partido})" if partido else nome
        fig.add_trace(
            go.Scatterpolar(
                r=valores_fechados,
                theta=rotulos_fechados,
                fill="toself",
                name=rotulo,
                line={"width": 1.4},
                opacity=0.55,
            )
        )

    fig.update_layout(
        title=titulo,
        polar={
            "radialaxis": {
                "visible": True,
                "range": [0.0, 1.0],
                "tickformat": ".0%",
            },
            "bgcolor": tema.BRANCO_OSSO,
        },
        paper_bgcolor=tema.BRANCO_OSSO,
        showlegend=True,
        legend={"font": {"size": 10}},
        height=520,
        margin={"l": 40, "r": 40, "t": 60, "b": 40},
    )
    st.plotly_chart(fig, use_container_width=True)
