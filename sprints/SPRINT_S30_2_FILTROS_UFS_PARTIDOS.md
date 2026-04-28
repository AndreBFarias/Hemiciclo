# Sprint S30.2 -- Aplicar filtros `params.ufs` e `params.partidos` no `pipeline_real`

**Projeto:** Hemiciclo
**Versão alvo:** v2.1.0 (sprint 7/7 -- última do release)
**Data criação:** 2026-04-28
**Status:** READY
**Depende de:** S29 (DONE), S30 (DONE), S27 (DONE), S26 (DONE)
**Bloqueia:** -- (sprint folha do release v2.1.0)
**Esforço:** P (1-2 dias)
**ADRs vinculados:** ADR-007 (Sessão de Pesquisa), ADR-011 (cascata C1-C4), ADR-012 (schema DuckDB)
**Branch:** feature/s30-2-filtros-ufs-partidos

---

## 1. Objetivo

`ParametrosBusca` (S29, `src/hemiciclo/sessao/modelo.py:119-126`) já declara
campos `ufs: list[str] | None = None` e `partidos: list[str] | None = None`,
e o validador `_ufs_canonicas` (linha 167) impõe pertencimento a
`UFS_BRASIL`. Mas o `pipeline_real` (S30, `src/hemiciclo/sessao/pipeline.py`)
**ignora ambos**: a etapa `_etapa_classificacao_c1_c2` (linhas 238-269)
chama `classificar(...)` sem filtro, agregando todos os 513 deputados +
81 senadores presentes em `parlamentares` da `dados.duckdb` da sessão.

Esta sprint conecta os campos ao pipeline: aplica `WHERE uf IN (...) AND
partido IN (...)` na tabela `parlamentares` (schema v1+,
`src/hemiciclo/etl/schema.py:142-153`) **antes** de C1+C2 chamar
`agregar_voto_por_parlamentar`, restringindo o JOIN aos parlamentares
do recorte.

Caso de uso central: "Como vota a bancada do PT em SP sobre aborto?".
Hoje a sessão classifica 594 parlamentares e produz relatório global.
Com S30.2: classifica ~12 deputados e devolve relatório focado, em
fração do tempo.

## 2. Contexto

S30 entregou pipeline funcional ponta-a-ponta. S30.1 (READY) propaga
`--max-itens` para `ParametrosColeta`. S30.2 fecha a outra metade do
recorte: filtros declarativos por UF e partido. Combinada com S30.1,
um usuário consegue rodar:

```bash
hemiciclo sessao iniciar --topico aborto --uf SP --partido PT --max-itens 100
```

e obter resultado focado em < 90s.

A CLI atual (`src/hemiciclo/cli.py:573-631`) **não tem flags `--uf` /
`--partido`** -- existe `--casas`, `--legislatura`, `--max-itens`,
`--dummy`, mas o construtor `ParametrosBusca(...)` na linha 620 só passa
`topico`, `casas`, `legislaturas`. Esta sprint **adiciona as duas flags**
multi-valor, com parsing repetível (`--uf SP --uf RJ`,
`--partido PT --partido PSOL`).

**Decisão preservada:** filtro acontece **após** o ETL (etapa 2), não
durante a coleta. Justificativa: (a) cache transversal SHA256 do S26
deduplica a coleta global, sessões diferentes compartilham parquets
brutos; (b) filtrar na coleta enviesa amostra quando combinado com
`--max-itens` (lição S30.1); (c) a tabela `parlamentares` só é populada
de forma confiável após o ETL consolidar `deputados.parquet` /
`senadores.parquet` em DuckDB.

**Ortogonalidade `--uf` × `--partido`:**

- `--uf X` apenas: filtra por UF, partidos não restritos
- `--partido P` apenas: filtra por partido, UFs não restritas
- ambos: AND lógico (`WHERE uf IN (...) AND partido IN (...)`)
- nenhum: comportamento atual (sem filtro, todos os parlamentares)

## 3. Escopo

### 3.1 In-scope

