"""Projecao de recortes locais no espaco induzido pelo modelo base (S28 stub).

Em S30, cada Sessão de Pesquisa rodara o seu recorte (subconjunto de
discursos) por :func:`projetar_em_base`, que aplica apenas ``transform``
do PCA -- nunca ``fit_transform`` -- garantindo que o eixo 1 do
parlamentar X seja o mesmo eixo 1 do parlamentar Y em pesquisas
diferentes.

Esta sprint entrega apenas a interface; o ajuste fino local
(``ModeloLocalV1`` + ``fit_partial`` sobre o recorte) fica em S30.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

    from hemiciclo.modelos.base import ModeloBaseV1


def projetar_em_base(modelo: ModeloBaseV1, X_local: np.ndarray) -> np.ndarray:
    """Projeta vetores locais ``(N, 1024)`` no espaco induzido do base.

    Apenas ``modelo.transform`` -- nunca refit. Idempotente: chamar
    duas vezes com o mesmo input retorna o mesmo output.

    Args:
        modelo: ModeloBaseV1 ja carregado/treinado.
        X_local: Embeddings densos do recorte da sessão, shape (N, 1024).

    Returns:
        Vetores projetados, shape (N, n_componentes).
    """
    return modelo.transform(X_local)
