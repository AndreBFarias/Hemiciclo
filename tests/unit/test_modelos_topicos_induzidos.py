"""Testes do stub WrapperBERTopic (S28).

Em S28 a interface e apenas placeholder; treino real entra em S30/S31.
Validamos: construtor lazy + ``treinar`` levanta NotImplementedError +
import lazy de bertopic so e tentado quando ``_garantir_modelo`` e chamado.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from hemiciclo.modelos.topicos_induzidos import WrapperBERTopic


def test_init_nao_carrega_bertopic() -> None:
    """Construtor nao deve importar ``bertopic``."""
    wrapper = WrapperBERTopic()
    assert wrapper._modelo is None  # noqa: SLF001 -- inspecao de estado


def test_treinar_levanta_not_implemented() -> None:
    """``treinar`` em S28 e placeholder."""
    wrapper = WrapperBERTopic()
    with pytest.raises(NotImplementedError, match="S30"):
        wrapper.treinar(["texto"], np.zeros((1, 10)))


def test_garantir_modelo_faz_lazy_import() -> None:
    """``_garantir_modelo`` importa BERTopic apenas quando chamado."""
    fake_bertopic_module = MagicMock()
    fake_bertopic_module.BERTopic.return_value = MagicMock(name="modelo_fake")

    with patch.dict("sys.modules", {"bertopic": fake_bertopic_module}):
        wrapper = WrapperBERTopic()
        wrapper._garantir_modelo()  # noqa: SLF001 -- exercitando lazy
        assert wrapper._modelo is not None  # noqa: SLF001
        fake_bertopic_module.BERTopic.assert_called_once_with(verbose=False)


def test_garantir_modelo_idempotente() -> None:
    """Chamar ``_garantir_modelo`` duas vezes nao re-instancia."""
    fake_bertopic_module = MagicMock()
    fake_bertopic_module.BERTopic.return_value = MagicMock(name="modelo_unico")

    with patch.dict("sys.modules", {"bertopic": fake_bertopic_module}):
        wrapper = WrapperBERTopic()
        wrapper._garantir_modelo()  # noqa: SLF001
        wrapper._garantir_modelo()  # noqa: SLF001
        assert fake_bertopic_module.BERTopic.call_count == 1
