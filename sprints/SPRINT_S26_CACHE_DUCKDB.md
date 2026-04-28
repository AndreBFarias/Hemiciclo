# Sprint S26 -- Cache transversal SHA256 + DuckDB schema + migrations

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-28
**Autor:** @AndreBFarias
**Status:** DONE (2026-04-28)
**Depende de:** S22 (DONE), S24 (DONE), S25 (DONE)
**Bloqueia:** S27, S29
**Esforço:** P (1-2 dias)
**ADRs vinculados:** ADR-012 (DuckDB + Parquet como storage analítico)
**Branch:** feature/s26-cache-duckdb

---

## 1. Objetivo

Consolidar os parquets produzidos por S24 (Câmara) e S25 (Senado) em um **banco DuckDB analítico unificado** com schema versionado via migrations, e implementar **cache transversal por hash SHA256** que permite reaproveitar conteúdos já baixados entre sessões diferentes.

Entregáveis-chave:
- Schema DuckDB unificado em 5 tabelas (`proposicoes`, `votacoes`, `votos`, `discursos`, `parlamentares`) com `casa` como discriminador
- Sistema de migrations sequenciais (M001, M002, ...) executável idempotente
- Cache transversal `~/hemiciclo/cache/discursos/<hash>.parquet`, `~/hemiciclo/cache/proposicoes/<id_completo>.parquet` reutilizável entre sessões
- Função `consolidar_parquets_em_duckdb(dir_parquets, dir_duckdb)` que pega outputs de S24+S25 e popula
- CLI `hemiciclo db init` (cria schema + migrations) e `hemiciclo db consolidar` (carrega parquets em duckdb)

## 2. Contexto

S24 entrega `proposicoes.parquet`, `votacoes.parquet`, `votos.parquet`, `discursos.parquet`, `deputados.parquet`. S25 entrega `materias.parquet`, `votacoes_senado.parquet`, `votos_senado.parquet`, `discursos_senado.parquet`, `senadores.parquet`. **10 arquivos com schemas alinhados em 12 colunas pra entidades comparáveis** (proposicoes/materias, deputados/senadores).

S27 (próxima após S26) precisará rodar regex/TF-IDF sobre **todas as proposições** (Câmara + Senado) num único query SQL. Sem schema unificado, isso vira código fragmentado.

S29 (sessão runner) também precisa do schema unificado pra montar relatório multidimensional cruzando dados das duas casas.

**Cache transversal** evita que cada sessão re-baixe os mesmos discursos: hash SHA256 do conteúdo é a chave universal. Sessão A baixa discurso X de aborto → cache. Sessão B procura "porte de armas" mas o mesmo deputado fala em ambos os PLs → discurso X reusado.

## 3. Escopo

### 3.1 In-scope

- [ ] **Dependências**: `duckdb>=1.0` em runtime
- [ ] `uv.lock` regenerado
- [ ] **`src/hemiciclo/etl/__init__.py`** marker
- [ ] **`src/hemiciclo/etl/schema.py`** schema DuckDB unificado:
  - `SCHEMA_VERSAO = 1` constante
  - Função `criar_schema_v1(conn: duckdb.DuckDBPyConnection) -> None` cria 5 tabelas:
    - **`proposicoes`** (id, sigla, numero, ano, ementa, tema_oficial, autor_principal, data_apresentacao, status, url_inteiro_teor, casa, hash_conteudo, criado_em) -- PK = (id, casa)
    - **`votacoes`** (id, casa, data, hora, descricao, resultado, total_sim, total_nao, total_abstencao, total_obstrucao, criado_em) -- PK = (id, casa)
    - **`votos`** (votacao_id, parlamentar_id, casa, voto, data, criado_em) -- PK = (votacao_id, parlamentar_id, casa)
    - **`discursos`** (hash_conteudo, parlamentar_id, casa, data, hora, conteudo, fase_sessao, sumario, criado_em) -- PK = hash_conteudo
    - **`parlamentares`** (id, casa, nome, partido, uf, ativo, foto_url, criado_em) -- PK = (id, casa)
  - Tabela meta `_migrations` (versao INTEGER PK, aplicada_em TIMESTAMP) pra controle
  - Index em `proposicoes(ementa)`, `discursos(parlamentar_id)`, `votos(parlamentar_id)`
