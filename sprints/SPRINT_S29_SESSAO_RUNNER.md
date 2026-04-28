# Sprint S29 -- Sessão de Pesquisa: runner subprocess + status + pid.lock + retomada

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-28
**Status:** DONE (2026-04-28)
**Depende de:** S22 (DONE), S26 (DONE)
**Bloqueia:** S30, S35
**Esforço:** M (3-5 dias)
**ADRs vinculados:** ADR-007 (sessão cidadão de primeira classe), ADR-013 (subprocess + status.json + pid.lock)
**Branch:** feature/s29-sessao-runner

---

## 1. Objetivo

Implementar o **Sessão de Pesquisa Runner** -- o cidadão de primeira classe do sistema (D7/ADR-007). Cada sessão é uma unidade autocontida em `~/hemiciclo/sessoes/<id>/` com pipeline executado via subprocess Python autônomo, comunicação via `status.json` arquivo (não memória), `pid.lock` para detecção de morte, e retomada idempotente após kill -9 / fechar navegador / máquina dormir.

Esta sprint **não roda pipeline real** -- entrega só a casca: runner, persistência, retomada, CLI. Pipeline integrado (coleta → ETL → classificar → modelar) fica em S30. O runner aceita uma callable arbitrária e executa em subprocess; em S30, essa callable será o pipeline real.

## 2. Contexto

D7 + ADR-007 estabelecem que cada busca é **unidade autocontida**: pasta com `params.json`, `status.json`, `pid.lock`, `dados.duckdb`, `discursos.parquet`, `votos.parquet`, `relatorio_state.json`, `log.txt`, `manifesto.json`.

S23 já entregou os schemas Pydantic (`ParametrosBusca`, `StatusSessao`, `EstadoSessao`) em `src/hemiciclo/sessao/modelo.py`. Esta sprint preenche o módulo `sessao/` com runner + persistência + retomada.

S26 entregou DuckDB unificado. Cada sessão pode ter seu próprio `dados.duckdb` (slice da master) ou apontar para o master via path -- decisão técnica fica nesta sprint.

S30 (próxima após S29 e S28) integra coleta + classificação no pipeline real. Aqui é só o esqueleto.

## 3. Escopo

### 3.1 In-scope

- [ ] `src/hemiciclo/sessao/__init__.py` — re-exporta principais
- [ ] **`src/hemiciclo/sessao/persistencia.py`**:
  - `gerar_id_sessao(params: ParametrosBusca) -> str` -- gera slug + timestamp único
  - `caminho_sessao(home: Path, id_sessao: str) -> Path` -- `<home>/sessoes/<id>/`
  - `salvar_params(params: ParametrosBusca, path: Path) -> None` -- escrita atômica
  - `carregar_params(path: Path) -> ParametrosBusca | None`
  - `salvar_status(status: StatusSessao, path: Path) -> None` -- escrita atômica
  - `carregar_status(path: Path) -> StatusSessao | None`
  - `listar_sessoes(home: Path) -> list[tuple[str, ParametrosBusca, StatusSessao]]` ordenado por iniciada_em desc
  - `deletar_sessao(home: Path, id_sessao: str) -> None`
- [ ] **`src/hemiciclo/sessao/runner.py`**:
  - `class SessaoRunner`:
    - `__init__(self, home: Path, params: ParametrosBusca)` cria sessão (id + pasta + params.json + status inicial)
    - `iniciar(self, callable: Callable[[ParametrosBusca, Path, StatusUpdater], None]) -> int` spawnsa subprocess.Popen, retorna PID
    - `_rodar_em_subprocess(callable, params, sessao_dir)` função que vai pra subprocess (executa callable + atualiza status)
    - Persiste `pid.lock` com PID + timestamp + checksum
    - Retorna imediatamente sem bloquear (subprocess detached)
  - `class StatusUpdater`:
    - Wrapper que o pipeline chama para atualizar `status.json`
    - `atualizar(estado: EstadoSessao, progresso_pct: float, etapa: str, mensagem: str)`
    - Escrita atômica via tmpfile + replace
  - `pid_vivo(pid_lock_path: Path) -> bool` -- verifica se PID no lockfile ainda existe (`os.kill(pid, 0)` em Linux/macOS, `tasklist` em Windows -- usar `psutil` se possível)
- [ ] **`src/hemiciclo/sessao/retomada.py`**:
  - `detectar_interrompidas(home: Path) -> list[tuple[str, StatusSessao]]` -- sessões com `status.estado != concluida` E (PID não vivo OU status sem update há > 5min)
  - `marcar_interrompida(sessao_dir: Path, motivo: str) -> None` -- atualiza status pra `INTERROMPIDA`
  - `retomar(home: Path, id_sessao: str, callable) -> int` -- relê params, spawnsa novo subprocess, callable deve ser idempotente (cabe ao S30 garantir)
