# Sprint S27 -- Classificador C1+C2: regex + categoria oficial + voto + TF-IDF + YAML schema

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-28
**Autor:** @AndreBFarias
**Status:** DONE (2026-04-28)
**Depende de:** S22 (DONE), S26 (DONE)
**Bloqueia:** S28
**Esforço:** M (3-5 dias)
**ADRs vinculados:** ADR-003 (mapeamento tópico->PL híbrido), ADR-011 (classificação multicamada)
**Branch:** feature/s27-classificador-c1-c2

---

## 1. Objetivo

Implementar **camadas 1 e 2 do classificador multicamada** (D11/ADR-011 do plano R2):

- **Camada 1 (Determinística)**: keywords + regex sobre ementas + categorias oficiais Câmara/Senado + voto nominal agregado + autoria/relatoria
- **Camada 2 (Estatística leve)**: TF-IDF sobre ementas filtradas por C1 + intensidade discursiva normalizada

Ambas consomem o DuckDB unificado (S26) e produzem **vetor de posição binária por parlamentar × tópico** com índice de relevância. Sem ML pesado nem GPU.

Adicionalmente: schema YAML de tópicos (`topicos/_schema.yaml`), validador (`scripts/validar_topicos.py`), e 3 tópicos seed (`aborto.yaml`, `porte_armas.yaml`, `marco_temporal.yaml`).

## 2. Contexto

S26 entregou DuckDB unificado com 5 tabelas. S27 é a primeira sprint que entrega **valor analítico real** (não só infraestrutura).

D11 do plano R2 estabelece classificação em cascata de 4 camadas. C1 + C2 (esta sprint) é o **baseline auditável** -- funciona offline, sem GPU, sem dep externa pesada. C3 (embeddings bge-m3) fica em S28; C4 (LLM opcional) em S34b. **A invariante D11 manda que o sistema entregue resultado útil mesmo com C3+C4 desligados** -- esta sprint cumpre isso.

YAML de tópicos é interface de extensão comunitária (D3): qualquer cidadão pode contribuir um YAML novo via PR.

## 3. Escopo

### 3.1 In-scope

- [ ] **Dependências**: `scikit-learn>=1.4` em runtime, `pyyaml>=6.0` em runtime, `jsonschema>=4.20` em runtime (validar YAML)
- [ ] `uv.lock` regenerado
- [ ] **`topicos/_schema.yaml`** -- JSON Schema validando estrutura do YAML de tópico:
  - Campos obrigatórios: `nome`, `versao`, `descricao_curta`, `keywords`, `regex`
  - Campos opcionais: `mantenedor`, `categorias_oficiais_camara`, `categorias_oficiais_senado`, `proposicoes_seed`, `exclusoes`, `embeddings_seed`, `limiar_similaridade`
  - Schema completo conforme plano R2 seção 3.6
- [ ] **`scripts/validar_topicos.py`** validador (Python puro, stdlib + pyyaml + jsonschema):
  - Lê todos `topicos/*.yaml` (não inclui `_schema.yaml`)
  - Valida cada um contra `_schema.yaml`
  - Verifica regex compila (`re.compile`)
  - Verifica keywords não-vazias
  - Exit 0 se todos OK, exit 1 com erro descritivo
- [ ] **`topicos/aborto.yaml`** seed completo conforme plano R2 §3.6 (12 keywords, 6 regex, 4 categorias oficiais, 5 PLs seed, 2 exclusões)
- [ ] **`topicos/porte_armas.yaml`** seed (10+ keywords, 4+ regex, categorias "Segurança Pública")
- [ ] **`topicos/marco_temporal.yaml`** seed (8+ keywords, 3+ regex, categorias "Direitos Humanos" + "Indígenas")
- [ ] **`topicos/README.md`** com instruções pra contribuir tópicos novos via PR
- [ ] **`src/hemiciclo/etl/topicos.py`** carregador e validador em runtime:
  - `Topico` Pydantic v2 model com mesmos campos do YAML
  - `carregar_topico(path: Path) -> Topico` -- valida, compila regex, retorna model
  - `listar_topicos(dir: Path) -> dict[str, Topico]` -- carrega todos
  - `Topico.casa_keywords(ementa: str) -> bool` -- combina keywords + regex
  - `Topico.casa_categoria_oficial(tema_oficial: str, casa: str) -> bool`
