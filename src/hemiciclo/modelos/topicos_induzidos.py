"""Wrapper BERTopic stub (S28; treino real em S30/S31).

BERTopic e o algoritmo escolhido (D11) para topic modeling sobre clusters
retoricos induzidos. O treino real depende de :class:`ModeloBaseV1` ja
treinado e de embeddings da sessão -- portanto fica para S30+.

Esta sprint entrega apenas a interface lazy-imported para não onerar boot
e não puxar BERTopic em CI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np


class WrapperBERTopic:
    """Wrapper lazy de ``bertopic.BERTopic``.

    Em S28 e apenas placeholder; metodos reais entram em S30/S31.
    """

    def __init__(self) -> None:
        self._modelo: Any = None

    def _garantir_modelo(self) -> None:
        """Lazy import de BERTopic; não acionado em S28."""
        if self._modelo is not None:
            return
        from bertopic import BERTopic  # noqa: PLC0415 -- lazy

        self._modelo = BERTopic(verbose=False)

    def treinar(self, textos: list[str], embeddings: np.ndarray) -> WrapperBERTopic:
        """Placeholder. Em S30 chamara ``BERTopic.fit_transform``.

        Em S28 levanta :class:`NotImplementedError` se acionado.
        """
        raise NotImplementedError(
            "WrapperBERTopic.treinar entra em S30 (depende de modelo base treinado)."
        )