- [ ] **`src/hemiciclo/etl/migrations.py`** sistema de migrations:
  - `Migration` dataclass: `versao: int`, `descricao: str`, `aplicar(conn) -> None`
  - Lista `MIGRATIONS = [M001, M002, ...]` ordenada por versão
  - Função `aplicar_migrations(conn) -> int` -- aplica todas que faltam, retorna quantas. Idempotente.
  - **M001**: cria schema v1 (delega pra `schema.py:criar_schema_v1`)
  - Migrations futuras (M002+) ficam em sprints subsequentes
- [ ] **`src/hemiciclo/etl/cache.py`** cache transversal por hash:
  - `caminho_cache_discurso(home: Path, hash_sha256: str) -> Path` -> `<home>/cache/discursos/<hash>.parquet`
  - `caminho_cache_proposicao(home: Path, id_completo: str) -> Path` -> `<home>/cache/proposicoes/<id>.parquet`
  - `salvar_cache(df: pl.DataFrame, path: Path) -> None` (escrita atômica via tmpfile + replace)
  - `carregar_cache(path: Path) -> pl.DataFrame | None`
  - `existe_no_cache(path: Path) -> bool`
- [ ] **`src/hemiciclo/etl/consolidador.py`** carregar parquets em DuckDB:
  - `consolidar_parquets_em_duckdb(dir_parquets: Path, db_path: Path) -> dict[str, int]`:
    - Detecta arquivos parquets em `dir_parquets/` (proposicoes.parquet, votacoes.parquet, etc.)
    - Conecta DuckDB em `db_path`, aplica migrations
    - Para cada parquet: `INSERT OR IGNORE INTO <tabela> SELECT * FROM read_parquet(...)` 
    - Trata schemas Camara vs Senado (renomeia `materias` -> `proposicoes` mantendo `casa`)
    - Retorna dict com contagem de linhas inseridas por tabela
- [ ] **CLI `hemiciclo db`** subcomando paralelo a `coletar`:
  - `hemiciclo db init [--db-path /path/to/hemiciclo.duckdb]` -- cria schema vazio
  - `hemiciclo db consolidar --parquets <dir> [--db-path ...]` -- carrega parquets em duckdb
  - `hemiciclo db info [--db-path ...]` -- mostra contagens de cada tabela + versão de schema
  - Default db_path: `~/hemiciclo/cache/hemiciclo.duckdb`
- [ ] **Testes unit** em `tests/unit/test_etl_schema.py` (5 testes):
  - `test_criar_schema_v1_cria_5_tabelas`
  - `test_criar_schema_v1_cria_tabela_migrations`
  - `test_pks_definidas_corretamente`
  - `test_indices_criados`
  - `test_idempotente` (chamar 2x não falha)
- [ ] **Testes unit** em `tests/unit/test_etl_migrations.py` (4 testes):
  - `test_aplicar_migrations_em_db_vazio_aplica_todas`
  - `test_aplicar_migrations_em_db_atualizado_nao_faz_nada`
  - `test_aplicar_migrations_em_db_parcial_aplica_pendentes`
  - `test_versao_atual_lida_corretamente`
- [ ] **Testes unit** em `tests/unit/test_etl_cache.py` (5 testes):
  - `test_caminho_cache_discurso_usa_hash`
  - `test_salvar_cache_escrita_atomica`
  - `test_carregar_cache_inexistente_retorna_none`
  - `test_round_trip_dataframe_polars`
  - `test_existe_no_cache_detecta_arquivo`
