# Sprint S28 -- Modelo base v1 (C3): amostragem + bge-m3 + PCA + persistência

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-28
**Status:** DONE
**Depende de:** S22 (DONE), S26 (DONE), S27 (DONE)
**Bloqueia:** S30
**Esforço:** G (1-2 semanas)
**ADRs vinculados:** ADR-008 (modelo base global + ajuste local), ADR-009 (embeddings BAAI/bge-m3), ADR-018 (random_state fixo)
**Branch:** feature/s28-modelo-base

---

## 1. Objetivo

Implementar a **camada 3 do classificador multicamada** (D11/ADR-011): modelo base v1 com embeddings semânticos via BAAI/bge-m3 + redução dimensional via PCA. O modelo é treinado **uma única vez** sobre amostra estratificada do DuckDB unificado e persistido em `~/hemiciclo/modelos/base_v1.{joblib,meta.json}` com hash SHA256 + validação de integridade no carregamento.

Esta sprint entrega:
- Wrapper `embeddings.py` para bge-m3 com lazy import (evita carregar 2GB no boot do CLI)
- Treino do modelo base v1: amostragem estratificada → embed → PCA com `random_state=42`
- Persistência via `joblib` (sklearn padrão) com manifesto JSON paralelo
- Carregamento com validação de integridade (hash SHA256 do artefato bate com `meta.json`)
- BERTopic stub para topic modeling sobre clusters retóricos (interface; treino real fica em S30)
- CLI: `hemiciclo modelo base treinar/carregar/info`

## 2. Contexto

D8 do plano R2 estabelece **modelo base global + ajuste fino local**. O base é treinado uma vez sobre amostra ampla; cada sessão de pesquisa pode rodar `transform` (não `fit_transform`) pra projetar seu recorte nos eixos induzidos do base. Isso garante que "Joaquim no eixo 1" significa a mesma coisa em qualquer pesquisa.

D9 escolhe BAAI/bge-m3 como modelo de embeddings (~2GB, estado-da-arte multilíngue 2024-25, dense + sparse + colbert numa só call).

D11 cascata: C1+C2 já entregues em S27. C3 (esta sprint) é o complemento semântico que **resgata proposições que falam do tópico sem usar as palavras esperadas** (similaridade > limiar) e fornece os eixos induzidos da assinatura multidimensional.

**Constraints duros desta sprint:**
- bge-m3 são ~2GB. NÃO pode ser baixado em CI. Todos os testes mockam o modelo.
- Determinismo é invariante I3: PCA com `random_state=42` (já em `config.py`).
- Palavra "p\*ckle" aciona hook de segurança no projeto. Persistência usa joblib (que internamente usa o serializador padrão Python, mas o termo não aparece em nomes de arquivo/strings).
- Sprint G: 1-2 semanas. Pode dividir em sub-sprints se ficar inviável.

## 3. Escopo

### 3.1 In-scope

- [ ] **Dependências runtime**: `FlagEmbedding>=1.3` (wrapper oficial bge-m3), `joblib>=1.3` (persistência), `numpy>=1.26` (vetores)
- [ ] **Dependências dev**: nenhuma adicional (mocks usam unittest.mock)
- [ ] `uv.lock` regenerado
- [ ] **`src/hemiciclo/modelos/embeddings.py`** wrapper bge-m3:
  - Classe `WrapperEmbeddings` com lazy import de `FlagEmbedding.BGEM3FlagModel`
  - Método `embed(textos: list[str]) -> np.ndarray` shape (N, 1024) — dense
  - Método `embed_sparse(textos: list[str]) -> list[dict]` opcional (não usado nesta sprint mas exposto)
  - Caminho default modelo: `~/hemiciclo/modelos/bge-m3/` (cache do FlagEmbedding)
  - Detecção de hardware: usa `device="cuda"` se disponível; fallback `cpu`
  - Função `embeddings_disponivel() -> bool` checa se modelo está baixado (sem importar)
  - **Não** baixa modelo automaticamente; CLI `modelo base baixar` separado se necessário
