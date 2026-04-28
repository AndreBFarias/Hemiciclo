# Convertibilidade -- ML do eixo de conversão (S34)

> Eixo `convertibilidade` da assinatura multidimensional D4 (ADR-004).
> Modelo experimental, correlacional, não causal. Caveats explícitos
> documentados ao final.

## Objetivo

Dado um parlamentar, prever a probabilidade de mudar de posição num
tópico nas próximas N votações. Esta é a entrega analítica que junta
três sprints anteriores num único score utilizável pelo cidadão:

- `indice_volatilidade` (S33)
- `centralidade_grau` / `centralidade_intermediacao` (S32 grafo voto)
- `proporcao_sim_topico` / `n_votos_topico` (S27 C1+C2)

## Pipeline

1. **Feature engineering** -- `ExtratorFeatures.extrair(sessao_dir)` lê:
   - `historico_conversao.json` (S33)
   - `metricas_rede.json` (S32)
   - `classificacao_c1_c2.json` (S27)

   Devolve `polars.DataFrame` com 1 linha por parlamentar e o target
   binário `mudou_recentemente`.

2. **Target proxy** -- `mudou_recentemente = 1` se o parlamentar tem
   pelo menos 1 evento em `mudancas_detectadas` (S33), `0` caso contrário.
   Documentado como **proxy** -- não temos ground truth de "vai mudar
   na próxima votação", então usamos o passado como aproximação.

3. **Modelo** -- `LogisticRegression` do scikit-learn, intencionalmente
   simples para máxima interpretabilidade. Coeficientes da regressão
   servem como proxy de SHAP (sem custo de SHAP completo).

4. **Treino** -- split 70/30 estratificado, `random_state=42` em três
   pontos:
   - `train_test_split(..., random_state=42)`
   - `LogisticRegression(random_state=42)`
   - solver `lbfgs` determinístico

5. **Métricas** -- accuracy, precision, recall, F1 (`zero_division=0`),
   ROC-AUC (defesa: só calcula se `y_te` tem 2 classes; senão 0.0).

6. **Persistência** -- `joblib.dump(classifier)` + `meta.json` paralelo
   contendo `versao`, `treinado_em`, `hash_sha256`, `feature_names`,
   `metricas`, `coeficientes`. `IntegridadeViolada` no carregamento se
   hash divergir ou versão for incompatível (precedente S28).

7. **Saída** -- top N parlamentares ranqueados por probabilidade
   prevista, em `<sessao_dir>/convertibilidade_scores.json`. Modelo
   binário em `<sessao_dir>/modelo_convertibilidade/`.

## Skip graceful rigoroso

Em todos os caminhos abaixo o pipeline continua até `CONCLUIDA` --
nunca é erro fatal. O dashboard mostra mensagem clara e segue:

| Condição | Resultado |
|---|---|
| `historico_conversao.json` ausente / vazio | DataFrame vazio + JSON `skipped=true` |
| Amostra < 30 parlamentares | JSON `skipped=true` com motivo "amostra insuficiente: N < 30 (recomenda-se coleta com mais parlamentares)" |
| Apenas 1 classe presente em `y` | `AmostraInsuficiente` (split estratificado impossível) -> capturada no helper -> JSON `skipped=true` |
| Erro inesperado dentro de `treinar_convertibilidade_sessao` | `try/except` no pipeline -> JSON `skipped=true` com `motivo="erro: <classe>: <msg>"` |

## Caveats metodológicos honestos

Este é o ponto onde o projeto se separa da maioria das ferramentas de
ML aplicado. O manifesto político do Hemiciclo exige rigor metodológico
publicizado, sem maquiagem:

1. **Amostra pequena (top 100)**. O modelo é treinado nos parlamentares
   mais ativos da sessão. Generalização limitada para parlamentares
   com poucos votos. Recomendação: futuras sprints podem ampliar a
   janela temporal e a base de treino.

2. **Target sintético é proxy**. Não temos ground truth de "vai mudar
   no futuro próximo". Usamos `mudou_recentemente` (passado) como
   aproximação. O modelo aprende a identificar parlamentares cujo
   passado parece com o passado de quem mudou -- não promete nada
   sobre o futuro.

3. **Vazamento parcial de target**. `indice_volatilidade` é construído
   por cima das mesmas mudanças que definem o target. O modelo
   "trapaceia" parcialmente. Aceito como limite MVP -- v2 deveria ter
   feature engineering com janela temporal estrita (ex: só mudanças
   antes de uma data de corte).

4. **Correlacional, não causal**. ROC-AUC mede capacidade de ranquear,
   não interpretação causal. Não dizemos "porque é volátil, vai mudar"
   -- dizemos "parlamentares com este perfil já mudaram no passado".

5. **Hyperparameter tuning ausente**. LogisticRegression com `max_iter=1000`,
   `solver='lbfgs'`, sem regularização customizada. Decisão consciente:
   privilegiar interpretabilidade do MVP. Sprint dedicada pode explorar
   XGBoost/LightGBM se a equipe entender que vale o custo de
   interpretabilidade reduzida.

6. **Single-split, sem cross-validation**. Métricas reportadas vêm de
   um único split 70/30. Variância de amostragem não é capturada.
   K-fold em sprint futura.

## Como ler o ranking no dashboard

A seção "Convertibilidade prevista (experimental)" lista os top 50
parlamentares ranqueados por probabilidade prevista. Duas barras de
progresso:

- **Probabilidade de conversão**: saída direta do `predict_proba`.
  Valores próximos de 1.0 indicam parlamentares cujo perfil casa com
  o de quem historicamente mudou.
- **Volatilidade histórica**: feature de input (S33). Útil pra
  contextualizar.

A expansível "Coeficientes da regressão" mostra o peso de cada feature
no log-odds. Positivo = aumenta probabilidade prevista; negativo =
diminui. Use isso pra entender qual sinal o modelo está aprendendo.

## CLI

```bash
hemiciclo convertibilidade treinar <id_sessao> [--top-n 100]
hemiciclo convertibilidade prever <id_sessao>
```

`treinar` extrai features, treina, persiste e ranqueia. Idempotente --
re-rodar sobrescreve modelo e scores.

`prever` recarrega modelo já treinado (validando SHA256) e regenera
apenas os scores. Útil pra ranquear com `top_n` diferente sem refazer
o treino.

## ADRs vinculados

- ADR-004 (D4 -- assinatura indutiva multidimensional)
- ADR-018 (random_state fixo em todos os modelos)

## Arquivos relevantes

- `src/hemiciclo/modelos/convertibilidade.py` -- ExtratorFeatures +
  ModeloConvertibilidade + helper end-to-end.
- `src/hemiciclo/dashboard/widgets/ranking_convertibilidade.py` -- widget
  Streamlit.
- `src/hemiciclo/sessao/pipeline.py::_etapa_convertibilidade` -- 95--98%.
- `src/hemiciclo/cli.py` -- subcomandos `treinar` e `prever`.
- `tests/unit/test_modelos_convertibilidade.py` -- 22 testes unit.
- `tests/unit/test_dashboard_widget_convertibilidade.py` -- 4 testes.
- `tests/integracao/test_convertibilidade_e2e.py` -- 3 testes E2E.