- [ ] **`src/hemiciclo/sessao/pipeline.py`** ganha helper novo
  `_montar_clausula_subset_parlamentares(conn, ufs, partidos) -> set[tuple[int, str]] | None`:
  - Aceita `conn: duckdb.DuckDBPyConnection`, `ufs: list[str] | None`,
    `partidos: list[str] | None`.
  - Se ambos forem `None`: retorna `None` (sentinela "sem filtro").
  - Caso contrário: roda `SELECT id, casa FROM parlamentares WHERE ...`
    com placeholders parametrizados (proteção contra injeção via UF
    de origem desconhecida -- defesa em profundidade mesmo com
    validador Pydantic).
  - Cláusula montada com `?` placeholders + `params` list:
    - UFs presentes: `uf IN (?, ?, ?)` (UPPER no validador já garante
      casamento com o que vem da API)
    - Partidos presentes: `UPPER(partido) IN (UPPER(?), UPPER(?), ...)`
      (defensivo: API Câmara devolve `"PT"`, mas Senado historicamente
      mistura caixa)
  - Retorna `set[tuple[int, str]]` com pares `(parlamentar_id, casa)`.
  - Logger `loguru` em INFO: `"[pipeline][filtro] ufs={u} partidos={p}
    -> {n} parlamentares"`.
  - Logger em **WARNING** se `n < 10` -- recorte muito estreito,
    relatório provavelmente terá baixa estatística (pré-condição
    documentada no riscos).
- [ ] **`_etapa_classificacao_c1_c2`** (linhas 238-269) modificada:
  - Antes de chamar `classificar(...)`, abre `duckdb.connect(db_path,
    read_only=True)`, chama o helper acima e fecha a conexão.
  - Passa o resultado adiante via novo parâmetro `parlamentares_subset`
    em `classificar(...)`.
- [ ] **`src/hemiciclo/modelos/classificador.py`** -- função `classificar`
  (linhas 55-166):
  - Adiciona parâmetro `parlamentares_subset: set[tuple[int, str]] | None
    = None` (default `None` = comportamento atual).
  - Repassa para `agregar_voto_por_parlamentar(df_props, conn,
    parlamentares_subset=...)`.
  - Inclui `n_parlamentares_subset` no dict de resultado quando
    `parlamentares_subset is not None`: número de pares aceitos pelo
    filtro (útil para auditoria do dashboard em S31).
- [ ] **`src/hemiciclo/modelos/classificador_c1.py`** -- função
  `agregar_voto_por_parlamentar` (linhas 113-194):
  - Adiciona parâmetro `parlamentares_subset: set[tuple[int, str]] | None
    = None` na assinatura pública.
  - Quando não-`None` e não-vazio: adiciona JOIN extra com tabela temp
    `_parlamentares_subset_tmp (parlamentar_id BIGINT, casa VARCHAR)`,
    populada via `executemany` no mesmo padrão de
    `_props_relevantes_tmp` (linhas 163-168).
  - SQL passa a ter cláusula adicional:
    `JOIN _parlamentares_subset_tmp ps
       ON ps.parlamentar_id = v.parlamentar_id AND ps.casa = v.casa`
  - Quando `parlamentares_subset` é set vazio: retorna `schema_vazio`
    imediatamente (curto-circuito; recorte sem ninguém).
  - DROP da tabela temp em `finally`-equivalente (após o segundo
    `conn.execute("DROP TABLE IF EXISTS _props_relevantes_tmp")`).
- [ ] **CLI -- `src/hemiciclo/cli.py:573-631`** flags novas:
  - `--uf` (alias `-u`): `list[str] = typer.Option([], "--uf", "-u",
    help="UF(s) alvo. Pode ser repetido. Default: todas as 27.")`.
    Aceita lista vazia (= sem filtro).
  - `--partido` (alias `-p`): `list[str] = typer.Option([], "--partido",
    "-p", help="Sigla(s) de partido. Pode ser repetido. Default: todos.")`.
  - No construtor `ParametrosBusca(...)` (linha 620): converte lista
    vazia em `None` (`ufs=ufs if ufs else None`, idem partidos) -- evita
    persistir `[]` que é semanticamente diferente de `None` no Pydantic.
  - Mensagem de erro amigável quando o validador
    `_ufs_canonicas` (`modelo.py:167-177`) rejeita: try/except em volta
    do `ParametrosBusca(...)` com `console.print` em vermelho + `raise
    typer.Exit(2)`.
