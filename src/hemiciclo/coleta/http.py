"""Cliente HTTP resiliente para APIs do Congresso.

Wrapper sobre ``httpx`` com:

- ``User-Agent`` identificável apontando para o repositório do Hemiciclo.
- Decorator ``@retry_resiliente`` aplicando ``tenacity``: 5 tentativas,
  backoff exponencial 1s -> 2s -> 4s -> 8s -> 16s, máximo 60s entre
  tentativas, log estruturado em cada retry.
- Retry apenas em falhas transitórias: 5xx, ``ConnectError``,
  ``TimeoutException`` e ``ReadError``.
- Sem retry em 4xx (erro permanente do cliente).

Cobre invariantes I1 (URLs apontam apenas para APIs públicas do governo
brasileiro -- responsabilidade dos chamadores), I4 (logs Loguru) e
I7 (tipagem estrita).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx
from loguru import logger
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from hemiciclo import __version__

if TYPE_CHECKING:  # pragma: no cover -- somente para o checker
    from collections.abc import Callable
    from typing import Any

USER_AGENT = f"Hemiciclo/{__version__} (+https://github.com/AndreBFarias/Hemiciclo)"
"""Identificação de cortesia para os endpoints públicos."""


def cliente_http(timeout: float = 30.0) -> httpx.Client:
    """Cria cliente ``httpx`` com User-Agent e timeout padrão.

    Args:
        timeout: Tempo limite global em segundos (default 30s).

    Returns:
        Cliente ``httpx.Client`` síncrono. O chamador é responsável por
        encerrá-lo via ``with`` ou ``cliente.close()``.
    """
    return httpx.Client(
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
    )


def _eh_falha_transitoria(exc: BaseException) -> bool:
    """Decide se a exceção justifica nova tentativa.

    Retorna ``True`` para 5xx, ``ConnectError``, ``TimeoutException`` e
    ``ReadError``. Retorna ``False`` para 4xx (erro permanente) e demais
    exceções (que devem ser propagadas sem retry).
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.is_server_error
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError))


# ``before_sleep_log`` espera ``logging.Logger`` nativo. Loguru é usado
# como sistema de log primário no resto do projeto; aqui ponte só para
# registrar a tentativa de retry.
_logger_compat = logging.getLogger("hemiciclo.coleta.http")


retry_resiliente: Callable[..., Any] = retry(
    retry=retry_if_exception(_eh_falha_transitoria),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(_logger_compat, logging.WARNING),
    reraise=True,
)
"""Decorator pronto para aplicar resiliência a funções de coleta.

Uso típico::

    @retry_resiliente
    def baixar(url: str) -> dict:
        with cliente_http() as cli:
            resp = cli.get(url)
            resp.raise_for_status()
            return resp.json()

5xx, timeouts e quedas de conexão são retentados. 4xx é propagado
imediatamente (erro permanente do cliente).
"""


def raise_para_status(resp: httpx.Response) -> None:
    """Levanta ``HTTPStatusError`` em 4xx ou 5xx, com log estruturado.

    Substituto direto de ``resp.raise_for_status()`` que registra a URL
    e o status via Loguru antes de propagar. Combinado com
    :data:`retry_resiliente`, garante que 5xx é retentado e 4xx é
    permanente.
    """
    if resp.is_server_error:
        logger.warning(
            "Resposta 5xx ({status}) em {url}",
            url=str(resp.request.url),
            status=resp.status_code,
        )
        resp.raise_for_status()
    if resp.is_client_error:
        logger.error(
            "Resposta 4xx ({status}) em {url} -- erro permanente, sem retry",
            url=str(resp.request.url),
            status=resp.status_code,
        )
        resp.raise_for_status()
