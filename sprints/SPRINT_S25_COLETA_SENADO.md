# Sprint S25 -- Coleta Senado: discursos + votos + cadastro + checkpoint

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-28
**Autor:** @AndreBFarias
**Status:** DONE (2026-04-28)
**Depende de:** S22 (DONE), S24 (DONE)
**Bloqueia:** S26
**Esforço:** M (3-5 dias)
**ADRs vinculados:** ADR-002 (voto nominal espinha dorsal)
**Branch:** feature/s25-coleta-senado

---

## 1. Objetivo

Implementar coleta resiliente da API Senado Federal (`legis.senado.leg.br/dadosabertos`) -- **proposições (matérias), votações nominais, votos individuais, discursos, cadastro de senadores** -- **replicando o padrão estabelecido em S24** (httpx + tenacity + TokenBucket + checkpoint Pydantic + Polars Parquet).

A diferença principal vs S24:
- API do Senado retorna **XML** por default em vários endpoints (negociar `Accept: application/json` quando disponível, fallback XML parsing).
- Endpoints distintos da Câmara (paths diferentes; ver §5.1).
- IDs de senador e código de matéria têm formato diferente.
- Volume menor: 81 senadores (vs 513 deputados), ~3-5k matérias por legislatura, ~2k votações nominais.

S26 (próxima após esta) consolida output S24+S25 em DuckDB.

## 2. Contexto

S24 estabeleceu o padrão. Esta sprint reaproveita:
- `src/hemiciclo/coleta/http.py` (`cliente_http`, `retry_resiliente`) -- inalterado
- `src/hemiciclo/coleta/rate_limit.py` (`TokenBucket`) -- inalterado
- Padrão de `CheckpointCamara` -- replicado como `CheckpointSenado` em arquivo separado
- Padrão Pydantic + escrita atômica de checkpoint -- mesmo de S24
- `ParametrosColeta` em `src/hemiciclo/coleta/__init__.py` -- já existe, basta validar que aceita Senado

A invariante I1 (tudo local) exige URLs apenas do governo brasileiro (`legis.senado.leg.br/dadosabertos/...`). Sem CDN proprietária.

## 3. Escopo

### 3.1 In-scope

- [ ] **Dependências adicionadas** (já presentes via S24): httpx, tenacity, polars, respx
  - **Nova dep:** `lxml>=5.0` em runtime (parse XML do Senado)
- [ ] `uv.lock` regenerado
- [ ] **`src/hemiciclo/coleta/checkpoint.py`** estendido:
  - Nova classe `CheckpointSenado(BaseModel)` análoga a `CheckpointCamara`:
    - `iniciado_em`, `atualizado_em`, `legislaturas`, `tipos`
    - `materias_baixadas: set[int]`
    - `votacoes_baixadas: set[int]` (códigos da votação Senado)
    - `votos_baixados: set[tuple[int, int]]` (votacao_id, senador_id)
    - `discursos_baixados: set[str]` (hash sha256)
    - `senadores_baixados: set[int]`
    - `erros: list[dict]`
  - Função `salvar_checkpoint_senado(cp, path)` e `carregar_checkpoint_senado(path)` análogas
  - Reaproveitar `hash_params(legislaturas, tipos)` já existente
- [ ] **`src/hemiciclo/coleta/senado.py`** módulo principal:
  - `URL_BASE = "https://legis.senado.leg.br/dadosabertos"`
  - Helper `_parse_xml_ou_json(resp, raiz_xml: str) -> dict`
  - `coletar_senadores(legislatura: int) -> list[dict]` -- endpoint `/senador/lista/legislatura/{N}`
  - `coletar_materias(ano: int, max_itens: int | None) -> Iterator[dict]` -- endpoint `/materia/pesquisa/lista` ou `/materia/atualizadas`
  - `coletar_votacoes(ano: int) -> Iterator[dict]` -- endpoint `/plenario/lista/votacao/<ano>`
  - `coletar_votos_de_votacao(votacao_id: int) -> list[dict]` -- endpoint `/plenario/votacao/{N}`
  - `coletar_discursos(senador_codigo: str) -> Iterator[dict]` -- endpoint `/senador/{cod}/discursos`
  - `executar_coleta(params, dir_saida, checkpoint) -> None` orquestrador
  - Cada função respeita rate limiter + checkpoint + retry
