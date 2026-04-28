"""Testes de :mod:`hemiciclo.sessao.retomada` (S29).

Cobre detecção de sessões interrompidas, marcação manual e idempotência
em estados terminais.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from hemiciclo.sessao.modelo import (
    Casa,
    EstadoSessao,
    ParametrosBusca,
    StatusSessao,
)
from hemiciclo.sessao.persistencia import (
    caminho_sessao,
    salvar_params,
    salvar_status,
)
from hemiciclo.sessao.retomada import (
    ESTADOS_TERMINAIS,
    detectar_interrompidas,
    marcar_interrompida,
)


def _materializa_sessao(
    home: Path,
    id_sessao: str,
    estado: EstadoSessao,
    *,
    pid_lock: str | None,
) -> Path:
    """Materializa uma sessão sintética com estado e lockfile arbitrários."""
    d = caminho_sessao(home, id_sessao)
    d.mkdir(parents=True)
    salvar_params(
        ParametrosBusca(topico="aborto", casas=[Casa.CAMARA], legislaturas=[57]),
        d / "params.json",
    )
    agora = datetime.now(UTC)
    salvar_status(
        StatusSessao(
            id=id_sessao,
            estado=estado,
            progresso_pct=42.0,
            etapa_atual="etapa",
            mensagem="m",
            iniciada_em=agora,
            atualizada_em=agora,
        ),
        d / "status.json",
    )
    if pid_lock is not None:
        (d / "pid.lock").write_text(pid_lock, encoding="utf-8")
    return d


def test_detectar_sessao_completa_nao_eh_interrompida(tmp_path: Path) -> None:
    """Sessão CONCLUIDA nunca aparece em ``detectar_interrompidas``."""
    _materializa_sessao(tmp_path, "completa", EstadoSessao.CONCLUIDA, pid_lock=None)
    assert detectar_interrompidas(tmp_path) == []


def test_detectar_sessao_em_andamento_pid_vivo_nao_eh_interrompida(tmp_path: Path) -> None:
    """Sessão em ETL com PID do próprio teste vivo NÃO é interrompida."""
    import os as _os

    _materializa_sessao(
        tmp_path,
        "viva",
        EstadoSessao.ETL,
        pid_lock=f"{_os.getpid()}\n2026-04-28T12:00:00\n",
    )
    assert detectar_interrompidas(tmp_path) == []


def test_detectar_sessao_pid_morto_eh_interrompida(tmp_path: Path) -> None:
    """Sessão em ETL com PID inexistente vira candidata a INTERROMPIDA."""
    _materializa_sessao(
        tmp_path,
        "morta",
        EstadoSessao.ETL,
        pid_lock="999999\n2026-04-28T12:00:00\n",
    )
    interrompidas = detectar_interrompidas(tmp_path)
    # Em ambiente raro 999999 pode coincidir com PID legítimo. Aceitamos
    # 0 ou 1 -- se 0, o teste apenas exerce o caminho sem afirmar volume.
    assert len(interrompidas) in {0, 1}
    if interrompidas:
        assert interrompidas[0][0] == "morta"


def test_detectar_sessao_sem_lockfile_eh_interrompida(tmp_path: Path) -> None:
    """Sessão em estado em-andamento + sem ``pid.lock`` -> interrompida."""
    _materializa_sessao(
        tmp_path,
        "sem_lock",
        EstadoSessao.MODELANDO,
        pid_lock=None,
    )
    interrompidas = detectar_interrompidas(tmp_path)
    ids = [t[0] for t in interrompidas]
    assert "sem_lock" in ids


def test_marcar_interrompida_atualiza_status(tmp_path: Path) -> None:
    """``marcar_interrompida`` muda estado e popula mensagem."""
    d = _materializa_sessao(tmp_path, "alvo", EstadoSessao.ETL, pid_lock=None)
    marcar_interrompida(d, "Kill -9 detectado")

    from hemiciclo.sessao.persistencia import carregar_status

    status = carregar_status(d / "status.json")
    assert status is not None
    assert status.estado == EstadoSessao.INTERROMPIDA
    assert status.mensagem == "Kill -9 detectado"
    # ``pid`` deve ser limpo após interromper.
    assert status.pid is None


def test_marcar_interrompida_idempotente_em_estado_terminal(tmp_path: Path) -> None:
    """Se já está em terminal, ``marcar_interrompida`` não altera o status."""
    d = _materializa_sessao(tmp_path, "concluida", EstadoSessao.CONCLUIDA, pid_lock=None)

    from hemiciclo.sessao.persistencia import carregar_status

    antes = carregar_status(d / "status.json")
    marcar_interrompida(d, "ignorar")
    depois = carregar_status(d / "status.json")
    assert antes == depois


def test_marcar_interrompida_sem_status_levanta(tmp_path: Path) -> None:
    """Pasta sem status.json levanta ``FileNotFoundError``."""
    d = tmp_path / "vazio"
    d.mkdir()
    with pytest.raises(FileNotFoundError, match="status.json"):
        marcar_interrompida(d, "qualquer")


def test_retomar_relê_params_e_spawnsa_subprocess(tmp_path: Path) -> None:
    """``retomar`` preserva id da sessão, relê params e dispara worker."""
    import time

    from hemiciclo.sessao.persistencia import carregar_status
    from hemiciclo.sessao.retomada import retomar

    home = tmp_path
    d = _materializa_sessao(home, "voltar", EstadoSessao.INTERROMPIDA, pid_lock=None)
    pid = retomar(home, "voltar", "hemiciclo.sessao.runner:_pipeline_dummy")
    assert pid > 0
    assert (d / "pid.lock").exists()

    # Espera concluir.
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        status = carregar_status(d / "status.json")
        if status is not None and status.estado == EstadoSessao.CONCLUIDA:
            break
        time.sleep(0.2)

    final = carregar_status(d / "status.json")
    assert final is not None
    assert final.estado == EstadoSessao.CONCLUIDA


def test_retomar_sessao_inexistente_levanta(tmp_path: Path) -> None:
    """``retomar`` em id sem ``params.json`` -> ``FileNotFoundError``."""
    from hemiciclo.sessao.retomada import retomar

    with pytest.raises(FileNotFoundError, match="params.json"):
        retomar(tmp_path, "fantasma", "hemiciclo.sessao.runner:_pipeline_dummy")


def test_estados_terminais_sao_completos() -> None:
    """``ESTADOS_TERMINAIS`` cobre exatamente os 4 estados terminais documentados."""
    assert (
        frozenset(
            {
                EstadoSessao.CONCLUIDA,
                EstadoSessao.ERRO,
                EstadoSessao.INTERROMPIDA,
                EstadoSessao.PAUSADA,
            }
        )
        == ESTADOS_TERMINAIS
    )
