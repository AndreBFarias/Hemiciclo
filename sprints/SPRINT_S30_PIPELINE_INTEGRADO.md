# Sprint S30 -- Pipeline integrado: coleta -> ETL -> C1+C2+C3 -> projeção + persistência da sessão

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-28
**Status:** DONE (2026-04-28)
**Depende de:** S22 (DONE), S26 (DONE), S27 (DONE), S28 (DONE), S29 (DONE)
**Bloqueia:** S31, S32, S33, S34, S34b, S35
**Esforço:** M (3-5 dias)
**ADRs vinculados:** ADR-008 (modelo base + ajuste local), ADR-011 (cascata C1-C4)
**Branch:** feature/s30-pipeline-integrado

---

## 1. Objetivo

Substituir `_pipeline_dummy` da S29 por **pipeline real** que orquestra todas as camadas anteriores em sequência dentro de uma sessão de pesquisa:

1. **Coleta** (S24/S25) -- baixa proposições, votações, votos, discursos das APIs Câmara+Senado conforme `params.casas`
2. **ETL** (S26) -- consolida parquets em DuckDB local da sessão
3. **Camada 1+2** (S27) -- aplica regex/keywords/categorias + voto agregado + TF-IDF sobre tópico
4. **Camada 3** (S28) -- carrega modelo base v1 + projeta embeddings do recorte (transform, sem refit)
5. **Persistência da sessão** -- materializa relatório em `~/hemiciclo/sessoes/<id>/relatorio_state.json` + `manifesto.json` com hashes

A sessão fica self-contained com `dados.duckdb`, `discursos.parquet`, `votos.parquet`, `proposicoes.parquet`, `relatorio_state.json`, `modelos_locais/`, `manifesto.json`, `log.txt`.

## 2. Contexto

S29 entregou runner subprocess com pipeline dummy. S22-S28 entregaram peças individuais (coleta, ETL, C1+C2, modelo base). S30 conecta tudo: a callable real do `SessaoRunner` agora é o pipeline funcional.

Esta é a sprint que torna o produto **utilizável de ponta a ponta** -- usuário inicia sessão pelo CLI ou Streamlit, pipeline real roda, relatório fica disponível pra dashboard (S31).

**Limitações herdadas (sprints novas READY):**
- S27.1: `votacoes.proposicao_id` ainda ausente -- C1 voto retorna agregação vazia (sprint S30 detecta e marca, não falha)
- S24b: 4 colunas de proposições vazias na produção (não bloqueia pipeline)
- S24c: coletor da Câmara só pega ano inicial da legislatura (limita recall mas não falha)
- S25.3: schema dual API Senado tratado defensivamente

S30 **respeita esses limites** sem regredir, registrando-os em `manifesto.json` da sessão como `limitacoes_conhecidas: ["S24b", "S24c", "S25.3", "S27.1"]`.

## 3. Escopo

### 3.1 In-scope

- [ ] **`src/hemiciclo/sessao/pipeline.py`** orquestrador real:
  - Função `pipeline_real(params: ParametrosBusca, sessao_dir: Path, updater: StatusUpdater) -> None`
  - Assinatura compatível com `_pipeline_dummy` (mesma signature)
  - Estrutura por etapas com `updater.atualizar(estado, pct, etapa, mensagem)` em cada transição:
    1. CRIADA (0%) -> COLETANDO (5-30%) -> ETL (30-50%) -> EMBEDDINGS (50-75%) -> MODELANDO (75-95%) -> CONCLUIDA (100%)
  - Cada etapa try/except: erro vai pra `EstadoSessao.ERRO` com mensagem rica em `status.json`
- [ ] **Etapa 1 -- Coleta (5-30%)**:
  - Para cada `casa` em `params.casas`, instancia coletor (Câmara ou Senado) com `dir_saida = sessao_dir / "raw"`
  - Aplica `params.legislaturas`, `params.data_inicio`, `params.data_fim`, `params.ufs`, `params.partidos` como filtros
  - Reaproveita `~/hemiciclo/cache/checkpoints/` -- sessões diferentes compartilham cache
  - Output: parquets em `sessao_dir / "raw" / {proposicoes,votacoes,votos,discursos,deputados/senadores}.parquet`
- [ ] **Etapa 2 -- ETL/consolidação (30-50%)**:
  - Cria `dados.duckdb` na pasta da sessão (slice próprio, não mestre)
  - `consolidar_parquets_em_duckdb(sessao_dir / "raw", sessao_dir / "dados.duckdb")`
  - Aplica filtros adicionais via SQL se `params.ufs`/`params.partidos` (após carga)
