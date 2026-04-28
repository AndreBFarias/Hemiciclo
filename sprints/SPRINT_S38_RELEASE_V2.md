# Sprint S38 -- Higienização final + manifesto + demo gif + release v2.0.0

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-28
**Status:** DONE (2026-04-28)
**Depende de:** S22, S23, S24, S25, S26, S27, S28, S29, S30, S31, S32, S33, S34, S35, S37 (TODAS DONE)
**Bloqueia:** -- (terminal)
**Esforço:** M (3-5 dias)
**ADRs vinculados:** -- (sprint de release)
**Branch:** feature/s38-release-v2-0-0

---

## 1. Objetivo

Última sprint do caminho crítico. Fecha o produto Hemiciclo 2.0.0 com:

1. **Higienização**: docs completos, README polish, badges atualizados
2. **Manifesto longo** em `docs/manifesto.md` (texto político ~1500 palavras)
3. **Anti-débito incorporado**: resolve 3 sprints READY que afetam release:
   - **S37b**: acentuação PT-BR consistente em `.github/PULL_REQUEST_TEMPLATE.md` + issue templates
   - **S37c**: cria ADR-012 a ADR-019 (referenciados no plano R2 mas ausentes)
   - **S25.2**: higieniza acentuação em CHANGELOG/ORDEM legado
4. **Demo screenshot** validando UX final
5. **CHANGELOG.md** consolida `[Unreleased]` em `## [2.0.0] - 2026-04-28`
6. **Tag git `v2.0.0`** dispara `release.yml` workflow
7. **GitHub Release** publicado com notas + assets

## 2. Contexto

S22-S37 entregaram os 16 sprints do plano R2. Suite final: 477 testes, cobertura 90.32%, 6 jobs CI multi-OS, 4 camadas de classificação (regex/voto/embeddings/LLM-opcional), grafos, histórico, ML convertibilidade.

S38 é a **higienização** que torna o produto release-ready: docs completos, manifesto político publicado, débitos críticos fechados, tag SemVer disparando workflow de release.

26 sprints novas READY do anti-débito ficam para v2.1.x — mas 3 entram nesta release porque são bloqueantes:
- S37b: PR templates inconsistentes mostram má impressão a contribuidores
- S37c: ADRs faltantes minam rastreabilidade do plano R2
- S25.2: CHANGELOG/ORDEM com acentuação legada quebra busca PT-BR

## 3. Escopo

### 3.1 In-scope

- [ ] **Manifesto político longo** em `docs/manifesto.md` (~1500 palavras):
  - Experiência prévia do autor (cientista de dados/netnógrafo entregando perfilamento corporativo a clientes do mercado de inteligência política privada)
  - Diagnóstico do mercado de inteligência política brasileira
  - Por que a ferramenta deve ser open-source GPL v3 (não MIT/BSD)
  - O que João Comum ganha tendo Hemiciclo na máquina
  - Roadmap político (não técnico): jornalismo investigativo, fiscalização cidadã, defesa de pautas progressistas e conservadoras com igual rigor
  - Limitações honestas: o que o Hemiciclo NÃO faz (não recomenda voto, não detecta corrupção)
- [ ] **README.md polish**:
  - Badges atualizados (CI, coverage Codecov, Python versions, license)
  - Seção "Início rápido" funcional (`./install.sh && ./run.sh`)
  - Link pra `docs/manifesto.md`
  - Seção "O que o Hemiciclo faz" com 3 exemplos concretos
  - Seção "Limitações" honesta (S24b/c, S27.1, modelo correlacional)
  - Estatísticas finais (sprints, testes, cobertura, ADRs)
- [ ] **S37b — Acentuação `.github/`**:
  - `.github/PULL_REQUEST_TEMPLATE.md`: correção, documentação, motivação, alternativas
  - `.github/ISSUE_TEMPLATE/bug.md`, `feature.md`, `topico.md`: versão, sessão, cosmético
- [ ] **S37c — ADRs 012-019** em `docs/adr/`:
  - ADR-012: DuckDB + Parquet como storage analítico
  - ADR-013: Subprocess + status.json + pid.lock como modelo de execução
  - ADR-014: install.sh/.bat exigem Python 3.11+ pré-instalado
  - ADR-015: CI multi-OS Linux+macOS+Windows × 3.11+3.12
  - ADR-016: Dependências fixadas em pyproject.toml (uv lock)
  - ADR-017: Conventional Commits + branch feature/fix/docs/chore
  - ADR-018: random_state fixo em todos os modelos
  - ADR-019: Ruff + Mypy strict + pytest --cov=90 como portões
  - `docs/adr/README.md` atualizado com índice 001-020
- [ ] **S25.2 — Acentuação CHANGELOG/ORDEM legado**:
  - `CHANGELOG.md` linhas legadas: configuração, sessão, instalação
  - `sprints/ORDEM.md` notas históricas: validação, padrão
