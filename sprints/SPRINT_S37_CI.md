# Sprint S37 -- CI multi-OS: pytest + ruff + mypy + matriz + coverage

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-27
**Autor:** @AndreBFarias
**Status:** DONE (2026-04-27)
**Depende de:** S22
**Bloqueia:** -- (paralelo a tudo daqui em diante)
**Esforço:** P (1-2 dias)
**ADRs vinculados:** ADR-015, ADR-019
**Branch:** feature/s37-ci

---

## 1. Objetivo

Configurar GitHub Actions com matriz `{ubuntu-22.04, macos-14, windows-2022} x {python-3.11, python-3.12}` (6 jobs), rodando lint + unit + integração + smoke install em cada job, publicando coverage no Codecov, validando ADRs e YAMLs de tópico (estes últimos quando existirem), e infraestrutura GitHub completa (issue templates, PR template, CODEOWNERS, dependabot, stale).

## 2. Contexto

S22 entregou bootstrap local com `make check` passando. Sem CI, qualquer regressão em PR posterior só é descoberta manualmente. Esta sprint protege todo o investimento futuro: cada PR daqui em diante valida lint + types + tests + coverage automaticamente nas 3 plataformas alvo do projeto.

Setup já feito (S22):

- pyproject.toml com configs Ruff, Mypy strict, pytest, coverage fail_under=90
- Makefile target `check` consolidando lint + tests
- 12 testes unit passando, cobertura 98.53%

Esta sprint apenas espelha esse pipeline em GitHub Actions e adiciona infraestrutura de governança do repo.

## 3. Escopo

### 3.1 In-scope

- [ ] `.github/workflows/ci.yml` -- workflow CI principal:
  - Trigger: push em `main` + pull_request em `main`
  - Matriz `{ubuntu-22.04, macos-14, windows-2022} x {python-3.11, python-3.12}` com `fail-fast: false`
  - Setup uv via `astral-sh/setup-uv@v3` com cache
  - `uv python install ${{ matrix.python }}`
  - `uv sync --frozen --all-extras` (falha se lock divergir)
  - `uv run ruff check src tests`
  - `uv run ruff format --check src tests`
  - `uv run mypy --strict src`
  - `uv run pytest tests/unit tests/integracao --cov=src/hemiciclo --cov-report=xml --cov-report=term-missing`
  - Upload Codecov apenas em `ubuntu-22.04 + python-3.11`
  - Validador de ADRs (`scripts/validar_adr.py` -- criar nesta sprint)
  - Validador de tópicos placeholder (skip se `topicos/_schema.yaml` ainda não existe)
- [ ] `.github/workflows/release.yml` -- esqueleto:
  - Trigger por tag `v*.*.*`
  - Roda CI completo
  - (Implementação completa do release fica pra S38)
- [ ] `.github/workflows/adr-check.yml` -- valida formato MADR de ADRs novos em PR (se diff toca `docs/adr/`)
- [ ] `.github/workflows/stale.yml` -- fecha issues sem atividade 90 dias com label `stale`
- [ ] `.github/dependabot.yml`:
  - Python deps semanais
  - GitHub Actions mensais
- [ ] `.github/CODEOWNERS` apontando @AndreBFarias como dono default
- [ ] `.github/PULL_REQUEST_TEMPLATE.md` com seções: Sumário, Sprint relacionada, Proof-of-work, Test plan, Notas de revisão
- [ ] `.github/ISSUE_TEMPLATE/bug.md` -- template de bug report
- [ ] `.github/ISSUE_TEMPLATE/feature.md` -- template de feature request
- [ ] `.github/ISSUE_TEMPLATE/topico.md` -- template específico para contribuir YAML de tópico
- [ ] `scripts/validar_adr.py` -- valida que ADRs novos seguem formato MADR (campos obrigatórios: Status, Data, Decisores, Tags, Contexto, Decisão, Consequências), numeração sequencial sem buracos, nenhuma duplicada
- [ ] Badge CI no `README.md` (acima do título)
- [ ] Badge coverage no `README.md` (Codecov)
- [ ] `docs/dev/workflow.md` -- documenta fluxo completo (clone -> branch -> commit -> PR -> CI -> review -> merge)

