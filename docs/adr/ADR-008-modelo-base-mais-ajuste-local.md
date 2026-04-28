# ADR-008 -- Modelo base global + ajuste fino local (híbrido)

- **Status:** accepted
- **Data:** 2026-04-27
- **Decisores:** @AndreBFarias
- **Tags:** ml, infra

## Contexto e problema

Treinar um modelo de classificação/projeção do zero em cada máquina exigiria horas, dataset compartilhado e requisitos absurdos de hardware. Delegar tudo a um modelo central viola ADR-006. Há um meio-termo natural: um modelo base global, treinado uma única vez sobre uma amostra representativa do Congresso, distribuído como artefato versionado, e refinado localmente sobre os dados específicos da Sessão de Pesquisa do usuário.

## Drivers de decisão

- Tempo aceitável para o usuário (ordem de minutos, não horas)
- Reprodutibilidade entre máquinas (mesma base de partida)
- Soberania (ADR-006: ajuste fino é local)
- Qualidade do modelo (base aprende invariâncias do português parlamentar; local aprende especificidades da pesquisa)

## Opções consideradas

### Opção A -- Treinar tudo localmente

- Prós: máxima soberania.
- Contras: custo computacional inviável para cidadão comum; resultados não comparáveis entre máquinas.

### Opção B -- Modelo central remoto

- Prós: melhor performance possível.
- Contras: viola ADR-006.

### Opção C -- Híbrido: base global + ajuste local

- Base: PCA/UMAP fitada uma vez sobre amostra ampla; salva como artefato versionado em `~/hemiciclo/modelos/base_v1.pkl`, distribuído com hash SHA256 e assinatura no release oficial. Carregamento sempre validado contra o hash conhecido antes do uso, e nunca a partir de fontes não confiáveis.
- Ajuste: sessão refita um classificador local sobre o subconjunto relevante.
- Prós: melhor de cada mundo; combina com ADR-005 (caminho indutivo).
- Contras: precisa de protocolo de versionamento do modelo base e validação de integridade.

## Decisão

Escolhida: **Opção C**.

Justificativa: balanceia tempo de execução, qualidade e soberania. O artefato base é público e versionado (hash + assinatura no `manifesto.json` do release); o ajuste local é zero-leak. A validação de integridade do artefato baixado é obrigatória antes de qualquer uso.

## Consequências

**Positivas:**

- Primeira pesquisa fica rápida (segundos para refit local).
- Modelos base são auditáveis (inspecionar binário e metadados publicados).
- ADR-018 (random_state fixo) garante reprodutibilidade entre máquinas dada a mesma base.

**Negativas / custos assumidos:**

- Distribuição do modelo base precisa de canal confiável (release GitHub com hash assinado).
- Versionamento explícito do modelo base é responsabilidade contínua.
- Carregar o artefato exige validação de integridade -- contrato a ser reforçado pela rotina de carregamento (S28).

## Pendências / follow-ups

- [ ] ADR-009 detalha embeddings (entrada do PCA).
- [ ] ADR-018 detalha determinismo via random_state.
- [ ] S28 implementa treino do modelo base v1, distribuição do artefato e validação SHA256 obrigatória no carregamento.

## Links

- Plano: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` (seção 2)
- Sprints relacionadas: S22 (registro), S28
