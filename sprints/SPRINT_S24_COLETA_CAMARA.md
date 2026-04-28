# Sprint S24 -- Coleta Câmara: discursos + votos + proposições + checkpoint

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-28
**Autor:** @AndreBFarias
**Status:** DONE (2026-04-28)
**Depende de:** S22 (DONE)
**Bloqueia:** S26, S30
**Esforço:** M (3-5 dias)
**ADRs vinculados:** ADR-002 (voto nominal espinha dorsal)
**Branch:** feature/s24-coleta-camara

---

## 1. Objetivo

Implementar coleta resiliente da API Câmara dos Deputados (Dados Abertos) -- **proposições, votações nominais, votos individuais, discursos, cadastro de deputados** -- com:

- Checkpoint persistente em JSON (Pydantic) com escrita atômica a cada 50 requisições
- Retomada idempotente: kill -9 + relançar continua exatamente de onde parou
- Retry com backoff exponencial (tenacity, 5 tentativas, max 60s entre)
- Rate limiting via token bucket (default 10 req/s, configurável via env)
- Persistência em Parquet via Polars (DuckDB schema unificado fica em S26)
- CLI `hemiciclo coletar camara --legislatura 55 56 57 --tipos proposicoes votacoes votos discursos`
- Logs estruturados Loguru por sessão

Esta sprint estabelece o **padrão de coleta** que S25 (Senado) replicará.

## 2. Contexto

API da Câmara é instável, lenta em horários de pico, e tem rate limits não-documentados que mudam sem aviso. Coleta longa de 12 anos (legislaturas 55-57, ~1.5M discursos + ~5k votações × ~513 deputados = ~2.5M votos) precisa sobreviver a quedas de internet, kill -9, fechamento de browser, máquina dormindo. Sem checkpoint resumível, projeto inviável: usuário não vai esperar 12h pra reiniciar do zero.

S22 já entregou estrutura `src/hemiciclo/coleta/` vazia. Esta sprint preenche com o coletor completo.

S26 (próxima após esta + S25) consolida output de S24+S25 em DuckDB schema unificado. Por enquanto, output é Parquet por tipo em pasta de saída.

## 3. Escopo

### 3.1 In-scope

- [ ] **Dependências adicionadas a `pyproject.toml`**:
  - `httpx>=0.27` em runtime
  - `tenacity>=8.2` em runtime
  - `polars>=1.0` em runtime
  - `respx>=0.21` em dev (mock httpx)
  - `freezegun>=1.5` em dev (controle de tempo nos testes)
- [ ] `uv.lock` regenerado
- [ ] **`src/hemiciclo/coleta/__init__.py`** marker
- [ ] **`src/hemiciclo/coleta/http.py`** wrapper httpx + tenacity:
  - Função `cliente_http(timeout: float = 30.0) -> httpx.Client` configurada
  - Decorator `@retry_resiliente` aplicando tenacity: 5 tentativas, backoff exponencial 1s -> 2s -> 4s -> 8s -> 16s, max 60s entre tentativas
  - Retry em: `httpx.HTTPStatusError` (5xx), `httpx.ConnectError`, `httpx.TimeoutException`, `httpx.ReadError`
  - **Não** retry em: 4xx (erro permanente), `httpx.RequestError` outros
  - User-Agent identificável: `Hemiciclo/0.1.0 (+https://github.com/AndreBFarias/Hemiciclo)`
  - Logs estruturados Loguru a cada retry
- [ ] **`src/hemiciclo/coleta/rate_limit.py`** token bucket:
  - Classe `TokenBucket(taxa: float, capacidade: int)` thread-safe
  - Método `aguardar() -> None` bloqueia até token disponível
  - Default: 10 req/s, capacidade 20
  - Override via env `HEMICICLO_RATE_LIMIT` (req/s)
