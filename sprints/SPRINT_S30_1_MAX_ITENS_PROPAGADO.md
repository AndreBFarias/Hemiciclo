# Sprint S30.1 -- Propagar `--max-itens` de `sessao iniciar` para `ParametrosColeta` da Câmara e do Senado

**Projeto:** Hemiciclo
**Versão alvo:** v2.1.0 (sprint 6/7 do ciclo de polimento pós-v2.0)
**Data criação:** 2026-04-28
**Status:** READY
**Depende de:** S30 (DONE)
**Bloqueia:** -- (sprint folha; destrava UX rápida do dashboard e smoke-real local)
**Esforço:** P (1 dia)
**ADRs vinculados:** ADR-007 (Sessão de Pesquisa cidadã de primeira classe), ADR-006 (tudo local)
**Branch:** `feature/s30-1-max-itens-propagado`

---

## 1. Objetivo

Tornar útil o flag `--max-itens N` do subcomando `hemiciclo sessao iniciar`, hoje placeholder herdado da S30 (`# noqa: ARG001 -- placeholder pra S30` em `src/hemiciclo/cli.py:592`). O valor passado pelo usuário deve atravessar a camada de modelo da sessão (`ParametrosBusca`) e chegar nos coletores reais Câmara/Senado dentro do `pipeline_real`, onde já existe o parâmetro `max_itens` no schema `ParametrosColeta` (`src/hemiciclo/coleta/__init__.py:65`) e no contrato runtime de `executar_coleta` das duas casas (`src/hemiciclo/coleta/camara.py:508`, `src/hemiciclo/coleta/senado.py:604`).

Sem isso, **toda sessão coleta o universo completo** de proposições, votações, votos e discursos das duas casas. Em rede doméstica isso significa 30-60 minutos por sessão, inviabilizando smoke-real local, demo de dashboard, dev iterativo e validação visual rápida de UI da S31. Após esta sprint, `hemiciclo sessao iniciar --topico aborto --max-itens 50` deve concluir em **menos de 2 minutos** com sessão `concluida` e relatório válido (mas amostral).

## 2. Contexto

S30 entregou o orquestrador `pipeline_real` em `src/hemiciclo/sessao/pipeline.py` (765 linhas) com 5 etapas mais grafos (S32), histórico (S33) e convertibilidade (S34). A função `_etapa_coleta` (linhas 161-203) constrói `ParametrosColeta` para Câmara e Senado **sem passar `max_itens`**, ou seja, sempre coleta full.

Coletores e CLI já estão prontos:

- `ParametrosColeta` aceita `max_itens: int | None = Field(default=None, ge=1)` (S24/S25 já validam isso).
- `executar_coleta` da Câmara propaga `max_itens=params.max_itens` para os 3 sub-coletores em uso no pipeline (proposicoes 567, votacoes 622, discursos 670).
- `executar_coleta` do Senado idem (676, 729, 773).
- `hemiciclo coletar camara/senado --max-itens N` já funciona standalone (lições S24/S25).

**O elo faltante é só:** `ParametrosBusca` -> `ParametrosColeta` no `_etapa_coleta`. Esta sprint fecha o circuito.

A entrada na ORDEM.md (linha 53) já lista S30.1 como READY com escopo "Propagar `--max-itens` de `sessao iniciar` em ParametrosColeta de Camara/Senado" e esforço P.

## 3. Escopo

### 3.1 In-scope

- [ ] **`src/hemiciclo/sessao/modelo.py`** -- adicionar campo `max_itens: int | None` em `ParametrosBusca`:
  - Default `None` (preserva comportamento full atual; compat).
  - Validador Pydantic: aceita `None` ou inteiro com `ge=1` (alinhado a `ParametrosColeta`; rejeita 0 e negativos).
  - Docstring explícita: "Limite de itens por tipo coletado por casa. None = sem limite (universo completo). Aplicado por casa: max_itens=N coleta no máximo N itens da Câmara e N do Senado, totalizando até 2N quando ambas as casas estão em params.casas."
  - Re-exportar via `src/hemiciclo/sessao/__init__.py` se já não exportado (apenas `ParametrosBusca` importado, campo novo segue automaticamente).

