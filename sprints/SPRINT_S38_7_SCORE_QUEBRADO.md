# Sprint S38.7 -- Corrigir score 1% nas tabelas Top a-favor / Top contra

**Projeto:** Hemiciclo
**Versão alvo:** v2.1.1
**Status:** DONE (2026-04-28)
**Esforço:** P (1h, fix dirigido + teste + smoke)
**Branch:** feature/s38-7-score-quebrado
**Depende de:** --
**Prioridade:** P0 -- bug funcional visível pós-v2.1.0

---

## 1. Objetivo

Corrigir renderização do `Score` em `top_pro_contra.py` (página `sessao_detalhe`). Atualmente todos os parlamentares aparecem com **1% no a-favor** e **0% no contra**, independente da posição real. Score quebrado invalida toda a leitura do relatório.

## 2. Contexto

Smoke real do browser pós v2.1.0 (sessão `_seed_concluida` de `seed_dashboard.py`):

**Top a-favor:** Sâmia, Talíria, Erika, Maria do Rosário, Benedita, Ivan, Glauber, Jandira -- todos com `1%`.
**Top contra:** todos com `0%`.

Comportamento esperado: parlamentares com 100% de SIM no tópico → 100%; com 100% de NÃO → 0% (e ficam em "contra").

## 3. Investigação realizada (planejador, 2026-04-28)

### 3.1 Schema do JSON (confirmado)

```bash
jq '.top_a_favor[0:3]' ~/hemiciclo/sessoes/_seed_concluida/classificacao_c1_c2.json
```

Saída real:
```json
[
  {"id":1001,"nome":"Sâmia Bomfim","partido":"PSOL","uf":"SP","proporcao_sim":0.9928,"posicao":0.9928,"intensidade":0.3138},
  {"id":1002,"nome":"Talíria Petrone","partido":"PSOL","uf":"RJ","proporcao_sim":0.9655,"posicao":0.9655,"intensidade":0.4228},
  {"id":1003,"nome":"Erika Hilton","partido":"PSOL","uf":"SP","proporcao_sim":0.9547,"posicao":0.9547,"intensidade":0.6722}
]
```

`top_contra[0]` (Eros Biondini): `proporcao_sim: 0.0528`. **Os dados estão corretos.**

### 3.2 Seed (confirmado limpo)

`scripts/seed_dashboard.py` linhas 65-72: gera scores plausíveis em `[0,1]` com jitter -- não é mock travado em 0.01. **Hipótese 1 do spec original refutada.**

### 3.3 Widget (causa raiz)

`src/hemiciclo/dashboard/widgets/top_pro_contra.py` linha 27:
```python
"Score": float(parl.get("proporcao_sim", parl.get("score", 0.0)) or 0.0),
```
Valor lido: `0.9928` (proporção em `[0,1]`). Correto.

Linhas 55-61 -- a falha:
```python
"Score": st.column_config.ProgressColumn(
    "Score",
    help="Proporção de votos sim no tópico (0-100%).",
    min_value=0.0,
    max_value=1.0,
    format="%.0f%%",
),
```

**Streamlit `ProgressColumn` com `format="%.0f%%"` aplica `printf` ao valor cru.** `"%.0f%%" % 0.9928` → `"1%"`. `"%.0f%%" % 0.0528` → `"0%"`. Bate exatamente com o smoke. A barra horizontal pode até estar correta (usa `min/max`), mas o texto exibido formata sem multiplicar por 100.

### 3.4 Hipótese 3 (`agregar_voto_por_parlamentar`) refutada

Não chegamos a inspecionar `classificador_c1.py` porque o JSON gerado tem valores corretos (Sâmia 0.9928, Eros 0.0528). Bug está estritamente na camada de renderização.

## 4. Causa raiz (confirmada)

`format="%.0f%%"` em `ProgressColumn` formata o valor `[0,1]` literalmente. Para exibir percentual a partir de proporção, ou:
- (a) escalar valor para `[0,100]` no `_normalizar_linha` e usar `min_value=0, max_value=100, format="%.0f%%"`, ou
- (b) manter valor em `[0,1]` e usar `format="percent"` (preset Streamlit que multiplica por 100), ou
- (c) usar `format="%.0f%%"` com valor já em `[0,100]` (preferido por consistência com `ranking_convertibilidade.py` que usa `format="%.2f"` em `[0,1]`).

