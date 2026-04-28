"""Modelo base v1: amostragem estratificada + bge-m3 + PCA (S28, ADR-008).

D8 do plano R2 estabelece **modelo base global + ajuste fino local**:
treinamos uma vez sobre amostra ampla; cada Sessão de Pesquisa pode
``transform`` o seu recorte nos eixos induzidos pelo base. Isso garante
que "Joaquim no eixo 1" significa a mesma coisa em qualquer pesquisa.

Este módulo entrega:

- :class:`ModeloBaseV1` -- dataclass que encapsula o ``PCA`` treinado,
  número de componentes, ``feature_names`` (``pc_0..pc_{N-1}``), versão,
  timestamp e hash da amostra usada (auditável).
- :func:`amostrar_estratificadamente` -- amostra DuckDB via
  ``USING SAMPLE n ROWS REPEATABLE (42)`` (sintaxe DuckDB,
  determinística). Retorna DataFrame Polars com colunas
  ``hash_conteudo, conteudo, parlamentar_id, casa``. Tabela vazia
  retorna DataFrame vazio sem erro (smoke local).
- :func:`treinar_base_v1` -- orquestra amostragem + embed em batches +
  PCA fit com ``random_state=Configuracao().random_state``.

Determinismo (I3): tres pontos garantidos:

1. Amostragem DuckDB com seed fixa (``REPEATABLE (42)``).
2. PCA com ``random_state`` global do projeto.
3. ``hash_amostra`` registra SHA256 dos hashes_conteudo concatenados
   da amostra -- permite auditar reprodutibilidade pos-treino.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import duckdb
import polars as pl
from loguru import logger
from sklearn.decomposition import PCA

from hemiciclo.config import Configuracao
from hemiciclo.modelos.embeddings import WrapperEmbeddings

if TYPE_CHECKING:
    import numpy as np


_COLUNAS_AMOSTRA = ("hash_conteudo", "conteudo", "parlamentar_id", "casa")


@dataclass
class ModeloBaseV1:
    """Snapshot do modelo base v1.

    Atributos sao serializaveis (PCA do sklearn aceita o serializador
    padrao Python via ``joblib``).
    """

    pca: PCA
    n_componentes: int
    feature_names: list[str]
    versao: str = "1"
    treinado_em: datetime = field(default_factory=lambda: datetime.now(UTC))
    hash_amostra: str = ""

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Projeta vetores ``(N, 1024)`` no espaco induzido ``(N, n_componentes)``."""
        import numpy as np  # noqa: PLC0415 -- defensivo (TYPE_CHECKING-only no topo)

        return np.asarray(self.pca.transform(X))


def _tabela_existe(conn: duckdb.DuckDBPyConnection, nome: str) -> bool:
    """Retorna ``True`` se a tabela existe no DuckDB conectado."""
    linha = conn.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        [nome],
    ).fetchone()
    return bool(linha and int(linha[0]) > 0)


def amostrar_estratificadamente(
    conn: duckdb.DuckDBPyConnection, n_amostra: int = 30000
) -> pl.DataFrame:
    """Amostra ``n_amostra`` discursos da tabela ``discursos``.

    Usa ``USING SAMPLE n ROWS REPEATABLE (42)`` (sintaxe DuckDB) para
    determinismo. Quando a tabela não existe ou esta vazia, retorna
    DataFrame vazio com schema esperado -- não e erro fatal (útil em
    smoke local sem coleta).
    """
    schema_vazio = {
        "hash_conteudo": pl.Utf8,
        "conteudo": pl.Utf8,
        "parlamentar_id": pl.Int64,
        "casa": pl.Utf8,
    }
    if not _tabela_existe(conn, "discursos"):
        logger.warning("[modelo_base] tabela 'discursos' inexistente; amostra vazia.")
        return pl.DataFrame(schema=schema_vazio)

    linha_total = conn.execute("SELECT COUNT(*) FROM discursos").fetchone()
    total = int(linha_total[0]) if linha_total else 0
    if total == 0:
        logger.warning("[modelo_base] tabela 'discursos' vazia; amostra vazia.")
        return pl.DataFrame(schema=schema_vazio)

    n_efetivo = min(n_amostra, total)
    colunas = ", ".join(_COLUNAS_AMOSTRA)
    # DuckDB 1.x: ``USING SAMPLE reservoir(N ROWS) REPEATABLE (seed)`` -- a
    # forma sem reservoir não aceita REPEATABLE diretamente. Reservoir e
    # determinismo + amostragem sem reposicao, perfeito para amostra base.
    sql = (
        f"SELECT {colunas} FROM discursos USING SAMPLE reservoir({n_efetivo} ROWS) REPEATABLE (42)"
    )
    return conn.execute(sql).pl()


def _hash_amostra(df: pl.DataFrame) -> str:
    """SHA256 da concatenacao dos ``hash_conteudo`` da amostra (auditável)."""
    if len(df) == 0:
        return hashlib.sha256(b"").hexdigest()
    seed = "\n".join(df["hash_conteudo"].fill_null("").to_list()).encode("utf-8")
    return hashlib.sha256(seed).hexdigest()


def treinar_base_v1(
    conn: duckdb.DuckDBPyConnection,
    embeddings: WrapperEmbeddings,
    n_amostra: int = 30000,
    n_componentes: int = 50,
) -> ModeloBaseV1:
    """Amostra -> embed em batches -> PCA fit -> retorna ``ModeloBaseV1``.

    Args:
        conn: DuckDB com tabela ``discursos`` populada.
        embeddings: Wrapper bge-m3. Em testes deve ser mockado.
        n_amostra: Tamanho da amostra (default 30k -- tradeoff custo/qualidade).
        n_componentes: Dimensoes do espaco induzido. Default 50.
    """
    cfg = Configuracao()
    df = amostrar_estratificadamente(conn, n_amostra)
    if len(df) == 0:
        raise ValueError(
            "Amostra vazia: tabela 'discursos' vazia ou inexistente. "
            "Rode 'hemiciclo coletar' + 'hemiciclo db consolidar' antes de treinar."
        )

    if len(df) < n_componentes:
        raise ValueError(
            f"Amostra com {len(df)} linhas e insuficiente para PCA com "
            f"{n_componentes} componentes. Aumente n_amostra ou reduza n_componentes."
        )

    textos = df["conteudo"].fill_null("").to_list()
    logger.info(
        "[modelo_base] amostragem={n} discursos; iniciando embed bge-m3.",
        n=len(textos),
    )
    matriz = embeddings.embed(textos)
    logger.info(
        "[modelo_base] embed concluido shape={s}; iniciando PCA n_componentes={k}.",
        s=tuple(matriz.shape),
        k=n_componentes,
    )

    pca = PCA(n_components=n_componentes, random_state=cfg.random_state)
    pca.fit(matriz)

    return ModeloBaseV1(
        pca=pca,
        n_componentes=n_componentes,
        feature_names=[f"pc_{i}" for i in range(n_componentes)],
        hash_amostra=_hash_amostra(df),
    )
