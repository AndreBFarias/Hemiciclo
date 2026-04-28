# Sprint S24b -- Enriquecer proposições da Câmara via `GET /proposicoes/{id}`

**Projeto:** Hemiciclo
**Versão alvo:** v2.1.0 (sprint 4/7 da janela 2.1.x)
**Data criação:** 2026-04-28
**Autor:** @AndreBFarias
**Status:** READY
**Depende de:** S24 (DONE), S26 (DONE)
**Bloqueia:** -- (melhoria de recall que destrava S27 a operar com dados completos no real)
**Esforço:** M (3-4 dias)
**ADRs vinculados:** ADR-002 (voto nominal espinha dorsal), ADR-016 (uv lock determinístico), ADR-012 (DuckDB+Parquet)
**Branch:** `feature/s24b-proposicoes-detalhe`

---

## 1. Objetivo

Enriquecer cada proposição já coletada pela S24 (`GET /proposicoes`) com uma chamada extra a `GET /proposicoes/{id}` que devolve o **payload completo**, permitindo preencher 4 colunas que ficam **vazias na produção** porque o endpoint listagem retorna apenas campos resumidos:

1. `tema_oficial` -- categorização oficial da Câmara (essencial para classificador C1, S27).
2. `autor_principal` -- assinatura primária da proposição (exibido no dashboard, S31).
3. `status` -- situação atual (`descricaoSituacao` do `statusProposicao`).
4. `url_inteiro_teor` -- link para o PDF/documento oficial (assinatura completa no dashboard).

A S24 já tem normalização preparada para esses campos em `_normalizar_proposicao` (camara.py:395-410): hoje todos retornam string vazia porque o payload bruto da listagem **não inclui** `temaOficial`, `autorPrincipal`, `statusProposicao` nem `urlInteiroTeor`. O endpoint detalhe retorna todos.

Sem este enriquecimento:

- Recall de C1 (categoria oficial) é zero -- toda classificação cai pra C2 (regex) ou C3 (embeddings), que são mais ruidosos.
- Dashboard mostra autoria como "" (vazio).
- Status "Em tramitação" vs "Arquivada" vs "Sancionada" indistinguível -- impossibilita filtro temporal.
- Link pro inteiro teor inexistente -- usuário não consegue auditar.

## 2. Contexto

A API da Câmara segue padrão REST típico: `GET /proposicoes` paginado devolve `{id, siglaTipo, numero, ano, ementa, dataApresentacao}` por item -- **6 campos resumidos**. Para os outros 6+ campos é necessária chamada individual a `GET /proposicoes/{id}` que devolve `dados` aninhado com:

```json
{
  "dados": {
    "id": 12345,
    "uri": "https://...",
    "siglaTipo": "PL",
    "numero": 100,
    "ano": 2023,
    "ementa": "...",
    "ementaDetalhada": "...",
    "keywords": "...",
    "dataApresentacao": "2023-02-01T15:00",
    "uriOrgaoNumerador": "...",
    "statusProposicao": {
      "dataHora": "2026-04-15T10:00",
      "sequencia": 42,
      "siglaOrgao": "PLEN",
      "descricaoTramitacao": "Aprovação",
      "descricaoSituacao": "Aprovada na Câmara",
      "despacho": "..."
    },
    "urlInteiroTeor": "https://www.camara.leg.br/proposicoesWeb/...",
    "uriAutores": "...",
    "temaOficial": "Política Econômica"
  }
}
```

Para `autor_principal`, o detalhe traz `uriAutores` mas **não o nome direto** -- requer mais um GET a `uriAutores`. Decisão (5.4): nesta sprint, consumir `uriAutores` quando presente e fallback para string vazia quando autor não puder ser resolvido em ≤ 1 chamada extra. Sprint futura S24g pode otimizar via batch.

### 2.1 Quanto custa?

Coleta plena legislatura 57 (~50k proposições) com 1 chamada extra cada = **50k requisições adicionais**. A 10 req/s = 5000s ≈ **83 min**. Aceitável: roda em background, ~50% mais lento que a coleta original mas ainda dentro de uma sessão de pesquisa única. Mitigação extra: cache transversal SHA256 (S26) reaproveita entre sessões.

### 2.2 Por que não embutir em S24?

S24 já está DONE, fundida em main, padrão de coleta estabelecido e replicado por S25. Reabrir S24 violaria o protocolo "DONE é DONE" e desestabilizaria o módulo. Anti-débito (BRIEF §Anti-débito) prevê **sprint nova com ID próprio** (`S24b`), exatamente este caso.

## 3. Escopo

### 3.1 In-scope

- [ ] **Função nova** `enriquecer_proposicao(prop_id: int, bucket: TokenBucket | None = None, cli: httpx.Client | None = None) -> dict[str, Any]` em `src/hemiciclo/coleta/camara.py`:
  - GET `{URL_BASE}/proposicoes/{prop_id}` via `_baixar_pagina` (já existente, S24).
  - Normaliza payload retornado em dict com **exatamente 4 campos** (mais `id` e `casa` para JOIN):
    - `id: int`
    - `casa: str = "camara"`
    - `tema_oficial: str | None`
    - `autor_principal: str | None`
    - `status: str | None`
    - `url_inteiro_teor: str | None`
  - Defaults seguros: `None` (não string vazia) quando campo ausente -- precedente lição S27.1 (NULL é semanticamente correto, "" quebra heurísticas de filtro).
  - Aplica rate limiter via `bucket.aguardar()`.
  - Aplica retry resiliente via `@retry_resiliente` (já existente).
  - Dentro do try, captura `httpx.HTTPStatusError` 404: retorna dict com 4 campos = `None` e log WARNING (proposição existe na listagem mas detalhe sumiu -- raro mas possível).