- [ ] **`src/hemiciclo/sessao/exportador.py`** stub:
  - `exportar_zip(sessao_dir: Path, destino: Path) -> Path` -- zipa pasta da sessão (sem cache de modelos/db, só metadados + parquets)
  - `importar_zip(zip_path: Path, home: Path) -> str` -- valida hashes (manifesto.json), extrai pra `home/sessoes/<id>/`
  - Implementação completa fica em S35; aqui é só o stub de zipar/extrair
- [ ] **CLI `hemiciclo sessao`** com 6 ações:
  - `hemiciclo sessao iniciar --topico ... [--casas camara senado] [--max-itens 100]` cria sessão e dispara pipeline DUMMY (callable que só dorme 2s e atualiza status; pipeline real fica em S30)
  - `hemiciclo sessao listar` lista sessões ordenadas por data
  - `hemiciclo sessao status <id>` mostra `status.json` formatado
  - `hemiciclo sessao retomar <id>` retoma interrompida
  - `hemiciclo sessao pausar <id>` envia SIGTERM (graceful)
  - `hemiciclo sessao cancelar <id>` envia SIGKILL + marca status erro
- [ ] Pipeline DUMMY de teste (`_pipeline_dummy(params, sessao_dir, updater)`) em `src/hemiciclo/sessao/runner.py`:
  - Atualiza progresso 0%→25%→50%→75%→100% com sleep 0.5s entre
  - Estados: COLETANDO → ETL → MODELANDO → CONCLUIDA
  - Permite teste e2e do runner sem dep de coleta real
- [ ] **Testes unit** em `tests/unit/test_sessao_persistencia.py` (6 testes):
  - `test_gerar_id_unico`
  - `test_salvar_carregar_params_round_trip`
  - `test_salvar_status_atomico`
  - `test_listar_sessoes_ordenadas`
  - `test_deletar_remove_pasta`
  - `test_arquivo_corrompido_retorna_none`
- [ ] **Testes unit** em `tests/unit/test_sessao_runner.py` (5 testes):
  - `test_runner_cria_pasta_e_arquivos_iniciais`
  - `test_runner_spawnsa_subprocess_e_retorna_pid`
  - `test_status_updater_atomic_write`
  - `test_pid_vivo_detecta_processo_existente`
  - `test_pid_vivo_detecta_pid_morto`
- [ ] **Testes unit** em `tests/unit/test_sessao_retomada.py` (4 testes):
  - `test_detectar_sessao_completa_nao_eh_interrompida`
  - `test_detectar_sessao_em_andamento_pid_vivo_nao_eh_interrompida`
  - `test_detectar_sessao_pid_morto_eh_interrompida`
  - `test_marcar_interrompida_atualiza_status`
- [ ] **Testes integração** em `tests/integracao/test_sessao_e2e.py` (3 testes):
  - `test_pipeline_dummy_completa_em_3s` -- executa pipeline dummy via runner, espera concluída, verifica progresso final 100%
  - `test_kill_subprocess_marca_interrompida` -- inicia, kill -9, detecta como interrompida
  - `test_workflow_iniciar_listar_status_cli` -- ciclo via CLI
- [ ] **Sentinelas** em `test_sentinela.py` (2):
  - `test_sessao_help` (com COLUMNS=200)
  - `test_sessao_listar_vazio`
- [ ] **`docs/arquitetura/sessao_de_pesquisa.md`** documentando: layout pasta sessão, ciclo de vida, detecção de morte, retomada
- [ ] **CHANGELOG.md** entrada `[Unreleased]` com bullet `feat(sessao): runner subprocess + persistência + retomada`

### 3.2 Out-of-scope (explícito)

