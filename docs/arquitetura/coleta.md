# Arquitetura da Coleta

> Documenta o subsistema `src/hemiciclo/coleta/` -- entregue na sprint
> S24 (Câmara) e replicado em S25 (Senado).

## Filosofia

A coleta é **resumível, resiliente e respeitosa**. Resumível porque o
checkpoint persistente sobrevive a `kill -9`, queda de internet e
máquina dormindo. Resiliente porque retentativas exponenciais cobrem
falhas transitórias (5xx, timeouts, quedas TCP). Respeitosa porque o
token bucket evita sobrecarregar APIs governamentais públicas.

## APIs alvo

Todas as URLs apontam **exclusivamente** para domínios do governo
brasileiro -- conforme invariante I1 do `VALIDATOR_BRIEF.md`.

### Câmara dos Deputados

| Endpoint | Uso |
|---|---|
| `https://dadosabertos.camara.leg.br/api/v2/proposicoes` | Lista de PLs/PECs/etc por legislatura |
| `https://dadosabertos.camara.leg.br/api/v2/votacoes` | Votações nominais por intervalo |
| `https://dadosabertos.camara.leg.br/api/v2/votacoes/{id}/votos` | Votos individuais |
| `https://dadosabertos.camara.leg.br/api/v2/deputados` | Cadastro |
| `https://dadosabertos.camara.leg.br/api/v2/deputados/{id}/discursos` | Discursos do deputado |
| `https://www.camara.leg.br/SitCamaraWS` | Endpoint legacy SOAP/XML para teor RTF (Base64) |

A versão da API documentada como referência é a `v2`, conforme
`https://dadosabertos.camara.leg.br/swagger/api.html`. Schema de
resposta pode mudar sem aviso -- mitigamos isso com normalização
explícita por função (`_normalizar_proposicao`, etc.) e schema Polars
declarado no Parquet.

## Padrão de retry

```text
[ ConnectError | TimeoutException | ReadError | 5xx ]
        |
        v
  [ tenacity ]  -- 5 tentativas
        |
   wait_exponential(min=1s, max=60s)
        |
   1s -> 2s -> 4s -> 8s -> 16s
```

- **Não** retentamos em **4xx** (erro permanente do cliente).
- Logs em cada retry via Loguru com nível WARNING.

Decorator pronto: `@retry_resiliente` em `coleta/http.py`.

## Token bucket

Default 10 req/s, capacidade 20 (rajada inicial permitida). Override
via `HEMICICLO_RATE_LIMIT=<float>`.

```python
bucket = TokenBucket()  # 10/s
bucket.aguardar()       # bloqueia até liberar 1 token
```

Thread-safe via `threading.Lock`. Sleep ocorre fora da seção crítica
para permitir paralelismo real entre threads competindo pelo mesmo
balde.

## Checkpoint persistente

Arquivo: `~/hemiciclo/cache/checkpoints/camara_<hash>.json`.

`<hash>` é os primeiros 16 chars do SHA-256 dos params normalizados
(legislaturas + tipos, ordenados). Mesmo conjunto de params resolve
para o mesmo arquivo entre execuções.

### Estrutura

```python
class CheckpointCamara(BaseModel):
    iniciado_em: datetime
    atualizado_em: datetime
    legislaturas: list[int]
    tipos: list[str]
    proposicoes_baixadas: set[int]
    votacoes_baixadas: set[str]
    votos_baixados: set[tuple[str, int]]   # (votacao_id, deputado_id)
    discursos_baixados: set[str]            # sha256 do conteúdo
    deputados_baixados: set[int]
    anos_concluidos: set[tuple[int, int]]   # (legislatura, ano) -- S24c
    erros: list[dict[str, Any]]
```

### Cobertura temporal de proposições (S24c)

`coletar_proposicoes(legislatura, ano=None)` itera os 4 anos canônicos
da legislatura quando o chamador omite `ano`. A API
`/proposicoes` filtra por `ano` (não por `idLegislatura`), então
cobrir uma legislatura inteira exige iterar
`[N, N+1, N+2, N+3]` onde `N = ano_inicial_legislatura(legislatura)`.
Por exemplo, L57 -> `[2023, 2024, 2025, 2026]`.