- [ ] **Função nova** `_resolver_autor_principal(uri_autores: str, bucket, cli) -> str | None` em `src/hemiciclo/coleta/camara.py` (privada):
  - GET `uri_autores` (URL absoluta vinda do detalhe).
  - Extrai primeiro autor da lista `dados[0]["nome"]`.
  - Retorna `None` em qualquer falha -- não bloqueia enriquecimento.
  - Cache em memória dentro da execução (`functools.lru_cache` desabilitado por causa de `httpx.Client` não-hashable; usar dict manual `_autores_resolvidos: dict[str, str | None]` no orquestrador).

- [ ] **Persistência: parquet separado** `<dir_saida>/proposicoes_detalhe.parquet`:
  - Decisão (5.3): **não** mergear no `proposicoes.parquet`; manter separado.
  - Schema dedicado `SCHEMA_PROPOSICAO_DETALHE`:
    ```python
    {
        "id": pl.Int64(),
        "casa": pl.Utf8(),
        "tema_oficial": pl.Utf8(),  # nullable
        "autor_principal": pl.Utf8(),  # nullable
        "status": pl.Utf8(),  # nullable
        "url_inteiro_teor": pl.Utf8(),  # nullable
        "enriquecido_em": pl.Utf8(),  # ISO 8601 datetime
    }
    ```
  - Polars escreve nulls nativos (`None` -> `null` no Parquet) -- compatível com DuckDB `IS NOT NULL` em downstream.

- [ ] **Cache transversal SHA256** (precedente S26):
  - Após resolver detalhe + autor, salvar payload **bruto** (JSON serializado) em `<home>/cache/proposicoes/camara-<id>.json`.
  - Função nova `salvar_cache_detalhe_proposicao(payload: dict, home: Path, casa: str, prop_id: int) -> None` em `src/hemiciclo/etl/cache.py`:
    - Path canônico: `home / "cache" / "proposicoes" / f"{casa}-{prop_id}.json"`.
    - Escrita atômica via `tempfile.NamedTemporaryFile` + `Path.replace` (mesmo padrão de `salvar_cache`).
  - Função nova `carregar_cache_detalhe_proposicao(home: Path, casa: str, prop_id: int) -> dict | None`:
    - Retorna `None` se ausente.
    - Antes de chamar API, `enriquecer_proposicao` consulta cache e retorna direto se hit.
  - **Justificativa do .json** (não .parquet): payload é dict aninhado pequeno (<5KB), Parquet não traz vantagem; JSON é debugável e portável entre sessões.

- [ ] **Checkpoint estendido**:
  - Em `src/hemiciclo/coleta/checkpoint.py`, classe `CheckpointCamara`: adicionar campo:
    ```python
    proposicoes_enriquecidas: set[int] = Field(default_factory=set)
    ```
  - Atualizar `_normaliza_para_json`: incluir `dados["proposicoes_enriquecidas"] = sorted(cp.proposicoes_enriquecidas)`.
  - **Compatibilidade retroativa**: `carregar_checkpoint` aceita JSON sem o campo (Pydantic default_factory cobre); checkpoint antigo carrega com `set()` vazio e enriquecimento começa do zero -- correto.
  - Atualizar `total_baixado()` somando `len(self.proposicoes_enriquecidas)`.

- [ ] **CLI: nova flag** `--enriquecer-proposicoes` / `--no-enriquecer-proposicoes` em `hemiciclo coletar camara`:
  - Default: `True` (enriquecer por padrão; UX-first conforme D10).
  - Em `src/hemiciclo/cli.py:coletar_camara`, adicionar `typer.Option`:
    ```python
    enriquecer_proposicoes: bool = typer.Option(
        True,
        "--enriquecer-proposicoes/--no-enriquecer-proposicoes",
        help="Após coleta listagem, busca detalhe via GET /proposicoes/{id} para preencher tema_oficial, autor_principal, status e url_inteiro_teor.",
    ),
    ```
  - Propagar via `ParametrosColeta.enriquecer_proposicoes: bool = True` (campo novo no Pydantic em `coleta/__init__.py`).
  - Default `True` aplicado quando `"proposicoes" in tipos`. Se `proposicoes` não está nos tipos, flag é ignorada (log DEBUG).

- [ ] **Pipeline orquestrador** `executar_coleta` em `src/hemiciclo/coleta/camara.py`:
  - Após laço de `coletar_proposicoes` (atual linhas 561-588), **se** `params.enriquecer_proposicoes and "proposicoes" in params.tipos`:
    - Itera `checkpoint.proposicoes_baixadas - checkpoint.proposicoes_enriquecidas` (apenas ainda não enriquecidas).
    - Para cada `prop_id`, chama `enriquecer_proposicao(prop_id, bucket=bucket, cli=cli)`.
    - Coleta resultados em `registros_detalhe: list[dict]`.
    - Marca `checkpoint.proposicoes_enriquecidas.add(prop_id)`.
    - Incrementa `contador_req` e chama `_talvez_salvar()`.
    - Ao fim, escreve `_escrever_parquet(registros_detalhe, SCHEMA_PROPOSICAO_DETALHE, params.dir_saida / "proposicoes_detalhe.parquet")`.
  - Erros individuais (404, timeout pós-retry) **não** abortam: registra em `checkpoint.erros` e segue.
  - Log final por legislatura: `"[coleta][camara] {n} proposicoes enriquecidas em {t:.1f}s ({e} erros)"`.

