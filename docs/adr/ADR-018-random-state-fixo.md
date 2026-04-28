# ADR-018 -- random_state fixo em todos os modelos estatísticos

- **Status:** accepted
- **Data:** 2026-04-28
- **Decisores:** @AndreBFarias
- **Tags:** modelo, qualidade, determinismo

## Contexto e problema

A análise política do Hemiciclo precisa ser **reproduzível bit-a-bit**.
Um pesquisador A roda a sessão, exporta o zip, manda para o pesquisador B;
B importa e re-treina; o resultado **deve** ser idêntico, ou os dois vão
discutir achados que vêm de aleatoriedade do scikit-learn, não de dados
reais.

Modelos estatísticos têm múltiplas fontes de aleatoriedade: amostragem,
inicialização, split train/test, solver de regressão, descida de gradiente.
Sem fixar a semente em **todos os pontos**, o resultado varia a cada run.

## Drivers de decisão

- Reprodutibilidade do achado científico.
- Auditabilidade radical (ADR-006).
- Confiança do usuário cidadão no que vê.
- Detecção de regressão de modelo via sentinela.

## Opções consideradas

### Opção A -- Aleatoriedade livre

- Prós: maior generalização teórica.
- Contras: viola reprodutibilidade, dois runs dão resultados diferentes.

### Opção B -- random_state global em config + repassado em cada chamada

- Prós: determinismo total, único ponto de mudança, auditável.
- Contras: precisa lembrar de passar em cada construção de estimador.

## Decisão

Escolhida: **Opção B**.

- `Configuracao.random_state = 42` (default), override via env
  `HEMICICLO_RANDOM_STATE`.
- Todo construtor sklearn / numpy / scipy recebe `random_state=cfg.random_state`
  ou equivalente (`numpy.random.default_rng(seed)`).
- Amostragem DuckDB usa `USING SAMPLE reservoir(N ROWS) REPEATABLE (42)`.
- BERTopic / UMAP recebem semente em construtor.
- Mesmo seed propaga em: `train_test_split`, `LogisticRegression`,
  `PCA`, `KMeans`, `WordCloud`, Louvain.

## Consequências

**Positivas:**

- Dois pesquisadores rodando a mesma sessão obtêm bytes idênticos.
- Sentinela de modelo detecta regressão silenciosa via SHA256 do resultado.
- Reprodutibilidade vira contrato testável.

**Negativas / custos assumidos:**

- Em produção real seria bom variar o seed em bootstrap CV (não aplicável
  neste produto cidadão).
- Mudança de seed quebra hash de modelos persistidos (esperado: nova versão).

## Pendências / follow-ups

- [x] S28 implementa amostragem reproduzível e PCA com seed.
- [x] S33/S34 herdam o padrão.

## Links

- Sprint relacionada: S22, S28, S31, S32, S33, S34
- Invariante: I3 do `VALIDATOR_BRIEF.md`
- Documentação: `src/hemiciclo/config.py`
