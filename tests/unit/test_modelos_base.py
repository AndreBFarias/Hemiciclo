"""Testes do treino do modelo base v1 (S28).

Embeddings sao sempre mockados (vetores aleatorios fixos via numpy seed).
DuckDB usa banco em memoria com schema real para amostragem realistica.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import duckdb
import numpy as np
import pytest

from hemiciclo.config import Configuracao
from hemiciclo.etl.migrations import aplicar_migrations
from hemiciclo.modelos.base import (
    ModeloBaseV1,
    amostrar_estratificadamente,
    treinar_base_v1,
)
from hemiciclo.modelos.embeddings import WrapperEmbeddings


def _conn_com_discursos(n: int) -> duckdb.DuckDBPyConnection:
    """Cria DuckDB em memoria com ``n`` discursos sinteticos."""
    conn = duckdb.connect(":memory:")
    aplicar_migrations(conn)
    rng = np.random.default_rng(seed=42)
    for i in range(n):
        casa = "camara" if i % 2 == 0 else "senado"
        partido = "PT" if rng.random() < 0.5 else "PL"
        conteudo = f"discurso sintetico {i} sobre tema {partido} casa {casa}"
        conn.execute(
            "INSERT INTO discursos (hash_conteudo, parlamentar_id, casa, conteudo) "
            "VALUES (?, ?, ?, ?)",
            [f"h{i:08d}", i, casa, conteudo],
        )
    return conn


def _wrapper_mockado(dim: int = 1024) -> WrapperEmbeddings:
    """Wrapper falso que devolve vetores aleatorios deterministicos."""
    rng = np.random.default_rng(seed=123)

    def _embed_fake(textos: list[str]) -> np.ndarray:
        return rng.standard_normal((len(textos), dim)).astype(np.float64)

    wrapper = MagicMock(spec=WrapperEmbeddings)
    wrapper.embed.side_effect = _embed_fake
    return wrapper


def test_modelobasev1_pca_random_state_fixo(tmp_hemiciclo_home: Path) -> None:
    """O PCA dentro do modelo recebe ``random_state`` da Configuracao (I3)."""
    conn = _conn_com_discursos(80)
    try:
        wrapper = _wrapper_mockado()
        modelo = treinar_base_v1(conn, wrapper, n_amostra=80, n_componentes=10)
    finally:
        conn.close()

    assert isinstance(modelo, ModeloBaseV1)
    assert modelo.pca.random_state == Configuracao().random_state == 42


def test_amostrar_estratificadamente_respeita_n() -> None:
    """``USING SAMPLE n ROWS`` retorna no maximo ``n`` linhas."""
    conn = _conn_com_discursos(100)
    try:
        df = amostrar_estratificadamente(conn, n_amostra=20)
        assert len(df) == 20
        assert set(df.columns) == {"hash_conteudo", "conteudo", "parlamentar_id", "casa"}
    finally:
        conn.close()


def test_amostrar_seed_42_deterministico() -> None:
    """Duas chamadas seguidas com REPEATABLE (42) retornam a mesma amostra."""
    conn = _conn_com_discursos(200)
    try:
        df1 = amostrar_estratificadamente(conn, n_amostra=50)
        df2 = amostrar_estratificadamente(conn, n_amostra=50)
    finally:
        conn.close()
    assert df1["hash_conteudo"].to_list() == df2["hash_conteudo"].to_list()


def test_treinar_base_v1_completa_sem_erro(tmp_hemiciclo_home: Path) -> None:
    """Treino end-to-end com mock completa sem erro e produz feature_names corretos."""
    conn = _conn_com_discursos(60)
    try:
        wrapper = _wrapper_mockado()
        modelo = treinar_base_v1(conn, wrapper, n_amostra=60, n_componentes=8)
    finally:
        conn.close()

    assert modelo.feature_names == [f"pc_{i}" for i in range(8)]
    assert modelo.versao == "1"
    assert modelo.hash_amostra != ""
    # bge-m3 mock recebeu 60 textos.
    assert wrapper.embed.call_count == 1


def test_treinar_base_v1_n_componentes_aplicado(tmp_hemiciclo_home: Path) -> None:
    """O PCA tem o numero de componentes solicitado."""
    conn = _conn_com_discursos(100)
    try:
        wrapper = _wrapper_mockado()
        modelo = treinar_base_v1(conn, wrapper, n_amostra=100, n_componentes=15)
    finally:
        conn.close()
    assert modelo.n_componentes == 15
    assert modelo.pca.n_components_ == 15


def test_modelo_transform_e_idempotente(tmp_hemiciclo_home: Path) -> None:
    """``transform`` chamado duas vezes sobre mesma entrada retorna o mesmo output."""
    conn = _conn_com_discursos(60)
    try:
        wrapper = _wrapper_mockado()
        modelo = treinar_base_v1(conn, wrapper, n_amostra=60, n_componentes=8)
    finally:
        conn.close()

    rng = np.random.default_rng(seed=7)
    X = rng.standard_normal((5, 1024))
    out1 = modelo.transform(X)
    out2 = modelo.transform(X)
    assert out1.shape == (5, 8)
    np.testing.assert_array_equal(out1, out2)


def test_treinar_base_v1_amostra_vazia_falha(tmp_hemiciclo_home: Path) -> None:
    """Tabela vazia deve falhar com mensagem clara antes de chamar embed."""
    conn = duckdb.connect(":memory:")
    aplicar_migrations(conn)
    try:
        wrapper = _wrapper_mockado()
        with pytest.raises(ValueError, match="Amostra vazia"):
            treinar_base_v1(conn, wrapper, n_amostra=10, n_componentes=5)
    finally:
        conn.close()


def test_amostrar_tabela_inexistente_retorna_vazio(tmp_hemiciclo_home: Path) -> None:
    """Tabela inexistente nao quebra; retorna DataFrame vazio com schema."""
    conn = duckdb.connect(":memory:")
    try:
        df = amostrar_estratificadamente(conn, n_amostra=10)
        assert len(df) == 0
        assert set(df.columns) == {"hash_conteudo", "conteudo", "parlamentar_id", "casa"}
    finally:
        conn.close()