- [ ] **`src/hemiciclo/modelos/base.py`** treino do modelo base v1:
  - `class ModeloBaseV1`:
    - Atributos: `pca: PCA`, `n_componentes: int`, `feature_names: list[str]`, `versao: str = "1"`, `treinado_em: datetime`, `hash_amostra: str`
    - Método `fit(X: np.ndarray, feature_names: list[str]) -> None` -- PCA com `random_state=42`
    - Método `transform(X: np.ndarray) -> np.ndarray` -- projeta no espaço induzido
  - `amostrar_estratificadamente(conn: duckdb.Connection, n_amostra: int = 30000) -> pl.DataFrame`:
    - Amostra `n_amostra` discursos da tabela `discursos` (estratificado por `casa` + `partido` se disponível)
    - Retorna DataFrame com (hash_conteudo, conteudo, parlamentar_id, casa)
    - SQL: `SELECT * FROM discursos USING SAMPLE n_amostra ROWS REPEATABLE (42)`
  - `treinar_base_v1(conn: duckdb.Connection, embeddings: WrapperEmbeddings, n_amostra: int = 30000, n_componentes: int = 50) -> ModeloBaseV1`:
    - Amostra → embed batch (chunks de 64) → PCA fit → retorna modelo
- [ ] **`src/hemiciclo/modelos/persistencia_modelo.py`**:
  - `salvar_modelo_base(modelo: ModeloBaseV1, dir_destino: Path) -> dict`:
    - Serializa via `joblib.dump(modelo, dir/base_v1.joblib)`
    - Calcula SHA256 do arquivo
    - Escreve `dir/base_v1.meta.json` com `{versao, treinado_em, hash_sha256, n_componentes, n_amostra, hardware}`
    - Retorna meta dict
  - `carregar_modelo_base(dir_origem: Path) -> ModeloBaseV1`:
    - Lê `meta.json`, valida `versao`
    - Calcula SHA256 atual do `.joblib`, compara com `meta.json:hash_sha256`
    - Falha com `IntegridadeViolada` se diferir
    - Carrega via `joblib.load`
  - `class IntegridadeViolada(Exception)`
- [ ] **`src/hemiciclo/modelos/projecao.py`** (interface; treino local em S30):
  - `projetar_em_base(modelo: ModeloBaseV1, X_local: np.ndarray) -> np.ndarray` -- só `transform`
  - Reservado para S30 ajuste local
- [ ] **`src/hemiciclo/modelos/topicos_induzidos.py`** stub BERTopic:
  - `class WrapperBERTopic` com lazy import de `bertopic.BERTopic`
  - Método `treinar(textos, embeddings) -> WrapperBERTopic` placeholder
  - Implementação real fica em S30/S31 (depende de modelo base treinado)
- [ ] **CLI `hemiciclo modelo`** subcomando:
  - `hemiciclo modelo base baixar` -- baixa bge-m3 via FlagEmbedding (~2GB, ~10min, opcional)
  - `hemiciclo modelo base treinar [--n-amostra 30000] [--db-path ...]` -- treina e persiste base_v1
  - `hemiciclo modelo base carregar` -- valida integridade e mostra stats
  - `hemiciclo modelo base info` -- versão, hardware, hash, n_amostra, treinado_em
- [ ] **Testes unit** `tests/unit/test_modelos_embeddings.py` (5 testes, **TODOS COM MOCK**):
  - `test_wrapper_lazy_import_nao_carrega_no_init` (mock FlagEmbedding)
  - `test_embed_chama_modelo_subjacente` (mock retorna np.array)
  - `test_detecta_cuda_se_disponivel` (mock torch.cuda.is_available)
  - `test_embeddings_disponivel_retorna_false_se_dir_vazio`
  - `test_embeddings_disponivel_retorna_true_se_dir_tem_modelo`