- [ ] **`src/hemiciclo/coleta/checkpoint.py`** persistência Pydantic:
  - Modelo `CheckpointCamara(BaseModel)`:
    - `iniciado_em: datetime`
    - `atualizado_em: datetime`
    - `legislaturas: list[int]`
    - `tipos: list[str]`
    - `proposicoes_baixadas: set[int]` (ids únicos)
    - `votacoes_baixadas: set[str]` (ids da Câmara)
    - `votos_baixados: set[tuple[str, int]]` (votacao_id, deputado_id)
    - `discursos_baixados: set[str]` (hash sha256 do conteúdo)
    - `deputados_baixados: set[int]`
    - `erros: list[dict]` ({url, codigo, mensagem, timestamp})
  - Função `hash_params(legislaturas, tipos) -> str` (sha256 dos params normalizados)
  - Função `caminho_checkpoint(home: Path, hash_params: str) -> Path` -> `<home>/cache/checkpoints/camara_<hash>.json`
  - Função `salvar_checkpoint(checkpoint, path) -> None` com escrita atômica (tempfile + replace)
  - Função `carregar_checkpoint(path) -> CheckpointCamara | None`
  - Salvar a cada 50 requisições OU ao final
- [ ] **`src/hemiciclo/coleta/camara.py`** módulo principal:
  - `URL_BASE = "https://dadosabertos.camara.leg.br/api/v2"`
  - `coletar_proposicoes(legislatura: int, ano: int | None, max_itens: int | None) -> Iterator[dict]` -- pagina via `link header`, yield item por item
  - `coletar_votacoes(legislatura: int, data_inicio: date, data_fim: date) -> Iterator[dict]`
  - `coletar_votos_de_votacao(votacao_id: str) -> list[dict]`
  - `coletar_discursos(legislatura: int, data_inicio: date, data_fim: date) -> Iterator[dict]` -- usa endpoint legacy SitCamaraWS para teor RTF (mantém padrão R)
  - `coletar_cadastro_deputados(legislatura: int) -> list[dict]`
  - `executar_coleta(params: ParametrosColeta, dir_saida: Path, checkpoint: CheckpointCamara) -> None` orquestrador
  - Cada função respeita rate limiter + checkpoint + retry
- [ ] **Persistência em Parquet via Polars**:
  - Após coleta, escreve `<dir_saida>/proposicoes.parquet` com schema definido (12 colunas mínimas: id, sigla, numero, ano, ementa, tema_oficial, autor_principal, data_apresentacao, status, url_inteiro_teor, casa, hash_conteudo)
  - `<dir_saida>/votacoes.parquet`, `<dir_saida>/votos.parquet`, `<dir_saida>/discursos.parquet`, `<dir_saida>/deputados.parquet`
  - DuckDB schema unificado fica em S26 -- aqui é só Parquet
- [ ] **Modelo `ParametrosColeta`** em `src/hemiciclo/coleta/__init__.py` (Pydantic):
  - `legislaturas: list[int]`
  - `tipos: list[Literal["proposicoes", "votacoes", "votos", "discursos", "deputados"]]`
  - `data_inicio: date | None = None`
  - `data_fim: date | None = None`
  - `max_itens: int | None = None`
  - `dir_saida: Path`
- [ ] **CLI `hemiciclo coletar camara`** novo subcomando em `cli.py`:
  - `--legislatura 55 56 57` (int multiple)
  - `--tipos proposicoes votacoes votos discursos deputados` (multiple)
  - `--data-inicio 2023-02-01` (opcional)
  - `--data-fim 2026-04-28` (opcional)
  - `--max-itens 100` (opcional, pra smoke test)
  - `--output /tmp/camara_smoke` (default `~/hemiciclo/cache/camara/`)
  - Progress bar Rich mostrando: itens baixados / total estimado / req/s atual / retries acumulados
- [ ] **Logs estruturados** com `logger.bind(coleta="camara", legislatura=L, tipo=T)`:
  - Por requisição: log INFO com URL + duração
  - Por retry: log WARNING com tentativa
  - Por erro permanente: log ERROR + adiciona em `checkpoint.erros`
  - Por checkpoint salvo: log DEBUG