`max_itens` é interpretado **globalmente** entre os 4 anos; o limite
não é multiplicado por ano. Quando `checkpoint` é fornecido (e
`coletar_proposicoes` é chamado pelo orquestrador), cada ano que
termina sem interrupção é registrado em `anos_concluidos`. Em uma
nova execução com o mesmo checkpoint, anos já marcados são pulados
-- retomada granular após `kill -9`. A idempotência via
`proposicoes_baixadas` continua protegendo contra duplicação no ano
em curso, que pode ser revisitado se interrompido no meio.

### Escrita atômica

```text
1. write -> <path>.tmp        (mesma partição)
2. Path.replace               (rename syscall, atômico em POSIX)
```

Em `kill -9` no meio do passo 1, o arquivo final original permanece
intacto.

### Frequência de salvamento

A cada **50 requisições bem-sucedidas** OU ao final da coleta. Trade-off
entre I/O excessivo e perda em caso de falha.

## Schema dos Parquet

Saída: `<dir_saida>/<tipo>.parquet`.

### proposicoes.parquet (12 colunas, conforme spec S24)

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | Int64 | ID único Câmara |
| `sigla` | Utf8 | Tipo da proposição (PL, PEC, MP, etc.) |
| `numero` | Int64 | Número sequencial |
| `ano` | Int64 | Ano de apresentação |
| `ementa` | Utf8 | Texto-resumo oficial |
| `tema_oficial` | Utf8 | Categoria oficial da Câmara |
| `autor_principal` | Utf8 | Nome do autor primário |
| `data_apresentacao` | Utf8 | Data ISO |
| `status` | Utf8 | Situação atual da tramitação |
| `url_inteiro_teor` | Utf8 | Link para PDF do teor |
| `casa` | Utf8 | Constante "camara" |
| `hash_conteudo` | Utf8 | URI da API (proxy de identidade) |

### votacoes.parquet, votos.parquet, discursos.parquet, deputados.parquet

Schemas definidos em `src/hemiciclo/coleta/camara.py` como
`SCHEMA_VOTACAO`, `SCHEMA_VOTO`, `SCHEMA_DISCURSO`, `SCHEMA_DEPUTADO`.

A consolidação em DuckDB unificado (Câmara + Senado, com chaves
estrangeiras) é trabalho da S26. Por enquanto, output é Parquet por
tipo, casa por casa.

## Padrão para S25 (Senado)

A S25 deve replicar o mesmo padrão arquitetural:

- `src/hemiciclo/coleta/senado.py` espelha `camara.py`.
- Reutiliza `coleta/http.py`, `coleta/rate_limit.py`, `coleta/checkpoint.py`.
- Pode introduzir `CheckpointSenado` se schema diferir
  significativamente; senão, parametriza `CheckpointCamara` ou cria
  `CheckpointBase`.
- Endpoint base: `https://legis.senado.leg.br/dadosabertos/`.

## Smoke test manual

```bash
uv run hemiciclo coletar camara \
    --legislatura 57 \
    --tipos proposicoes \
    --max-itens 100 \
    --output /tmp/camara_smoke

ls /tmp/camara_smoke/proposicoes.parquet

uv run python -c "
import polars as pl
df = pl.read_parquet('/tmp/camara_smoke/proposicoes.parquet')
print(f'rows: {len(df)}, cols: {len(df.columns)}')
"
```

Esperado: `rows: 100, cols: >= 12`.

Teste de retomada:

```bash
uv run hemiciclo coletar camara -l 57 -t proposicoes --max-itens 200 \
    --output /tmp/camara_resume &
sleep 3 && kill -9 $!
time uv run hemiciclo coletar camara -l 57 -t proposicoes --max-itens 200 \
    --output /tmp/camara_resume
```

Segunda execução completa em < 50% do tempo da primeira.

## Limites conhecidos

- **Coleta sequencial.** asyncio fica em sprint dedicada se gargalo
  emergir. Para uso doméstico (1 usuário, alguns G de dados), sequencial
  é suficiente.
- **Sem autenticação.** Endpoints públicos da Câmara não exigem token
  hoje. Se mudar, adicionar suporte em sprint nova.
- **RTF Base64 dos discursos.** S24 entrega o pipeline de coleta de
  metadados de discurso; o decode RTF (replicando `src/lib/rtf.R` legacy)
  fica como sub-tarefa de S30 quando o pipeline integrado for armado.
- **Rate limit informal.** A Câmara não documenta limites estritos.
  Default 10/s é conservador; observar comportamento em produção pode
  permitir aumentar.

