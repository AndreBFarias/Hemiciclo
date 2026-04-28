"""Checkpoint persistente da coleta (Câmara e Senado), com escrita atômica.

A coleta longa (legislaturas 55-57, ~2.5M itens estimados) precisa
sobreviver a quedas de internet, ``kill -9``, máquina dormindo e
fechamento de browser. Sem checkpoint resumível o projeto é inviável.

Modelo:

- :class:`CheckpointCamara` -- Pydantic v2 com sets de IDs por tipo.
- :class:`CheckpointSenado` -- análogo, parametrizado por ano (não legislatura)
  e com IDs de matéria/votação/senador no formato Senado.
- :func:`hash_params` / :func:`hash_params_senado` -- determinísticos, ordem
  de listas é normalizada.
- :func:`salvar_checkpoint` / :func:`salvar_checkpoint_senado` --
  ``tempfile + Path.replace`` (atômico em POSIX).
- :func:`carregar_checkpoint` / :func:`carregar_checkpoint_senado` --
  reidratam sets a partir de listas e tuples a partir de pares.

Cobre I3 (determinismo via sort de listas), I6 (Pydantic estrito),
I7 (tipagem precisa, sem ``Any``).
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class CheckpointCamara(BaseModel):
    """Estado persistente da coleta da Câmara.

    Cada coleção é um ``set`` para idempotência: relançar após ``kill -9``
    nunca rebaixa um item já marcado como completo.

    - ``proposicoes_baixadas`` -- IDs únicos da Câmara.
    - ``proposicoes_enriquecidas`` -- IDs já detalhados via ``GET /proposicoes/{id}`` (S24b).
    - ``votacoes_baixadas`` -- IDs string da Câmara.
    - ``votos_baixados`` -- pares ``(votacao_id, deputado_id)``.
    - ``discursos_baixados`` -- hash sha256 do conteúdo (RTF decodificado).
    - ``deputados_baixados`` -- IDs únicos da Câmara.
    - ``erros`` -- lista de eventos ``{url, codigo, mensagem, timestamp}``.
    """

    iniciado_em: datetime
    atualizado_em: datetime
    legislaturas: list[int]
    tipos: list[str]
    proposicoes_baixadas: set[int] = Field(default_factory=set)
    proposicoes_enriquecidas: set[int] = Field(default_factory=set)
    votacoes_baixadas: set[str] = Field(default_factory=set)
    votos_baixados: set[tuple[str, int]] = Field(default_factory=set)
    discursos_baixados: set[str] = Field(default_factory=set)
    deputados_baixados: set[int] = Field(default_factory=set)
    anos_concluidos: set[tuple[int, int]] = Field(default_factory=set)
    """Pares ``(legislatura, ano)`` cuja iteração de páginas terminou sem
    interrupção (introduzido em S24c). Permite retomada granular por ano
    quando ``coletar_proposicoes`` itera os 4 anos da legislatura."""
    erros: list[dict[str, Any]] = Field(default_factory=list)

    def total_baixado(self) -> int:
        """Soma de todos os IDs baixados (qualquer tipo)."""
        return (
            len(self.proposicoes_baixadas)
            + len(self.proposicoes_enriquecidas)
            + len(self.votacoes_baixadas)
            + len(self.votos_baixados)
            + len(self.discursos_baixados)
            + len(self.deputados_baixados)
        )


def hash_params(legislaturas: list[int], tipos: list[str]) -> str:
    """Hash determinístico dos parâmetros de coleta.

    Ordem das listas é irrelevante: ``[55, 56]`` produz o mesmo hash que
    ``[56, 55]``. Útil para localizar checkpoint correspondente entre
    relançamentos.

    Returns:
        Primeiros 16 chars do sha256 hex (suficiente para evitar colisão
        entre poucas dezenas de combinações de coleta).
    """
    base = f"{sorted(legislaturas)}-{sorted(tipos)}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def caminho_checkpoint(home: Path, hash_params_str: str) -> Path:
    """Resolve o caminho canônico do checkpoint.

    Args:
        home: Diretório raiz do Hemiciclo (ex.: ``~/hemiciclo``).
        hash_params_str: Resultado de :func:`hash_params`.

    Returns:
        ``<home>/cache/checkpoints/camara_<hash>.json``
    """
    return home / "cache" / "checkpoints" / f"camara_{hash_params_str}.json"


def _normaliza_para_json(cp: CheckpointCamara) -> dict[str, Any]:
    """Converte o checkpoint em dict JSON-serializável e determinístico.

    Sets viram listas ordenadas; tuples viram listas para travessar JSON
    sem ambiguidade. ``datetime`` vira ISO 8601.
    """
    dados = cp.model_dump(mode="json")
    dados["proposicoes_baixadas"] = sorted(cp.proposicoes_baixadas)
    dados["proposicoes_enriquecidas"] = sorted(cp.proposicoes_enriquecidas)
    dados["votacoes_baixadas"] = sorted(cp.votacoes_baixadas)
    dados["votos_baixados"] = sorted(
        ([v[0], v[1]] for v in cp.votos_baixados),
        key=lambda par: (par[0], par[1]),
    )
    dados["discursos_baixados"] = sorted(cp.discursos_baixados)
    dados["deputados_baixados"] = sorted(cp.deputados_baixados)
    dados["anos_concluidos"] = sorted(
        ([par[0], par[1]] for par in cp.anos_concluidos),
        key=lambda par: (par[0], par[1]),
    )
    return dados


def salvar_checkpoint(cp: CheckpointCamara, path: Path) -> None:
    """Persiste o checkpoint via escrita atômica.

    Algoritmo:

    1. Escreve em ``<path>.tmp`` (mesmo diretório, mesma partição).
    2. ``Path.replace`` -- atômico em POSIX (``rename`` syscall).

    Sobrevive a ``kill -9`` no meio: ou o arquivo final foi escrito
    inteiro, ou ainda contém a versão anterior.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    dados = _normaliza_para_json(cp)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        suffix=".tmp",
    ) as tmp:
        json.dump(dados, tmp, ensure_ascii=False, indent=2, default=str)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def carregar_checkpoint(path: Path) -> CheckpointCamara | None:
    """Carrega checkpoint de ``path``, ou retorna ``None`` se ausente.

    Reidrata sets a partir de listas e tuples a partir de pares. Aceita
    checkpoints escritos por versões anteriores desde que mantenham o
    schema documentado em :class:`CheckpointCamara`.
    """
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        dados = json.load(f)

    # Reconstrói tuples a partir de listas pares.
    if "votos_baixados" in dados:
        dados["votos_baixados"] = [tuple(v) for v in dados["votos_baixados"]]
    if "anos_concluidos" in dados:
        dados["anos_concluidos"] = [tuple(par) for par in dados["anos_concluidos"]]
    return CheckpointCamara.model_validate(dados)


