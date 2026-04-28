# Sprint S38.5 -- Tema Streamlit completo (config.toml + CSS de componentes)

**Projeto:** Hemiciclo
**Versão alvo:** v2.1.1
**Status:** READY
**Esforço:** M (3-4h)
**Branch:** feature/s38-5-tema-streamlit-completo
**Depende de:** --
**Bloqueia:** divulgação visual

---

## 1. Objetivo

Aplicar tema institucional sóbrio (paleta `tema.py`) a TODOS os componentes Streamlit, eliminando os defaults pretos/vermelhos que atualmente sobrepõem o tema do projeto.

## 2. Contexto

Smoke real do browser pós v2.1.0 mostrou:
- Selectbox/multiselect/date_input com **fundo preto** (default Streamlit dark mode)
- Tags do multiselect em **vermelho** (não AMARELO_OURO/AZUL_HEMICICLO)
- Botão "Iniciar pesquisa" e "+ Nova pesquisa" em **vermelho** (default `primaryColor`)
- "**Choose options**" em inglês (placeholder default)
- `st.dataframe` (tabelas Top a-favor / Top contra) com fundo preto e linhas em vermelho
- Labels "Casas/UFs/Período/Camadas" em cor invisível sobre fundo claro

Isso contradiz `dashboard/tema.py` que declara paleta institucional `BRANCO_OSSO`/`AZUL_HEMICICLO`/`AMARELO_OURO`.

## 3. Escopo

### 3.1 In-scope

**3.1.1. Criar `.streamlit/config.toml`** (root do repo, não em `~/.streamlit`):
```toml
[theme]
base = "light"
primaryColor = "#D4A537"          # AMARELO_OURO (CTA)
backgroundColor = "#FAF8F3"       # BRANCO_OSSO
secondaryBackgroundColor = "#E8E4D8"  # CINZA_AREIA
textColor = "#4A4A4A"             # CINZA_PEDRA
font = "sans serif"
```

**3.1.2. Estender `dashboard/style.css`** com regras para:
- `[data-baseweb="select"]` -- selectbox/multiselect com fundo `BRANCO_OSSO`, borda `CINZA_AREIA`, texto `CINZA_PEDRA`
- `[data-baseweb="popover"]` -- dropdown aberto com mesma paleta
- `[data-baseweb="tag"]` -- tags com fundo `AZUL_CLARO`, texto branco (não vermelho)
- `[data-testid="stDateInput"]` -- date_input com paleta tema
- `[data-testid="stDataFrame"]` -- tabelas com header `AZUL_HEMICICLO`, zebra `BRANCO_OSSO`/`CINZA_AREIA`, sem barras vermelhas espúrias
- `.stButton > button[kind="primary"]` -- botão primary com `AMARELO_OURO` background
- `[data-testid="stForm"] label` -- labels visíveis em `AZUL_HEMICICLO`, peso 600
- `[data-testid="stMarkdownContainer"] code` -- inline code com fundo `CINZA_AREIA`, sem default cinza-azul

**3.1.3. Traduzir defaults Streamlit:**
- `st.multiselect(..., placeholder="Selecione...")` em todos os usos
- `st.selectbox(..., placeholder="Selecione...")`
- Mensagens de erro Pydantic via try/except → traduzir para PT-BR

**3.1.4. Tabelas Top a-favor / Top contra:**
Substituir `st.dataframe` cru por componente customizado que renderiza com tema institucional. Pode ser HTML/CSS direto via `st.markdown(html, unsafe_allow_html=True)` ou `st.column_config` com cores corretas.

### 3.2 Out-of-scope
- Modo dark (sprint futura se for prioridade)
- Animações
- Mobile-first responsivo (já há media query em style.css)

## 4. Proof-of-work

Smoke visual via Playwright headless + checklist multimodal:
- [ ] Selectbox aberto: dropdown branco-osso, sem fundo preto
- [ ] Multiselect tags: AZUL_CLARO ou AMARELO_OURO, nunca vermelho
- [ ] Date input: paleta institucional
- [ ] Botão "Iniciar pesquisa": AMARELO_OURO ou AZUL_HEMICICLO
- [ ] Tabelas Top a-favor/Top contra: cabeçalho azul-marinho, linhas zebra, score em barra horizontal verde-folha (não vermelho)
- [ ] "Choose options" inexistente (substituído por "Selecione")
- [ ] Labels do form visíveis (não somem em fundo claro)

```bash
# Validador-sprint dispara skill validacao-visual
make run &
# (3 screenshots: nova_pesquisa form, lista_sessoes cards, sessao_detalhe relatório)
```

## 5. Riscos

- Streamlit injeta CSS depois do user CSS via `<style>`; algumas regras precisam de `!important` ou seletores mais específicos.
- Mudanças em `[data-baseweb=*]` podem quebrar com upgrade Streamlit -- pinar versão >= 1.40 (já está) e documentar.

## 6. Próximo passo após DONE

S38.6 (despoluição de jargão técnico).
