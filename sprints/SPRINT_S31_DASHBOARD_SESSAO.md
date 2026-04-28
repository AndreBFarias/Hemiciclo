# Sprint S31 -- Dashboard sessão: relatório multidimensional + word clouds + séries

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-28
**Status:** DONE (2026-04-28)
**Depende de:** S22 (DONE), S23 (DONE), S29 (DONE), S30 (DONE)
**Bloqueia:** S38
**Esforço:** G (1-2 semanas)
**ADRs vinculados:** ADR-010 (shell visível primeiro)
**Branch:** feature/s31-dashboard-sessao

---

## 1. Objetivo

Conectar o dashboard Streamlit (S23) com os artefatos reais produzidos pelo pipeline (S30):
- `relatorio_state.json` (top a-favor / top contra / assinatura)
- `manifesto.json` (hashes + limitações conhecidas)
- `classificacao_c1_c2.json` (DataFrame parlamentar × posição)
- `status.json` (polling em tempo real para sessões em andamento)
- `params.json` (parâmetros da sessão)

Esta é a **primeira sprint que entrega valor analítico real ao usuário cidadão final** via interface gráfica. Substitui o stub `sessao_detalhe.py` da S23 por página funcional com widgets ricos.

Out-of-scope (sprints próprias): grafos de rede (S32), histórico de conversão (S33), ML convertibilidade (S34), exportação completa (S35).

## 2. Contexto

S23 entregou shell Streamlit com 4 páginas (intro, lista_sessoes, nova_pesquisa, sobre) e form de pesquisa que persiste rascunho. S29 entregou runner de sessão; S30 entregou pipeline real produzindo artefatos. **Falta agora a página de detalhe que renderiza esses artefatos.**

UX-first (D10): essa sprint faz a entrega visual completa do produto -- ciclo "iniciar pesquisa → ver progresso → ler relatório" funciona ponta-a-ponta no navegador.

## 3. Escopo

### 3.1 In-scope

- [ ] **Dependências runtime**: `wordcloud>=1.9` (visualização), `pillow>=10.0` (renderização imagem)
- [ ] `uv.lock` regenerado
- [ ] **`src/hemiciclo/dashboard/widgets/__init__.py`** marker
- [ ] **`src/hemiciclo/dashboard/widgets/word_cloud.py`**:
  - `renderizar_word_cloud(textos: list[str], titulo: str, max_palavras: int = 100) -> None`
  - Usa `wordcloud.WordCloud` com paleta institucional (`tema.AZUL_HEMICICLO` + `tema.AMARELO_OURO`)
  - Stop words PT-BR básicas (`de, do, da, para, em, com, e, o, a, os, as`)
  - Renderiza via `st.image(buf)` a partir de PIL
- [ ] **`src/hemiciclo/dashboard/widgets/radar_assinatura.py`**:
  - `renderizar_radar(parlamentares: list[dict], eixos: list[str]) -> None`
  - Plotly polar chart com até 7 eixos (D4: posição, intensidade, hipocrisia, volatilidade, centralidade, convertibilidade, enquadramento)
  - Por enquanto, eixos disponíveis: `posicao`, `intensidade` (de C1+C2). Demais ficam None até sprints futuras.
- [ ] **`src/hemiciclo/dashboard/widgets/heatmap_hipocrisia.py`**:
  - `renderizar_heatmap(parlamentares: list[dict]) -> None`
  - Plotly heatmap (parlamentar × tópico) com cor = `proporcao_sim`
  - Stub: aceita dados; na S31 só renderiza com 1 tópico (recorte da sessão)
- [ ] **`src/hemiciclo/dashboard/widgets/timeline_conversao.py`** stub:
  - `renderizar_timeline_conversao(parlamentar_id: int, dados: dict) -> None`
  - Stub que mostra "Histórico de conversão chega em S33" -- placeholder visual
- [ ] **`src/hemiciclo/dashboard/widgets/progresso_sessao.py`**:
  - `renderizar_progresso(status: StatusSessao, etapa_atual: str, mensagem: str, eta_segundos: int | None) -> None`
  - Streamlit progress bar + `st.empty()` que atualiza via polling
  - Lista de etapas concluídas/em andamento/pendentes
  - Compatível com mockup §10.3 do plano R2 Tela 4
