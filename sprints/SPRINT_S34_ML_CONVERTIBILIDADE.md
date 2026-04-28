# Sprint S34 -- ML de convertibilidade (sklearn + features S32+S33)

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-28
**Status:** DONE (2026-04-28)
**Depende de:** S22 (DONE), S26 (DONE), S30 (DONE), S31 (DONE), S32 (DONE), S33 (DONE)
**Bloqueia:** S38
**Esforço:** G (1-2 semanas)
**ADRs vinculados:** ADR-004 (eixo convertibilidade da assinatura D4), ADR-018 (random_state fixo)
**Branch:** feature/s34-ml-convertibilidade

---

## 1. Objetivo

Implementar o **modelo de convertibilidade**: dado um parlamentar, prever a probabilidade de mudar de posição num tópico nas próximas N votações. Esta é a entrega do **eixo `convertibilidade`** da assinatura multidimensional (D4) e o ouro analítico do produto.

**Pipeline:**
1. Feature engineering sobre o que já existe:
   - `indice_volatilidade` (S33)
   - `centralidade_grau`, `centralidade_intermediacao` (S32 grafo voto)
   - `comunidade_voto` (S32)
   - `proporcao_sim_topico_atual` (C1+C2)
   - `n_votos_topico` (C1)
2. Target: usar mudanças do `DetectorMudancas` da S33 como label binário (`mudou_recentemente: 0/1`)
3. Modelo: scikit-learn `LogisticRegression` (interpretável)
4. Treino: split estratificado 70/30, `random_state=42`
5. Métricas: accuracy, precision, recall, F1, ROC-AUC
6. Output: ranking dos parlamentares por probabilidade prevista de conversão
7. Persistência: modelo via joblib (SHA256 + meta.json) + scores JSON

## 2. Contexto

S30 conecta tudo. S32 entrega features de rede. S33 entrega features temporais. S34 fecha o ciclo: usa esses features pra produzir o **score-chave do produto**.

**Caveats metodológicos honestos:**
- Amostra pequena (top 100 parlamentares mais ativos) limita generalização
- Target sintético "mudou >= 30pp" é proxy
- Modelo é correlacional, não causal -- relatório DEVE registrar isso
- Features podem vazar info do target (volatilidade já é feita de mudanças)

## 3. Escopo

### 3.1 In-scope

- [ ] **`src/hemiciclo/modelos/convertibilidade.py`**:
  - `class ExtratorFeatures`:
    - `extrair(conn, sessao_dir) -> pl.DataFrame`
    - Lê: `dados.duckdb` + `historico_conversao.json` + `metricas_rede.json`
    - Retorna DataFrame com (parlamentar_id, casa, features, target=mudou_recentemente)
    - Skip graceful: artefatos pré-requisito ausentes -> DataFrame vazio + aviso
  - `class ModeloConvertibilidade` (dataclass):
    - `treinar(X, y) -> ModeloConvertibilidade` (split 70/30 estratificado, `random_state=42`)
    - `prever_proba(X) -> pl.Series`
    - `salvar(path)` -> persiste via joblib + meta.json com SHA256
    - `carregar(path)` -> classmethod com validação integridade
    - `metricas: dict[str, float]` (accuracy, precision, recall, f1, roc_auc, n_treino, n_teste)
  - `class IntegridadeViolada(Exception)` (mesmo padrão da S28)
- [ ] **`src/hemiciclo/sessao/pipeline.py`** estendido:
  - Nova etapa `_etapa_convertibilidade` (95-98%) APÓS histórico (S33)
  - Só roda se `params.incluir_convertibilidade=True` (default False)
  - Skip graceful: features vazias / amostra < 30 -> SKIPPED
  - Persiste `convertibilidade_scores.json` com top 100
- [ ] **`src/hemiciclo/dashboard/widgets/ranking_convertibilidade.py`**:
  - `renderizar_ranking(scores, top_n=50) -> None`
  - Tabela Streamlit com barra de progresso amarela-ouro
  - Tooltip com coeficientes da regressão (interpretabilidade)
- [ ] **`src/hemiciclo/dashboard/paginas/sessao_detalhe.py`**:
  - Nova seção "Convertibilidade prevista (experimental)"
  - Banner explicando metodologia + caveats
- [ ] **CLI `hemiciclo convertibilidade`**:
  - `treinar <sessao_id> [--top-n 100]`
  - `prever <sessao_id>`
- [ ] **Testes unit** `tests/unit/test_modelos_convertibilidade.py` (10 testes):
  - extrator, sem histórico, sem grafo
  - treinar com random_state, prever em [0,1], métricas
  - salvar/carregar round trip + integridade violada
  - amostra mínima 30, coeficientes
- [ ] **Testes unit** `tests/unit/test_dashboard_widget_convertibilidade.py` (4 testes)
- [ ] **Testes integração** `tests/integracao/test_convertibilidade_e2e.py` (3 testes)
- [ ] **Sentinela** `test_sentinela.py`:
  - `test_convertibilidade_help`
- [ ] **`docs/arquitetura/convertibilidade.md`** com caveats explícitos
- [ ] **CHANGELOG.md** entrada `[Unreleased]`

