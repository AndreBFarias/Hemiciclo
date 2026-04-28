# Sessão de Pesquisa -- runner subprocess + status + retomada

> Documento técnico da S29. Cobre o cidadão de primeira classe do produto
> (D7 / ADR-007 do plano R2): cada busca cidadã é uma **unidade autocontida**
> em ``~/hemiciclo/sessoes/<id>/``, com pipeline executado em subprocess
> Python detached, comunicação via arquivo, e retomada idempotente após
> kill -9 / fechar navegador / máquina dormir.

## Layout da pasta da sessão

```
~/hemiciclo/sessoes/<slug>_<UTC-timestamp>/
  params.json         # ParametrosBusca serializado (Pydantic v2)
  status.json         # StatusSessao, atualizado pelo subprocess
  pid.lock            # PID + ISO timestamp (1 linha cada)
  log.txt             # Loguru rotacionado por sessão (S30+)
  manifesto.json      # Hashes SHA256 dos artefatos (preenchido em S30/S35)
  dummy_artefato.txt  # Marcador do pipeline dummy (apagado em S30)
  dados.duckdb        # Banco da sessão (S30)
  discursos.parquet   # (S30)
  votos.parquet       # (S30)
  modelos_locais/     # Ajuste fino do modelo base (S28/S30)
```

O id é gerado por :func:`hemiciclo.sessao.persistencia.gerar_id_sessao`
combinando slug ASCII do tópico (acentos removidos, símbolos viram ``_``)
com timestamp UTC com precisão de microssegundos -- duas sessões
disparadas em sequência rápida nunca colidem.

## Ciclo de vida

```
                    + ---------- + iniciar
                    |   CRIADA   | -----> COLETANDO --> ETL --> EMBEDDINGS
                    + ---------- +              |          |          |
                                                v          v          v
   PAUSADA <-- pausar (SIGTERM) -- {qualquer}            MODELANDO --> CONCLUIDA
                                                                         |
   INTERROMPIDA <-- kill -9 / morte sem update -- {qualquer não-terminal}
   ERRO          <-- exceção não tratada no pipeline   --                |
                                                                         v
                                                              {estado terminal}
```

Estados em :class:`hemiciclo.sessao.modelo.EstadoSessao`. Estados
terminais (``CONCLUIDA``, ``ERRO``, ``INTERROMPIDA``, ``PAUSADA``) ficam
em :data:`hemiciclo.sessao.retomada.ESTADOS_TERMINAIS` e são imunes a
``marcar_interrompida`` (idempotente).

## Como o runner spawnsa o subprocess

A classe :class:`hemiciclo.sessao.runner.SessaoRunner`:

1. No construtor, cria a pasta ``<home>/sessoes/<id>/`` e persiste
   ``params.json`` + ``status.json`` (estado ``CRIADA``).
2. Em ``iniciar(callable_path)``, monta o comando::

       python -m hemiciclo._sessao_worker
           --callable hemiciclo.sessao.runner:_pipeline_dummy
           --sessao-dir <pasta>

   e invoca :func:`subprocess.Popen`:
   - **POSIX** (Linux/macOS): ``start_new_session=True`` cria um
     *session leader* independente, imune ao SIGHUP do shell pai.
   - **Windows**: ``creationflags=subprocess.CREATE_NEW_PROCESS_GROUP``
     desacopla do console pai e permite enviar ``CTRL_BREAK_EVENT``.
   - **Modo testes** (``detached=False``): chama Popen sem flags --
     útil em hosts CI restritivos.
3. Persiste ``pid.lock`` com PID + timestamp ISO 8601 (UTF-8, 2 linhas).

O *callable* é passado como **string** (``modulo:funcao``) por dois motivos:

1. Funções não atravessam fronteiras de processo de forma serializável
   segura -- ``multiprocessing.spawn`` exige imports puros de qualquer
   forma.