- [ ] **Persistência em Parquet via Polars**:
  - `<dir_saida>/materias.parquet` (12 colunas: id, sigla, numero, ano, ementa, tema_oficial, autor_principal, data_apresentacao, status, url_inteiro_teor, casa, hash_conteudo)
  - `<dir_saida>/votacoes_senado.parquet`
  - `<dir_saida>/votos_senado.parquet`
  - `<dir_saida>/discursos_senado.parquet`
  - `<dir_saida>/senadores.parquet`
  - **`hash_conteudo` é SHA256 da ementa** (lição da S24, ACHADO 3 do validador)
- [ ] **CLI `hemiciclo coletar senado`** novo subcomando paralelo a `coletar camara`:
  - `--legislatura 55 56 57`
  - `--tipos materias votacoes votos discursos senadores`
  - `--ano 2024 2025 2026` (alternativa a legislatura, mais granular)
  - `--max-itens 100`
  - `--output /tmp/senado_smoke`
- [ ] **Testes unit** em `tests/unit/test_coleta_senado.py` (8 testes via respx):
  - `test_coletar_senadores_caminho_feliz`
  - `test_coletar_materias_paginacao`
  - `test_coletar_votacoes_intervalo_de_ano`
  - `test_coletar_votos_de_votacao`
  - `test_coletar_discursos_por_senador`
  - `test_503_retry_e_sucesso`
  - `test_404_propaga_erro`
  - `test_max_itens_respeitado`
  - `test_parse_xml_fallback` (resp Content-Type XML)
- [ ] **Testes unit** em `tests/unit/test_coleta_checkpoint_senado.py` (5 testes):
  - `test_serializacao_round_trip_senado`
  - `test_set_de_tuples_serializa_como_lista`
  - `test_carregar_inexistente_retorna_none`
  - `test_property_based_via_hypothesis`
  - `test_cohabita_com_checkpoint_camara` (ambos podem coexistir em `~/hemiciclo/cache/checkpoints/`)
- [ ] **Testes integração** em `tests/integracao/test_coleta_senado_e2e.py` (5 testes mockados):
  - `test_coleta_completa_persiste_parquet`
  - `test_kill_e_retomada_idempotente`
  - `test_xml_payload_parseado_correto`
  - `test_checkpoint_senado_sobrevive_a_kill`
  - `test_orquestrador_processa_5_tipos`
- [ ] **Test sentinela** em `test_sentinela.py`:
  - `test_coletar_senado_help` (com `COLUMNS=200, TERM=dumb, NO_COLOR=1` -- precedente S24 fix CI)
  - `test_coletar_senado_tipo_invalido`
- [ ] **`docs/arquitetura/coleta.md`** estendido com seção "API Senado":
  - Endpoints alvo
  - Diferenças de schema vs Câmara
  - Estratégia de parse XML/JSON
- [ ] **`CHANGELOG.md`** entrada `[Unreleased]` com bullet `feat(coleta): coletor do Senado replicando padrão da Câmara`

### 3.2 Out-of-scope (explícito)

