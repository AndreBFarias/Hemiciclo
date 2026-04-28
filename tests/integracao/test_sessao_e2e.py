"""Testes end-to-end da Sessão de Pesquisa (S29).

Exercitam o caminho real sem mocks:

- spawn de subprocess Popen detached
- worker entrypoint via ``python -m``
- importlib resolvendo callable
- StatusUpdater publicando em status.json no subprocess
- CLI Typer disparando + listando + status

Cada teste tem timeout razoável; o pipeline dummy nominal completa em 1.5s.
"""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hemiciclo.cli import app
from hemiciclo.sessao.modelo import Casa, EstadoSessao, ParametrosBusca
from hemiciclo.sessao.persistencia import carregar_status
from hemiciclo.sessao.retomada import detectar_interrompidas, marcar_interrompida
from hemiciclo.sessao.runner import SessaoRunner


def _esperar_estado(
    sessao_dir: Path,
    estado_alvo: EstadoSessao,
    timeout: float = 10.0,
) -> EstadoSessao | None:
    """Faz polling de ``status.json`` até atingir ``estado_alvo`` ou timeout."""
    deadline = time.monotonic() + timeout
    ultimo: EstadoSessao | None = None
    while time.monotonic() < deadline:
        status = carregar_status(sessao_dir / "status.json")
        if status is not None:
            ultimo = status.estado
            if status.estado == estado_alvo:
                return status.estado
        time.sleep(0.2)
    return ultimo


def test_pipeline_dummy_completa_em_3s(tmp_path: Path) -> None:
    """Runner real -> pipeline dummy -> CONCLUIDA em < 10s, progresso 100%."""
    runner = SessaoRunner(
        tmp_path,
        ParametrosBusca(topico="aborto", casas=[Casa.CAMARA], legislaturas=[57]),
    )
    runner.iniciar("hemiciclo.sessao.runner:_pipeline_dummy")

    estado = _esperar_estado(runner.dir, EstadoSessao.CONCLUIDA, timeout=10.0)
    assert estado == EstadoSessao.CONCLUIDA, f"último estado: {estado}"

    status = carregar_status(runner.dir / "status.json")
    assert status is not None
    assert status.progresso_pct == 100.0
    assert (runner.dir / "dummy_artefato.txt").exists()


def test_kill_subprocess_marca_interrompida(tmp_path: Path) -> None:
    """SIGKILL do subprocess + ``marcar_interrompida`` produz INTERROMPIDA."""
    runner = SessaoRunner(
        tmp_path,
        ParametrosBusca(topico="aborto", casas=[Casa.CAMARA], legislaturas=[57]),
    )
    pid = runner.iniciar("hemiciclo.sessao.runner:_pipeline_dummy")

    # Espera o subprocess sair de CRIADA pra estado em-andamento.
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        st = carregar_status(runner.dir / "status.json")
        if st and st.estado != EstadoSessao.CRIADA:
            break
        time.sleep(0.1)

    # Kill no PID do subprocess. SIGKILL no POSIX, SIGTERM no Windows.
    sinal_kill = getattr(signal, "SIGKILL", signal.SIGTERM)
    try:
        os.kill(pid, sinal_kill)
    except ProcessLookupError:
        pytest.skip("subprocess saiu antes do SIGKILL (pipeline dummy completou rápido demais)")

    # Garante que o processo terminou antes de detectar.
    time.sleep(0.3)

    # Agora detectar deve apontar a sessão como interrompida.
    interrompidas = detectar_interrompidas(tmp_path)
    ids = {t[0] for t in interrompidas}
    assert runner.id_sessao in ids, f"esperava {runner.id_sessao} em {ids}"

    # Marca explicitamente e verifica o estado final.
    marcar_interrompida(runner.dir, "kill -9 simulado")
    status = carregar_status(runner.dir / "status.json")
    assert status is not None
    assert status.estado == EstadoSessao.INTERROMPIDA


def test_workflow_iniciar_listar_status_cli(
    tmp_hemiciclo_home: Path,
) -> None:
    """Ciclo via CLI: iniciar -> aguardar -> listar -> status."""
    runner_cli = CliRunner()

    # 1) iniciar -- com --dummy mantemos compat S29 em e2e (sem rede)
    r1 = runner_cli.invoke(
        app,
        ["sessao", "iniciar", "--topico", "aborto", "--dummy"],
    )
    assert r1.exit_code == 0, r1.stdout
    assert "sessao iniciar:" in r1.stdout
    assert "sessao=" in r1.stdout
    assert "pid=" in r1.stdout
    assert "pipeline=dummy" in r1.stdout

    # Extrai id da saída ("sessao=<id> pid=...")
    linha = next(ln for ln in r1.stdout.splitlines() if "sessao=" in ln)
    id_sessao = linha.split("sessao=")[1].split(" ")[0].strip()
    sessao_dir = tmp_hemiciclo_home / "sessoes" / id_sessao

    # 2) Espera concluir.
    estado = _esperar_estado(sessao_dir, EstadoSessao.CONCLUIDA, timeout=10.0)
    assert estado == EstadoSessao.CONCLUIDA, f"último estado: {estado}"

    # 3) listar deve mostrar a sessão concluída.
    r2 = runner_cli.invoke(
        app,
        ["sessao", "listar"],
        env={**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"},
    )
    assert r2.exit_code == 0
    assert id_sessao in r2.stdout
    assert "concluida" in r2.stdout

    # 4) status mostra JSON completo.
    r3 = runner_cli.invoke(app, ["sessao", "status", id_sessao])
    assert r3.exit_code == 0
    assert id_sessao in r3.stdout
    assert "concluida" in r3.stdout
    assert "100.0" in r3.stdout
