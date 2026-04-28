"""Runner subprocess da Sessão de Pesquisa.

Spawna um processo Python detached que executa um *callable arbitrário*
(``modulo:funcao`` resolvido por :mod:`importlib`) com 3 argumentos:

1. :class:`ParametrosBusca` carregado da pasta da sessão
2. :class:`pathlib.Path` para a pasta da sessão
3. :class:`StatusUpdater` que o callable usa pra publicar progresso

O callable em si é resolvido pelo entrypoint :mod:`hemiciclo._sessao_worker`
(separado pra ser importável por ``python -m`` em subprocess novo).

Por que **string** em vez de função Python? Funções não atravessam
fronteiras de processo de forma serializável segura, e ``multiprocessing.spawn``
exige imports puros. Passar ``modulo:funcao`` como CLI arg + ``importlib``
resolve no subprocess é o caminho idiomático (precedente: pytest entry-points,
Celery tasks).

ADRs vinculados: ADR-007 (sessão cidadão de primeira classe), ADR-013
(subprocess + status.json + pid.lock).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil

from hemiciclo.sessao.modelo import EstadoSessao, ParametrosBusca, StatusSessao
from hemiciclo.sessao.persistencia import (
    caminho_sessao,
    carregar_status,
    gerar_id_sessao,
    salvar_params,
    salvar_status,
)


class StatusUpdater:
    """Wrapper que o pipeline chama pra atualizar ``status.json``.

    Preserva ``iniciada_em`` da primeira escrita relendo o status atual
    a cada update -- assim o pipeline não precisa carregar o instante de
    início manualmente.

    Escrita é atômica via :func:`salvar_status` (tmpfile + replace).
    """

    def __init__(self, sessao_dir: Path, id_sessao: str) -> None:
        self._dir = sessao_dir
        self._id = id_sessao
        self._iniciada_em: datetime | None = None

    def _resolver_iniciada_em(self) -> datetime:
        """Retorna ``iniciada_em`` cacheado ou o relê do status persistido."""
        if self._iniciada_em is not None:
            return self._iniciada_em
        atual = carregar_status(self._dir / "status.json")
        if atual is not None:
            self._iniciada_em = atual.iniciada_em
        else:
            self._iniciada_em = datetime.now(UTC)
        return self._iniciada_em

    def atualizar(
        self,
        estado: EstadoSessao,
        progresso_pct: float,
        etapa: str,
        mensagem: str = "",
        erro: str | None = None,
    ) -> None:
        """Publica um snapshot novo de :class:`StatusSessao` no disco."""
        agora = datetime.now(UTC)
        iniciada_em = self._resolver_iniciada_em()
        # ``atualizada_em`` precisa ser >= ``iniciada_em`` (validator do modelo).
        # Em situações de relógio ruim ou cache inicial, garantimos isso.
        if agora < iniciada_em:
            agora = iniciada_em
        status = StatusSessao(
            id=self._id,
            estado=estado,
            progresso_pct=progresso_pct,
            etapa_atual=etapa,
            mensagem=mensagem,
            iniciada_em=iniciada_em,
            atualizada_em=agora,
            pid=os.getpid(),
            erro=erro,
        )
        salvar_status(status, self._dir / "status.json")


class SessaoRunner:
    """Cria pasta de sessão e spawnsa subprocess Python autônomo.

    O subprocess é detached (``start_new_session=True`` em POSIX,
    ``CREATE_NEW_PROCESS_GROUP`` em Windows) -- sobrevive a fechar o
    Streamlit, terminal pai morto, etc. Em testes CI alguns hosts proíbem
    detach; passe ``detached=False`` no construtor pra rodar inline.
    """

    def __init__(
        self,
        home: Path,
        params: ParametrosBusca,
        *,
        detached: bool = True,
    ) -> None:
        self.home = home
        self.params = params
        self.detached = detached
        self.id_sessao = gerar_id_sessao(params)
        self.dir = caminho_sessao(home, self.id_sessao)
        self.dir.mkdir(parents=True, exist_ok=True)
        salvar_params(params, self.dir / "params.json")

        agora = datetime.now(UTC)
        salvar_status(
            StatusSessao(
                id=self.id_sessao,
                estado=EstadoSessao.CRIADA,
                progresso_pct=0.0,
                etapa_atual="criada",
                mensagem="Sessão criada, aguardando início",
                iniciada_em=agora,
                atualizada_em=agora,
            ),
            self.dir / "status.json",
        )

    def _spawn(self, cmd: list[str]) -> subprocess.Popen[bytes]:
        """Invoca :class:`subprocess.Popen` com kwargs corretos para o OS.

        Mantém ``Popen`` chamado com argumentos *explícitos* (em vez de
        ``**kwargs`` opaco) pra preservar a tipagem estrita do mypy.

        - POSIX detached: ``start_new_session=True``.
        - Windows detached: ``creationflags=CREATE_NEW_PROCESS_GROUP``.
        - ``detached=False``: chama Popen sem flags (testes inline).
        """
        if not self.detached:
            return subprocess.Popen(cmd)
        if sys.platform == "win32":
            return subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        return subprocess.Popen(cmd, start_new_session=True)

    def iniciar(self, callable_path: str) -> int:
        """Spawnsa subprocess invocando ``callable_path`` e retorna o PID.

        Args:
            callable_path: Especificação ``modulo.submodulo:funcao``
                (ex.: ``hemiciclo.sessao.runner:_pipeline_dummy``). O
                worker resolve via :mod:`importlib` no subprocess.

        Returns:
            PID do subprocess recém-spawnado (também persistido em
            ``pid.lock`` na pasta da sessão).
        """
        cmd = [
            sys.executable,
            "-m",
            "hemiciclo._sessao_worker",
            "--callable",
            callable_path,
            "--sessao-dir",
            str(self.dir),
        ]
        proc = self._spawn(cmd)
        agora = datetime.now(UTC)
        (self.dir / "pid.lock").write_text(
            f"{proc.pid}\n{agora.isoformat()}\n",
            encoding="utf-8",
        )
        return proc.pid


def pid_vivo(pid_lock_path: Path) -> bool:
    """Verifica se o PID gravado em ``pid.lock`` ainda está vivo.

    Usa :mod:`psutil` por ser cross-OS (Linux, macOS, Windows). Considera
    zumbis como mortos -- um processo zumbi não consegue mais publicar
    status, portanto a sessão deve ser tratada como interrompida.

    Returns:
        ``True`` se o PID está vivo e não-zumbi. ``False`` se o lockfile
        não existe, está malformado, ou o PID já saiu.
    """
    if not pid_lock_path.exists():
        return False
    try:
        primeira_linha = pid_lock_path.read_text(encoding="utf-8").split("\n")[0].strip()
        pid = int(primeira_linha)
    except (ValueError, OSError):
        return False
    if not psutil.pid_exists(pid):
        return False
    try:
        proc = psutil.Process(pid)
        return proc.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


# ---------------------------------------------------------------------------
# Pipeline DUMMY de teste
# ---------------------------------------------------------------------------


def _pipeline_dummy(
    params: ParametrosBusca,
    sessao_dir: Path,
    updater: StatusUpdater,
) -> None:
    """Pipeline dummy pra testar o runner sem dep de coleta real.

    Avança 4 etapas (COLETANDO -> ETL -> MODELANDO -> CONCLUIDA) com
    sleep de 0.5s entre transições. Total ~1.5-2s de execução. O
    pipeline real (S30) substitui isto por coleta + ETL + classificação.

    O parâmetro ``params`` é aceito (não ignorado) pra documentar o
    contrato esperado dos pipelines reais; aqui apenas o ``topico`` é
    referenciado nas mensagens.
    """
    updater.atualizar(
        EstadoSessao.COLETANDO,
        25.0,
        "coletando",
        f"Coleta dummy do tópico {params.topico}",
    )
    time.sleep(0.5)
    updater.atualizar(EstadoSessao.ETL, 50.0, "etl", "ETL dummy")
    time.sleep(0.5)
    updater.atualizar(EstadoSessao.MODELANDO, 75.0, "modelando", "Modelagem dummy")
    time.sleep(0.5)
    updater.atualizar(
        EstadoSessao.CONCLUIDA,
        100.0,
        "concluida",
        "Pipeline dummy concluído",
    )
    # Marca artefato simbólico pra testes verificarem que o pipeline
    # realmente passou pelo subprocess, não só atualizou status.
    (sessao_dir / "dummy_artefato.txt").write_text("ok\n", encoding="utf-8")