- **DuckDB schema unificado** -- fica em S26
- **Mapeamento tópico→matéria** -- fica em S27
- **Coleta paralela Câmara+Senado** -- fica em S30 (pipeline integrado)
- **Detalhe de cada matéria via GET /materia/{id}** -- mesma limitação observada em S24 (ACHADO 2). Aplicável em sprint análoga (S25b se necessário)
- **Cache HTTP transversal** -- fica em S26
- **Progress bar Rich** -- ausente em S24 também, vira S24d (já READY); não duplicar em S25

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `src/hemiciclo/coleta/senado.py` | Módulo principal de coleta Senado |
| `tests/unit/test_coleta_senado.py` | 9 testes via respx |
| `tests/unit/test_coleta_checkpoint_senado.py` | 5 testes |
| `tests/integracao/test_coleta_senado_e2e.py` | 5 testes integração |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `pyproject.toml` | Adiciona lxml>=5.0 |
| `uv.lock` | Regenerado |
| `src/hemiciclo/coleta/checkpoint.py` | Adiciona `CheckpointSenado` + funções salvar/carregar análogas |
| `src/hemiciclo/coleta/__init__.py` | Garantir que `ParametrosColeta` aceita tipos Senado |
| `src/hemiciclo/cli.py` | Novo subcomando `coletar senado` |
| `tests/unit/test_sentinela.py` | 2 testes do subcomando |
| `docs/arquitetura/coleta.md` | Seção "API Senado" |
| `CHANGELOG.md` | Entrada [Unreleased] |
| `sprints/ORDEM.md` | S25 -> DONE |

## 5. Implementação detalhada

### 5.1 Endpoints alvo (Senado Dados Abertos)

- `GET /senador/lista/legislatura/{leg}` -- cadastro
- `GET /senador/{cod}` -- detalhe + biografia
- `GET /materia/pesquisa/lista?ano={ano}` -- listagem de matérias
- `GET /materia/{cod}` -- detalhe (mesma limitação S24/ACHADO 2)
- `GET /plenario/lista/votacao/{ano}` -- votações nominais
- `GET /plenario/votacao/{cod}` -- detalhe da votação + votos individuais
- `GET /senador/{cod}/discursos?ano={ano}` -- discursos

Default response: XML. Negociar `Accept: application/json` quando suportado (alguns endpoints retornam só XML).

### 5.2 Padrões herdados de S24 (sem reescrever)

- `cliente_http()` de `src/hemiciclo/coleta/http.py`
- `@retry_resiliente` decorator
- `TokenBucket` de `src/hemiciclo/coleta/rate_limit.py`
- Estrutura `CheckpointCamara` (replicar como `CheckpointSenado`)
- Pattern `executar_coleta(params, dir_saida, checkpoint)`
- Persistência via `pl.DataFrame.write_parquet()`
- Schema 12 colunas para matéria/proposição (alinhado com S24)
- `hash_conteudo = SHA256(ementa)` -- aplicar mesmo fix da S24 desde o início
- Smoke real opcional, testes via respx obrigatórios

### 5.3 Diferenças vs S24

- API retorna XML por default; precisa parse via `lxml.etree`.
- IDs são `int` (Senado) ou `str` (Câmara em alguns endpoints).
- Volume menor permite testes e2e mais cobrindo.
- Endpoint de discursos é por senador (vs por sessão na Câmara) -- modelo diferente.

### 5.4 Trecho de referência -- `_parse_xml_ou_json`

```python
def _parse_xml_ou_json(resp: httpx.Response, raiz_xml: str) -> dict[str, Any]:
    """Parseia resposta JSON ou XML (fallback)."""
    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype:
        return resp.json()  # type: ignore[no-any-return]
    from lxml import etree
    raiz = etree.fromstring(resp.content)
    return _xml_para_dict(raiz)
```

### 5.5 Passo a passo

