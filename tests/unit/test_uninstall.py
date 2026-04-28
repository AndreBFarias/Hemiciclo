"""Testes estruturais dos scripts de desinstalação (cross-OS).

Validam o **arquivo versionado** (bytes + decode UTF-8), nunca executam o
script. Garante que regressões de encoding (CRLF no .bat, UTF-8, ``chcp``,
acentuação PT-BR) sejam pegas no CI cross-OS.

Sprint S38.2 -- substitui ``uninstall.sh`` legado da era R por scripts
compatíveis com a stack Python 3.11+ atual e adiciona ``uninstall.bat``
para Windows.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
UNINSTALL_SH = ROOT / "uninstall.sh"
UNINSTALL_BAT = ROOT / "uninstall.bat"


def test_uninstall_sh_existe() -> None:
    assert UNINSTALL_SH.is_file(), "uninstall.sh deve existir na raiz"


def test_uninstall_bat_existe() -> None:
    assert UNINSTALL_BAT.is_file(), "uninstall.bat deve existir na raiz"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="NTFS não preserva bit +x; uninstall.sh é payload Linux/macOS",
)
def test_uninstall_sh_executavel() -> None:
    """Bit de execução presente (Linux/macOS) — gitattributes garante."""
    import stat

    modo = UNINSTALL_SH.stat().st_mode
    assert modo & stat.S_IXUSR, "uninstall.sh precisa de bit +x"


def test_uninstall_bat_crlf_line_endings() -> None:
    raw = UNINSTALL_BAT.read_bytes()
    assert b"\r\n" in raw, "uninstall.bat deve ter line endings CRLF"
    for i, byte in enumerate(raw):
        if byte == 0x0A and (i == 0 or raw[i - 1] != 0x0D):
            pytest.fail(f"uninstall.bat: LF órfão em offset {i}")


def test_uninstall_bat_tem_chcp_utf8() -> None:
    """Lição S32: encoding UTF-8 explícito evita cp1252."""
    txt = UNINSTALL_BAT.read_text(encoding="utf-8")
    assert "chcp 65001" in txt, "uninstall.bat precisa de ``chcp 65001`` no topo"


def test_uninstall_bat_tem_echo_off() -> None:
    txt = UNINSTALL_BAT.read_text(encoding="utf-8")
    assert txt.lstrip().startswith("@echo off"), "uninstall.bat deve começar com @echo off"


def test_uninstall_sh_remove_venv_e_hemiciclo_home() -> None:
    """Garante que os 2 alvos canônicos (venv + ~/hemiciclo) estão cobertos."""
    txt = UNINSTALL_SH.read_text(encoding="utf-8")
    assert ".venv" in txt, "uninstall.sh deve mencionar .venv"
    assert "hemiciclo" in txt.lower(), "uninstall.sh deve mencionar ~/hemiciclo"
    assert "rm -rf" in txt, "uninstall.sh deve usar rm -rf"


def test_uninstall_bat_remove_venv_e_hemiciclo_home() -> None:
    txt = UNINSTALL_BAT.read_text(encoding="utf-8")
    assert ".venv" in txt
    assert "hemiciclo" in txt.lower()
    assert "rmdir /s /q" in txt or "rmdir /S /Q" in txt


def test_uninstall_sh_modo_yes_documentado() -> None:
    """Modo --yes para CI/scripts."""
    txt = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "--yes" in txt, "uninstall.sh deve suportar --yes para confirmações automáticas"


def test_uninstall_bat_modo_yes_documentado() -> None:
    txt = UNINSTALL_BAT.read_text(encoding="utf-8")
    assert "--yes" in txt, "uninstall.bat deve suportar --yes"


def test_uninstall_sh_nao_e_legado_r() -> None:
    """Garante que não há resquício do uninstaller R legado.

    O script anterior tentava remover pacotes R (tidyverse, RCurl, doMC etc.)
    que não fazem mais parte da stack Python 3.11+.
    """
    txt = UNINSTALL_SH.read_text(encoding="utf-8")
    palavras_proibidas = ["tidyverse", "RCurl", "doMC", "Rscript", "remove.packages"]
    for palavra in palavras_proibidas:
        assert palavra not in txt, (
            f"uninstall.sh ainda contém resquício R legado: '{palavra}'. "
            "S38.2 deveria ter removido toda referência à stack R."
        )


def test_uninstall_sh_acentuacao_pt_br() -> None:
    """I2 do BRIEF: textos visíveis em PT-BR com acentuação correta."""
    txt = UNINSTALL_SH.read_text(encoding="utf-8").lower()
    if "instalacao" in txt and "instalação" not in txt:
        pytest.fail("uninstall.sh: 'instalacao' sem acento")
    if "desinstalacao" in txt and "desinstalação" not in txt:
        pytest.fail("uninstall.sh: 'desinstalacao' sem acento")


def test_uninstall_bat_sem_redirecionamento_unix() -> None:
    """Lição S36: ``>/dev/null`` é Unix; em CMD é ``>nul``."""
    txt = UNINSTALL_BAT.read_text(encoding="utf-8")
    assert "/dev/null" not in txt, "uninstall.bat: use ``>nul`` em vez de ``>/dev/null``"
