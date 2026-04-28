"""Wrapper bge-m3 com lazy import (S28, ADR-009 -- D9).

A camada 3 do classificador multicamada (D11/ADR-011) usa o modelo
``BAAI/bge-m3`` (estado-da-arte multilíngue 2024-25) para gerar
embeddings densos de 1024 dimensões. O modelo pesa ~2GB e não deve ser
carregado no boot do CLI nem em testes -- por isso este módulo isola o
import de ``FlagEmbedding`` dentro de :meth:`WrapperEmbeddings._garantir_modelo`.

Decisões:

- **Lazy import**: ``from FlagEmbedding import BGEM3FlagModel`` só
  acontece quando ``embed`` e chamado pela primeira vez. Isso permite
  ``from hemiciclo.modelos.embeddings import WrapperEmbeddings`` rodar
  em milissegundos.
- **Cache em ``~/hemiciclo/modelos/bge-m3/``**: a própria FlagEmbedding
  mantem cache em ``cache_dir``; não baixamos automaticamente -- usuário
  invoca ``hemiciclo modelo base baixar`` se quiser pré-aquecer.
- **Detecção de hardware**: ``device="auto"`` testa ``torch.cuda.is_available``
  via lazy import; fallback ``cpu``. Sem torch instalado, fallback ``cpu``.
- **Batches de 64**: bge-m3 prefere chunks pequenos para memória estável.
- **Sparse opcional**: ``embed_sparse`` e exposto mas não usado em S28
  (PCA dense basta para o modelo base v1).

Determinismo: o modelo em si e determinístico em modo eval (default da
FlagEmbedding); não precisamos passar ``random_state`` aqui. O random
state global do projeto é aplicado no PCA (ver :mod:`base`).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np

from hemiciclo.config import Configuracao


class WrapperEmbeddings:
    """Wrapper lazy do modelo ``BAAI/bge-m3``.

    Uso típico::

        wrapper = WrapperEmbeddings()
        vetores = wrapper.embed(["texto 1", "texto 2"])  # shape (2, 1024)

    Args:
        dir_modelo: Diretório de cache do FlagEmbedding. Default
            ``~/hemiciclo/modelos/bge-m3/``.
        device: ``"auto"`` (default), ``"cuda"`` ou ``"cpu"``.
    """

    def __init__(self, dir_modelo: Path | None = None, device: str = "auto") -> None:
        self.dir_modelo = dir_modelo or (Configuracao().modelos_dir / "bge-m3")
        self.device = device
        self._modelo: Any = None

    def _resolver_device(self) -> str:
        """Retorna ``cuda`` se disponível, senão ``cpu``."""
        if self.device != "auto":
            return self.device
        try:
            import torch  # noqa: PLC0415 -- lazy

            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def _garantir_modelo(self) -> None:
        """Carrega ``BGEM3FlagModel`` na primeira chamada (lazy)."""
        if self._modelo is not None:
            return
        from FlagEmbedding import BGEM3FlagModel  # noqa: PLC0415 -- lazy 2GB

        self._modelo = BGEM3FlagModel(
            "BAAI/bge-m3",
            cache_dir=str(self.dir_modelo),
            use_fp16=False,
            device=self._resolver_device(),
        )

    def embed(self, textos: list[str]) -> np.ndarray:
        """Gera embeddings densos shape ``(N, 1024)``.

        Aplica batches de 64 internamente (bge-m3 estável em chunks
        pequenos para memória controlada).
        """
        import numpy as np  # noqa: PLC0415 -- lazy

        self._garantir_modelo()
        out = self._modelo.encode(textos, batch_size=64, return_dense=True)
        return np.array(out["dense_vecs"])

    def embed_sparse(self, textos: list[str]) -> list[dict[str, float]]:
        """Gera representações sparse (dict ``term_id -> peso``).

        Exposto para uso futuro (S30+). Em S28 o modelo base v1 usa
        apenas o vetor dense.
        """
        self._garantir_modelo()
        out = self._modelo.encode(textos, batch_size=64, return_sparse=True)
        return list(out["lexical_weights"])


def embeddings_disponivel(dir_modelo: Path | None = None) -> bool:
    """Verifica se o modelo bge-m3 já está baixado em ``dir_modelo``.

    Procura por arquivos ``.safetensors`` recursivamente. Não importa
    ``FlagEmbedding`` -- chamada barata, segura para boot do CLI.
    """
    dir_modelo = dir_modelo or (Configuracao().modelos_dir / "bge-m3")
    if not dir_modelo.exists():
        return False
    for _ in dir_modelo.rglob("*.safetensors"):
        return True
    return False