- **Pipeline real** (coleta + ETL + classificar) -- fica em S30
- **Exportação/importação completa com manifesto.json + verificação de integridade** -- fica em S35 (stub aqui)
- **Streamlit polling em status.json** -- já está stub em S23, integração real fica em S31
- **Modelo bge-m3** -- fica em S28
- **Convertibilidade ML** -- fica em S34

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `src/hemiciclo/sessao/persistencia.py` | Read/write atômico da pasta da sessão |
| `src/hemiciclo/sessao/runner.py` | SessaoRunner + StatusUpdater + pipeline dummy |
| `src/hemiciclo/sessao/retomada.py` | Detecção e retomada de sessões interrompidas |
| `src/hemiciclo/sessao/exportador.py` | Stub zip/unzip |
| `tests/unit/test_sessao_persistencia.py` | 6 testes |
| `tests/unit/test_sessao_runner.py` | 5 testes |
| `tests/unit/test_sessao_retomada.py` | 4 testes |
| `tests/integracao/test_sessao_e2e.py` | 3 testes |
| `docs/arquitetura/sessao_de_pesquisa.md` | Documentação técnica |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `src/hemiciclo/sessao/__init__.py` | Re-exporta runner/persistencia/retomada |
| `src/hemiciclo/cli.py` | Subcomando `sessao` (iniciar/listar/status/retomar/pausar/cancelar) |
| `tests/unit/test_sentinela.py` | 2 testes sessao CLI |
| `pyproject.toml` | Adiciona `psutil>=5.9` (PID checking cross-OS) |
| `uv.lock` | Regenerado |
| `CHANGELOG.md` | Entrada [Unreleased] |
| `sprints/ORDEM.md` | S29 -> DONE |

## 5. Implementação detalhada

### 5.1 Layout da pasta da sessão

```
~/hemiciclo/sessoes/<slug>_<timestamp>/
  params.json       # ParametrosBusca serializado
  status.json       # StatusSessao, atualizado pelo subprocess
  pid.lock          # PID + iniciado_em + checksum
  log.txt           # Loguru rotacionado por sessão
  manifesto.json    # Hashes dos artefatos (preenchido em S30/S35)
  dados.duckdb      # Banco da sessão (S30)
  discursos.parquet # (S30)
  votos.parquet     # (S30)
  modelos_locais/   # (S30/S28)
```

### 5.2 Trecho de referência -- `runner.py` esqueleto

```python
"""Runner de sessão de pesquisa."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from hemiciclo.sessao.modelo import EstadoSessao, ParametrosBusca, StatusSessao
from hemiciclo.sessao.persistencia import (
    caminho_sessao,
    gerar_id_sessao,
    salvar_params,
    salvar_status,
)


class StatusUpdater:
    """Wrapper que o pipeline chama para atualizar status.json."""

    def __init__(self, sessao_dir: Path, id_sessao: str) -> None:
        self._dir = sessao_dir
        self._id = id_sessao

    def atualizar(
        self, estado: EstadoSessao, progresso_pct: float, etapa: str, mensagem: str
    ) -> None:
        agora = datetime.now(timezone.utc)
        status = StatusSessao(
            id=self._id,
            estado=estado,
            progresso_pct=progresso_pct,
            etapa_atual=etapa,
            mensagem=mensagem,
            iniciada_em=agora,  # placeholder; manter primeira via load
            atualizada_em=agora,
            pid=os.getpid(),
        )
        salvar_status(status, self._dir / "status.json")


class SessaoRunner:
    def __init__(self, home: Path, params: ParametrosBusca) -> None:
        self.home = home
        self.params = params
        self.id_sessao = gerar_id_sessao(params)
        self.dir = caminho_sessao(home, self.id_sessao)
        self.dir.mkdir(parents=True, exist_ok=True)
        salvar_params(params, self.dir / "params.json")
        # Status inicial CRIADA
        agora = datetime.now(timezone.utc)
        salvar_status(
            StatusSessao(
                id=self.id_sessao, estado=EstadoSessao.CRIADA,
                progresso_pct=0.0, etapa_atual="criada",
                mensagem="Sessao criada, aguardando inicio",
                iniciada_em=agora, atualizada_em=agora,
            ),
            self.dir / "status.json",
        )

    def iniciar(self, callable_path: str) -> int:
        """Spawnsa subprocess Python invocando o callable via importlib.

        callable_path: 'modulo.submodulo:funcao' (ex: 'hemiciclo.sessao.runner:_pipeline_dummy')
        """
        cmd = [
            sys.executable, "-m", "hemiciclo._sessao_worker",
            "--callable", callable_path,
            "--sessao-dir", str(self.dir),
        ]
        proc = subprocess.Popen(cmd, start_new_session=True)
        # Persiste pid.lock
        (self.dir / "pid.lock").write_text(
            f"{proc.pid}\n{datetime.now(timezone.utc).isoformat()}\n",
            encoding="utf-8",
        )
        return proc.pid


def _pipeline_dummy(params: ParametrosBusca, sessao_dir: Path, updater: StatusUpdater) -> None:
    """Pipeline dummy para testar runner sem dep de coleta real."""
    import time
    updater.atualizar(EstadoSessao.COLETANDO, 25.0, "coletando", "Coleta dummy")
    time.sleep(0.5)
    updater.atualizar(EstadoSessao.ETL, 50.0, "etl", "ETL dummy")
    time.sleep(0.5)
    updater.atualizar(EstadoSessao.MODELANDO, 75.0, "modelando", "Modelagem dummy")
    time.sleep(0.5)
    updater.atualizar(EstadoSessao.CONCLUIDA, 100.0, "concluida", "Pipeline dummy concluido")
```