- [ ] **`src/hemiciclo/modelos/__init__.py`** marker
- [ ] **`src/hemiciclo/modelos/classificador_c1.py`** Camada 1 determinística:
  - `proposicoes_relevantes(topico: Topico, conn: duckdb.Connection) -> pl.DataFrame`:
    - SELECT em `proposicoes` aplicando regex/keywords sobre ementa
    - + categoria_oficial match
    - Retorna DataFrame com (id, casa, ementa, score_match)
  - `agregar_voto_por_parlamentar(props_relevantes, conn) -> pl.DataFrame`:
    - JOIN votos × proposições relevantes
    - Calcula `proporcao_sim` por parlamentar
    - Retorna DataFrame com (parlamentar_id, casa, n_votos, proporcao_sim, posicao_agregada)
  - `posicao_agregada` é Enum: `A_FAVOR` (>= 70% SIM), `CONTRA` (<= 30% SIM), `NEUTRO` (entre)
- [ ] **`src/hemiciclo/modelos/classificador_c2.py`** Camada 2 estatística leve:
  - `tfidf_relevancia(props_relevantes: pl.DataFrame) -> pl.DataFrame`:
    - Aplica TfidfVectorizer (sklearn) sobre ementas
    - Retorna DataFrame com (id, casa, score_tfidf)
  - `intensidade_discursiva(parlamentar_id: int, topico: Topico, conn) -> float`:
    - Conta discursos do parlamentar que casam keywords/regex
    - Normaliza por baseline total de discursos do parlamentar
- [ ] **`src/hemiciclo/modelos/classificador.py`** orquestrador:
  - `classificar(topico_yaml: Path, db_path: Path, camadas: list[str]) -> dict`:
    - Chama C1 + C2 conforme `camadas`
    - Persiste resultado em `~/hemiciclo/cache/classificacoes/<topico>_<hash_db>.parquet`
    - Retorna estrutura com top a-favor / top contra / metadata
- [ ] **CLI `hemiciclo classificar`**:
  - `--topico topicos/aborto.yaml`
  - `--db-path ~/hemiciclo/cache/hemiciclo.duckdb` (default)
  - `--camadas regex,votos,tfidf` (default)
  - `--top-n 100` (default)
  - `--output /tmp/classificacao_aborto.json` (opcional)
- [ ] **Pre-commit hook** `validar-topicos` ativado em `.pre-commit-config.yaml` (estava placeholder em S22)
- [ ] **CI workflow** `validar_topicos.py` ativado em `.github/workflows/ci.yml` (S37 deixou placeholder)
- [ ] **Testes unit** em `tests/unit/test_topicos.py` (6 testes):
  - `test_carregar_aborto_valido`
  - `test_yaml_invalido_falha`
  - `test_regex_compila`
  - `test_casa_keywords_match`
  - `test_casa_categoria_oficial_match`
  - `test_listar_topicos_5_seed`
- [ ] **Testes unit** em `tests/unit/test_classificador_c1.py` (5 testes):
  - `test_proposicoes_relevantes_via_regex`
  - `test_proposicoes_relevantes_via_categoria_oficial`
  - `test_exclusoes_filtram_falsos_positivos`
  - `test_agregar_voto_por_parlamentar`
  - `test_posicao_agregada_a_favor_contra_neutro`
- [ ] **Testes unit** em `tests/unit/test_classificador_c2.py` (4 testes):
  - `test_tfidf_relevancia_ordena`
  - `test_tfidf_lista_vazia_nao_falha`
  - `test_intensidade_discursiva_normalizada`
  - `test_random_state_determinismo`
- [ ] **Testes unit** em `tests/unit/test_classificador.py` (3 testes):
  - `test_classificar_camada_1_apenas`
  - `test_classificar_camada_1_e_2`
  - `test_persiste_resultado_em_cache`
