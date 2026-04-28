# ADR-005 -- Caminho indutivo data-driven (não dedutivo-teórico)

- **Status:** accepted
- **Data:** 2026-04-27
- **Decisores:** @AndreBFarias
- **Tags:** metodologia, ml

## Contexto e problema

Há duas posturas possíveis ao construir uma plataforma de perfilamento: (a) partir de uma teoria política a priori (ex: clivagens clássicas esquerda-direita, modelo de spatial voting), encaixar dados nela e medir desvio; (b) deixar a estrutura emergir dos dados (clustering não-supervisionado, redução de dimensionalidade, BERTopic) e nomear posteriormente o que emerge. As duas são legítimas em ciência política, mas têm implicações distintas para um projeto cidadão.

## Drivers de decisão

- Compromisso com o que os dados realmente mostram
- Resistência a pré-conceitos teóricos do autor
- Capacidade de lidar com configurações políticas brasileiras que não cabem em molduras estrangeiras
- Auditabilidade da metodologia

## Opções consideradas

### Opção A -- Dedutiva (modelo a priori)

- Prós: hipóteses claras; estatística clássica facilitada; literatura abundante.
- Contras: enquadra os dados em categorias pré-existentes; pode mascarar fenômenos emergentes; sensível a viés do projetista.

### Opção B -- Indutiva (data-driven)

- Prós: deixa a estrutura emergir; mais honesta com a especificidade do Congresso brasileiro; permite descobertas inesperadas.
- Contras: nomenclatura dos clusters/eixos vira responsabilidade explícita; estatística inferencial é mais delicada (testes pós-hoc).

## Decisão

Escolhida: **Opção B**.

Justificativa: o manifesto do projeto exige que ele seja útil sem precisar comprar uma teoria pré-concebida. O caminho indutivo casa com PCA + BERTopic + clustering pós-embeddings, e a interpretação fica como um passo separado e explícito (rotulação de clusters, sempre auditável). Casos de uso teóricos podem ser feitos por cima dos dados emergentes.

## Consequências

**Positivas:**

- Resultados são surpreendentes e específicos ao Brasil real.
- Reduz risco de confirmação de hipótese.
- Combina diretamente com ADR-008 (modelo base + ajuste local) e ADR-009 (embeddings).

**Negativas / custos assumidos:**

- Rotulagem de clusters precisa ser feita com cuidado e versionada.
- Métricas de validação interna (silhouette, Davies-Bouldin) viram primeira ordem.
- Comunicação com leigos exige passo extra de tradução.

## Pendências / follow-ups

- [ ] ADR-008 detalha modelo base global + ajuste local.
- [ ] ADR-009 detalha embeddings.
- [ ] Sprints S28 e S30 implementam pipeline indutivo.

## Links

- Plano: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` (seção 2)
- Sprints relacionadas: S22 (registro), S28, S30