- [ ] **`src/hemiciclo/dashboard/widgets/top_pro_contra.py`**:
  - `renderizar_top(top_a_favor: list[dict], top_contra: list[dict], top_n: int = 100) -> None`
  - Duas colunas com tables Streamlit
  - Cada row: ranking, nome, partido, UF, score (proporção sim normalizada)
  - Click em nome abre detalhes (futuro: link pra página parlamentar — fica em S33)
- [ ] **`src/hemiciclo/dashboard/paginas/sessao_detalhe.py`** página completa:
  - Lê `~/hemiciclo/sessoes/<id>/{params,status,relatorio_state,manifesto,classificacao_c1_c2}.json`
  - Header: tópico, casas, período, status, data
  - Se status `concluida`: renderiza widgets (top, radar, heatmap, word clouds)
  - Se status em andamento: renderiza `progresso_sessao` com polling 2s
  - Se status `interrompida`/`erro`: mensagem clara + botões "retomar" / "deletar"
  - Botão "Exportar relatório" (stub -- abre `st.info("Exportação em S35")`)
  - Storytelling no topo (extensão de `tema.STORYTELLING`)
- [ ] **`src/hemiciclo/dashboard/paginas/lista_sessoes.py`** atualizada:
  - Cards de sessão clicáveis -> `session_state["pagina_ativa"] = "sessao_detalhe"` + `session_state["sessao_id"] = <id>`
  - Badge colorido por status (verde=concluida, amarelo=em-andamento, vermelho=erro/interrompida)
  - Mostra parâmetros chave (tópico, casa, período)
- [ ] **`src/hemiciclo/dashboard/app.py`** atualização:
  - Inclui página `sessao_detalhe` no roteador
  - Quando ativa, lê `session_state["sessao_id"]` e despacha
- [ ] **`src/hemiciclo/dashboard/tema.py`** extensão:
  - `STORYTELLING["sessao_detalhe"] = "Relatório multidimensional da pesquisa..."`
  - 7 cores adicionais para eixos do radar (manter paleta institucional)
- [ ] **Testes unit** `tests/unit/test_dashboard_widgets.py` (10 testes via mocker):
  - `test_word_cloud_renderiza_sem_erro`
  - `test_word_cloud_lista_vazia_nao_quebra`
  - `test_radar_4_parlamentares_4_eixos`
  - `test_heatmap_dados_vazios`
  - `test_timeline_stub_mostra_placeholder`
  - `test_progresso_renderiza_etapas`
  - `test_progresso_em_andamento_polling`
  - `test_top_pro_contra_renderiza_2_colunas`
  - `test_top_pro_contra_lista_vazia_nao_quebra`
  - `test_top_pro_contra_top_n_respeitado`
- [ ] **Testes unit** `tests/unit/test_dashboard_sessao_detalhe.py` (8 testes):
  - `test_pagina_carrega_sessao_concluida`
  - `test_pagina_concluida_renderiza_top_a_favor_e_contra`
  - `test_pagina_concluida_renderiza_radar`
  - `test_pagina_em_andamento_renderiza_progresso`
  - `test_pagina_erro_renderiza_mensagem_clara`
  - `test_pagina_interrompida_oferece_retomar`
  - `test_artefato_ausente_nao_quebra_pagina`
  - `test_manifesto_lista_limitacoes`
- [ ] **Testes integração** `tests/integracao/test_dashboard_sessao_e2e.py` (3 testes via AppTest):
  - `test_navegacao_lista_para_detalhe`
  - `test_app_renderiza_sessao_concluida_seed`
  - `test_app_renderiza_sessao_em_andamento_seed`
- [ ] **`scripts/seed_dashboard.py`** popula `~/hemiciclo/sessoes/` com fixtures sintéticas (3 sessões: concluida, em-andamento, erro) pra dev validar UI sem rodar pipeline real
- [ ] **`docs/usuario/interpretando_relatorio.md`** documentando:
  - Como ler top a-favor / top contra
  - Significado dos 7 eixos da assinatura
  - Limitações conhecidas (S24b/c, S25.3, S27.1) e como afetam interpretação
- [ ] **`CHANGELOG.md`** entrada `[Unreleased]`

### 3.2 Out-of-scope (explícito)