- [ ] **ETL/consolidador** `src/hemiciclo/etl/consolidador.py`:
  - Função nova `_inserir_proposicoes_detalhe(conn, parquet) -> int`:
    - `UPDATE proposicoes` join lateral em `read_parquet(<detalhe>)` para preencher os 4 campos quando `casa = 'camara' AND id = <det.id>`.
    - SQL:
      ```sql
      UPDATE proposicoes p
      SET tema_oficial    = COALESCE(d.tema_oficial,    p.tema_oficial),
          autor_principal = COALESCE(d.autor_principal, p.autor_principal),
          status          = COALESCE(d.status,          p.status),
          url_inteiro_teor = COALESCE(d.url_inteiro_teor, p.url_inteiro_teor)
      FROM (SELECT * FROM read_parquet(?)) d
      WHERE p.casa = 'camara' AND p.id = d.id;
      ```
    - **`COALESCE`** preserva valor existente se detalhe vier `NULL` (segurança).
    - Retorna `conn.changes` (linhas afetadas).
  - Em `consolidar_parquets_em_duckdb`: detectar `proposicoes_detalhe.parquet`, chamar `_inserir_proposicoes_detalhe` **depois** de `_inserir_proposicoes_camara` (ordem importa: precisa da row já inserida).
  - Mapeamento exato:
    ```python
    "proposicoes_detalhe.parquet": _inserir_proposicoes_detalhe,
    ```

- [ ] **Testes unit (8+)** em `tests/unit/test_coleta_camara_detalhe.py`:
  1. `test_enriquecer_proposicao_caminho_feliz` -- respx mock do `/proposicoes/12345` com payload completo, valida 4 campos preenchidos.
  2. `test_enriquecer_proposicao_404_retorna_nones` -- mock 404, valida 4 campos = None + sem raise.
  3. `test_enriquecer_proposicao_503_retry_e_sucesso` -- mock 503 + 200, valida retry funcionou.
  4. `test_enriquecer_proposicao_campos_ausentes_no_payload` -- mock payload com só `id`/`ementa`, valida 4 campos = None (não "").
  5. `test_resolver_autor_principal_caminho_feliz` -- mock `/proposicoes/{id}/autores`, valida primeiro nome.
  6. `test_resolver_autor_principal_lista_vazia` -- mock `dados: []`, valida None.
  7. `test_cache_detalhe_round_trip` -- salva e carrega payload via `salvar_cache_detalhe_proposicao` / `carregar_cache_detalhe_proposicao`, valida igualdade.
  8. `test_enriquecer_consulta_cache_antes_de_api` -- popular cache, mockar API com erro, validar que enriquecer **não** chama API e retorna do cache.
  9. `test_pipeline_marca_proposicoes_enriquecidas_no_checkpoint` -- e2e mockado curto: 3 proposições, executar_coleta com flag True, validar `len(cp.proposicoes_enriquecidas) == 3`.
  10. `test_retomada_idempotente_pula_ja_enriquecidas` -- pré-popular `cp.proposicoes_enriquecidas = {1, 2}`, mockar API com erro pra qualquer chamada, validar que apenas a proposição 3 é tentada.
  11. `test_cli_flag_enriquecer_default_true` -- typer CliRunner sem flag, valida que params.enriquecer_proposicoes is True.
  12. `test_cli_flag_no_enriquecer` -- typer CliRunner com `--no-enriquecer-proposicoes`, valida False.

- [ ] **Teste integração** em `tests/integracao/test_coleta_camara_enriquecimento_e2e.py` (1 teste):
  - `test_pipeline_full_listagem_mais_detalhe_persiste_parquet`: 5 proposições mockadas listagem + 5 detalhes mockados; executa pipeline completo; valida que `proposicoes.parquet` tem 5 linhas e `proposicoes_detalhe.parquet` tem 5 linhas com os 4 campos preenchidos.

- [ ] **Atualização de teste consolidador** `tests/unit/test_etl_consolidador.py`:
  - Novo teste `test_inserir_proposicoes_detalhe_atualiza_4_colunas`:
    - Insere proposicao listagem com 4 campos vazios.
    - Roda `_inserir_proposicoes_detalhe`.
    - SELECT confirma que tema_oficial, autor_principal, status, url_inteiro_teor ficaram NOT NULL.

- [ ] **CHANGELOG.md**: entrada `[Unreleased]` com bullet:
  - `feat(coleta): enriquecimento de proposições da Câmara via GET /proposicoes/{id} preenche tema_oficial, autor_principal, status e url_inteiro_teor (S24b)`

- [ ] **`docs/arquitetura/coleta.md`**: nova seção `### Enriquecimento de proposições (S24b)` documentando:
  - Por que duas chamadas (listagem resumida vs detalhe completo).
  - Path do cache.
  - Flag CLI.
  - Custo estimado (~50k req extras por legislatura).

- [ ] **`sprints/ORDEM.md`**: marcar S24b como DONE com data ao fim da sprint.

### 3.2 Out-of-scope (explícito)