- [ ] **Testes unit** em `tests/unit/test_coleta_http.py` (5 testes):
  - `test_cliente_http_user_agent_correto`
  - `test_retry_em_503`
  - `test_retry_em_timeout`
  - `test_nao_retry_em_404`
  - `test_backoff_exponencial_respeitado` (com freezegun)
- [ ] **Testes unit** em `tests/unit/test_coleta_rate_limit.py` (4 testes):
  - `test_token_bucket_consome_token`
  - `test_token_bucket_aguarda_quando_vazio`
  - `test_capacidade_maxima`
  - `test_taxa_via_env_override`
- [ ] **Testes unit** em `tests/unit/test_coleta_checkpoint.py` (8 testes):
  - `test_serializacao_round_trip`
  - `test_hash_params_deterministico`
  - `test_hash_params_ordem_irrelevante` (legislaturas [55, 56] == [56, 55])
  - `test_escrita_atomica_nao_corrompe_em_kill` (simula write parcial)
  - `test_carregar_inexistente_retorna_none`
  - `test_caminho_checkpoint_em_home_correto`
  - `test_set_de_tuples_serializa_como_lista`
  - `test_property_based_via_hypothesis` (hypothesis: round-trip arbitrário)
- [ ] **Testes unit** em `tests/unit/test_coleta_camara.py` (8 testes via respx):
  - `test_coletar_proposicoes_caminho_feliz`
  - `test_coletar_proposicoes_paginacao_link_header`
  - `test_coletar_votacoes_intervalo_de_data`
  - `test_coletar_votos_de_votacao`
  - `test_coletar_discursos_legacy_rtf`
  - `test_503_retry_e_sucesso`
  - `test_404_propaga_erro` (não retry)
  - `test_max_itens_respeitado`
- [ ] **Testes integração** em `tests/integracao/test_coleta_camara_e2e.py` (3 testes mockados):
  - `test_coleta_completa_persiste_parquet` (smoke 10 proposições mockadas)
  - `test_kill_e_retomada_idempotente` (kill no meio, relança, conta requisições -- segunda execução < 50% da primeira)
  - `test_checkpoint_persistido_com_set_de_tuples`
- [ ] **`docs/arquitetura/coleta.md`** documentando: APIs alvo, padrão de retry, formato de checkpoint, schema dos parquets
- [ ] **`CHANGELOG.md`** entrada `[Unreleased]` com bullet `feat(coleta): coletor da Câmara com checkpoint resumível`

### 3.2 Out-of-scope (explícito)

- **Senado** -- fica em S25 (replica padrão)
- **DuckDB schema unificado** -- fica em S26
- **Mapeamento tópico→PL** -- fica em S27
- **Coleta real em CI** -- nesta sprint, todos os testes usam respx mocks; coleta real é smoke manual
- **Autenticação/proxy/Tor** -- fica em sprints futuras se necessário
- **Coleta paralela com asyncio** -- fica em sprint dedicada se gargalo emergir; nesta sprint, coleta sequencial é suficiente
- **Persistência incremental em DuckDB** -- só Parquet final aqui

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `src/hemiciclo/coleta/__init__.py` | Marker + ParametrosColeta Pydantic |
| `src/hemiciclo/coleta/http.py` | Cliente httpx + tenacity wrapper |
| `src/hemiciclo/coleta/rate_limit.py` | TokenBucket thread-safe |
| `src/hemiciclo/coleta/checkpoint.py` | CheckpointCamara Pydantic + escrita atômica |
| `src/hemiciclo/coleta/camara.py` | Módulo principal de coleta |
| `tests/unit/test_coleta_http.py` | 5 testes |
| `tests/unit/test_coleta_rate_limit.py` | 4 testes |
| `tests/unit/test_coleta_checkpoint.py` | 8 testes |
| `tests/unit/test_coleta_camara.py` | 8 testes via respx |
| `tests/integracao/test_coleta_camara_e2e.py` | 3 testes integração |
| `docs/arquitetura/coleta.md` | Documentação técnica |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `pyproject.toml` | Adiciona httpx, tenacity, polars, respx, freezegun |
| `uv.lock` | Regenerado |
| `src/hemiciclo/cli.py` | Novo subcomando `coletar camara` |
| `tests/unit/test_sentinela.py` | Novo teste do subcomando coletar (smoke) |
| `CHANGELOG.md` | Entrada [Unreleased] |
| `sprints/ORDEM.md` | S24 -> DONE |