- **Grafos de rede** (coautoria + voto pyvis) -- fica em S32
- **Histórico de conversão** completo -- fica em S33
- **ML convertibilidade** -- fica em S34
- **LLM camada 4** -- fica em S34b
- **Exportação completa zip** -- fica em S35 (stub no botão aqui)
- **Página de parlamentar individual** -- fica em S33
- **Filtros interativos avançados** (re-query DuckDB no cliente) -- fica em S33

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `src/hemiciclo/dashboard/widgets/__init__.py` | Marker |
| `src/hemiciclo/dashboard/widgets/word_cloud.py` | wordcloud + PIL |
| `src/hemiciclo/dashboard/widgets/radar_assinatura.py` | Plotly polar chart |
| `src/hemiciclo/dashboard/widgets/heatmap_hipocrisia.py` | Plotly heatmap |
| `src/hemiciclo/dashboard/widgets/timeline_conversao.py` | Stub histórico |
| `src/hemiciclo/dashboard/widgets/progresso_sessao.py` | Progress bar + polling |
| `src/hemiciclo/dashboard/widgets/top_pro_contra.py` | Duas tabelas Streamlit |
| `tests/unit/test_dashboard_widgets.py` | 10 testes |
| `tests/unit/test_dashboard_sessao_detalhe.py` | 8 testes |
| `tests/integracao/test_dashboard_sessao_e2e.py` | 3 testes AppTest |
| `scripts/seed_dashboard.py` | Fixtures sintéticas pra dev |
| `docs/usuario/interpretando_relatorio.md` | Guia de interpretação |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `pyproject.toml` | Adiciona wordcloud, pillow |
| `uv.lock` | Regenerado |
| `src/hemiciclo/dashboard/paginas/sessao_detalhe.py` | Página completa (substitui stub) |
| `src/hemiciclo/dashboard/paginas/lista_sessoes.py` | Cards clicáveis -> detalhe |
| `src/hemiciclo/dashboard/app.py` | Roteador inclui sessao_detalhe |
| `src/hemiciclo/dashboard/tema.py` | Storytelling + cores eixos |
| `tests/unit/test_sentinela.py` | 1 sentinela seed dashboard |
| `CHANGELOG.md` | Entrada [Unreleased] |
| `sprints/ORDEM.md` | S31 -> DONE |

## 5. Implementação detalhada

### 5.1 Layout da página `sessao_detalhe`

```
+--------------------------------------------------------+
| Header: Hemiciclo / nav 4 abas / versão                |
+--------------------------------------------------------+
| [voltar] aborto * Câmara * BR * 2023-2026 [exportar]  |
| 87 proposições * 513 deputados * 234 votações nominais |
+--------------------------------------------------------+
| Top a-favor (col 1)        | Top contra (col 2)       |
|  1. Sâmia Bomfim           |  1. Eros Biondini        |
|  ...                       |  ...                     |
+--------------------------------------------------------+
| Assinatura multidimensional (radar dos top 20)         |
+--------------------------------------------------------+
| Heatmap hipocrisia (parlamentar x topico)              |
+--------------------------------------------------------+
| Word clouds: a-favor / contra (2 colunas)              |
+--------------------------------------------------------+
| Limitações conhecidas: S24c (recall reduzido), S27.1   |
+--------------------------------------------------------+
| Footer: versão, sessões, modelo base                   |
+--------------------------------------------------------+
```

### 5.2 Polling para sessões em andamento

```python
import time

placeholder = st.empty()
while True:
    status = carregar_status(sessao_dir / "status.json")
    if status is None:
        st.error("status.json não encontrado")
        break
    if status.estado in ("concluida", "erro", "interrompida"):
        st.rerun()
        break
    with placeholder.container():
        renderizar_progresso(status, status.etapa_atual, status.mensagem, eta_segundos=None)
    time.sleep(2.0)
```

### 5.3 Word cloud esqueleto

```python
"""Renderiza word cloud com paleta institucional."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    pass

STOP_PT_BR = {
    "de", "do", "da", "dos", "das", "para", "em", "com", "e", "o", "a", "os", "as",
    "que", "se", "no", "na", "nos", "nas", "por", "como", "mais", "ou", "mas",
}


def renderizar_word_cloud(textos: list[str], titulo: str, max_palavras: int = 100) -> None:
    if not textos:
        st.info(f"Sem dados para word cloud: {titulo}")
        return
    from wordcloud import WordCloud
    from hemiciclo.dashboard.tema import AZUL_HEMICICLO, BRANCO_OSSO

    texto_unico = " ".join(textos)
    wc = WordCloud(
        max_words=max_palavras,
        background_color=BRANCO_OSSO,
        color_func=lambda *_a, **_k: AZUL_HEMICICLO,
        stopwords=STOP_PT_BR,
        random_state=42,  # I3
        width=800,
        height=400,
    ).generate(texto_unico)

    buf = io.BytesIO()
    wc.to_image().save(buf, format="PNG")
    st.image(buf.getvalue(), caption=titulo)
```

