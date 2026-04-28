"""Token bucket simples e thread-safe para limitar taxa de requisições.

A API da Câmara não documenta limites estritos, mas observamos throttling
informal em horários de pico. Este token bucket protege contra picos
acidentais e padroniza comportamento entre coletores (Câmara e Senado).

Default: 10 req/s, capacidade 20 (permite rajada inicial). Override via
variável de ambiente ``HEMICICLO_RATE_LIMIT`` (req/s).
"""

from __future__ import annotations

import os
import threading
import time


def taxa_padrao() -> float:
    """Lê a taxa padrão de ``HEMICICLO_RATE_LIMIT`` ou retorna 10.0 req/s.

    Variável de ambiente é lida em cada chamada (não em import-time)
    para facilitar testes com ``monkeypatch.setenv``.
    """
    valor = os.environ.get("HEMICICLO_RATE_LIMIT")
    if valor is None:
        return 10.0
    try:
        return float(valor)
    except ValueError:
        return 10.0


class TokenBucket:
    """Token bucket determinístico baseado em ``time.monotonic``.

    Algoritmo clássico:

    - ``capacidade`` define o tamanho máximo do balde (rajada permitida).
    - ``taxa`` é a velocidade de reposição (tokens por segundo).
    - Cada chamada a :meth:`aguardar` consome 1 token, esperando o tempo
      necessário se o balde estiver vazio.

    Thread-safe via lock interno. O sleep ocorre **fora** da seção
    crítica, permitindo paralelismo real entre threads competindo pelo
    mesmo balde.
    """

    def __init__(self, taxa: float | None = None, capacidade: int = 20) -> None:
        """Inicializa o balde.

        Args:
            taxa: Tokens por segundo. Se ``None``, lê de
                ``HEMICICLO_RATE_LIMIT`` ou usa 10.0.
            capacidade: Tamanho máximo do balde em tokens.
        """
        if taxa is None:
            taxa = taxa_padrao()
        if taxa <= 0:
            raise ValueError(f"taxa deve ser > 0, recebido {taxa}")
        if capacidade <= 0:
            raise ValueError(f"capacidade deve ser > 0, recebido {capacidade}")
        self.taxa = taxa
        self.capacidade = capacidade
        self._tokens = float(capacidade)
        self._ultimo = time.monotonic()
        self._lock = threading.Lock()

    def aguardar(self) -> None:
        """Bloqueia até consumir 1 token. Atualiza estado a cada chamada."""
        while True:
            with self._lock:
                agora = time.monotonic()
                elapsed = agora - self._ultimo
                self._tokens = min(
                    float(self.capacidade),
                    self._tokens + elapsed * self.taxa,
                )
                self._ultimo = agora
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                espera = (1.0 - self._tokens) / self.taxa
            time.sleep(espera)

    @property
    def tokens_disponiveis(self) -> float:
        """Tokens atualmente no balde (snapshot, não thread-safe a leitura)."""
        return self._tokens
