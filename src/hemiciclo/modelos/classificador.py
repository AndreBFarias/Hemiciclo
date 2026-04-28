"""Orquestrador do classificador multicamada (S27, ADR-011 -- D11).

Costura C1 e C2 (esta sprint), reservando ganchos para C3 (S28) e C4
(S34b). API pública:

- :func:`classificar` -- ponto de entrada principal usado pela CLI e por
  outras camadas (Sessão de Pesquisa em S29+).

Persistência: o resultado é serializado em
``<home>/cache/classificacoes/<topico>_<hash_db>.parquet`` (lição S26 de
cache transversal por hash). O dict retornado é compatível com
serialização JSON para a flag ``--output`` da CLI.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb
import polars as pl
from loguru import logger

from hemiciclo.config import Configuracao
from hemiciclo.etl.migrations import aplicar_migrations
from hemiciclo.etl.topicos import carregar_topico
from hemiciclo.modelos.classificador_c1 import (
    agregar_voto_por_parlamentar,
    proposicoes_relevantes,
)
from hemiciclo.modelos.classificador_c2 import tfidf_relevancia

CAMADAS_VALIDAS = {"regex", "votos", "tfidf"}
"""Camadas que esta sprint suporta. C3 ('embeddings') e C4 ('llm') são
adicionadas em sprints posteriores -- recusar aqui torna o erro óbvio."""

_CACHE_SUBDIR = "classificacoes"


def _hash_db(db_path: Path) -> str:
    """Hash curto (16 chars) do path absoluto + mtime do DB.

    Não lê conteúdo; o objetivo é deduplicar runs do mesmo DB via cache.
    """
    chave = f"{db_path.resolve()}::{db_path.stat().st_mtime if db_path.exists() else 0}"
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()[:16]


def _path_cache(topico_nome: str, db_path: Path, home: Path) -> Path:
    return home / "cache" / _CACHE_SUBDIR / f"{topico_nome}_{_hash_db(db_path)}.parquet"


def classificar(
    topico_yaml: Path,
    db_path: Path,
    camadas: list[str] | None = None,
    top_n: int = 100,
    home: Path | None = None,
    parlamentares_subset: set[tuple[int, str]] | None = None,
) -> dict[str, Any]:
    """Classifica um tópico contra um DuckDB unificado (S26).

    Args:
        topico_yaml: Caminho do YAML do tópico.
        db_path: DuckDB analítico (criado por ``hemiciclo db init``).
        camadas: Subconjunto de :data:`CAMADAS_VALIDAS`. Default: todas.
        top_n: Tamanho dos rankings ``top_a_favor`` / ``top_contra``.
        home: Override do diretório raiz do Hemiciclo (testes).
        parlamentares_subset: Filtro opcional (S30.2) com pares
            ``(parlamentar_id, casa)`` aceitos. ``None`` (default) =
            comportamento legado, todos os parlamentares. Set vazio =
            recorte casou ninguém, agregação retorna vazio.

    Returns:
        Dict com ``topico``, ``versao_topico``, ``camadas``,
        ``hash_db``, ``n_props``, ``n_parlamentares``, ``top_a_favor``,
        ``top_contra``, ``cache_parquet`` (path absoluto). Quando
        ``parlamentares_subset`` é informado, inclui também
        ``n_parlamentares_subset`` (tamanho do recorte aplicado).
    """
    cfg = Configuracao(home=home) if home is not None else Configuracao()
    cfg.garantir_diretorios()

    if camadas is None:
        camadas_efetivas: set[str] = set(CAMADAS_VALIDAS)
    else:
        invalidas = set(camadas) - CAMADAS_VALIDAS
        if invalidas:
            raise ValueError(
                f"camadas invalidas: {sorted(invalidas)} -- validas: {sorted(CAMADAS_VALIDAS)}"
            )
        camadas_efetivas = set(camadas)

    topico = carregar_topico(topico_yaml)

    if not db_path.exists():
        raise FileNotFoundError(f"DB inexistente: {db_path}")

    conn = duckdb.connect(str(db_path))
    try:
        aplicar_migrations(conn)

        # Camada 1 -- proposições relevantes (sempre roda; é o filtro base).
        if "regex" in camadas_efetivas:
            df_props = proposicoes_relevantes(topico, conn)
        else:
            df_props = pl.DataFrame()

        # TF-IDF refinement -- só quando há props.
        if "tfidf" in camadas_efetivas and len(df_props) > 0:
            df_props = tfidf_relevancia(df_props)

        # Agregação de voto. Quando ``parlamentares_subset`` é informado
        # (S30.2), restringe o JOIN ao recorte; ``set()`` curto-circuita
        # para ``schema_vazio``.
        if "votos" in camadas_efetivas and len(df_props) > 0:
            df_agg = agregar_voto_por_parlamentar(
                df_props, conn, parlamentares_subset=parlamentares_subset
            )
        else:
            df_agg = pl.DataFrame()

        n_props = int(len(df_props))
        n_parlamentares = int(len(df_agg))

        if n_parlamentares > 0:
            df_a_favor = (
                df_agg.filter(pl.col("posicao_agregada") == "A_FAVOR")
                .sort("proporcao_sim", descending=True)
                .head(top_n)
            )
            df_contra = (
                df_agg.filter(pl.col("posicao_agregada") == "CONTRA")
                .sort("proporcao_sim", descending=False)
                .head(top_n)
            )
            top_a_favor = df_a_favor.to_dicts()
            top_contra = df_contra.to_dicts()
        else:
            top_a_favor = []
            top_contra = []

        # Persistência do DataFrame de proposições relevantes em parquet
        # (cache leve; agrega DF por parlamentar fica em memória/JSON).
        cache_path = _path_cache(topico.nome, db_path, cfg.home)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        if len(df_props) > 0:
            df_props.write_parquet(cache_path)
        else:
            # Cria parquet vazio com schema mínimo para auditoria
            pl.DataFrame(schema={"id": pl.Int64, "casa": pl.Utf8, "ementa": pl.Utf8}).write_parquet(
                cache_path
            )

        resultado: dict[str, Any] = {
            "topico": topico.nome,
            "versao_topico": topico.versao,
            "camadas": sorted(camadas_efetivas),
            "hash_db": _hash_db(db_path),
            "n_props": n_props,
            "n_parlamentares": n_parlamentares,
            "n_parlamentares_subset": (
                len(parlamentares_subset) if parlamentares_subset is not None else None
            ),
            "top_a_favor": top_a_favor,
            "top_contra": top_contra,
            "cache_parquet": str(cache_path),
        }
        logger.info(
            "[classificar][{t}] {n} props, {p} parlamentares (camadas={c})",
            t=topico.nome,
            n=n_props,
            p=n_parlamentares,
            c=sorted(camadas_efetivas),
        )
        return resultado
    finally:
        conn.close()


def salvar_resultado_json(resultado: dict[str, Any], destino: Path) -> None:
    """Serializa o dict de :func:`classificar` em JSON UTF-8 com indent=2."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
