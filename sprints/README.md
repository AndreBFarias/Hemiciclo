# Sprints do Hemiciclo

Diretório com specs de sprint, contratos de execução para agentes Claude (Opus / Sonnet / Haiku).

## Padrão

Cada arquivo `SPRINT_S<NN>_<TITULO>.md` segue o padrão ULTRA-DETALHADO documentado em `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` -- seção 9.2.

## Como executar

Cada sprint passa pelo ciclo:

1. **planejar-sprint** (escreve spec a partir do plano R2)
2. **executor-sprint** (implementa)
3. **validador-sprint** (valida proof-of-work + invariantes do `VALIDATOR_BRIEF.md`)
4. **/commit-push-pr** (auto-commit + push + PR)

Em caso de REPROVADO, validador escreve patch-brief e executor refaz (até 3 iterações).

## Status

Ver `ORDEM.md` para tabela com status atual e grafo de dependências.

## Anti-débito

Achados colaterais durante execução nunca viram "issue depois" ou "TODO solto". Viram:
- (a) Edit pronto dentro da própria sprint, ou
- (b) `SPRINT_S<N+1>_*.md` nova auto-criada pelo agente que descobriu.

Ver `VALIDATOR_BRIEF.md` na raiz do repo para invariantes inegociáveis.
