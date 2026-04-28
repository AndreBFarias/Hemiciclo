"""Testes e2e do dashboard com seed_dashboard (S31).

Roda ``scripts/seed_dashboard.main`` para popular as 3 sessões fake e
checa que o app sobe + navega entre lista e detalhe.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

_APP = "src/hemiciclo/dashboard/app.py"
_TIMEOUT = 20


def _carregar_seed_dashboard() -> object:
    """Importa ``scripts/seed_dashboard.py`` como módulo (não está em src/)."""
    raiz = Path(__file__).resolve().parents[2]
    caminho = raiz / "scripts" / "seed_dashboard.py"
    spec = importlib.util.spec_from_file_location("seed_dashboard", caminho)
    if spec is None or spec.loader is None:
        msg = f"não foi possível carregar {caminho}"
        raise RuntimeError(msg)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def seed(tmp_hemiciclo_home: Path) -> Path:  # noqa: ARG001 -- HOME isolada via fixture
    """Roda o seed_dashboard.main e devolve a home temporária."""
    mod = _carregar_seed_dashboard()
    main = mod.main  # type: ignore[attr-defined]
    main()
    return tmp_hemiciclo_home


def test_app_renderiza_sessao_concluida_seed(seed: Path) -> None:  # noqa: ARG001
    """Após seed, abrir ``_seed_concluida`` mostra top a-favor/contra."""
    app = AppTest.from_file(_APP, default_timeout=_TIMEOUT)
    app.session_state["pagina_ativa"] = "sessao_detalhe"
    app.session_state["sessao_id"] = "_seed_concluida"
    app.run()
    assert not app.exception, f"exceção: {app.exception}"
    todos = " ".join(m.value for m in app.markdown)
    assert "Top a-favor" in todos
    assert "Top contra" in todos
    assert "aborto" in todos.lower()


def test_app_renderiza_sessao_erro_seed(seed: Path) -> None:  # noqa: ARG001
    """Sessão ``_seed_erro`` exibe mensagem de erro do pipeline simulado."""
    app = AppTest.from_file(_APP, default_timeout=_TIMEOUT)
    app.session_state["pagina_ativa"] = "sessao_detalhe"
    app.session_state["sessao_id"] = "_seed_erro"
    app.run()
    assert not app.exception
    erros = " ".join(e.value for e in app.error)
    assert "503" in erros or "HTTPError" in erros


def test_navegacao_lista_para_detalhe(seed: Path) -> None:  # noqa: ARG001
    """Após seed, lista mostra botões 'Abrir relatório' que redirecionam pra detalhe."""
    app = AppTest.from_file(_APP, default_timeout=_TIMEOUT)
    app.session_state["pagina_ativa"] = "lista_sessoes"
    app.run()
    assert not app.exception
    keys = {b.key for b in app.button}
    abrir_buttons = {k for k in keys if k.startswith("abrir_sessao_")}
    assert len(abrir_buttons) >= 3, f"esperava >=3 botões abrir; achei {abrir_buttons}"
