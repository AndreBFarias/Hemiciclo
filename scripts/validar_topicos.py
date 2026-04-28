#!/usr/bin/env python3
"""Validador de tópicos YAML do Hemiciclo (S27).

Espelha o padrão de scripts/validar_adr.py: Python puro, mínima superfície
de dependência (stdlib + pyyaml + jsonschema), CLI e biblioteca.

Regras (erro -> exit 1):
- Cada `topicos/*.yaml` (exceto `_schema.yaml`) valida contra `_schema.yaml`.
- Cada padrão em `regex` compila com `re.compile`.
- Cada padrão em `exclusoes[].regex` compila.
- Lista `keywords` não-vazia e sem entradas vazias.
- Nome do arquivo bate com `nome:` interno (sem extensão).

Saída:
- Exit 0: `[validar_topicos] N topicos validados em <dir>. Zero erros.`
- Exit 1: erros descritivos em stderr.

Uso:
    python scripts/validar_topicos.py [<diretorio>]

Default `<diretorio>`: `<raiz_do_repo>/topicos`.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

NOME_SCHEMA = "_schema.yaml"


@dataclass
class TopicoBruto:
    """Resultado mínimo do parse de um YAML de tópico."""

    path: Path
    dados: dict[str, Any] = field(default_factory=dict)


def _carregar_schema(schema_path: Path) -> dict[str, Any]:
    """Carrega `_schema.yaml` e devolve dict (já validado como JSON Schema)."""
    if not schema_path.exists():
        raise FileNotFoundError(f"schema ausente: {schema_path}")
    with schema_path.open(encoding="utf-8") as f:
        bruto = yaml.safe_load(f)
    if not isinstance(bruto, dict):
        raise ValueError(f"{schema_path.name}: raiz deve ser mapa YAML")
    Draft202012Validator.check_schema(bruto)
    return bruto


def _ler_topico(path: Path) -> tuple[TopicoBruto | None, list[str]]:
    """Lê um YAML; devolve (TopicoBruto, lista_de_erros_de_parse)."""
    erros: list[str] = []
    try:
        with path.open(encoding="utf-8") as f:
            dados = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        erros.append(f"{path.name}: YAML inválido ({exc})")
        return None, erros
    except OSError as exc:
        erros.append(f"{path.name}: erro de leitura ({exc})")
        return None, erros

    if not isinstance(dados, dict):
        erros.append(f"{path.name}: raiz deve ser mapa YAML, não {type(dados).__name__}")
        return None, erros
    return TopicoBruto(path=path, dados=dados), erros


def _validar_regex(topico: TopicoBruto) -> list[str]:
    """Tenta `re.compile` em todos os padrões; retorna lista de erros."""
    erros: list[str] = []
    nome = topico.path.name
    for i, padrao in enumerate(topico.dados.get("regex") or []):
        if not isinstance(padrao, str):
            erros.append(f"{nome}: regex[{i}] não é string ({type(padrao).__name__})")
            continue
        try:
            re.compile(padrao)
        except re.error as exc:
            erros.append(f"{nome}: regex[{i}] inválida -- {exc} -- padrão: {padrao!r}")
    for i, item in enumerate(topico.dados.get("exclusoes") or []):
        if not isinstance(item, dict):
            erros.append(f"{nome}: exclusoes[{i}] não é objeto")
            continue
        padrao = item.get("regex")
        if not isinstance(padrao, str):
            erros.append(f"{nome}: exclusoes[{i}].regex ausente ou não-string")
            continue
        try:
            re.compile(padrao)
        except re.error as exc:
            erros.append(f"{nome}: exclusoes[{i}].regex inválida -- {exc}")
    return erros


def _validar_keywords(topico: TopicoBruto) -> list[str]:
    """Garante que keywords não tem strings vazias."""
    erros: list[str] = []
    nome = topico.path.name
    kws = topico.dados.get("keywords") or []
    for i, kw in enumerate(kws):
        if not isinstance(kw, str) or not kw.strip():
            erros.append(f"{nome}: keywords[{i}] vazia ou não-string")
    return erros


def _validar_nome_filename(topico: TopicoBruto) -> list[str]:
    """O `nome:` interno deve bater com o filename (sem extensão)."""
    erros: list[str] = []
    nome_arquivo = topico.path.stem
    nome_interno = topico.dados.get("nome")
    if isinstance(nome_interno, str) and nome_interno != nome_arquivo:
        erros.append(
            f"{topico.path.name}: campo 'nome' ({nome_interno!r}) "
            f"diverge do filename ({nome_arquivo!r})"
        )
    return erros


def validar_topico(topico: TopicoBruto, schema: dict[str, Any]) -> list[str]:
    """Valida um tópico individual contra schema + checagens semânticas."""
    erros: list[str] = []
    nome = topico.path.name

    validator = Draft202012Validator(schema)
    schema_erros: list[ValidationError] = sorted(
        validator.iter_errors(topico.dados), key=lambda e: list(e.absolute_path)
    )
    for err in schema_erros:
        caminho = "/".join(str(p) for p in err.absolute_path) or "(raiz)"
        erros.append(f"{nome}: schema -- {caminho}: {err.message}")

    erros.extend(_validar_regex(topico))
    erros.extend(_validar_keywords(topico))
    erros.extend(_validar_nome_filename(topico))
    return erros


def validar_diretorio(topicos_dir: Path) -> tuple[list[str], int]:
    """Valida todos os tópicos do diretório.

    Returns:
        (erros, total_validados). `total_validados` conta apenas os YAMLs
        de tópico (exclui ``_schema.yaml``).
    """
    erros: list[str] = []
    if not topicos_dir.exists():
        erros.append(f"diretório inexistente: {topicos_dir}")
        return erros, 0

    schema_path = topicos_dir / NOME_SCHEMA
    try:
        schema = _carregar_schema(schema_path)
    except (FileNotFoundError, ValueError, ValidationError) as exc:
        erros.append(f"schema inválido: {exc}")
        return erros, 0

    arquivos = sorted(p for p in topicos_dir.glob("*.yaml") if p.name != NOME_SCHEMA)
    total = 0
    for arquivo in arquivos:
        topico, erros_parse = _ler_topico(arquivo)
        erros.extend(erros_parse)
        if topico is None:
            continue
        erros.extend(validar_topico(topico, schema))
        total += 1
    return erros, total


def main(argv: list[str] | None = None) -> int:
    """Entry point CLI. Retorna 0 (OK) ou 1 (erro)."""
    if argv is None:
        argv = sys.argv[1:]

    if argv:
        topicos_dir = Path(argv[0])
    else:
        raiz = Path(__file__).resolve().parent.parent
        topicos_dir = raiz / "topicos"

    erros, total = validar_diretorio(topicos_dir)
    if erros:
        for e in erros:
            sys.stderr.write(f"[validar_topicos][erro] {e}\n")
        sys.stderr.write(
            f"[validar_topicos] {len(erros)} erro(s) em {total} tópico(s) de {topicos_dir}.\n"
        )
        return 1

    print(f"[validar_topicos] {total} topicos validados em {topicos_dir}/. Zero erros.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