1. Confirmar branch `feature/s25-coleta-senado`.
2. Adicionar `lxml>=5.0` ao pyproject; `uv sync --all-extras`.
3. Estender `coleta/checkpoint.py` com `CheckpointSenado`.
4. Escrever `tests/unit/test_coleta_checkpoint_senado.py` (5 testes).
5. Implementar `coleta/senado.py` com 5 funções de coleta + orquestrador + helper de parse XML/JSON.
6. Escrever `tests/unit/test_coleta_senado.py` (9 testes via respx).
7. Adicionar subcomando `coletar senado` em `cli.py` (paralelo a `coletar camara`).
8. Adicionar `test_coletar_senado_help` e `test_coletar_senado_tipo_invalido` em `test_sentinela.py` com `env={COLUMNS:200,TERM:dumb,NO_COLOR:1}` (lição S24).
9. Escrever `tests/integracao/test_coleta_senado_e2e.py` (5 testes).
10. Estender `docs/arquitetura/coleta.md` com seção API Senado.
11. Atualizar `CHANGELOG.md`.
12. Smoke local opcional: `uv run hemiciclo coletar senado --ano 2024 --tipos materias --max-itens 50 --output /tmp/senado_smoke` (se rede disponível).
13. `make check` deve passar com cobertura ≥ 90% nos arquivos novos.
14. Atualizar `sprints/ORDEM.md` mudando S25 para DONE.

## 6. Testes (resumo)

- **9** senado (caminho feliz, paginação, retry, max_itens, parse XML)
- **5** checkpoint senado (round-trip, hypothesis, coexistência com checkpoint Câmara)
- **5** integração e2e (coleta completa, retomada, XML)
- **2** CLI sentinela
- **Total: 21 testes novos** + 114 herdados = 135 testes na suíte total.

## 7. Proof-of-work runtime-real

**Comando local:**

```bash
$ make check
$ uv run hemiciclo coletar senado --ano 2024 --tipos materias --max-itens 50 --output /tmp/senado_smoke
$ ls /tmp/senado_smoke/materias.parquet
$ uv run python -c "import polars as pl; df = pl.read_parquet('/tmp/senado_smoke/materias.parquet'); print(f'rows: {len(df)}, cols: {len(df.columns)}')"
```

**Saída esperada:**

```
make check: 135 passed, cobertura ≥ 90%
[coleta][senado] 50 materias baixadas em XXs
/tmp/senado_smoke/materias.parquet
rows: 50, cols: 12
```

**Critério de aceite:**

- [ ] `make check` 135 testes verdes, cobertura ≥ 90%
- [ ] Smoke real (se rede ok) baixa 50 matérias em < 60s
- [ ] Parquet de saída com schema 12 colunas (mesmo da Câmara, casa="senado")
- [ ] Checkpoint Senado coexiste com Câmara no mesmo `~/hemiciclo/cache/checkpoints/`
- [ ] respx mocks cobrem 9 cenários (incluindo XML)
- [ ] Cobertura ≥ 90% nos arquivos novos
- [ ] Mypy --strict zero erros
- [ ] Ruff zero violações
- [ ] CI verde nos 6 jobs do PR
- [ ] CHANGELOG.md atualizado

## 8. Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| API do Senado fora do ar | A | M | Testes via respx; smoke opcional |
| Schema XML do Senado mudar entre endpoints | M | M | Helper `_parse_xml_ou_json` defensivo + Pydantic valida payload |
| `lxml` falhar em Windows wheels | B | A | uv sync resolve binários pré-compilados; CI matriz Windows pega cedo |
| Endpoint de discursos paginado diferente da Câmara | A | M | Documentar em `docs/arquitetura/coleta.md`; teste cobre |
| `hash_params` colidir entre coletor Camara e Senado se mesma chave | B | M | Prefixar com `"camara_"` ou `"senado_"` no nome do arquivo de checkpoint |

## 9. Validação multi-agente

**Executor (`executor-sprint`):** Implementa, roda smoke local + proof-of-work, NÃO push, NÃO PR.

**Validador (`validador-sprint`):** Roda proof-of-work independente, verifica I1-I12, smoke real se rede disponível, decide APROVADO / RESSALVAS / REPROVADO.

## 10. Próximo passo após DONE

S26 (cache transversal SHA256 + DuckDB schema + migrations) -- consolida output S24+S25.