- [ ] **`src/hemiciclo/sessao/pipeline.py`** -- propagar `max_itens` em `_etapa_coleta`:
  - Linha ~179: `params_camara = ParametrosColeta(..., max_itens=params.max_itens, dir_saida=raw)`.
  - Linha ~195: `params_senado = ParametrosColeta(..., max_itens=params.max_itens, dir_saida=raw)`.
  - Sem mais nenhuma mudança nas etapas posteriores: ETL, C1+C2, C3, grafos, histórico, convertibilidade processam tudo o que coleta entregar (escopo restrito por design -- ver §3.2).
  - Atualizar docstring do `pipeline_real` (linha 68 em diante) com nota: "Quando `params.max_itens` é fornecido, a coleta limita N itens por tipo por casa. Etapas subsequentes operam sobre a amostra coletada -- sem propagação adicional."

- [ ] **`src/hemiciclo/cli.py`** -- ativar o flag `--max-itens`:
  - Remover `# noqa: ARG001 -- placeholder pra S30` da linha 592.
  - Atualizar `help` do flag: "Limite de itens por tipo coletado por casa (default sem limite). Útil para smoke local e dashboards rápidos. Ex.: --max-itens 50 coleta até 50 proposições da Câmara e 50 do Senado."
  - Passar `max_itens=max_itens` na construção de `ParametrosBusca(...)` (linha 620).
  - Sem mudar default (`None`) nem assinatura do flag (já existe).

- [ ] **`docs/arquitetura/pipeline_integrado.md`** -- adicionar seção curta:
  - Subseção "Limite de coleta (`max_itens`)" após o diagrama das 5 etapas.
  - Documentar que limita apenas a coleta (etapa 1) e cada casa recebe N independentemente.
  - Anotar tempos típicos observados: full ~30-60min, `--max-itens 50` ~1-2min em rede doméstica.

- [ ] **Testes unit** em `tests/unit/test_pipeline_real.py` (já existe -- adicionar 5 testes novos, sem renomear os 8 herdados):
  1. `test_max_itens_default_none_preserva_comportamento_full` -- `ParametrosBusca(...)` sem `max_itens` resulta em `params.max_itens is None` e `_etapa_coleta` chama coletor mockado com `max_itens=None`.
  2. `test_max_itens_valor_propaga_em_camara_e_senado` -- `ParametrosBusca(..., max_itens=10)` chama Câmara e Senado mockados com `params_coleta.max_itens == 10` em ambas.
  3. `test_max_itens_zero_rejeitado_pydantic` -- `ParametrosBusca(..., max_itens=0)` levanta `pydantic.ValidationError`.
  4. `test_max_itens_negativo_rejeitado_pydantic` -- idem para `-5`.
  5. `test_etapa_etl_e_classificacao_nao_recebem_max_itens` -- mocks de `consolidar_parquets_em_duckdb` e `classificar` confirmam que nenhum kwarg `max_itens` é passado (out-of-scope explícito; defesa contra propagação acidental).

- [ ] **Testes unit** em `tests/unit/test_sessao_modelo.py` (existir? verificar; adicionar suite se não houver -- mais provável `test_modelo.py` ou similar):
  1. `test_parametros_busca_max_itens_default_none` -- instância sem campo aceita.
  2. `test_parametros_busca_max_itens_valido_inteiro_positivo` -- `max_itens=42` aceito.
  3. `test_parametros_busca_max_itens_zero_rejeitado` -- `ValidationError`.

  *(Total: 5 testes pipeline + 3 testes modelo = 8 unit novos. Se `test_sessao_modelo.py` não existir, criar -- mas verificar primeiro o nome real do arquivo de teste do `ParametrosBusca`. Lição S29 indica que existe cobertura Pydantic dos schemas.)*

