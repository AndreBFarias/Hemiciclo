#!/usr/bin/env python3
"""Validador de ADRs (Architecture Decision Records) no formato MADR adaptado.

Usado pelo workflow .github/workflows/adr-check.yml e localmente via CLI.

Regras estruturais (erro -> exit 1):
- Filename deve casar `ADR-NNN-titulo-com-hifens.md` (NNN com 3 digitos, titulo ASCII).
- Cabecalho deve ter `# ADR-NNN -- titulo`.
- Metadados obrigatorios: `**Status:**`, `**Data:**`, `**Decisores:**`, `**Tags:**`.
- Secoes obrigatorias: `## Contexto` (prefixo, aceita "## Contexto e problema"),
  `## Decisao` (com ou sem acento), `## Consequencias` (com ou sem acento).
- O `docs/adr/README.md` deve listar todos os ADRs presentes no diretório.

Regras não-fatais (warning):
- Numeracao com buracos (ex: ADR-001, ADR-003 sem ADR-002).

Saidas:
- Exit 0: OK, mensagem `[validar_adr] N ADRs validados em <dir>. Zero erros.`
- Exit 1: erros, lista descritiva e exit code != 0.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

FILENAME_RE = re.compile(r"^ADR-(\d{3})-([a-z0-9-]+)\.md$")
HEADER_RE = re.compile(r"^#\s+ADR-(\d{3})\s+--\s+(.+?)\s*$", re.MULTILINE)
META_RE = re.compile(
    r"^-\s+\*\*(?P<chave>[^:]+):\*\*\s*(?P<valor>.+?)\s*$",
    re.MULTILINE,
)
SECAO_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
README_LINK_RE = re.compile(r"\[ADR-(\d{3})\]")

CAMPOS_OBRIGATORIOS = ("Status", "Data", "Decisores", "Tags")
SECOES_OBRIGATORIAS_NORMALIZADAS = ("contexto", "decisao", "consequencias")


@dataclass
class ADRParseado:
    """Resultado da analise de um arquivo ADR."""

    path: Path
    numero: int
    titulo: str
    metadados: dict[str, str]
    secoes: list[str]


def _normaliza(texto: str) -> str:
    """Remove acentos e baixa caixa para comparacao tolerante."""
    forma_nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in forma_nfkd if not unicodedata.combining(c))
    return sem_acento.lower().strip()


def parse_adr(path: Path) -> tuple[ADRParseado | None, list[str]]:
    """Le um arquivo ADR e devolve estrutura parseada + lista de erros estruturais."""
    erros: list[str] = []
    nome = path.name

    casamento_filename = FILENAME_RE.match(nome)
    if casamento_filename is None:
        erros.append(
            f"{nome}: filename não casa padrao 'ADR-NNN-titulo-ascii.md'"
        )
        return None, erros

    numero_filename = int(casamento_filename.group(1))
    conteudo = path.read_text(encoding="utf-8")

    casamento_header = HEADER_RE.search(conteudo)
    if casamento_header is None:
        erros.append(
            f"{nome}: cabecalho não casa '# ADR-NNN -- titulo'"
        )
        return None, erros

    numero_header = int(casamento_header.group(1))
    titulo = casamento_header.group(2).strip()

    if numero_header != numero_filename:
        erros.append(
            f"{nome}: numero do filename ({numero_filename:03d}) "
            f"diverge do numero do cabecalho ({numero_header:03d})"
        )

    metadados = {
        casamento.group("chave").strip(): casamento.group("valor").strip()
        for casamento in META_RE.finditer(conteudo)
    }

    secoes = [casamento.group(1).strip() for casamento in SECAO_RE.finditer(conteudo)]

    parseado = ADRParseado(
        path=path,
        numero=numero_filename,
        titulo=titulo,
        metadados=metadados,
        secoes=secoes,
    )
    return parseado, erros


def validar_adr(parseado: ADRParseado) -> list[str]:
    """Valida estrutura do ADR. Retorna lista de erros (vazia se OK)."""
    erros: list[str] = []
    nome = parseado.path.name

    for campo in CAMPOS_OBRIGATORIOS:
        if campo not in parseado.metadados:
            erros.append(f"{nome}: metadado obrigatorio ausente: '**{campo}:**'")
        elif not parseado.metadados[campo]:
            erros.append(f"{nome}: metadado '**{campo}:**' presente mas vazio")

    secoes_normalizadas = [_normaliza(s) for s in parseado.secoes]

    for esperada in SECOES_OBRIGATORIAS_NORMALIZADAS:
        encontrada = any(s.startswith(esperada) for s in secoes_normalizadas)
        if not encontrada:
            erros.append(
                f"{nome}: secao obrigatoria ausente (procurando por "
                f"prefixo '## {esperada}' ignorando acento/caixa)"
            )

    return erros


def validar_diretorio(adr_dir: Path) -> tuple[list[str], list[str]]:
    """Valida todos os ADRs de um diretório.

    Retorna (erros, warnings). Erros bloqueiam (exit 1); warnings não.
    """
    erros: list[str] = []
    warnings: list[str] = []

    if not adr_dir.exists():
        erros.append(f"diretório inexistente: {adr_dir}")
        return erros, warnings

    arquivos_adr = sorted(adr_dir.glob("ADR-*.md"))
    parseados: list[ADRParseado] = []

    for arquivo in arquivos_adr:
        parseado, erros_parse = parse_adr(arquivo)
        erros.extend(erros_parse)
        if parseado is not None:
            erros.extend(validar_adr(parseado))
            parseados.append(parseado)

    if parseados:
        numeros = sorted({p.numero for p in parseados})
        esperados = list(range(numeros[0], numeros[-1] + 1))
        faltantes = sorted(set(esperados) - set(numeros))
        if faltantes:
            warnings.append(
                "numeracao com buracos: faltam "
                + ", ".join(f"ADR-{n:03d}" for n in faltantes)
            )

        vistos: dict[int, Path] = {}
        for p in parseados:
            if p.numero in vistos:
                erros.append(
                    f"numero duplicado ADR-{p.numero:03d}: "
                    f"{vistos[p.numero].name} e {p.path.name}"
                )
            else:
                vistos[p.numero] = p.path

    readme = adr_dir / "README.md"
    if readme.exists() and parseados:
        texto_readme = readme.read_text(encoding="utf-8")
        listados = {int(m.group(1)) for m in README_LINK_RE.finditer(texto_readme)}
        presentes = {p.numero for p in parseados}
        nao_listados = sorted(presentes - listados)
        if nao_listados:
            erros.append(
                f"{readme.name}: ADRs presentes no diretório mas ausentes do indice: "
                + ", ".join(f"ADR-{n:03d}" for n in nao_listados)
            )

    return erros, warnings


def main(argv: list[str] | None = None) -> int:
    """Entry point CLI. Retorna 0 (OK) ou 1 (erro)."""
    if argv is None:
        argv = sys.argv[1:]

    if argv:
        adr_dir = Path(argv[0])
    else:
        raiz = Path(__file__).resolve().parent.parent
        adr_dir = raiz / "docs" / "adr"

    erros, warnings = validar_diretorio(adr_dir)
    arquivos = sorted(adr_dir.glob("ADR-*.md")) if adr_dir.exists() else []
    total = len(arquivos)

    for w in warnings:
        sys.stderr.write(f"[validar_adr][warning] {w}\n")

    if erros:
        for e in erros:
            sys.stderr.write(f"[validar_adr][erro] {e}\n")
        sys.stderr.write(
            f"[validar_adr] {len(erros)} erro(s) em {total} ADR(s) de {adr_dir}.\n"
        )
        return 1

    print(f"[validar_adr] {total} ADRs validados em {adr_dir}/. Zero erros.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