- [ ] **Persistência no relatório** -- `_agregar_relatorio`
  (`pipeline.py:712-735`) já recebe `params`; adiciona ao dict:
  - `"ufs": list(params.ufs) if params.ufs else None`
  - `"partidos": list(params.partidos) if params.partidos else None`
  - `"n_parlamentares_subset": int | None` (do dict de classificação)

  Justificativa: dashboard (S31) já lê `relatorio_state.json` e pode
  exibir badge "recorte: SP/PT (12 parlamentares)".
- [ ] **Manifesto inalterado** -- `_gerar_manifesto`
  (`pipeline.py:738-765`) já gera SHA256 por arquivo; o
  `relatorio_state.json` enriquecido vai ter hash diferente
  automaticamente.
- [ ] **Testes unit** `tests/unit/test_pipeline_filtros.py` (NOVO,
  6 testes):
  - `test_filtro_ambos_none_retorna_sentinela_sem_filtro` --
    ufs=None, partidos=None -> helper retorna `None`.
  - `test_filtro_uf_apenas_aplica_clausula_uf` -- mock conn,
    ufs=["SP"], partidos=None -> SQL contém `uf IN (?)`, params
    `["SP"]`, retorna set não-`None`.
  - `test_filtro_partido_apenas_uppercase_defensivo` --
    ufs=None, partidos=["pt", "PSOL"] -> SQL aplica `UPPER(partido)`,
    casa "pt" e "PT" no DB.
  - `test_filtro_ambos_combinados_aplica_AND` --
    ufs=["SP", "RJ"], partidos=["PT"] -> set resultante respeita ambos.
  - `test_filtro_resultado_menor_que_10_emite_warning` -- captura
    `loguru` via `caplog`, asserta `WARNING` com substring
    `"recorte muito estreito"`.
  - `test_filtro_set_vazio_propaga_para_classificador` -- helper
    devolve `set()`, `agregar_voto_por_parlamentar` curto-circuita
    para `schema_vazio`.
- [ ] **Testes unit estendidos** em `tests/unit/test_classificador_c1.py`
  (2 testes adicionais):
  - `test_agregar_voto_com_subset_filtra_join` -- DB pequeno com 5
    parlamentares, subset = 2 pares, agregação retorna apenas 2 linhas.
  - `test_agregar_voto_com_subset_vazio_retorna_schema_vazio` --
    subset=set() -> DataFrame vazio com schema correto.
- [ ] **Testes unit CLI** em `tests/unit/test_cli.py` (3 testes
  adicionais; criar arquivo se não existir):
  - `test_sessao_iniciar_com_uf_repetido_passa_para_params` -- usa
    `CliRunner` ou monkeypatch em `SessaoRunner.iniciar`, asserta que
    `params.ufs == ["SP", "RJ"]`.
  - `test_sessao_iniciar_com_partido_repetido_passa_para_params` --
    análogo para `--partido PT --partido PSOL`.
  - `test_sessao_iniciar_uf_invalida_emite_erro_amigavel` -- `--uf XX`
    sai com exit code 2 e mensagem em vermelho contendo `"UF inválida"`.
- [ ] **Sentinelas** em `tests/unit/test_sentinela.py` (2 adicionais):
  - `test_sentinela_pipeline_aplica_filtro_apos_etl` -- grep estático:
    arquivo `pipeline.py` chama `_montar_clausula_subset_parlamentares`
    **dentro** de `_etapa_classificacao_c1_c2` e **não** em
    `_etapa_coleta` ou `_etapa_etl` (anti-débito: confirma decisão
    arquitetural).
  - `test_sentinela_classificar_aceita_subset_kwarg` -- `inspect.signature`
    da função `classificar` contém parâmetro `parlamentares_subset`.
- [ ] **`CHANGELOG.md`** entrada `[Unreleased]` -> sob `### Added`:
  - "Filtros `--uf` e `--partido` em `hemiciclo sessao iniciar` (S30.2)"
  - "ParametrosBusca.ufs e ParametrosBusca.partidos passam a ser
    aplicados no pipeline_real (S30.2)"
- [ ] **`sprints/ORDEM.md`**: linha S30.2 -> `DONE (2026-04-NN, v2.1.0)`.

### 3.2 Out-of-scope (explícito)

- **Filtro por gênero, idade, escolaridade** -- depende de cadastro
  complementar (ADR-futuro).
- **Filtro por mandato (vereador / deputado / senador)** -- já há
  separação por casa via `params.casas`; mandato municipal não está no
  escopo do Hemiciclo.