- [ ] **Etapa 3 -- Camada 1+2 (50-65%)**:
  - Carrega tópico via `topicos.carregar_topico(params.topico_yaml)` se `params.topico` for path; senão usa carregador implícito de `topicos/<topico>.yaml`
  - Chama `classificar_c1_c2(topico, conn)` que retorna DataFrame parlamentar × posição × intensidade
- [ ] **Etapa 4 -- Camada 3 (65-90%)**:
  - Apenas se `Camada.EMBEDDINGS in params.camadas`
  - Verifica `embeddings_disponivel()` -- se não, marca etapa SKIPPED no log e continua
  - Senão: carrega `WrapperEmbeddings`, embed discursos do recorte, `carregar_modelo_base()` e `transform()`
  - Output: `modelos_locais/projecao.parquet` com (parlamentar_id, casa, eixo_0, eixo_1, ..., eixo_49)
- [ ] **Etapa 5 -- Persistência relatório (90-100%)**:
  - `relatorio_state.json` agregando: top 100 a-favor, top 100 contra, assinatura multidimensional dos top 20, contagens, parametros usados
  - `manifesto.json` com SHA256 de cada artefato + versões + timestamps + limitacoes_conhecidas
- [ ] **`src/hemiciclo/sessao/pipeline.py`** módulo único orquestrador (~250-400 linhas)
- [ ] **CLI `hemiciclo sessao iniciar` ATUALIZADA**:
  - Default callable agora é `hemiciclo.sessao.pipeline:pipeline_real` (não mais `_pipeline_dummy`)
  - Flag `--dummy` opcional pra forçar pipeline antigo (útil pra testes locais sem coleta)
- [ ] **Detecção de erros graceful**:
  - API offline -> sessão marcada ERRO com `mensagem` clara
  - Modelo base ausente -> camada 3 SKIPPED, sessão continua
  - Tópico YAML inexistente -> ERRO antes de iniciar coleta
- [ ] **Testes unit** `tests/unit/test_pipeline_real.py` (8 testes, mocks agressivos):
  - `test_pipeline_real_atualiza_status_em_cada_etapa`
  - `test_etapa_coleta_chama_coletor_correto_por_casa`
  - `test_etapa_etl_consolida_parquets_em_duckdb`
  - `test_etapa_classificacao_chama_c1_c2`
  - `test_etapa_embeddings_skipped_se_modelo_ausente`
  - `test_etapa_persiste_relatorio_e_manifesto`
  - `test_falha_api_marca_erro`
  - `test_topico_inexistente_falha_antes_de_coleta`
- [ ] **Testes integração** `tests/integracao/test_pipeline_e2e.py` (2 testes):
  - `test_pipeline_real_completa_em_sessao_mockada` (todos os subsistemas mockados)
  - `test_workflow_sessao_runner_com_pipeline_real` (subprocess + pipeline real, mocks externos)
- [ ] **Sentinela** `test_sentinela.py`:
  - `test_sessao_iniciar_default_pipeline_real` (verifica que `--dummy` é flag opcional)
  - `test_sessao_iniciar_dummy_explicito_funciona`
- [ ] **`docs/arquitetura/pipeline_integrado.md`** documentando:
  - Diagrama das 5 etapas
  - Mapeamento etapas -> EstadoSessao
  - Tratamento de erro por etapa
  - Listagem de limitações conhecidas (S24b/c, S25.3, S27.1)
- [ ] **`CHANGELOG.md`** entrada `[Unreleased]`

### 3.2 Out-of-scope (explícito)

- **Dashboard de relatório** -- fica em S31
- **Grafos de rede** -- fica em S32
- **Histórico de conversão** -- fica em S33
- **ML convertibilidade** -- fica em S34
- **LLM camada 4** -- fica em S34b
- **Exportação completa de sessão** -- fica em S35
- **Smoke real ponta-a-ponta com download de bge-m3** -- proibido em CI; smoke local opcional do executor
- **Treino do modelo base novo** -- pipeline assume base já treinado por `hemiciclo modelo base treinar`

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `src/hemiciclo/sessao/pipeline.py` | Orquestrador real das 5 etapas |
| `tests/unit/test_pipeline_real.py` | 8 testes mockados |
| `tests/integracao/test_pipeline_e2e.py` | 2 testes |
| `docs/arquitetura/pipeline_integrado.md` | Documentação |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `src/hemiciclo/cli.py` | `sessao iniciar` default `pipeline_real`, flag `--dummy` |
| `src/hemiciclo/sessao/__init__.py` | Re-exporta `pipeline_real` |
| `tests/unit/test_sentinela.py` | 2 sentinelas adicionais |
| `CHANGELOG.md` | Entrada [Unreleased] |
| `sprints/ORDEM.md` | S30 -> DONE |

## 5. Implementação detalhada

### 5.1 Esqueleto `pipeline_real`