- [ ] **Sentinela CLI** em `tests/unit/test_sentinela.py`:
  1. `test_sessao_iniciar_aceita_max_itens_smoke` -- `runner.invoke(app, ["sessao", "iniciar", "--topico", "aborto", "--max-itens", "5"])` com `SessaoRunner.iniciar` mockado retorna exit 0 e mensagem "pipeline=real".
  2. `test_sessao_iniciar_max_itens_zero_falha_com_mensagem_amigavel` -- exit code != 0, stderr/stdout cita "max_itens" ou "ge=1" (mensagem do Pydantic).

- [ ] **`CHANGELOG.md`** entrada `[Unreleased]`:
  ```
  ### Fixed
  - S30.1: `--max-itens` de `hemiciclo sessao iniciar` agora propaga para os
    coletores Câmara/Senado dentro do pipeline real. Sessão amostral conclui
    em ~1-2 min com `--max-itens 50` em vez de 30-60 min full.
  ```

- [ ] **`sprints/ORDEM.md`** -- mover S30.1 de READY para DONE no rodapé (linha 53) e registrar entrada de progresso na seção de logs por data.

### 3.2 Out-of-scope (explícito -- anti-débito; sprints novas se aparecerem)

- **Limites por etapa pós-coleta** (ETL, C1+C2, C3, grafos, histórico, convertibilidade). `max_itens` aplica-se **apenas** à coleta. Etapas subsequentes operam sobre 100% da amostra coletada. Se aparecer necessidade de limitar, por exemplo, "top 50 parlamentares no relatório", abrir sprint nova `S30.4 -- Limites por etapa do pipeline`.
- **Estimativa de tempo restante** na UI (S31). Quando dashboard mostrar progresso, faz sentido exibir "ETA ~90s" baseado em `max_itens`. Fica para sprint nova `S31.1 -- ETA por etapa em status.json`.
- **Quotas por tópico/casa**. Hoje `max_itens=N` aplica-se uniformemente. Se aparecer pedido por `--max-itens-camara 100 --max-itens-senado 30`, abrir sprint nova `S30.5 -- Limites por casa`.
- **Limite por tipo dentro de uma casa** (ex.: 50 proposições mas 200 votos). `executar_coleta` já propaga uniformemente; mexer aqui exigiria mudar o coletor. Não nesta sprint.
- **Persistência do `max_itens` em `manifesto.json`** -- desejável mas hoje `params.json` já registra. Auditor lê `params.json`. Não duplicar.
- **Mudar `ge=1` de `ParametrosColeta`** para `ge=0`. O contrato existente (`ge=1`) é correto: `max_itens=0` é absurdo (coletar zero não faz sentido; usar `None` para "sem limite"). Manter `ge=1` em ambos os schemas e expor erro Pydantic claro.

## 4. Entregas

### 4.1 Arquivos criados

Nenhum. Sprint puramente de fechamento de circuito existente.

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `src/hemiciclo/sessao/modelo.py` | Campo `max_itens: int | None = Field(default=None, ge=1, description=...)` em `ParametrosBusca` |
| `src/hemiciclo/sessao/pipeline.py` | `_etapa_coleta` passa `max_itens=params.max_itens` em `ParametrosColeta` Câmara e Senado; docstring de `pipeline_real` atualizada |
| `src/hemiciclo/cli.py` | Remove `noqa: ARG001`; passa `max_itens=max_itens` em `ParametrosBusca(...)`; help atualizado |
| `tests/unit/test_pipeline_real.py` | +5 testes (default None, propagação, zero rejeitado, negativo rejeitado, defesa não-propagação para ETL/C1) |
| `tests/unit/test_sessao_modelo.py` (ou nome equivalente -- verificar) | +3 testes Pydantic |
| `tests/unit/test_sentinela.py` | +2 sentinelas CLI |
| `docs/arquitetura/pipeline_integrado.md` | Subseção "Limite de coleta (`max_itens`)" |
| `CHANGELOG.md` | Entrada `[Unreleased]` Fixed |
| `sprints/ORDEM.md` | S30.1 READY -> DONE; log de progresso |