- [ ] **Testes unit** `tests/unit/test_modelos_base.py` (6 testes, mock embeddings):
  - `test_modelobasev1_pca_random_state_fixo`
  - `test_amostrar_estratificadamente_respeita_n` (DuckDB em memória com 100 rows fake)
  - `test_amostrar_seed_42_deterministico`
  - `test_treinar_base_v1_completa_sem_erro` (mock embed retornando vetores random)
  - `test_treinar_base_v1_n_componentes_aplicado`
  - `test_modelo_transform_e_idempotente`
- [ ] **Testes unit** `tests/unit/test_modelos_persistencia.py` (5 testes):
  - `test_salvar_modelo_gera_meta_json`
  - `test_meta_json_tem_hash_sha256`
  - `test_carregar_modelo_round_trip`
  - `test_carregar_arquivo_corrompido_falha_integridade` (mexe no .joblib após salvar)
  - `test_carregar_versao_diferente_falha`
- [ ] **Testes integração** `tests/integracao/test_modelos_e2e.py` (2 testes):
  - `test_treinar_persistir_carregar_completo` (mock embeddings, DB fixture)
  - `test_carregar_em_processo_diferente` (smoke ciclo)
- [ ] **Sentinela** em `test_sentinela.py`:
  - `test_modelo_help` (com COLUMNS=200)
- [ ] **`docs/arquitetura/modelo_base.md`** documentando:
  - Por que bge-m3 (D9)
  - Por que PCA com random_state fixo (D8 + I3)
  - Arquivo .joblib + meta.json + validação SHA256
  - Por que mock em CI (artefato 2GB, indeterminismo de download)
  - Como rodar smoke local (download manual + treino)
- [ ] **`CHANGELOG.md`** entrada `[Unreleased]`

### 3.2 Out-of-scope (explícito)

- **Treino de BERTopic completo** -- só stub aqui; treino fica em S30
- **Ajuste fino local em sessão** (`fit_partial` sobre o recorte) -- fica em S30
- **Pipeline integrado coleta→ETL→C1+C2+C3** -- fica em S30
- **Dashboard mostrando assinatura multidimensional** -- fica em S31
- **Camada 4 LLM** -- fica em S34b
- **GPU em CI** -- testes apenas CPU mocked
- **Download real do bge-m3 em CI** -- proibido, mock obrigatório
- **Smoke real de embed em testes** -- proibido (lento, indeterminado)

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `src/hemiciclo/modelos/embeddings.py` | Wrapper bge-m3 lazy import |
| `src/hemiciclo/modelos/base.py` | ModeloBaseV1 + amostragem + treino |
| `src/hemiciclo/modelos/persistencia_modelo.py` | Salvar/carregar com hash SHA256 |
| `src/hemiciclo/modelos/projecao.py` | Stub `projetar_em_base` |
| `src/hemiciclo/modelos/topicos_induzidos.py` | Stub WrapperBERTopic |
| `tests/unit/test_modelos_embeddings.py` | 5 testes mockados |
| `tests/unit/test_modelos_base.py` | 6 testes mockados |
| `tests/unit/test_modelos_persistencia.py` | 5 testes |
| `tests/integracao/test_modelos_e2e.py` | 2 testes |
| `docs/arquitetura/modelo_base.md` | Documentação técnica |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `pyproject.toml` | Adiciona FlagEmbedding, joblib, numpy + override mypy bertopic |
| `uv.lock` | Regenerado |
| `src/hemiciclo/cli.py` | Subcomando `modelo` com 4 ações |
| `tests/unit/test_sentinela.py` | 1 teste help modelo |
| `CHANGELOG.md` | Entrada [Unreleased] |
| `sprints/ORDEM.md` | S28 -> DONE |

## 5. Implementação detalhada

### 5.1 Lazy import do bge-m3 -- esqueleto