2. O entrypoint :mod:`hemiciclo._sessao_worker` resolve o callable via
   :mod:`importlib`, carrega ``params.json``, instancia
   :class:`StatusUpdater` e invoca a função. Caminho clean, sem mágica.

Por que ``hemiciclo._sessao_worker`` mora **fora** de ``hemiciclo.sessao``?
Pra evitar import circular com o próprio runner que o spawnsa e pra que
``python -m`` resolva sem nenhum lazy-import no submódulo.

## Detecção de morte (pid.lock)

A função :func:`hemiciclo.sessao.runner.pid_vivo` lê o PID do
``pid.lock`` e usa :mod:`psutil` (cross-OS) pra checar:

- ``psutil.pid_exists(pid)`` -- existe processo com esse PID?
- ``psutil.Process(pid).status() != STATUS_ZOMBIE`` -- não é zumbi?

Caminhos negativos (lockfile ausente, conteúdo corrompido, processo
inexistente, zumbi, ``AccessDenied``) **todos** retornam ``False`` -- é
suficiente pra que ``detectar_interrompidas`` trate a sessão como morta.

PIDs reusados pelo OS após morte são um risco aceitável nesta sprint
(o lockfile inclui timestamp mas a verificação atual não compara). S35
ou sprint posterior pode endurecer com fingerprint do executável.

## Retomada

:func:`hemiciclo.sessao.retomada.detectar_interrompidas` itera todas as
sessões em ``<home>/sessoes/`` e marca como interrompida quem
satisfaz **ambas** condições:

1. ``status.estado`` NÃO em ``ESTADOS_TERMINAIS``.
2. ``pid_vivo(pid.lock)`` retorna ``False``.

:func:`hemiciclo.sessao.retomada.retomar` relê ``params.json``, instancia
um runner *sem* refazer o id (preserva pasta original) e dispara um
subprocess novo do mesmo callable. **Idempotência do pipeline real é
responsabilidade do S30** -- aqui o contrato é apenas "spawnsa de novo
com mesmos params". O pipeline dummy não tem estado persistente, então
retomar é sempre seguro.

## CLI

Subcomando :mod:`hemiciclo.cli` ``sessao`` com 6 ações::

    hemiciclo sessao iniciar --topico aborto [--casas camara senado] [--legislatura 57]
    hemiciclo sessao listar
    hemiciclo sessao status <id>
    hemiciclo sessao retomar <id>
    hemiciclo sessao pausar <id>     # SIGTERM
    hemiciclo sessao cancelar <id>   # SIGKILL + INTERROMPIDA

Mensagens usam ``key=value`` em vez de ``[tag][nome]`` pra evitar que
``rich.markup`` interprete nomes de tópicos como style tags (mesma
lição da S27).

## Smoke local end-to-end

```bash
$ uv run hemiciclo sessao iniciar --topico aborto
sessao iniciar: sessao=aborto_20260428T120015_123456 pid=42001

$ sleep 3 && uv run hemiciclo sessao listar
ID                                               ESTADO         PROGRESSO  INICIADA_EM
aborto_20260428T120015_123456                    concluida      100.0%     2026-04-28 12:00:15

$ uv run hemiciclo sessao status aborto_20260428T120015_123456
{
  "id": "aborto_20260428T120015_123456",
  "estado": "concluida",
  "progresso_pct": 100.0,
  "etapa_atual": "concluida",
  "mensagem": "Pipeline dummy concluído",
  "iniciada_em": "...",
  "atualizada_em": "...",
  "pid": 42002,
  "erro": null
}
```

## Próximas sprints

- **S30** (pipeline integrado): substitui ``_pipeline_dummy`` pelo
  pipeline real (coleta + ETL + classificar + projetar) preservando
  o contrato ``(params, sessao_dir, updater) -> None``.
- **S31** (dashboard): polling em ``status.json`` no Streamlit.
- **S35** (export): :func:`hemiciclo.sessao.exportador.exportar_zip` ganha
  manifesto.json com SHA256 dos artefatos + verificação de integridade
  na importação.
