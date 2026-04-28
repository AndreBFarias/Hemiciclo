# Classificação Multicamada

Implementação de **D11 / ADR-011** -- o motor de classificação de proposições, parlamentares e discursos por tópico opera em quatro camadas em cascata. Cada camada é independente, desligável e barata o suficiente para rodar localmente.

```
+-----+    +-----+    +-----+    +-----+
|  C1 | -> |  C2 | -> |  C3 | -> |  C4 |
+-----+    +-----+    +-----+    +-----+
  ^          ^          ^          ^
  |          |          |          |
  | Regex    | TF-IDF   | bge-m3   | LLM (opcional)
  | Categoria| Intens.  | Cosseno  | Resumo + sentimento
  | Voto     | discurso | em alvo  | Detecção de subterfúgio
```

A invariante D11: **o sistema entrega resultado útil mesmo com C3 e C4 desligados**. C1 + C2 (S27) é o baseline que atende essa invariante.

## Status atual

| Camada | Sprint | Estado | Dependências |
|---|---|---|---|
| C1 (regex + categoria + voto) | S27 | DONE (2026-04-28) | DuckDB schema v1 (S26), tópicos YAML |
| C2 (TF-IDF + intensidade discursiva) | S27 | DONE (2026-04-28) | sklearn 1.4+, C1 |
| C3 (embeddings bge-m3) | S28 | READY após S27 | sentence-transformers, ~2 GB para o modelo |
| C4 (LLM opcional via ollama) | S34b | DEPENDS S30 | ollama local; cache por hash |

## Schema do tópico (`topicos/*.yaml`)

Cada arquivo `topicos/<slug>.yaml` é validado pelo JSON Schema em `topicos/_schema.yaml` (draft 2020-12). Campos:

| Campo | Tipo | Obrigatório | Uso |
|---|---|---|---|
| `nome` | string snake_case ASCII | sim | identificador, bate com filename |
| `versao` | int >= 1 | sim | versão semântica simples |
| `descricao_curta` | string 10-280 chars | sim | resumo PT-BR |
| `keywords` | lista string | sim | match `ILIKE` em ementa/discurso |
| `regex` | lista string | sim | regex Python -- `(?i)` para ignorar caixa |
| `mantenedor` | string | não | curador |
| `categorias_oficiais_camara` | lista string | não | match `tema_oficial` na Câmara |
| `categorias_oficiais_senado` | lista string | não | match no Senado |
| `proposicoes_seed` | lista de objetos | não | proposições-âncora |
| `exclusoes` | lista de `{regex, motivo?}` | não | filtra falsos positivos |
| `embeddings_seed` | lista string | não | C3 (S28+) |
| `limiar_similaridade` | float 0..1 | não | C3 (S28+) |

Validador: `python scripts/validar_topicos.py` (exit 0 / exit 1) -- também ativado como hook pre-commit `validar-topicos` e como step do CI.

## Camada 1 -- determinística

Função: `hemiciclo.modelos.classificador_c1`.

### `proposicoes_relevantes(topico, conn) -> pl.DataFrame`

1. SQL com `LOWER(ementa) LIKE '%kw%'` por keyword + `tema_oficial IN (...)` por categoria oficial. DuckDB regex é POSIX ERE, sintaxe diferente de Python -- por isso preferimos o filtro em duas etapas.
2. Polars filtra por **exclusões** (regex Python) sobre o resultado SQL.

Saída: DataFrame com `id, casa, sigla, numero, ano, ementa, tema_oficial, score_match`.

### `agregar_voto_por_parlamentar(props, conn) -> pl.DataFrame`

Calcula a `proporcao_sim` de cada parlamentar nas votações ligadas às proposições relevantes:

- `A_FAVOR` se `proporcao_sim >= 0.70`
- `CONTRA` se `proporcao_sim <= 0.30`
- `NEUTRO` no intervalo

#### Compatibilidade retroativa (S27.1)

A tabela `votacoes` ganhou a coluna `proposicao_id BIGINT` na S27.1 (Migration M002). A função `agregar_voto_por_parlamentar` chama `aplicar_migrations(conn)` antes do JOIN, garantindo compat com DBs v1 antigos -- a coluna é adicionada automaticamente, com `NULL` nas linhas existentes. Recall completo só vem após recoletar e reconsolidar os parquets pós-S27.1 (ou rodar `python scripts/migracao_m002.py --db-path <db>` para apenas aplicar a migration sem reconsolidar). O JOIN é direto, sem fallback dinâmico.

## Camada 2 -- estatística leve

Função: `hemiciclo.modelos.classificador_c2`.