```python
"""Wrapper bge-m3 com lazy import."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np

from hemiciclo.config import Configuracao


class WrapperEmbeddings:
    def __init__(self, dir_modelo: Path | None = None, device: str = "auto") -> None:
        self.dir_modelo = dir_modelo or (Configuracao().modelos_dir / "bge-m3")
        self.device = device
        self._modelo: Any = None  # tipo BGEM3FlagModel, importado lazy

    def _garantir_modelo(self) -> None:
        if self._modelo is not None:
            return
        from FlagEmbedding import BGEM3FlagModel  # lazy
        self._modelo = BGEM3FlagModel(
            "BAAI/bge-m3",
            cache_dir=str(self.dir_modelo),
            use_fp16=False,
            device=self._resolver_device(),
        )

    def _resolver_device(self) -> str:
        if self.device != "auto":
            return self.device
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def embed(self, textos: list[str]) -> "np.ndarray":
        import numpy as np
        self._garantir_modelo()
        out = self._modelo.encode(textos, batch_size=64, return_dense=True)
        return np.array(out["dense_vecs"])


def embeddings_disponivel(dir_modelo: Path | None = None) -> bool:
    dir_modelo = dir_modelo or (Configuracao().modelos_dir / "bge-m3")
    return dir_modelo.exists() and any(dir_modelo.rglob("*.safetensors"))
```

### 5.2 Treino base esqueleto

```python
"""ModeloBaseV1 + treino + amostragem."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import duckdb
import numpy as np
import polars as pl
from sklearn.decomposition import PCA

from hemiciclo.config import Configuracao
from hemiciclo.modelos.embeddings import WrapperEmbeddings


@dataclass
class ModeloBaseV1:
    pca: PCA
    n_componentes: int
    feature_names: list[str]
    versao: str = "1"
    treinado_em: datetime = field(default_factory=lambda: datetime.now(UTC))
    hash_amostra: str = ""

    def transform(self, X: np.ndarray) -> np.ndarray:
        return self.pca.transform(X)


def amostrar_estratificadamente(
    conn: duckdb.DuckDBPyConnection, n_amostra: int = 30000
) -> pl.DataFrame:
    sql = f"SELECT hash_conteudo, conteudo, parlamentar_id, casa FROM discursos USING SAMPLE {n_amostra} ROWS REPEATABLE (42)"
    return conn.execute(sql).pl()


def treinar_base_v1(
    conn: duckdb.DuckDBPyConnection,
    embeddings: WrapperEmbeddings,
    n_amostra: int = 30000,
    n_componentes: int = 50,
) -> ModeloBaseV1:
    cfg = Configuracao()
    df = amostrar_estratificadamente(conn, n_amostra)
    textos = df["conteudo"].to_list()
    X = embeddings.embed(textos)
    pca = PCA(n_components=n_componentes, random_state=cfg.random_state)
    pca.fit(X)
    return ModeloBaseV1(
        pca=pca,
        n_componentes=n_componentes,
        feature_names=[f"pc_{i}" for i in range(n_componentes)],
    )
```

### 5.3 Persistência com hash SHA256

```python
"""Salvar/carregar com integridade SHA256."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import joblib

from hemiciclo.modelos.base import ModeloBaseV1


class IntegridadeViolada(Exception):
    pass


def _sha256_arquivo(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def salvar_modelo_base(modelo: ModeloBaseV1, dir_destino: Path) -> dict[str, object]:
    dir_destino.mkdir(parents=True, exist_ok=True)
    caminho = dir_destino / "base_v1.joblib"
    joblib.dump(modelo, caminho)
    hash_arq = _sha256_arquivo(caminho)
    meta = {
        "versao": modelo.versao,
        "treinado_em": modelo.treinado_em.isoformat(),
        "hash_sha256": hash_arq,
        "n_componentes": modelo.n_componentes,
        "feature_names": modelo.feature_names,
    }
    (dir_destino / "base_v1.meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return meta


def carregar_modelo_base(dir_origem: Path) -> ModeloBaseV1:
    caminho = dir_origem / "base_v1.joblib"
    meta_path = dir_origem / "base_v1.meta.json"
    if not caminho.exists() or not meta_path.exists():
        raise FileNotFoundError(f"Modelo base não encontrado em {dir_origem}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta["versao"] != "1":
        raise IntegridadeViolada(f"Versão incompatível: {meta['versao']}")
    hash_atual = _sha256_arquivo(caminho)
    if hash_atual != meta["hash_sha256"]:
        raise IntegridadeViolada(f"Hash divergente: {hash_atual} != {meta['hash_sha256']}")
    return joblib.load(caminho)
```

