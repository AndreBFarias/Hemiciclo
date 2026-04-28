"""Testes unit dos widgets do dashboard (S31).

Cada widget é testado isoladamente -- não dependemos de AppTest do
Streamlit aqui (mais lento). Mockamos chamadas Streamlit pra inspecionar
o que foi renderizado e garantir que o widget não quebra nas bordas
(lista vazia, top_n respeitado, etc).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pytest_mock import MockerFixture

from hemiciclo.dashboard.widgets import (
    heatmap_hipocrisia,
    progresso_sessao,
    radar_assinatura,
    timeline_conversao,
    top_pro_contra,
    word_cloud,
)
from hemiciclo.sessao.modelo import EstadoSessao, StatusSessao

# ---------------------------------------------------------------------------
# word_cloud
# ---------------------------------------------------------------------------


def test_word_cloud_renderiza_sem_erro(mocker: MockerFixture) -> None:
    """Word cloud com lista de textos não-vazia chama ``st.image`` exatamente uma vez."""
    mock_image = mocker.patch.object(word_cloud.st, "image")
    mock_info = mocker.patch.object(word_cloud.st, "info")

    word_cloud.renderizar_word_cloud(
        textos=["aborto direito mulher saúde", "vida desde concepção família"],
        titulo="Teste",
    )

    assert mock_image.call_count == 1
    assert mock_info.call_count == 0


def test_word_cloud_lista_vazia_nao_quebra(mocker: MockerFixture) -> None:
    """Lista vazia exibe ``st.info`` e não chama ``st.image``."""
    mock_image = mocker.patch.object(word_cloud.st, "image")
    mock_info = mocker.patch.object(word_cloud.st, "info")

    word_cloud.renderizar_word_cloud(textos=[], titulo="Vazio")

    assert mock_image.call_count == 0
    assert mock_info.call_count == 1


def test_word_cloud_strings_em_branco_nao_quebra(mocker: MockerFixture) -> None:
    """Strings só com espaço em branco caem no caminho de lista vazia."""
    mock_image = mocker.patch.object(word_cloud.st, "image")
    mock_info = mocker.patch.object(word_cloud.st, "info")

    word_cloud.renderizar_word_cloud(textos=["   ", " ", ""], titulo="brancos")

    assert mock_image.call_count == 0
    assert mock_info.call_count == 1


# ---------------------------------------------------------------------------
# radar_assinatura
# ---------------------------------------------------------------------------


def test_radar_4_parlamentares_4_eixos(mocker: MockerFixture) -> None:
    """Radar com 4 parlamentares e eixos default chama ``plotly_chart`` uma vez."""
    mock_plot = mocker.patch.object(radar_assinatura.st, "plotly_chart")
    parlamentares = [
        {"id": i, "nome": f"P{i}", "partido": "X", "posicao": 0.8, "intensidade": 0.5}
        for i in range(4)
    ]
    radar_assinatura.renderizar_radar(parlamentares, top_n=20)
    assert mock_plot.call_count == 1


def test_radar_lista_vazia_emite_info(mocker: MockerFixture) -> None:
    """Lista vazia: usa ``st.info``, não tenta plotar."""
    mock_plot = mocker.patch.object(radar_assinatura.st, "plotly_chart")
    mock_info = mocker.patch.object(radar_assinatura.st, "info")
    radar_assinatura.renderizar_radar([], top_n=20)
    assert mock_plot.call_count == 0
    assert mock_info.call_count == 1


def test_radar_top_n_limita_traços(mocker: MockerFixture) -> None:
    """Com 50 parlamentares e top_n=5, plotly recebe Figure com 5 traços."""
    mock_plot = mocker.patch.object(radar_assinatura.st, "plotly_chart")
    parlamentares = [
        {"id": i, "nome": f"P{i}", "posicao": 0.5, "intensidade": 0.5} for i in range(50)
    ]
    radar_assinatura.renderizar_radar(parlamentares, top_n=5)
    assert mock_plot.call_count == 1
    fig = mock_plot.call_args[0][0]
    assert len(fig.data) == 5


# ---------------------------------------------------------------------------
# heatmap_hipocrisia
# ---------------------------------------------------------------------------


def test_heatmap_dados_vazios(mocker: MockerFixture) -> None:
    """Heatmap com lista vazia não chama ``plotly_chart``."""
    mock_plot = mocker.patch.object(heatmap_hipocrisia.st, "plotly_chart")
    mock_info = mocker.patch.object(heatmap_hipocrisia.st, "info")
    heatmap_hipocrisia.renderizar_heatmap([], topico="x")
    assert mock_plot.call_count == 0
    assert mock_info.call_count == 1


def test_heatmap_renderiza_com_dados(mocker: MockerFixture) -> None:
    """Heatmap com 3 parlamentares chama ``plotly_chart`` uma vez."""
    mock_plot = mocker.patch.object(heatmap_hipocrisia.st, "plotly_chart")
    parlamentares = [{"id": i, "nome": f"P{i}", "proporcao_sim": 0.5} for i in range(3)]
    heatmap_hipocrisia.renderizar_heatmap(parlamentares, topico="aborto")
    assert mock_plot.call_count == 1


# ---------------------------------------------------------------------------
# timeline_conversao (S33 -- real, testes detalhados em
# tests/unit/test_dashboard_timeline_conversao.py)
# ---------------------------------------------------------------------------


def test_timeline_sem_historico_emite_info(mocker: MockerFixture) -> None:
    """Sem histórico calculado, widget cai em ``st.info`` neutro."""
    mock_info = mocker.patch.object(timeline_conversao.st, "info")
    mock_plot = mocker.patch.object(timeline_conversao.st, "plotly_chart")
    timeline_conversao.renderizar_timeline_conversao(None, parlamentar_id=42)
    assert mock_info.call_count == 1
    assert mock_plot.call_count == 0


# ---------------------------------------------------------------------------
# progresso_sessao
# ---------------------------------------------------------------------------


def _status_em_etapa(estado: EstadoSessao, pct: float = 50.0) -> StatusSessao:
    agora = datetime.now(UTC)
    return StatusSessao(
        id="teste",
        estado=estado,
        progresso_pct=pct,
        etapa_atual="etapa_teste",
        mensagem="msg",
        iniciada_em=agora,
        atualizada_em=agora,
    )


def test_progresso_renderiza_etapas(mocker: MockerFixture) -> None:
    """Renderiza barra, caption e markdown da lista de etapas."""
    mock_progress = mocker.patch.object(progresso_sessao.st, "progress")
    mock_caption = mocker.patch.object(progresso_sessao.st, "caption")
    mock_md = mocker.patch.object(progresso_sessao.st, "markdown")

    progresso_sessao.renderizar_progresso(
        _status_em_etapa(EstadoSessao.ETL, pct=50.0),
        etapa_atual="ETL",
        mensagem="mensagem",
        eta_segundos=120,
    )

    assert mock_progress.call_count == 1
    assert mock_caption.call_count == 1
    assert mock_md.call_count == 1
    md_html = mock_md.call_args[0][0]
    assert "etl" in md_html.lower()
    assert "~2min" in md_html


def test_progresso_eta_none_retorna_placeholder(mocker: MockerFixture) -> None:
    """Sem ETA, mostra ``--`` no rodapé."""
    mock_md = mocker.patch.object(progresso_sessao.st, "markdown")
    mocker.patch.object(progresso_sessao.st, "progress")
    mocker.patch.object(progresso_sessao.st, "caption")

    progresso_sessao.renderizar_progresso(
        _status_em_etapa(EstadoSessao.COLETANDO, pct=10.0),
        etapa_atual="coleta",
        mensagem="msg",
        eta_segundos=None,
    )

    md_html = mock_md.call_args[0][0]
    assert "--" in md_html


# ---------------------------------------------------------------------------
# top_pro_contra
# ---------------------------------------------------------------------------


def _parlamentares(n: int, score_base: float = 0.9) -> list[dict[str, Any]]:
    return [
        {
            "id": 100 + i,
            "nome": f"P{i}",
            "partido": "X",
            "uf": "SP",
            "proporcao_sim": score_base - 0.01 * i,
        }
        for i in range(n)
    ]


def test_top_pro_contra_renderiza_2_colunas(mocker: MockerFixture) -> None:
    """Top a-favor + top contra renderiza 2 colunas + 2 dataframes."""
    cols = (mocker.MagicMock(), mocker.MagicMock())
    cols[0].__enter__ = lambda *_a, **_k: cols[0]
    cols[0].__exit__ = lambda *_a, **_k: None
    cols[1].__enter__ = lambda *_a, **_k: cols[1]
    cols[1].__exit__ = lambda *_a, **_k: None
    mocker.patch.object(top_pro_contra.st, "columns", return_value=cols)
    mock_df = mocker.patch.object(top_pro_contra.st, "dataframe")
    mocker.patch.object(top_pro_contra.st, "markdown")

    top_pro_contra.renderizar_top(_parlamentares(5), _parlamentares(5, 0.1), top_n=10)

    assert mock_df.call_count == 2


def test_top_pro_contra_lista_vazia_nao_quebra(mocker: MockerFixture) -> None:
    """Listas vazias usam ``st.info`` em vez de ``st.dataframe``."""
    cols = (mocker.MagicMock(), mocker.MagicMock())
    cols[0].__enter__ = lambda *_a, **_k: cols[0]
    cols[0].__exit__ = lambda *_a, **_k: None
    cols[1].__enter__ = lambda *_a, **_k: cols[1]
    cols[1].__exit__ = lambda *_a, **_k: None
    mocker.patch.object(top_pro_contra.st, "columns", return_value=cols)
    mock_df = mocker.patch.object(top_pro_contra.st, "dataframe")
    mock_info = mocker.patch.object(top_pro_contra.st, "info")
    mocker.patch.object(top_pro_contra.st, "markdown")

    top_pro_contra.renderizar_top([], [], top_n=10)

    assert mock_df.call_count == 0
    assert mock_info.call_count == 2


def test_top_pro_contra_top_n_respeitado(mocker: MockerFixture) -> None:
    """Com 100 parlamentares e top_n=3, dataframe recebe lista de 3 elementos."""
    cols = (mocker.MagicMock(), mocker.MagicMock())
    cols[0].__enter__ = lambda *_a, **_k: cols[0]
    cols[0].__exit__ = lambda *_a, **_k: None
    cols[1].__enter__ = lambda *_a, **_k: cols[1]
    cols[1].__exit__ = lambda *_a, **_k: None
    mocker.patch.object(top_pro_contra.st, "columns", return_value=cols)
    mock_df = mocker.patch.object(top_pro_contra.st, "dataframe")
    mocker.patch.object(top_pro_contra.st, "markdown")

    top_pro_contra.renderizar_top(_parlamentares(100), _parlamentares(100, 0.1), top_n=3)

    assert mock_df.call_count == 2
    for chamada in mock_df.call_args_list:
        linhas = chamada[0][0]
        assert len(linhas) == 3


def test_top_pro_contra_score_escalado_para_percentual() -> None:
    """``proporcao_sim`` em ``[0, 1]`` é escalado para ``[0, 100]`` no ``Score``.

    Caso real do JSON ``_seed_concluida`` (S38.7): Sâmia Bomfim com
    ``proporcao_sim=0.9928`` deve renderizar ``Score=99.28`` (e o
    ``ProgressColumn`` formatado como ``"99%"``); Eros Biondini com
    ``proporcao_sim=0.0528`` deve render ``Score=5.28`` (``"5%"``).
    """
    linha_samia = top_pro_contra._normalizar_linha(
        1, {"nome": "Sâmia Bomfim", "proporcao_sim": 0.9928}
    )
    assert linha_samia["Score"] == pytest.approx(99.28, abs=0.01)

    linha_eros = top_pro_contra._normalizar_linha(
        1, {"nome": "Eros Biondini", "proporcao_sim": 0.0528}
    )
    assert linha_eros["Score"] == pytest.approx(5.28, abs=0.01)


def test_top_pro_contra_score_default_seguro() -> None:
    """Dict sem ``proporcao_sim`` nem ``score`` produz ``Score=0.0`` (S38.7)."""
    linha = top_pro_contra._normalizar_linha(1, {})
    assert linha["Score"] == 0.0


def test_top_pro_contra_score_aceita_alias_score() -> None:
    """Fallback ``score`` mantido para compatibilidade -- também escalado (S38.7)."""
    linha = top_pro_contra._normalizar_linha(1, {"score": 0.75})
    assert linha["Score"] == pytest.approx(75.0, abs=0.01)


@pytest.mark.parametrize(
    "estado",
    [
        EstadoSessao.CRIADA,
        EstadoSessao.COLETANDO,
        EstadoSessao.ETL,
        EstadoSessao.EMBEDDINGS,
        EstadoSessao.MODELANDO,
        EstadoSessao.CONCLUIDA,
    ],
)
def test_progresso_cobre_todos_os_estados_canonicos(
    mocker: MockerFixture, estado: EstadoSessao
) -> None:
    """``ETAPAS_CANONICAS`` cobre cada um dos 6 estados sequenciais."""
    mocker.patch.object(progresso_sessao.st, "progress")
    mocker.patch.object(progresso_sessao.st, "caption")
    mocker.patch.object(progresso_sessao.st, "markdown")
    progresso_sessao.renderizar_progresso(
        _status_em_etapa(estado),
        etapa_atual="x",
        mensagem="y",
        eta_segundos=10,
    )