**Recomendação:** opção (a) -- escalar `proporcao_sim * 100` em `_normalizar_linha`, ajustar `min_value=0.0, max_value=100.0, format="%.0f%%"`. Mantém intenção visual e elimina ambiguidade.

## 5. Escopo

### 5.1 Touches autorizados

- **Modificar:**
  - `src/hemiciclo/dashboard/widgets/top_pro_contra.py` (linhas 20-28 e 55-62)
  - `tests/unit/test_dashboard_widgets.py` (adicionar caso que valida escala `[0,100]`)
- **NÃO tocar:**
  - `scripts/seed_dashboard.py` (dados corretos)
  - `src/hemiciclo/modelos/classificador_c1.py` (agregação correta)
  - JSONs em `~/hemiciclo/sessoes/_seed_concluida/` (já corretos)

### 5.2 Out-of-scope

- Refatorar agregação de voto (escopo S27/S30).
- Cor verde-folha das barras (escopo S38.5).
- Adicionar coluna de % abstenção / votos absolutos.

## 6. Plano de implementação

1. Editar `_normalizar_linha`: multiplicar `proporcao_sim` por `100.0` ao construir campo `Score`.
2. Editar `_renderizar_tabela`: ajustar `column_config.ProgressColumn` para `min_value=0.0, max_value=100.0`.
3. Atualizar docstring linha 4-9 explicitando a escala `[0,100]`.
4. Adicionar teste unit `test_top_pro_contra_score_escalado_para_percentual` em `tests/unit/test_dashboard_widgets.py` que invoca `_normalizar_linha({"nome": "X", "proporcao_sim": 0.9928})` e asserta `linha["Score"] == pytest.approx(99.28)`.
5. Rodar smoke real (ver §8).

## 7. Critérios de aceite (verificáveis programaticamente)

- [ ] `_normalizar_linha({"proporcao_sim": 0.9928})["Score"] == pytest.approx(99.28, abs=0.01)`
- [ ] `_normalizar_linha({"proporcao_sim": 0.0528})["Score"] == pytest.approx(5.28, abs=0.01)`
- [ ] `_normalizar_linha({})["Score"] == 0.0` (default seguro)
- [ ] Smoke real do browser: scores no top a-favor entre 70-99%, top contra entre 1-30%
- [ ] Suite verde com `make check`, cobertura `>= 90%` no arquivo modificado
- [ ] PNG validado pela skill `validacao-visual` mostrando barras com texto `"99%"`, `"96%"`, etc.

## 8. Proof-of-work

```bash
# Unit
uv run pytest tests/unit/test_dashboard_widgets.py -v -k "top_pro_contra"

# Suite + cobertura
make check

# Smoke real obrigatório (lição feedback_smoke_real_browser_obrigatorio.md)
make run
# Abrir http://localhost:8501, clicar em sessão _seed_concluida,
# capturar PNG da tabela Top a-favor e Top contra,
# rodar skill validacao-visual passando o PNG.

# Hipótese verificada (lição 4): rg confirma identificadores citados
rg "_normalizar_linha|ProgressColumn|proporcao_sim" src/hemiciclo/dashboard/widgets/top_pro_contra.py
```

## 9. Invariantes a preservar

- I2 (PT-BR sem perda) -- nenhum texto alterado, apenas escala numérica.
- I4 (sem prints) -- não introduzir.
- I7 (mypy strict) -- assinatura de `_normalizar_linha` permanece `dict[str, Any]`.
- I8 (ruff zero) -- formatar com `uv run ruff format`.
- I9 (cobertura >= 90%) -- novo teste mantém.
- Conformidade com padrão de `ranking_convertibilidade.py` -- aceitável diferença porque aqui usamos formato percentual textual; documentar no docstring.

## 10. Time-box e cláusula de escalada

**Time-box: 1h.** Como a investigação do planejador já confirmou causa raiz na renderização (não na agregação), o fix é mecânico. Se durante execução o teste unit reproduzir bug fora do widget (ex.: JSON real do pipeline tem `proporcao_sim` em `[0,100]` em vez de `[0,1]`), abrir **S38.7-r** e fechar S38.7 sem mexer em escopo maior.

## 11. Referências

- BRIEF: `/home/andrefarias/Desenvolvimento/Hemiciclo/VALIDATOR_BRIEF.md`
- Memória: `feedback_smoke_real_browser_obrigatorio.md`
- Sprint relacionada: S38.5 (cor das barras)
- Padrão de widget: `src/hemiciclo/dashboard/widgets/ranking_convertibilidade.py`
