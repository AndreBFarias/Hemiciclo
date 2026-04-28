---
name: Contribuição de tópico (YAML curado)
about: Propor novo tópico ou ajuste em tópico existente para o classificador C1
title: "[topico] "
labels: ["topico", "triage"]
assignees: []
---

## Nome do tópico

<!-- Slug em ASCII (ex.: meio-ambiente, reforma-tributaria). -->

## Descrição curta

<!-- 1-2 linhas em PT-BR. -->

## Justificativa

<!-- Por que este tópico merece existir? Quais agendas legislativas concretas ele cobre? -->

## Termos-chave (regex C1)

<!--
Liste os termos / expressões regex que devem disparar o classificador C1 para
proposições e discursos. Use raiz de palavra quando possível para cobrir flexão.
-->

```
- "\\b(?:meio[ ]?ambiente|sustentab[ia])"
- ...
```

## Categorias oficiais relacionadas

<!--
Quais categorias das APIs Câmara/Senado mapeiam aproximadamente para este tópico?
-->

## PLs paradigmáticos

<!-- Liste 2-5 PLs reais (numero + ano + casa) que claramente pertencem a este tópico. -->

## Anti-exemplos

<!-- Casos que parecem casar mas não pertencem; ajuda a refinar regex. -->

## Sprint relacionada

<!-- Provavelmente S27 (criação do schema YAML); deixe em branco se ainda não programada. -->

## Conformidade com `topicos/_schema.yaml`

- [ ] Os campos cobertos são compatíveis com o schema (quando existir, S27).
- [ ] Termos são regex compatíveis com Python `re` módulo (sem PCRE-only).

## Notas

<!-- Referências acadêmicas, mapeamento com ADR-003, dependências com outros tópicos. -->
