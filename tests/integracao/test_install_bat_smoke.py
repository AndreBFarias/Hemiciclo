"""Smoke de execução real de ``install.bat --check`` (Windows-only).

Em Linux/macOS estes testes são pulados via ``pytest.skipif``. No CI rodam
no runner ``windows-2022`` da matriz multi-OS (job ``test`` do
``.github/workflows/ci.yml``), garantindo que o caminho do usuário final
Windows funcione de fato.

Sprint S36 -- paridade Windows.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="install.bat smoke roda apenas em Windows",
)

ROOT = Path(__file__).parent.parent.parent


def _rodar_install_check() -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- caminho controlado, sem shell
        [str(ROOT / "install.bat"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        shell=True,
    )


def test_install_bat_check_mode_exit_zero() -> None:
    result = _rodar_install_check()
    assert result.returncode == 0, (
        f"install.bat --check falhou: code={result.returncode} "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def test_install_bat_check_mode_imprime_python_ok() -> None:
    result = _rodar_install_check()
    assert "Python" in result.stdout, f"stdout sem 'Python': {result.stdout!r}"
    assert "OK" in result.stdout, f"stdout sem 'OK': {result.stdout!r}"


def test_install_bat_check_mode_imprime_em_pt_br() -> None:
    """I2 do BRIEF: PT-BR com acentuação correta em mensagens visíveis."""
    result = _rodar_install_check()
    assert "validação" in result.stdout, (
        f"stdout deve conter 'validação' (com acento), recebido: {result.stdout!r}"
    )
