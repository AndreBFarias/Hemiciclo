# ADR-003 -- Mapeamento tópico → proposições via híbrido (regex + categoria + YAML)

- **Status:** accepted
- **Data:** 2026-04-27
- **Decisores:** @AndreBFarias
- **Tags:** etl, classificacao, ml

## Contexto e problema

Para cruzar voto nominal (ADR-002) com tópico de pesquisa, o sistema precisa decidir quais proposições pertencem a um determinado tema. Há três fontes de sinal disponíveis: (a) regex sobre ementa/título, (b) categoria oficial atribuída pela própria casa legislativa, (c) curadoria manual via YAML. Nenhuma sozinha é suficiente: regex tem falsos positivos, a categoria oficial é grosseira e sub-utilizada, e curadoria manual não escala.

## Drivers de decisão

- Cobertura ampla (recall) sem sacrificar precisão
- Auditabilidade do mapeamento (cidadão deve poder inspecionar)
- Capacidade de evolução incremental (curador adiciona casos sem romper o sistema)
- Compatibilidade com a classificação multicamada (ADR-011)

## Opções consideradas

### Opção A -- Apenas regex sobre ementa

- Prós: simples, rápido, totalmente determinístico.
- Contras: alta taxa de falsos positivos; difícil cobrir variantes lexicais; cidadão não consegue ajustar sem virar dev.

### Opção B -- Apenas categoria oficial da API

- Prós: dado primário; bem definido legalmente.
- Contras: categorias são amplas demais ("Direito Civil") e pouco politicamente relevantes; muitos PLs aparecem com categoria "Outros".

### Opção C -- Híbrido (regex + categoria oficial + YAML curado)

- Prós: combina determinismo, dado primário e curadoria; YAML versionado é auditável; fallback gracioso quando uma camada falha.
- Contras: três fontes precisam ser mantidas em sincronia; YAML schema (ADR-011, S27) vira contrato.

## Decisão

Escolhida: **Opção C**.

Justificativa: o projeto não pode escolher entre rigor e cobertura -- precisa dos dois. Cada PL recebe três sinais binários (regex, categoria, YAML); a função de combinação fica explicitamente definida no classificador C1 (S27). YAML curado por sub-tópico permite que comunidades especializadas (educação, direitos humanos, meio ambiente) contribuam sem mexer em código.

## Consequências

**Positivas:**

- Cobertura aumenta com curadoria sem quebrar estabilidade do regex.
- YAMLs ficam auditáveis em `topicos/` no repo, validados via `_schema.yaml`.
- Compõe naturalmente com C2 (TF-IDF) e C3 (embeddings) na cascata.

**Negativas / custos assumidos:**

- Manutenção dos YAMLs vira fluxo permanente.
- Validação automática via `scripts/validar_topicos.py` (S27) e CI.

## Pendências / follow-ups

- [ ] ADR-011 detalha como C1 combina os três sinais.
- [ ] Schema YAML descrito na seção 3.6 do plano R2; implementação em S27.

## Links

- Plano: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` (seções 3 e 3.6)
- Sprints relacionadas: S22 (registro), S27 (implementação)