## 5. Implementação detalhada

### 5.1 Passo a passo

1. Confirmar branch `feature/s24-coleta-camara`.
2. Adicionar deps (httpx, tenacity, polars, respx, freezegun) ao pyproject; `uv sync --all-extras`.
3. Implementar `coleta/http.py` (wrapper httpx + tenacity).
4. Escrever `tests/unit/test_coleta_http.py` (5 testes); rodar isolado.
5. Implementar `coleta/rate_limit.py` (TokenBucket).
6. Escrever `tests/unit/test_coleta_rate_limit.py` (4 testes).
7. Implementar `coleta/checkpoint.py` (Pydantic + atomic write).
8. Escrever `tests/unit/test_coleta_checkpoint.py` (8 testes, incl. property-based).
9. Implementar `coleta/__init__.py` com `ParametrosColeta`.
10. Implementar `coleta/camara.py` (5 funções de coleta + orquestrador).
11. Escrever `tests/unit/test_coleta_camara.py` (8 testes mockando httpx via respx).
12. Adicionar subcomando `coletar` em `cli.py` (Typer subapp).
13. Escrever teste do CLI em `test_sentinela.py`.
14. Escrever `tests/integracao/test_coleta_camara_e2e.py` (3 testes integrados).
15. Escrever `docs/arquitetura/coleta.md`.
16. Atualizar `CHANGELOG.md`.
17. Rodar smoke local: `uv run hemiciclo coletar camara --legislatura 57 --tipos proposicoes --max-itens 100 --output /tmp/camara_smoke` -> conta linhas no Parquet, deve ser 100.
18. Testar retomada: `uv run hemiciclo coletar camara ... --max-itens 200 &; sleep 3 && kill -9 %1; uv run hemiciclo coletar camara ... --max-itens 200` -> segunda execução completa em < 50% do tempo.
19. `make check` deve passar com cobertura ≥ 90% nos novos arquivos.
20. Atualizar `sprints/ORDEM.md` mudando S24 para DONE.

### 5.2 Decisões técnicas

- **httpx síncrono**, não async, para esta sprint. asyncio é overkill pra coleta sequencial; fica pra sprint futura se gargalo aparecer.
- **tenacity decorator** em vez de retry manual -- API testada, exponencial built-in, logs prontos.
- **Polars sobre Pandas** -- conforme D1 do plano. `pl.DataFrame.write_parquet()` é mais rápido.
- **Set serializa como lista ordenada** em JSON do checkpoint -- determinismo e compatibilidade.
- **Atomic write via `tempfile.NamedTemporaryFile` + `Path.replace`** -- evita corromper checkpoint em kill -9.
- **respx pra mockar httpx** -- precedente moderno (substitui responses).
- **hypothesis pra property-based** no checkpoint -- garante round-trip pra qualquer entrada válida.

### 5.3 Trecho de referência -- `coleta/http.py` esqueleto

```python
"""Cliente HTTP resiliente para APIs do Congresso."""

from __future__ import annotations

import httpx
from loguru import logger
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from hemiciclo import __version__

USER_AGENT = f"Hemiciclo/{__version__} (+https://github.com/AndreBFarias/Hemiciclo)"


def cliente_http(timeout: float = 30.0) -> httpx.Client:
    """Cria cliente httpx com User-Agent e timeout padrao."""
    return httpx.Client(
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
    )


retry_resiliente = retry(
    retry=retry_if_exception_type(
        (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException, httpx.ReadError)
    ),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, "WARNING"),
    reraise=True,
)
```

