# ADR-017 -- Conventional Commits + branches feature/fix/docs/chore

- **Status:** accepted
- **Data:** 2026-04-28
- **Decisores:** @AndreBFarias
- **Tags:** workflow, qualidade

## Contexto e problema

O histórico Git é a documentação operacional viva do projeto. Mensagens
inconsistentes (`fix stuff`, `wip`, `update`) sabotam três ferramentas:
geração automática de CHANGELOG, identificação de commits para reverter,
e rastreabilidade do que entrou em qual release. Em projeto multi-agente
(humano + Claude executor + Claude validador), sem padrão claro o histórico
vira ruído.

## Drivers de decisão

- Geração automática de CHANGELOG em release.
- Rastreabilidade entre commit -> sprint -> ADR.
- Interoperabilidade com ferramentas (`git-cliff`, `commitizen`, etc.).
- Padrão ergonômico para humanos e agentes Claude.

## Opções consideradas

### Opção A -- Texto livre

- Prós: zero atrito.
- Contras: sem ganchos para automação, histórico opaco.

### Opção B -- Conventional Commits (cc)

- Prós: padrão industry-wide, grammar simples (`<tipo>(<escopo>): <mensagem>`),
  habilita semantic-release, ferramental abundante.
- Contras: precisa disciplina (mitigado por hook).

### Opção C -- Gitmoji

- Prós: visual.
- Contras: viola convenção do CLAUDE.md (zero emoji em código/commits).

## Decisão

Escolhida: **Opção B** -- Conventional Commits.

Tipos canônicos: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `ci`,
`build`, `style`, `perf`, `release`. Escopo recomendado: `s<NN>` da sprint
relacionada (ex.: `feat(s27): classificador C1+C2`). Quebras de compat
sinalizadas com `!` ou `BREAKING CHANGE:` no corpo.

Branches:
- `feature/s<NN>-<slug>` -- sprint feature.
- `fix/<id>-<slug>` -- bugfix isolado.
- `docs/<slug>` -- documentação isolada.
- `chore/<slug>` -- infra / tooling.

## Consequências

**Positivas:**

- `git log --oneline` lê como changelog.
- `git-cliff` (futuro) gera release notes automaticamente.
- Fácil filtrar por tipo/escopo (`git log --grep "^feat(s27)"`).

**Negativas / custos assumidos:**

- PRs de Claude executor às vezes precisam ajuste fino na mensagem
  (mitigado por hook de validação no commit).

## Pendências / follow-ups

- [x] S22 documenta o padrão em CONTRIBUTING.md.
- [x] S37 valida via CI (commit lint opcional).
- [ ] Geração automática de CHANGELOG via git-cliff (v2.1+).

## Links

- Sprint relacionada: S22
- Padrão: https://www.conventionalcommits.org/
- Documentação: `CONTRIBUTING.md`
