# Sprint S32 -- Grafos de rede: coautoria + voto + pyvis embedável

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-28
**Status:** DONE (2026-04-28)
**Depende de:** S22 (DONE), S26 (DONE), S30 (DONE), S31 (DONE)
**Bloqueia:** S38
**Esforço:** M (3-5 dias)
**ADRs vinculados:** ADR-004 (assinatura multidimensional -- eixo centralidade)
**Branch:** feature/s32-grafos-rede

---

## 1. Objetivo

Adicionar análise de **redes parlamentares** ao Hemiciclo via 2 grafos complementares:

1. **Grafo de coautoria de proposições** -- aresta = mesmo PL coautorado, peso = número de coautorias
2. **Grafo de afinidade por voto nominal** -- aresta = mesma posição (SIM/NÃO/ABSTENÇÃO) em N votações, peso = proporção de coincidência

Ambos via `networkx` (cálculo) + `pyvis` (visualização interativa HTML standalone embedada no Streamlit). Métricas derivadas: centralidade de grau, intermediação, comunidades (Louvain), tamanho da maior componente.

Esta é a entrega do **eixo `centralidade`** da assinatura multidimensional (D4) e prepara terreno pra S33 (histórico de conversão -- usa rede como contexto).

## 2. Contexto

S30 entrega `dados.duckdb` da sessão com tabelas `proposicoes`, `votacoes`, `votos`. S31 entrega dashboard com radar/heatmap/word clouds. S32 adiciona análise de redes:

- Lê `dados.duckdb` da sessão
- Constrói 2 grafos via networkx
- Calcula métricas (centralidade, comunidades)
- Renderiza pyvis HTML
- Embeda no `sessao_detalhe.py` (nova seção "Rede de coautoria" + "Rede de voto")

S27.1 (READY): JOIN voto×proposição depende de `votacoes.proposicao_id`. S32 contorna isso usando `votacoes.id` agrupado por janela temporal (proxy).

## 3. Escopo

### 3.1 In-scope

- [ ] **Dependências runtime**: `networkx>=3.2`, `pyvis>=0.3`, `python-louvain>=0.16` (comunidades opcional)
- [ ] `uv.lock` regenerado
- [ ] **`src/hemiciclo/modelos/grafo.py`** módulo principal:
  - `class GrafoCoautoria`:
    - `construir(conn: duckdb.DuckDBPyConnection) -> nx.Graph`
    - SQL: SELECT autor_principal + coautores em proposicoes (assumindo schema -- ajustar se ausente)
    - Nó = parlamentar (id, nome, partido, casa)
    - Aresta = coautoria, peso = contagem de PLs co-assinadas
  - `class GrafoVoto`:
    - `construir(conn: duckdb.DuckDBPyConnection) -> nx.Graph`
    - SQL: agrupa votações em janelas, calcula coincidência par-a-par
    - Nó = parlamentar
    - Aresta = afinidade de voto, peso = proporção de coincidência
  - `class MetricasGrafo`:
    - `calcular_centralidade(grafo: nx.Graph) -> dict[node, float]`
    - `detectar_comunidades(grafo: nx.Graph) -> dict[node, int]` (Louvain via python-louvain ou modularity_max do networkx)
    - `tamanho_maior_componente(grafo: nx.Graph) -> int`
- [ ] **`src/hemiciclo/modelos/grafo_pyvis.py`** wrapper visualização:
  - `renderizar_pyvis(grafo: nx.Graph, html_path: Path, titulo: str = "") -> Path`
  - Usa `pyvis.network.Network` com paleta institucional do tema
  - Opções: physics=barnesHut, hover labels com nome+partido+UF
  - Cor dos nós por comunidade (Louvain)
  - Tamanho dos nós por centralidade de grau
- [ ] **`src/hemiciclo/dashboard/widgets/rede.py`**:
  - `renderizar_rede(html_path: Path, altura: int = 600) -> None`
  - `st.components.v1.html(html_string, height=altura)`
- [ ] **`src/hemiciclo/sessao/pipeline.py`** estendido:
  - Nova etapa `_etapa_grafos` (88-93%) APÓS C3 e ANTES de relatório
  - Persiste `<sessao_dir>/grafo_coautoria.html` e `<sessao_dir>/grafo_voto.html` se `params.incluir_grafo`
  - Persiste `<sessao_dir>/metricas_rede.json` com centralidade + comunidades
- [ ] **`src/hemiciclo/dashboard/paginas/sessao_detalhe.py`** atualizada:
  - Nova seção "Redes de coautoria e voto"
  - Tabs Streamlit: "Coautoria" / "Voto" / "Métricas"
  - Carrega HTML pyvis salvo em sessao_dir
  - Métricas: tabela com top 10 mais centrais
