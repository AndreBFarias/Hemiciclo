"""Testes estruturais dos scripts ``.bat`` Windows (rodam em qualquer SO).

Validam o **arquivo versionado** (bytes + decode UTF-8), nunca executam o
script. Isso garante que regressões de encoding (CRLF, UTF-8, ``chcp``,
acentuação PT-BR) sejam pegas no CI cross-OS, mesmo em runners Linux/macOS
onde ``cmd.exe`` não existe.

Sprint S36 -- paridade Windows com ``install.sh``/``run.sh``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
INSTALL_BAT = ROOT / "install.bat"
RUN_BAT = ROOT / "run.bat"


def test_install_bat_existe() -> None:
    assert INSTALL_BAT.is_file(), "install.bat deve existir na raiz do repo"


def test_run_bat_existe() -> None:
    assert RUN_BAT.is_file(), "run.bat deve existir na raiz do repo"


def test_install_bat_crlf_line_endings() -> None:
    raw = INSTALL_BAT.read_bytes()
    assert b"\r\n" in raw, "install.bat deve ter line endings CRLF"
    # Garantir que todo \n é precedido de \r (sem LF órfão)
    for i, byte in enumerate(raw):
        if byte == 0x0A and (i == 0 or raw[i - 1] != 0x0D):
            pytest.fail(f"install.bat: LF órfão (sem CR) em offset {i}")


def test_run_bat_crlf_line_endings() -> None:
    raw = RUN_BAT.read_bytes()
    assert b"\r\n" in raw, "run.bat deve ter line endings CRLF"
    for i, byte in enumerate(raw):
        if byte == 0x0A and (i == 0 or raw[i - 1] != 0x0D):
            pytest.fail(f"run.bat: LF órfão (sem CR) em offset {i}")


def test_install_bat_tem_chcp_utf8() -> None:
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    assert "chcp 65001" in txt[:300], "install.bat deve declarar chcp 65001 no topo"


def test_run_bat_tem_chcp_utf8() -> None:
    txt = RUN_BAT.read_text(encoding="utf-8")
    assert "chcp 65001" in txt[:300], "run.bat deve declarar chcp 65001 no topo"


def test_install_bat_tem_echo_off() -> None:
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    assert txt.lstrip().startswith("@echo off"), "primeira linha útil deve ser @echo off"


def test_run_bat_tem_echo_off() -> None:
    txt = RUN_BAT.read_text(encoding="utf-8")
    assert txt.lstrip().startswith("@echo off"), "primeira linha útil deve ser @echo off"


def test_install_bat_referencia_python_3_11() -> None:
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    assert "3.11" in txt, "install.bat deve referenciar versão mínima 3.11"


def test_install_bat_referencia_uv_sync_all_extras() -> None:
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    assert "uv sync --all-extras" in txt, "install.bat deve invocar uv sync --all-extras"


def test_install_bat_referencia_python_org() -> None:
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    assert "python.org" in txt, "install.bat deve apontar python.org em mensagem de erro"


def test_install_bat_modo_check_documentado() -> None:
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    assert "--check" in txt, "install.bat deve suportar modo --check"


def test_install_bat_documenta_com_modelo() -> None:
    """Sprint S23.4: install.bat deve declarar a flag --com-modelo e o alias --com-bge."""
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    assert "--com-modelo" in txt, "install.bat deve declarar a flag --com-modelo"
    assert "--com-bge" in txt, "install.bat deve declarar o alias --com-bge"


def test_install_bat_documenta_dry_run() -> None:
    """Sprint S23.4: install.bat deve declarar a flag --dry-run."""
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    assert "--dry-run" in txt, "install.bat deve declarar a flag --dry-run"


def test_install_bat_referencia_bge_m3() -> None:
    """Sprint S23.4: bloco --com-modelo deve invocar BAAI/bge-m3 via FlagEmbedding."""
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    assert "BAAI/bge-m3" in txt, "install.bat deve referenciar BAAI/bge-m3 no bloco --com-modelo"
    assert "FlagEmbedding" in txt, "install.bat deve invocar FlagEmbedding no bloco --com-modelo"
    assert "BGEM3FlagModel" in txt, "install.bat deve usar BGEM3FlagModel para baixar bge-m3"


def test_run_bat_referencia_streamlit_run() -> None:
    txt = RUN_BAT.read_text(encoding="utf-8")
    assert "streamlit run src\\hemiciclo\\dashboard\\app.py" in txt, (
        "run.bat deve invocar streamlit run com path Windows (backslashes)"
    )


def test_run_bat_porta_8501() -> None:
    txt = RUN_BAT.read_text(encoding="utf-8")
    assert "8501" in txt, "run.bat deve subir Streamlit na porta 8501"


def test_bats_acentuacao_pt_br_consistente() -> None:
    """Garante I2 do BRIEF: textos PT-BR visíveis com acentuação correta.

    Palavras canônicas que só aparecem com acento se aparecerem (ou seja,
    a forma sem acento é proibida quando indica termo PT-BR no qual o
    acento é semanticamente obrigatório).
    """
    pares_obrigatorios = [
        # (sem_acento_proibido, com_acento_canonico)
        ("instalacao concluida", "instalação concluída"),
        ("dependencias", "dependências"),
        ("validacao OK", "validação OK"),
    ]
    for path in (INSTALL_BAT, RUN_BAT):
        txt = path.read_text(encoding="utf-8").lower()
        for sem_acento, com_acento in pares_obrigatorios:
            sem = sem_acento.lower()
            com = com_acento.lower()
            if sem in txt and com not in txt:
                pytest.fail(
                    f"{path.name}: '{sem_acento}' presente sem versão acentuada "
                    f"'{com_acento}' (I2 do BRIEF)"
                )


def test_install_bat_sem_path_em_blocos_if() -> None:
    """Bug regressão S36: ``%PATH%`` dentro de bloco ``if (... )`` é
    expandido em parse-time. Se PATH contém ``Program Files (x86)``, o
    ``)`` interno quebra o agrupamento do bloco e CMD reporta
    "... was unexpected at this time." com exit 255.

    Solução: dentro de blocos delimitados por ``(`` ``)``, usar
    ``!VAR!`` (delayed expansion) em vez de ``%VAR%`` para PATH e outras
    variáveis que podem conter parênteses.
    """
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    # Procura linhas dentro de blocos com `set "PATH=...%PATH%..."`.
    # Uso simples: nenhuma linha pode misturar `set "PATH=` com `%PATH%`.
    for linha in txt.splitlines():
        if "set " in linha and "PATH=" in linha and "%PATH%" in linha:
            pytest.fail(
                f"install.bat: linha '{linha.strip()}' usa %PATH% em set; "
                "use !PATH! (delayed expansion) para evitar quebra em "
                "diretórios com parênteses (Program Files (x86))"
            )


def test_install_bat_sem_parenteses_literais_em_echo_dentro_bloco() -> None:
    """Bug regressão S36: ``)`` literal em ``echo ... (texto)`` dentro de
    bloco ``if/else (... )`` é interpretado pelo CMD como fim do bloco.

    Detecção heurística: qualquer linha de ``echo`` que comece com 4
    espaços (indentada, portanto provavelmente dentro de bloco) e contenha
    ``)`` não-escapado dispara fail.
    """
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    for n_linha, linha in enumerate(txt.splitlines(), start=1):
        if not linha.startswith("    echo "):
            continue
        # Procura ')' não precedido de '^' (escape CMD)
        for i, c in enumerate(linha):
            if c == ")" and (i == 0 or linha[i - 1] != "^"):
                pytest.fail(
                    f"install.bat:{n_linha}: ``echo`` indentado com ``)`` "
                    f"não-escapado quebra o agrupamento do bloco enclosing. "
                    f"Use ``^)`` ou substitua por outro caractere. Linha: "
                    f"{linha.strip()!r}"
                )


def test_bats_sem_redirecionamento_unix() -> None:
    """Bug regressão S36: ``>/dev/null`` é sintaxe Unix; em CMD é ``>nul``.

    Versão original do install.bat usava ``>/dev/null 2>&1``, que no Windows
    causa "The system cannot find the path specified." em cada uso e exit
    code 255 quando combinado com encadeamento de ``if`` (efeito colateral
    do redirect falho).
    """
    for path in (INSTALL_BAT, RUN_BAT):
        txt = path.read_text(encoding="utf-8")
        assert "/dev/null" not in txt, (
            f"{path.name}: ``/dev/null`` é sintaxe Unix; use ``>nul 2>&1`` no Windows"
        )