### 5.4 Trecho de referência -- `coleta/rate_limit.py`

```python
"""Token bucket simples thread-safe."""

from __future__ import annotations

import threading
import time


class TokenBucket:
    def __init__(self, taxa: float = 10.0, capacidade: int = 20) -> None:
        self.taxa = taxa
        self.capacidade = capacidade
        self._tokens = float(capacidade)
        self._ultimo = time.monotonic()
        self._lock = threading.Lock()

    def aguardar(self) -> None:
        while True:
            with self._lock:
                agora = time.monotonic()
                elapsed = agora - self._ultimo
                self._tokens = min(
                    self.capacidade,
                    self._tokens + elapsed * self.taxa,
                )
                self._ultimo = agora
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                espera = (1.0 - self._tokens) / self.taxa
            time.sleep(espera)
```

### 5.5 Trecho de referência -- `coleta/checkpoint.py` modelo

```python
"""Checkpoint persistente com escrita atomica."""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class CheckpointCamara(BaseModel):
    iniciado_em: datetime
    atualizado_em: datetime
    legislaturas: list[int]
    tipos: list[str]
    proposicoes_baixadas: set[int] = Field(default_factory=set)
    votacoes_baixadas: set[str] = Field(default_factory=set)
    votos_baixados: set[tuple[str, int]] = Field(default_factory=set)
    discursos_baixados: set[str] = Field(default_factory=set)
    deputados_baixados: set[int] = Field(default_factory=set)
    erros: list[dict] = Field(default_factory=list)

    def total_baixado(self) -> int:
        return (
            len(self.proposicoes_baixadas)
            + len(self.votacoes_baixadas)
            + len(self.votos_baixados)
            + len(self.discursos_baixados)
            + len(self.deputados_baixados)
        )


def hash_params(legislaturas: list[int], tipos: list[str]) -> str:
    base = f"{sorted(legislaturas)}-{sorted(tipos)}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def salvar_checkpoint(cp: CheckpointCamara, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dados = cp.model_dump(mode="json")
    # set serializa como list, tuple como list -- normalizar:
    dados["proposicoes_baixadas"] = sorted(dados["proposicoes_baixadas"])
    dados["votacoes_baixadas"] = sorted(dados["votacoes_baixadas"])
    dados["votos_baixados"] = sorted(map(list, cp.votos_baixados))
    dados["discursos_baixados"] = sorted(dados["discursos_baixados"])
    dados["deputados_baixados"] = sorted(dados["deputados_baixados"])

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as tmp:
        json.dump(dados, tmp, ensure_ascii=False, indent=2, default=str)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def carregar_checkpoint(path: Path) -> CheckpointCamara | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        dados = json.load(f)
    dados["votos_baixados"] = [tuple(v) for v in dados["votos_baixados"]]
    return CheckpointCamara.model_validate(dados)
```

## 6. Testes (resumo)

- **5** http (retry, user-agent, backoff)
- **4** rate_limit (token bucket, env override)
- **8** checkpoint (round-trip, atomic, hypothesis)
- **8** camara (respx mocks, paginação, retry, max_itens)
- **3** integração (e2e mockado, retomada idempotente)
- **1** CLI subcomando coletar
- **Total: 29 testes novos** + 73 herdados = 102 testes na suíte total.

## 7. Proof-of-work runtime-real

**Comando local:**

```bash
$ uv run hemiciclo coletar camara \
    --legislatura 57 \
    --tipos proposicoes \
    --max-itens 100 \
    --output /tmp/camara_smoke
$ ls /tmp/camara_smoke/proposicoes.parquet
$ uv run python -c "import polars as pl; df = pl.read_parquet('/tmp/camara_smoke/proposicoes.parquet'); print(f'rows: {len(df)}, cols: {len(df.columns)}')"
```

