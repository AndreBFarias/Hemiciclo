# Sprint S38.4 -- "Iniciar pesquisa" dispara pipeline_real (P0 funcional)

**Projeto:** Hemiciclo
**Versão alvo:** v2.1.1
**Data criação:** 2026-04-28
**Revisado em:** 2026-04-28 (correções de API contra base 98aad25)
**Autor:** @AndreBFarias
**Status:** READY
**Depende de:** S30 (DONE), S29 (DONE)
**Bloqueia:** uso real do dashboard pelo cidadão João
**Esforço:** P-M (~1-2h)
**Branch sugerida:** feature/s38-4-iniciar-pesquisa-real
**Prioridade:** **P0 -- BUG CRÍTICO DE RELEASE**

---

## 1. Objetivo

Trocar o stub legacy da S23 em `dashboard/paginas/nova_pesquisa.py` por uma chamada real que dispara `pipeline_real` via `SessaoRunner` (S29) e redireciona o usuário para `sessao_detalhe` com polling de progresso.

## 2. Contexto

Bug encontrado em smoke real do browser pós v2.1.0: clicar "Iniciar pesquisa" no dashboard gera apenas:

```
Rascunho salvo em /home/.../sessoes/aborto_rascunho. Quando o pipeline real
for liberado, esta pesquisa estará pronta para retomar de onde parou.

Funcionalidade chega em S30 -- coleta, ETL, classificação multicamada e
modelagem rodam no seu computador em background.
```

Mas **S30, S30.1 e S30.2 já estão mergeadas** em main. O `pipeline_real` é disparável via CLI: `uv run hemiciclo sessao iniciar --topico aborto`. O dashboard apenas não foi atualizado para usar a infra que já existe.

## 3. Escopo

### 3.1 Arquivos tocados

- **Modificar:** `src/hemiciclo/dashboard/paginas/nova_pesquisa.py`
- **Modificar:** `tests/unit/test_dashboard_paginas.py` (adicionar caso novo; convenção do projeto, não criar arquivo separado)
- **NÃO TOCAR:** `src/hemiciclo/sessao/runner.py`, `src/hemiciclo/sessao/pipeline.py`, `src/hemiciclo/sessao/modelo.py`, `src/hemiciclo/dashboard/paginas/sessao_detalhe.py`

### 3.2 In-scope

- Em `nova_pesquisa.py`, **substituir bloco de linhas 199-211** (chamada `_persistir_rascunho(...)` + `st.success(...)` + `st.info(...)`) por:
  1. `cfg.garantir_diretorios()` (caso usuário fresh-install)
  2. Instanciar `runner = SessaoRunner(cfg.home, params)` (params já validado em try/except `ValidationError` linhas 180-197 -- preservar esse bloco)
  3. Chamar `pid = runner.iniciar(_PIPELINE_REAL_PATH)` onde `_PIPELINE_REAL_PATH = "hemiciclo.sessao.pipeline:pipeline_real"` (constante local na página, mesmo padrão do `cli.py:580`)
  4. Setar `st.session_state["sessao_id"] = runner.id_sessao` (chave canônica do projeto, NÃO `sessao_id_ativa`)
  5. Setar `st.session_state["pagina_ativa"] = "sessao_detalhe"`
  6. `logger.info("Sessão {id} iniciada via dashboard, pid={pid}", ...)`
  7. `st.rerun()` para navegar imediatamente
- **Deletar** funções órfãs após a substituição:
  - `_persistir_rascunho` (linhas 50-60) -- não tem mais callers
  - `_estimar_tempo_e_espaco` (linhas 63-81) -- texto de estimativa some junto com o `st.info` legacy
- Tratamento de erros (mensagens PT-BR amigáveis, sem traceback):
  - `ValidationError` Pydantic -- já existe (linhas 191-197), preservar como está
  - `OSError` (falha ao criar pasta da sessão / escrever `params.json`) -- novo: `st.error("Não foi possível criar a sessão: {erro}. Verifique permissões em ~/hemiciclo/sessoes/.")` + `return`
  - Falha em `runner.iniciar` (Popen) -- novo: capturar `OSError`/`FileNotFoundError` em torno do spawn; `st.error("Não foi possível iniciar o pipeline: {erro}.")` + `return`
- Atualizar/remover bloco de "estimativa" -- o usuário verá progresso real em `sessao_detalhe` (polling 2s já implementado em `_renderizar_em_andamento`, linha 376)

### 3.3 Out-of-scope