### `tfidf_relevancia(props, max_features=100) -> pl.DataFrame`

Aplica `sklearn.feature_extraction.text.TfidfVectorizer` sobre as ementas de C1, soma os pesos por documento e devolve coluna `score_tfidf`. Quando `len(props) < 2`, preenche zeros (TF-IDF degenera com 1 doc).

**Determinismo**: `TfidfVectorizer` em si não tem `random_state`, mas os scores são reprodutíveis com:

1. Input ordenado: ordenamos `props` por `(casa, id)` antes do `fit_transform`.
2. `max_features` fixo = 100.
3. `lowercase=True`.

`sklearn` é importado lazy (dentro da função) para não onerar o boot do CLI.

### `intensidade_discursiva(parlamentar_id, casa, topico, conn) -> float`

Conta discursos do parlamentar que casam `Topico.casa_keywords()` e divide pelo total de discursos do parlamentar. Frequência relativa em `[0.0, 1.0]`.

## Orquestrador

Função: `hemiciclo.modelos.classificador.classificar()`.

Encadeia C1 e C2 em cascata, persiste o DataFrame de proposições em `<home>/cache/classificacoes/<topico>_<hash16>.parquet` (lição S26: cache transversal por hash) e devolve dict serializável:

```python
{
  "topico": "aborto",
  "versao_topico": 1,
  "camadas": ["regex", "tfidf", "votos"],
  "hash_db": "1a2b3c4d5e6f7890",
  "n_props": 2,
  "n_parlamentares": 3,
  "top_a_favor": [{"parlamentar_id": 100, "casa": "camara", ...}],
  "top_contra": [{"parlamentar_id": 200, "casa": "camara", ...}],
  "cache_parquet": "/home/.../cache/classificacoes/aborto_1a2b...parquet"
}
```

## CLI

```bash
hemiciclo classificar \
    --topico topicos/aborto.yaml \
    --db-path ~/hemiciclo/cache/hemiciclo.duckdb \
    --camadas regex,votos,tfidf \
    --top-n 100 \
    --output /tmp/aborto.json
```

Saída literal:

```
[classificar] topico=aborto props=2 parlamentares=3 em 0.04s camadas=['regex', 'tfidf', 'votos']
[classificar] topico=aborto JSON em /tmp/aborto.json
```

## Smoke local end-to-end

```bash
make check                                    # 202 testes verdes
python scripts/validar_topicos.py             # 3 topicos validados
uv run hemiciclo db init --db-path /tmp/hemi27.duckdb
uv run hemiciclo coletar camara --legislatura 57 --tipos proposicoes --max-itens 50 --output /tmp/c27
uv run hemiciclo db consolidar --parquets /tmp/c27 --db-path /tmp/hemi27.duckdb
uv run hemiciclo classificar --topico topicos/aborto.yaml --db-path /tmp/hemi27.duckdb --camadas regex --output /tmp/c1_aborto.json
```

Em smoke pequeno (50 proposições) é esperado que o tópico `aborto.yaml` não case nada -- isso valida o **pipeline**, não recall. Para recall, a sprint S24c (iterar 4 anos da legislatura) e o backfill via S24b alimentam um corpus maior.

## Decisões fundamentais

- **Regex Python, não DuckDB**: a aplicação de exclusões fica em Polars (`pl.col(...).str.contains(...)`) porque DuckDB usa POSIX ERE que diverge da sintaxe Python. Filtragem em duas etapas (SQL grosso + Polars fino).
- **Lazy import de sklearn**: 8 MB no disco + 200 ms de boot. Só carrega quando C2 é invocada de fato.
- **Cache por hash do DB**: chave = `sha256(absolute_path::mtime)[:16]`. Reaplica classificação só quando o DB mudou.
- **Camadas independentes**: a flag `--camadas` permite desligar qualquer combinação; testes `test_camadas_desligaveis` cobrem.

## Próximas sprints

- **S27.1 (DONE 2026-04-28, v2.1.0)**: ``proposicao_id`` em ``votacoes`` (Migration M002 + propagação coletor + consolidador + classificador sem fallback). Desbloqueou o JOIN de votos.
- **S28 (DONE)**: camada C3 -- embeddings bge-m3 + PCA + persistência do modelo base local.
- **S31 (DONE)**: dashboard Streamlit para visualizar ``top_a_favor`` / ``top_contra`` em cards.
- **Roadmap v2.1.x**: backfill automático de proposições por id, enriquecimento via ``GET /proposicoes/{id}`` (S24b), iteração 4 anos da legislatura quando ano=None (S24c).