- **Senado análogo** -- API do Senado já entrega payload completo na listagem; análise se for necessário fica em S25.x se virar gargalo (já registrado em ORDEM.md).
- **Re-enriquecer proposições antigas em massa** (já em produção do usuário) -- script CLI separado `hemiciclo coletar camara reenriquecer` fica para sprint nova S24h se demanda surgir; aqui só enriquece o que está sendo coletado.
- **Modelar autoria via grafo** -- S32 já cuida (coautoria parlamentar). Aqui é apenas o nome do autor principal.
- **Otimização batch** (várias proposições em uma chamada) -- API da Câmara não suporta; sprint futura se aparecer endpoint bulk.
- **Asyncio para paralelizar enriquecimento** -- mantém padrão sequencial S24. Otimização fica em sprint dedicada com benchmark prévio.

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `tests/unit/test_coleta_camara_detalhe.py` | 12 testes unit do enriquecimento + CLI flag |
| `tests/integracao/test_coleta_camara_enriquecimento_e2e.py` | 1 teste e2e mockado pipeline completo |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `src/hemiciclo/coleta/camara.py` | Funções `enriquecer_proposicao`, `_resolver_autor_principal`, `SCHEMA_PROPOSICAO_DETALHE`, ramo no `executar_coleta` |
| `src/hemiciclo/coleta/checkpoint.py` | Campo `proposicoes_enriquecidas: set[int]` em `CheckpointCamara` + serializer |
| `src/hemiciclo/coleta/__init__.py` | Campo `enriquecer_proposicoes: bool = True` em `ParametrosColeta` |
| `src/hemiciclo/etl/cache.py` | Funções `salvar_cache_detalhe_proposicao`, `carregar_cache_detalhe_proposicao` |
| `src/hemiciclo/etl/consolidador.py` | Função `_inserir_proposicoes_detalhe` + registro no mapeamento |
| `src/hemiciclo/cli.py` | Flag `--enriquecer-proposicoes/--no-enriquecer-proposicoes` em `coletar_camara` |
| `tests/unit/test_etl_consolidador.py` | Novo teste `test_inserir_proposicoes_detalhe_atualiza_4_colunas` |
| `docs/arquitetura/coleta.md` | Seção nova "Enriquecimento de proposições (S24b)" |
| `CHANGELOG.md` | Entrada `[Unreleased]` |
| `sprints/ORDEM.md` | S24b -> DONE |

## 5. Implementação detalhada

### 5.1 Passo a passo

1. Criar branch `feature/s24b-proposicoes-detalhe` a partir de `main` atualizado.
2. Estender `CheckpointCamara` com `proposicoes_enriquecidas: set[int]`. Atualizar `_normaliza_para_json` e `total_baixado`. Rodar `tests/unit/test_coleta_checkpoint.py` -- todos devem continuar verdes (default_factory cobre testes antigos).
3. Estender `ParametrosColeta` em `coleta/__init__.py` com `enriquecer_proposicoes: bool = True`.
4. Adicionar `SCHEMA_PROPOSICAO_DETALHE` em `coleta/camara.py` (próximo aos outros schemas, ~linha 88).
5. Implementar `enriquecer_proposicao` em `coleta/camara.py` (após `coletar_cadastro_deputados`, ~linha 393).
6. Implementar `_resolver_autor_principal` em `coleta/camara.py` (privada, próxima à anterior).
7. Implementar `salvar_cache_detalhe_proposicao` e `carregar_cache_detalhe_proposicao` em `etl/cache.py`.
8. Plugar consulta a cache no início de `enriquecer_proposicao` (cache hit retorna direto, sem API).
9. Estender `executar_coleta`: após o ramo `if "proposicoes" in params.tipos:` (linha ~588), adicionar bloco de enriquecimento condicional a `params.enriquecer_proposicoes`. Iterar `proposicoes_baixadas - proposicoes_enriquecidas`, chamar `enriquecer_proposicao`, persistir parquet detalhe.
10. Estender CLI `coletar_camara` em `cli.py` com a flag. Propagar para `ParametrosColeta`.
11. Estender `consolidador.py`: implementar `_inserir_proposicoes_detalhe`, registrar mapeamento, chamar **depois** de `_inserir_proposicoes_camara`.
12. Escrever `tests/unit/test_coleta_camara_detalhe.py` com os 12 testes especificados.
13. Escrever `tests/integracao/test_coleta_camara_enriquecimento_e2e.py`.
14. Adicionar teste novo a `tests/unit/test_etl_consolidador.py`.
15. Atualizar `docs/arquitetura/coleta.md` (seção nova).
16. Atualizar `CHANGELOG.md` com bullet `[Unreleased]`.
17. Rodar localmente:
    - `uv run ruff check src tests` -- zero violações
    - `uv run ruff format --check src tests`
    - `uv run mypy --strict src` -- zero erros
    - `uv run pytest tests/unit -v --cov=src/hemiciclo --cov-report=term-missing` -- cobertura ≥ 90% nos arquivos novos/tocados
    - `uv run pytest tests/integracao -v`
18. Smoke real (rede saudável): seção 7 abaixo.
19. Atualizar `sprints/ORDEM.md`: S24b -> DONE.
20. Commit Conventional Commits: `feat(coleta): enriquecer proposicoes Camara via /proposicoes/{id}` (ADR-017).

### 5.2 Decisões técnicas registradas

#### 5.2.1 Defaults `None` em vez de `""`

**Lição S27.1** (registrada em camara.py:425-426): `0` como sentinela em `proposicao_id` quebrou JOIN do classificador C1 porque é BIGINT válido. Análogo aqui: `""` em `tema_oficial` passa em filtro `IS NOT NULL` mas em qualquer `LIKE '%econom%'` retorna falso, gerando recall falsamente baixo nas métricas. **`NULL` é a verdade semântica de "campo desconhecido"** -- usar `None` no Python que Polars converte em null no Parquet, e DuckDB representa como NULL.

#### 5.2.2 Parquet separado vs merge

