"""Testes do TokenBucket em ``hemiciclo.coleta.rate_limit``."""

from __future__ import annotations

import time

import pytest

from hemiciclo.coleta.rate_limit import TokenBucket, taxa_padrao


def test_token_bucket_consome_token() -> None:
    """O balde inicia cheio e consume 1 token por chamada."""
    bucket = TokenBucket(taxa=10.0, capacidade=5)
    assert bucket.tokens_disponiveis == pytest.approx(5.0)
    bucket.aguardar()
    # Após consumir 1, sobram aproximadamente 4 (mais a reposição minúscula).
    assert bucket.tokens_disponiveis < 5.0
    assert bucket.tokens_disponiveis >= 3.5


def test_token_bucket_aguarda_quando_vazio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quando o balde está vazio, ``aguardar`` chama ``time.sleep``."""
    sleeps: list[float] = []
    monkeypatch.setattr(
        "hemiciclo.coleta.rate_limit.time.sleep",
        lambda s: sleeps.append(s),
    )

    # Capacidade 1, taxa 5 req/s.
    bucket = TokenBucket(taxa=5.0, capacidade=1)
    bucket.aguardar()  # consome o único token (sem sleep)
    assert sleeps == []

    # Forçamos relógio a não avançar para simular requisições muito rápidas:
    tempo_atual = time.monotonic()
    monkeypatch.setattr(
        "hemiciclo.coleta.rate_limit.time.monotonic",
        lambda: tempo_atual,
    )
    # Reset interno do bucket para usar o mock:
    bucket._ultimo = tempo_atual  # noqa: SLF001
    bucket._tokens = 0.0  # noqa: SLF001

    # Próxima chamada precisa esperar 1/5 = 0.2s.
    # Como sleep é mock e não avança o relógio, ficaria em loop infinito.
    # Para destravar, o sleep avança ``_tokens`` artificialmente:
    chamadas = {"n": 0}

    def _avanca(s: float) -> None:
        sleeps.append(s)
        chamadas["n"] += 1
        if chamadas["n"] >= 1:
            bucket._tokens = 1.0  # noqa: SLF001 -- empurra para sair do loop

    monkeypatch.setattr(
        "hemiciclo.coleta.rate_limit.time.sleep",
        _avanca,
    )
    bucket.aguardar()
    assert len(sleeps) == 1
    assert sleeps[0] == pytest.approx(0.2, abs=0.01)


def test_capacidade_maxima(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_tokens`` nunca excede ``capacidade``, mesmo após longa ociosidade."""
    bucket = TokenBucket(taxa=10.0, capacidade=3)
    assert bucket.tokens_disponiveis == pytest.approx(3.0)

    # Avança o relógio simulando 100s de ociosidade -- mesmo assim
    # o balde não passa de 3 tokens.
    tempo_inicial = bucket._ultimo  # noqa: SLF001
    monkeypatch.setattr(
        "hemiciclo.coleta.rate_limit.time.monotonic",
        lambda: tempo_inicial + 100.0,
    )
    bucket.aguardar()  # consome 1 dos 3 (após cap)
    assert bucket.tokens_disponiveis < 3.0
    assert bucket.tokens_disponiveis >= 1.5


def test_taxa_via_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """``HEMICICLO_RATE_LIMIT`` sobrescreve a taxa default."""
    assert taxa_padrao() == pytest.approx(10.0)
    monkeypatch.setenv("HEMICICLO_RATE_LIMIT", "2.5")
    assert taxa_padrao() == pytest.approx(2.5)

    bucket = TokenBucket()  # taxa lida do env
    assert bucket.taxa == pytest.approx(2.5)


def test_taxa_invalida_levanta() -> None:
    """Taxa <= 0 ou capacidade <= 0 levantam ``ValueError``."""
    with pytest.raises(ValueError, match="taxa"):
        TokenBucket(taxa=0.0)
    with pytest.raises(ValueError, match="capacidade"):
        TokenBucket(taxa=10.0, capacidade=0)


def test_env_invalido_usa_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Valor não-numérico em env volta ao default 10.0."""
    monkeypatch.setenv("HEMICICLO_RATE_LIMIT", "abacaxi")
    assert taxa_padrao() == pytest.approx(10.0)