- [ ] **Testes unit** em `tests/unit/test_etl_consolidador.py` (5 testes):
  - `test_consolidar_proposicoes_camara` -- fixture parquet 10 props -> insere 10 rows
  - `test_consolidar_materias_senado` -- mapeia para mesma tabela com casa=senado
  - `test_consolidar_idempotente` -- rodar 2x não duplica (INSERT OR IGNORE)
  - `test_dir_vazio_nao_falha`
  - `test_arquivo_corrompido_loga_e_continua`
- [ ] **Testes integração** em `tests/integracao/test_etl_e2e.py` (3 testes):
  - `test_init_consolidar_info_workflow` -- ciclo completo CLI: init → consolidar parquets de fixture → info mostra contagens
  - `test_consolidar_camara_e_senado_juntos` -- proposicoes e materias na mesma tabela com discriminador casa
  - `test_query_cross_casa` -- SELECT FROM proposicoes WHERE ementa LIKE '%aborto%' retorna props de ambas as casas
- [ ] **Test sentinela** em `test_sentinela.py`:
  - `test_db_init_help` (com env COLUMNS=200 etc — lição S24)
  - `test_db_consolidar_help`
  - `test_db_info_em_db_vazio`
- [ ] **`docs/arquitetura/cache_e_db.md`** documentando: schema DuckDB, política de migrations, cache transversal, queries comuns
- [ ] **`CHANGELOG.md`** entrada `[Unreleased]` com bullet `feat(etl): cache transversal SHA256 + DuckDB schema unificado + migrations`

### 3.2 Out-of-scope (explícito)

- **Mapeamento tópico → proposições** -- fica em S27
- **Embeddings + bge-m3** -- fica em S28
- **Sessão runner** -- fica em S29
- **Pipeline integrado coleta→ETL→modelagem** -- fica em S30
- **Dashboard de relatório** -- fica em S31
- **Performance tuning específico** (índices secundários, partitioning) -- otimização futura
- **Migrations futuras** (M002+) -- aplicáveis quando schema evoluir

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `src/hemiciclo/etl/__init__.py` | Marker |
| `src/hemiciclo/etl/schema.py` | Schema DuckDB v1 (5 tabelas) |
| `src/hemiciclo/etl/migrations.py` | Sistema de migrations sequenciais |
| `src/hemiciclo/etl/cache.py` | Cache transversal por hash SHA256 |
| `src/hemiciclo/etl/consolidador.py` | Carrega parquets em DuckDB |
| `tests/unit/test_etl_schema.py` | 5 testes |
| `tests/unit/test_etl_migrations.py` | 4 testes |
| `tests/unit/test_etl_cache.py` | 5 testes |
| `tests/unit/test_etl_consolidador.py` | 5 testes |
| `tests/integracao/test_etl_e2e.py` | 3 testes |
| `docs/arquitetura/cache_e_db.md` | Documentação técnica |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `pyproject.toml` | Adiciona duckdb>=1.0 |
| `uv.lock` | Regenerado |
| `src/hemiciclo/cli.py` | Subcomando `db` (init, consolidar, info) |
| `tests/unit/test_sentinela.py` | 3 testes db CLI |
| `CHANGELOG.md` | Entrada [Unreleased] |
| `sprints/ORDEM.md` | S26 -> DONE |

## 5. Implementação detalhada

### 5.1 Passo a passo

