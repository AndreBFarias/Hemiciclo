# ADR-013 -- Subprocess detached + status.json + pid.lock como modelo de execução

- **Status:** accepted
- **Data:** 2026-04-28
- **Decisores:** @AndreBFarias
- **Tags:** infra, sessao

## Contexto e problema

A Sessão de Pesquisa (ADR-007) pode levar minutos ou horas para concluir
(coleta + ETL + classificação + embeddings). O dashboard Streamlit precisa
mostrar progresso sem bloquear a UI; o usuário precisa fechar o navegador e
voltar; o sistema precisa detectar processos mortos sem limpeza
(crash, SIGKILL, queda de energia).

Threads Python sofrem com GIL e morrem com o processo principal. Filas tipo
Celery exigem broker (Redis/RabbitMQ) -- viola ADR-006. Async puro não
isola CPU-bound de I/O.

## Drivers de decisão

- Desacoplar UI Streamlit do trabalho pesado.
- Usuário pode fechar e reabrir o navegador sem matar a sessão.
- Detectar processo morto sem limpeza voluntária.
- Funcionar em Linux, macOS e Windows com mesmo modelo.
- Zero broker, zero daemon central.

## Opções consideradas

### Opção A -- Threads Python

- Prós: simples, sem IPC.
- Contras: GIL bloqueia CPU-bound, morre com Streamlit, sem isolamento.

### Opção B -- Celery / RQ / Dramatiq

- Prós: maduros, retry automático.
- Contras: exigem broker, violam ADR-006.

### Opção C -- Subprocess detached + status.json + pid.lock

- Prós: isolamento total, sobrevive ao Streamlit, detecção de morte via
  `psutil.pid_exists()`, funciona cross-OS, IPC trivial via JSON em disco.
- Contras: parsing de status via polling, não push.

## Decisão

Escolhida: **Opção C**.

- `subprocess.Popen` com `start_new_session=True` (POSIX) ou
  `CREATE_NEW_PROCESS_GROUP` (Windows) -- subprocess detached.
- `status.json` atualizado pelo worker em escrita atômica (`tempfile + replace`).
- `pid.lock` com PID + timestamp + checksum, escrito no startup do worker.
- Streamlit faz polling em `status.json` a cada 2s.
- `psutil.pid_exists()` detecta processo morto sem update de status >= 30s
  (marca a sessão como `INTERROMPIDA`).

## Consequências

**Positivas:**

- Fechar o navegador não mata a coleta.
- Crash do worker é detectado e a sessão é marcada `INTERROMPIDA`.
- Mesmo modelo nos 3 SOs do CI matrix (ADR-015).
- Logs por sessão em `log.txt`, isolados.

**Negativas / custos assumidos:**

- IPC por arquivo é mais lento que socket (ok para granularidade humana).
- Polling consome ciclo extra (mitigado por intervalo 2s).
- Dependência `psutil>=5.9`.

## Pendências / follow-ups

- [x] S29 implementa runner + persistencia + retomada.
- [ ] S29.1: `sessao listar` auto-detecta PID morto e marca INTERROMPIDA.
- [ ] S29.2: trocar `write_text` de pid.lock por escrita atômica.

## Links

- Sprint relacionada: S29
- Documentação: `docs/arquitetura/sessao_de_pesquisa.md`
- ADR vinculada: ADR-007 (Sessão de Pesquisa)
