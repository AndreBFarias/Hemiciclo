"""Configuração centralizada via Pydantic Settings.

Carrega variáveis de ambiente com prefixo ``HEMICICLO_``.

Invariantes do projeto cobertos por este módulo:

- I3 (determinismo): ``random_state`` declarado e fixo (default 42).
- I6 (Pydantic v2 estrito): toda configuração atravessa modelo Pydantic.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    """Configuração do Hemiciclo.

    Todos os campos podem ser sobrescritos via variáveis de ambiente
    no padrão ``HEMICICLO_<NOME_DO_CAMPO>`` (case-insensitive).

    Exemplos:
        - ``HEMICICLO_HOME=/tmp/foo``
        - ``HEMICICLO_LOG_LEVEL=DEBUG``
        - ``HEMICICLO_RANDOM_STATE=99``
    """

    model_config = SettingsConfigDict(
        env_prefix="HEMICICLO_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    home: Path = Field(
        default_factory=lambda: Path.home() / "hemiciclo",
        description="Diretório raiz do Hemiciclo no filesystem do usuário.",
    )
    log_level: str = Field(
        default="INFO",
        description="Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    )
    random_state: int = Field(
        default=42,
        description="Seed determinista para todos os modelos aleatórios.",
    )

    @property
    def modelos_dir(self) -> Path:
        """Diretório de modelos treinados (base global + ajustes locais)."""
        return self.home / "modelos"

    @property
    def sessoes_dir(self) -> Path:
        """Diretório das Sessões de Pesquisa do usuário."""
        return self.home / "sessoes"

    @property
    def cache_dir(self) -> Path:
        """Cache transversal SHA256 de respostas de API e artefatos derivados."""
        return self.home / "cache"

    @property
    def logs_dir(self) -> Path:
        """Logs globais rotacionados (Loguru)."""
        return self.home / "logs"

    @property
    def topicos_dir(self) -> Path:
        """Diretório de YAMLs curados de tópicos."""
        return self.home / "topicos"

    def garantir_diretorios(self) -> None:
        """Cria todos os diretórios necessários se ainda não existirem.

        Idempotente: chamadas repetidas são seguras.
        """
        for diretorio in (
            self.home,
            self.modelos_dir,
            self.sessoes_dir,
            self.cache_dir,
            self.logs_dir,
            self.topicos_dir,
        ):
            diretorio.mkdir(parents=True, exist_ok=True)
