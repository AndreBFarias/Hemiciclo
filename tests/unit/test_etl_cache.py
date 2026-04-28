"""Testes do cache transversal por hash SHA256 (S26)."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from hemiciclo.etl.cache import (
    caminho_cache_discurso,
    caminho_cache_proposicao,
    carregar_cache,
    existe_no_cache,
    salvar_cache,
)


def test_caminho_cache_discurso_usa_hash(tmp_path: Path) -> None:
    """O path canônico de discurso é ``<home>/cache/discursos/<hash>.parquet``."""
    h = "abc123def4567890"  # 16 chars (S24/S25)
    p = caminho_cache_discurso(tmp_path, h)
    # Compara com forward-slash normalizado para resistir a Windows (lição S23).
    assert p.as_posix().endswith(f"cache/discursos/{h}.parquet")
    assert p.parent.name == "discursos"


def test_caminho_cache_proposicao_usa_id_completo(tmp_path: Path) -> None:
    """O path canônico de proposição usa identificador composto ``<casa>-<id>``."""
    p = caminho_cache_proposicao(tmp_path, "camara-12345")
    assert p.as_posix().endswith("cache/proposicoes/camara-12345.parquet")
    assert p.parent.name == "proposicoes"


def test_salvar_cache_escrita_atomica(tmp_path: Path) -> None:
    """Após ``salvar_cache``, não restam arquivos ``.tmp`` órfãos no diretório."""
    df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    destino = tmp_path / "cache" / "discursos" / "deadbeef.parquet"
    salvar_cache(df, destino)
    assert destino.exists()
    arquivos_tmp = list(destino.parent.glob("*.tmp"))
    assert arquivos_tmp == []


def test_carregar_cache_inexistente_retorna_none(tmp_path: Path) -> None:
    """Caminho ausente retorna ``None`` (não levanta exceção)."""
    p = tmp_path / "nada.parquet"
    assert carregar_cache(p) is None


def test_round_trip_dataframe_polars(tmp_path: Path) -> None:
    """Escrever e ler de volta preserva linhas e colunas."""
    df = pl.DataFrame(
        {"id": [1, 2, 3], "nome": ["alice", "bob", "carol"], "valor": [1.5, 2.5, 3.5]}
    )
    destino = tmp_path / "cache" / "discursos" / "deadbeef.parquet"
    salvar_cache(df, destino)
    carregado = carregar_cache(destino)
    assert carregado is not None
    assert carregado.height == df.height
    assert carregado.columns == df.columns
    assert carregado["id"].to_list() == [1, 2, 3]
    assert carregado["nome"].to_list() == ["alice", "bob", "carol"]


def test_existe_no_cache_detecta_arquivo(tmp_path: Path) -> None:
    """``existe_no_cache`` é ``False`` antes e ``True`` depois de salvar."""
    df = pl.DataFrame({"a": [1]})
    destino = tmp_path / "cache" / "x.parquet"
    assert existe_no_cache(destino) is False
    salvar_cache(df, destino)
    assert existe_no_cache(destino) is True
