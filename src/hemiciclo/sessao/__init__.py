"""Pacote de Sessão de Pesquisa do Hemiciclo.

Define os modelos Pydantic v2 (S23) e o runner subprocess autocontido
(S29) que materializa cada busca cidadã como pasta em
``~/hemiciclo/sessoes/<id>/`` -- o cidadão de primeira classe do produto
(D7 / ADR-007 do plano R2).

Re-exporta a superfície pública:

- Schemas: :class:`ParametrosBusca`, :class:`StatusSessao`,
  :class:`EstadoSessao`, :class:`Casa`, :class:`Camada`, :data:`UFS_BRASIL`.
- Persistência: :func:`gerar_id_sessao`, :func:`caminho_sessao`,
  :func:`salvar_params`, :func:`carregar_params`, :func:`salvar_status`,
  :func:`carregar_status`, :func:`listar_sessoes`, :func:`deletar_sessao`.
- Runner: :class:`SessaoRunner`, :class:`StatusUpdater`, :func:`pid_vivo`.
- Retomada: :func:`detectar_interrompidas`, :func:`marcar_interrompida`,
  :func:`retomar`.
- Exportador: :func:`exportar_zip`, :func:`exportar_zip_bytes`,
  :func:`importar_zip`, :class:`IntegridadeImportadaInvalida`.
"""

from __future__ import annotations

from hemiciclo.sessao.exportador import (
    IntegridadeImportadaInvalida,
    exportar_zip,
    exportar_zip_bytes,
    importar_zip,
)
from hemiciclo.sessao.modelo import (
    UFS_BRASIL,
    Camada,
    Casa,
    EstadoSessao,
    ParametrosBusca,
    StatusSessao,
)
from hemiciclo.sessao.persistencia import (
    caminho_sessao,
    carregar_params,
    carregar_status,
    deletar_sessao,
    gerar_id_sessao,
    listar_sessoes,
    salvar_params,
    salvar_status,
)
from hemiciclo.sessao.pipeline import (
    LIMITACOES_CONHECIDAS,
    VERSAO_PIPELINE,
    pipeline_real,
)
from hemiciclo.sessao.retomada import (
    ESTADOS_TERMINAIS,
    detectar_interrompidas,
    marcar_interrompida,
    retomar,
)
from hemiciclo.sessao.runner import SessaoRunner, StatusUpdater, pid_vivo

__all__ = [
    "ESTADOS_TERMINAIS",
    "LIMITACOES_CONHECIDAS",
    "UFS_BRASIL",
    "VERSAO_PIPELINE",
    "Camada",
    "Casa",
    "EstadoSessao",
    "IntegridadeImportadaInvalida",
    "ParametrosBusca",
    "SessaoRunner",
    "StatusSessao",
    "StatusUpdater",
    "caminho_sessao",
    "carregar_params",
    "carregar_status",
    "deletar_sessao",
    "detectar_interrompidas",
    "exportar_zip",
    "exportar_zip_bytes",
    "gerar_id_sessao",
    "importar_zip",
    "listar_sessoes",
    "marcar_interrompida",
    "pid_vivo",
    "pipeline_real",
    "retomar",
    "salvar_params",
    "salvar_status",
]
