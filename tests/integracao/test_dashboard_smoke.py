"""Smoke tests do dashboard via ``streamlit.testing.v1.AppTest``.

A API do AppTest roda o app dentro do mesmo processo do pytest e expõe
listas de elementos renderizados. Não validamos pixels (isso fica para o
skill ``validacao-visual``); validamos contrato lógico do app: roda sem
exceção, mostra storytelling, navega entre abas, valida o form.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

_APP = "src/hemiciclo/dashboard/app.py"
_TIMEOUT = 30


@pytest.fixture
def app(tmp_hemiciclo_home: Path) -> AppTest:  # noqa: ARG001 -- fixture isola HOME
    """AppTest pronto para rodar com HOME isolada por teste."""
    return AppTest.from_file(_APP, default_timeout=_TIMEOUT)


def test_app_carrega_sem_erro(app: AppTest) -> None:
    """O app sobe e termina o primeiro run sem exception."""
    app.run()
    assert not app.exception, f"Exceção ao subir o app: {app.exception}"


def test_intro_renderiza_titulo_hemiciclo(app: AppTest) -> None:
    """A página inicial menciona 'Hemiciclo' em algum markdown."""
    app.run()
    todos = " ".join(m.value for m in app.markdown)
    assert "Hemiciclo" in todos


def test_intro_storytelling_aparece(app: AppTest) -> None:
    """O storytelling da intro está presente no markdown renderizado."""
    app.run()
    todos = " ".join(m.value for m in app.markdown)
    assert "Inteligência política aberta" in todos


def test_lista_sessoes_vazia_mostra_cta(app: AppTest) -> None:
    """Sem sessões em disco, a aba de pesquisas mostra o CTA."""
    app.run()
    # Navega para a aba de lista de sessões via session_state.
    app.session_state["pagina_ativa"] = "lista_sessoes"
    app.run()
    todos = " ".join(m.value for m in app.markdown)
    assert "Você ainda não fez nenhuma pesquisa" in todos


def test_nova_pesquisa_form_renderiza_inputs(app: AppTest) -> None:
    """O formulário de Nova Pesquisa expõe os 7 campos esperados."""
    app.run()
    app.session_state["pagina_ativa"] = "nova_pesquisa"
    app.run()
    # Esperamos: tópico (text_input), casas/legislaturas/UFs/partidos/camadas (multiselect),
    # período (date_input). Ao menos 1 text_input + 5 multiselects + 1 date_input.
    assert len(app.text_input) >= 1
    assert len(app.multiselect) >= 5
    assert len(app.date_input) >= 1


def test_sobre_renderiza_manifesto(app: AppTest) -> None:
    """A página 'Sobre' inclui o storytelling e a stack técnica."""
    app.run()
    app.session_state["pagina_ativa"] = "sobre"
    app.run()
    todos = " ".join(m.value for m in app.markdown)
    assert "ferramenta cidadã" in todos
    assert "GPL v3" in todos


def test_navegacao_botoes_existem(app: AppTest) -> None:
    """Os 4 botões de navegação principal estão presentes."""
    app.run()
    keys = {b.key for b in app.button}
    assert {
        "nav_intro",
        "nav_lista_sessoes",
        "nav_nova_pesquisa",
        "nav_sobre",
    } <= keys


def test_footer_mostra_versao(app: AppTest) -> None:
    """O footer global declara a versão do app (S38 -- release v2.0.0)."""
    from hemiciclo import __version__

    app.run()
    todos = " ".join(m.value for m in app.markdown)
    assert f"v{__version__}" in todos
