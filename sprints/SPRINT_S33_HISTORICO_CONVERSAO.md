# Sprint S33 -- Histórico de conversão por parlamentar x tópico

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-28
**Status:** DONE (2026-04-28)
**Depende de:** S22 (DONE), S26 (DONE), S27 (DONE), S30 (DONE), S31 (DONE)
**Bloqueia:** S34, S38
**Esforço:** M (3-5 dias)
**ADRs vinculados:** ADR-004 (assinatura multidimensional -- eixo volatilidade)
**Branch:** feature/s33-historico-conversao

---

## 1. Objetivo

Implementar **histórico temporal de posição** por parlamentar × tópico. Para cada parlamentar com dados em N legislaturas/anos, calcular trajetória da `proporcao_sim` ao longo do tempo, detectar **mudanças de posição** (deltas significativos), e renderizar timeline interativa via Plotly no dashboard.

Esta é a entrega do **eixo `volatilidade`** da assinatura multidimensional (D4) e fornece input chave pra S34 (ML de convertibilidade).

Exemplo de saída: "Joaquim votou 80% SIM em PLs de aborto em 2018, 20% SIM em 2024 — mudança de -60pp = ALTA volatilidade."

## 2. Contexto

S30 já entrega `dados.duckdb` com tabelas `votos`, `votacoes` por sessão. S27 entrega C1 (votos agregados). S32 entrega análise de redes.

S33 adiciona **dimensão temporal**: agrupa votos por (parlamentar_id, ano OU legislatura), calcula proporção SIM por bucket, detecta deltas. Saída persistida em `<sessao_dir>/historico_conversao.json` + visualizada via Plotly line chart no `sessao_detalhe.py`.

**Limitações herdadas (S27.1):** sem `votacoes.proposicao_id`, é impossível filtrar histórico só pelos PLs do tópico atual. Solução pragmática: histórico geral do parlamentar (todas as votações) + nota explicando que recall específico do tópico chega quando S27.1 fechar.

## 3. Escopo

### 3.1 In-scope

- [ ] **`src/hemiciclo/modelos/historico.py`** módulo principal:
  - `class HistoricoConversao`:
    - `calcular(conn: duckdb.DuckDBPyConnection, parlamentar_id: int, casa: str, granularidade: str = "ano") -> pl.DataFrame`
    - `granularidade in ("ano", "legislatura")` agrupa votos por bucket temporal
    - Retorna DataFrame com colunas (bucket, n_votos, proporcao_sim, proporcao_nao, posicao_dominante)
    - Posição dominante: A_FAVOR (sim>=70%), CONTRA (sim<=30%), NEUTRO (entre)
  - `class DetectorMudancas`:
    - `detectar(historico: pl.DataFrame, threshold_pp: float = 30.0) -> list[dict]`
    - Compara buckets adjacentes; mudança = abs(delta_proporcao_sim) >= threshold_pp
    - Retorna lista de eventos: {bucket_anterior, bucket_posterior, delta_pp, posicao_anterior, posicao_posterior}
  - `class IndiceVolatilidade`:
    - `calcular(historico: pl.DataFrame) -> float`
    - Volatilidade = std(proporcao_sim) sobre os buckets, normalizada [0, 1]
    - Score 0 = parlamentar consistente; score 1 = parlamentar errático
- [ ] **`src/hemiciclo/sessao/pipeline.py`** estendido:
  - Nova etapa `_etapa_historico` (93-95%) APÓS C3 e DEPOIS de grafos
  - Para top 100 parlamentares mais ativos: calcula histórico + detecta mudanças
  - Persiste `<sessao_dir>/historico_conversao.json` com formato:
    ```json
    {
      "parlamentares": {
        "<id>": {
          "casa": "camara",
          "nome": "...",
          "historico": [{"bucket": 2018, "proporcao_sim": 0.8, "n_votos": 47, "posicao": "a_favor"}, ...],
          "mudancas_detectadas": [{"bucket_anterior": 2018, "bucket_posterior": 2024, "delta_pp": -60.0, ...}],
          "indice_volatilidade": 0.42
        }
      },
      "metadata": {"granularidade": "ano", "threshold_pp": 30.0, "n_parlamentares": 100}
    }
    ```
