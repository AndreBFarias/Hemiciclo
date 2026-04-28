"""Testes dos componentes reutilizáveis do dashboard (S23).

Usamos ``pytest-mock`` para interceptar chamadas a ``streamlit`` sem subir
o runtime real do Streamlit. Os testes verificam contrato e payload de
``st.markdown`` em vez de renderização visual (essa é coberta pelo skill
``validacao-visual`` no validador da sprint).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hemiciclo.dashboard import componentes, tema

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def _markdown_payload(mock_call) -> str:  # type: ignore[no-untyped-def]
    """Concatena os argumentos posicionais de uma chamada a st.markdown."""
    return " ".join(str(a) for a in mock_call.args)


def test_header_global_renderiza_versao(mocker: MockerFixture) -> None:
    """``header_global`` exibe a versão informada."""
    fake_md = mocker.patch("hemiciclo.dashboard.componentes.st.markdown")
    componentes.header_global("0.1.0")
    chamadas = " ".join(_markdown_payload(c) for c in fake_md.mock_calls)
    assert "v0.1.0" in chamadas
    assert "Hemiciclo" in chamadas


def test_storytelling_renderiza_chave_existente(mocker: MockerFixture) -> None:
    """``storytelling`` injeta o texto correspondente da aba."""
    fake_md = mocker.patch("hemiciclo.dashboard.componentes.st.markdown")
    componentes.storytelling("intro")
    payload = " ".join(_markdown_payload(c) for c in fake_md.mock_calls)
    assert tema.STORYTELLING["intro"][:30] in payload


def test_storytelling_chave_inexistente_silencioso(mocker: MockerFixture) -> None:
    """Chave inexistente não levanta erro nem renderiza markdown."""
    fake_md = mocker.patch("hemiciclo.dashboard.componentes.st.markdown")
    componentes.storytelling("inexistente")
    fake_md.assert_not_called()


def test_card_sessao_renderiza_metadados(mocker: MockerFixture) -> None:
    """``card_sessao`` inclui tópico, casas, UFs e badge do estado."""
    fake_md = mocker.patch("hemiciclo.dashboard.componentes.st.markdown")
    sessao = {
        "topico": "aborto",
        "casas": ["camara"],
        "ufs": ["SP", "RJ"],
        "estado": "coletando",
        "progresso_pct": 42.0,
        "iniciada_em": "2026-04-28T12:00:00",
    }
    componentes.card_sessao(sessao)
    payload = " ".join(_markdown_payload(c) for c in fake_md.mock_calls)
    assert "aborto" in payload
    assert "camara" in payload
    assert "SP" in payload
    assert "coletando" in payload
    assert "hemiciclo-card-sessao" in payload


def test_card_sessao_estado_concluida_omite_progresso(
    mocker: MockerFixture,
) -> None:
    """Sessão concluída não exibe a barra de progresso textual."""
    fake_md = mocker.patch("hemiciclo.dashboard.componentes.st.markdown")
    sessao = {
        "topico": "x",
        "casas": ["camara"],
        "ufs": [],
        "estado": "concluida",
        "progresso_pct": 100.0,
        "iniciada_em": "2026-04-28",
    }
    componentes.card_sessao(sessao)
    payload = " ".join(_markdown_payload(c) for c in fake_md.mock_calls)
    assert "progresso:" not in payload


def test_cta_primeira_pesquisa_renderiza_e_botao(mocker: MockerFixture) -> None:
    """``cta_primeira_pesquisa`` renderiza markdown e tenta criar botão."""
    fake_md = mocker.patch("hemiciclo.dashboard.componentes.st.markdown")
    fake_btn = mocker.patch("hemiciclo.dashboard.componentes.st.button", return_value=False)
    componentes.cta_primeira_pesquisa()
    payload = " ".join(_markdown_payload(c) for c in fake_md.mock_calls)
    assert "Você ainda não fez nenhuma pesquisa" in payload
    fake_btn.assert_called_once()


def test_cta_primeira_pesquisa_botao_navega(mocker: MockerFixture) -> None:
    """Clique no botão grava ``pagina_ativa`` e força rerun."""
    mocker.patch("hemiciclo.dashboard.componentes.st.markdown")
    mocker.patch("hemiciclo.dashboard.componentes.st.button", return_value=True)
    fake_session: dict[str, object] = {}
    mocker.patch.object(componentes.st, "session_state", fake_session, create=True)
    fake_rerun = mocker.patch("hemiciclo.dashboard.componentes.st.rerun")
    componentes.cta_primeira_pesquisa()
    assert fake_session["pagina_ativa"] == "nova_pesquisa"
    fake_rerun.assert_called_once()


def test_footer_global_inclui_estatisticas(mocker: MockerFixture) -> None:
    """Footer mostra versão, contagem de sessões e modelo base."""
    fake_md = mocker.patch("hemiciclo.dashboard.componentes.st.markdown")
    componentes.footer_global({"versao": "0.1.0", "n_sessoes": 3, "modelo_base": "base_v1"})
    payload = " ".join(_markdown_payload(c) for c in fake_md.mock_calls)
    assert "v0.1.0" in payload
    assert "3 sessão(ões)" in payload
    assert "base_v1" in payload


def test_navegacao_principal_clique_navega(mocker: MockerFixture) -> None:
    """Clique num botão de navegação grava a aba e força rerun."""
    mocker.patch("hemiciclo.dashboard.componentes.st.markdown")
    fake_session: dict[str, object] = {}
    mocker.patch.object(componentes.st, "session_state", fake_session, create=True)

    class _FakeCol:
        def __enter__(self) -> _FakeCol:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    mocker.patch(
        "hemiciclo.dashboard.componentes.st.columns",
        return_value=[_FakeCol(), _FakeCol(), _FakeCol(), _FakeCol()],
    )
    # Botão da segunda aba clicado.
    mocker.patch(
        "hemiciclo.dashboard.componentes.st.button",
        side_effect=[False, True, False, False],
    )
    fake_rerun = mocker.patch("hemiciclo.dashboard.componentes.st.rerun")

    paginas: dict[str, tuple[str, object]] = {
        "intro": ("Início", lambda _cfg: None),
        "lista_sessoes": ("Pesquisas", lambda _cfg: None),
        "nova_pesquisa": ("Nova pesquisa", lambda _cfg: None),
        "sobre": ("Sobre", lambda _cfg: None),
    }
    componentes.navegacao_principal(paginas)  # type: ignore[arg-type]
    assert fake_session["pagina_ativa"] == "lista_sessoes"
    fake_rerun.assert_called_once()
