"""Testes estruturais e funcionais de ``install.sh`` (Linux/macOS).

Cobrem o **arquivo versionado** (estrutura, flags, mensagens PT-BR) e
também executam o script com Python 3.12 stub para validar parse das
flags `--check`, `--com-modelo`, `--com-bge` e `--dry-run` (sprint S23.4).

Os testes são executáveis em qualquer SO Unix-like com `bash` no PATH.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
INSTALL_SH = ROOT / "install.sh"


# ---------------------------------------------------------------------------
# Estrutural -- valida bytes versionados.
# ---------------------------------------------------------------------------


def test_install_sh_existe() -> None:
    assert INSTALL_SH.is_file(), "install.sh deve existir na raiz do repo"


def test_install_sh_executavel() -> None:
    assert os.access(INSTALL_SH, os.X_OK), "install.sh deve ser executável"


def test_install_sh_shebang_bash() -> None:
    txt = INSTALL_SH.read_text(encoding="utf-8")
    assert txt.startswith("#!/usr/bin/env bash"), (
        "install.sh deve começar com shebang ``#!/usr/bin/env bash``"
    )


def test_install_sh_set_strict() -> None:
    txt = INSTALL_SH.read_text(encoding="utf-8")
    assert "set -euo pipefail" in txt, (
        "install.sh deve usar ``set -euo pipefail`` para falhas estritas"
    )


def test_install_sh_referencia_python_3_11() -> None:
    txt = INSTALL_SH.read_text(encoding="utf-8")
    assert "3.11" in txt, "install.sh deve referenciar versão mínima 3.11"


def test_install_sh_referencia_uv_sync_all_extras() -> None:
    txt = INSTALL_SH.read_text(encoding="utf-8")
    assert "uv sync --all-extras" in txt, "install.sh deve invocar uv sync --all-extras"


# ---------------------------------------------------------------------------
# Sprint S23.4 -- flags --com-modelo / --com-bge / --dry-run.
# ---------------------------------------------------------------------------


def test_install_sh_documenta_com_modelo() -> None:
    txt = INSTALL_SH.read_text(encoding="utf-8")
    assert "--com-modelo" in txt, "install.sh deve declarar a flag --com-modelo"
    assert "--com-bge" in txt, "install.sh deve declarar o alias --com-bge"


def test_install_sh_documenta_dry_run() -> None:
    txt = INSTALL_SH.read_text(encoding="utf-8")
    assert "--dry-run" in txt, "install.sh deve declarar a flag --dry-run"


def test_install_sh_referencia_bge_m3() -> None:
    txt = INSTALL_SH.read_text(encoding="utf-8")
    assert "BAAI/bge-m3" in txt, (
        "install.sh deve referenciar o modelo BAAI/bge-m3 no bloco --com-modelo"
    )


def test_install_sh_referencia_flag_embedding() -> None:
    txt = INSTALL_SH.read_text(encoding="utf-8")
    assert "FlagEmbedding" in txt, "install.sh deve invocar FlagEmbedding no bloco --com-modelo"
    assert "BGEM3FlagModel" in txt, "install.sh deve usar BGEM3FlagModel para baixar bge-m3"


def test_install_sh_falha_graciosa_documentada() -> None:
    """Bloco --com-modelo deve capturar exceções e não abortar a instalação base."""
    txt = INSTALL_SH.read_text(encoding="utf-8")
    assert "set +e" in txt, "bloco --com-modelo deve desativar set -e ao redor do download"
    assert "set -e" in txt, "install.sh deve restabelecer set -e após o download"
    assert "Falha graciosa" in txt or "falha graciosa" in txt, (
        "install.sh deve documentar falha graciosa em PT-BR"
    )


# ---------------------------------------------------------------------------
# Acentuação PT-BR consistente (I2 do BRIEF).
# ---------------------------------------------------------------------------


def test_install_sh_acentuacao_pt_br() -> None:
    txt = INSTALL_SH.read_text(encoding="utf-8").lower()
    pares = [
        ("dependencias", "dependências"),
        ("instalacao concluida", "instalação concluída"),
        ("validacao ok", "validação ok"),
    ]
    for sem, com in pares:
        if sem in txt and com not in txt:
            pytest.fail(f"install.sh: '{sem}' presente sem versão acentuada '{com}' (I2)")


# ---------------------------------------------------------------------------
# Smoke real -- executa o script com Python 3.12 stub.
# ---------------------------------------------------------------------------


def _python_3_11_plus_disponivel() -> str | None:
    """Retorna o caminho de um python3.x (>=3.11) disponível, ou None."""
    candidatos = ["python3.12", "python3.11", "python3.13"]
    for nome in candidatos:
        caminho = shutil.which(nome)
        if caminho:
            return caminho
    # Pyenv shim
    pyenv_shim = Path.home() / ".pyenv" / "shims" / "python3.12"
    if pyenv_shim.exists():
        return str(pyenv_shim)
    return None


@pytest.fixture
def python_311_stub_dir(tmp_path: Path) -> Path | None:
    """Cria um diretório com um stub ``python3`` apontando para Python 3.11+.

    Retorna None se nenhum Python 3.11+ estiver disponível no host, casos em
    que os smoke tests são pulados.
    """
    py = _python_3_11_plus_disponivel()
    if py is None:
        return None
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "python3"
    stub.symlink_to(py)
    return bin_dir


def _rodar_install_sh(args: list[str], stub_dir: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PATH"] = f"{stub_dir}:{env.get('PATH', '')}"
    # Pyenv local pode forçar 3.11; desabilitamos para não atrapalhar o stub.
    env["PYENV_VERSION"] = ""
    return subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        cwd=stub_dir.parent,  # tmp_path; sem pyproject.toml
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_install_sh_check_modo_baseline(python_311_stub_dir: Path | None) -> None:
    """``--check`` deve validar e sair sem instalar (regressão zero)."""
    if python_311_stub_dir is None:
        pytest.skip("Python 3.11+ não disponível no host para smoke test")
    result = _rodar_install_sh(["--check"], python_311_stub_dir)
    assert result.returncode == 0, (
        f"--check falhou: code={result.returncode} stderr={result.stderr!r}"
    )
    assert "Modo --check: validação OK" in result.stdout


def test_install_sh_check_com_modelo_avisa(
    python_311_stub_dir: Path | None,
) -> None:
    """``--check --com-modelo`` avisa que --com-modelo foi ignorado."""
    if python_311_stub_dir is None:
        pytest.skip("Python 3.11+ não disponível no host para smoke test")
    result = _rodar_install_sh(["--check", "--com-modelo"], python_311_stub_dir)
    assert result.returncode == 0
    assert "ignorado em --check" in result.stdout


def test_install_sh_dry_run_sem_modelo(python_311_stub_dir: Path | None) -> None:
    """``--dry-run`` (sem --com-modelo) imprime plano sem o passo de download."""
    if python_311_stub_dir is None:
        pytest.skip("Python 3.11+ não disponível no host para smoke test")
    result = _rodar_install_sh(["--dry-run"], python_311_stub_dir)
    assert result.returncode == 0
    assert "Modo --dry-run: plano de execução" in result.stdout
    assert "uv sync --all-extras" in result.stdout
    assert "sem --com-modelo" in result.stdout
    assert "bge-m3 não será baixado" in result.stdout


def test_install_sh_dry_run_com_modelo(python_311_stub_dir: Path | None) -> None:
    """``--com-modelo --dry-run`` mostra o passo de download no plano."""
    if python_311_stub_dir is None:
        pytest.skip("Python 3.11+ não disponível no host para smoke test")
    result = _rodar_install_sh(["--com-modelo", "--dry-run"], python_311_stub_dir)
    assert result.returncode == 0
    assert "Baixar BAAI/bge-m3" in result.stdout
    assert "FlagEmbedding" in result.stdout


def test_install_sh_alias_com_bge(python_311_stub_dir: Path | None) -> None:
    """O alias ``--com-bge`` deve produzir o mesmo plano de ``--com-modelo``."""
    if python_311_stub_dir is None:
        pytest.skip("Python 3.11+ não disponível no host para smoke test")
    result = _rodar_install_sh(["--com-bge", "--dry-run"], python_311_stub_dir)
    assert result.returncode == 0
    assert "Baixar BAAI/bge-m3" in result.stdout


def test_install_sh_arg_desconhecido_avisa_e_continua(
    python_311_stub_dir: Path | None,
) -> None:
    """Args desconhecidas geram aviso mas o script segue (compatibilidade)."""
    if python_311_stub_dir is None:
        pytest.skip("Python 3.11+ não disponível no host para smoke test")
    # Combinamos com --check para o script encerrar antes de tentar uv sync.
    result = _rodar_install_sh(["--argumento-fake", "--check"], python_311_stub_dir)
    assert result.returncode == 0
    assert "argumento desconhecido" in result.stderr or "argumento desconhecido" in result.stdout