## 5. Implementação detalhada

### 5.1 Patch em `src/hemiciclo/sessao/modelo.py`

Após o campo `incluir_convertibilidade` (linha ~143), inserir:

```python
max_itens: int | None = Field(
    default=None,
    ge=1,
    description=(
        "Limite de itens por tipo coletado por casa. ``None`` = sem limite "
        "(universo completo). Aplicado por casa: ``max_itens=N`` coleta no "
        "máximo N itens da Câmara e N do Senado, totalizando até 2N quando "
        "ambas as casas estão em ``params.casas``. Útil para smoke local "
        "(``--max-itens 50`` ~1-2 min vs full ~30-60 min)."
    ),
)
```

Sem `field_validator` adicional -- `ge=1` cobre rejeição de 0 e negativos via Pydantic. Sem `model_validator` (campo independente).

### 5.2 Patch em `src/hemiciclo/sessao/pipeline.py`

Em `_etapa_coleta` (linhas 161-203), nas duas construções de `ParametrosColeta`:

```python
params_camara = ParametrosColeta(
    legislaturas=list(params.legislaturas),
    tipos=_tipos_camara(),
    data_inicio=params.data_inicio,
    data_fim=params.data_fim,
    max_itens=params.max_itens,  # <-- NOVO
    dir_saida=raw,
)
```

Análogo para `params_senado`. O `executar_coleta` já consome `params.max_itens` internamente (verificado em `coleta/camara.py:567` e `coleta/senado.py:676`).

Atualizar docstring de `pipeline_real` (após linha 78, antes do `try:`):

```python
"""...
Args:
    params: Parâmetros validados da sessão. Quando ``params.max_itens``
        é fornecido (default ``None``), a etapa de coleta limita N
        itens por tipo por casa. Etapas posteriores (ETL, C1+C2, C3,
        grafos, histórico, convertibilidade) operam sobre toda a
        amostra coletada -- sem propagação adicional.
    sessao_dir: Pasta da sessão (já criada pelo runner).
    updater: Publicador de progresso em ``status.json``.
"""
```

### 5.3 Patch em `src/hemiciclo/cli.py`

Linhas 592-596 antes:
```python
max_itens: int | None = typer.Option(  # noqa: ARG001 -- placeholder pra S30
    None,
    "--max-itens",
    help="Limite de itens (placeholder; pipeline real usa em S30).",
),
```

Depois:
```python
max_itens: int | None = typer.Option(
    None,
    "--max-itens",
    help=(
        "Limite de itens por tipo coletado por casa (default sem limite). "
        "Útil para smoke local e dashboards rápidos. "
        "Ex.: --max-itens 50 coleta até 50 proposições da Câmara e 50 do Senado."
    ),
),
```

E na construção de `ParametrosBusca` (linha 620):
```python
params = ParametrosBusca(
    topico=topico,
    casas=casas_enum,
    legislaturas=list(legislaturas),
    max_itens=max_itens,  # <-- NOVO
)
```

### 5.4 Passo a passo

1. Confirmar branch `feature/s30-1-max-itens-propagado` criada do `main`.
2. **Hipótese verificada com grep** (lição 4): rodar `rg "max_itens" src/hemiciclo/coleta/ src/hemiciclo/sessao/ src/hemiciclo/cli.py` e confirmar:
   - `coleta/__init__.py:65` define `max_itens: int | None = Field(default=None, ge=1)`.
   - `coleta/camara.py:508` e `coleta/senado.py:604` -- `executar_coleta` propaga `params.max_itens` para sub-coletores.
   - `sessao/modelo.py` -- **não cita `max_itens`** (este é o gap a fechar).
   - `cli.py:592` -- `max_itens` é flag mas marcada `noqa: ARG001 -- placeholder pra S30`.
   - `sessao/pipeline.py:179, 195` -- constrói `ParametrosColeta` sem `max_itens`.