# ---------------------------------------------------------------------------
# Senado -- replica do padrão acima (S25). Coexiste com CheckpointCamara no
# mesmo diretório ``~/hemiciclo/cache/checkpoints/`` distinto pelo prefixo
# ``senado_<hash>.json`` vs ``camara_<hash>.json``.
# ---------------------------------------------------------------------------


class CheckpointSenado(BaseModel):
    """Estado persistente da coleta do Senado Federal.

    Diferenças de schema vs :class:`CheckpointCamara`:

    - Parametrizado por ``anos`` (mais granular) em vez de legislaturas, mas
      mantém compatibilidade com legislaturas via ``legislaturas`` opcional.
    - ``materias_baixadas`` -- códigos inteiros de matéria do Senado.
    - ``votacoes_baixadas`` -- códigos inteiros de votação no plenário.
    - ``votos_baixados`` -- pares ``(votacao_id, senador_id)`` (ambos int).
    - ``discursos_baixados`` -- hash sha256 do conteúdo, idêntico à Câmara.
    - ``senadores_baixados`` -- códigos inteiros de senador.
    - ``erros`` -- lista de eventos ``{url, codigo, mensagem, timestamp}``.
    """

    iniciado_em: datetime
    atualizado_em: datetime
    legislaturas: list[int] = Field(default_factory=list)
    anos: list[int] = Field(default_factory=list)
    tipos: list[str]
    materias_baixadas: set[int] = Field(default_factory=set)
    votacoes_baixadas: set[int] = Field(default_factory=set)
    votos_baixados: set[tuple[int, int]] = Field(default_factory=set)
    discursos_baixados: set[str] = Field(default_factory=set)
    senadores_baixados: set[int] = Field(default_factory=set)
    erros: list[dict[str, Any]] = Field(default_factory=list)

    def total_baixado(self) -> int:
        """Soma de todos os IDs baixados (qualquer tipo)."""
        return (
            len(self.materias_baixadas)
            + len(self.votacoes_baixadas)
            + len(self.votos_baixados)
            + len(self.discursos_baixados)
            + len(self.senadores_baixados)
        )


def hash_params_senado(anos: list[int], tipos: list[str]) -> str:
    """Hash determinístico dos parâmetros de coleta do Senado.

    Ordem das listas é irrelevante. Distinto de :func:`hash_params` da Câmara
    pelo prefixo ``senado:`` na seed, evitando colisão acidental entre
    checkpoints quando os parâmetros numéricos por acaso coincidem.

    Returns:
        Primeiros 16 chars do sha256 hex.
    """
    base = f"senado:{sorted(anos)}-{sorted(tipos)}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def caminho_checkpoint_senado(home: Path, hash_params_str: str) -> Path:
    """Resolve o caminho canônico do checkpoint do Senado.

    Args:
        home: Diretório raiz do Hemiciclo (ex.: ``~/hemiciclo``).
        hash_params_str: Resultado de :func:`hash_params_senado`.

    Returns:
        ``<home>/cache/checkpoints/senado_<hash>.json``
    """
    return home / "cache" / "checkpoints" / f"senado_{hash_params_str}.json"


def _normaliza_senado_para_json(cp: CheckpointSenado) -> dict[str, Any]:
    """Converte o checkpoint do Senado em dict JSON-serializável determinístico."""
    dados = cp.model_dump(mode="json")
    dados["materias_baixadas"] = sorted(cp.materias_baixadas)
    dados["votacoes_baixadas"] = sorted(cp.votacoes_baixadas)
    dados["votos_baixados"] = sorted(
        ([v[0], v[1]] for v in cp.votos_baixados),
        key=lambda par: (par[0], par[1]),
    )
    dados["discursos_baixados"] = sorted(cp.discursos_baixados)
    dados["senadores_baixados"] = sorted(cp.senadores_baixados)
    return dados


def salvar_checkpoint_senado(cp: CheckpointSenado, path: Path) -> None:
    """Persiste checkpoint do Senado via escrita atômica (mesmo padrão da Câmara)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    dados = _normaliza_senado_para_json(cp)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        suffix=".tmp",
    ) as tmp:
        json.dump(dados, tmp, ensure_ascii=False, indent=2, default=str)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def carregar_checkpoint_senado(path: Path) -> CheckpointSenado | None:
    """Carrega checkpoint do Senado de ``path``, ou retorna ``None`` se ausente."""
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        dados = json.load(f)

    if "votos_baixados" in dados:
        dados["votos_baixados"] = [tuple(v) for v in dados["votos_baixados"]]
    return CheckpointSenado.model_validate(dados)
