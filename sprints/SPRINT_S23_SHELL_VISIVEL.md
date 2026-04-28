# Sprint S23 -- Shell visível: Streamlit + install.sh + intro narrativo + lista vazia

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-28
**Autor:** @AndreBFarias
**Status:** DONE (2026-04-28)
**Depende de:** S22 (DONE)
**Bloqueia:** S31, S36
**Esforço:** M (3-5 dias)
**ADRs vinculados:** ADR-010 (shell visível primeiro), ADR-014 (install.sh exige Python 3.11+ pré-instalado)
**Branch:** feature/s23-shell-visivel

---

## 1. Objetivo

Entregar primeiro sinal de vida visível do Hemiciclo 2.0: usuário Linux/macOS comum executa `./install.sh` e `./run.sh`, navegador abre em `localhost:8501` mostrando intro narrativo, lista de sessões (vazia na primeira execução), form completo de "Nova Pesquisa" com validação Pydantic, e página "Sobre" com manifesto longo. Pipeline real ainda não roda -- botão "Iniciar pesquisa" exibe mensagem "Funcionalidade chega em S30".

## 2. Contexto

D10 do plano R2 manda UX antes de profundidade técnica: o usuário comum precisa ver o app rodando antes de qualquer ETL existir. Sem isso, todas as sprints subsequentes (S24-S38) ficam invisíveis pra quem não é dev. Esta sprint entrega a casca visual completa do produto.

S22 já entregou bootstrap Python (CLI `hemiciclo`, Pydantic Settings, Makefile). S37 entregou CI multi-OS verde. Esta sprint é a primeira entrega visível ao usuário cidadão final.

A referência estilística é o projeto `stilingue-energisa-etl` (`/home/andrefarias/Desenvolvimento/stilingue-energisa-etl/dashboard/`): storytelling por aba, header customizado, navegação com cores, CSS injetado, layout wide com sidebar collapsed.

## 3. Escopo

### 3.1 In-scope

- [ ] **Dependências Streamlit** adicionadas a `pyproject.toml`:
  - `streamlit>=1.40` em deps runtime
  - `plotly>=5.20` em deps runtime
  - `pytest-mock>=3.14` em deps dev (pra mockar Streamlit em testes)