- [ ] **CLI `hemiciclo rede`** subcomando:
  - `hemiciclo rede analisar <sessao_id> [--tipo coautoria|voto|ambos]`
  - Útil pra rodar análise pós-pipeline (caso sessão antiga sem grafos)
- [ ] **Skip graceful**:
  - Tabela `proposicoes` sem coluna autores -> grafo coautoria SKIPPED com warning
  - Sem `votacoes.proposicao_id` (S27.1 pendente) -> grafo voto usa janela temporal
  - Menos de 5 nós -> grafo SKIPPED ("amostra insuficiente")
- [ ] **Testes unit** `tests/unit/test_modelos_grafo.py` (8 testes):
  - `test_grafo_coautoria_constroi`
  - `test_grafo_coautoria_dados_vazios`
  - `test_grafo_voto_constroi`
  - `test_grafo_voto_calcula_coincidencia`
  - `test_centralidade_grau`
  - `test_comunidades_louvain` (com fallback se python-louvain ausente)
  - `test_tamanho_maior_componente`
  - `test_amostra_insuficiente_levanta`
- [ ] **Testes unit** `tests/unit/test_modelos_grafo_pyvis.py` (4 testes):
  - `test_renderizar_pyvis_gera_html`
  - `test_html_contem_nodes`
  - `test_html_contem_paleta_institucional`
  - `test_grafo_vazio_gera_html_placeholder`
- [ ] **Testes unit** `tests/unit/test_dashboard_widget_rede.py` (3 testes):
  - `test_renderizar_rede_chama_components_html`
  - `test_html_inexistente_mostra_aviso`
  - `test_altura_configuravel`
- [ ] **Testes integração** `tests/integracao/test_grafos_e2e.py` (2 testes):
  - `test_pipeline_gera_grafos_em_sessao` (mock data + verificação de HTMLs gerados)
  - `test_dashboard_renderiza_grafo_em_sessao_detalhe`
- [ ] **Sentinela** `test_sentinela.py`:
  - `test_rede_help`
- [ ] **`docs/arquitetura/grafos_redes.md`** documentando:
  - 2 grafos (coautoria + voto)
  - Algoritmos (Louvain, centralidade)
  - Limitações conhecidas (S27.1 dependency)
  - Como interpretar comunidades
- [ ] **CHANGELOG.md** entrada `[Unreleased]`

### 3.2 Out-of-scope

- **Histórico temporal das redes** -- fica em S33
- **ML de convertibilidade usando features de rede** -- fica em S34
- **Grafo dirigido (relator -> autor)** -- fica em sprint dedicada
- **Análise multilevel (parlamentar × partido × casa)** -- fica em sprint futura
- **Export de grafo para GEXF/GraphML** -- fica fora do MVP

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `src/hemiciclo/modelos/grafo.py` | GrafoCoautoria + GrafoVoto + MetricasGrafo |
| `src/hemiciclo/modelos/grafo_pyvis.py` | Renderização pyvis HTML |
| `src/hemiciclo/dashboard/widgets/rede.py` | Widget Streamlit |
| `tests/unit/test_modelos_grafo.py` | 8 testes |
| `tests/unit/test_modelos_grafo_pyvis.py` | 4 testes |
| `tests/unit/test_dashboard_widget_rede.py` | 3 testes |
| `tests/integracao/test_grafos_e2e.py` | 2 testes |
| `docs/arquitetura/grafos_redes.md` | Documentação |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `pyproject.toml` | Adiciona networkx, pyvis, python-louvain |
| `uv.lock` | Regenerado |
| `src/hemiciclo/sessao/pipeline.py` | Etapa `_etapa_grafos` |
| `src/hemiciclo/dashboard/paginas/sessao_detalhe.py` | Nova seção "Redes" |
| `src/hemiciclo/cli.py` | Subcomando `rede analisar` |
| `tests/unit/test_sentinela.py` | Sentinela rede |
| `CHANGELOG.md` | Entrada [Unreleased] |
| `sprints/ORDEM.md` | S32 -> DONE |

## 5. Implementação detalhada

### 5.1 GrafoCoautoria esqueleto