- **Persistir filtros aplicados em `manifesto.json`** -- `manifesto`
  é hash de artefato, não metadado de busca. Filtro já vai em
  `relatorio_state.json`.
- **Filtro por bloco partidário** ("oposição", "centrão") -- requer
  taxonomia política não trivial; sprint própria no futuro.
- **Validação que o partido informado existe na DB** -- validador
  Pydantic só checa UF; partido aceita qualquer string. Se filtrar
  por partido inexistente o pipeline simplesmente devolve set vazio
  e WARNING (item testado em
  `test_filtro_resultado_menor_que_10_emite_warning`).
- **Smoke real ponta-a-ponta** com download bge-m3 -- proibido em CI;
  smoke local opcional do executor (seção 7).

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `tests/unit/test_pipeline_filtros.py` | 6 testes do helper + integração leve |
| `tests/unit/test_cli.py` | 3 testes de parsing das flags `--uf`/`--partido` (criar se ausente) |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `src/hemiciclo/sessao/pipeline.py` | Helper novo + chamada em `_etapa_classificacao_c1_c2` + enriquecimento de `_agregar_relatorio` |
| `src/hemiciclo/modelos/classificador.py` | Param `parlamentares_subset` em `classificar` + repasse |
| `src/hemiciclo/modelos/classificador_c1.py` | Param `parlamentares_subset` em `agregar_voto_por_parlamentar` + JOIN extra |
| `src/hemiciclo/cli.py` | Flags `--uf`/`--partido` em `sessao iniciar` + try/except amigável |
| `tests/unit/test_classificador_c1.py` | 2 testes adicionais |
| `tests/unit/test_sentinela.py` | 2 sentinelas adicionais |
| `CHANGELOG.md` | Entrada `[Unreleased]` |
| `sprints/ORDEM.md` | S30.2 -> DONE |

## 5. Implementação detalhada

### 5.1 Helper `_montar_clausula_subset_parlamentares`

```python
# src/hemiciclo/sessao/pipeline.py

def _montar_clausula_subset_parlamentares(
    conn: duckdb.DuckDBPyConnection,
    ufs: list[str] | None,
    partidos: list[str] | None,
) -> set[tuple[int, str]] | None:
    """Resolve `(ufs, partidos)` em set de pares (parlamentar_id, casa).

    Retorno:
        - ``None`` -- ambos `ufs` e `partidos` são `None`. Sentinela
          "sem filtro": classificador roda com todos os parlamentares.
        - ``set[tuple[int, str]]`` -- subset filtrado, possivelmente
          vazio. Set vazio é sinal de "filtro casou ninguém" e o
          classificador deve curto-circuitar.

    Loga em INFO o tamanho do recorte; em WARNING quando ``n < 10``.
    """
    if ufs is None and partidos is None:
        return None

    where: list[str] = []
    params: list[str] = []
    if ufs:
        where.append("uf IN (" + ", ".join(["?"] * len(ufs)) + ")")
        params.extend(ufs)
    if partidos:
        where.append(
            "UPPER(partido) IN (" + ", ".join(["UPPER(?)"] * len(partidos)) + ")"
        )
        params.extend(partidos)

    sql = "SELECT id, casa FROM parlamentares"
    if where:
        sql += " WHERE " + " AND ".join(where)

    rows = conn.execute(sql, params).fetchall()
    subset: set[tuple[int, str]] = {(int(r[0]), str(r[1])) for r in rows}
    n = len(subset)
    logger.info(
        "[pipeline][filtro] ufs={u} partidos={p} -> {n} parlamentares",
        u=ufs, p=partidos, n=n,
    )
    if 0 < n < 10:
        logger.warning(
            "[pipeline][filtro] recorte muito estreito: apenas {n} "
            "parlamentares -- estatísticas podem ser ruidosas",
            n=n,
        )
    elif n == 0:
        logger.warning(
            "[pipeline][filtro] recorte vazio -- nenhum parlamentar "
            "casou ufs={u} AND partidos={p}",
            u=ufs, p=partidos,
        )
    return subset
```

### 5.2 Integração na etapa C1+C2

