"""Cache transversal por hash SHA256 (S26) e por ID estável (S24b).

Conteúdos pesados (discursos com transcrição RTF, proposições com inteiro
teor) são identificados por **hash SHA256 do conteúdo bruto** e armazenados
como Parquet sob ``<home>/cache/<categoria>/<hash>.parquet``.

Vantagem: sessões de pesquisa diferentes que tocam o mesmo conteúdo o
reutilizam sem rebaixar. Sessão A baixa um discurso de aborto; Sessão B
procura "porte de armas" mas o mesmo deputado fala em ambas as
proposições -- discurso já está em cache, é apenas lido.

A camada DuckDB (em :mod:`hemiciclo.etl.schema`) referencia o ``hash_conteudo``
como FK lógica para o Parquet aqui descrito, mantendo o banco analítico
leve (apenas metadados) e a massa textual em arquivos por hash.

Escrita atômica via ``tempfile + Path.replace`` -- mesmo padrão de
:func:`hemiciclo.coleta.checkpoint.salvar_checkpoint` (POSIX rename).

S24b: além do cache em Parquet por hash, esta camada também serve como
cache por **ID estável** para detalhes de proposições (``GET
/proposicoes/{id}``). O payload é dict aninhado pequeno (~3-5KB) e
fica em JSON debugável sob ``<home>/cache/proposicoes/<casa>-<id>.json``.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import polars as pl


def caminho_cache_discurso(home: Path, hash_sha256: str) -> Path:
    """Resolve o path canônico de um discurso em cache.

    Args:
        home: Diretório raiz do Hemiciclo (ex.: ``~/hemiciclo``).
        hash_sha256: Hash SHA256 (16 ou 64 chars hex) do conteúdo do discurso.

    Returns:
        ``<home>/cache/discursos/<hash>.parquet``
    """
    return home / "cache" / "discursos" / f"{hash_sha256}.parquet"


def caminho_cache_proposicao(home: Path, id_completo: str) -> Path:
    """Resolve o path canônico de uma proposição em cache.

    Diferente do discurso, a proposição é identificada pelo seu identificador
    composto (``<casa>-<id>``), não por hash do conteúdo, porque o teor é
    versionado pela API mas o ID é estável.

    Args:
        home: Diretório raiz do Hemiciclo.
        id_completo: Identificador composto canônico (ex.: ``camara-12345``).

    Returns:
        ``<home>/cache/proposicoes/<id_completo>.parquet``
    """
    return home / "cache" / "proposicoes" / f"{id_completo}.parquet"


def salvar_cache(df: pl.DataFrame, path: Path) -> None:
    """Persiste DataFrame Polars em ``path`` via escrita atômica.

    Algoritmo:

    1. Garante que ``path.parent`` existe.
    2. Escreve em ``<path>.tmp`` (mesmo diretório, mesma partição).
    3. ``Path.replace`` -- atômico em POSIX.

    Sobrevive a ``kill -9`` no meio: ou o arquivo final tem versão consistente,
    ou ainda contém a anterior.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    df.write_parquet(tmp_path)
    tmp_path.replace(path)


def carregar_cache(path: Path) -> pl.DataFrame | None:
    """Carrega DataFrame de ``path``, ou retorna ``None`` se ausente.

    Args:
        path: Caminho de cache (resultado de :func:`caminho_cache_discurso`
            ou :func:`caminho_cache_proposicao`).

    Returns:
        DataFrame Polars carregado, ou ``None`` se o arquivo não existe.
    """
    if not path.exists():
        return None
    return pl.read_parquet(path)


def existe_no_cache(path: Path) -> bool:
    """Retorna ``True`` se há cache em ``path``."""
    return path.exists()


def caminho_cache_detalhe_proposicao(home: Path, casa: str, prop_id: int) -> Path:
    """Resolve o path canônico do JSON de detalhe de uma proposição (S24b).

    Args:
        home: Diretório raiz do Hemiciclo (ex.: ``~/hemiciclo``).
        casa: ``"camara"`` ou ``"senado"``.
        prop_id: ID inteiro da proposição na casa de origem.

    Returns:
        ``<home>/cache/proposicoes/<casa>-<prop_id>.json``
    """
    return home / "cache" / "proposicoes" / f"{casa}-{prop_id}.json"


def salvar_cache_detalhe_proposicao(
    payload: dict[str, Any], home: Path, casa: str, prop_id: int
) -> None:
    """Persiste payload bruto de ``GET /proposicoes/{id}`` em JSON atômico (S24b).

    O payload é dict aninhado pequeno; mantemos JSON em vez de Parquet para
    facilitar inspeção manual e portabilidade entre sessões. Escrita
    atômica via ``tempfile + Path.replace`` -- mesmo padrão dos demais
    caches.
    """
    path = caminho_cache_detalhe_proposicao(home, casa, prop_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        suffix=".tmp",
    ) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2, default=str)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def carregar_cache_detalhe_proposicao(home: Path, casa: str, prop_id: int) -> dict[str, Any] | None:
    """Carrega payload bruto do cache de detalhe, ou ``None`` se ausente (S24b).

    Returns:
        Dict aninhado original (formato ``dados`` retornado por
        ``GET /proposicoes/{id}``), ou ``None`` se não há cache local.
    """
    path = caminho_cache_detalhe_proposicao(home, casa, prop_id)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        carregado = json.load(f)
    if not isinstance(carregado, dict):
        return None
    return carregado