**Decisão: separado.** Argumentos:

- **Idempotência granular**: re-rodar enriquecimento sem reescrever listagem é trivial.
- **Reversibilidade**: deletar `proposicoes_detalhe.parquet` desfaz enriquecimento sem perder listagem.
- **Compatibilidade retroativa**: parquets gerados pré-S24b continuam carregáveis sem nenhuma mudança.
- **Schema evolution**: futuro adicionar 5ª coluna não exige rescrever parquet listagem.

Custo: consolidador precisa de UPDATE em vez de INSERT (já abordado em 3.1).

#### 5.2.3 Cache em JSON (não Parquet)

Payload de detalhe é dict aninhado pequeno (~3-5KB). Parquet adiciona overhead de schema/metadata sem ganho. JSON é grep-able, debugável, portável. Mantém consistência com `cache/checkpoints/*.json` (já estabelecido S24).

#### 5.2.4 Autor principal em chamada extra opcional

`/proposicoes/{id}` retorna `uriAutores` mas não o nome. Resolver requer `GET <uriAutores>` extra. Nesta sprint:

- Resolver opcionalmente: se `uri_autores` presente no detalhe, fazer 1 chamada extra; se falhar, `autor_principal = None`.
- **Não** quebrar pipeline se autor falhar.
- Cache de autores em memória dentro da execução (`dict[str, str | None]` no orquestrador) -- evita rebuscar quando vários PLs do mesmo autor aparecem.
- Custo total: ~2x chamadas vs S24 sozinha (~100k req em legislatura cheia). Aceitável.

#### 5.2.5 Compatibilidade do consolidador

`_inserir_proposicoes_detalhe` usa `UPDATE ... FROM ... WHERE` (sintaxe DuckDB ≥ 0.9 suportada). Validar com `uv run python -c "import duckdb; print(duckdb.__version__)"` se ≥ 0.9. Caso versão antiga, fallback para `MERGE` ou loop Python (improvável -- pyproject já exige duckdb ≥ 1.0).

#### 5.2.6 Rate limiting compartilhado

`enriquecer_proposicao` recebe `bucket` opcional. No orquestrador, **mesmo bucket** usado em `coletar_proposicoes` é passado adiante -- garante que rate limit global respeita 10 req/s mesmo com listagem + detalhe + autor concorrendo.

### 5.3 Trecho de referência -- `enriquecer_proposicao`

```python
def enriquecer_proposicao(
    prop_id: int,
    home: Path | None = None,
    bucket: TokenBucket | None = None,
    cli: httpx.Client | None = None,
    autores_resolvidos: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Busca detalhe completo de uma proposicao da Camara.

    Faz GET /proposicoes/{id}, normaliza payload e devolve dict com 4
    campos preenchidos (mais id e casa para JOIN). Defaults None quando
    campo ausente -- nunca string vazia.

    Estrategia:

    1. Consulta cache local em ``<home>/cache/proposicoes/camara-{id}.json``.
    2. Cache miss: GET API com retry resiliente.
    3. Resolve autor principal via uriAutores (chamada extra opcional).
    4. Persiste payload bruto em cache para reuso entre sessoes.
    5. Retorna dict normalizado (4 campos + id + casa + enriquecido_em).

    Returns:
        Dict com chaves: id, casa, tema_oficial, autor_principal, status,
        url_inteiro_teor, enriquecido_em.
    """
    from datetime import UTC, datetime
    from hemiciclo.etl.cache import (
        carregar_cache_detalhe_proposicao,
        salvar_cache_detalhe_proposicao,
    )

    if bucket is None:
        bucket = TokenBucket()

    fechar_cli = cli is None
    if cli is None:
        cli = cliente_http()

    if autores_resolvidos is None:
        autores_resolvidos = {}

    try:
        payload: dict[str, Any] | None = None
        if home is not None:
            payload = carregar_cache_detalhe_proposicao(home, "camara", prop_id)

        if payload is None:
            url = f"{URL_BASE}/proposicoes/{prop_id}"
            try:
                bucket.aguardar()
                corpo, _ = _baixar_pagina(cli, url)
                payload = corpo.get("dados") or {}
                if home is not None:
                    salvar_cache_detalhe_proposicao(payload, home, "camara", prop_id)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    logger.warning("Detalhe ausente para proposicao {id} (404)", id=prop_id)
                    payload = {}
                else:
                    raise

        # Resolve autor principal (chamada extra opcional).
        autor: str | None = None
        uri_autores = payload.get("uriAutores")
        if uri_autores:
            if uri_autores in autores_resolvidos:
                autor = autores_resolvidos[uri_autores]
            else:
                autor = _resolver_autor_principal(uri_autores, bucket=bucket, cli=cli)
                autores_resolvidos[uri_autores] = autor

        return {
            "id": prop_id,
            "casa": "camara",
            "tema_oficial": payload.get("temaOficial") or None,
            "autor_principal": autor,
            "status": (
                (payload.get("statusProposicao") or {}).get("descricaoSituacao")
                or None
            ),
            "url_inteiro_teor": payload.get("urlInteiroTeor") or None,
            "enriquecido_em": datetime.now(UTC).isoformat(),
        }
    finally:
        if fechar_cli:
            cli.close()
```

### 5.4 Trecho de referência -- `_resolver_autor_principal`

