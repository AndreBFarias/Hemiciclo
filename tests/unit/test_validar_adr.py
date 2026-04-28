"""Testes do validador MADR `scripts/validar_adr.py`."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parent.parent.parent
SCRIPT = RAIZ_REPO / "scripts" / "validar_adr.py"

_spec = importlib.util.spec_from_file_location("validar_adr", SCRIPT)
assert _spec is not None
assert _spec.loader is not None
validar_adr = importlib.util.module_from_spec(_spec)
sys.modules["validar_adr"] = validar_adr
_spec.loader.exec_module(validar_adr)


ADR_VALIDO = """# ADR-001 -- Decisao de teste

- **Status:** accepted
- **Data:** 2026-04-27
- **Decisores:** @AndreBFarias
- **Tags:** infra

## Contexto e problema

Texto de contexto.

## Decisão

Texto da decisao.

## Consequências

Texto das consequencias.
"""

ADR_SEM_DECISAO = """# ADR-001 -- Decisao de teste

- **Status:** accepted
- **Data:** 2026-04-27
- **Decisores:** @AndreBFarias
- **Tags:** infra

## Contexto

Texto de contexto.

## Consequências

Texto das consequencias.
"""

ADR_SEM_STATUS = """# ADR-001 -- Decisao de teste

- **Data:** 2026-04-27
- **Decisores:** @AndreBFarias
- **Tags:** infra

## Contexto

Texto.

## Decisão

Texto.

## Consequências

Texto.
"""

README_TEMPLATE = """# Indice de ADRs

| ADR | Titulo |
|---|---|
{linhas}
"""


def _escreve_adr(diretorio: Path, nome: str, conteudo: str) -> Path:
    arquivo = diretorio / nome
    arquivo.write_text(conteudo, encoding="utf-8")
    return arquivo


def _escreve_readme(diretorio: Path, numeros: list[int]) -> Path:
    linhas = "\n".join(f"| [ADR-{n:03d}](ADR-{n:03d}-x.md) | titulo {n} |" for n in numeros)
    readme = diretorio / "README.md"
    readme.write_text(README_TEMPLATE.format(linhas=linhas), encoding="utf-8")
    return readme


def test_adr_valido_passa(tmp_path: Path) -> None:
    _escreve_adr(tmp_path, "ADR-001-decisao-de-teste.md", ADR_VALIDO)
    _escreve_readme(tmp_path, [1])
    erros, warnings = validar_adr.validar_diretorio(tmp_path)
    assert erros == []
    assert warnings == []


def test_adr_sem_decisao_falha(tmp_path: Path) -> None:
    _escreve_adr(tmp_path, "ADR-001-decisao-de-teste.md", ADR_SEM_DECISAO)
    _escreve_readme(tmp_path, [1])
    erros, _ = validar_adr.validar_diretorio(tmp_path)
    assert any("decisao" in e.lower() for e in erros), erros


def test_adr_sem_status_falha(tmp_path: Path) -> None:
    _escreve_adr(tmp_path, "ADR-001-decisao-de-teste.md", ADR_SEM_STATUS)
    _escreve_readme(tmp_path, [1])
    erros, _ = validar_adr.validar_diretorio(tmp_path)
    assert any("Status" in e for e in erros), erros


def test_numeracao_com_buraco_warning(tmp_path: Path) -> None:
    _escreve_adr(tmp_path, "ADR-001-um.md", ADR_VALIDO)
    terceiro = ADR_VALIDO.replace("ADR-001", "ADR-003")
    _escreve_adr(tmp_path, "ADR-003-tres.md", terceiro)
    _escreve_readme(tmp_path, [1, 3])
    erros, warnings = validar_adr.validar_diretorio(tmp_path)
    assert erros == []
    assert any("ADR-002" in w for w in warnings), warnings


def test_readme_desatualizado_falha(tmp_path: Path) -> None:
    _escreve_adr(tmp_path, "ADR-001-um.md", ADR_VALIDO)
    segundo = ADR_VALIDO.replace("ADR-001", "ADR-002")
    _escreve_adr(tmp_path, "ADR-002-dois.md", segundo)
    _escreve_readme(tmp_path, [1])
    erros, _ = validar_adr.validar_diretorio(tmp_path)
    assert any("ADR-002" in e for e in erros), erros


def test_readme_atualizado_passa(tmp_path: Path) -> None:
    _escreve_adr(tmp_path, "ADR-001-um.md", ADR_VALIDO)
    segundo = ADR_VALIDO.replace("ADR-001", "ADR-002")
    _escreve_adr(tmp_path, "ADR-002-dois.md", segundo)
    _escreve_readme(tmp_path, [1, 2])
    erros, warnings = validar_adr.validar_diretorio(tmp_path)
    assert erros == []
    assert warnings == []


def test_diretorio_vazio_passa(tmp_path: Path) -> None:
    erros, warnings = validar_adr.validar_diretorio(tmp_path)
    assert erros == []
    assert warnings == []


def test_main_no_repo_real_retorna_zero() -> None:
    repo_adr_dir = RAIZ_REPO / "docs" / "adr"
    rc = validar_adr.main([str(repo_adr_dir)])
    assert rc == 0


def test_filename_invalido_falha(tmp_path: Path) -> None:
    arquivo = tmp_path / "ADR-1-bad.md"
    arquivo.write_text(ADR_VALIDO, encoding="utf-8")
    erros, _ = validar_adr.validar_diretorio(tmp_path)
    assert any("filename" in e.lower() for e in erros), erros


def test_numero_filename_diverge_header(tmp_path: Path) -> None:
    conteudo = ADR_VALIDO.replace("ADR-001", "ADR-007")
    _escreve_adr(tmp_path, "ADR-002-divergente.md", conteudo)
    _escreve_readme(tmp_path, [2])
    erros, _ = validar_adr.validar_diretorio(tmp_path)
    assert any("diverge" in e for e in erros), erros


def test_main_em_diretorio_inexistente_falha(tmp_path: Path) -> None:
    inexistente = tmp_path / "nao_existe"
    rc = validar_adr.main([str(inexistente)])
    assert rc == 1


def test_main_default_repo(capsys: pytest.CaptureFixture[str]) -> None:
    rc = validar_adr.main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert "ADRs validados" in captured.out
