"""Fixtures globais do pytest."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_hemiciclo_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Cria home temporária do Hemiciclo e exporta ``HEMICICLO_HOME``.

    Garante isolamento entre testes -- nenhum teste toca em ``~/hemiciclo`` real.
    """
    home = tmp_path / "hemiciclo_home"
    monkeypatch.setenv("HEMICICLO_HOME", str(home))
    return home
