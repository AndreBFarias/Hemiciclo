# ADR-007 -- Sessão de Pesquisa como cidadão de primeira classe

- **Status:** accepted
- **Data:** 2026-04-27
- **Decisores:** @AndreBFarias
- **Tags:** infra, ux, manifesto

## Contexto e problema

Em ferramentas analíticas tradicionais, o "estado de uma pesquisa" é um conceito frouxo: filtros aplicados em uma interface, talvez exportados em CSV. Para o Hemiciclo, no entanto, uma pesquisa cidadã sobre um tópico envolve coleta, ETL, classificação multicamada, embeddings, projeção em eixos, grafos -- tudo isso pode levar minutos a horas e produzir vários gigabytes de artefatos. Tratar isso como "sessão volátil de UI" descarta valor e viola a soberania prometida em ADR-006.

## Drivers de decisão

- Cada pesquisa é um artefato científico arquivável
- Possibilidade de retomada após interrupção (queda de luz, kernel killer)
- Exportação/importação para auditoria por terceiros
- Reprodutibilidade exata

## Opções consideradas

### Opção A -- Sessão volátil (estado só na UI Streamlit)

- Prós: simples de implementar.
- Contras: perda total ao fechar; impossível auditar; impossível compartilhar; viola soberania.

### Opção B -- Cache leve de resultados em DuckDB compartilhado

- Prós: alguma persistência; reuso de dados.
- Contras: separa dados de parâmetros; difícil exportar coerentemente; difícil retomar com fidelidade.

### Opção C -- Sessão de Pesquisa como diretório autocontido

- Estrutura: `~/hemiciclo/sessoes/<id>/` com `params.json`, `status.json`, `pid.lock`, `dados.duckdb`, `discursos.parquet`, `votos.parquet`, `modelos_locais/`, `relatorio_state.json`, `log.txt`, `manifesto.json`.
- Prós: artefato científico completo; exportável (zip); retomável; auditável; reprodutível; combina com ADR-006.
- Contras: contrato grande -- toda a stack precisa respeitar a estrutura.

## Decisão

Escolhida: **Opção C**.

Justificativa: a Sessão é o objeto cidadão central -- o que João arquiva, compartilha com colega, auditável por outro pesquisador. Faz a UI ser stateless por cima de um filesystem rico. Combina com runner subprocess (ADR-013) e exportação zip (S35).

## Consequências

**Positivas:**

- Streamlit faz polling em `status.json`; fica desacoplado do processo pesado.
- Sessões podem ser zipadas e enviadas para outro computador (S35).
- Auditoria externa fica trivial: `unzip` + `tree` + `cat manifesto.json`.
- Sessão tem ciclo de vida claro (criada → coletando → ETL → ... → concluída/erro).

**Negativas / custos assumidos:**

- Contrato do filesystem precisa ser estável e versionado em `manifesto.json`.
- Migração entre versões da estrutura exige código de upgrade.

## Pendências / follow-ups

- [ ] ADR-013 detalha runner subprocess + status + pid.lock.
- [ ] S29 implementa runner.
- [ ] S35 implementa export/import.

## Links

- Plano: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` (seções 5.1 e 5.4)
- Sprints relacionadas: S22 (registro), S29, S35