1. Confirmar branch `feature/s26-cache-duckdb`.
2. Adicionar `duckdb>=1.0` ao pyproject; `uv sync --all-extras`.
3. Implementar `etl/schema.py` (constante VERSAO + função `criar_schema_v1`).
4. Escrever `tests/unit/test_etl_schema.py` (5 testes).
5. Implementar `etl/migrations.py` (Migration dataclass + lista MIGRATIONS + função aplicar).
6. Escrever `tests/unit/test_etl_migrations.py` (4 testes).
7. Implementar `etl/cache.py` (4 funções: caminho/salvar/carregar/existe).
8. Escrever `tests/unit/test_etl_cache.py` (5 testes).
9. Implementar `etl/consolidador.py` (`consolidar_parquets_em_duckdb`).
10. Escrever `tests/unit/test_etl_consolidador.py` (5 testes com fixtures parquets pequenas).
11. Adicionar subcomando `db` em `cli.py` (3 ações: init, consolidar, info).
12. Escrever `test_db_*_help` em `test_sentinela.py` com COLUMNS=200 (lição S24).
13. Escrever `tests/integracao/test_etl_e2e.py` (3 testes ciclo completo).
14. Escrever `docs/arquitetura/cache_e_db.md`.
15. Atualizar `CHANGELOG.md`.
16. Smoke local: rodar coleta S24 + S25 com `--max-itens 10`, depois `hemiciclo db consolidar --parquets <dir>`, depois `hemiciclo db info` mostra `proposicoes: 20, materias_count: 0` (ambas em tabela proposicoes com `casa` distinto).
17. `make check` deve passar com cobertura ≥ 90%.
18. Atualizar `sprints/ORDEM.md` mudando S26 para DONE.

### 5.2 Decisões técnicas

- **DuckDB sobre SQLite** -- colunar, otimizado pra análise (D1 do plano R2). 
- **Schema unificado em 1 tabela `proposicoes`** com `casa` discriminador (em vez de 2 tabelas separadas) -- queries cross-casa (que S27/S30 farão) ficam triviais com `WHERE casa IN ('camara','senado')`.
- **Migrations versionadas** com tabela meta `_migrations` -- futuro evoluível sem quebrar bases existentes.
- **`INSERT OR IGNORE`** -- idempotência ao reconsolidar parquets atualizados sem duplicar.
- **Cache transversal por hash** ortogonal ao DuckDB -- discursos pesados (RTF longo) ficam em parquet por hash; DuckDB só armazena metadados + reference.
- **Polars + DuckDB** integram nativamente -- `pl.DataFrame.to_arrow()` ou `read_parquet()` direto no SQL DuckDB.

### 5.3 Trecho de referência -- `etl/schema.py`

```python
"""Schema DuckDB unificado para Camara + Senado."""

from __future__ import annotations

import duckdb

SCHEMA_VERSAO = 1


def criar_schema_v1(conn: duckdb.DuckDBPyConnection) -> None:
    """Cria 5 tabelas + meta de migrations. Idempotente."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            versao INTEGER PRIMARY KEY,
            aplicada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            descricao VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS proposicoes (
            id BIGINT NOT NULL,
            casa VARCHAR NOT NULL,
            sigla VARCHAR,
            numero INTEGER,
            ano INTEGER,
            ementa TEXT,
            tema_oficial VARCHAR,
            autor_principal VARCHAR,
            data_apresentacao DATE,
            status VARCHAR,
            url_inteiro_teor VARCHAR,
            hash_conteudo VARCHAR,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id, casa)
        )
    """)
    # ... (votacoes, votos, discursos, parlamentares analogos)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_proposicoes_ementa ON proposicoes USING (ementa)")
```

### 5.4 Trecho de referência -- `etl/cache.py`

```python
"""Cache transversal por hash SHA256."""

from __future__ import annotations

import tempfile
from pathlib import Path

import polars as pl


def caminho_cache_discurso(home: Path, hash_sha256: str) -> Path:
    return home / "cache" / "discursos" / f"{hash_sha256}.parquet"


def caminho_cache_proposicao(home: Path, id_completo: str) -> Path:
    return home / "cache" / "proposicoes" / f"{id_completo}.parquet"


def salvar_cache(df: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, suffix=".tmp", delete=False
    ) as tmp:
        tmp_path = Path(tmp.name)
    df.write_parquet(tmp_path)
    tmp_path.replace(path)


def carregar_cache(path: Path) -> pl.DataFrame | None:
    if not path.exists():
        return None
    return pl.read_parquet(path)


def existe_no_cache(path: Path) -> bool:
    return path.exists()
```

