# Cache transversal e banco DuckDB unificado (S26 + S27.1)

> Última atualização: 2026-04-28 (S27.1 -- ``votacoes.proposicao_id`` via Migration M002)

## Visão geral

A camada de ETL do Hemiciclo (`src/hemiciclo/etl/`) consolida os parquets
produzidos pelas sprints S24 (Câmara) e S25 (Senado) em um banco DuckDB
analítico unificado. As tabelas usam um discriminador `casa` (`'camara'`
ou `'senado'`) em vez de tabelas separadas, simplificando queries
cross-casa que serão exigidas por S27 (classificador), S29 (sessão runner)
e S30 (pipeline).

```
~/hemiciclo/
├── cache/
│   ├── camara/                    # parquets brutos S24 (proposicoes, votacoes, ...)
│   ├── senado/                    # parquets brutos S25 (materias, votacoes_senado, ...)
│   ├── checkpoints/               # camara_<hash>.json, senado_<hash>.json
│   ├── discursos/<sha256>.parquet # cache transversal por hash de conteúdo
│   ├── proposicoes/<id>.parquet   # cache transversal por id composto
│   └── hemiciclo.duckdb           # banco analítico unificado (S26)
└── ...
```

## Schema DuckDB (v2 -- S27.1)

Cinco tabelas de domínio + uma tabela meta (`_migrations`):

| Tabela          | PK                                  | Conteúdo |
|-----------------|-------------------------------------|----------|
| `proposicoes`   | `(id, casa)`                        | PLs/projetos: id, sigla, número, ano, ementa, tema oficial, autor, data, status, URL inteiro teor, hash do conteúdo |
| `votacoes`      | `(id, casa)`                        | Votações nominais: id (VARCHAR para acomodar Câmara str + Senado int), data, descrição, resultado, totais e **`proposicao_id BIGINT` (v2, S27.1)** apontando à proposição/matéria votada |
| `votos`         | `(votacao_id, parlamentar_id, casa)` | Voto individual: tipo (Sim/Não/Abstenção/...), data |
| `discursos`     | `hash_conteudo` (SHA256)            | Texto bruto + parlamentar + casa + data + súmario; hash é a chave universal |
| `parlamentares` | `(id, casa)`                        | Cadastro: nome, partido, UF, ativo, foto |

Todos os DDLs usam `IF NOT EXISTS` -- chamadas repetidas são idempotentes.

### Histórico de versões

- **v1 (S26 / M001)** -- 5 tabelas de domínio + meta ``_migrations``.
- **v2 (S27.1 / M002)** -- ``votacoes.proposicao_id BIGINT``: destrava o
  JOIN ``votos × votacoes × proposições relevantes`` no classificador C1
  e nos relatórios de histórico/grafo. Em DBs v1 antigos a coluna entra
  com ``NULL``; recall completo só vem após recoletar/reconsolidar.

### Atalhos no Python

- ``hemiciclo.etl.schema.criar_schema_v1(conn)`` -- DDL puro do schema v1
  (compatibilidade com testes legados; pula a meta ``_migrations``).
- ``hemiciclo.etl.schema.criar_schema(conn)`` -- aplica todas as migrations
  registradas em :data:`hemiciclo.etl.migrations.MIGRATIONS`. Atalho
  recomendado para fixtures e smoke locais.
- ``SCHEMA_VERSAO_ATUAL = 2`` -- versão alvo do schema "vivo"
  (``criar_schema`` deixa o DB nessa versão).

### Indexes mínimos

- `idx_proposicoes_ementa` -- acelera buscas de tópico (S27).
- `idx_discursos_parlamentar` -- acelera relatório multidimensional (S31).
- `idx_votos_parlamentar` -- acelera coautoria/eixo de posição (S32).

## Migrations sequenciais

`src/hemiciclo/etl/migrations.py` define `Migration(versao, descricao, aplicar)`
e a lista `MIGRATIONS`, ordenada por versão crescente. Hoje temos:

- **M001** -- cria schema v1 (delega para `criar_schema_v1`).
- **M002** -- ``ALTER TABLE votacoes ADD COLUMN IF NOT EXISTS proposicao_id BIGINT``
  (S27.1, destrava JOIN do classificador C1).

Migrations futuras (M003+) serão adicionadas como sprints posteriores
quando o schema evoluir; jamais editamos migrations já publicadas.

`aplicar_migrations(conn) -> int` é idempotente: lê a versão atual em
`_migrations` e roda só as pendentes. Em base nova, retorna `len(MIGRATIONS)`.
Em base atualizada, retorna 0.

### Aplicar M002 em DBs já existentes

Para DBs criados antes de S27.1 (ex.: sessões de pesquisa antigas em
``~/hemiciclo/sessoes/<id>/dados.duckdb``), use o utilitário CLI:

```bash
python scripts/migracao_m002.py --db-path ~/hemiciclo/sessoes/<id>/dados.duckdb
```