### 5.3 `_sessao_worker` -- entrypoint do subprocess

```python
"""Entrypoint subprocess pra sessao runner.

Invocado via: python -m hemiciclo._sessao_worker --callable mod:func --sessao-dir /...
"""
# ... importlib resolve callable, carrega params, chama com StatusUpdater
```

### 5.4 Detecção de PID vivo (cross-OS via psutil)

```python
def pid_vivo(pid_lock_path: Path) -> bool:
    if not pid_lock_path.exists():
        return False
    try:
        pid = int(pid_lock_path.read_text().split("\n")[0])
        import psutil
        return psutil.pid_exists(pid)
    except (ValueError, FileNotFoundError):
        return False
```

### 5.5 Passo a passo

1. Confirmar branch.
2. Adicionar `psutil>=5.9` deps + types stubs em dev.
3. Implementar `persistencia.py` (8 funções).
4. Escrever `test_sessao_persistencia.py` (6 testes).
5. Implementar `runner.py` (`SessaoRunner`, `StatusUpdater`, `pid_vivo`, `_pipeline_dummy`).
6. Criar `src/hemiciclo/_sessao_worker.py` (entrypoint do subprocess).
7. Escrever `test_sessao_runner.py` (5 testes).
8. Implementar `retomada.py` (`detectar_interrompidas`, `marcar_interrompida`, `retomar`).
9. Escrever `test_sessao_retomada.py` (4 testes).
10. Implementar `exportador.py` stub (zipar pasta + validar checksum básico).
11. Adicionar subcomando `sessao` ao CLI Typer.
12. Escrever `test_sentinela.py` adições.
13. Escrever `tests/integracao/test_sessao_e2e.py` (3 testes).
14. Escrever `docs/arquitetura/sessao_de_pesquisa.md`.
15. Atualizar CHANGELOG.
16. Smoke local: `hemiciclo sessao iniciar --topico aborto && sleep 3 && hemiciclo sessao listar` deve mostrar sessão CONCLUIDA.
17. `make check` ≥ 90%.
18. Atualizar ORDEM.md.

## 6. Testes (resumo)

- 6 persistencia + 5 runner + 4 retomada + 3 e2e + 2 sentinela = **20 testes novos**
- Suite total: 222 + 20 = 242 testes

## 7. Proof-of-work runtime-real

```bash
$ make check
$ uv run hemiciclo sessao iniciar --topico aborto
[sessao][iniciar] sessao=aborto_<timestamp> pid=<N>

$ sleep 3 && uv run hemiciclo sessao listar
ID                          ESTADO       PROGRESSO   INICIADA_EM
aborto_<timestamp>          CONCLUIDA    100.0%      <date>

$ uv run hemiciclo sessao status aborto_<timestamp>
{
  "id": "aborto_<timestamp>",
  "estado": "concluida",
  "progresso_pct": 100.0,
  "etapa_atual": "concluida",
  ...
}
```

**Critério de aceite:**

- [ ] `make check` 242 testes verdes, cobertura ≥ 90%
- [ ] `sessao iniciar` cria pasta + spawnsa subprocess + retorna PID
- [ ] Subprocess executa `_pipeline_dummy` em ~2s e marca CONCLUIDA
- [ ] `sessao listar` mostra sessões em ordem desc
- [ ] kill -9 do PID + `sessao listar` detecta como INTERROMPIDA
- [ ] Mypy/ruff zero
- [ ] Hook + CI verdes

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Subprocess detached comportamento diferente Linux/macOS/Windows | psutil + `start_new_session=True` (Linux/macOS) + `subprocess.CREATE_NEW_PROCESS_GROUP` (Windows) |
| status.json corrompido em concorrência | Escrita atômica tmpfile + replace (precedente S24) |
| PID reusado pelo OS após morte | Lockfile inclui timestamp + checksum mas detecção é só "pid existe"; aceitável |
| Pipeline dummy nem termina antes do test e2e | Default sleep 0.5s × 3 etapas = 1.5s; teste espera com timeout 10s |
| Runner em CI sem permissão de detached | `start_new_session=False` em testes (subprocess regular) |

## 9. Validação multi-agente

Padrão executor → validador → integração.

## 10. Próximo passo após DONE

S30 (pipeline integrado) substitui `_pipeline_dummy` por callable real. S35 estende `exportador.py` com manifesto + integridade.