```python
# src/hemiciclo/sessao/pipeline.py -- _etapa_classificacao_c1_c2

def _etapa_classificacao_c1_c2(
    params: ParametrosBusca,
    sessao_dir: Path,
    updater: StatusUpdater,
    log: Any,
) -> None:
    updater.atualizar(EstadoSessao.ETL, 55.0, "classificar_c1_c2", "Classificando C1+C2")
    import duckdb  # noqa: PLC0415 -- lazy
    from hemiciclo.modelos.classificador import classificar  # noqa: PLC0415

    db_path = sessao_dir / "dados.duckdb"
    topico_path = _resolver_topico(params.topico)
    cfg = Configuracao()

    # Filtro pos-ETL: resolve subset antes de chamar classificar.
    subset: set[tuple[int, str]] | None = None
    if params.ufs is not None or params.partidos is not None:
        conn = duckdb.connect(str(db_path), read_only=True)
        try:
            subset = _montar_clausula_subset_parlamentares(
                conn, params.ufs, params.partidos
            )
        finally:
            conn.close()

    resultado = classificar(
        topico_yaml=topico_path,
        db_path=db_path,
        camadas=["regex", "votos", "tfidf"],
        top_n=100,
        home=cfg.home,
        parlamentares_subset=subset,
    )
    destino = sessao_dir / "classificacao_c1_c2.json"
    destino.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    log.info(
        "[pipeline][c1c2] n_props={p} n_parlamentares={n} subset={s}",
        p=resultado.get("n_props", 0),
        n=resultado.get("n_parlamentares", 0),
        s=resultado.get("n_parlamentares_subset"),
    )
```

### 5.3 Repasse em `classificar`

```python
# src/hemiciclo/modelos/classificador.py

def classificar(
    topico_yaml: Path,
    db_path: Path,
    camadas: list[str] | None = None,
    top_n: int = 100,
    home: Path | None = None,
    parlamentares_subset: set[tuple[int, str]] | None = None,
) -> dict[str, Any]:
    # ... (corpo existente até) ...

    # Agregação de voto.
    if "votos" in camadas_efetivas and len(df_props) > 0:
        df_agg = agregar_voto_por_parlamentar(
            df_props, conn, parlamentares_subset=parlamentares_subset
        )
    else:
        df_agg = pl.DataFrame()

    # ... resto ...

    resultado: dict[str, Any] = {
        "topico": topico.nome,
        # ... campos existentes ...
        "n_parlamentares_subset": (
            len(parlamentares_subset)
            if parlamentares_subset is not None
            else None
        ),
    }
```

### 5.4 JOIN extra em `agregar_voto_por_parlamentar`

```python
# src/hemiciclo/modelos/classificador_c1.py

def agregar_voto_por_parlamentar(
    props_relevantes: pl.DataFrame,
    conn: duckdb.DuckDBPyConnection,
    parlamentares_subset: set[tuple[int, str]] | None = None,
) -> pl.DataFrame:
    schema_vazio = pl.DataFrame(
        schema={
            "parlamentar_id": pl.Int64,
            "casa": pl.Utf8,
            "n_votos": pl.Int64,
            "proporcao_sim": pl.Float64,
            "posicao_agregada": pl.Utf8,
        }
    )

    if len(props_relevantes) == 0:
        return schema_vazio

    # Curto-circuito: subset explicitamente vazio = ninguém no recorte.
    if parlamentares_subset is not None and len(parlamentares_subset) == 0:
        return schema_vazio

    aplicar_migrations(conn)
    # ... cria _props_relevantes_tmp como hoje ...

    join_subset_clause = ""
    if parlamentares_subset is not None:
        conn.execute("DROP TABLE IF EXISTS _parlamentares_subset_tmp")
        conn.execute(
            "CREATE TEMP TABLE _parlamentares_subset_tmp "
            "(parlamentar_id BIGINT, casa VARCHAR)"
        )
        conn.executemany(
            "INSERT INTO _parlamentares_subset_tmp VALUES (?, ?)",
            list(parlamentares_subset),
        )
        join_subset_clause = (
            "JOIN _parlamentares_subset_tmp ps "
            "ON ps.parlamentar_id = v.parlamentar_id AND ps.casa = v.casa"
        )

    sql = f"""
        SELECT
            v.parlamentar_id,
            v.casa,
            COUNT(*) AS n_votos,
            CAST(SUM(CASE WHEN UPPER(v.voto) = 'SIM' THEN 1 ELSE 0 END) AS DOUBLE)
                / NULLIF(COUNT(*), 0) AS proporcao_sim
        FROM votos v
        JOIN votacoes vt ON vt.id = v.votacao_id AND vt.casa = v.casa
        JOIN _props_relevantes_tmp pr
            ON pr.id = vt.proposicao_id AND pr.casa = vt.casa
        {join_subset_clause}
        GROUP BY v.parlamentar_id, v.casa
    """
    df_agg = conn.execute(sql).pl()
    conn.execute("DROP TABLE IF EXISTS _props_relevantes_tmp")
    if parlamentares_subset is not None:
        conn.execute("DROP TABLE IF EXISTS _parlamentares_subset_tmp")
    # ... resto inalterado ...
```

