"""Testes do wrapper httpx + tenacity em ``hemiciclo.coleta.http``."""

from __future__ import annotations

import httpx
import pytest
import respx

from hemiciclo import __version__
from hemiciclo.coleta.http import (
    USER_AGENT,
    cliente_http,
    raise_para_status,
    retry_resiliente,
)


def test_cliente_http_user_agent_correto() -> None:
    """O cliente injeta User-Agent identificável com versão e URL."""
    with cliente_http() as cli:
        assert cli.headers["User-Agent"] == USER_AGENT
    assert __version__ in USER_AGENT
    assert "github.com/AndreBFarias/Hemiciclo" in USER_AGENT


@respx.mock
def test_retry_em_503() -> None:
    """503 dispara retry e a chamada eventualmente sucede."""
    rota = respx.get("https://exemplo.gov.br/x").mock(
        side_effect=[
            httpx.Response(503, text="indisponivel"),
            httpx.Response(503, text="indisponivel"),
            httpx.Response(200, json={"ok": True}),
        ]
    )

    @retry_resiliente
    def baixar() -> dict[str, bool]:
        with cliente_http(timeout=5.0) as cli:
            resp = cli.get("https://exemplo.gov.br/x")
            raise_para_status(resp)
            return resp.json()  # type: ignore[no-any-return]

    resultado = baixar()
    assert resultado == {"ok": True}
    assert rota.call_count == 3


@respx.mock
def test_retry_em_timeout() -> None:
    """``TimeoutException`` dispara retry e eventualmente sucede."""
    rota = respx.get("https://exemplo.gov.br/y").mock(
        side_effect=[
            httpx.TimeoutException("timeout"),
            httpx.Response(200, json={"v": 1}),
        ]
    )

    @retry_resiliente
    def baixar() -> dict[str, int]:
        with cliente_http(timeout=5.0) as cli:
            resp = cli.get("https://exemplo.gov.br/y")
            raise_para_status(resp)
            return resp.json()  # type: ignore[no-any-return]

    resultado = baixar()
    assert resultado == {"v": 1}
    assert rota.call_count == 2


@respx.mock
def test_nao_retry_em_404() -> None:
    """404 propaga ``HTTPStatusError`` sem retry."""
    rota = respx.get("https://exemplo.gov.br/z").mock(
        return_value=httpx.Response(404, text="nao encontrado")
    )

    @retry_resiliente
    def baixar() -> None:
        with cliente_http(timeout=5.0) as cli:
            resp = cli.get("https://exemplo.gov.br/z")
            raise_para_status(resp)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        baixar()

    assert exc_info.value.response.status_code == 404
    assert rota.call_count == 1, "404 não deve disparar retry"


@respx.mock
def test_backoff_exponencial_respeitado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tenacity respeita backoff exponencial entre tentativas.

    Substituímos ``time.sleep`` da tenacity por um stub que captura as
    durações solicitadas, em vez de esperar. Verificamos que cada espera
    é estritamente maior que a anterior (crescimento exponencial).
    """
    esperas: list[float] = []

    def _fake_sleep(segundos: float) -> None:
        esperas.append(segundos)

    # tenacity usa ``nap.sleep`` por baixo dos panos, que vem de ``time.sleep``
    monkeypatch.setattr("tenacity.nap.time.sleep", _fake_sleep)

    respx.get("https://exemplo.gov.br/back").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, json={"ok": 1}),
        ]
    )

    @retry_resiliente
    def baixar() -> dict[str, int]:
        with cliente_http(timeout=5.0) as cli:
            resp = cli.get("https://exemplo.gov.br/back")
            raise_para_status(resp)
            return resp.json()  # type: ignore[no-any-return]

    resultado = baixar()
    assert resultado == {"ok": 1}
    # Três retries -> três sleeps.
    assert len(esperas) == 3
    # Backoff exponencial: cada espera é >= anterior.
    for anterior, atual in zip(esperas, esperas[1:], strict=False):
        assert atual >= anterior, f"esperas devem crescer: {esperas}"
    # Limite máximo de 60s respeitado:
    assert all(e <= 60.0 for e in esperas)