**Saída esperada:**

```
[coleta][camara] 100 proposicoes baixadas em XXs (taxa media YY req/s, 0 retries)
/tmp/camara_smoke/proposicoes.parquet
rows: 100, cols: >= 12
```

**Teste de retomada:**

```bash
$ uv run hemiciclo coletar camara --legislatura 57 --tipos proposicoes --max-itens 200 --output /tmp/camara_resume &
$ sleep 3 && kill -9 $!
$ time uv run hemiciclo coletar camara --legislatura 57 --tipos proposicoes --max-itens 200 --output /tmp/camara_resume
```

Segunda execução deve completar em < 50% do tempo da primeira (cache + checkpoint).

**Critério de aceite (checkbox):**

- [ ] Coleta de 100 proposições reais completa em < 60s (com rede saudável)
- [ ] kill -9 + relançar retoma exatamente de onde parou (segunda execução faz < 50% das requisições)
- [ ] 503 da API gera retry com backoff exponencial visível em log
- [ ] 404 propaga erro sem retry
- [ ] Checkpoint salvo a cada 50 requisições no `~/hemiciclo/cache/checkpoints/camara_<hash>.json`
- [ ] Parquet de saída tem >= 12 colunas conforme schema declarado
- [ ] respx mocks cobrem 8 cenários (caminho feliz + paginação + 503 + 404 + intervalo + max_itens + RTF + cadastro)
- [ ] hypothesis property-based no round-trip do checkpoint passa
- [ ] Cobertura >= 90% nos arquivos novos
- [ ] Mypy --strict zero erros
- [ ] Ruff zero violações
- [ ] CI verde nos 6 jobs do PR
- [ ] CHANGELOG.md atualizado

## 8. Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| API da Câmara fora do ar durante smoke local | A | M | Smoke é opcional; testes unit/integração via respx cobrem 100% do caminho |
| Rate limit da API mais agressivo que documentado | M | M | TokenBucket com taxa baixa default (10/s) + retry em 429 |
| RTF Base64 dos discursos quebrar parsing | M | M | Padrão R já validado em S22 (rtf.R legacy); replicar regex de decode |
| Schema de proposição da API mudar | B | A | Documentar versão da API em `docs/arquitetura/coleta.md`; validação Pydantic do payload |
| Polars 1.0 incompatível com pyarrow do uv.lock | B | M | Pinning explícito + CI matriz pega cedo |
| Tempo de coleta legislatura 57 completa exceder paciência humana (>2h) | A | A | `--max-itens` permite smoke; coleta completa real é trabalho de pipeline integrado em S30 |
| `set[tuple[str, int]]` não serializa direto em JSON | A | M | Função `salvar_checkpoint` normaliza explicitamente; teste cobre |

## 9. Validação multi-agente

**Executor (`executor-sprint`):**

1. Lê `VALIDATOR_BRIEF.md`.
2. Lê este spec.
3. Implementa entregas conforme passo a passo.
4. Roda smoke local + proof-of-work.
5. Reporta saída literal.
6. NÃO push, NÃO PR -- orquestrador integra.

**Validador (`validador-sprint`):**

1. Lê BRIEF + spec.
2. Roda proof-of-work independentemente (incluindo smoke real se rede disponível).
3. Verifica I1-I12. Atenção especial a I1 (URL_BASE não pode apontar pra serviço proprietário; só APIs públicas do governo brasileiro).
4. Verifica que checkpoint sobrevive a kill -9 simulado.
5. Decide APROVADO / APROVADO_COM_RESSALVAS / REPROVADO.

## 10. Próximo passo após DONE

S25 (coleta Senado) replica padrão estabelecido aqui. S29 (sessão runner) também desbloqueada (não depende de coleta funcional, mas de modelo Pydantic já existente).
