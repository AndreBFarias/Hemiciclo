<!--
Obrigado por contribuir com o Hemiciclo. Preencha as seções abaixo
antes de marcar o PR como pronto para revisão. Referência: VALIDATOR_BRIEF.md.
-->

## Sumário

<!-- 1-3 linhas em PT-BR descrevendo a mudança e o motivo. -->

## Sprint relacionada

<!-- Ex.: S37 (sprints/SPRINT_S37_CI.md) ou nenhuma. -->

- ID:
- Spec:

## Tipo de mudança

- [ ] `feat` -- nova funcionalidade
- [ ] `fix` -- correção de bug
- [ ] `refactor` -- mudança interna sem alterar comportamento
- [ ] `docs` -- documentação
- [ ] `test` -- testes
- [ ] `chore` / `ci` / `build` -- infra
- [ ] `perf` / `style` -- performance / formatação

## Proof-of-work

<!--
Cole a saída literal dos comandos canônicos do BRIEF executados localmente:

  make check
  uv run python scripts/validar_adr.py
  uv run pytest tests/unit -v

Sem proof-of-work runtime-real, o PR é rejeitado em revisão (lição 1 do BRIEF).
-->

```
<saida literal aqui>
```

## Test plan

<!-- Cheque manualmente o que precisar ser checado. -->

- [ ] `make check` verde local
- [ ] CI verde nos 6 jobs (matriz multi-OS x multi-Python)
- [ ] Cobertura >= 90% em código novo (I9)
- [ ] Mypy --strict zero erros (I7)
- [ ] Ruff zero violações (I8)
- [ ] Sem `print()` em src/ (I4)
- [ ] CHANGELOG.md atualizado em `## [Unreleased]` (I12)

## Notas de revisão

<!--
Pontos onde o revisor deve focar atenção especial: trade-offs, decisões
de design, áreas potencialmente frágeis, follow-ups planejados (sprint nova).
-->

## ADRs vinculados

<!-- ADR-XXX se aplicável; deixe em branco caso não impacte decisão arquitetural. -->
