"""Detecção e retomada de sessões interrompidas.

Sessão é considerada **interrompida** quando o subprocess morreu sem
publicar :class:`EstadoSessao.CONCLUIDA` ou :class:`EstadoSessao.ERRO`.
Casos típicos: ``kill -9``, máquina dormiu, runner crashou, terminal
fechou antes de detached completar.

Heurística (S29):

1. Se ``status.estado`` está em estado terminal (``CONCLUIDA``, ``ERRO``,
   ``INTERROMPIDA``, ``PAUSADA``): **NÃO interrompida**.
2. Se ``pid.lock`` aponta pra processo vivo: **NÃO interrompida** (ainda
   rodando).
3. Caso contrário (estado em andamento + PID morto OU lock ausente):
   **interrompida**.

A retomada (``retomar``) relê ``params.json`` e dispara novo subprocess
do mesmo callable. Idempotência do pipeline real é responsabilidade do
S30 -- aqui o contrato é apenas "spawnsa de novo com mesmos params".
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from hemiciclo.sessao.modelo import EstadoSessao, StatusSessao
from hemiciclo.sessao.persistencia import (
    caminho_sessao,
    carregar_params,
    carregar_status,
    salvar_status,
)
from hemiciclo.sessao.runner import SessaoRunner, pid_vivo

# Estados terminais -- não devem ser marcados como interrompidos.
ESTADOS_TERMINAIS: frozenset[EstadoSessao] = frozenset(
    {
        EstadoSessao.CONCLUIDA,
        EstadoSessao.ERRO,
        EstadoSessao.INTERROMPIDA,
        EstadoSessao.PAUSADA,
    }
)


def _eh_interrompida(sessao_dir: Path, status: StatusSessao) -> bool:
    """Decide se uma sessão está interrompida pelo critério canônico."""
    if status.estado in ESTADOS_TERMINAIS:
        return False
    return not pid_vivo(sessao_dir / "pid.lock")


def detectar_interrompidas(home: Path) -> list[tuple[str, StatusSessao]]:
    """Lista sessões em ``<home>/sessoes/`` que estão interrompidas.

    Returns:
        Lista de pares ``(id_sessao, status)`` ordenada por
        ``status.iniciada_em`` desc. Vazia se ``home/sessoes/`` não existe.
    """
    raiz = home / "sessoes"
    if not raiz.exists():
        return []

    interrompidas: list[tuple[str, StatusSessao]] = []
    for pasta in raiz.iterdir():
        if not pasta.is_dir():
            continue
        status = carregar_status(pasta / "status.json")
        if status is None:
            continue
        if _eh_interrompida(pasta, status):
            interrompidas.append((pasta.name, status))

    interrompidas.sort(key=lambda par: par[1].iniciada_em, reverse=True)
    return interrompidas


def marcar_interrompida(sessao_dir: Path, motivo: str) -> None:
    """Atualiza ``status.json`` da sessão para :class:`EstadoSessao.INTERROMPIDA`.

    Mantém ``iniciada_em`` original. Atualiza ``atualizada_em`` pro instante
    atual e popula ``mensagem`` com o motivo informado pelo chamador.

    Idempotente: se a sessão já está em estado terminal, não faz nada.
    """
    status_path = sessao_dir / "status.json"
    atual = carregar_status(status_path)
    if atual is None:
        msg = f"status.json ausente ou corrompido em {sessao_dir}"
        raise FileNotFoundError(msg)
    if atual.estado in ESTADOS_TERMINAIS:
        return

    agora = datetime.now(UTC)
    if agora < atual.iniciada_em:
        agora = atual.iniciada_em

    novo = StatusSessao(
        id=atual.id,
        estado=EstadoSessao.INTERROMPIDA,
        progresso_pct=atual.progresso_pct,
        etapa_atual=atual.etapa_atual,
        mensagem=motivo,
        iniciada_em=atual.iniciada_em,
        atualizada_em=agora,
        pid=None,
        erro=atual.erro,
    )
    salvar_status(novo, status_path)


def retomar(home: Path, id_sessao: str, callable_path: str) -> int:
    """Relê params da sessão e spawnsa novo subprocess do mesmo callable.

    Args:
        home: Raiz do Hemiciclo (``<home>/sessoes/<id>/``).
        id_sessao: Identificador da sessão a retomar.
        callable_path: ``modulo:funcao`` do pipeline (mesmo formato do
            :meth:`SessaoRunner.iniciar`). Em S30 será o pipeline real.

    Returns:
        PID do novo subprocess.

    Raises:
        FileNotFoundError: ``params.json`` ausente -- sessão não existe
            ou foi corrompida.
    """
    sessao_dir = caminho_sessao(home, id_sessao)
    params = carregar_params(sessao_dir / "params.json")
    if params is None:
        msg = f"params.json ausente ou corrompido em {sessao_dir}"
        raise FileNotFoundError(msg)

    # Marca como retomada (em andamento de novo). Reusa pasta existente:
    # construímos o runner manualmente pra preservar o id_sessao original
    # em vez de deixar o construtor gerar id novo.
    runner = SessaoRunner.__new__(SessaoRunner)
    runner.home = home
    runner.params = params
    runner.detached = True
    runner.id_sessao = id_sessao
    runner.dir = sessao_dir
    return runner.iniciar(callable_path)
