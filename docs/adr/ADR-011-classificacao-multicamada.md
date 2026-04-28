# ADR-011 -- Classificação multicamada em cascata, cada camada desligável

- **Status:** accepted
- **Data:** 2026-04-27
- **Decisores:** @AndreBFarias
- **Tags:** ml, classificacao

## Contexto e problema

Decidir se uma proposição/discurso pertence a um tópico não tem solução única certa. Métodos puramente determinísticos (regex) têm alta precisão mas baixo recall; métodos puramente semânticos (embeddings) têm alto recall mas baixa explicabilidade; LLMs têm boa qualidade mas dependem de servidor remoto, comprometendo ADR-006. Uma solução robusta precisa combinar métodos com graus distintos de confiança e custo.

## Drivers de decisão

- Cobertura sem perder precisão
- Auditabilidade -- cidadão precisa saber por que algo foi classificado
- Soberania -- cada camada precisa funcionar localmente, com a opcional de LLM remota desligada por default
- Custo computacional escalonado

## Opções consideradas

### Opção A -- Camada única (escolher uma)

- Prós: simples.
- Contras: precisão OU recall, nunca os dois; sem auditoria progressiva.

### Opção B -- Multicamada em cascata, cada camada desligável

- C1 (regex + categoria + YAML curado): determinística, sempre ligada (ADR-003).
- C2 (TF-IDF + voto): estatística leve, default ligada.
- C3 (embeddings bge-m3 + similaridade): semântica, default ligada (ADR-009).
- C4 (LLM via Ollama local): opcional, **desligada por default** (alinha com ADR-006: LLM externa não é permitida).
- Prós: cada item recebe múltiplos sinais; cidadão escolhe quais camadas confiar; explicabilidade vem de quais camadas marcaram positivo.
- Contras: contrato entre camadas precisa ser fixo; UI precisa expor o estado das camadas.

## Decisão

Escolhida: **Opção B**.

Justificativa: combina precisão (C1), volume (C2), nuance (C3) e profundidade opcional (C4) com explicabilidade total. Cada camada é desligável independentemente; manifesto da sessão registra quais foram usadas, garantindo reprodutibilidade.

## Consequências

**Positivas:**

- Cobertura cresce com sobreposição de sinais.
- Cidadão pode auditar cada camada isoladamente.
- C4 fica fora do default -- nenhum dado sai da máquina sem ato deliberado do usuário.

**Negativas / custos assumidos:**

- Função de combinação dos sinais precisa ser definida e fixada (S27).
- Cada camada tem sua sprint dedicada (S27 cobre C1+C2; S28 cobre C3; S34b cobre C4).
- UI precisa expor estado por camada -- complexidade extra na seção 10.

## Pendências / follow-ups

- [ ] S27 implementa C1 e C2.
- [ ] S28 implementa C3 (embeddings).
- [ ] S34b implementa C4 (LLM opcional).

## Links

- Plano: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` (seção 3)
- Sprints relacionadas: S22 (registro), S27, S28, S34b