## 6. Testes (resumo)

- **5** schema (5 tabelas, PKs, índices, idempotente)
- **4** migrations (vazio, atualizado, parcial, versão atual)
- **5** cache (caminho hash, escrita atômica, round-trip Polars)
- **5** consolidador (Câmara, Senado, idempotente, vazio, corrompido)
- **3** integração (workflow CLI, cross-casa, query LIKE)
- **3** CLI sentinela
- **Total: 25 testes novos** + 144 herdados = 169 testes na suíte total.

## 7. Proof-of-work runtime-real

**Comando local:**

```bash
$ make check
$ uv run hemiciclo db init --db-path /tmp/hemi.duckdb
$ uv run hemiciclo coletar camara --legislatura 57 --tipos proposicoes --max-itens 10 --output /tmp/c
$ uv run hemiciclo coletar senado --ano 2024 --tipos materias --max-itens 10 --output /tmp/s
$ uv run hemiciclo db consolidar --parquets /tmp/c --db-path /tmp/hemi.duckdb
$ uv run hemiciclo db consolidar --parquets /tmp/s --db-path /tmp/hemi.duckdb
$ uv run hemiciclo db info --db-path /tmp/hemi.duckdb
$ uv run python -c "import duckdb; conn = duckdb.connect('/tmp/hemi.duckdb'); print(conn.execute(\"SELECT casa, COUNT(*) FROM proposicoes GROUP BY casa\").fetchall())"
```

**Saída esperada:**

```
make check: 169 passed, cobertura ≥ 90%
[db][init] schema v1 criado em /tmp/hemi.duckdb
[coleta][camara] 10 proposicoes baixadas
[coleta][senado] 10 materias baixadas
[db][consolidar] proposicoes: +10 rows
[db][consolidar] proposicoes: +10 rows
[db][info] schema v1, proposicoes: 20, votacoes: 0, votos: 0, discursos: 0, parlamentares: 0

[('camara', 10), ('senado', 10)]
```

**Critério de aceite:**

- [ ] `make check` 169 testes verdes, cobertura ≥ 90%
- [ ] DB DuckDB criado com 5 tabelas + meta `_migrations`
- [ ] Parquets de S24 e S25 consolidados na mesma tabela `proposicoes` com `casa` discriminador
- [ ] `hemiciclo db info` mostra contagens corretas
- [ ] Query SQL cross-casa funciona (`WHERE casa = 'camara' UNION casa = 'senado'`)
- [ ] Cache transversal salva e carrega DataFrames Polars
- [ ] Migrations idempotentes (rodar 2x não falha)
- [ ] Mypy --strict zero erros
- [ ] Ruff zero violações
- [ ] CI verde nos 6 jobs do PR
- [ ] CHANGELOG.md atualizado

## 8. Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| DuckDB 1.0 incompatível com Polars 1.0 | B | A | Pinning explícito; testes integração pegam cedo |
| `INSERT OR IGNORE` mascarando bug de duplicação real | M | M | Teste `test_consolidar_idempotente` verifica contagem; logs imprimem rows ignoradas |
| Schema diferente entre Câmara e Senado parquets | A | A | Mapeamento explícito no consolidador; testes cobrem ambos |
| Tabela `_migrations` corrompida bloqueia atualização | B | A | DROP + recriar é fluxo aceitável em projeto novo |
| Cache transversal ocupar muito disco | M | M | Apenas discursos hashados; metadados ficam só no DuckDB |

## 9. Validação multi-agente

**Executor (`executor-sprint`):** Implementa, smoke local, NÃO push, NÃO PR.

**Validador (`validador-sprint`):** Roda proof-of-work, smoke real do ciclo S24+S25→DuckDB, verifica I1-I12, decide.

## 10. Próximo passo após DONE

S27 (classificador C1+C2: regex + categoria oficial + voto + TF-IDF + YAML schema) -- usa DuckDB como fonte de verdade.
