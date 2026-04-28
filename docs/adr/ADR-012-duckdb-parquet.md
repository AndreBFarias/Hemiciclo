# ADR-012 -- DuckDB + Parquet como storage analítico local

- **Status:** accepted
- **Data:** 2026-04-28
- **Decisores:** @AndreBFarias
- **Tags:** storage, infra

## Contexto e problema

O Hemiciclo precisa armazenar localmente, na máquina do usuário, dados volumosos
do Congresso (proposições, votações, votos, discursos, parlamentares) e
permitir consultas analíticas rápidas sobre eles dentro de cada Sessão de
Pesquisa. SQLite é generalista e não tem desempenho competitivo em agregações
colunares; CSV bruto não tem schema; um RDBMS servidor (Postgres) viola
ADR-006 (tudo local, sem servidor central).

## Drivers de decisão

- Soberania local (ADR-006): zero servidor, zero porta aberta.
- Analytics colunar competitivo (group by, joins, agregações).
- Suporte nativo a Parquet (formato de troca canônico do ecossistema).
- Embarcável em processo Python (sem daemon).
- Licença permissiva compatível com GPL v3 do projeto.

## Opções consideradas

### Opção A -- SQLite

- Prós: ubiquidade, estabilidade, padrão do ecossistema Python.
- Contras: orientado a linhas, lento em agregações analíticas, sem suporte
  nativo a Parquet, JSON tipado limitado.

### Opção B -- DuckDB + Parquet

- Prós: vetorizado, colunar, leitura nativa de Parquet via `read_parquet`,
  embarcável sem daemon, MIT, performance comparável a Postgres em analytics
  locais.
- Contras: ecossistema mais novo (1.x estabilizado em 2024), menos extensões
  do que SQLite.

### Opção C -- Postgres local

- Prós: maturidade, recursos analíticos avançados.
- Contras: viola ADR-006 (daemon ouvindo porta), instalação complexa para
  o "João comum", incompatível com `install.sh` ergonômico.

## Decisão

Escolhida: **Opção B** -- DuckDB 1.x como motor analítico embarcado, com
Parquet como formato canônico de coleta (output de S24/S25) e consolidação
via `read_parquet` em tabelas DuckDB (S26).

## Consequências

**Positivas:**

- Consultas agregadas sobre milhões de votos em milissegundos.
- Round-trip Polars <-> DuckDB <-> Parquet sem cópia, via Apache Arrow.
- `dados.duckdb` por sessão é um arquivo único, portável, auditável.
- Zero processo daemon. Zero porta. Zero credencial.

**Negativas / custos assumidos:**

- Dependência runtime nova (`duckdb>=1.0`).
- Schema migrations via tabela `_migrations` interna (S26).
- Backup é cópia de arquivo; sem replicação automática (aceito por escopo).

## Pendências / follow-ups

- [x] S26 implementa schema v1 + migrations.
- [ ] S27.1 adiciona coluna `proposicao_id` em `votacoes` (Migration M002).

## Links

- Plano: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md`
- Sprint relacionada: S26
- Documentação: `docs/arquitetura/coleta.md`