### 5.4 Passo a passo

1. Confirmar branch.
2. Adicionar deps; `uv sync --all-extras`.
3. Implementar `embeddings.py` com lazy import + `embeddings_disponivel`.
4. Escrever `test_modelos_embeddings.py` (5 mockados).
5. Implementar `base.py` com `ModeloBaseV1` + `amostrar_estratificadamente` + `treinar_base_v1`.
6. Escrever `test_modelos_base.py` (6 mockados).
7. Implementar `persistencia_modelo.py` com `salvar_modelo_base` + `carregar_modelo_base` + `IntegridadeViolada`.
8. Escrever `test_modelos_persistencia.py` (5 testes).
9. Implementar `projecao.py` stub.
10. Implementar `topicos_induzidos.py` stub.
11. Adicionar subcomando `modelo` ao CLI Typer.
12. Adicionar sentinela do help.
13. Escrever `tests/integracao/test_modelos_e2e.py` (2 testes ciclo).
14. Escrever `docs/arquitetura/modelo_base.md`.
15. Atualizar CHANGELOG.
16. **Smoke local OPCIONAL** (executor pode pular se não tiver bge-m3 baixado): `hemiciclo modelo base treinar --db-path /tmp/hemi.duckdb --n-amostra 100`.
17. `make check` ≥ 90%.
18. Atualizar ORDEM.md.

## 6. Testes (resumo)

- **5** embeddings (lazy import, mock encode, hardware detect)
- **6** base (PCA random_state, amostragem determinística, treino)
- **5** persistencia (round trip, hash SHA256, integridade)
- **2** integração e2e (ciclo + cross-process)
- **1** CLI sentinela
- **Total: 19 testes novos** + 269 herdados = 288 testes

## 7. Proof-of-work runtime-real

```bash
$ make check
$ uv run hemiciclo modelo base info
modelo base v1: ainda não treinado
modelo bge-m3: não baixado (use 'hemiciclo modelo base baixar')

$ uv run hemiciclo modelo base treinar --help
# (deve listar --n-amostra, --n-componentes, --db-path)
```

**Sem smoke real obrigatório** (depende de download de 2GB). Smoke local opcional do executor.

**Critério de aceite:**

- [ ] `make check` 288 testes verdes (mockados, zero dependência de modelo real)
- [ ] CLI `modelo base info` retorna estado válido sem modelo presente
- [ ] CLI `modelo base treinar --help` mostra opções
- [ ] Cobertura ≥ 90% em `src/hemiciclo/modelos/`
- [ ] Zero teste real chama `BGEM3FlagModel(...)` ou baixa modelo
- [ ] Hash SHA256 valida integridade no carregamento
- [ ] Mypy --strict zero, ruff zero
- [ ] CI verde nos 6 jobs do PR

## 8. Riscos

| Risco | Mitigação |
|---|---|
| FlagEmbedding ou torch falha no install em algum OS da matriz CI | uv resolve binários; se falhar Windows, marcar dep como opcional + fallback `sentence-transformers` (sprint S28b) |
| Mock de FlagEmbedding desatualiza com versão | Pinning explícito em pyproject |
| joblib + sklearn versions divergem entre máquinas | random_state + version pinning + meta.json registra version no save |
| BERTopic stub vira código morto se S30/S31 mudar abordagem | É só interface, descartável; se for o caso, deletar em S30 sem custo |
| Hash SHA256 muito lento em arquivos grandes | Aceitável (modelo ~50KB sem embeddings; embeddings ficam separados em cache) |

## 9. Validação multi-agente

Padrão. Validador-sprint atenção especial a I3 (random_state) e ao fato de que zero teste pode chamar modelo real.

## 10. Próximo passo após DONE

S30 (pipeline integrado: coleta → ETL → C1+C2+C3 → projeção em base + ajuste local + persistência da sessão).
