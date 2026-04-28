"""Testes do wrapper bge-m3 (S28).

REGRA DE OURO: nenhum teste pode baixar o modelo real (~2GB). Toda
instancia de ``BGEM3FlagModel`` e mockada via ``unittest.mock``. Se o
mock vazar (ex: alguem acidentalmente importar no top-level), CI ira
quebrar com timeout de download.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from hemiciclo.modelos.embeddings import WrapperEmbeddings, embeddings_disponivel


def test_wrapper_lazy_import_nao_carrega_no_init(tmp_path: Path) -> None:
    """Construtor nao deve importar FlagEmbedding nem instanciar o modelo."""
    with patch("FlagEmbedding.BGEM3FlagModel") as mock_modelo:
        wrapper = WrapperEmbeddings(dir_modelo=tmp_path / "bge-m3")
        # Construtor por si so nao deve ter chamado o construtor do modelo.
        assert mock_modelo.call_count == 0
        assert wrapper._modelo is None  # noqa: SLF001 -- inspecao de estado


def test_embed_chama_modelo_subjacente(tmp_path: Path) -> None:
    """``embed`` instancia o modelo via lazy import e devolve numpy array."""
    instancia = MagicMock()
    instancia.encode.return_value = {"dense_vecs": np.zeros((2, 1024))}
    with patch("FlagEmbedding.BGEM3FlagModel", return_value=instancia) as mock_modelo:
        wrapper = WrapperEmbeddings(dir_modelo=tmp_path / "bge-m3", device="cpu")
        out = wrapper.embed(["a", "b"])

        assert out.shape == (2, 1024)
        assert mock_modelo.call_count == 1
        # batch_size=64 e contrato (lição do spec; bge-m3 prefere batches pequenos).
        instancia.encode.assert_called_once_with(["a", "b"], batch_size=64, return_dense=True)


def test_detecta_cuda_se_disponivel(tmp_path: Path) -> None:
    """Quando ``torch.cuda.is_available`` retorna True, device='cuda'."""
    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = True

    with patch.dict("sys.modules", {"torch": fake_torch}):
        wrapper = WrapperEmbeddings(dir_modelo=tmp_path / "bge-m3", device="auto")
        assert wrapper._resolver_device() == "cuda"

    fake_torch.cuda.is_available.return_value = False
    with patch.dict("sys.modules", {"torch": fake_torch}):
        wrapper = WrapperEmbeddings(dir_modelo=tmp_path / "bge-m3", device="auto")
        assert wrapper._resolver_device() == "cpu"


def test_embeddings_disponivel_retorna_false_se_dir_vazio(tmp_path: Path) -> None:
    """Sem arquivos .safetensors no dir, retorna False (mesmo se dir existe)."""
    dir_bge = tmp_path / "bge-m3"
    # Diretorio inexistente.
    assert embeddings_disponivel(dir_bge) is False
    # Diretorio existe mas vazio.
    dir_bge.mkdir(parents=True)
    assert embeddings_disponivel(dir_bge) is False


def test_embeddings_disponivel_retorna_true_se_dir_tem_modelo(tmp_path: Path) -> None:
    """Presenca de qualquer .safetensors recursivo basta."""
    dir_bge = tmp_path / "bge-m3" / "models--BAAI--bge-m3"
    dir_bge.mkdir(parents=True)
    (dir_bge / "model.safetensors").write_bytes(b"x")
    assert embeddings_disponivel(tmp_path / "bge-m3") is True


def test_embed_sparse_chama_modelo_subjacente(tmp_path: Path) -> None:
    """``embed_sparse`` aciona lazy load + retorna lista de dicts."""
    instancia = MagicMock()
    instancia.encode.return_value = {
        "lexical_weights": [{"123": 0.5}, {"456": 0.7}],
    }
    with patch("FlagEmbedding.BGEM3FlagModel", return_value=instancia):
        wrapper = WrapperEmbeddings(dir_modelo=tmp_path / "bge-m3", device="cpu")
        out = wrapper.embed_sparse(["a", "b"])
        assert out == [{"123": 0.5}, {"456": 0.7}]
        instancia.encode.assert_called_once_with(["a", "b"], batch_size=64, return_sparse=True)


def test_resolver_device_explicito_nao_chama_torch(tmp_path: Path) -> None:
    """``device`` explicito (cpu ou cuda) e respeitado sem importar torch."""
    wrapper = WrapperEmbeddings(dir_modelo=tmp_path / "bge-m3", device="cpu")
    assert wrapper._resolver_device() == "cpu"
    wrapper2 = WrapperEmbeddings(dir_modelo=tmp_path / "bge-m3", device="cuda")
    assert wrapper2._resolver_device() == "cuda"


def test_resolver_device_sem_torch_fallback_cpu(tmp_path: Path) -> None:
    """Se ``import torch`` falha, fallback para cpu."""
    import builtins

    real_import = builtins.__import__

    def _fake_import(nome: str, *args: object, **kwargs: object) -> object:
        if nome == "torch":
            raise ImportError("torch nao instalado neste ambiente")
        return real_import(nome, *args, **kwargs)

    with patch("builtins.__import__", side_effect=_fake_import):
        wrapper = WrapperEmbeddings(dir_modelo=tmp_path / "bge-m3", device="auto")
        assert wrapper._resolver_device() == "cpu"