- [ ] **Testes unit** em `tests/unit/test_validar_topicos.py` (5 testes):
  - `test_yaml_valido_passa`
  - `test_yaml_sem_keywords_falha`
  - `test_regex_invalida_falha`
  - `test_diretorio_vazio_passa`
  - `test_seed_3_topicos_validos`
- [ ] **Testes integração** em `tests/integracao/test_classificador_e2e.py` (3 testes):
  - `test_classificar_aborto_em_db_seed`
  - `test_workflow_db_init_consolidar_classificar` (ciclo completo)
  - `test_camadas_desligaveis`
- [ ] **Test sentinela** em `test_sentinela.py`:
  - `test_classificar_help` (com COLUMNS=200 lição S24)
- [ ] **`docs/arquitetura/classificacao_multicamada.md`** documentando: cascata C1-C4, schema YAML, função de cada camada, exemplos de output
- [ ] **`CHANGELOG.md`** entrada `[Unreleased]`

### 3.2 Out-of-scope (explícito)

- **Camada 3 (embeddings bge-m3)** -- fica em S28
- **Camada 4 (LLM)** -- fica em S34b
- **Detalhe de proposições via GET /proposicoes/{id}** -- já registrado em S24b
- **Iterar 4 anos da legislatura** -- registrado em S24c
- **Dashboard UI da classificação** -- fica em S31
- **Modelo base PCA/FactorAnalysis** -- fica em S28
- **YAMLs adicionais além dos 3 seed** -- ficam pra contribuição comunitária via PR

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `topicos/_schema.yaml` | JSON Schema dos tópicos |
| `topicos/aborto.yaml` | Seed |
| `topicos/porte_armas.yaml` | Seed |
| `topicos/marco_temporal.yaml` | Seed |
| `topicos/README.md` | Como contribuir |
| `scripts/validar_topicos.py` | Validador YAML (CLI + biblioteca) |
| `src/hemiciclo/etl/topicos.py` | Carregador runtime + Topico Pydantic |
| `src/hemiciclo/modelos/__init__.py` | Marker |
| `src/hemiciclo/modelos/classificador_c1.py` | Camada 1 (determinística) |
| `src/hemiciclo/modelos/classificador_c2.py` | Camada 2 (TF-IDF + intensidade) |
| `src/hemiciclo/modelos/classificador.py` | Orquestrador |
| `tests/unit/test_topicos.py` | 6 testes |
| `tests/unit/test_classificador_c1.py` | 5 testes |
| `tests/unit/test_classificador_c2.py` | 4 testes |
| `tests/unit/test_classificador.py` | 3 testes |
| `tests/unit/test_validar_topicos.py` | 5 testes |
| `tests/integracao/test_classificador_e2e.py` | 3 testes |
| `docs/arquitetura/classificacao_multicamada.md` | Documentação |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `pyproject.toml` | Adiciona scikit-learn, pyyaml, jsonschema |
| `uv.lock` | Regenerado |
| `src/hemiciclo/cli.py` | Subcomando `classificar` |
| `tests/unit/test_sentinela.py` | 1 teste help classificar |
| `.pre-commit-config.yaml` | Hook `validar-topicos` ativado |
| `.github/workflows/ci.yml` | Step `validar_topicos.py` ativado |
| `CHANGELOG.md` | Entrada [Unreleased] |
| `sprints/ORDEM.md` | S27 -> DONE |

## 5. Implementação detalhada

### 5.1 Schema do tópico (referência simplificada)

```yaml
# topicos/aborto.yaml
nome: aborto
versao: 1
mantenedor: comunidade
descricao_curta: "Pauta sobre interrupção da gravidez no ordenamento jurídico brasileiro"
keywords:
  - aborto
  - interrupção da gravidez
  - aborto legal
regex:
  - "(?i)aborto\\s+(?:legal|terap[êe]utico|provocado)"
  - "(?i)interrup[çc][ãa]o\\s+(?:vol[ui]nt[áa]ria|legal)\\s+da\\s+gravidez"
categorias_oficiais_camara:
  - "Direitos Humanos, Minorias e Cidadania"
  - "Saúde"
proposicoes_seed:
  - { sigla: "PL", numero: 1904, ano: 2024, casa: "camara", posicao_implicita: contra }
exclusoes:
  - regex: "(?i)aborto\\s+espont[âa]neo"
limiar_similaridade: 0.62
```