```python
import networkx as nx
import duckdb


class GrafoCoautoria:
    @staticmethod
    def construir(conn: duckdb.DuckDBPyConnection) -> nx.Graph:
        # Sem coluna 'coautores' formal: usar autor_principal x co-autores
        # quando ambos votaram em mesma proposição
        # Adaptar conforme schema disponível
        sql = """
        SELECT v1.parlamentar_id AS u, v2.parlamentar_id AS v, COUNT(*) AS peso
        FROM votos v1
        JOIN votos v2 ON v1.votacao_id = v2.votacao_id
        WHERE v1.parlamentar_id < v2.parlamentar_id
        GROUP BY u, v
        HAVING peso >= 5
        """
        df = conn.execute(sql).pl()
        g = nx.Graph()
        for row in df.iter_rows(named=True):
            g.add_edge(row["u"], row["v"], weight=row["peso"])
        return g
```

### 5.2 Pyvis com paleta institucional

```python
def renderizar_pyvis(grafo: nx.Graph, html_path: Path, titulo: str = "") -> Path:
    from pyvis.network import Network
    from hemiciclo.dashboard.tema import AZUL_HEMICICLO, AMARELO_OURO

    net = Network(
        height="600px",
        width="100%",
        bgcolor="#FAF8F3",  # BRANCO_OSSO
        font_color=AZUL_HEMICICLO,
        notebook=False,
    )
    for node in grafo.nodes():
        comunidade = grafo.nodes[node].get("comunidade", 0)
        cor = [AZUL_HEMICICLO, AMARELO_OURO, "#3D7A3D", "#A8403A"][comunidade % 4]
        net.add_node(
            node,
            label=grafo.nodes[node].get("nome", str(node)),
            title=f"{grafo.nodes[node].get('partido', '')} / {grafo.nodes[node].get('uf', '')}",
            color=cor,
            size=10 + 30 * grafo.nodes[node].get("centralidade", 0),
        )
    for u, v, d in grafo.edges(data=True):
        net.add_edge(u, v, value=d.get("weight", 1))
    net.save_graph(str(html_path))
    return html_path
```

### 5.3 Passo a passo

1. Confirmar branch.
2. Adicionar deps; `uv sync --all-extras`.
3. Implementar `modelos/grafo.py`.
4. Escrever `test_modelos_grafo.py` (8 testes).
5. Implementar `modelos/grafo_pyvis.py`.
6. Escrever `test_modelos_grafo_pyvis.py` (4 testes).
7. Implementar `dashboard/widgets/rede.py`.
8. Escrever `test_dashboard_widget_rede.py` (3 testes).
9. Atualizar `pipeline.py` com `_etapa_grafos`.
10. Atualizar `sessao_detalhe.py` com nova seção.
11. Adicionar subcomando `rede analisar` em `cli.py`.
12. Adicionar sentinela.
13. Escrever `tests/integracao/test_grafos_e2e.py`.
14. Escrever docs.
15. Smoke local: rodar pipeline em sessão fixture, verificar HTMLs gerados.
16. `make check` ≥ 90%.
17. Atualizar ORDEM.md.

## 6. Testes (resumo)

- 8 grafo + 4 pyvis + 3 widget + 2 e2e + 1 sentinela = **18 testes novos**
- Total: 378 + 18 = 396 testes

## 7. Proof-of-work runtime-real

```bash
$ make check
$ uv run python scripts/seed_dashboard.py
$ uv run hemiciclo rede analisar _seed_concluida --tipo ambos
[rede] grafo_coautoria.html gerado (X nós, Y arestas)
[rede] grafo_voto.html gerado
$ ls ~/hemiciclo/sessoes/_seed_concluida/grafo*.html
```

**Critério de aceite:**

- [ ] `make check` 396 testes verdes, cobertura ≥ 90%
- [ ] Sessão concluida com `incluir_grafo=True` gera 2 HTMLs pyvis
- [ ] Dashboard renderiza grafo na seção "Redes"
- [ ] Métricas no JSON: top 10 mais centrais + número de comunidades
- [ ] Skip graceful: amostra < 5 nós não falha
- [ ] Mypy/ruff zero
- [ ] CI verde

## 8. Riscos

| Risco | Mitigação |
|---|---|
| pyvis HTML pesado em sessões grandes | Limitar a top 200 nós + filtros de peso mínimo |
| python-louvain não instala em Windows | Fallback `nx.community.greedy_modularity_communities` |
| `dados.duckdb` sem coluna autores | Skip graceful + warning + grafo voto only |
| HTML embedado quebra layout Streamlit | `st.components.v1.html(height=600)` fixo |

## 9. Validação multi-agente

Padrão. Validador atenção a: skill `validacao-visual` ativada (diff toca dashboard/), Plotly não-determinismo evitado via `random_state` em layouts.

## 10. Próximo passo após DONE

S33 (histórico de conversão -- usa rede como feature) ou S36 (Windows install.bat).