```python
def _resolver_autor_principal(
    uri_autores: str,
    bucket: TokenBucket,
    cli: httpx.Client,
) -> str | None:
    """Resolve nome do primeiro autor de uma proposicao.

    Returns:
        Nome do primeiro autor, ou ``None`` em qualquer falha.
    """
    try:
        bucket.aguardar()
        corpo, _ = _baixar_pagina(cli, uri_autores)
        autores = corpo.get("dados") or []
        if not autores:
            return None
        primeiro = autores[0]
        nome = primeiro.get("nome")
        return str(nome) if nome else None
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
        logger.warning("Falha ao resolver autor de {uri}: {e}", uri=uri_autores, e=exc)
        return None
```

### 5.5 Trecho de referência -- bloco no `executar_coleta`

```python
# Após o bloco "proposicoes" existente (~ linha 588), antes de "deputados":
if "proposicoes" in params.tipos and params.enriquecer_proposicoes:
    inicio_enr = time.monotonic()
    pendentes = checkpoint.proposicoes_baixadas - checkpoint.proposicoes_enriquecidas
    registros_det: list[dict[str, Any]] = []
    autores_resolvidos: dict[str, str | None] = {}
    erros_enr = 0
    for prop_id in sorted(pendentes):
        try:
            det = enriquecer_proposicao(
                prop_id,
                home=home,
                bucket=bucket,
                cli=cli,
                autores_resolvidos=autores_resolvidos,
            )
            registros_det.append(det)
            checkpoint.proposicoes_enriquecidas.add(prop_id)
            contador_req += 1
            _talvez_salvar()
        except (httpx.HTTPError, ValueError) as exc:
            erros_enr += 1
            checkpoint.erros.append({
                "url": f"{URL_BASE}/proposicoes/{prop_id}",
                "codigo": getattr(getattr(exc, "response", None), "status_code", None),
                "mensagem": str(exc),
                "timestamp": datetime.now(UTC).isoformat(),
            })
    qtd_det = _escrever_parquet(
        registros_det,
        SCHEMA_PROPOSICAO_DETALHE,
        params.dir_saida / "proposicoes_detalhe.parquet",
    )
    duracao_enr = time.monotonic() - inicio_enr
    log.info(
        "[coleta][camara] {n} proposicoes enriquecidas em {t:.1f}s ({e} erros)",
        n=qtd_det,
        t=duracao_enr,
        e=erros_enr,
    )
    _talvez_salvar(forcar=True)
```

### 5.6 Trecho de referência -- `_inserir_proposicoes_detalhe`

```python
def _inserir_proposicoes_detalhe(conn: duckdb.DuckDBPyConnection, parquet: Path) -> int:
    """Atualiza 4 colunas em ``proposicoes`` a partir do parquet de detalhe.

    Usa ``COALESCE`` para preservar valores existentes quando o detalhe
    vem ``NULL`` (seguranca anti-regressao).

    Returns:
        Numero de linhas afetadas pelo UPDATE.
    """
    antes_row = conn.execute(
        "SELECT COUNT(*) FROM proposicoes WHERE tema_oficial IS NOT NULL"
    ).fetchone()
    antes = int(antes_row[0]) if antes_row else 0

    conn.execute(
        """
        UPDATE proposicoes
        SET tema_oficial    = COALESCE(d.tema_oficial,    proposicoes.tema_oficial),
            autor_principal = COALESCE(d.autor_principal, proposicoes.autor_principal),
            status          = COALESCE(d.status,          proposicoes.status),
            url_inteiro_teor = COALESCE(d.url_inteiro_teor, proposicoes.url_inteiro_teor)
        FROM (SELECT * FROM read_parquet(?)) d
        WHERE proposicoes.casa = 'camara' AND proposicoes.id = d.id;
        """,
        [str(parquet)],
    )

    depois_row = conn.execute(
        "SELECT COUNT(*) FROM proposicoes WHERE tema_oficial IS NOT NULL"
    ).fetchone()
    depois = int(depois_row[0]) if depois_row else 0
    return depois - antes
```

## 6. Aritmética numérica

Esta sprint **não** tem meta de redução de linhas (não é refatoração). Linhas adicionadas estimadas:

| Arquivo | Linhas adicionadas estimadas |
|---|---|
| `src/hemiciclo/coleta/camara.py` | ~120 (2 funções novas + bloco no orquestrador + schema) |
| `src/hemiciclo/coleta/checkpoint.py` | ~5 (campo + linhas no serializer + total_baixado) |
| `src/hemiciclo/coleta/__init__.py` | ~2 (campo) |
| `src/hemiciclo/etl/cache.py` | ~50 (2 funções) |
| `src/hemiciclo/etl/consolidador.py` | ~30 (1 função) |
| `src/hemiciclo/cli.py` | ~5 (flag) |
| Testes (3 arquivos) | ~350 (12 + 1 + 1 testes) |
| Docs | ~40 (seção em coleta.md + entrada CHANGELOG + linha ORDEM) |
| **Total estimado** | **~600 linhas** |

Critério: nenhum arquivo deve ultrapassar 800 linhas após a mudança. `coleta/camara.py` está hoje em 693L; passa para ~813L. **Atenção: ultrapassa 800L** -- se executor confirmar (`wc -l`), abrir sub-sprint de extração `S24b-r` extraindo `_normalizar_*` para `coleta/normalizar.py` antes de mergear. Verificar com:

```bash
wc -l src/hemiciclo/coleta/camara.py  # antes
# implementar
wc -l src/hemiciclo/coleta/camara.py  # depois
# se > 800: extrair normalizadores para arquivo novo
```

## 7. Proof-of-work runtime-real

### 7.1 Comandos canônicos do BRIEF