### 5.2 Algoritmo C1 (determinístico)

```python
def proposicoes_relevantes(topico: Topico, conn) -> pl.DataFrame:
    # 1. Match por keywords/regex em ementa
    where_keywords = " OR ".join(f"ementa ILIKE '%{k}%'" for k in topico.keywords)
    where_categorias = (
        " OR ".join(f"tema_oficial = '{c}'" for c in topico.categorias_oficiais_camara + topico.categorias_oficiais_senado)
        if topico.categorias_oficiais_camara or topico.categorias_oficiais_senado
        else "FALSE"
    )
    sql = f"""
        SELECT id, casa, ementa, sigla, numero, ano, tema_oficial
        FROM proposicoes
        WHERE ({where_keywords}) OR ({where_categorias})
    """
    df = conn.execute(sql).pl()
    # 2. Filtrar exclusões via regex Python (DuckDB regex limitado)
    if topico.exclusoes:
        for excl in topico.exclusoes:
            df = df.filter(~pl.col("ementa").str.contains(excl["regex"]))
    return df
```

### 5.3 Algoritmo C1 (agregação de voto)

```python
def agregar_voto_por_parlamentar(props: pl.DataFrame, conn) -> pl.DataFrame:
    ids_props = props["id"].to_list()
    casas = props["casa"].to_list()
    # JOIN votos × proposicoes_relevantes
    sql = """
        SELECT v.parlamentar_id, v.casa,
               COUNT(*) AS n_votos,
               SUM(CASE WHEN v.voto = 'SIM' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS proporcao_sim
        FROM votos v
        JOIN votacoes vt ON vt.id = v.votacao_id AND vt.casa = v.casa
        WHERE vt.id IN (SELECT id FROM proposicoes WHERE id IN ?)
        GROUP BY v.parlamentar_id, v.casa
    """
    # ... agregação + categorização
```

(Schema real exige cuidado: votação está ligada a proposição via campo na tabela `votacoes`. Ajustar conforme schema S26.)

### 5.4 Algoritmo C2 (TF-IDF)

```python
def tfidf_relevancia(props: pl.DataFrame) -> pl.DataFrame:
    from sklearn.feature_extraction.text import TfidfVectorizer
    if len(props) == 0:
        return props.with_columns(pl.lit(0.0).alias("score_tfidf"))
    vectorizer = TfidfVectorizer(max_features=100, stop_words=None)  # PT-BR sem stop words por enquanto
    matrix = vectorizer.fit_transform(props["ementa"].to_list())
    scores = matrix.sum(axis=1).A1
    return props.with_columns(pl.Series("score_tfidf", scores))
```

### 5.5 Passo a passo

1. Confirmar branch `feature/s27-classificador-c1-c2`.
2. Adicionar deps; `uv sync --all-extras`.
3. Criar `topicos/_schema.yaml` (JSON Schema completo).
4. Criar 3 YAMLs seed (aborto, porte_armas, marco_temporal).
5. Criar `topicos/README.md`.
6. Implementar `scripts/validar_topicos.py`.
7. Escrever `tests/unit/test_validar_topicos.py` (5 testes).
8. Implementar `src/hemiciclo/etl/topicos.py` (Topico Pydantic + carregador).
9. Escrever `tests/unit/test_topicos.py` (6 testes).
10. Implementar `src/hemiciclo/modelos/classificador_c1.py`.
11. Escrever `tests/unit/test_classificador_c1.py` (5 testes).
12. Implementar `src/hemiciclo/modelos/classificador_c2.py`.
13. Escrever `tests/unit/test_classificador_c2.py` (4 testes).
14. Implementar `src/hemiciclo/modelos/classificador.py` (orquestrador).
15. Escrever `tests/unit/test_classificador.py` (3 testes).
16. Adicionar subcomando `classificar` em `cli.py`.
17. Adicionar `test_classificar_help` em `test_sentinela.py`.
18. Escrever `tests/integracao/test_classificador_e2e.py` (3 testes).
19. Ativar hook `validar-topicos` em `.pre-commit-config.yaml`.
20. Ativar step `validar_topicos.py` em `.github/workflows/ci.yml`.
21. Escrever `docs/arquitetura/classificacao_multicamada.md`.
22. Atualizar `CHANGELOG.md`.
23. Smoke local: rodar `validar_topicos.py` (passa nos 3 seeds), depois `hemiciclo classificar --topico topicos/aborto.yaml --db-path /tmp/hemi.duckdb` em DB com fixtures S24+S25.
24. `make check` deve passar com cobertura ≥ 90%.
25. Atualizar `sprints/ORDEM.md` mudando S27 para DONE.