3. Editar `src/hemiciclo/sessao/modelo.py`: adicionar campo `max_itens` em `ParametrosBusca` (5.1).
4. Editar `src/hemiciclo/sessao/pipeline.py`: propagar nas duas construções (5.2). Atualizar docstring.
5. Editar `src/hemiciclo/cli.py`: remover `noqa`, atualizar help, passar `max_itens=max_itens` (5.3).
6. Adicionar 5 testes em `tests/unit/test_pipeline_real.py` (mocks de `executar_coleta` Câmara e Senado capturando `params_coleta` recebido).
7. Localizar arquivo de teste de `ParametrosBusca` (`rg "ParametrosBusca" tests/unit/`); adicionar 3 testes Pydantic.
8. Adicionar 2 sentinelas em `tests/unit/test_sentinela.py`.
9. Atualizar `docs/arquitetura/pipeline_integrado.md` com subseção "Limite de coleta (`max_itens`)".
10. Atualizar `CHANGELOG.md` em `[Unreleased]`.
11. Rodar `make check` -- 0 violações ruff/mypy strict, todos os testes verdes, cobertura ≥ 90% nos arquivos modificados.
12. **Smoke real local opcional** (não bloqueia merge se rede offline): `time uv run hemiciclo sessao iniciar --topico aborto --max-itens 30 --casas camara`. Aguardar até `hemiciclo sessao listar` mostrar `concluida`. Validar tempo total < 2min e `n_proposicoes_coletadas <= ~30` na seção do relatório.
13. Atualizar `sprints/ORDEM.md`: linha 53 S30.1 -> DONE; adicionar linha de progresso na seção de logs.

## 6. Aritmética da cobertura e linhas

Sprint puramente de propagação. Sem extração nem refatoração de tamanho. Verificações:

- **`src/hemiciclo/sessao/modelo.py`:** 240L atuais + ~10L (campo novo + docstring) = ~250L. Sem meta superior; estável.
- **`src/hemiciclo/sessao/pipeline.py`:** 765L atuais + ~4L (2 atribuições + docstring update) = ~769L. Confortável bem abaixo de qualquer limite implícito (precedente S30 nasceu com 765L sem flag de tamanho).
- **`src/hemiciclo/cli.py`:** 1367L atuais + ~6L (help expandido) -1L (noqa removido) +1L (kwarg em ParametrosBusca) = ~1373L. Sem meta superior.
- **Cobertura:** I9 exige ≥ 90% em arquivos novos. Aqui são arquivos **existentes modificados**. Os 3 caminhos novos (campo Pydantic, propagação Câmara, propagação Senado) precisam ter teste cobrindo todas as ramificações. Os 5 testes pipeline + 3 testes modelo + 2 sentinelas (10 testes novos) garantem 100% das linhas adicionadas.
- **Total testes:** 378 herdados (S35 último) + 10 novos = 388 testes na suite após sprint.

## 7. Testes

| Arquivo | Testes novos |
|---|---|
| `tests/unit/test_pipeline_real.py` | 5 |
| `tests/unit/test_sessao_modelo.py` (ou nome equivalente) | 3 |
| `tests/unit/test_sentinela.py` | 2 |

**Total: 10 testes novos.**

Mocks chave:

- `monkeypatch.setattr("hemiciclo.coleta.camara.executar_coleta", spy_camara)` onde `spy_camara` captura `params: ParametrosColeta` e expõe via list mutável.
- Análogo para Senado.
- Verificação: `assert spy_camara.calls[0].max_itens == esperado`.