### 3.2 Out-of-scope

- **SHAP values completos** -- usa coeficientes da regressão como proxy
- **Hyperparameter tuning** -- valores razoáveis fixos
- **Cross-validation k-fold** -- single split MVP
- **XGBoost/LightGBM** -- LogisticRegression cobre MVP
- **Página individual de explicação** -- sprint dedicada
- **Treino federado / online learning** -- futuro

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `src/hemiciclo/modelos/convertibilidade.py` | ExtratorFeatures + ModeloConvertibilidade |
| `src/hemiciclo/dashboard/widgets/ranking_convertibilidade.py` | Tabela ranqueada |
| `tests/unit/test_modelos_convertibilidade.py` | 10 testes |
| `tests/unit/test_dashboard_widget_convertibilidade.py` | 4 testes |
| `tests/integracao/test_convertibilidade_e2e.py` | 3 testes |
| `docs/arquitetura/convertibilidade.md` | Documentação metodológica |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `src/hemiciclo/sessao/pipeline.py` | Etapa `_etapa_convertibilidade` (95-98%) |
| `src/hemiciclo/dashboard/paginas/sessao_detalhe.py` | Nova seção |
| `src/hemiciclo/cli.py` | Subcomando `convertibilidade {treinar,prever}` |
| `tests/unit/test_sentinela.py` | Sentinela |
| `CHANGELOG.md` | Entrada [Unreleased] |
| `sprints/ORDEM.md` | S34 -> DONE |

## 5. Implementação detalhada

### 5.1 Padrão de persistência

Reusa precedente da S28 (modelo base): `joblib.dump(modelo, path)` + `meta.json` paralelo com `{versao, treinado_em, hash_sha256, metricas}`. Carregamento valida hash antes de desserializar (defesa contra adulteração). `IntegridadeViolada` raised se diferir.

### 5.2 ExtratorFeatures

Lê 3 artefatos JSON da sessão (`historico_conversao.json` da S33, `metricas_rede.json` da S32, `classificacao_c1_c2.json` da S27) + `dados.duckdb` se necessário. Constrói DataFrame Polars com features numéricas + target binário.

### 5.3 ModeloConvertibilidade

`@dataclass` com `LogisticRegression` (sklearn) + `feature_names` + `metricas`. Métodos:
- `treinar(X, y)` classmethod com split 70/30 estratificado
- `prever_proba(X) -> pl.Series` com probabilidade da classe positiva
- `salvar(path)` -> joblib + meta.json
- `carregar(path)` classmethod com validação SHA256
- Random state fixo em todos os pontos (split, classifier)

### 5.4 Passo a passo

1. Confirmar branch.
2. Implementar `modelos/convertibilidade.py`.
3. Escrever `test_modelos_convertibilidade.py` (10 testes).
4. Implementar widget `ranking_convertibilidade.py`.
5. Escrever `test_dashboard_widget_convertibilidade.py` (4 testes).
6. Atualizar `pipeline.py` com `_etapa_convertibilidade` em 95-98%.
7. Atualizar `sessao_detalhe.py`.
8. Adicionar subcomando `convertibilidade` em `cli.py`.
9. Adicionar sentinela.
10. Escrever `tests/integracao/test_convertibilidade_e2e.py`.
11. Escrever `docs/arquitetura/convertibilidade.md`.
12. Atualizar `CHANGELOG.md`.
13. Smoke local em `_seed_real` (gera fixture com votos suficientes).
14. `make check` ≥ 90%.
15. Atualizar ORDEM.md.

## 6. Testes

- 10 unit + 4 widget + 3 e2e + 1 sentinela = **18 testes novos**
- Total: 444 + 18 = 462 testes

## 7. Proof-of-work runtime-real

```bash
$ make check
$ uv run python scripts/seed_dashboard.py
$ uv run hemiciclo convertibilidade treinar _seed_real --top-n 50
[convertibilidade] amostra=50, accuracy=0.78, F1=0.65, ROC-AUC=0.81
[convertibilidade] modelo persistido + scores JSON
```

**Critério de aceite:**

- [ ] `make check` 462 testes verdes, cobertura ≥ 90%
- [ ] CLI `convertibilidade treinar` retorna exit 0 (mesmo SKIPPED)
- [ ] Modelo persistido com SHA256 validado
- [ ] Scores JSON com top N ranqueado
- [ ] `random_state=42` em todos os pontos
- [ ] Skip graceful: amostra < 30 / sem features
- [ ] Mypy/ruff zero, CI verde

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Amostra muito pequena bloqueia treino | Skip graceful + mensagem |
| ROC-AUC ruim | Documentar caveats; baseline MVP |
| Vazamento de features do target | Documentar honestamente; limitação MVP |
| sklearn version mismatch | Pinning + meta.json registra versão |

## 9. Validação multi-agente

Padrão. Validador atenção a I3 (random_state em 3 pontos), I9 (cobertura), e ao ML **real** (NÃO mockar features artificialmente -- usa `indice_volatilidade` real do `historico_conversao.json` + `centralidade` real do `metricas_rede.json`).

## 10. Próximo passo

S38 (higienização final + manifesto + demo gif + release v2.0.0).
