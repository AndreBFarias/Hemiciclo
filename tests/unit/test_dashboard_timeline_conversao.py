"""Testes unit do widget ``timeline_conversao`` (S33).

Cobre o caminho real (Plotly chamado), os caminhos de skip graceful
(``st.info``) e a coloração por posição. Mocka ``st.plotly_chart``,
``st.info``, ``st.caption`` para inspecionar o que foi enviado.
"""

from __future__ import annotations

from typing import Any

from pytest_mock import MockerFixture

from hemiciclo.dashboard import tema
from hemiciclo.dashboard.widgets import timeline_conversao


def _historico_2_buckets() -> dict[str, Any]:
    """Histórico mínimo válido (2 buckets) com 1 mudança detectada."""
    return {
        "metadata": {"granularidade": "ano", "threshold_pp": 30.0},
        "parlamentares": {
            "101": {
                "casa": "camara",
                "nome": "Parlamentar 101",
                "historico": [
                    {
                        "bucket": 2018,
                        "n_votos": 10,
                        "proporcao_sim": 0.8,
                        "proporcao_nao": 0.2,
                        "posicao": "a_favor",
                    },
                    {
                        "bucket": 2024,
                        "n_votos": 12,
                        "proporcao_sim": 0.2,
                        "proporcao_nao": 0.8,
                        "posicao": "contra",
                    },
                ],
                "mudancas_detectadas": [
                    {
                        "bucket_anterior": 2018,
                        "bucket_posterior": 2024,
                        "proporcao_sim_anterior": 0.8,
                        "proporcao_sim_posterior": 0.2,
                        "delta_pp": -60.0,
                        "posicao_anterior": "a_favor",
                        "posicao_posterior": "contra",
                    }
                ],
                "indice_volatilidade": 0.6,
            },
        },
    }


def test_renderizar_timeline_chama_plotly(mocker: MockerFixture) -> None:
    """Histórico válido -> uma chamada a ``plotly_chart`` + caption."""
    mock_plot = mocker.patch.object(timeline_conversao.st, "plotly_chart")
    mock_info = mocker.patch.object(timeline_conversao.st, "info")
    mocker.patch.object(timeline_conversao.st, "caption")

    timeline_conversao.renderizar_timeline_conversao(_historico_2_buckets(), parlamentar_id=101)

    assert mock_plot.call_count == 1
    assert mock_info.call_count == 0


def test_marca_mudancas_no_grafico(mocker: MockerFixture) -> None:
    """Mudança detectada vira anotação com texto ``-60pp`` na figura."""
    mock_plot = mocker.patch.object(timeline_conversao.st, "plotly_chart")
    mocker.patch.object(timeline_conversao.st, "caption")

    timeline_conversao.renderizar_timeline_conversao(_historico_2_buckets(), parlamentar_id=101)

    fig = mock_plot.call_args[0][0]
    # Plotly Figure: layout.annotations
    annotations = list(fig.layout.annotations)
    assert len(annotations) == 1
    texto = str(annotations[0].text)
    assert "-60" in texto
    assert "pp" in texto


def test_dados_vazios_mostra_aviso(mocker: MockerFixture) -> None:
    """``historico_dict=None`` -> ``st.info``, sem chamar Plotly."""
    mock_plot = mocker.patch.object(timeline_conversao.st, "plotly_chart")
    mock_info = mocker.patch.object(timeline_conversao.st, "info")

    timeline_conversao.renderizar_timeline_conversao(None, parlamentar_id=42)

    assert mock_plot.call_count == 0
    assert mock_info.call_count == 1


def test_parlamentar_inexistente_mostra_aviso(mocker: MockerFixture) -> None:
    """Id sem entrada no dict -> ``st.info``."""
    mock_plot = mocker.patch.object(timeline_conversao.st, "plotly_chart")
    mock_info = mocker.patch.object(timeline_conversao.st, "info")

    timeline_conversao.renderizar_timeline_conversao(_historico_2_buckets(), parlamentar_id=999)

    assert mock_plot.call_count == 0
    assert mock_info.call_count == 1


def test_apenas_um_bucket_mostra_aviso(mocker: MockerFixture) -> None:
    """Histórico com 1 bucket único -> info de dados insuficientes."""
    mock_plot = mocker.patch.object(timeline_conversao.st, "plotly_chart")
    mock_info = mocker.patch.object(timeline_conversao.st, "info")

    historico_pobre = {
        "parlamentares": {
            "101": {
                "casa": "camara",
                "nome": "P101",
                "historico": [
                    {
                        "bucket": 2024,
                        "n_votos": 5,
                        "proporcao_sim": 1.0,
                        "proporcao_nao": 0.0,
                        "posicao": "a_favor",
                    },
                ],
                "mudancas_detectadas": [],
                "indice_volatilidade": 0.0,
            },
        },
    }
    timeline_conversao.renderizar_timeline_conversao(historico_pobre, parlamentar_id=101)

    assert mock_plot.call_count == 0
    assert mock_info.call_count == 1


def test_cor_por_posicao() -> None:
    """``_cor_posicao`` mapeia rótulos canônicos para cores institucionais."""
    assert timeline_conversao._cor_posicao("a_favor") == tema.VERDE_FOLHA
    assert timeline_conversao._cor_posicao("contra") == tema.VERMELHO_ARGILA
    assert timeline_conversao._cor_posicao("neutro") == tema.CINZA_PEDRA
    # Default seguro
    assert timeline_conversao._cor_posicao("desconhecido") == tema.CINZA_PEDRA