- [ ] **`src/hemiciclo/dashboard/widgets/timeline_conversao.py`** atualizada (substitui stub da S31):
  - `renderizar_timeline_conversao(historico_dict: dict, parlamentar_id: int) -> None`
  - Plotly line chart com X=bucket, Y=proporcao_sim, marcadores em mudanças detectadas
  - Anotações com delta_pp em cada mudança significativa
  - Cor verde-folha pra a_favor, vermelho-argila pra contra, cinza pra neutro
- [ ] **`src/hemiciclo/dashboard/paginas/sessao_detalhe.py`** atualizada:
  - Nova seção "Histórico de conversão"
  - Selectbox: top 20 parlamentares mais voláteis (por `indice_volatilidade` desc)
  - Renderiza timeline do parlamentar selecionado
  - Indicador "X mudanças detectadas (>=30pp)" + lista das mudanças
- [ ] **CLI `hemiciclo historico`** subcomando:
  - `hemiciclo historico calcular <sessao_id> [--granularidade ano|legislatura] [--threshold-pp 30]`
  - Útil pra rodar pós-pipeline em sessões antigas
- [ ] **Skip graceful**:
  - Menos de 2 buckets temporais (parlamentar com só 1 ano de dados) -> SKIPPED
  - Sem `votos` na sessão -> SKIPPED com warning
- [ ] **Testes unit** `tests/unit/test_modelos_historico.py` (8 testes):
  - `test_historico_conversao_agrupa_por_ano`
  - `test_historico_conversao_agrupa_por_legislatura`
  - `test_posicao_dominante_a_favor_contra_neutro`
  - `test_detector_mudancas_threshold_padrao`
  - `test_detector_mudancas_threshold_customizado`
  - `test_indice_volatilidade_consistente_zero`
  - `test_indice_volatilidade_erratico_alto`
  - `test_amostra_insuficiente_levanta`
- [ ] **Testes unit** `tests/unit/test_dashboard_timeline_conversao.py` (4 testes):
  - `test_renderizar_timeline_chama_plotly`
  - `test_marca_mudancas_no_grafico`
  - `test_dados_vazios_mostra_aviso`
  - `test_cor_por_posicao`
- [ ] **Testes integração** `tests/integracao/test_historico_e2e.py` (3 testes):
  - `test_pipeline_gera_historico_em_sessao`
  - `test_dashboard_renderiza_timeline_em_sessao_detalhe`
  - `test_workflow_cli_historico_calcular`
- [ ] **Sentinela** `test_sentinela.py`:
  - `test_historico_help`
- [ ] **`docs/arquitetura/historico_conversao.md`** documentando:
  - Granularidades (ano vs legislatura)
  - Detecção de mudanças (threshold padrão 30pp)
  - Índice de volatilidade (interpretação 0-1)
  - Limitação atual (depende de S27.1 pra recall específico do tópico)
- [ ] **CHANGELOG.md** entrada `[Unreleased]`

### 3.2 Out-of-scope

- **ML de convertibilidade** -- fica em S34 (usa volatilidade como feature)
- **Histórico cruzado com discurso** (fala-vs-voto temporal) -- fica em sprint dedicada
- **Filtragem temporal pelo tópico** (depende de S27.1) -- fica nessa sprint
- **Página individual do parlamentar** -- fica em sprint dedicada
- **Comparativo entre parlamentares (overlay)** -- fica em sprint dedicada

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `src/hemiciclo/modelos/historico.py` | HistoricoConversao + DetectorMudancas + IndiceVolatilidade |
| `tests/unit/test_modelos_historico.py` | 8 testes |
| `tests/unit/test_dashboard_timeline_conversao.py` | 4 testes |
| `tests/integracao/test_historico_e2e.py` | 3 testes |
| `docs/arquitetura/historico_conversao.md` | Documentação |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `src/hemiciclo/sessao/pipeline.py` | Nova etapa `_etapa_historico` (93-95%) |
| `src/hemiciclo/dashboard/widgets/timeline_conversao.py` | Substitui stub por implementação real |
| `src/hemiciclo/dashboard/paginas/sessao_detalhe.py` | Nova seção "Histórico" |
| `src/hemiciclo/cli.py` | Subcomando `historico calcular` |
| `tests/unit/test_sentinela.py` | Sentinela |
| `CHANGELOG.md` | Entrada [Unreleased] |
| `sprints/ORDEM.md` | S33 -> DONE |

## 5. Implementação detalhada

