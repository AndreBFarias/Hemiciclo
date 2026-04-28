"""Testes unit do widget ``ranking_convertibilidade`` (S34).

Cobre os 4 caminhos canônicos:

- ``scores_payload`` ``None`` -> ``st.info``.
- ``skipped=True`` -> ``st.info`` com motivo.
- Lista vazia -> ``st.info`` neutro.
- Lista preenchida -> ``st.dataframe`` chamado (renderização real).

A estratégia é monkeypatch nos métodos do streamlit pra observar o
caminho percorrido. Não montamos servidor Streamlit -- testes
unit puros, igual o padrão do widget de timeline_conversao (S33).
"""

from __future__ import annotations

from typing import Any

import pytest
import streamlit as st

from hemiciclo.dashboard.widgets import ranking_convertibilidade


@pytest.fixture
def chamadas(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Substitui métodos relevantes do streamlit por stubs e devolve log."""
    log: list[str] = []

    def _info(*_a: object, **_k: object) -> None:
        log.append("info")

    def _markdown(*_a: object, **_k: object) -> None:
        log.append("markdown")

    def _caption(*_a: object, **_k: object) -> None:
        log.append("caption")

    def _dataframe(*_a: object, **_k: object) -> None:
        log.append("dataframe")

    class _ExpanderStub:
        def __enter__(self) -> _ExpanderStub:
            log.append("expander_enter")
            return self

        def __exit__(self, *_a: object) -> None:
            log.append("expander_exit")

    def _expander(*_a: object, **_k: object) -> _ExpanderStub:
        return _ExpanderStub()

    monkeypatch.setattr(st, "info", _info)
    monkeypatch.setattr(st, "markdown", _markdown)
    monkeypatch.setattr(st, "caption", _caption)
    monkeypatch.setattr(st, "dataframe", _dataframe)
    monkeypatch.setattr(st, "expander", _expander)
    return log


def test_widget_payload_none(chamadas: list[str]) -> None:
    """``None`` mostra info amigável."""
    ranking_convertibilidade.renderizar_ranking(None)
    assert chamadas == ["info"]


def test_widget_skipped(chamadas: list[str]) -> None:
    """``skipped=True`` mostra motivo via st.info."""
    ranking_convertibilidade.renderizar_ranking({"skipped": True, "motivo": "amostra insuficiente"})
    assert chamadas == ["info"]


def test_widget_lista_vazia(chamadas: list[str]) -> None:
    """``scores=[]`` ou ausente cai em info neutro."""
    ranking_convertibilidade.renderizar_ranking({"skipped": False, "scores": [], "metricas": {}})
    assert chamadas == ["info"]


def test_widget_lista_preenchida_renderiza_tabela(chamadas: list[str]) -> None:
    """Scores não-vazios chamam st.dataframe e mostram coeficientes."""
    payload: dict[str, Any] = {
        "skipped": False,
        "n_amostra": 40,
        "metricas": {"accuracy": 0.81, "f1": 0.65, "roc_auc": 0.78},
        "feature_names": ["indice_volatilidade", "centralidade_grau"],
        "coeficientes": {
            "indice_volatilidade": 1.23,
            "centralidade_grau": -0.45,
        },
        "scores": [
            {
                "parlamentar_id": 101,
                "nome": "Fulano de Tal",
                "casa": "camara",
                "proba": 0.91,
                "indice_volatilidade": 0.78,
            },
            {
                "parlamentar_id": 102,
                "nome": "Sicrano",
                "casa": "camara",
                "proba": 0.42,
                "indice_volatilidade": 0.31,
            },
        ],
    }
    ranking_convertibilidade.renderizar_ranking(payload, top_n=10)
    # markdown do header + caption + dataframe principal +
    # expander dos coeficientes (enter, dataframe, caption, exit).
    assert "dataframe" in chamadas
    assert "expander_enter" in chamadas
    assert "expander_exit" in chamadas
    # Pelo menos 2 chamadas a dataframe (tabela principal + tabela coefs)
    assert chamadas.count("dataframe") >= 2  # noqa: PLR2004


def test_widget_filtra_entradas_nao_dict_e_sem_coefs(chamadas: list[str]) -> None:
    """Cobre linhas 74 (entrada não-dict descartada), 89-90 (lista vazia
    após filtro) e 116 (branch sem coeficientes não abre expander)."""
    payload: dict[str, Any] = {
        "skipped": False,
        "n_amostra": 5,
        "metricas": {"accuracy": 0.5, "f1": 0.0, "roc_auc": 0.0},
        "feature_names": [],
        "coeficientes": {},  # vazio -> não abre expander
        # Todas as entradas inválidas -> linhas filtradas vazias
        "scores": ["nao-dict", 42, None],  # cada uma triggers continue
    }
    ranking_convertibilidade.renderizar_ranking(payload, top_n=10)
    # Cabeçalho roda (markdown+caption), depois cai em info de "vazia após filtro"
    assert "info" in chamadas
    assert "expander_enter" not in chamadas  # sem coeficientes -> branch False