### 3.2 Out-of-scope (explícito)

- E2E completo (`@pytest.mark.slow`) rodando em CI -- fica em S38; nesta sprint, marcador existe mas não é executado
- Publicação no PyPI -- fica para v2.1.x
- `scripts/validar_topicos.py` -- fica em S27 (junto com criação do `topicos/_schema.yaml`)
- `codeql.yml` security workflow -- fica em S38
- Smoke install em CI (`./install.sh --check`) -- fica em S23 (que cria install.sh)
- Branch protection rules no GitHub (configuração via UI ou API) -- documentado mas não automatizado

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `.github/workflows/ci.yml` | CI principal multi-OS x multi-Python |
| `.github/workflows/release.yml` | Esqueleto de release (tag-triggered) |
| `.github/workflows/adr-check.yml` | Valida MADR em PRs que tocam ADRs |
| `.github/workflows/stale.yml` | Fecha issues sem atividade |
| `.github/dependabot.yml` | Atualizações automáticas de deps |
| `.github/CODEOWNERS` | @AndreBFarias dono default |
| `.github/PULL_REQUEST_TEMPLATE.md` | Template de PR |
| `.github/ISSUE_TEMPLATE/bug.md` | Template de bug |
| `.github/ISSUE_TEMPLATE/feature.md` | Template de feature |
| `.github/ISSUE_TEMPLATE/topico.md` | Template de tópico YAML |
| `.github/ISSUE_TEMPLATE/config.yml` | Configuração do issue chooser (desabilita issues em branco) |
| `scripts/validar_adr.py` | Validador MADR usado por adr-check.yml |
| `tests/unit/test_validar_adr.py` | Testes do validador |
| `docs/dev/workflow.md` | Documentação do fluxo dev |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `README.md` | Adiciona badges CI + coverage acima do título |
| `CHANGELOG.md` | Entrada `[Unreleased]` com bullet "ci: pipeline multi-OS configurado" |
| `sprints/ORDEM.md` | S37 status -> DONE com data |

## 5. Implementação detalhada

### 5.1 Passo a passo

1. Confirmar branch: `git rev-parse --abbrev-ref HEAD` retorna `feature/s37-ci`.
2. Criar `.github/workflows/ci.yml` com a matriz de 6 jobs.
3. Criar `.github/workflows/release.yml` com esqueleto tag-triggered.
4. Criar `.github/workflows/adr-check.yml` que dispara em paths `docs/adr/**`.
5. Criar `.github/workflows/stale.yml` simples (90 dias, label `stale`).
6. Criar `.github/dependabot.yml`.
7. Criar `.github/CODEOWNERS` (uma linha: `* @AndreBFarias`).
8. Criar `.github/PULL_REQUEST_TEMPLATE.md`.
9. Criar `.github/ISSUE_TEMPLATE/{bug,feature,topico}.md` + `config.yml`.
10. Implementar `scripts/validar_adr.py` (Python puro, sem deps extras):
    - Lê todos os arquivos `docs/adr/ADR-*.md`
    - Verifica numeração sequencial sem buracos (warning, não erro)
    - Verifica que cada ADR tem: `# ADR-NNN -- titulo`, `**Status:**`, `**Data:**`, `**Decisores:**`, `## Contexto`, `## Decisão`, `## Consequências`
    - Verifica que `docs/adr/README.md` lista todos os ADRs presentes
    - Exit 0 se OK, exit 1 com erro descritivo se inválido
11. `tests/unit/test_validar_adr.py`:
    - Fixture com ADR válido em tmp_path -> validador passa
    - Fixture com ADR sem `## Decisão` -> falha
    - Fixture com numeração com buraco -> warning mas não falha
    - Fixture com README desatualizado -> falha
12. Atualizar `README.md` com badges (Markdown):
    ```
    [![CI](https://github.com/AndreBFarias/Hemiciclo/actions/workflows/ci.yml/badge.svg)](https://github.com/AndreBFarias/Hemiciclo/actions/workflows/ci.yml)
    [![codecov](https://codecov.io/gh/AndreBFarias/Hemiciclo/branch/main/graph/badge.svg)](https://codecov.io/gh/AndreBFarias/Hemiciclo)
    [![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
    [![License](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE)
    ```