### 5.5 CLI atualizada

```python
# src/hemiciclo/cli.py -- sessao_iniciar

@sessao_app.command("iniciar")
def sessao_iniciar(
    topico: str = typer.Option(..., "--topico", help="..."),
    casas: list[str] = typer.Option(["camara", "senado"], "--casas", "-c"),
    legislaturas: list[int] = typer.Option([57], "--legislatura", "-l"),
    ufs: list[str] = typer.Option(  # noqa: B008
        [],
        "--uf",
        "-u",
        help="UF(s) alvo. Pode ser repetido. Default: todas as 27.",
    ),
    partidos: list[str] = typer.Option(  # noqa: B008
        [],
        "--partido",
        "-p",
        help="Sigla(s) de partido. Pode ser repetido. Default: todos.",
    ),
    max_itens: int | None = typer.Option(None, "--max-itens"),
    dummy: bool = typer.Option(False, "--dummy"),
) -> None:
    from hemiciclo.sessao import Casa, ParametrosBusca, SessaoRunner

    cfg = Configuracao()
    cfg.garantir_diretorios()
    try:
        casas_enum = [Casa(c) for c in casas]
    except ValueError as exc:
        console.print(f"[red]Casa inválida: {exc}[/red]")
        raise typer.Exit(code=2) from exc

    try:
        params = ParametrosBusca(
            topico=topico,
            casas=casas_enum,
            legislaturas=list(legislaturas),
            ufs=ufs or None,
            partidos=partidos or None,
        )
    except ValueError as exc:
        console.print(f"[red]Parâmetros inválidos: {exc}[/red]")
        raise typer.Exit(code=2) from exc

    runner = SessaoRunner(cfg.home, params)
    callable_path = _PIPELINE_DUMMY_PATH if dummy else _PIPELINE_REAL_PATH
    pid = runner.iniciar(callable_path)
    console.print(
        f"sessao iniciar: sessao={runner.id_sessao} pid={pid} pipeline="
        f"{'dummy' if dummy else 'real'} ufs={ufs or '(todas)'} "
        f"partidos={partidos or '(todos)'}"
    )
```

### 5.6 Passo a passo

1. Confirmar branch `feature/s30-2-filtros-ufs-partidos`.
2. Implementar `_montar_clausula_subset_parlamentares` em `pipeline.py`.
3. Modificar `_etapa_classificacao_c1_c2` para abrir conn read-only,
   chamar helper, fechar conn, passar `subset` para `classificar`.
4. Adicionar param `parlamentares_subset` em
   `classificar` (`classificador.py`) com repasse + `n_parlamentares_subset`
   no dict de resultado.
5. Adicionar param `parlamentares_subset` em
   `agregar_voto_por_parlamentar` (`classificador_c1.py`) com curto-circuito
   + tabela temp + JOIN.
6. Adicionar flags `--uf` e `--partido` em `sessao iniciar` (`cli.py`)
   com try/except amigável.
7. Enriquecer `_agregar_relatorio` com `ufs`, `partidos`,
   `n_parlamentares_subset`.
8. Escrever `tests/unit/test_pipeline_filtros.py` (6 testes).
9. Estender `tests/unit/test_classificador_c1.py` (2 testes).
10. Criar/estender `tests/unit/test_cli.py` (3 testes).
11. Adicionar 2 sentinelas em `tests/unit/test_sentinela.py`.
12. Atualizar `CHANGELOG.md` `[Unreleased] -- ### Added`.
13. Atualizar `sprints/ORDEM.md` linha S30.2 -> DONE.
14. `make check` -- todos verdes, cobertura ≥ 90% nos arquivos novos.
15. Smoke local opcional (seção 7) -- com sessão real, validar
    `parlamentares: <= 30`.
