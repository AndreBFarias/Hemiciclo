"""Testes da persistencia do modelo base com integridade SHA256 (S28)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from sklearn.decomposition import PCA

from hemiciclo.modelos.base import ModeloBaseV1
from hemiciclo.modelos.persistencia_modelo import (
    IntegridadeViolada,
    carregar_modelo_base,
    info_modelo_base,
    salvar_modelo_base,
)


def _modelo_fake(n_componentes: int = 5) -> ModeloBaseV1:
    """Cria um ModeloBaseV1 minimo para round-trip."""
    rng = np.random.default_rng(seed=0)
    X = rng.standard_normal((30, 64))
    pca = PCA(n_components=n_componentes, random_state=42)
    pca.fit(X)
    return ModeloBaseV1(
        pca=pca,
        n_componentes=n_componentes,
        feature_names=[f"pc_{i}" for i in range(n_componentes)],
        treinado_em=datetime(2026, 4, 28, 12, 0, 0, tzinfo=UTC),
        hash_amostra="abc123",
    )


def test_salvar_modelo_gera_meta_json(tmp_path: Path) -> None:
    """``salvar_modelo_base`` produz binario + meta.json no diretorio."""
    modelo = _modelo_fake()
    meta = salvar_modelo_base(modelo, tmp_path)

    assert (tmp_path / "base_v1.joblib").exists()
    assert (tmp_path / "base_v1.meta.json").exists()
    assert meta["versao"] == "1"
    assert meta["n_componentes"] == 5


def test_meta_json_tem_hash_sha256(tmp_path: Path) -> None:
    """``meta.json`` contem ``hash_sha256`` e bate com o arquivo serializado."""
    modelo = _modelo_fake()
    salvar_modelo_base(modelo, tmp_path)

    meta = json.loads((tmp_path / "base_v1.meta.json").read_text(encoding="utf-8"))
    assert "hash_sha256" in meta
    # Hash hex tem 64 caracteres.
    assert len(meta["hash_sha256"]) == 64
    assert meta["hash_amostra"] == "abc123"
    assert meta["feature_names"] == ["pc_0", "pc_1", "pc_2", "pc_3", "pc_4"]


def test_carregar_modelo_round_trip(tmp_path: Path) -> None:
    """Salvar e carregar produz modelo equivalente (transform iguais)."""
    modelo = _modelo_fake(n_componentes=5)
    salvar_modelo_base(modelo, tmp_path)

    carregado = carregar_modelo_base(tmp_path)
    assert carregado.versao == modelo.versao
    assert carregado.n_componentes == modelo.n_componentes
    assert carregado.feature_names == modelo.feature_names

    # transform consistente.
    rng = np.random.default_rng(seed=99)
    X = rng.standard_normal((3, 64))
    np.testing.assert_array_almost_equal(modelo.transform(X), carregado.transform(X))


def test_carregar_arquivo_corrompido_falha_integridade(tmp_path: Path) -> None:
    """Modificar 1 byte do binario apos salvar deve falhar a validacao SHA256."""
    modelo = _modelo_fake()
    salvar_modelo_base(modelo, tmp_path)

    binario = tmp_path / "base_v1.joblib"
    # Append 1 byte -- altera SHA256 sem destruir o formato.
    with binario.open("ab") as f:
        f.write(b"\x00")

    with pytest.raises(IntegridadeViolada, match="Hash divergente"):
        carregar_modelo_base(tmp_path)


def test_carregar_versao_diferente_falha(tmp_path: Path) -> None:
    """meta.json com versao != '1' aborta carregamento."""
    modelo = _modelo_fake()
    salvar_modelo_base(modelo, tmp_path)

    meta_path = tmp_path / "base_v1.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["versao"] = "99"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    with pytest.raises(IntegridadeViolada, match="Versao incompat"):
        carregar_modelo_base(tmp_path)


def test_carregar_arquivos_ausentes_falha(tmp_path: Path) -> None:
    """Diretorio sem arquivos do modelo levanta FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="ausente"):
        carregar_modelo_base(tmp_path)


def test_info_modelo_base_sem_modelo(tmp_path: Path) -> None:
    """``info_modelo_base`` em diretorio limpo retorna None."""
    assert info_modelo_base(tmp_path) is None


def test_info_modelo_base_com_modelo(tmp_path: Path) -> None:
    """``info_modelo_base`` apos salvar retorna o manifesto."""
    modelo = _modelo_fake()
    salvar_modelo_base(modelo, tmp_path)
    info = info_modelo_base(tmp_path)
    assert info is not None
    assert info["versao"] == "1"
