"""Cobertura dos cliques nos CTAs da página intro (S23)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st  # noqa: F401 -- usado por mocker.patch implícito

from hemiciclo.dashboard.paginas import intro

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def _fakes_basicos(mocker):  # type: ignore[no-untyped-def]
    """Configura mocks compartilhados pelos testes de intro."""
    mocker.patch("hemiciclo.dashboard.paginas.intro.st.markdown")
    mocker.patch("hemiciclo.dashboard.paginas.intro.componentes.storytelling")

    class _FakeCol:
        def __enter__(self) -> _FakeCol:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    mocker.patch(
        "hemiciclo.dashboard.paginas.intro.st.columns",
        return_value=[_FakeCol(), _FakeCol(), _FakeCol()],
    )


def test_intro_cta_nova_pesquisa(mocker: MockerFixture, tmp_hemiciclo_home: Path) -> None:
    """Clique no CTA primário leva à aba ``nova_pesquisa``."""
    from hemiciclo.config import Configuracao

    _fakes_basicos(mocker)
    fake_session: dict[str, object] = {}
    mocker.patch.object(intro.st, "session_state", fake_session, create=True)
    # Primeiro botão (CTA primário) retorna True; segundo retorna False.
    mocker.patch(
        "hemiciclo.dashboard.paginas.intro.st.button",
        side_effect=[True, False],
    )
    fake_rerun = mocker.patch("hemiciclo.dashboard.paginas.intro.st.rerun")

    intro.render(Configuracao())
    assert fake_session["pagina_ativa"] == "nova_pesquisa"
    fake_rerun.assert_called_once()


def test_intro_cta_manifesto(mocker: MockerFixture, tmp_hemiciclo_home: Path) -> None:
    """Clique em ``Ler manifesto`` leva à aba ``sobre``."""
    from hemiciclo.config import Configuracao

    _fakes_basicos(mocker)
    fake_session: dict[str, object] = {}
    mocker.patch.object(intro.st, "session_state", fake_session, create=True)
    mocker.patch(
        "hemiciclo.dashboard.paginas.intro.st.button",
        side_effect=[False, True],
    )
    fake_rerun = mocker.patch("hemiciclo.dashboard.paginas.intro.st.rerun")

    intro.render(Configuracao())
    assert fake_session["pagina_ativa"] == "sobre"
    fake_rerun.assert_called_once()