```bash
# Bootstrap idempotente
uv sync --all-extras

# Lint + types
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy --strict src

# Testes
uv run pytest tests/unit/test_coleta_camara_detalhe.py -v
uv run pytest tests/integracao/test_coleta_camara_enriquecimento_e2e.py -v
uv run pytest tests/unit -v --cov=src/hemiciclo/coleta/camara --cov=src/hemiciclo/etl/cache --cov=src/hemiciclo/etl/consolidador --cov-report=term-missing

# Smoke CLI (rede saudável)
uv run hemiciclo coletar camara \
    --legislatura 57 \
    --tipos proposicoes \
    --max-itens 20 \
    --enriquecer-proposicoes \
    --output /tmp/s24b_smoke

ls /tmp/s24b_smoke/
# Esperado: proposicoes.parquet  proposicoes_detalhe.parquet

uv run python -c "
import polars as pl
det = pl.read_parquet('/tmp/s24b_smoke/proposicoes_detalhe.parquet')
print(f'rows: {len(det)}')
print(f'cols: {det.columns}')
print(f'tema_oficial nao-nulo: {det[\"tema_oficial\"].is_not_null().sum()}')
print(f'autor_principal nao-nulo: {det[\"autor_principal\"].is_not_null().sum()}')
print(f'status nao-nulo: {det[\"status\"].is_not_null().sum()}')
print(f'url_inteiro_teor nao-nulo: {det[\"url_inteiro_teor\"].is_not_null().sum()}')
"

# Smoke ETL: consolidar e validar
uv run hemiciclo db consolidar --dir-parquets /tmp/s24b_smoke

uv run python -c "
import duckdb
from pathlib import Path
home = Path.home() / 'hemiciclo'
db = home / 'cache' / 'hemiciclo.duckdb'
c = duckdb.connect(str(db), read_only=True)
total = c.execute(\"SELECT COUNT(*) FROM proposicoes WHERE casa='camara'\").fetchone()[0]
com_tema = c.execute(\"SELECT COUNT(*) FROM proposicoes WHERE casa='camara' AND tema_oficial IS NOT NULL\").fetchone()[0]
print(f'Total proposicoes Camara no DB: {total}')
print(f'Com tema_oficial: {com_tema}')
print(f'Recall: {100*com_tema/total:.1f}%')
"
```

### 7.2 Saída esperada

```
$ ls /tmp/s24b_smoke/
proposicoes.parquet  proposicoes_detalhe.parquet

$ uv run python -c "..."
rows: 20
cols: ['id', 'casa', 'tema_oficial', 'autor_principal', 'status', 'url_inteiro_teor', 'enriquecido_em']
tema_oficial nao-nulo: >= 18
autor_principal nao-nulo: >= 16
status nao-nulo: >= 19
url_inteiro_teor nao-nulo: >= 18

$ uv run python -c "..."
Total proposicoes Camara no DB: 20
Com tema_oficial: >= 18
Recall: >= 90.0%
```

**Critério de aceite numérico:** `tema_oficial IS NOT NULL` em ≥ **90% das proposições** (tolerância para 1-2 falhas de rede em smoke de 20).

### 7.3 Teste de retomada idempotente

```bash
# Executa 50% e mata.
uv run hemiciclo coletar camara -l 57 -t proposicoes --max-itens 30 --output /tmp/s24b_resume &
PID=$!
sleep 5
kill -9 $PID

# Conta enriquecidos no checkpoint após primeiro run.
uv run python -c "
import json
from pathlib import Path
ck = list(Path.home().glob('hemiciclo/cache/checkpoints/camara_*.json'))[0]
d = json.loads(ck.read_text())
print(f'Apos kill: enriquecidas = {len(d[\"proposicoes_enriquecidas\"])}')
"

# Relança -- deve completar APENAS o que falta.
time uv run hemiciclo coletar camara -l 57 -t proposicoes --max-itens 30 --output /tmp/s24b_resume

# Conta enriquecidos final.
uv run python -c "
import json
from pathlib import Path
ck = list(Path.home().glob('hemiciclo/cache/checkpoints/camara_*.json'))[0]
d = json.loads(ck.read_text())
print(f'Final: enriquecidas = {len(d[\"proposicoes_enriquecidas\"])}')
"
```

Esperado: segunda execução completa em < 50% do tempo da primeira (cache + checkpoint pulam o que já foi feito).

### 7.4 Critério de aceite (checklist)

- [ ] `enriquecer_proposicao` retorna dict com 7 chaves (incluindo `enriquecido_em` ISO 8601).
- [ ] Defaults `None` (não `""`) quando campo ausente no payload.
- [ ] 404 em detalhe não interrompe pipeline -- registra em `checkpoint.erros` e segue.
- [ ] 503 em detalhe dispara retry resiliente (5 tentativas, exponencial).
- [ ] `proposicoes_detalhe.parquet` escrito com schema de 7 colunas.
- [ ] Cache `<home>/cache/proposicoes/camara-{id}.json` populado.
- [ ] Cache hit pula chamada à API (testado em mock).
- [ ] Checkpoint `proposicoes_enriquecidas` cresce a cada item enriquecido.
- [ ] Retomada após `kill -9` salta items já enriquecidos.
- [ ] CLI flag `--enriquecer-proposicoes` default `True`.
- [ ] CLI flag `--no-enriquecer-proposicoes` desliga enriquecimento (parquet de detalhe não é gerado).
- [ ] Consolidador SQL UPDATE preenche 4 colunas no DuckDB sem sobrescrever valores existentes (COALESCE).
- [ ] Smoke real: ≥ 90% das 20 proposições têm `tema_oficial IS NOT NULL`.
- [ ] Cobertura ≥ 90% nos arquivos novos/tocados.
- [ ] `uv run mypy --strict src` zero erros.
- [ ] `uv run ruff check src tests` zero violações.
- [ ] CHANGELOG.md `[Unreleased]` com bullet S24b.
- [ ] `wc -l src/hemiciclo/coleta/camara.py` ≤ 800 (ou sub-sprint de extração registrada).
- [ ] Acentuação periférica varrida em todos arquivos modificados (PT-BR correto).