Baseline: FAIL_BEFORE = 0 (suite verde após S35). FAIL_AFTER esperado = 0.

## 8. Proof-of-work runtime-real

```bash
$ uv run pytest tests/unit -v -k "max_itens or sentinela_sessao_iniciar" 2>&1 | tail -30
$ uv run mypy --strict src
$ uv run ruff check src tests
$ uv run ruff format --check src tests
$ make check
```

**Smoke real opcional** (depende de rede pública para api.camara.leg.br; CI sempre pula):

```bash
$ time uv run hemiciclo sessao iniciar --topico aborto --max-itens 30 --casas camara
sessao iniciar: sessao=<id> pid=<pid> pipeline=real
$ sleep 90 && uv run hemiciclo sessao listar | grep concluida
<id>  concluida  ...
$ # Tempo total esperado: < 2min com max-itens 30 (vs ~15-30min full só Câmara)
```

**Critério de aceite:**

- [ ] `make check` 388 testes verdes, cobertura ≥ 90% nos 3 arquivos modificados (`modelo.py`, `pipeline.py`, `cli.py`)
- [ ] `--max-itens` deixa de ser placeholder; aparece corretamente em `ParametrosBusca.max_itens` na sessão criada (verificável por `cat ~/hemiciclo/sessoes/<id>/params.json` mostrando `"max_itens": N`)
- [ ] Coletores Câmara e Senado recebem `params_coleta.max_itens == N` (mock spy)
- [ ] `max_itens=0` rejeitado por Pydantic com mensagem amigável
- [ ] `max_itens=None` mantém comportamento full (default; sem regressão)
- [ ] Etapas pós-coleta (ETL, C1+C2, C3, grafos, histórico, convertibilidade) **não recebem** `max_itens` -- defesa explícita por teste
- [ ] Mypy strict zero erros, ruff zero violações
- [ ] CHANGELOG entrada `[Unreleased]` registrada
- [ ] CI verde nos 6 jobs multi-OS (lições S37 sobre matrix)
- [ ] Acentuação PT-BR correta em todos os textos visíveis (helps, docstrings, mensagens) -- I2 do BRIEF

## 9. Invariantes a preservar

Do `VALIDATOR_BRIEF.md`:

- **I1 (Tudo local):** sem novas chamadas a hosts proprietários (apenas Câmara/Senado, já inventariadas).
- **I2 (PT-BR sem perda):** docstrings, helps de CLI, mensagem de CHANGELOG e seção nova de doc devem ter acentuação correta. Verificar em todos os arquivos modificados.
- **I4 (Sem prints):** `grep -rn "print(" src/` continua zero.
- **I5 (Sem TODO sem ID):** o próprio `noqa: ARG001 -- placeholder pra S30` desaparece nesta sprint.
- **I6 (Pydantic v2 estrito):** novo campo é Pydantic v2 com `Field(...)`, validação `ge=1` integrada; sem dict solto.
- **I7 (Mypy strict):** `int | None` como tipo público, sem `Any`.
- **I8 (Ruff zero):** linhas longas devem ficar <= 100 cols.
- **I9 (Cobertura ≥ 90%):** linhas novas 100% cobertas pelos 10 testes.
- **I10 (Conventional Commits):** `fix(s30.1): propagar max-itens em sessao iniciar para coletores Câmara/Senado`.
- **I12 (CHANGELOG sempre):** entrada `[Unreleased]` Fixed obrigatória.

Do plano R2 e ADRs:

- **ADR-007 (Sessão de Pesquisa cidadã de primeira classe):** `params.json` continua sendo o contrato canônico; campo novo é registrado pela serialização Pydantic automática.
- **D6 (Tudo local):** `--max-itens` reduz dependência de rede e tempo de coleta -- alinhado.
- **D10 (Shell visível antes de ETL real):** UX-first; sprint destrava UI rápida no dashboard da S31.

## 10. Riscos