## API Senado (S25)

A coleta do Senado Federal segue o mesmo padrão arquitetural da Câmara
(httpx + tenacity + TokenBucket + Pydantic + Polars Parquet), mas com
três diferenças relevantes que motivaram um módulo dedicado em
`src/hemiciclo/coleta/senado.py`.

### Endpoints alvo

Base: `https://legis.senado.leg.br/dadosabertos`

| Endpoint | Propósito |
|---|---|
| `/senador/lista/legislatura/{leg}` | Cadastro de senadores ativos |
| `/senador/{cod}` | Detalhe + biografia |
| `/materia/pesquisa/lista?ano={ano}` | Listagem de matérias |
| `/materia/{cod}` | Detalhe (mesma limitação ACHADO 2 da Câmara; fica em S25b se necessário) |
| `/plenario/lista/votacao/{ano}` | Votações nominais por ano |
| `/plenario/votacao/{cod}` | Detalhe + votos individuais |
| `/senador/{cod}/discursos?ano={ano}` | Discursos por senador |

### Diferença 1: XML por default, JSON negociável

A API do Senado entrega XML como `Content-Type` default em vários
endpoints. Negociamos `Accept: application/json` em todas as chamadas
do `_baixar`, mas mantemos fallback robusto via `_parse_xml_ou_json`:

```python
def _parse_xml_ou_json(resp: httpx.Response) -> dict[str, Any]:
    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype or ctype.endswith("/json"):
        return resp.json()
    from lxml import etree
    raiz = etree.fromstring(resp.content)
    return {tag_raiz: _xml_para_dict(raiz)}
```

O parser XML lida com:

- Múltiplos filhos com mesma tag (vira lista).
- Namespaces XML (são removidos da chave).
- Texto livre vs estrutura aninhada.

### Diferença 2: IDs inteiros e códigos distintos

- Senador: `CodigoParlamentar` é `int` (ex.: 5012, 5013).
- Matéria: `CodigoMateria` é `int` (ex.: 100, 101).
- Votação: `CodigoSessaoVotacao` é `int`.

A `CheckpointSenado` portanto usa `set[int]` para `materias_baixadas`,
`votacoes_baixadas`, `senadores_baixados`, e `set[tuple[int, int]]`
para `votos_baixados` (vs `set[str]`/`set[tuple[str, int]]` da Câmara).

### Diferença 3: Discursos por senador, não por sessão

Diferente da Câmara que tem `/proposicoes/{id}` paginado por sessão,
o Senado expõe discursos sob o senador (`/senador/{cod}/discursos`).
O orquestrador colete senadores antes de discursos, então itera sobre
os códigos coletados.

### Coexistência de checkpoints

Ambos checkpoints podem coexistir em `~/hemiciclo/cache/checkpoints/`
sem colisão de nome de arquivo:

- `camara_<hash>.json` -- via `caminho_checkpoint(home, h)`.
- `senado_<hash>.json` -- via `caminho_checkpoint_senado(home, h)`.

O `hash_params_senado` adiciona prefixo `senado:` na seed do SHA256,
garantindo hashes distintos mesmo com parâmetros numéricos coincidentes.

### Schema 12 colunas alinhado

O Parquet `materias.parquet` reusa o mesmo schema de 12 colunas das
proposições da Câmara, com `casa = "senado"`. Isso permite união
trivial em S26 (DuckDB unificado):

```sql
CREATE TABLE proposicoes_unificadas AS
    SELECT * FROM read_parquet('camara/proposicoes.parquet')
    UNION ALL
    SELECT * FROM read_parquet('senado/materias.parquet');
```

`hash_conteudo` é SHA256 da ementa (lição S24, ACHADO 3): determinístico,
útil para deduplicação cross-casa.

### Smoke test local

```bash
uv run hemiciclo coletar senado --ano 2024 --tipos materias \
    --max-itens 50 --output /tmp/senado_smoke
ls /tmp/senado_smoke/materias.parquet
uv run python -c "
import polars as pl
df = pl.read_parquet('/tmp/senado_smoke/materias.parquet')
print(f'rows: {len(df)}, cols: {len(df.columns)}')
"
```

Esperado: `rows: 50, cols: 12`.

## Enriquecimento de proposições (S24b)

### Por que duas chamadas?