```python
"""Pipeline integrado real da sessão de pesquisa."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from hemiciclo.sessao.modelo import (
    Camada,
    Casa,
    EstadoSessao,
    ParametrosBusca,
)
from hemiciclo.sessao.runner import StatusUpdater


def pipeline_real(
    params: ParametrosBusca, sessao_dir: Path, updater: StatusUpdater
) -> None:
    """Executa pipeline integrado real: coleta -> ETL -> C1+C2+C3 -> projeção -> persistência."""
    try:
        _etapa_validar(params, sessao_dir, updater)
        _etapa_coleta(params, sessao_dir, updater)
        _etapa_etl(sessao_dir, updater)
        _etapa_classificacao_c1_c2(params, sessao_dir, updater)
        if Camada.EMBEDDINGS in params.camadas:
            _etapa_embeddings_c3(params, sessao_dir, updater)
        _etapa_relatorio(params, sessao_dir, updater)
        updater.atualizar(EstadoSessao.CONCLUIDA, 100.0, "concluida", "Pipeline concluído")
    except Exception as exc:
        logger.exception("[pipeline_real] erro fatal")
        updater.atualizar(
            EstadoSessao.ERRO, -1.0, "erro", f"{type(exc).__name__}: {exc}"
        )
        raise


def _etapa_validar(
    params: ParametrosBusca, sessao_dir: Path, updater: StatusUpdater
) -> None:
    updater.atualizar(EstadoSessao.COLETANDO, 5.0, "validar", "Validando parâmetros")
    # Verifica tópico YAML existe
    # Verifica DuckDB schema migration disponível
    ...


def _etapa_coleta(
    params: ParametrosBusca, sessao_dir: Path, updater: StatusUpdater
) -> None:
    """Etapa 1: coleta APIs Câmara/Senado para sessao_dir/raw/."""
    raw = sessao_dir / "raw"
    raw.mkdir(exist_ok=True)
    if Casa.CAMARA in params.casas:
        updater.atualizar(EstadoSessao.COLETANDO, 10.0, "coleta_camara", "Coletando Câmara")
        from hemiciclo.coleta.camara import executar_coleta as exec_camara
        # ... configura ParametrosColeta, chama
    if Casa.SENADO in params.casas:
        updater.atualizar(EstadoSessao.COLETANDO, 25.0, "coleta_senado", "Coletando Senado")
        from hemiciclo.coleta.senado import executar_coleta as exec_senado
        # ... configura, chama


def _etapa_etl(sessao_dir: Path, updater: StatusUpdater) -> None:
    """Etapa 2: consolida parquets em DuckDB local da sessão."""
    updater.atualizar(EstadoSessao.ETL, 35.0, "etl", "Consolidando em DuckDB")
    from hemiciclo.etl.consolidador import consolidar_parquets_em_duckdb
    db_path = sessao_dir / "dados.duckdb"
    consolidar_parquets_em_duckdb(sessao_dir / "raw", db_path)


def _etapa_classificacao_c1_c2(
    params: ParametrosBusca, sessao_dir: Path, updater: StatusUpdater
) -> None:
    """Etapa 3: aplica camadas 1 e 2 do classificador."""
    updater.atualizar(EstadoSessao.ETL, 55.0, "classificar_c1_c2", "Classificando C1+C2")
    from hemiciclo.modelos.classificador import classificar
    db_path = sessao_dir / "dados.duckdb"
    topico_path = _resolver_topico(params.topico)
    resultado = classificar(
        topico_yaml=topico_path,
        db_path=db_path,
        camadas=["regex", "votos", "tfidf"],
        top_n=100,
    )
    (sessao_dir / "classificacao_c1_c2.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _etapa_embeddings_c3(
    params: ParametrosBusca, sessao_dir: Path, updater: StatusUpdater
) -> None:
    """Etapa 4: projeta embeddings do recorte no modelo base v1 (apenas transform)."""
    updater.atualizar(EstadoSessao.EMBEDDINGS, 70.0, "embeddings_c3", "Projetando em base v1")
    from hemiciclo.modelos.embeddings import WrapperEmbeddings, embeddings_disponivel
    from hemiciclo.modelos.persistencia_modelo import carregar_modelo_base
    from hemiciclo.config import Configuracao
    cfg = Configuracao()
    if not embeddings_disponivel():
        logger.warning("Modelo bge-m3 não disponível -- camada C3 SKIPPED")
        return
    try:
        modelo_base = carregar_modelo_base(cfg.modelos_dir)
    except FileNotFoundError:
        logger.warning("Modelo base v1 não treinado -- camada C3 SKIPPED")
        return
    # ... carrega discursos do recorte, embed, transform, persiste
    ...


def _etapa_relatorio(
    params: ParametrosBusca, sessao_dir: Path, updater: StatusUpdater
) -> None:
    """Etapa 5: agrega resultado em relatorio_state.json + manifesto.json."""
    updater.atualizar(EstadoSessao.MODELANDO, 95.0, "relatorio", "Persistindo relatório")
    relatorio = _agregar_relatorio(params, sessao_dir)
    (sessao_dir / "relatorio_state.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifesto = _gerar_manifesto(sessao_dir)
    (sessao_dir / "manifesto.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _resolver_topico(topico: str) -> Path:
    """Resolve string `topico` em Path do YAML de tópico curado."""
    p = Path(topico)
    if p.exists() and p.suffix in (".yaml", ".yml"):
        return p
    # Tenta topicos/<slug>.yaml na raiz do repo
    repo_topico = Path.cwd() / "topicos" / f"{topico}.yaml"
    if repo_topico.exists():
        return repo_topico
    raise FileNotFoundError(f"Tópico YAML não encontrado: {topico}")


def _agregar_relatorio(params: ParametrosBusca, sessao_dir: Path) -> dict:
    ...

def _gerar_manifesto(sessao_dir: Path) -> dict:
    """Hashes SHA256 de cada artefato + lista limitacoes_conhecidas."""
    import hashlib
    artefatos = {}
    for p in sessao_dir.rglob("*"):
        if p.is_file() and p.suffix in (".parquet", ".duckdb", ".json"):
            sha = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
            artefatos[str(p.relative_to(sessao_dir))] = sha
    return {
        "criado_em": datetime.now(UTC).isoformat(),
        "artefatos": artefatos,
        "limitacoes_conhecidas": ["S24b", "S24c", "S25.3", "S27.1"],
        "versao_pipeline": "1",
    }
```

