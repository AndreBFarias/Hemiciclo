"""E2E do modelo base v1 (S28).

Cobre o ciclo completo: amostragem -> embed mockado -> PCA -> salvar
-> carregar (com validacao SHA256) -> transform identico ao original.

NUNCA carrega o bge-m3 real. Todos os testes mockam ``WrapperEmbeddings``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import duckdb
import numpy as np

from hemiciclo.etl.migrations import aplicar_migrations
from hemiciclo.modelos.base import treinar_base_v1
from hemiciclo.modelos.embeddings import WrapperEmbeddings
from hemiciclo.modelos.persistencia_modelo import (
    carregar_modelo_base,
    salvar_modelo_base,
)
from hemiciclo.modelos.projecao import projetar_em_base


def _conn_populado(n: int) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:")
    aplicar_migrations(conn)
    for i in range(n):
        conn.execute(
            "INSERT INTO discursos (hash_conteudo, parlamentar_id, casa, conteudo) "
            "VALUES (?, ?, ?, ?)",
            [f"e2e_{i:04d}", i, "camara" if i % 2 == 0 else "senado", f"discurso {i}"],
        )
    return conn


def _wrapper_mockado() -> WrapperEmbeddings:
    rng = np.random.default_rng(seed=2026)

    def _embed_fake(textos: list[str]) -> np.ndarray:
        return rng.standard_normal((len(textos), 1024)).astype(np.float64)

    wrapper = MagicMock(spec=WrapperEmbeddings)
    wrapper.embed.side_effect = _embed_fake
    return wrapper


def test_treinar_persistir_carregar_completo(tmp_path: Path) -> None:
    """Ciclo completo: treinar -> salvar -> carregar -> projetar."""
    conn = _conn_populado(120)
    try:
        wrapper = _wrapper_mockado()
        modelo = treinar_base_v1(conn, wrapper, n_amostra=120, n_componentes=10)
    finally:
        conn.close()

    salvar_modelo_base(modelo, tmp_path)
    carregado = carregar_modelo_base(tmp_path)

    rng = np.random.default_rng(seed=11)
    X_local = rng.standard_normal((4, 1024))

    proj_original = modelo.transform(X_local)
    proj_carregado = projetar_em_base(carregado, X_local)
    np.testing.assert_array_almost_equal(proj_original, proj_carregado)
    assert proj_carregado.shape == (4, 10)


def test_carregar_em_processo_diferente(tmp_path: Path) -> None:
    """Smoke ciclo: carregamento isolado funciona mesmo apos descartar tudo."""
    conn = _conn_populado(80)
    try:
        wrapper = _wrapper_mockado()
        modelo = treinar_base_v1(conn, wrapper, n_amostra=80, n_componentes=8)
        salvar_modelo_base(modelo, tmp_path)
    finally:
        conn.close()

    # Simula "outro processo" descartando referencias e reabrindo do disco.
    del modelo
    del wrapper

    carregado = carregar_modelo_base(tmp_path)
    assert carregado.n_componentes == 8
    assert carregado.versao == "1"
