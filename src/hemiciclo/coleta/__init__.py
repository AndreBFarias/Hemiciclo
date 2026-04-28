"""Subsistema de coleta de dados públicos do Congresso Nacional.

Esta sprint (S24) entrega o coletor da Câmara dos Deputados:

- :mod:`hemiciclo.coleta.http` -- cliente httpx + tenacity.
- :mod:`hemiciclo.coleta.rate_limit` -- TokenBucket thread-safe.
- :mod:`hemiciclo.coleta.checkpoint` -- persistência Pydantic atômica.
- :mod:`hemiciclo.coleta.camara` -- coletor principal (proposições,
  votações, votos, discursos, cadastro de deputados).

S25 replicará o mesmo padrão para o Senado. S26 consolida o output em
DuckDB unificado. Por enquanto, output são arquivos Parquet por tipo.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, Field, model_validator

TipoColeta = Literal[
    # Câmara
    "proposicoes",
    "votacoes",
    "votos",
    "discursos",
    "deputados",
    # Senado (S25)
    "materias",
    "senadores",
]
"""Tipos de itens que os coletores (Câmara e Senado) sabem baixar.

Câmara aceita: proposicoes, votacoes, votos, discursos, deputados.
Senado aceita: materias, votacoes, votos, discursos, senadores.
"""


class ParametrosColeta(BaseModel):
    """Parâmetros da invocação do coletor (Câmara ou Senado).

    Pydantic estrito (I6). Todos os campos exceto ``legislaturas`` e
    ``dir_saida`` têm default razoável para uso em smoke tests.
    """

    legislaturas: list[int] = Field(
        ...,
        min_length=1,
        description="Legislaturas a coletar (ex.: [55, 56, 57]).",
    )
    tipos: list[TipoColeta] = Field(
        default_factory=lambda: cast(list[TipoColeta], ["proposicoes"]),
        description="Tipos de itens. Default coleta apenas proposições.",
    )
    data_inicio: date | None = Field(
        default=None,
        description="Data inicial do recorte (filtro adicional).",
    )
    data_fim: date | None = Field(
        default=None,
        description="Data final do recorte (filtro adicional).",
    )
    max_itens: int | None = Field(
        default=None,
        ge=1,
        description="Limite total de itens por tipo. None = sem limite.",
    )
    dir_saida: Path = Field(
        ...,
        description="Diretório onde escrever os Parquet finais.",
    )
    enriquecer_proposicoes: bool = Field(
        default=True,
        description=(
            "S24b: após coleta listagem da Câmara, busca detalhe via "
            "GET /proposicoes/{id} para preencher tema_oficial, "
            "autor_principal, status e url_inteiro_teor."
        ),
    )

    @model_validator(mode="after")
    def _valida_periodo_e_legislaturas(self) -> ParametrosColeta:
        """Valida coerência de período e legislaturas."""
        if self.data_inicio and self.data_fim and self.data_inicio > self.data_fim:
            raise ValueError("data_inicio não pode ser posterior a data_fim")
        for leg in self.legislaturas:
            if leg < 1 or leg > 99:
                raise ValueError(f"legislatura fora do intervalo razoável: {leg}")
        if not self.tipos:
            raise ValueError("tipos não pode ser vazio")
        return self


__all__ = ["ParametrosColeta", "TipoColeta"]