## 6. Testes (resumo)

- **5** validar_topicos
- **6** topicos.py (carregador)
- **5** C1 (regex, categoria, exclusões, voto, posição)
- **4** C2 (TF-IDF, intensidade, determinismo)
- **3** orquestrador (camadas individuais, persistência cache)
- **3** integração e2e
- **1** CLI sentinela
- **Total: 27 testes novos** + 175 herdados = 202 testes na suíte total.

## 7. Proof-of-work runtime-real

**Comando local:**

```bash
$ make check
$ python scripts/validar_topicos.py
$ uv run hemiciclo db init --db-path /tmp/hemi27.duckdb
$ uv run hemiciclo coletar camara --legislatura 57 --tipos proposicoes votacoes votos --max-itens 50 --output /tmp/c27
$ uv run hemiciclo db consolidar --parquets /tmp/c27 --db-path /tmp/hemi27.duckdb
$ uv run hemiciclo classificar --topico topicos/aborto.yaml --db-path /tmp/hemi27.duckdb --camadas regex,votos --output /tmp/c1_aborto.json
$ uv run python -c "import json; r = json.load(open('/tmp/c1_aborto.json')); print(f\"props_relevantes: {r['n_props']}, parlamentares: {r['n_parlamentares']}, top_a_favor[0]: {r['top_a_favor'][0] if r['top_a_favor'] else 'vazio'}\")"
```

**Saída esperada:**

```
make check: 202 passed, cobertura ≥ 90%
[validar_topicos] 3 topicos validados em topicos/. Zero erros.
[classificar][aborto] N props_relevantes, M parlamentares classificados
{
  "topico": "aborto",
  "n_props": ...,
  "n_parlamentares": ...,
  "top_a_favor": [...],
  "top_contra": [...]
}
```

**Critério de aceite:**

- [ ] `validar_topicos.py` passa nos 3 YAMLs seed
- [ ] `make check` 202 testes verdes, cobertura ≥ 90%
- [ ] Hook pre-commit `validar-topicos` ativo
- [ ] CI step `validar_topicos.py` ativo (verde)
- [ ] CLI `classificar` produz JSON com top a-favor / top contra
- [ ] C1 sozinha (sem TF-IDF) produz output válido
- [ ] Exclusões filtram falsos positivos (`aborto espontâneo` não casa)
- [ ] Mypy --strict zero erros
- [ ] Ruff zero violações
- [ ] CHANGELOG atualizado
- [ ] CI verde nos 6 jobs do PR

## 8. Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| TF-IDF em PT-BR sem stop words pode dar score ruim | M | M | Testes cobrem ementas reais; sklearn default funciona razoavelmente; tuning fica pra S28+ |
| DuckDB regex tem sintaxe diferente de Python | A | M | Filtrar via Polars após load (não DuckDB regex) |
| YAML com regex inválida quebra hook em runtime | M | A | Validador testa `re.compile` antes de aceitar |
| sklearn 1.4 vs 1.5 mudança em TfidfVectorizer | B | M | Pinning + CI matriz |
| DB de smoke vazio (sem votos coletados) | A | B | Smoke usa proposicoes apenas se votos não há |

## 9. Validação multi-agente

Padrão estabelecido: executor → make check + smoke → reporta; validador → proof-of-work independente + I1-I12 + decisão.

## 10. Próximo passo após DONE

S28 (Modelo base v1: amostragem + bge-m3 + PCA + persistência) -- camada C3.