A API da Câmara (Dados Abertos v2) segue padrão REST: `GET /proposicoes`
paginado devolve apenas os 6 campos resumidos -- `id`, `siglaTipo`,
`numero`, `ano`, `ementa`, `dataApresentacao`. Para os campos
críticos do classificador (`temaOficial`), do dashboard (`autorPrincipal`,
`urlInteiroTeor`) e dos filtros temporais (`statusProposicao.descricaoSituacao`),
é preciso uma segunda chamada `GET /proposicoes/{id}` por proposição.

A S24 já criou normalização com placeholders vazios para esses 4 campos;
sem o enriquecimento da S24b, a produção real do usuário tem recall
de C1 (categoria oficial) próximo de zero. Após S24b, o classificador
opera em recall pleno e cai para C2/C3 só nos casos legítimos onde
a Câmara não preencheu `temaOficial` no payload.

### Pipeline de enriquecimento

Após `coletar_proposicoes()` para uma legislatura, o orquestrador itera
`checkpoint.proposicoes_baixadas - checkpoint.proposicoes_enriquecidas`
e chama `enriquecer_proposicao(prop_id, home=, bucket=, cli=,
autores_resolvidos=)` para cada uma. A função:

1. Consulta cache local `<home>/cache/proposicoes/camara-<id>.json`.
2. Cache miss -> `GET /proposicoes/{id}` com retry resiliente (5xx).
3. Resolve `autor_principal` via `GET <uriAutores>` extra (cache em
   memória dentro da execução evita rebuscar autor repetido).
4. Persiste payload bruto em cache para reuso entre sessões.
5. Retorna dict com 7 chaves (`id`, `casa`, 4 campos, `enriquecido_em`).

### Persistência: parquet separado

O detalhe vai para `<dir_saida>/proposicoes_detalhe.parquet` (NÃO mergeado
no `proposicoes.parquet`). Justificativas:

- **Idempotência granular**: re-rodar enriquecimento sem reescrever listagem.
- **Reversibilidade**: deletar `proposicoes_detalhe.parquet` desfaz tudo.
- **Compatibilidade retroativa**: parquets pré-S24b continuam carregáveis.
- **Schema evolution**: adicionar 5ª coluna no detalhe não exige rescrever
  o arquivo de listagem.

Custo: consolidador faz `UPDATE ... FROM ... COALESCE` em vez de `INSERT`
(ver `_inserir_proposicoes_detalhe` em `etl/consolidador.py`).

### Cache transversal

Path canônico: `<home>/cache/proposicoes/<casa>-<id>.json`. JSON em vez
de Parquet porque o payload é dict aninhado pequeno (~3-5KB) e JSON é
debugável/portável entre sessões. Escrita atômica via
`tempfile.NamedTemporaryFile` + `Path.replace`.

Cache hit pula a chamada à API: `enriquecer_proposicao` consulta o cache
**antes** de bater no endpoint, então re-rodar a coleta na mesma máquina
custa zero rede.

### Flag CLI

```bash
hemiciclo coletar camara -l 57 -t proposicoes --enriquecer-proposicoes
hemiciclo coletar camara -l 57 -t proposicoes --no-enriquecer-proposicoes
```

Default: `--enriquecer-proposicoes` ligado. Desligar é útil em testes
de regressão ou quando o usuário quer só a listagem rápida.

### Custo estimado

Coleta plena legislatura 57 (~50k proposições) = **50k requisições extras**
para detalhe + até **50k extras** para autores (cache em memória reduz na
prática). A 10 req/s, isso adiciona ~83 min ao tempo total da sprint --
aceitável; documentado no spec da S24b.

### Smoke

```bash
uv run hemiciclo coletar camara -l 57 -t proposicoes --max-itens 20 \
    --enriquecer-proposicoes --output /tmp/s24b_smoke
ls /tmp/s24b_smoke/
# Esperado: proposicoes.parquet  proposicoes_detalhe.parquet

uv run python -c "
import polars as pl
det = pl.read_parquet('/tmp/s24b_smoke/proposicoes_detalhe.parquet')
print(f'rows: {len(det)}')
print(f'tema_oficial nao-nulo: {det[\"tema_oficial\"].is_not_null().sum()}')
"
```

Critério: `tema_oficial IS NOT NULL` em ≥ 90% das 20 proposições
(tolerância para 1-2 falhas de rede em smoke pequeno).
