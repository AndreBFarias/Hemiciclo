"""Modelos Pydantic v2 da Sessão de Pesquisa.

Refs:
- Plano R2 §5.4 (esqueleto canônico).
- ADR-007 (Sessão de Pesquisa como cidadão de primeira classe).
- VALIDATOR_BRIEF I6 (Pydantic v2 estrito; sem dicts soltos).

Esta camada entrega apenas os schemas. Runner subprocess, PID lockfile,
persistência em disco e retomada via checkpoint são responsabilidades da S29.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# UFs canônicas (27 unidades federativas: 26 estados + DF).
UFS_BRASIL: tuple[str, ...] = (
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
)


class Camada(StrEnum):
    """Camadas de classificação multicamada (D11 do plano R2)."""

    REGEX = "regex"
    VOTOS = "votos"
    EMBEDDINGS = "embeddings"
    LLM = "llm"


class Casa(StrEnum):
    """Casa legislativa do Congresso Nacional."""

    CAMARA = "camara"
    SENADO = "senado"


class EstadoSessao(StrEnum):
    """Estado de execução de uma Sessão de Pesquisa.

    Ciclo de vida típico:
    ``CRIADA -> COLETANDO -> ETL -> EMBEDDINGS -> MODELANDO -> CONCLUIDA``.

    Estados de exceção: ``ERRO`` (falha não recuperável),
    ``INTERROMPIDA`` (kill externo, processo sumiu sem update),
    ``PAUSADA`` (usuário pausou via UI).
    """

    CRIADA = "criada"
    COLETANDO = "coletando"
    ETL = "etl"
    EMBEDDINGS = "embeddings"
    MODELANDO = "modelando"
    CONCLUIDA = "concluida"
    ERRO = "erro"
    INTERROMPIDA = "interrompida"
    PAUSADA = "pausada"


class ParametrosBusca(BaseModel):
    """Parâmetros canônicos de uma busca cidadã.

    Persistidos em ``~/hemiciclo/sessoes/<id>/params.json`` quando a sessão é
    criada (mesmo que ainda em rascunho, via S23). Imutáveis após início do
    pipeline real (S30).
    """

    model_config = ConfigDict(
        frozen=False,
        str_strip_whitespace=True,
        extra="forbid",
        validate_assignment=True,
    )

    topico: str = Field(
        ...,
        min_length=1,
        description="Texto livre OU id de YAML curado em ``topicos/``.",
    )
    casas: list[Casa] = Field(
        ...,
        min_length=1,
        description="Casas legislativas alvo (ao menos uma).",
    )
    legislaturas: list[int] = Field(
        ...,
        min_length=1,
        description="Legislaturas numeradas (ex: 55, 56, 57).",
    )
    ufs: list[str] | None = Field(
        default=None,
        description="UFs alvo. ``None`` = todas as 27.",
    )
    partidos: list[str] | None = Field(
        default=None,
        description="Siglas de partido alvo. ``None`` = todos.",
    )
    data_inicio: date | None = Field(
        default=None,
        description="Início do período. ``None`` = sem limite inferior.",
    )
    data_fim: date | None = Field(
        default=None,
        description="Fim do período. ``None`` = sem limite superior.",
    )
    camadas: list[Camada] = Field(
        default_factory=lambda: [Camada.REGEX, Camada.VOTOS, Camada.EMBEDDINGS],
        description="Camadas de classificação ativas. LLM desligada por default.",
    )
    incluir_grafo: bool = Field(
        default=True,
        description="Renderizar grafo de coautoria + voto (S32).",
    )
    incluir_convertibilidade: bool = Field(
        default=False,
        description="Calcular convertibilidade ML (S34, custoso).",
    )
    max_itens: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Limite de itens por tipo coletado por casa. ``None`` = sem limite "
            "(universo completo). Aplicado por casa: ``max_itens=N`` coleta no "
            "máximo N itens da Câmara e N do Senado, totalizando até 2N quando "
            "ambas as casas estão em ``params.casas``. Útil para smoke local "
            "(``--max-itens 50`` ~1-2 min vs full ~30-60 min)."
        ),
    )

    @field_validator("topico")
    @classmethod
    def _topico_nao_pode_ser_branco(cls, valor: str) -> str:
        """Rejeita tópico vazio ou só com espaços."""
        if not valor.strip():
            msg = "tópico não pode ser vazio"
            raise ValueError(msg)
        return valor

    @field_validator("legislaturas")
    @classmethod
    def _legislaturas_positivas(cls, valor: list[int]) -> list[int]:
        """Legislaturas precisam ser inteiros positivos."""
        for n in valor:
            if n <= 0:
                msg = f"legislatura inválida: {n} (deve ser > 0)"
                raise ValueError(msg)
        return valor

    @field_validator("ufs")
    @classmethod
    def _ufs_canonicas(cls, valor: list[str] | None) -> list[str] | None:
        """Valida que UFs informadas estão na lista canônica brasileira."""
        if valor is None:
            return None
        for uf in valor:
            if uf.upper() not in UFS_BRASIL:
                msg = f"UF inválida: {uf!r}"
                raise ValueError(msg)
        return [uf.upper() for uf in valor]

    @model_validator(mode="after")
    def _periodo_coerente(self) -> ParametrosBusca:
        """``data_inicio`` não pode ser posterior a ``data_fim``."""
        if (
            self.data_inicio is not None
            and self.data_fim is not None
            and self.data_inicio > self.data_fim
        ):
            msg = "data_inicio não pode ser posterior a data_fim"
            raise ValueError(msg)
        return self


class StatusSessao(BaseModel):
    """Status de execução publicado pelo subprocess da sessão.

    Lido pelo Streamlit em polling. Persistido em ``status.json`` na pasta
    da sessão. Atualização atômica via gravação em ``status.json.tmp`` +
    rename é responsabilidade do runner (S29).
    """

    model_config = ConfigDict(
        frozen=False,
        str_strip_whitespace=True,
        extra="forbid",
        validate_assignment=True,
    )

    id: str = Field(..., min_length=1, description="Identificador único da sessão.")
    estado: EstadoSessao
    progresso_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Progresso global da sessão, no intervalo [0, 100].",
    )
    etapa_atual: str = Field(
        ...,
        description="Descrição curta da etapa atual (ex.: 'Coletando votações').",
    )
    mensagem: str = Field(
        default="",
        description="Mensagem auxiliar para o usuário (texto livre).",
    )
    iniciada_em: datetime
    atualizada_em: datetime
    pid: int | None = Field(
        default=None,
        description="PID do subprocess que detém o lockfile da sessão.",
    )
    erro: str | None = Field(
        default=None,
        description="Mensagem de erro se ``estado == ERRO``.",
    )

    @model_validator(mode="after")
    def _atualizada_nao_anterior_a_iniciada(self) -> StatusSessao:
        """Coerência temporal mínima: ``atualizada_em >= iniciada_em``."""
        if self.atualizada_em < self.iniciada_em:
            msg = "atualizada_em não pode ser anterior a iniciada_em"
            raise ValueError(msg)
        return self