- Estimativa precisa de tempo (depende de medição empírica que pode ser sprint própria)
- Cancelar pipeline em andamento via UI (já funciona via CLI: `hemiciclo sessao cancelar <id>`)
- Suporte ao pipeline DUMMY no dashboard (CLI tem `--dummy`, dashboard segue só real -- se necessário em testes locais, usar CLI direto)

## 4. API real confirmada (anti-divergência)

Base `98aad25`. Estes são os contratos exatos -- spec original tinha imprecisões:

```python
# src/hemiciclo/sessao/runner.py:99
class SessaoRunner:
    def __init__(self, home: Path, params: ParametrosBusca, *, detached: bool = True) -> None: ...
    def iniciar(self, callable_path: str) -> int: ...   # NÃO recebe params; recebe string "modulo:funcao"
    # atributos pós-init: self.id_sessao, self.dir
```

```python
# src/hemiciclo/cli.py:579-580 (constantes a replicar)
_PIPELINE_DUMMY_PATH = "hemiciclo.sessao.runner:_pipeline_dummy"
_PIPELINE_REAL_PATH = "hemiciclo.sessao.pipeline:pipeline_real"
```

Padrão precedente em `cli.py:668-670`:
```python
runner = SessaoRunner(cfg.home, params)
callable_path = _PIPELINE_DUMMY_PATH if dummy else _PIPELINE_REAL_PATH
pid = runner.iniciar(callable_path)
```

`sessao_detalhe.py:446` lê `st.session_state.get("sessao_id")` -- **chave é `sessao_id`** (não `sessao_id_ativa`). Demais consumidores: `lista_sessoes.py:120`, `importar.py:96`. Padrão idêntico ao já vigente.

## 5. Testes

Adicionar a `tests/unit/test_dashboard_paginas.py` (convenção do projeto -- evitar criar arquivo novo):

- `test_nova_pesquisa_iniciar_dispara_runner_real`:
  - Usa `streamlit.testing.v1.AppTest`
  - Monkeypatch `hemiciclo.dashboard.paginas.nova_pesquisa.SessaoRunner` para mock que NÃO faz spawn (atributo `id_sessao = "fake-123"`, método `iniciar` retorna PID 99999)
  - Preenche form, submete
  - Asserts:
    - `SessaoRunner` chamado com `(cfg.home, params_pydantic)` onde params bate com form
    - `iniciar` chamado com `"hemiciclo.sessao.pipeline:pipeline_real"`
    - `st.session_state["sessao_id"] == "fake-123"`
    - `st.session_state["pagina_ativa"] == "sessao_detalhe"`
- `test_nova_pesquisa_validation_error_mantem_pagina`: form inválido (tópico vazio) -> NÃO chama SessaoRunner, NÃO muda `pagina_ativa`
- `test_nova_pesquisa_oserror_em_iniciar`: SessaoRunner mock levanta `OSError` em `iniciar` -> `st.error` chamado, `pagina_ativa` permanece em `nova_pesquisa`

**Mock obrigatório:** subprocess real spawnaria pipeline_real (rede + ETL, ~30min). Tests unit MUST mockar `SessaoRunner` na pagina (pelo nome importado). Padrão precedente em `tests/unit/test_sentinela.py:408-415` (`runner_module.SessaoRunner.__init__`).

Cobertura mínima do diff: >= 90% (I9).

## 6. Proof-of-work (validação obrigatória)

### 6.1 Smoke real no browser (lição 4 -- v2.1.0 saiu quebrada por skip disso)

```bash
# Sobe dashboard em background
nohup uv run streamlit run src/hemiciclo/dashboard/app.py --server.headless true > /tmp/hemiciclo_dash.log 2>&1 &
DASH_PID=$!
sleep 8

# Valida processo vivo e porta aberta
ps -p $DASH_PID && curl -sI http://localhost:8501 | head -1

# Marca timestamp ANTES do click (filtro pra evidência)
TS_INICIO=$(date +%s)

# Skill validacao-visual: navega para Nova pesquisa, preenche tópico "smoke",
# casas=Câmara, legislatura=57, max_itens=10, clica Iniciar
# Captura PNG + sha256 da página de progresso (sessao_detalhe)

# Evidência: sessão criada DEPOIS do TS_INICIO com status.json válido
find ~/hemiciclo/sessoes -maxdepth 1 -type d -newer /tmp/ts_inicio_marker -name "*smoke*" -exec ls -la {}/status.json \;

# Subprocess do pipeline vivo
ps aux | grep -E "_sessao_worker|pipeline_real" | grep -v grep

# Cleanup
kill $DASH_PID
```