- [ ] **CHANGELOG.md release v2.0.0**:
  - Move tudo de `## [Unreleased]` para `## [2.0.0] - 2026-04-28`
  - Adiciona seção "Highlights" com 5 destaques
  - Lista 4 invariantes da release
  - Lista 26 sprints READY remanescentes para v2.1.x
- [ ] **Demo screenshot final** em `docs/assets/demo.png`:
  - Página `sessao_detalhe.py` com `_seed_concluida` mostrando todas as seções
  - Capturado via Playwright (já instalado em S31)
  - Embed no README
- [ ] **`docs/usuario/instalacao.md`** revisado:
  - Pré-requisitos finais (Python 3.11+, RAM 4GB, disco 5GB sem bge-m3 / 8GB com)
  - Fluxo `./install.sh` (Linux/macOS) -- Windows fica em S36
  - Troubleshooting completo
- [ ] **Tag git `v2.0.0`** + push:
  - `git tag -a v2.0.0 -m "Hemiciclo 2.0.0 -- ..."`
  - `git push origin v2.0.0` -> dispara `release.yml`
- [ ] **Sentinela final** `test_sentinela.py`:
  - `test_versao_e_2_0_0` -- valida `__version__` em `src/hemiciclo/__init__.py` é `"2.0.0"`
- [ ] **Bump versão** `src/hemiciclo/__init__.py` e `pyproject.toml`: `0.1.0` -> `2.0.0`
- [ ] **`sprints/ORDEM.md`** S38 -> DONE + tabela final mostra 17 sprints DONE + 26 READY para v2.1.x

### 3.2 Out-of-scope

- **23 sprints READY remanescentes** -- ficam para v2.1.x
- **Publicação no PyPI** -- v2.1.x (precisa pyproject final + release validado)
- **Produção docs.hemiciclo.org** -- v2.1.x
- **Logo SVG novo** -- v2.1.x (mantém placeholder atual)
- **Tradução EN-US** -- v3.x

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `docs/adr/ADR-012-duckdb-parquet.md` | ADR S37c |
| `docs/adr/ADR-013-subprocess-pid-lock.md` | ADR S37c |
| `docs/adr/ADR-014-install-python-pre-instalado.md` | ADR S37c |
| `docs/adr/ADR-015-ci-multi-os.md` | ADR S37c |
| `docs/adr/ADR-016-uv-lock.md` | ADR S37c |
| `docs/adr/ADR-017-conventional-commits.md` | ADR S37c |
| `docs/adr/ADR-018-random-state-fixo.md` | ADR S37c |
| `docs/adr/ADR-019-ruff-mypy-pytest.md` | ADR S37c |
| `docs/assets/demo.png` | Screenshot principal pra README |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `docs/manifesto.md` | Reescrito de stub curto para texto longo (~1500 palavras) |
| `README.md` | Polish completo: badges, exemplos, limitações |
| `docs/adr/README.md` | Índice 001-020 |
| `.github/PULL_REQUEST_TEMPLATE.md` | Acentuação consistente (S37b) |
| `.github/ISSUE_TEMPLATE/bug.md` | Acentuação (S37b) |
| `.github/ISSUE_TEMPLATE/feature.md` | Acentuação (S37b) |
| `.github/ISSUE_TEMPLATE/topico.md` | Acentuação (S37b) |
| `CHANGELOG.md` | Consolida em `## [2.0.0]` + S25.2 fixes |
| `sprints/ORDEM.md` | S38 -> DONE + S25.2/S37b/S37c -> DONE |
| `src/hemiciclo/__init__.py` | `__version__ = "2.0.0"` |
| `pyproject.toml` | `version = "2.0.0"` |
| `tests/unit/test_sentinela.py` | Atualiza assert para 2.0.0 |
| `docs/usuario/instalacao.md` | Revisado |

## 5. Implementação detalhada

### 5.1 Estrutura do manifesto longo

Seções em ordem:
1. **"O que faz quem trabalha pra lobistas"** (3 parágrafos): experiência prévia do autor no mercado de inteligência política privada
2. **"Por que isso é problema"** (3 parágrafos): assimetria de informação política
3. **"O Hemiciclo é a inversão do vetor"** (3 parágrafos): manifesto político central
4. **"Por que GPL v3"** (2 parágrafos): garantia de software livre permanente
5. **"O que João Comum ganha"** (3 parágrafos): casos de uso (jornalista, ativista, eleitor curioso)
6. **"O que o Hemiciclo NÃO faz"** (1 parágrafo): limitações honestas
7. **"Roadmap político"** (2 parágrafos): visão pra v2.1+

### 5.2 README.md polish