13. Escrever `docs/dev/workflow.md` (3-5 KB) cobrindo: clone, branch convention, commit convention, PR template, validação CI, review, merge strategy.
14. Atualizar `CHANGELOG.md`.
15. Rodar `uv run python scripts/validar_adr.py` localmente e confirmar que passa nos 11 ADRs criados em S22.
16. Rodar `make check` -- ainda deve passar.
17. Atualizar `sprints/ORDEM.md` mudando S37 para DONE.

### 5.2 Decisões técnicas

- **Matriz `fail-fast: false`** -- mesmo se Linux/3.11 falhar, queremos saber se Windows/3.12 também falha. Mais sinal por execução.
- **Codecov apenas em Linux/3.11** -- evita 6 uploads sobrepostos do mesmo coverage.
- **uv com cache** -- builds sucessivos terminam em < 60s (vs 3-5min sem cache).
- **`uv sync --frozen`** em CI -- falha se `uv.lock` divergir de `pyproject.toml`. Garante reprodutibilidade.
- **Validador ADR em Python puro** -- sem deps extras pra não inflar pyproject. Apenas stdlib.

### 5.3 Trecho de código de referência -- `ci.yml` literal

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  test:
    name: ${{ matrix.os }} / Python ${{ matrix.python }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-22.04, macos-14, windows-2022]
        python: ["3.11", "3.12"]
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Install Python ${{ matrix.python }}
        run: uv python install ${{ matrix.python }}

      - name: Sync dependencies
        run: uv sync --frozen --all-extras

      - name: Validar ADRs
        run: uv run python scripts/validar_adr.py

      - name: Ruff check
        run: uv run ruff check src tests

      - name: Ruff format check
        run: uv run ruff format --check src tests

      - name: Mypy strict
        run: uv run mypy --strict src

      - name: Pytest unit + integration
        run: uv run pytest tests/unit tests/integracao --cov=src/hemiciclo --cov-report=xml --cov-report=term-missing

      - name: Upload coverage to Codecov
        if: matrix.os == 'ubuntu-22.04' && matrix.python == '3.11'
        uses: codecov/codecov-action@v4
        with:
          files: coverage.xml
          fail_ci_if_error: false
```

### 5.4 Estrutura do `scripts/validar_adr.py`

Validador Python puro (apenas stdlib). Funções:

- `parse_adr(path: Path) -> dict` -- extrai metadados de cabeçalho MADR
- `validate_adr(parsed: dict) -> list[str]` -- retorna lista de erros (vazia se OK)
- `validate_directory(adr_dir: Path) -> tuple[list[str], list[str]]` -- (erros, warnings)
- `main()` -- exit 0 ou 1 com mensagem clara

### 5.5 Branch protection (documentação para configuração manual)

Em `docs/dev/workflow.md`, documentar que após merge da S37 deve-se configurar manualmente no GitHub:

- Settings > Branches > Add rule pra `main`:
  - Require a pull request before merging
  - Require approvals: 1
  - Require status checks: `test (ubuntu-22.04, 3.11)` mínimo
  - Require branches to be up to date

Não automatizado via GitHub CLI nesta sprint pra evitar dependência de token específico.

## 6. Testes

### 6.1 Unit (`tests/unit/test_validar_adr.py`)

- `test_adr_valido_passa` -- ADR completo em tmp_path, validate retorna OK.
- `test_adr_sem_decisao_falha` -- ADR sem seção `## Decisão`, validate falha com mensagem clara.
- `test_adr_sem_status_falha` -- sem campo `**Status:**`, validate falha.
- `test_numeracao_com_buraco_warning` -- ADR-001, ADR-003 (sem 002), retorna warning mas não erro.
- `test_readme_desatualizado_falha` -- README.md sem listar todos os ADRs presentes, valida falha.
- `test_readme_atualizado_passa` -- README listando todos, passa.
- `test_diretorio_vazio_passa` -- `docs/adr/` sem ADRs, retorna OK (zero erros, zero warnings).

