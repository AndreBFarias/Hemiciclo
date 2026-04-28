# Pipeline integrado da Sessão de Pesquisa (S30)

> Substitui o `_pipeline_dummy` da S29 e conecta os subsistemas S24 (coleta Câmara), S25 (coleta Senado), S26 (ETL/DuckDB), S27 (classificador C1+C2) e S28 (modelo base C3) em uma execução autocontida na pasta da sessão.

## Diagrama das 5 etapas

```
+--------+   +-----------------+   +-----+   +--------+   +--------+   +-------------+
| valida |-->| coleta C+S      |-->| ETL |-->| C1+C2  |-->| C3     |-->| relatório   |
| 0-5%   |   | 5-30%           |   |30-50|   | 50-65% |   | 65-90% |   | 90-100%     |
+--------+   +-----------------+   +-----+   +--------+   +--------+   +-------------+
                  |                    |          |            |               |
                  v                    v          v            v               v
            sessao_dir/raw/      sessao_dir/    sessao_dir/  sessao_dir/    sessao_dir/
            *.parquet            dados.duckdb  classificacao c3_status     relatorio_state.json
                                               _c1_c2.json   .json         manifesto.json
```

## Limite de coleta (`max_itens`)

Desde a S30.1, o flag `hemiciclo sessao iniciar --max-itens N` propaga `N` como `ParametrosBusca.max_itens`, que por sua vez vira `ParametrosColeta.max_itens` em ambas as casas dentro de `_etapa_coleta`. O efeito é restrito à etapa 1 (coleta):

- `--max-itens 50 --casas camara senado` -> até 50 itens por tipo da Câmara e 50 por tipo do Senado (totalizando até 2N por tipo entre as duas casas).
- Etapas pós-coleta (ETL, C1+C2, C3, grafos, histórico, convertibilidade) processam **toda** a amostra coletada -- sem propagação adicional. Para limitar pós-coleta, abrir sprint nova (precedente: S30.4).
- Default `None` preserva o comportamento de coleta full (universo completo).
- Validação Pydantic `ge=1` em ambos os schemas (`ParametrosBusca` e `ParametrosColeta`): `max_itens=0` é rejeitado; "sem limite" é `None`.

Tempos típicos observados em rede doméstica:

| Modo | Tempo aproximado |
|---|---|
| Full (`max_itens=None`) | 30 a 60 min |
| `--max-itens 50` | 1 a 2 min |
| `--max-itens 30 --casas camara` | < 1 min |

Útil para smoke local, demo de dashboard e iteração rápida da S31.

## Mapeamento etapas -> EstadoSessao

| Etapa | Função | Estado | Progresso |
|---|---|---|---|
| validar | `_etapa_validar` | `COLETANDO` | 2% |
| coleta Câmara | `_etapa_coleta` | `COLETANDO` | 10% |
| coleta Senado | `_etapa_coleta` | `COLETANDO` | 22% |
| ETL | `_etapa_etl` | `ETL` | 35% |
| C1+C2 | `_etapa_classificacao_c1_c2` | `ETL` | 55% |
| C3 (transform) | `_etapa_embeddings_c3` | `EMBEDDINGS` | 70-88% |
| Relatório | `_etapa_relatorio` | `MODELANDO` | 95% |
| Final | `pipeline_real` | `CONCLUIDA` | 100% |

## Tratamento de erro por etapa

`pipeline_real` envolve as 5 etapas em um único `try/except Exception`:

- Qualquer falha em validação, coleta, ETL ou C1+C2 -> `EstadoSessao.ERRO` em `status.json` com mensagem `<TipoExc>: <texto>` e re-raise para o subprocess worker (S29) deixar exit code 1.
- A camada C3 implementa **skip graceful** -- bge-m3 ausente, modelo base não treinado ou base com integridade violada não falham o pipeline. Apenas marcam `c3_status.json` com `skipped=True` e seguem.

Casos cobertos por testes (em `tests/unit/test_pipeline_real.py`):

- `test_falha_api_marca_erro` -- coletor levanta `RuntimeError` -> sessão fica em `ERRO`.
- `test_topico_inexistente_falha_antes_de_coleta` -- YAML ausente bloqueia antes de qualquer rede.
- `test_etapa_embeddings_skipped_se_modelo_ausente` -- bge-m3 não disponível.
- `test_etapa_embeddings_skipped_se_base_nao_treinado` -- modelo base ausente.