16. Commit Conventional Commits: `feat(s30-2): aplica filtros ufs/partidos
    no pipeline_real`.
17. PR: descrição linka para esta sprint + cita aritmética da seção 6.

## 6. Aritmética esperada

Não há meta de "linhas máximas" nesta sprint -- os arquivos modificados
são todos < 800L.

**Aritmética de teste:**

- Testes herdados (S30 entregou 314, S30 + S31 + S32 + S33 + S34 + S35
  estão DONE): leitura de baseline antes de editar via
  `uv run pytest --collect-only -q | tail -5`. Esperado ≥ 470 testes
  (estado pré-S30.2).
- Testes adicionados nesta sprint:
  - `test_pipeline_filtros.py`: 6 novos
  - `test_classificador_c1.py`: 2 novos
  - `test_cli.py`: 3 novos
  - `test_sentinela.py`: 2 novos
  - **Total: 13 testes novos.**
- Cobertura alvo nos arquivos novos/modificados: ≥ 90% (I9 do BRIEF).

**Aritmética do recorte (smoke real):**

- Universo total: 513 deputados (Câmara) + 81 senadores (Senado) = 594.
- Recorte SP: ~70 deputados na Câmara em legislatura 57 (proporcional
  ao colégio eleitoral) + 3 senadores = ~73.
- Recorte SP + PT: estimativa ~10-14 deputados + 0-1 senador = **<= 15
  parlamentares**.
- Esperado em `relatorio_state.json` após smoke: `n_parlamentares <= 30`,
  `n_parlamentares_subset <= 15`.
- Validação grosseira (não estrita -- pode variar com legislatura ativa).

## 7. Proof-of-work runtime-real

### 7.1 Comandos canônicos do BRIEF (sempre verdes)

```bash
$ make check
# Esperado: ruff/mypy zero, 470+ testes, cobertura >= 90%

$ uv run pytest tests/unit/test_pipeline_filtros.py -v
# 6 testes verdes

$ uv run pytest tests/unit/test_classificador_c1.py tests/unit/test_cli.py \
    tests/unit/test_sentinela.py -v
# 7 testes novos verdes (entre os existentes)

$ uv run hemiciclo sessao iniciar --help
# Esperado: opções --uf/-u e --partido/-p documentadas
```

### 7.2 Smoke local opcional (com rede)

```bash
$ uv run hemiciclo sessao iniciar \
    --topico aborto \
    --casas camara \
    --legislatura 57 \
    --uf SP \
    --partido PT \
    --max-itens 100  # combinando S30.1 quando disponível
# Saída esperada: "sessao iniciar: sessao=<uuid> pid=<N> pipeline=real
#                  ufs=['SP'] partidos=['PT']"

$ sleep 60
$ SESSAO_ID=$(uv run hemiciclo sessao listar --formato json 2>/dev/null \
              | jq -r '.[0].id' || ls -t ~/hemiciclo/sessoes | head -1)

$ uv run python -c "
import json, os
p = os.path.expanduser(f'~/hemiciclo/sessoes/{os.environ[\"SESSAO_ID\"]}/relatorio_state.json')
r = json.load(open(p))
total = len(r['top_a_favor']) + len(r['top_contra'])
print(f'parlamentares no relatório: {total}')
print(f'subset declarado: {r.get(\"n_parlamentares_subset\")}')
print(f'ufs={r.get(\"ufs\")} partidos={r.get(\"partidos\")}')
"
# Esperado:
# parlamentares no relatório: <= 30
# subset declarado: <= 15
# ufs=['SP'] partidos=['PT']
```

Tempo total esperado: < 90s (cache S26 + filtro elimina 95% das
agregações de voto).

### 7.3 Hipótese verificada (lição 4 do CLAUDE.md)

Identificadores citados nesta spec **confirmados via grep antes da
redação**:

- `ParametrosBusca.ufs` / `partidos` -- `src/hemiciclo/sessao/modelo.py:119,123`
- `_etapa_classificacao_c1_c2` -- `src/hemiciclo/sessao/pipeline.py:238`
- `agregar_voto_por_parlamentar` -- `src/hemiciclo/modelos/classificador_c1.py:113`
- `classificar` (5 args atuais) -- `src/hemiciclo/modelos/classificador.py:55`
- Tabela `parlamentares` (id, casa, nome, partido, uf, ...) -- `src/hemiciclo/etl/schema.py:142-153`
- `_props_relevantes_tmp` (precedente do padrão TEMP TABLE) -- `classificador_c1.py:163-168`
- CLI `sessao iniciar` -- `src/hemiciclo/cli.py:573-631`
- `UFS_BRASIL` + validador `_ufs_canonicas` -- `modelo.py:20-48,167`

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Partido pode mudar entre legislaturas (deputado migra do PT para PCdoB) | Documentar no docstring de `_montar_clausula_subset_parlamentares`: "filtro usa partido REGISTRADO no momento da coleta da tabela `parlamentares`". Auditoria via `cadastro_partido_data` é sprint futura. |
| Lista vazia após filtro quebra pipeline | `agregar_voto_por_parlamentar` curto-circuita para `schema_vazio`; `_agregar_relatorio` produz `top_a_favor=[]` e `top_contra=[]`; sessão termina CONCLUIDA com `n_parlamentares_subset=0` + WARNING no log. **Não há ERRO**. Teste `test_filtro_set_vazio_propaga_para_classificador` cobre. |
| Combinação com S30.1 (`--max-itens`) enviesando amostra | Filtro de UF/partido acontece **após** ETL, então independe do ranqueamento de `--max-itens` da coleta. Documentar ordem em `pipeline_integrado.md` (out-of-scope desta sprint, ficar pra S30.x se aparecer demanda). |
| Validador Pydantic não checa partido (apenas UF) | Aceitável: lista canônica de partidos brasileiros muda por legislatura (fusões, novos registros TSE). Filtro silencioso para partido inexistente -> set vazio + WARNING. |
| SQL injection via `--uf` (string da CLI direto no SQL) | Defesa em profundidade: validador Pydantic já restringe a 27 strings; helper usa `?` placeholders parametrizados além disso. |
| Tabela `parlamentares` vazia (S24/S25 não populou) | `helper` retorna `set()` (subset vazio); pipeline curto-circuita; WARNING claro. Não falha. |
| `read_only=True` na conn auxiliar conflita com migrations já aplicadas no DB principal | Conn auxiliar só faz `SELECT`. Não roda `aplicar_migrations`. Se schema antigo (sem coluna `partido`), DuckDB devolve erro -> capturar e logar `ERROR` claro: "tabela parlamentares sem coluna partido -- recolete via ETL". Add em `try/except duckdb.BinderException`. |

## 9. Validação multi-agente

Padrão. Validador atenção a:

- **Hipótese verificada**: confirmar que assinaturas tocadas
  (`agregar_voto_por_parlamentar`, `classificar`) batem com o repo
  pré-merge -- nenhuma reescrita acidental de outras camadas.
- **Filtro NÃO está em `_etapa_coleta` nem em `_etapa_etl`** -- decisão
  arquitetural confirmada por sentinela `test_sentinela_pipeline_aplica_filtro_apos_etl`.
- **`relatorio_state.json` ganhou 3 campos novos** (`ufs`, `partidos`,
  `n_parlamentares_subset`) sem renomear ou remover existentes
  (compat S31).
- **Acentuação periférica PT-BR** em todos os arquivos modificados
  (BRIEF I2): rodar `rg "[áéíóúâêôãõàç]" --files-with-matches` no diff
  e auditar.
- **Sem `print()`** (BRIEF I4) e **sem `# TODO` solto** (BRIEF I5) nos
  diffs.
- **`mypy --strict` zero** (BRIEF I7) -- atenção a tipo de
  `parlamentares_subset` (`set[tuple[int, str]] | None`) não vazar `Any`.

## 10. Próximo passo após DONE

S30.2 é a última sprint planejada para v2.1.0. Após DONE:

1. Tag `v2.1.0` em main.
2. Release notes consolidando S23.1 + S27.1 + S30.1 + S30.2 + (sprints
   incorporadas em S38).
3. Demo gif curto: "sessao iniciar --uf SP --partido PT --topico aborto"
   mostrando relatório focado.
4. Avaliar promover S29.1, S29.2, S27.2, S25.1, S25.3 para uma sprint
   guarda-chuva v2.2.0 ("higienização da família coleta+sessão") OU
   pivotar para S34b (camada 4 LLM, primeiro release com IA opt-in).