- [ ] `uv.lock` regenerado (`uv sync --all-extras`)
- [ ] **`install.sh`** Linux/macOS:
  - Detecta SO via `uname -s`
  - Valida Python 3.11+ instalado (`python3 --version` >= 3.11)
  - Aborta com mensagem clara + link `https://python.org/downloads` se ausente
  - Instala uv globalmente se faltar (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
  - `uv sync --all-extras` (~3-5 min)
  - **NÃO baixa modelo bge-m3** (fica pra S28)
  - Imprime tempo decorrido e comando `./run.sh` ao final
  - Modo `--check` que valida ambiente sem instalar (pra CI smoke test futuro)
- [ ] **`run.sh`** Linux/macOS:
  - Ativa `.venv`
  - `uv run streamlit run src/hemiciclo/dashboard/app.py --server.headless=false`
  - Streamlit abre browser automaticamente (default behavior)
  - Captura SIGINT pra `streamlit stop` graceful
- [ ] **`src/hemiciclo/dashboard/__init__.py`** vazio
- [ ] **`src/hemiciclo/dashboard/app.py`** entry-point Streamlit:
  - `st.set_page_config(page_title="Hemiciclo", layout="wide", initial_sidebar_state="collapsed")`
  - Carrega CSS injetado de `style.css`
  - Detecta primeira execução (sessão sem `~/hemiciclo/config.toml`) -> abre intro
  - Navegação por 4 abas via `st.session_state["pagina_ativa"]`: `intro`, `lista_sessoes`, `nova_pesquisa`, `sobre`
  - Roda `Configuracao().garantir_diretorios()` na carga
  - Renderiza header global + página ativa + footer global
- [ ] **`src/hemiciclo/dashboard/tema.py`** design tokens literais (seção 10.2 do plano R2):
  - `AZUL_HEMICICLO`, `AZUL_CLARO`, `AMARELO_OURO`, `VERDE_FOLHA`, `VERMELHO_ARGILA`, `CINZA_PEDRA`, `CINZA_AREIA`, `BRANCO_OSSO`
  - `TIPOGRAFIA` dict com `titulo`, `corpo`, `mono`
  - `ESPACAMENTO` dict com `xs`, `sm`, `md`, `lg`, `xl`, `xxl`
  - `STORYTELLING` dict com 4 chaves (uma por aba)
- [ ] **`src/hemiciclo/dashboard/style.css`** CSS injetado:
  - Tipografia Inter (Google Fonts ou fallback system-ui)
  - Cores via CSS variables a partir de `tema.py`
  - Botões com border-radius, transições suaves
  - Cards de sessão com sombra leve
  - Header fixo com logo placeholder + título
  - Footer fixo com versão + estatísticas
  - Responsivo até 1024px (acima é desktop only)
- [ ] **`src/hemiciclo/dashboard/componentes.py`**:
  - `header_global(versao: str) -> None` -- renderiza topo
  - `footer_global(stats: dict) -> None` -- renderiza rodapé
  - `navegacao_principal() -> str` -- 4 botões, cor por aba, retorna aba ativa
  - `card_sessao(sessao_meta: dict) -> None` -- card de sessão na lista
  - `cta_primeira_pesquisa() -> None` -- call-to-action quando lista vazia
- [ ] **`src/hemiciclo/dashboard/paginas/__init__.py`** vazio
- [ ] **`src/hemiciclo/dashboard/paginas/intro.py`**:
  - Manifesto curto (3-4 frases)
  - Botão grande "Fazer minha primeira pesquisa" (vai pra `nova_pesquisa`)
  - Links secundários: "Ler manifesto" (vai pra `sobre`), "Como funciona" (anchor docs)
- [ ] **`src/hemiciclo/dashboard/paginas/lista_sessoes.py`**:
  - Lê `~/hemiciclo/sessoes/*/params.json` + `status.json`
  - Se vazia: `cta_primeira_pesquisa()`
  - Se há sessões: grid de `card_sessao()` ordenado por `iniciada_em` desc
  - Botão "+ Nova pesquisa" no topo
  - Card mostra: tópico, casas, UF, status (badge colorido), progresso se rodando, data
- [ ] **`src/hemiciclo/dashboard/paginas/nova_pesquisa.py`**:
  - `st.form` validando `ParametrosBusca` (Pydantic v2) -- importar de `src/hemiciclo/sessao/modelo.py` (criar nesta sprint? não -- placeholder Pydantic mínimo aqui, schema completo fica em S29)
  - Inputs: tópico (text), casas (multiselect Câmara/Senado), legislaturas (multiselect 55-57), UFs (multiselect com 27 estados), partidos (multiselect com partidos canônicos), período (date_input range), camadas (multiselect: regex, votos, embeddings, llm)
  - Estimativa de tempo + espaço calculada client-side a partir dos params
  - Botão "Iniciar pesquisa" -- ao clicar exibe `st.info("Funcionalidade chega em S30")` + persiste `params.json` na pasta da sessão como rascunho
  - Validação: tópico não-vazio, ao menos 1 casa, ao menos 1 legislatura
- [ ] **`src/hemiciclo/dashboard/paginas/sobre.py`**:
  - Manifesto longo (texto político ~500 palavras) -- conteúdo em `docs/manifesto.md` (criar nesta sprint, versão curta; versão final fica em S38)
  - Lista de tecnologias usadas + licença GPLv3
  - Link pro repo GitHub
  - Versão do app
- [ ] **`src/hemiciclo/sessao/__init__.py`** vazio
- [ ] **`src/hemiciclo/sessao/modelo.py`** Pydantic mínimo desta sprint:
  - Enum `Camada` (REGEX, VOTOS, EMBEDDINGS, LLM)
  - Enum `Casa` (CAMARA, SENADO)
  - Enum `EstadoSessao` (CRIADA, COLETANDO, ETL, EMBEDDINGS, MODELANDO, CONCLUIDA, ERRO, INTERROMPIDA, PAUSADA)
  - Modelo `ParametrosBusca` com campos da seção 5.4 do plano R2
  - Modelo `StatusSessao` (estado, progresso_pct, etapa_atual, mensagem, iniciada_em, atualizada_em, pid, erro)
  - **Não inclui** runner, persistência, retomada -- isso fica em S29
- [ ] **CLI `hemiciclo dashboard`** (novo subcomando em `cli.py`):
  - Sobe Streamlit chamando `subprocess.run(["streamlit", "run", ...])`
  - Equivalente a `./run.sh` mas via CLI Python
- [ ] **Testes unit** em `tests/unit/test_dashboard_componentes.py`:
  - `test_navegacao_define_pagina_ativa` -- mock streamlit, verifica session_state
  - `test_card_sessao_renderiza_metadados`
  - `test_cta_primeira_pesquisa_aparece_se_vazia`
- [ ] **Testes unit** em `tests/unit/test_modelo_sessao.py`:
  - `test_parametros_busca_topico_obrigatorio` -- ValidationError se vazio
  - `test_parametros_busca_camadas_default` -- regex+votos+embeddings (sem llm)
  - `test_status_sessao_progresso_clamp` -- pct no range [0, 100]
  - `test_estado_sessao_enum_valores` -- 9 valores literais
  - `test_serializacao_round_trip` -- model_dump_json + model_validate_json
- [ ] **Testes integração** em `tests/integracao/test_dashboard_smoke.py`:
  - Usa `streamlit.testing.v1.AppTest`
  - `test_app_carrega_sem_erro` -- AppTest.from_file roda sem exception
  - `test_intro_renderiza_titulo` -- página intro aparece no rerun
  - `test_lista_sessoes_vazia_mostra_cta`
  - `test_nova_pesquisa_form_renderiza_inputs`
  - `test_sobre_renderiza_manifesto`
- [ ] **`docs/manifesto.md`** versão curta (~500 palavras) -- versão final fica em S38
- [ ] **`docs/usuario/instalacao.md`** Linux/macOS:
  - Pré-requisitos (Python 3.11+, RAM >= 4GB, disco >= 5GB)
  - Comandos por SO (Ubuntu, Fedora, macOS)
  - Troubleshooting (Python ausente, certificado SSL, M1 vs Intel)
  - Como verificar (rodar `./run.sh`, abrir browser, ver intro)
- [ ] **`docs/usuario/primeira_pesquisa.md`** stub (~200 palavras) -- documenta jornada esperada quando S30 estiver pronta
- [ ] **`README.md`** atualizado:
  - Substitui seção "Migração para Python 2.0 em andamento" por "Instalação rápida" + "Primeira pesquisa"
  - Mantém badges
- [ ] **`CHANGELOG.md`** entrada `[Unreleased]` com bullet "feat(dashboard): shell visível Streamlit + install.sh"

### 3.2 Out-of-scope (explícito)

- `install.bat` e `run.bat` Windows -- fica em S36 (paridade Windows)
- Coleta real, ETL, embeddings, modelagem -- fica em S24/S25/S26/S27/S28/S30
- Runner de subprocess de sessão -- fica em S29
- Dashboard de relatório de sessão concluída -- fica em S31
- Grafos de rede + word clouds -- fica em S32, S33
- Mock seed de sessões fake (`scripts/seed_dados.py`) -- script existe stub, mas conteúdo de mock fica fora desta sprint
- Word clouds, gráficos Plotly -- fica em S31
- Manifesto longo final -- fica em S38 (versão curta agora)

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `install.sh` | Bootstrap usuário final Linux/macOS |
| `run.sh` | Atalho rodar Streamlit |
| `src/hemiciclo/dashboard/__init__.py` | Marker package |
| `src/hemiciclo/dashboard/app.py` | Entry-point Streamlit |
| `src/hemiciclo/dashboard/tema.py` | Design tokens (cores, tipografia, espaçamento, storytelling) |
| `src/hemiciclo/dashboard/style.css` | CSS injetado |
| `src/hemiciclo/dashboard/componentes.py` | header, footer, navegação, cards, CTA |
| `src/hemiciclo/dashboard/paginas/__init__.py` | Marker |
| `src/hemiciclo/dashboard/paginas/intro.py` | Página intro narrativo |
| `src/hemiciclo/dashboard/paginas/lista_sessoes.py` | Lista de sessões |
| `src/hemiciclo/dashboard/paginas/nova_pesquisa.py` | Form de configuração |
| `src/hemiciclo/dashboard/paginas/sobre.py` | Página manifesto |
| `src/hemiciclo/sessao/__init__.py` | Marker |
| `src/hemiciclo/sessao/modelo.py` | Pydantic v2 schemas (ParametrosBusca, StatusSessao, enums) |
| `tests/unit/test_dashboard_componentes.py` | Testes componentes |
| `tests/unit/test_modelo_sessao.py` | Testes modelo Pydantic |
| `tests/integracao/test_dashboard_smoke.py` | Smoke tests via AppTest |
| `docs/manifesto.md` | Texto político (versão curta) |
| `docs/usuario/instalacao.md` | Guia instalação Linux/macOS |
| `docs/usuario/primeira_pesquisa.md` | Stub jornada do usuário |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `pyproject.toml` | Adiciona streamlit, plotly, pytest-mock |
| `uv.lock` | Regenerado |
| `src/hemiciclo/cli.py` | Adiciona subcomando `hemiciclo dashboard` |
| `README.md` | Substitui seção placeholder por instalação + primeira pesquisa |
| `CHANGELOG.md` | Entrada [Unreleased] |
| `sprints/ORDEM.md` | S23 -> DONE |

## 5. Implementação detalhada

### 5.1 Passo a passo

1. Confirmar branch `feature/s23-shell-visivel`.
2. Adicionar `streamlit`, `plotly`, `pytest-mock` ao pyproject; rodar `uv sync --all-extras` -> regenera lock.
3. Escrever `src/hemiciclo/sessao/modelo.py` (Pydantic enums + ParametrosBusca + StatusSessao).
4. Escrever `tests/unit/test_modelo_sessao.py` (5 testes; rodar `pytest -k modelo` antes de prosseguir).
5. Escrever `src/hemiciclo/dashboard/tema.py` (design tokens literais).
6. Escrever `src/hemiciclo/dashboard/style.css`.
7. Escrever `src/hemiciclo/dashboard/componentes.py` (5 funções).
8. Escrever as 4 páginas em `paginas/`.
9. Escrever `src/hemiciclo/dashboard/app.py` integrando tudo.
10. Adicionar subcomando `hemiciclo dashboard` em `cli.py`.
11. Escrever `tests/unit/test_dashboard_componentes.py` (3 testes).
12. Escrever `tests/integracao/test_dashboard_smoke.py` (5 testes via AppTest).
13. Escrever `install.sh` Linux/macOS.
14. Escrever `run.sh`.
15. Escrever `docs/manifesto.md`, `docs/usuario/instalacao.md`, `docs/usuario/primeira_pesquisa.md`.
16. Atualizar `README.md` e `CHANGELOG.md`.
17. Rodar smoke manual: `./install.sh` em ambiente limpo (ou em venv separado), `./run.sh`, browser abre em localhost:8501, navega pelas 4 abas, submete form -> vê mensagem "Funcionalidade em S30".
18. `make check` deve passar com cobertura >= 90%.
19. Atualizar `sprints/ORDEM.md` mudando S23 para DONE.

### 5.2 Decisões técnicas

- **Navegação por session_state, não st.tabs nem st.sidebar.** Sidebar já está collapsed (mais real estate). `st.tabs` não permite controle programático de "ir pra próxima aba" via botão.
- **CSS injetado via `unsafe_allow_html=True`** -- padrão estabelecido no `stilingue-energisa-etl`.
- **`Configuracao().garantir_diretorios()` na carga do app** -- garante que `~/hemiciclo/sessoes/` etc existem antes de tentar listar.
- **Form validação Pydantic** em `nova_pesquisa.py` -- `try: ParametrosBusca(**form_data) except ValidationError as e: st.error(...)`.
- **Botão "Iniciar pesquisa" persiste rascunho** mesmo sem rodar pipeline -- pasta `~/hemiciclo/sessoes/<slug>_rascunho/params.json` criada. Quando S30 ficar pronto, basta detectar rascunhos e oferecer "retomar". Anti-débito.
- **Sem React/JS custom** -- só Streamlit + CSS. Mantém deploy trivial.

### 5.3 Trecho de código de referência -- `tema.py` literal

```python
"""Design tokens do dashboard Hemiciclo.

Paleta inspirada em institucional sóbrio (não-partidária).
Inter como tipografia primária, JetBrains Mono pra código.
"""

from __future__ import annotations

AZUL_HEMICICLO = "#1E3A5F"        # primary
AZUL_CLARO = "#4A7BAB"            # primary-light
AMARELO_OURO = "#D4A537"          # accent (Brasil sem ser kitsch)
VERDE_FOLHA = "#3D7A3D"           # success / a-favor
VERMELHO_ARGILA = "#A8403A"       # danger / contra
CINZA_PEDRA = "#4A4A4A"           # neutral-strong
CINZA_AREIA = "#E8E4D8"           # neutral-light bg
BRANCO_OSSO = "#FAF8F3"           # bg principal

TIPOGRAFIA = {
    "titulo": "'Inter', system-ui, sans-serif",
    "corpo": "'Inter', system-ui, sans-serif",
    "mono": "'JetBrains Mono', monospace",
}

ESPACAMENTO = {
    "xs": 4,
    "sm": 8,
    "md": 16,
    "lg": 24,
    "xl": 32,
    "xxl": 48,
}

STORYTELLING = {
    "intro": (
        "Inteligência política aberta. Soberana. Local. "
        "Quem vota a favor do quê. Quem mudou de lado. Quem fala uma coisa "
        "e vota outra. Sem opinião nossa -- só dados."
    ),
    "lista_sessoes": (
        "Suas pesquisas ficam salvas localmente. "
        "Cada uma é uma análise autocontida que você pode revisitar, "
        "exportar, ou compartilhar com outros pesquisadores."
    ),
    "nova_pesquisa": (
        "Configure tópico, casa legislativa, estado, partido e período. "
        "A coleta roda em background na sua máquina -- pode levar minutos "
        "ou horas dependendo do recorte."
    ),
    "sobre": (
        "Hemiciclo é uma ferramenta cidadã para entender o Congresso "
        "Brasileiro com o mesmo rigor metodológico que se vende a "
        "lobistas. Open-source, GPL v3, sem servidor central."
    ),
}
```

### 5.4 Trecho de código de referência -- `app.py` esqueleto

```python
"""Entry-point do dashboard Streamlit do Hemiciclo."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from hemiciclo import __version__
from hemiciclo.config import Configuracao
from hemiciclo.dashboard import componentes
from hemiciclo.dashboard.paginas import intro, lista_sessoes, nova_pesquisa, sobre

PAGINAS = {
    "intro": ("Início", intro.render),
    "lista_sessoes": ("Pesquisas", lista_sessoes.render),
    "nova_pesquisa": ("Nova pesquisa", nova_pesquisa.render),
    "sobre": ("Sobre", sobre.render),
}


def _carregar_css() -> None:
    css_path = Path(__file__).parent / "style.css"
    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _coletar_stats(cfg: Configuracao) -> dict[str, str | int]:
    sessoes = (
        sorted(p for p in cfg.sessoes_dir.iterdir() if p.is_dir())
        if cfg.sessoes_dir.exists()
        else []
    )
    return {
        "versao": __version__,
        "n_sessoes": len(sessoes),
        "modelo_base": "nenhum"
        if not (cfg.modelos_dir / "base_v1.pkl").exists()
        else "base_v1",
    }


def main() -> None:
    st.set_page_config(
        page_title="Hemiciclo -- inteligência política aberta",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _carregar_css()

    cfg = Configuracao()
    cfg.garantir_diretorios()

    if "pagina_ativa" not in st.session_state:
        st.session_state["pagina_ativa"] = "intro"

    componentes.header_global(__version__)
    pagina = componentes.navegacao_principal(PAGINAS)
    PAGINAS[pagina][1](cfg)
    componentes.footer_global(_coletar_stats(cfg))


if __name__ == "__main__":
    main()
```

### 5.5 install.sh esqueleto

```bash
#!/usr/bin/env bash
# install.sh -- Bootstrap do Hemiciclo 2.0 (Linux/macOS).

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[Hemiciclo] Verificando Python 3.11+..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "[Hemiciclo] Erro: python3 nao encontrado." >&2
    echo "  Instale Python 3.11+ de https://python.org/downloads" >&2
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    echo "[Hemiciclo] Erro: Python $PY_VER detectado, requer 3.11+." >&2
    exit 1
fi

echo "[Hemiciclo] Python $PY_VER OK."

if ! command -v uv >/dev/null 2>&1; then
    echo "[Hemiciclo] Instalando uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

cd "$DIR"

if [ "${1:-}" = "--check" ]; then
    echo "[Hemiciclo] Modo --check: validacao OK, sem instalar."
    exit 0
fi

START=$(date +%s)
echo "[Hemiciclo] Sincronizando dependencias..."
uv sync --all-extras

END=$(date +%s)
DECORRIDO=$((END - START))
echo ""
echo "[Hemiciclo] Instalacao concluida em ${DECORRIDO}s."
echo "[Hemiciclo] Para iniciar: ./run.sh"
```

### 5.6 run.sh esqueleto

```bash
#!/usr/bin/env bash
# run.sh -- Sobe dashboard Streamlit em localhost:8501.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "[Hemiciclo] Subindo Streamlit em http://localhost:8501"
echo "[Hemiciclo] Ctrl+C para encerrar."

trap 'echo "[Hemiciclo] Encerrando..."; exit 0' INT

uv run streamlit run src/hemiciclo/dashboard/app.py \
    --server.headless=false \
    --server.port=8501
```

## 6. Testes

### 6.1 Unit (`tests/unit/test_modelo_sessao.py` -- 5 testes)

- `test_parametros_busca_topico_obrigatorio`
- `test_parametros_busca_camadas_default`
- `test_status_sessao_progresso_clamp_lower` -- progresso < 0 raise
- `test_status_sessao_progresso_clamp_upper` -- progresso > 100 raise
- `test_serializacao_round_trip` -- json -> model -> json igual

### 6.2 Unit (`tests/unit/test_dashboard_componentes.py` -- 3 testes via mocker)

- `test_navegacao_define_pagina_ativa` -- mocker patch st.button/st.session_state
- `test_card_sessao_renderiza_metadados` -- mock st.markdown captura strings
- `test_cta_primeira_pesquisa_aparece_se_vazia`

### 6.3 Integração (`tests/integracao/test_dashboard_smoke.py` -- 5 testes via AppTest)

```python
from streamlit.testing.v1 import AppTest

def test_app_carrega_sem_erro():
    at = AppTest.from_file("src/hemiciclo/dashboard/app.py", default_timeout=10)
    at.run()
    assert not at.exception

def test_intro_renderiza_titulo():
    at = AppTest.from_file("src/hemiciclo/dashboard/app.py")
    at.run()
    assert any("Hemiciclo" in m.value for m in at.markdown)
```

### 6.4 Smoke manual (executor reporta saída)

```
$ ./install.sh
[Hemiciclo] Verificando Python 3.11+... Python 3.11.x OK.
[Hemiciclo] Sincronizando dependencias...
[Hemiciclo] Instalacao concluida em XX s.
[Hemiciclo] Para iniciar: ./run.sh

$ ./run.sh
[Hemiciclo] Subindo Streamlit em http://localhost:8501
```

(Browser abre, intro narrativo aparece, navegação funciona, form valida.)

## 7. Proof-of-work runtime-real

**Comando local:**

```bash
$ ./install.sh --check && \
  uv run pytest tests/unit/test_modelo_sessao.py tests/unit/test_dashboard_componentes.py tests/integracao/test_dashboard_smoke.py -v && \
  uv run python -c "from streamlit.testing.v1 import AppTest; at = AppTest.from_file('src/hemiciclo/dashboard/app.py'); at.run(); print('OK' if not at.exception else f'FAIL: {at.exception}')"
```

**Saída esperada:**

```
[Hemiciclo] Modo --check: validacao OK, sem instalar.
13 passed
OK
```

(5 testes modelo + 3 componentes + 5 integração = 13.)

E `make check` continua passando com cobertura >= 90% nos arquivos novos.

**Critério de aceite (checkbox):**

- [ ] `./install.sh --check` passa em ambiente com Python 3.11+
- [ ] `./run.sh` sobe Streamlit em localhost:8501 sem erro
- [ ] Browser abre automaticamente
- [ ] Tela inicial mostra intro narrativo (storytelling tema.py STORYTELLING["intro"])
- [ ] Botão "Fazer minha primeira pesquisa" navega pra `nova_pesquisa`
- [ ] Form de Nova Pesquisa tem 7 inputs (tópico, casas, legislaturas, UFs, partidos, período, camadas)
- [ ] Form valida `ParametrosBusca` Pydantic e mostra erro se tópico vazio
- [ ] Botão "Iniciar pesquisa" exibe `st.info("Funcionalidade chega em S30")` e cria pasta de rascunho
- [ ] Página "Sobre" exibe manifesto longo (>= 300 palavras)
- [ ] Lista de sessões: vazia mostra CTA, com sessões mostra cards
- [ ] Tema visual aplicado (cores hex de tema.py visíveis no DOM)
- [ ] Footer mostra versão `0.1.0`, n_sessoes, modelo_base
- [ ] 13 testes passando (5+3+5)
- [ ] Cobertura >= 90% nos novos arquivos
- [ ] Mypy --strict zero erros
- [ ] Ruff zero violações
- [ ] CI verde nos 6 jobs do PR
- [ ] CHANGELOG.md atualizado
- [ ] `docs/usuario/instalacao.md` cobre Linux + macOS

## 8. Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| `streamlit.testing.v1.AppTest` incompatível com versão do Streamlit | B | A | Pinning `streamlit>=1.40` (AppTest estável desde 1.27) |
| CSS injetado quebrar em browsers diferentes | M | M | Testar manualmente Firefox + Chromium antes de DONE |
| Form Pydantic falhar silenciosamente em campos opcionais | M | M | Testes cobrem missing fields + erro mostrado em st.error |
| `install.sh` falhar em macOS Apple Silicon (uv binário ARM) | B | M | uv da Astral suporta arm64 macOS desde 0.4 |
| Streamlit auto-rerun causando piscadas em formulário | M | B | `st.form` com `clear_on_submit=False` |
| Sessão de rascunho sem `status.json` quebrar lista_sessoes | M | M | Tratamento defensivo: skip pasta sem status.json + log |
| Manifesto curto soar genérico | M | B | Reaproveitar trechos do plano R2 §1.3 (manifesto declarado) |

## 9. Validação multi-agente

**Executor (`executor-sprint`):**

1. Lê `VALIDATOR_BRIEF.md`.
2. Lê este spec.
3. Confirma branch `feature/s23-shell-visivel`.
4. Implementa entregas conforme passo a passo.
5. Roda smoke local + proof-of-work.
6. NÃO push, NÃO PR -- orquestrador integra.

**Validador (`validador-sprint`):**

1. Lê BRIEF + spec.
2. Roda proof-of-work independentemente.
3. Verifica I1-I12 (atenção especial a I2 PT-BR no manifesto, storytelling, mensagens UI).
4. **Aciona skill `validacao-visual`** porque diff toca `src/hemiciclo/dashboard/`.
5. Captura screenshot das 4 páginas + form preenchido + lista vazia.
6. Decide APROVADO / APROVADO_COM_RESSALVAS / REPROVADO.

## 10. Próximo passo após DONE

S24 + S25 em paralelo (coleta Câmara + Senado) e/ou S29 (sessão runner) podem iniciar. S36 (paridade Windows install.bat/run.bat) também desbloqueada.