| Risco | Mitigação |
|---|---|
| `max_itens` propagado acidentalmente para etapas pós-coleta | Teste defensivo `test_etapa_etl_e_classificacao_nao_recebem_max_itens` valida via mock que ETL e C1 não recebem kwarg `max_itens` |
| `ParametrosColeta` exige `ge=1` mas `ParametrosBusca.max_itens=0` passar e quebrar internamente | Mesmo `ge=1` em `ParametrosBusca` rejeita antes; teste explícito |
| Schema dual de Senado (S25.3) interagir mal com `max_itens=N` baixo | `executar_coleta` Senado já propaga via 3 sub-coletores; comportamento idêntico a `hemiciclo coletar senado --max-itens N` que está em produção desde S25 |
| Rede instável em smoke local enviesar percepção de tempo | Smoke é opcional; mocks unit cobrem o circuito completo |
| Coleta Câmara só pega ano inicial da legislatura (S24c) | Não regredido nem corrigido aqui; `max_itens` aplica-se ao que o coletor entrega, qualquer que seja o recall |
| Cobertura ≥ 90% comprometida se algum mock não exercitar a propagação | Os 5 testes pipeline cobrem default None, valor explícito, propagação Câmara, propagação Senado e defesa pós-coleta |

## 11. Referências de código (confirmado via grep antes da redação)

- `src/hemiciclo/sessao/pipeline.py` -- `pipeline_real` (linha 68), `_etapa_coleta` (linha 161, 2 construções de `ParametrosColeta` em 179 e 195).
- `src/hemiciclo/sessao/modelo.py` -- `class ParametrosBusca(BaseModel)` linha 89, `model_config = ConfigDict(extra="forbid", ...)` linha 97 (campo novo precisa estar declarado para passar `extra="forbid"`).
- `src/hemiciclo/cli.py` -- `sessao_iniciar` linha 573, flag `--max-itens` linha 592, construção de `ParametrosBusca` linha 620, constantes `_PIPELINE_DUMMY_PATH`/`_PIPELINE_REAL_PATH` linhas 569-570.
- `src/hemiciclo/coleta/__init__.py` -- `class ParametrosColeta(BaseModel)` linha 41, campo `max_itens: int | None = Field(default=None, ge=1)` linha 65.
- `src/hemiciclo/coleta/camara.py` -- `def executar_coleta` linha 508, propagação interna `max_itens=params.max_itens` linhas 567/622/670.
- `src/hemiciclo/coleta/senado.py` -- `def executar_coleta` linha 604, propagação interna linhas 676/729/773.
- `tests/unit/test_pipeline_real.py` -- 8 testes herdados; ponto de extensão para os 5 novos.
- `sprints/ORDEM.md:53` -- linha S30.1 READY a virar DONE.

## 12. Validação multi-agente

Padrão. Validador atenção a:

- O campo novo em `ParametrosBusca` foi de fato propagado pela cadeia inteira CLI -> Pydantic -> pipeline -> ParametrosColeta -> coletor real (verificável por leitura linear).
- Default `None` preserva 100% do comportamento da S30 (regressão zero).
- Out-of-scope §3.2 respeitado: nenhuma etapa pós-coleta foi tocada.
- `ge=1` consistente entre `ParametrosBusca` e `ParametrosColeta` -- sem possibilidade de `0` ou negativo escapar.
- Acentuação periférica em help, docstring, CHANGELOG e doc nova.
- 10 testes novos contemplam todas as ramificações; 0 testes herdados quebram.

## 13. Próximo passo após DONE

Sprint S37b/S37c ou S23.x do anti-débito CI multi-OS, conforme decisão da próxima rodada do grupo `READY`. Esta S30.1 é folha (não bloqueia ninguém) e desbloqueia smoke-real local fluído para todo o ciclo v2.1.0 -- útil para refinar dashboard da S31 com sessões reais em < 2min cada.
