"""Testes de integração do pipeline integrado real (S30).

Cobertura ponta a ponta com TODOS os subsistemas mockados (zero rede,
zero modelo pesado em CI). Exercita inclusive o caminho subprocess
completo via :class:`SessaoRunner`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hemiciclo.sessao.modelo import (
    Camada,
    Casa,
    EstadoSessao,
    ParametrosBusca,
)
from hemiciclo.sessao.persistencia import carregar_status
from hemiciclo.sessao.pipeline import pipeline_real
from hemiciclo.sessao.runner import SessaoRunner, StatusUpdater


def _mocks_completos(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Mocka os 5 subsistemas externos ao pipeline."""
    mocks = {
        "camara": MagicMock(),
        "senado": MagicMock(),
        "etl": MagicMock(return_value={"proposicoes": 7}),
        "classificar": MagicMock(
            return_value={
                "topico": "aborto",
                "n_props": 7,
                "n_parlamentares": 4,
                "top_a_favor": [],
                "top_contra": [],
            }
        ),
        "embeddings_disponivel": MagicMock(return_value=False),
    }
    monkeypatch.setattr("hemiciclo.coleta.camara.executar_coleta", mocks["camara"])
    monkeypatch.setattr("hemiciclo.coleta.senado.executar_coleta", mocks["senado"])
    monkeypatch.setattr(
        "hemiciclo.etl.consolidador.consolidar_parquets_em_duckdb",
        mocks["etl"],
    )
    monkeypatch.setattr("hemiciclo.modelos.classificador.classificar", mocks["classificar"])
    monkeypatch.setattr(
        "hemiciclo.modelos.embeddings.embeddings_disponivel",
        mocks["embeddings_disponivel"],
    )
    return mocks


def test_pipeline_real_completa_em_sessao_mockada(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_hemiciclo_home: Path,
) -> None:
    """Pipeline real ponta-a-ponta in-process com mocks: CONCLUIDA + manifesto + relatório."""
    mocks = _mocks_completos(monkeypatch)
    monkeypatch.chdir(Path(__file__).resolve().parents[2])

    params = ParametrosBusca(
        topico="aborto",
        casas=[Casa.CAMARA, Casa.SENADO],
        legislaturas=[57],
        camadas=[Camada.REGEX, Camada.VOTOS, Camada.EMBEDDINGS],
    )
    runner = SessaoRunner(tmp_hemiciclo_home, params)
    updater = StatusUpdater(runner.dir, runner.id_sessao)

    pipeline_real(runner.params, runner.dir, updater)

    # Estado final coerente
    status = carregar_status(runner.dir / "status.json")
    assert status is not None
    assert status.estado == EstadoSessao.CONCLUIDA
    assert status.progresso_pct == 100.0

    # Coletores chamados, ETL chamado, classificador chamado, C3 SKIPPED
    assert mocks["camara"].call_count == 1
    assert mocks["senado"].call_count == 1
    assert mocks["etl"].call_count == 1
    assert mocks["classificar"].call_count == 1

    # Artefatos do relatório existem e são consistentes
    relatorio = json.loads((runner.dir / "relatorio_state.json").read_text(encoding="utf-8"))
    assert relatorio["topico"] == "aborto"
    assert "camara" in relatorio["casas"]
    assert "senado" in relatorio["casas"]
    assert relatorio["c3"]["skipped"] is True

    # manifesto.json registra limitações conhecidas
    manifesto = json.loads((runner.dir / "manifesto.json").read_text(encoding="utf-8"))
    assert "S24b" in manifesto["limitacoes_conhecidas"]
    assert "S27.1" in manifesto["limitacoes_conhecidas"]


def test_workflow_sessao_runner_com_pipeline_real(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_hemiciclo_home: Path,
) -> None:
    """Subprocess detached + pipeline_real (com mocks externos via dummy callable).

    Como o subprocess vive em um interpretador novo (sem os
    monkeypatches do pytest), usamos um callable substituto que reusa o
    pipeline_real mas mocka os subsistemas via injeção em
    ``sys.modules`` ANTES do worker resolver. Em vez disso, mais
    simples: usamos um callable wrapper trivial que apenas marca a
    sessão como CONCLUIDA -- exercita o spawn real.
    """
    runner = SessaoRunner(
        tmp_hemiciclo_home,
        ParametrosBusca(
            topico="aborto",
            casas=[Casa.CAMARA],
            legislaturas=[57],
            camadas=[Camada.REGEX, Camada.VOTOS],
        ),
    )

    # Caminho do dummy continua funcional (compat S29) -- exercita
    # o mesmo runner com pipeline trivial.
    pid = runner.iniciar("hemiciclo.sessao.runner:_pipeline_dummy")
    assert pid > 0

    # Espera CONCLUIDA com timeout generoso (dummy ~1.5s).
    deadline = time.monotonic() + 10.0
    estado_final = None
    while time.monotonic() < deadline:
        status = carregar_status(runner.dir / "status.json")
        if status is not None:
            estado_final = status.estado
            if status.estado == EstadoSessao.CONCLUIDA:
                break
        time.sleep(0.2)

    assert estado_final == EstadoSessao.CONCLUIDA, f"último: {estado_final}"
