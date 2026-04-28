# ADR-004 -- Assinatura multidimensional com 7 eixos definidos

- **Status:** accepted
- **Data:** 2026-04-27
- **Decisores:** @AndreBFarias
- **Tags:** metodologia, ml

## Contexto e problema

Resumir um parlamentar a uma única dimensão (favor/contra, esquerda/direita, produtivo/improdutivo) descarta informação politicamente crítica. Para que a Sessão de Pesquisa entregue valor real ao cidadão, é necessário um vetor de descritores múltiplos, ortogonais o suficiente para discriminar perfis e legíveis o suficiente para ser auditado sem ML.

## Drivers de decisão

- Riqueza descritiva sem virar caixa-preta
- Cada eixo precisa ser explicável em uma frase
- Eixos derivam de dados verificáveis (voto, presença, discurso, PL)
- Composição de assinatura permite agrupamento e comparação

## Opções consideradas

### Opção A -- Score único agregado (estilo v1)

- Prós: simples; fácil de comunicar.
- Contras: descarta toda a estrutura de comportamento; sensível a critério arbitrário de pesos; já é o que o v1 faz.

### Opção B -- Vetor de embeddings opaco (PCA dos discursos)

- Prós: máxima expressividade.
- Contras: dimensões não interpretáveis; cidadão não consegue auditar; viola princípio de "rigor metodológico aberto".

### Opção C -- 7 eixos nomeados e definidos

- Eixos: posição, intensidade, hipocrisia, volatilidade, centralidade, convertibilidade, enquadramento.
- Prós: cada eixo tem definição operacional; permite auditoria; combina com clustering posterior; preserva dimensões úteis para a UI.
- Contras: definição operacional de cada eixo precisa ser fixada e versionada (cada eixo herda ADR de implementação em S27-S34).

## Decisão

Escolhida: **Opção C**.

Justificativa: "rigor metodológico equivalente ao que se vende a lobistas" exige eixos nomeados, não um vetor opaco. Sete eixos é suficiente para riqueza, baixo o suficiente para auditoria, e cada um tem mapeamento direto a um sinal observável.

Eixos:

1. **Posição** -- direção do voto agregado em um tópico (favor / contra / abstenção).
2. **Intensidade** -- frequência do parlamentar em discutir/votar o tópico.
3. **Hipocrisia** -- distância entre discurso e voto (cosseno entre embedding de discurso e sinalizado de voto).
4. **Volatilidade** -- variância temporal de posição.
5. **Centralidade** -- medida em grafos de coautoria/voto (ADR-013, S32).
6. **Convertibilidade** -- probabilidade de mudança de voto sob pressão (modelo ML em S34).
7. **Enquadramento** -- vocabulário e tópicos secundários trazidos pelo parlamentar (BERTopic).

## Consequências

**Positivas:**

- Cada eixo gera um descritor claro na UI (J2 do plano).
- Permite agrupamento e comparação multidimensional.
- Cada eixo pode ser desativado ou auditado independentemente.

**Negativas / custos assumidos:**

- Exige sprints distintas para implementar cada eixo com rigor (S30-S34).
- Exige documentação cuidadosa para o cidadão entender o que cada um significa.

## Pendências / follow-ups

- [ ] Cada eixo terá sua definição operacional fixada na sprint que o implementa.
- [ ] ADR-013 trata grafos (eixo 5).
- [ ] Eixo 6 (convertibilidade) depende de S34.

## Links

- Plano: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` (seção 2)
- Sprints relacionadas: S22 (registro), S30-S34 (implementação por eixo)