Estrutura final:
```markdown
[badges]
# Hemiciclo
[tagline]
[demo.png]

## O que é
3 frases.

## Início rápido
3 comandos.

## O que faz (3 exemplos)
- Top a-favor / contra de aborto
- Histórico de Joaquim mudou de posição
- Rede de coautoria do partido

## Limitações honestas
4 bullets

## Como contribuir
Link CONTRIBUTING.md

## Manifesto
Link manifesto.md
```

### 5.3 ADRs 012-019 (formato MADR curto, ~30 linhas cada)

Cada ADR segue o mesmo template da S22 (precedente ADR-001 a ADR-011):
- Status: accepted
- Data: 2026-04-28
- Decisores: @AndreBFarias
- Tags: storage|infra|workflow|qualidade
- Contexto: 2 parágrafos
- Decisão: 1 parágrafo claro
- Consequências: positivas + negativas

### 5.4 Demo screenshot via Playwright

```bash
HEMICICLO_HOME=/tmp/demo uv run python scripts/seed_dashboard.py
HEMICICLO_HOME=/tmp/demo uv run streamlit run src/hemiciclo/dashboard/app.py --server.headless=true --server.port=8501 &
sleep 5
playwright screenshot --browser=chromium --full-page \
  http://localhost:8501 docs/assets/demo.png
```

### 5.5 Passo a passo

1. Confirmar branch.
2. Bump versão para 2.0.0 em `__init__.py` e `pyproject.toml`.
3. Atualizar `test_sentinela.py` para 2.0.0.
4. Reescrever `docs/manifesto.md` (~1500 palavras).
5. Polish `README.md` (badges + exemplos + limitações).
6. Criar 8 ADRs (012-019) em `docs/adr/`.
7. Atualizar `docs/adr/README.md` com índice completo.
8. Aplicar S37b: acentuação `.github/PULL_REQUEST_TEMPLATE.md` + 3 issue templates.
9. Aplicar S25.2: acentuação CHANGELOG.md/ORDEM.md legados.
10. Capturar `docs/assets/demo.png` via Playwright.
11. Embed demo.png no README.md.
12. Revisar `docs/usuario/instalacao.md`.
13. Consolidar CHANGELOG `[Unreleased]` em `## [2.0.0] - 2026-04-28`.
14. Atualizar `sprints/ORDEM.md` marcando S25.2/S37b/S37c/S38 -> DONE.
15. `make check` ≥ 90% (não pode regredir).
16. Commits granulares Conventional.
17. Push + PR.
18. Após CI verde + merge: criar tag `v2.0.0` e push.
19. Verificar `release.yml` workflow disparado.

## 6. Testes

- 1 sentinela atualizada (`test_versao_e_2_0_0`)
- Suite mantém 477+ testes verdes
- Cobertura ≥ 90% sem regressão

## 7. Proof-of-work runtime-real

```bash
$ make check
$ uv run hemiciclo --version
hemiciclo 2.0.0

$ uv run python scripts/validar_adr.py
20 ADRs validados em docs/adr/. Zero erros.

$ ls docs/assets/demo.png
$ git tag v2.0.0 && git push origin v2.0.0
```

**Critério de aceite:**

- [ ] `make check` 477+ testes verdes, cobertura ≥ 90%
- [ ] `hemiciclo --version` retorna `hemiciclo 2.0.0`
- [ ] 20 ADRs presentes (001-020)
- [ ] `docs/manifesto.md` >= 1500 palavras
- [ ] README com demo.png embedado
- [ ] CHANGELOG consolidado em `[2.0.0]`
- [ ] S25.2/S37b/S37c marcados DONE em ORDEM.md
- [ ] Tag `v2.0.0` pushada
- [ ] CI verde, release.yml disparado
- [ ] GitHub Release publicado

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Tag v2.0.0 disparar release.yml e falhar (release.yml é stub da S37) | Verificar release.yml antes de tag; se stub, completar implementação ou usar release manual |
| Playwright não disponível em ambiente do executor | Já instalado em S31; fallback: screenshot manual via Chrome |
| Manifesto longo com erros de revisão | Spec dá esqueleto; conteúdo é responsabilidade do autor real (Andre) -- executor preenche com placeholder honesto |
| 8 ADRs criados de uma vez sem consistência | Template fixo + revisão pelo validador |

## 9. Validação multi-agente

Padrão. Validador atenção a:
- Skill `validacao-visual` ATIVADA (demo.png deve ser válida)
- Manifesto >= 1500 palavras (`wc -w`)
- 20 ADRs (`ls docs/adr/ADR-*.md | wc -l == 20`)
- Tag v2.0.0 NÃO criada ainda (orquestrador cria após validação aprovada)

## 10. Próximo passo após DONE

**Hemiciclo 2.0.0 publicado.** Próximas releases:
- v2.1.0: 23 sprints READY remanescentes (S23.1-3, S24b-f, S25.1/3, S27.1, S29.1-2, S28-polish, S30.1-3, S35a-c)
- v2.x.0: S34b (LLM camada 4), S36 (Windows), features comunitárias
