# ADR-001 -- Migração de R para Python 3.11+ com Streamlit

- **Status:** accepted
- **Data:** 2026-04-27
- **Decisores:** @AndreBFarias
- **Tags:** stack, infra

## Contexto e problema

O Hemiciclo v1 era um conjunto de scripts R focado em rankings agregados de discursos e proposições. Para virar uma plataforma cidadã de perfilamento parlamentar com classificação semântica, embeddings, dashboard interativo e Sessões de Pesquisa persistentes, R impunha custos altos: ecossistema de ML mais frágil, integração débil com bibliotecas de embeddings modernas, dashboard via Shiny menos ergonômico que alternativas Python, e curva de manutenção mais íngreme para colaboradores externos.

## Drivers de decisão

- Ecossistema maduro de ML / NLP / embeddings
- Dashboard interativo de baixo atrito para o usuário final
- Tipagem estática viável (Mypy strict)
- Atratividade para contribuidores
- Reaproveitamento direto de bibliotecas estado-da-arte (BERTopic, FlagEmbedding, DuckDB, Polars)

## Opções consideradas

### Opção A -- Manter R + Shiny + reticulate

- Prós: continuidade do código v1; Shiny tem boa integração com gráficos.
- Contras: ecossistema de embeddings frágil; tipagem inexistente; reticulate é ponte friável; menor pool de contribuidores.

### Opção B -- Python 3.11+ + Streamlit + DuckDB + Polars

- Prós: stack moderno; tipagem estrita; dashboards rápidos de fazer; embeddings de ponta nativos; melhor integração CI/CD.
- Contras: reescrita; perda temporária do que já funcionava em R (mitigada por preservação em branch `legacy-r`).

## Decisão

Escolhida: **Opção B**.

Justificativa: o salto de funcionalidade alvo (multi-camada, sessões persistentes, embeddings, grafos) é incompatível com o custo/benefício de manter R. A reescrita é compatível com a postura indutiva e iterativa do projeto -- versão 2.0 nasce com fundações testáveis, R fica preservado em `legacy-r` para auditoria histórica.

## Consequências

**Positivas:**

- Permite todas as ADRs subsequentes (003, 008, 009, 011, 012).
- Onboarding facilitado para qualquer dev Python.
- Dashboard Streamlit consistente em todos os SOs suportados.
- Tipagem estrita desde o dia 1 (ADR-019).

**Negativas / custos assumidos:**

- Esforço de migração distribuído nas sprints S22-S37.
- `install.sh/.bat` exigem Python 3.11+ pré-instalado (ADR-014); abordagem PyInstaller fica fora do v1.
- Documentação e CI precisam ser refeitos do zero.

## Pendências / follow-ups

- [ ] ADR-014 trata exigência de Python pré-instalado.
- [ ] ADR-015 trata matriz CI multi-OS.
- [ ] ADR-019 trata portões de qualidade (Ruff, Mypy, pytest cov).

## Links

- Plano: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` (seção 5.3)
- Sprint relacionada: S22