Critério mínimo de evidência (não basta print do botão):
- [ ] `~/hemiciclo/sessoes/<sessao_id>/status.json` criado com mtime > TS_INICIO
- [ ] `~/hemiciclo/sessoes/<sessao_id>/params.json` contém `topico: "smoke"`
- [ ] Processo `python -m hemiciclo._sessao_worker` aparece em `ps aux` (PID match com `pid.lock`)
- [ ] PNG da `sessao_detalhe` mostra widget de progresso (`progresso_sessao`) renderizando

### 6.2 Suite automatizada

```bash
uv run pytest tests/unit/test_dashboard_paginas.py -v -k nova_pesquisa
uv run pytest tests/unit/test_dashboard_paginas.py --cov=src/hemiciclo/dashboard/paginas/nova_pesquisa --cov-report=term-missing
```

Cobertura `nova_pesquisa.py` >= 90% pós-mudança.

### 6.3 Lint + tipos

```bash
uv run ruff check src/hemiciclo/dashboard/paginas/nova_pesquisa.py tests/unit/test_dashboard_paginas.py
uv run ruff format --check src/hemiciclo/dashboard/paginas/nova_pesquisa.py tests/unit/test_dashboard_paginas.py
uv run mypy --strict src/hemiciclo/dashboard/paginas/nova_pesquisa.py
```

### 6.4 Acentuação periférica (I2)

`grep -nP "[ÀàÁáÂâÃãÉéÊêÍíÓóÔôÕõÚúÇç]" src/hemiciclo/dashboard/paginas/nova_pesquisa.py` -- todos os textos PT-BR visíveis ao usuário com acentuação correta.

### 6.5 Hipótese verificada (lição 4)

Antes de codar, executor confirma:
```bash
grep -n "class SessaoRunner" src/hemiciclo/sessao/runner.py
grep -n "_PIPELINE_REAL_PATH" src/hemiciclo/cli.py
grep -rn 'st.session_state\["sessao_id"\]' src/hemiciclo/dashboard/paginas/
```
Se algum grep não retornar a linha esperada, parar e replanejar.

## 7. Invariantes a preservar

- **I1** (tudo local): `pipeline_real` já é local; nada novo a verificar.
- **I2** (PT-BR com acentuação): mensagens de erro novas (OSError, falha spawn) com á/é/í/ó/ú/ç corretos.
- **I4** (sem print): usar `loguru.logger` (já importado linha 16).
- **I5** (sem TODO solto): não introduzir TODOs sem ID.
- **I6** (Pydantic estrito): manter `ParametrosBusca` como contrato; não passar dict.
- **I7** (mypy strict): tipar tudo; sem `Any` em assinatura pública.
- Anti-débito: funções `_persistir_rascunho` e `_estimar_tempo_e_espaco` ficam órfãs após a sub e DEVEM ser deletadas no mesmo commit. Não deixar para "limpeza depois".

## 8. Riscos

- **Subprocess órfão se Streamlit cai.** Mitigação: já existe `pid.lock` (S29) + `retomada.py` detecta INTERROMPIDA via `pid_vivo()`.
- **Dashboard fica esperando muito tempo.** Mitigação: redirect IMEDIATO via `st.rerun()`; polling em outra tela (`sessao_detalhe._renderizar_em_andamento`, intervalo 2s).
- **Click duplo gera duas sessões.** Streamlit `st.form_submit_button` já protege contra isso na mesma execução; rerun pós-click muda página antes de novo render.
- **Mock de teste vaza spawn real.** Mitigação: monkeypatch no símbolo importado pelo módulo (`hemiciclo.dashboard.paginas.nova_pesquisa.SessaoRunner`), não no original.

## 9. Próximo passo após DONE

Smoke real ponta-a-ponta: usuário comum consegue clicar form -> ver dashboard -> exportar zip. Esse smoke faz parte de v2.1.1 release-readiness, não desta sprint.

## 10. Referências

- BRIEF: `VALIDATOR_BRIEF.md` (raiz do repo)
- Padrão precedente: `src/hemiciclo/cli.py:579-675` (sessão CLI iniciar)
- Padrão de mock SessaoRunner: `tests/unit/test_sentinela.py:408-415`
- Polling existente: `src/hemiciclo/dashboard/paginas/sessao_detalhe.py:376-406`