Idempotente. Adiciona ``proposicao_id`` (preenche com ``NULL`` para
linhas existentes). Para repopular ``proposicao_id`` numa sessão, use
``hemiciclo coletar camara/senado --tipos votacoes`` seguido de
``hemiciclo db consolidar``.

## Cache transversal por hash

Conteúdos pesados (transcrições RTF de discursos, inteiro teor de proposições)
ficam em parquets separados nomeados pelo SHA256 do conteúdo:

- `caminho_cache_discurso(home, sha256) -> <home>/cache/discursos/<sha256>.parquet`
- `caminho_cache_proposicao(home, id_completo) -> <home>/cache/proposicoes/<id>.parquet`

A escrita usa `tempfile.NamedTemporaryFile` + `Path.replace` (atômico em
POSIX) -- mesma estratégia de
[`coleta.checkpoint.salvar_checkpoint`](./coleta.md#checkpoint).

**Vantagem**: Sessão de Pesquisa A baixa um discurso de aborto. Sessão B
procura "porte de armas" mas o mesmo deputado fala em ambas as
proposições -- o discurso já está em cache, pulando rede.

## Consolidador

`consolidar_parquets_em_duckdb(dir_parquets: Path, db_path: Path) -> dict[str, int]`
mapeia 10 nomes de arquivo para 5 tabelas:

| Arquivo                   | Tabela alvo      | Casa    |
|---------------------------|------------------|---------|
| `proposicoes.parquet`     | `proposicoes`    | camara (do parquet) |
| `materias.parquet`        | `proposicoes`    | senado (do parquet) |
| `votacoes.parquet`        | `votacoes`       | camara (do parquet) |
| `votacoes_senado.parquet` | `votacoes`       | senado (do parquet) |
| `votos.parquet`           | `votos`          | camara (constante)  |
| `votos_senado.parquet`    | `votos`          | senado (constante)  |
| `discursos.parquet`       | `discursos`      | camara (constante)  |
| `discursos_senado.parquet`| `discursos`      | senado (constante)  |
| `deputados.parquet`       | `parlamentares`  | camara (constante)  |
| `senadores.parquet`       | `parlamentares`  | senado (constante)  |

Cada inserção usa `INSERT OR IGNORE INTO ... SELECT ... FROM read_parquet(?)`,
permitindo reconsolidação idempotente sem duplicar linhas. Arquivos
corrompidos são logados via Loguru e ignorados, não interrompendo a
consolidação dos demais.

## CLI

```bash
# Cria/atualiza schema (idempotente)
hemiciclo db init [--db-path /path/to/hemiciclo.duckdb]

# Carrega parquets em DuckDB
hemiciclo db consolidar --parquets <dir> [--db-path ...]

# Mostra contagens por tabela e versão de schema
hemiciclo db info [--db-path ...]
```

Default `--db-path`: `~/hemiciclo/cache/hemiciclo.duckdb`.

## Queries comuns (referência)

```sql
-- Todas as proposições sobre aborto, qualquer casa
SELECT casa, sigla, numero, ano, ementa
FROM proposicoes
WHERE ementa LIKE '%aborto%'
ORDER BY ano DESC, casa;

-- Discursos de um parlamentar específico (cross-casa via hash)
SELECT d.casa, d.data, d.sumario
FROM discursos d
WHERE d.parlamentar_id = 12345 AND d.casa = 'camara'
ORDER BY d.data DESC;

-- Contagem por casa após consolidar
SELECT casa, COUNT(*) AS total
FROM proposicoes
GROUP BY casa;
```

## Smoke local end-to-end

```bash
# 1. cria schema
uv run hemiciclo db init --db-path /tmp/hemi.duckdb

# 2. coleta amostras (precisa de internet)
uv run hemiciclo coletar camara --legislatura 57 --tipos proposicoes --max-itens 10 --output /tmp/c
uv run hemiciclo coletar senado --ano 2024 --tipos materias --max-itens 10 --output /tmp/s

# 3. consolida em DuckDB
uv run hemiciclo db consolidar --parquets /tmp/c --db-path /tmp/hemi.duckdb
uv run hemiciclo db consolidar --parquets /tmp/s --db-path /tmp/hemi.duckdb

# 4. inspeciona
uv run hemiciclo db info --db-path /tmp/hemi.duckdb
uv run python -c "
import duckdb
conn = duckdb.connect('/tmp/hemi.duckdb')
print(conn.execute('SELECT casa, COUNT(*) FROM proposicoes GROUP BY casa').fetchall())
"
# Esperado: [('camara', 10), ('senado', 10)]
```

## Decisões registradas

- ADR-012 (cache SHA256 + DuckDB analítico) -- imutável; toda mudança
  estrutural exige novo ADR.
- Tabela única `proposicoes` com `casa` discriminador (não duas tabelas
  separadas) -- queries cross-casa triviais.
- `votacao_id` é `VARCHAR` mesmo quando o Senado usa Int -- aceita ambas
  via CAST no consolidador, sem migração futura quando o schema mudar.
- `hash_conteudo` é `VARCHAR` -- aceita versão 16-char (S24/S25 default)
  e 64-char (futuro). A discriminação fica para S25.1.
