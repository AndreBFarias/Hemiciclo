# ADR-009 -- Embeddings BAAI/bge-m3 como default

- **Status:** accepted
- **Data:** 2026-04-27
- **Decisores:** @AndreBFarias
- **Tags:** ml, nlp

## Contexto e problema

A camada semântica (C3 da classificação multicamada, ADR-011) precisa de um modelo de embeddings para discursos e proposições em português brasileiro. As opções precisam ser pesadas em três dimensões: qualidade multilíngue (português é minoritário em modelos anglófonos), tamanho/desempenho em CPU (ADR-006), e licença (ADR-006 implica licença permissiva).

## Drivers de decisão

- Qualidade comprovada em PT-BR
- Cabe em ~2GB e roda em CPU razoável
- Licença permissiva (compatível com GPL-3.0)
- Suporte a sequências longas (discursos parlamentares são longos)
- Comunidade ativa e atualizações

## Opções consideradas

### Opção A -- multilingual-e5-large

- Prós: bom desempenho geral; suporte multilíngue.
- Contras: PT-BR ainda fica atrás em alguns benchmarks; sequência limitada.

### Opção B -- BAAI/bge-m3

- Prós: estado-da-arte multilíngue 2024-25; suporta sequências longas (até 8192 tokens); modos dense + sparse + multi-vector; Apache 2.0 (compatível); tamanho aceitável após quantização.
- Contras: tamanho original ~2.3GB; FlagEmbedding é a interface padrão (mais um pacote no stack).

### Opção C -- modelos brasileiros menores (BERTimbau etc.)

- Prós: 100% PT-BR; menor.
- Contras: stale (não atualizam desde 2022); sequências curtas; sem modo sparse.

## Decisão

Escolhida: **Opção B (BAAI/bge-m3)**.

Justificativa: melhor combinação de qualidade PT-BR, tamanho viável e features modernas (long context, sparse, multi-vector). Apache 2.0 não conflita com a licença GPL-3.0 do projeto. Quantização opcional para máquinas mais fracas.

## Consequências

**Positivas:**

- Suporte a discursos longos sem chunking artificial.
- Modos sparse e dense permitem hibridização busca-semântica.
- Comunidade ativa; atualizações esperadas.

**Negativas / custos assumidos:**

- Download de ~2GB no primeiro uso (gerenciado pelo runner; cache em `~/hemiciclo/cache/`).
- Inferência em CPU é ordens de magnitude mais lenta que GPU; aceitável para escala cidadão.

## Pendências / follow-ups

- [ ] ADR-008 detalha como o modelo base usa esses embeddings.
- [ ] S28 implementa treino com bge-m3 + PCA.

## Links

- Plano: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` (seções 3.3 e 5.3)
- Sprints relacionadas: S22 (registro), S28
