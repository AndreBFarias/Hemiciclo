# Sprint S38.10 -- Tematização do `st.dataframe` (canvas grid)

(ID renomeado de S38.9 para S38.10 -- S38.9 reservado para release v2.1.1)

**Projeto:** Hemiciclo
**Versão alvo:** v2.1.1 (ou v2.1.2 se sair do hotfix)
**Status:** READY
**Esforço:** M (3-5h)
**Branch sugerida:** feature/s38-9-dataframe-canvas-theme
**Depende de:** S38.5 (DONE)
**Bloqueia:** --

## 1. Origem

Achado colateral durante execução de **S38.5 -- Tema Streamlit completo**.

Streamlit 1.56 renderiza `st.dataframe` via `glide-data-grid` em **canvas HTML5**, não via DOM cells. Isso significa que os seletores CSS aplicados em S38.5 (`[data-testid="stDataFrame"] [role="columnheader"]`, `[role="gridcell"]`) **não pegam** as cores do header e das células zebra -- a tabela renderizada na cena `sessao_detalhe` ficou com cabeçalho `BRANCO_OSSO` em vez do `AZUL_HEMICICLO` esperado pelo spec.

O critério **mínimo** de S38.5 (sem fundo preto, score não vermelho) foi atingido -- mas o critério **estético** (cabeçalho `AZUL_HEMICICLO` + score `VERDE_FOLHA`) não. Esta sprint fecha o gap.

## 2. Evidência

Captura `playwright` em `/tmp/hemiciclo_s38_5_top_tables.png` (sha256 `055dec3900d550f843296c554e880af3cb17c1ec84e53dcdcb479e690ae95fcd`) mostra:
- Headers `#`, `Nome`, `Partido`, `UF`, `Score` com fundo claro neutro (próximo do `BRANCO_OSSO`/`CINZA_AREIA`) -- aceitável mas não institucional.
- Score em barra `AMARELO_OURO` (default `primaryColor` do `config.toml`) -- aceitável (não vermelho), mas spec original pedia `VERDE_FOLHA`.

## 3. Escopo

### 3.1 In-scope

**Opção A (recomendada):** substituir `st.dataframe` por componente HTML/CSS direto via `st.markdown(html, unsafe_allow_html=True)` em `widgets/top_pro_contra.py`. Renderizar tabela `<table>` com classes do `style.css` (`.hemiciclo-tabela-rank` a criar) e `<div class="bar">` para Score. Vantagem: controle total da paleta. Desvantagem: perde sort interativo do glide.

**Opção B:** manter `st.dataframe` e usar `st.column_config.ProgressColumn(..., format="...")` + uma camada de CSS via `theme.toml` extras. Streamlit 1.56 não expõe cor da barra de `ProgressColumn` programaticamente. Pesquisar se 1.58+ traz API; se sim, bumpar pin.

**Opção C:** investigar se `st.column_config.Column(..., width=...)` aceita `background_color` em versão futura; se não, descartar.

Decidir entre A/B/C ao iniciar; A é o caminho mais rápido com paleta institucional total.

Touches autorizados:
- `src/hemiciclo/dashboard/widgets/top_pro_contra.py`
- `src/hemiciclo/dashboard/style.css` (novas classes `.hemiciclo-tabela-rank*`)
- `src/hemiciclo/dashboard/widgets/ranking_convertibilidade.py` (mesmo padrão se reaproveitar)
- `tests/unit/test_dashboard_widgets.py` (atualizar asserts se houver)
- `CHANGELOG.md`

### 3.2 Out-of-scope
- Substituir TODOS os `st.dataframe` do dashboard (só os 3 críticos: top_pro_contra, ranking_convertibilidade, eventual top voláteis em sessao_detalhe).
- Sort/filter UI do glide (componente HTML pode renderizar sem sort).

## 4. Acceptance criteria

- [ ] Cabeçalho da tabela em `AZUL_HEMICICLO` (#1E3A5F) com texto branco
- [ ] Linhas zebra `BRANCO_OSSO` / `CINZA_AREIA`
- [ ] Score como barra horizontal em `VERDE_FOLHA` (#3D7A3D), com `%` à direita
- [ ] Smoke real no browser (Playwright) confirma cores via PNG + sha256 + descrição
- [ ] Testes unit em `widgets/top_pro_contra.py` continuam passando (524 → 524 ou mais)
- [ ] `mypy --strict` zero erros
- [ ] CHANGELOG atualizado em `[Unreleased]`

## 5. Proof-of-work

```bash
# 1. Smoke real (Playwright):
make run &
node /tmp/capture_top_tables.mjs
sha256sum /tmp/hemiciclo_s38_9_top_tables.png

# 2. Unit:
uv run pytest tests/unit/test_dashboard_widgets.py -v

# 3. Lint/type:
uv run ruff check src tests
uv run mypy --strict src
```

## 6. Riscos

- Perda do sort/filter interativo do `glide-data-grid` se tomarmos Opção A. Mitigação: tabelas Top são pré-ordenadas pelo `relatorio_state.json`; sort interativo é nice-to-have, não essencial.
- Mudança em `ranking_convertibilidade` pode quebrar testes existentes; revisar `test_dashboard_widget_convertibilidade.py`.
