"""Carregador runtime de tópicos YAML (S27).

Lê arquivos `topicos/<slug>.yaml`, valida contra `topicos/_schema.yaml` via
``jsonschema``, compila os padrões regex (``re.compile``) e devolve um
modelo ``Topico`` Pydantic v2 imutável.

API pública:

- :class:`Topico` -- modelo do tópico carregado.
- :class:`ProposicaoSeed` -- entrada de ``proposicoes_seed``.
- :class:`Exclusao` -- entrada de ``exclusoes``.
- :func:`carregar_topico` -- lê, valida e devolve um ``Topico``.
- :func:`listar_topicos` -- carrega todos os tópicos de um diretório.

Helpers de matching ficam em ``Topico.casa_keywords()`` e
``Topico.casa_categoria_oficial()``: o classificador consome esses métodos
em vez de duplicar lógica de regex/ILIKE.

Decisão (ADR-003): match por keyword é case-insensitive simples
(``str.lower in str.lower``); match por regex é o que está no YAML
(usuário deve usar ``(?i)`` quando quiser ignorar caixa).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from pydantic import BaseModel, ConfigDict, Field, field_validator

NOME_SCHEMA = "_schema.yaml"


class ProposicaoSeed(BaseModel):
    """Proposição-âncora declarada em ``proposicoes_seed``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sigla: str
    numero: int
    ano: int
    casa: str
    posicao_implicita: str | None = None


class Exclusao(BaseModel):
    """Padrão regex que desclassifica falsos positivos."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    regex: str
    motivo: str | None = None


class Topico(BaseModel):
    """Tópico carregado a partir de um YAML.

    Atributos espelham o JSON Schema em ``topicos/_schema.yaml``. Os
    padrões regex já vêm pré-compilados em :attr:`regex_compilados`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    nome: str = Field(pattern=r"^[a-z0-9_]+$", min_length=2, max_length=60)
    versao: int = Field(ge=1)
    descricao_curta: str = Field(min_length=10, max_length=280)
    keywords: tuple[str, ...]
    regex: tuple[str, ...]
    mantenedor: str | None = None
    categorias_oficiais_camara: tuple[str, ...] = ()
    categorias_oficiais_senado: tuple[str, ...] = ()
    proposicoes_seed: tuple[ProposicaoSeed, ...] = ()
    exclusoes: tuple[Exclusao, ...] = ()
    embeddings_seed: tuple[str, ...] = ()
    limiar_similaridade: float | None = None

    @field_validator("regex")
    @classmethod
    def _valida_regex(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for i, padrao in enumerate(v):
            try:
                re.compile(padrao)
            except re.error as exc:
                raise ValueError(f"regex[{i}] inválida: {exc} -- padrão {padrao!r}") from exc
        return v

    @property
    def regex_compilados(self) -> tuple[re.Pattern[str], ...]:
        """Lista pré-compilada dos padrões em :attr:`regex`."""
        return tuple(re.compile(p) for p in self.regex)

    @property
    def exclusoes_compiladas(self) -> tuple[re.Pattern[str], ...]:
        """Lista pré-compilada dos padrões em :attr:`exclusoes`."""
        return tuple(re.compile(e.regex) for e in self.exclusoes)

    def casa_keywords(self, ementa: str) -> bool:
        """Retorna True se a ementa casar alguma keyword OU algum regex.

        Match de keyword é case-insensitive simples (``in`` após ``lower()``).
        Match de regex usa o padrão como veio do YAML (usuário controla
        case-insensitivity via ``(?i)``).

        Exclusões são aplicadas primeiro: se alguma exclusão casar, o
        método já retorna False.
        """
        if not ementa:
            return False
        baixa = ementa.lower()
        for excl in self.exclusoes_compiladas:
            if excl.search(ementa):
                return False
        for kw in self.keywords:
            if kw.lower() in baixa:
                return True
        return any(padrao.search(ementa) for padrao in self.regex_compilados)

    def casa_categoria_oficial(self, tema_oficial: str | None, casa: str) -> bool:
        """Retorna True se ``tema_oficial`` está nas categorias da ``casa``.

        ``casa`` deve ser ``"camara"`` ou ``"senado"``; outros valores
        retornam False sem erro.
        """
        if not tema_oficial:
            return False
        if casa == "camara":
            return tema_oficial in self.categorias_oficiais_camara
        if casa == "senado":
            return tema_oficial in self.categorias_oficiais_senado
        return False


def _carregar_schema(schema_path: Path) -> dict[str, Any]:
    if not schema_path.exists():
        raise FileNotFoundError(f"schema ausente: {schema_path}")
    with schema_path.open(encoding="utf-8") as f:
        bruto = yaml.safe_load(f)
    if not isinstance(bruto, dict):
        raise ValueError(f"{schema_path.name}: raiz deve ser mapa YAML")
    Draft202012Validator.check_schema(bruto)
    return bruto


def carregar_topico(path: Path, schema_path: Path | None = None) -> Topico:
    """Carrega um tópico de ``path``.

    Args:
        path: Arquivo `<slug>.yaml`.
        schema_path: Caminho para `_schema.yaml`. Default: irmão de ``path``.

    Returns:
        Modelo :class:`Topico` validado e com regex já compiláveis.

    Raises:
        FileNotFoundError: Arquivo ou schema ausente.
        ValueError: Estrutura inválida segundo o schema.
    """
    if not path.exists():
        raise FileNotFoundError(f"tópico inexistente: {path}")
    schema_real = schema_path if schema_path is not None else path.parent / NOME_SCHEMA
    schema = _carregar_schema(schema_real)

    with path.open(encoding="utf-8") as f:
        dados = yaml.safe_load(f)
    if not isinstance(dados, dict):
        raise ValueError(f"{path.name}: raiz deve ser mapa YAML")

    validator = Draft202012Validator(schema)
    erros: list[ValidationError] = sorted(
        validator.iter_errors(dados), key=lambda e: list(e.absolute_path)
    )
    if erros:
        msgs = "; ".join(
            f"{('/'.join(str(p) for p in e.absolute_path) or '(raiz)')}: {e.message}" for e in erros
        )
        raise ValueError(f"{path.name}: schema inválido -- {msgs}")

    return Topico.model_validate(dados)


def listar_topicos(diretorio: Path) -> dict[str, Topico]:
    """Carrega todos os tópicos de ``diretorio``, exceto ``_schema.yaml``.

    Args:
        diretorio: Pasta com `*.yaml`.

    Returns:
        Mapa ``{nome: Topico}`` ordenado pelo nome.
    """
    if not diretorio.exists():
        raise FileNotFoundError(f"diretório inexistente: {diretorio}")
    schema_path = diretorio / NOME_SCHEMA
    arquivos = sorted(p for p in diretorio.glob("*.yaml") if p.name != NOME_SCHEMA)
    saida: dict[str, Topico] = {}
    for arq in arquivos:
        topico = carregar_topico(arq, schema_path=schema_path)
        saida[topico.nome] = topico
    return saida