## Limitações conhecidas (registradas em `manifesto.json`)

A constante `LIMITACOES_CONHECIDAS = ("S24b", "S24c", "S25.3", "S27.1")` é serializada em todo `manifesto.json` para tornar explícito o que esta versão do pipeline ainda não cobre. Cada item aponta para uma sprint READY documentando o débito:

| ID | Limite |
|---|---|
| S24b | 4 colunas vazias em proposições da Câmara (autor_principal, status, url_inteiro_teor, etc.). |
| S24c | Coletor da Câmara só pega ano inicial da legislatura quando `data_inicio` é `None`. |
| S25.3 | Schema dual da API Senado v7 tratado defensivamente -- ADR ainda pendente. |
| S27.1 | `votacoes.proposicao_id` ainda ausente -- C1 voto retorna agregação vazia mas não falha. |

## Layout final da pasta da sessão

```
~/hemiciclo/sessoes/<id>/
├── params.json                  # ParametrosBusca
├── status.json                  # StatusSessao (atualizado pelo subprocess)
├── pid.lock                     # PID + timestamp
├── raw/                         # parquets crus da coleta
│   ├── proposicoes.parquet
│   ├── votacoes.parquet
│   ├── votos.parquet
│   ├── discursos.parquet
│   ├── deputados.parquet
│   ├── materias.parquet         # Senado
│   ├── senadores.parquet
│   ├── votacoes_senado.parquet
│   ├── votos_senado.parquet
│   └── discursos_senado.parquet
├── dados.duckdb                 # ETL consolidado
├── classificacao_c1_c2.json     # output do classificar()
├── c3_status.json               # marca skipped/ok da camada 3
├── relatorio_state.json         # agregação final pra dashboard (S31)
└── manifesto.json               # SHA256 16-char + limitacoes_conhecidas
```

## Decisões fundamentais

- **Imports lazy por etapa.** Cada etapa faz `from hemiciclo.<sub> import ...` dentro da própria função para preservar boot rápido do CLI (~200ms) e permitir mock cirúrgico em testes via `monkeypatch.setattr("hemiciclo.<sub>.<fn>", mock)`.
- **SHA256 truncado em 16 chars.** Precedente S24/S25 -- confirmado pela sprint S25.1. Faz `manifesto.json` legível por humanos sem perder utilidade de auditoria.
- **`Path.cwd()` como referência de tópicos.** `_resolver_topico("aborto")` busca `<cwd>/topicos/aborto.yaml`. Usuário comum invoca pelo CLI na raiz do repo; testes setam `monkeypatch.chdir(repo_root)`.
- **C3 skip graceful, não fail-graceful.** Sessão CONCLUIDA é melhor que ERRO quando o problema é só "modelo opcional ausente". UI tem como diferenciar via `relatorio.c3.skipped`.

## Smoke local opcional

```bash
# Compat S29 (sem rede, sem modelo base) -- pipeline dummy
uv run hemiciclo sessao iniciar --topico aborto --dummy
sleep 3
uv run hemiciclo sessao listar    # mostra CONCLUIDA

# Pipeline real (depende de rede para coleta; C3 fica SKIPPED se bge-m3 ausente)
uv run hemiciclo sessao iniciar --topico aborto --casas camara
# Pode demorar minutos. Sessão fica CONCLUIDA com manifesto.json populado.
```

## Testes

- `tests/unit/test_pipeline_real.py` -- 15 testes com mocks agressivos dos 5 subsistemas.
- `tests/integracao/test_pipeline_e2e.py` -- 2 testes (in-process com mocks + subprocess via dummy callable).
- `tests/unit/test_sentinela.py` -- 2 sentinelas garantindo flag `--dummy` documentada.

Total novo: **19 testes**. Suite cresce de 302 para 321 testes; cobertura mantida em 90%+.

## Próximas sprints destravadas

- S31 -- dashboard sessão renderiza `relatorio_state.json` + `manifesto.json`.
- S32 -- grafos de coautoria + voto sobre `dados.duckdb`.
- S33 -- histórico de conversão por parlamentar × tópico.
- S34/S34b -- ML + LLM opcional.
- S35 -- exportação completa de sessão (zip + verificação).
