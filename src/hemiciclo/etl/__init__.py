"""Camada de ETL do Hemiciclo (S26+).

Responsável por consolidar os parquets da coleta (S24 Câmara, S25 Senado)
em um banco DuckDB analítico unificado, controlando schema via
:mod:`hemiciclo.etl.migrations` e expondo cache transversal por hash em
:mod:`hemiciclo.etl.cache`.

A entrada principal de uso é :func:`hemiciclo.etl.consolidador.consolidar_parquets_em_duckdb`,
chamada também pelo subcomando ``hemiciclo db consolidar`` do CLI.
"""

from __future__ import annotations

from hemiciclo.etl.schema import SCHEMA_VERSAO, criar_schema_v1

__all__ = ["SCHEMA_VERSAO", "criar_schema_v1"]