### 6.2 Integração

CI rodando neste mesmo PR é a integração. PR de S37 deve ter os 6 jobs verdes.

## 7. Proof-of-work runtime-real

**Comando local:**

```bash
$ uv run python scripts/validar_adr.py && \
  uv run pytest tests/unit/test_validar_adr.py -v && \
  yq eval '.jobs.test.strategy.matrix.os | length' .github/workflows/ci.yml
```

**Saída esperada:**

```
[validar_adr] 11 ADRs validados em docs/adr/. Zero erros.
[pytest] 7 passed
3
```

(11 ADRs já criados em S22; 7 testes novos do validador; 3 OS na matriz CI.)

**Proof-of-work remoto (ground truth):**

CI verde no PR desta sprint. 6 jobs (`test (ubuntu-22.04, 3.11)`, `test (ubuntu-22.04, 3.12)`, `test (macos-14, 3.11)`, `test (macos-14, 3.12)`, `test (windows-2022, 3.11)`, `test (windows-2022, 3.12)`) todos passando. Coverage publicado no Codecov.

**Critério de aceite:**

- [ ] `.github/workflows/ci.yml` existe com matriz 3x2
- [ ] CI verde nos 6 jobs do PR desta sprint
- [ ] `scripts/validar_adr.py` valida os 11 ADRs criados em S22 sem erro
- [ ] `tests/unit/test_validar_adr.py` 7 testes passando
- [ ] Badges CI + coverage + python + license no README
- [ ] `.github/PULL_REQUEST_TEMPLATE.md` aplicado neste PR
- [ ] CHANGELOG.md tem entrada CI
- [ ] `docs/dev/workflow.md` documentando fluxo + branch protection rules
- [ ] Mypy --strict zero erros (esperado, validador é Python puro)
- [ ] Ruff zero violações
- [ ] Cobertura >= 90% no `scripts/validar_adr.py`

## 8. Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| `uv sync --frozen` falha em macOS/Windows por diferença de wheels | M | A | Setup uv da Astral cobre isso; em caso extremo, remover `--frozen` em CI primeiro release |
| `mypy --strict` zero erros em S22 mas falha em CI por diff Python 3.11 vs 3.12 | B | M | Matriz pega cedo; correção pontual de typing |
| Codecov rate-limit no primeiro upload | B | B | `fail_ci_if_error: false` no step de upload |
| Workflows YAML inválidos (sintaxe) | M | A | `yq` ou `actionlint` localmente antes de commit |
| Validador ADR muito rígido bloqueia ADRs legítimos com pequenas variações de formato | M | M | Lista de campos OBRIGATÓRIOS curta (apenas estruturais); demais campos warning |
| `dependabot` cria PRs barulhentos | M | B | Frequência semanal Python + mensal Actions; agrupar em uma só |

## 9. Validação multi-agente

**Executor (`executor-sprint`):**

1. Lê `VALIDATOR_BRIEF.md`.
2. Lê este spec.
3. Confirma branch ativo `feature/s37-ci`.
4. Implementa entregas conforme passo a passo.
5. Roda proof-of-work local.
6. Reporta saída literal.
7. **Não pusha**. Não abre PR. Eu (orquestrador) integro depois da validação.

**Validador (`validador-sprint`):**

1. Lê `VALIDATOR_BRIEF.md`.
2. Lê este spec.
3. Roda proof-of-work local independentemente.
4. Verifica I1-I12.
5. Inspeciona `.github/workflows/ci.yml` por syntax errors via `yq` ou inspeção visual.
6. Confirma que `scripts/validar_adr.py` passa nos 11 ADRs reais.
7. Decide APROVADO / APROVADO_COM_RESSALVAS / REPROVADO.

Como o critério de aceite remoto (CI verde no PR) só pode ser confirmado depois do push, validação local é a barra mínima. CI verde será verificado depois do PR aberto, antes do merge.

## 10. Próximo passo após DONE

S23 (Streamlit shell visível) -- entrega valor visível pro usuário comum.