### 5.4 Passo a passo

1. Confirmar branch.
2. Adicionar deps; `uv sync --all-extras`.
3. Implementar 7 widgets em `dashboard/widgets/`.
4. Escrever `test_dashboard_widgets.py` (10 testes mockados).
5. Reescrever `dashboard/paginas/sessao_detalhe.py` (substitui stub).
6. Atualizar `dashboard/paginas/lista_sessoes.py` (cards clicáveis).
7. Atualizar `dashboard/app.py` (roteador).
8. Atualizar `dashboard/tema.py` (storytelling + cores).
9. Escrever `test_dashboard_sessao_detalhe.py` (8 testes).
10. Escrever `tests/integracao/test_dashboard_sessao_e2e.py` (3 testes via AppTest).
11. Escrever `scripts/seed_dashboard.py` (3 fixtures sintéticas).
12. Adicionar sentinela em `test_sentinela.py`.
13. Escrever `docs/usuario/interpretando_relatorio.md`.
14. Atualizar `CHANGELOG.md`.
15. **Smoke real**: `uv run python scripts/seed_dashboard.py && uv run streamlit run src/hemiciclo/dashboard/app.py`. Navegar lista → clicar sessão concluida seed → ver radar + top + word cloud.
16. `make check` ≥ 90%.
17. Atualizar ORDEM.md.

## 6. Testes (resumo)

- **10** widgets (word cloud, radar, heatmap, timeline, progresso, top)
- **8** sessao_detalhe (concluida, em-andamento, erro, interrompida, artefato ausente)
- **3** integração e2e via AppTest
- **1** CLI sentinela
- **Total: 22 testes novos** + 321 herdados = 343 testes

## 7. Proof-of-work runtime-real

```bash
$ make check
$ uv run python scripts/seed_dashboard.py
seed_dashboard: 3 sessões sintéticas criadas em ~/hemiciclo/sessoes/
$ uv run streamlit run src/hemiciclo/dashboard/app.py --server.headless=true --server.port=8501 &
$ sleep 5 && curl -s http://localhost:8501/_stcore/health
ok
$ # navegar manual: lista_sessoes -> clicar concluida -> ver radar + top + word cloud
```

**Critério de aceite:**

- [ ] `make check` 343 testes verdes, cobertura ≥ 90%
- [ ] `seed_dashboard.py` popula 3 sessões fake (concluida/em-andamento/erro)
- [ ] AppTest renderiza sessão concluida com top + radar visíveis
- [ ] Sessão em andamento mostra progress bar atualizando via polling
- [ ] Sessão erro mostra mensagem clara + botão retomar
- [ ] Word cloud usa paleta institucional + stop words PT-BR
- [ ] `tema.py` random_state=42 em wordcloud (I3)
- [ ] Mypy/ruff zero
- [ ] CI verde nos 6 jobs

## 8. Riscos

| Risco | Mitigação |
|---|---|
| wordcloud não compila Windows wheels | uv resolve binários; fallback: `pip install wordcloud --no-binary` documentado |
| AppTest do Streamlit lento em CI matriz | Marcar testes pesados com `@pytest.mark.slow` (executar só em main) |
| Polling 2s causa redraw piscante | Usar `st.empty()` + `placeholder.container()` (precedente stilingue-energisa-etl) |
| Plotly polar pesado em sessões >20 parlamentares | Limitar top_n radar a 20; mais usa heatmap |
| seed_dashboard.py pode sobrescrever sessões reais do dev | Usar nome prefixado `_seed_*` + checagem |

## 9. Validação multi-agente

Padrão. Validador atenção a: skill `validacao-visual` deve disparar (diff toca `src/hemiciclo/dashboard/`). Capturar screenshot da página `sessao_detalhe` com seed `concluida`.

## 10. Próximo passo após DONE

S32 (grafos de rede) ou S35 (exportação) podem rodar em paralelo. S33 (histórico) também desbloqueada.
