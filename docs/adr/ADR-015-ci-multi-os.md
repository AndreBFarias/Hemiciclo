# ADR-015 -- CI multi-OS Linux + macOS + Windows × Python 3.11 + 3.12

- **Status:** accepted
- **Data:** 2026-04-28
- **Decisores:** @AndreBFarias
- **Tags:** ci, infra, qualidade

## Contexto e problema

O Hemiciclo é um produto local instalável em qualquer máquina do "João
comum". As três famílias de SO em uso doméstico relevante são Linux,
macOS e Windows. Diferenças sutis entre elas (path separators, encoding
default, fork vs spawn, signals POSIX) quebram código sem aviso. A única
forma de garantir paridade é **rodar a suíte completa em todos os SOs**
em CI antes de cada merge.

## Drivers de decisão

- Tudo local em qualquer SO (ADR-006 + ADR-014).
- Detecção precoce de bugs cross-OS (paths, signals, encoding).
- Cobrir as duas versões Python no LTS atual (3.11 e 3.12).
- Tempo de CI razoável (< 10 min por job).

## Opções consideradas

### Opção A -- CI só Linux

- Prós: rápido, barato, simples.
- Contras: bugs Windows / macOS detectados só no usuário final.

### Opção B -- Matrix 3 SO × 2 Python

- Prós: 6 jobs paralelos cobrem 100% do espaço suportado, falhas
  imediatamente visíveis no PR.
- Contras: mais minutos consumidos, Windows runners mais lentos.

### Opção C -- Linux + Windows (sem macOS)

- Prós: meio-termo.
- Contras: macOS é base de muitos contribuidores; CI cego ali viola I7/I8.

## Decisão

Escolhida: **Opção B** -- matrix 3 × 2 = 6 jobs paralelos, com `fail-fast: false`
para ver todas as falhas mesmo quando uma falha primeiro.

Cada job roda: `ruff check`, `ruff format --check`, `mypy --strict`,
`pytest --cov`, `validar_topicos.py`, `validar_adr.py`.

## Consequências

**Positivas:**

- Paridade real cross-OS validada a cada PR.
- Lições empíricas documentadas (S24: `COLUMNS=200 TERM=dumb NO_COLOR=1`
  em testes de CLI; S31: encoding UTF-8 explícito em escrita JSON).
- Pull requests rejeitados se quebram em qualquer dos 6.

**Negativas / custos assumidos:**

- Tempo total CI ~8 min (Windows mais lento).
- Quota GitHub Actions consumida proporcionalmente.

## Pendências / follow-ups

- [x] S37 entrega 4 workflows (`ci`, `release`, `adr-check`, `stale`).
- [ ] Codecov integrado em todos os jobs (após release v2.0.0).

## Links

- Sprint relacionada: S37
- Documentação: `docs/dev/workflow.md`
- Workflow: `.github/workflows/ci.yml`