### 5.1 HistoricoConversao SQL

```python
def calcular(self, conn, parlamentar_id, casa, granularidade="ano"):
    if granularidade == "ano":
        bucket_expr = "EXTRACT(YEAR FROM vt.data)::INTEGER"
    else:  # legislatura: 2015-2018=55, 2019-2022=56, 2023+=57
        bucket_expr = """CASE
            WHEN EXTRACT(YEAR FROM vt.data) BETWEEN 2015 AND 2018 THEN 55
            WHEN EXTRACT(YEAR FROM vt.data) BETWEEN 2019 AND 2022 THEN 56
            WHEN EXTRACT(YEAR FROM vt.data) >= 2023 THEN 57
            ELSE 0
        END"""

    sql = f"""
        SELECT
            {bucket_expr} AS bucket,
            COUNT(*) AS n_votos,
            SUM(CASE WHEN v.voto = 'SIM' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS proporcao_sim,
            SUM(CASE WHEN v.voto = 'NAO' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS proporcao_nao
        FROM votos v
        JOIN votacoes vt ON vt.id = v.votacao_id AND vt.casa = v.casa
        WHERE v.parlamentar_id = ? AND v.casa = ?
        GROUP BY bucket
        HAVING COUNT(*) >= 5
        ORDER BY bucket
    """
    return conn.execute(sql, [parlamentar_id, casa]).pl()
```

### 5.2 IndiceVolatilidade

```python
def calcular(historico: pl.DataFrame) -> float:
    if len(historico) < 2:
        return 0.0
    series = historico["proporcao_sim"].to_numpy()
    desvio = float(series.std())
    # Normaliza para [0, 1]: std máxima teórica = 0.5 (alternar 0/1)
    return min(desvio / 0.5, 1.0)
```

### 5.3 Passo a passo

1. Confirmar branch.
2. Implementar `modelos/historico.py` (3 classes).
3. Escrever `test_modelos_historico.py` (8 testes).
4. Atualizar `dashboard/widgets/timeline_conversao.py` (substitui stub S31).
5. Escrever `test_dashboard_timeline_conversao.py` (4 testes).
6. Atualizar `pipeline.py` com `_etapa_historico` em 93-95%.
7. Atualizar `sessao_detalhe.py` com nova seção.
8. Adicionar subcomando `historico calcular` em `cli.py`.
9. Adicionar sentinela.
10. Escrever `tests/integracao/test_historico_e2e.py` (3 testes).
11. Escrever `docs/arquitetura/historico_conversao.md`.
12. Atualizar `CHANGELOG.md`.
13. Smoke local: rodar `seed_dashboard` + `historico calcular _seed_com_votos`, verificar JSON gerado.
14. `make check` ≥ 90%.
15. Atualizar ORDEM.md.

## 6. Testes (resumo)

- 8 historico + 4 timeline + 3 e2e + 1 sentinela = **16 testes novos**
- Total: 414 + 16 = 430 testes

## 7. Proof-of-work runtime-real

```bash
$ make check
$ uv run python scripts/seed_dashboard.py
$ uv run hemiciclo historico calcular _seed_com_votos --granularidade ano
[historico] 100 parlamentares processados (10 com mudancas detectadas)
$ ls ~/hemiciclo/sessoes/_seed_com_votos/historico_conversao.json
```

**Critério de aceite:**

- [ ] `make check` 430 testes verdes, cobertura ≥ 90%
- [ ] CLI `historico calcular` retorna exit 0 (mesmo SKIPPED se dados insuficientes)
- [ ] JSON gerado tem `parlamentares` + `metadata`
- [ ] Skip graceful: < 2 buckets / sem votos na sessão
- [ ] Mypy/ruff zero
- [ ] CI verde

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Plotly line chart pesado com 100 parlamentares | Selectbox 1 por vez, 20 mais voláteis |
| Pipeline lento se calcular pra todos | Limitar a top 100 mais ativos por padrão |
| `votacoes.data` ausente em alguns registros | WHERE vt.data IS NOT NULL no SQL |

## 9. Validação multi-agente

Padrão. Validador atenção a: skill `validacao-visual` ativada (diff toca dashboard/), determinismo do detector de mudanças (threshold fixo).

## 10. Próximo passo

S34 (ML convertibilidade -- usa volatilidade como feature) ou S36 (Windows install.bat).