### 5.2 Passo a passo

1. Confirmar branch.
2. Implementar `sessao/pipeline.py` com 5 etapas mais helpers.
3. Re-exportar em `sessao/__init__.py`.
4. Atualizar CLI `sessao iniciar` (default `pipeline_real`, flag `--dummy`).
5. Atualizar `test_sentinela.py` com 2 sentinelas.
6. Escrever `tests/unit/test_pipeline_real.py` (8 testes mockados).
7. Escrever `tests/integracao/test_pipeline_e2e.py` (2 testes).
8. Escrever `docs/arquitetura/pipeline_integrado.md`.
9. Atualizar `CHANGELOG.md`.
10. Smoke local OPCIONAL: rodar `hemiciclo sessao iniciar --topico aborto --casas camara --max-itens 50`. Se rede ok, deve completar em ~1-2 min com sessão CONCLUIDA mas SKIPPED em C3 (modelo bge-m3 não baixado).
11. `make check` ≥ 90%.
12. Atualizar `sprints/ORDEM.md` mudando S30 para DONE.

## 6. Testes

- 8 unit (`test_pipeline_real.py`)
- 2 integração (`test_pipeline_e2e.py`)
- 2 sentinelas
- **Total: 12 testes novos** + 302 herdados = 314 testes

## 7. Proof-of-work runtime-real

```bash
$ make check
$ uv run hemiciclo sessao iniciar --topico aborto --dummy  # ainda funciona
$ sleep 3 && uv run hemiciclo sessao listar
# (uma sessão dummy CONCLUIDA)

$ uv run hemiciclo sessao iniciar --topico aborto --casas camara
# pipeline real, depende de rede; pode demorar minutos
```

**Critério de aceite:**

- [ ] `make check` 314 testes verdes, cobertura ≥ 90%
- [ ] `pipeline_real` é a default do `sessao iniciar`
- [ ] Flag `--dummy` ainda funciona (compat com S29)
- [ ] Pipeline reporta erro graceful em cada etapa
- [ ] `manifesto.json` lista hashes + limitações conhecidas
- [ ] Mypy/ruff zero
- [ ] CI verde nos 6 jobs

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Pipeline real depende de 5 subsistemas anteriores | Mocks agressivos em testes; smoke real opcional |
| API Câmara/Senado lenta degrada UX | StatusUpdater reporta tempo decorrido em cada etapa |
| Modelo base ausente quebra C3 | Skip graceful + warning, sessão continua sem C3 |
| Cache transversal corrompido entre sessões | Hash SHA256 valida integridade no carregamento (S26) |
| Pipeline travar em deadlock no subprocess | Timeout duro de 30min via signal alarm (Linux/macOS); Windows usa thread checker |

## 9. Validação multi-agente

Padrão. Validador atenção a: pipeline integra todos os subsistemas anteriores, mocks devem cobrir cada um sem rodar real.

## 10. Próximo passo após DONE

S31 (dashboard sessão real lendo `relatorio_state.json` + `manifesto.json`) -- maior valor visível ao usuário comum.