## 8. Riscos e mitigações

| # | Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|---|
| R1 | API throttling: 50k req extras estouram limite não-documentado | M | A | TokenBucket compartilhado em 10 req/s; retry exponencial; usuário pode reduzir via env `HEMICICLO_RATE_LIMIT=5` |
| R2 | Payload `/proposicoes/{id}` tem campo opcional ausente em algumas proposições antigas | A | M | Defaults `None` em todos os 4 campos; testes 4 e 6 cobrem cenário |
| R3 | `uriAutores` retorna 404 (proposição sem autor cadastrado) | B | B | `_resolver_autor_principal` captura erro, retorna None, log WARNING |
| R4 | Custo total dobra tempo de coleta (10k → 20k req) | A | M | Aceitável: legitimamente faz coleta 2x mais lenta; documentado em coleta.md; flag `--no-enriquecer-proposicoes` permite skip |
| R5 | Cache local cresce indefinidamente (~50k arquivos JSON na legislatura cheia) | M | B | Filesystem moderno suporta; documentar em coleta.md; sprint futura S24i pode adicionar `hemiciclo cache limpar` |
| R6 | `coleta/camara.py` ultrapassa 800 linhas | A | M | Aritmética seção 6 calcula 813L estimado; sub-sprint S24b-r de extração já prevista; verificação `wc -l` obrigatória |
| R7 | Consolidador UPDATE colide com migração futura S26.x | B | A | UPDATE é idempotente (COALESCE), funciona após qualquer migration que mantenha colunas vivas; documentado em coleta.md |
| R8 | `set[int]` em checkpoint não desserializa de checkpoint antigo (sem o campo novo) | M | M | Pydantic `default_factory=set` cobre; testar explicitamente em `test_checkpoint_compatibilidade_retroativa` (adicionar a `test_coleta_checkpoint.py`) |
| R9 | Smoke offline: rede no momento do PR pode estar fora | M | B | Smoke é proof-of-work mas testes unit/integração via respx cobrem 100% do caminho lógico |

## 9. Validação multi-agente

### 9.1 Executor (`executor-sprint`)

1. Lê `VALIDATOR_BRIEF.md`.
2. Lê este spec inteiro.
3. Roda `wc -l src/hemiciclo/coleta/camara.py` antes de tudo. Confirma baseline.
4. Implementa 20 passos da seção 5.1.
5. Após implementação, roda `wc -l` de novo. Se > 800: NÃO commitar; abrir sub-sprint S24b-r e parar.
6. Roda proof-of-work seção 7. Reporta saída literal.
7. Acentuação periférica varrida nos arquivos modificados.
8. NÃO push, NÃO PR -- orquestrador integra.

### 9.2 Validador (`validador-sprint`)

1. Lê BRIEF + spec.
2. Roda proof-of-work independentemente (smoke real se rede disponível; mock-only senão).
3. Verifica I1-I12 do BRIEF, **com atenção especial a**:
   - I1 (URL_BASE inalterado, ainda governo BR)
   - I3 (sem random_state aqui, não aplica diretamente, mas verificar determinismo do hash de cache)
   - I6 (Pydantic na nova flag)
   - I7 (mypy --strict zero, em particular `dict[str, Any]` minimizado)
4. Roda SQL `SELECT COUNT(*) FROM proposicoes WHERE casa='camara' AND tema_oficial IS NOT NULL` e valida ≥ 90% recall.
5. Verifica retomada após kill -9 simulado.
6. Decide APROVADO / APROVADO_COM_RESSALVAS / REPROVADO.

## 10. Próximo passo após DONE

- Habilita classificador C1 (S27) a operar em recall completo na produção do usuário (tema_oficial preenchido permite filtro direto sem cair pra C2/C3).
- Dashboard (S31) mostra autoria + status + link teor corretamente.
- Análoga para Senado: avaliar se S25 precisa de sprint similar (`S25.x`); por ora, payload do Senado já é completo.
- Sub-sprint potencial `S24b-r` se `wc -l` da camara.py ultrapassar 800.

## 11. Referências

- BRIEF: `/home/andrefarias/Desenvolvimento/Hemiciclo/VALIDATOR_BRIEF.md`
- Plano R2: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md`
- Spec mãe: `sprints/SPRINT_S24_COLETA_CAMARA.md` (DONE)
- Precedente cache: `sprints/SPRINT_S26_CACHE_DUCKDB.md`
- Precedente normalização defensiva: `sprints/SPRINT_S27_1_VOTACOES_PROPOSICAO_ID.md` (lição "nunca usar 0 como sentinela")
- Código tocado: `src/hemiciclo/coleta/camara.py`, `src/hemiciclo/coleta/checkpoint.py`, `src/hemiciclo/etl/consolidador.py`, `src/hemiciclo/etl/cache.py`, `src/hemiciclo/cli.py`
- ADRs: ADR-002 (voto nominal), ADR-012 (DuckDB+Parquet), ADR-016 (uv lock), ADR-017 (Conventional Commits), ADR-019 (ruff/mypy/pytest)
