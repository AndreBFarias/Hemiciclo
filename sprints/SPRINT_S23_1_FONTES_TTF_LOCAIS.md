# Sprint S23.1 -- Fontes TTF locais (Inter + JetBrains Mono)

**Projeto:** Hemiciclo
**Versão alvo:** v2.1.0 (segunda sprint do nível 1 anti-débito)
**Data criação:** 2026-04-28 (descoberto pelo validador-sprint da S23 quando Google Fonts foi removido por ferir I1)
**Status:** DONE (2026-04-28)
**Depende de:** S23 (DONE)
**Bloqueia:** release público amplo (estética degradada em sistemas sem Inter/JetBrains Mono no fallback `system-ui`)
**Esforço:** P (1-2 dias)
**ADRs vinculados:** ADR-021 (fontes auto-hospedadas, Inter + JetBrains Mono sob SIL OFL 1.1)
**Branch:** feature/s23-1-fontes-ttf-locais

---

## 1. Objetivo

Bundlar **Inter** (4 pesos: 400/500/600/700) + **JetBrains Mono** (2 pesos: 400/700) como TTF local em `src/hemiciclo/dashboard/static/fonts/`, eliminando dependência de fonte externa do sistema. Quando S23 removeu o `@import url('https://fonts.googleapis.com/...')` por violar I1 (tudo local), o tema.py passou a depender de `system-ui` fallback — em máquinas sem essas fontes instaladas, estética degrada (Linux puro = DejaVu Sans, Windows = Segoe UI).

Esta sprint fecha o **segundo bloqueante de release público amplo** (após S27.1). Depois, o produto será autossuficiente esteticamente em qualquer máquina Linux/macOS/Windows sem internet.

## 2. Contexto

S23 entregou design tokens em `src/hemiciclo/dashboard/tema.py` declarando Inter + JetBrains Mono. Original plano: importar via Google Fonts. **Validador-sprint da S23 reprovou criticamente** porque feria I1 ("Tudo local. Nunca chamada a servidor central proprietário"). Fix inline: removido `@import` do `style.css`, fallback `system-ui` no tema.py — funcional mas estética inconsistente.

S23.1 fecha esse débito declarado. Aborda também a questão de **licenciamento**: ambas as fontes são SIL Open Font License v1.1, compatível com GPL v3 do projeto e redistribuíveis.

## 3. Escopo

### 3.1 In-scope

- [ ] **Baixar TTFs oficiais** (script de download determinístico):
  - Inter v4.0+ (Regular 400, Medium 500, SemiBold 600, Bold 700) — 4 arquivos
  - JetBrains Mono v2.304+ (Regular 400, Bold 700) — 2 arquivos
  - Total: 6 TTFs, ~600KB-1MB
  - Origens oficiais: `rsms.me/inter/` e `jetbrains.com/lp/mono/`
  - **Verificação SHA256** dos TTFs baixados contra hashes conhecidos (defesa contra bit-flip ou tampering)
- [ ] **Pasta `src/hemiciclo/dashboard/static/fonts/`** com 6 TTFs + arquivo `LICENSE` (SIL OFL 1.1) + `README.md` documentando origem e versão
- [ ] **`src/hemiciclo/dashboard/style.css`** atualizado:
  - 6 declarações `@font-face` apontando para `static/fonts/<nome>.ttf` via path relativo
  - Fallback `system-ui` mantido (defesa em profundidade caso fontes não carreguem)
  - Comentário explicando: "Fontes auto-hospedadas, sem CDN externa (I1)"
- [ ] **`src/hemiciclo/dashboard/app.py`** ajustado pra servir static via Streamlit:
  - Streamlit não tem static hosting nativo — usa hack canônico com `st.markdown(f"<style>@font-face {{ src: url('data:font/ttf;base64,{base64.b64encode(ttf).decode()}') }} </style>", unsafe_allow_html=True)`
  - OU: copiar TTFs pra `~/.streamlit/static/fonts/` no boot (mais simples, mas suja FS do user)
  - Recomendação: **base64 inline** no startup do app (custo ~1MB de markup, mas zero efeito colateral no FS)
  - Alternativa avaliada: usar `streamlit-extras` (lib externa) — rejeitada por ferir I6 (deps mínimas)
- [ ] **`scripts/baixar_fontes.py`** utilitário CLI:
  - Baixa os 6 TTFs das origens oficiais
  - Verifica SHA256 contra constantes embutidas
  - Salva em `src/hemiciclo/dashboard/static/fonts/`
  - Idempotente (não re-baixa se hashes batem)
  - Roda em `make bootstrap` apenas se TTFs ausentes (cache transversal)
- [ ] **`Makefile`** target novo `make fonts`:
  - Chama `python scripts/baixar_fontes.py`
  - Documenta em `make help`
- [ ] **`pyproject.toml`** declara `package_data` incluindo `dashboard/static/fonts/*.ttf`:
  - Quando a lib for empacotada (PyPI v2.1.x), TTFs vão junto
- [ ] **`docs/adr/ADR-021-fontes-auto-hospedadas.md`** registra decisão:
  - Por que não Google Fonts (I1)
  - Por que não system-ui puro (estética inconsistente)
  - Por que SIL OFL 1.1 é compatível com GPL v3
  - Por que base64 inline em vez de filesystem
- [ ] **Testes unit** em `tests/unit/test_dashboard_fontes.py` (5 testes):
  - `test_ttfs_existem_em_static_fonts`
  - `test_style_css_referencia_6_fontfaces`
  - `test_app_carrega_fontes_em_base64`
  - `test_fallback_system_ui_preservado`
  - `test_baixar_fontes_idempotente_se_hashes_batem`
- [ ] **`docs/arquitetura/ui_design_tokens.md`** novo:
  - Documenta paleta institucional + tipografia
  - Lista das 6 fontes + pesos disponíveis
  - Como adicionar peso novo (download + SHA256 + style.css)
- [ ] **CHANGELOG.md** entrada `[2.1.0-dev]` com bullet S23.1
- [ ] **`docs/adr/README.md`** atualizado com ADR-021

### 3.2 Out-of-scope

- **Variabilidade de fontes** (variable fonts) -- ficar com pesos discretos é mais leve
- **Subset Latin-Extended** (reduzir tamanho cortando glifos não-PT) -- otimização futura
- **Fontes para code highlighting** (Pygments) -- não usado ainda no produto
- **Customizar paleta para tema escuro** -- v2.x ou v3.x

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `src/hemiciclo/dashboard/static/fonts/Inter-Regular.ttf` | Inter 400 |
| `src/hemiciclo/dashboard/static/fonts/Inter-Medium.ttf` | Inter 500 |
| `src/hemiciclo/dashboard/static/fonts/Inter-SemiBold.ttf` | Inter 600 |
| `src/hemiciclo/dashboard/static/fonts/Inter-Bold.ttf` | Inter 700 |
| `src/hemiciclo/dashboard/static/fonts/JetBrainsMono-Regular.ttf` | JetBrains Mono 400 |
| `src/hemiciclo/dashboard/static/fonts/JetBrainsMono-Bold.ttf` | JetBrains Mono 700 |
| `src/hemiciclo/dashboard/static/fonts/LICENSE` | SIL OFL 1.1 |
| `src/hemiciclo/dashboard/static/fonts/README.md` | Origem + versão das fontes |
| `scripts/baixar_fontes.py` | Utilitário CLI |
| `docs/adr/ADR-021-fontes-auto-hospedadas.md` | ADR |
| `docs/arquitetura/ui_design_tokens.md` | Documentação |
| `tests/unit/test_dashboard_fontes.py` | 5 testes |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `src/hemiciclo/dashboard/style.css` | 6 `@font-face` apontando para TTFs locais |
| `src/hemiciclo/dashboard/app.py` | Inline base64 das fontes no boot |
| `Makefile` | Target `fonts` |
| `pyproject.toml` | `package_data` inclui TTFs |
| `docs/adr/README.md` | Índice com ADR-021 |
| `CHANGELOG.md` | Entrada [2.1.0-dev] |
| `sprints/ORDEM.md` | S23.1 -> DONE |

## 5. Implementação detalhada

### 5.1 Origens oficiais e SHA256

Inter v4.1 (rsms.me/inter):
- Inter-Regular.ttf: ~310KB
- Inter-Medium.ttf: ~310KB
- Inter-SemiBold.ttf: ~315KB
- Inter-Bold.ttf: ~315KB

JetBrains Mono v2.304 (jetbrains.com):
- JetBrainsMono-Regular.ttf: ~245KB
- JetBrainsMono-Bold.ttf: ~250KB

Total: ~1.7MB de TTFs (após compressão zip do release: ~1MB).

**Hashes esperados embedados em `scripts/baixar_fontes.py`:**

```python
HASHES_TTF = {
    "Inter-Regular.ttf": "sha256:<hash_real>",
    "Inter-Medium.ttf": "sha256:<hash_real>",
    "Inter-SemiBold.ttf": "sha256:<hash_real>",
    "Inter-Bold.ttf": "sha256:<hash_real>",
    "JetBrainsMono-Regular.ttf": "sha256:<hash_real>",
    "JetBrainsMono-Bold.ttf": "sha256:<hash_real>",
}
```

Executor calcula hashes reais ao baixar primeira vez e os fixa.

### 5.2 style.css com @font-face

```css
@font-face {
    font-family: 'Inter';
    src: url('static/fonts/Inter-Regular.ttf') format('truetype');
    font-weight: 400;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: 'Inter';
    src: url('static/fonts/Inter-Medium.ttf') format('truetype');
    font-weight: 500;
    font-style: normal;
}
/* ... outras 4 declarações ... */

:root {
    /* Tipografia agora prefere Inter local, fallback system-ui */
    --tipografia-titulo: 'Inter', system-ui, sans-serif;
    --tipografia-corpo: 'Inter', system-ui, sans-serif;
    --tipografia-mono: 'JetBrains Mono', 'JetBrainsMono', 'Courier New', monospace;
}
```

### 5.3 Inline base64 no app.py

```python
def _carregar_fontes_inline() -> str:
    """Retorna CSS com @font-face em data: URLs base64 (zero rede)."""
    import base64
    from pathlib import Path

    fontes_dir = Path(__file__).parent / "static" / "fonts"
    declaracoes = []
    mapa = {
        "Inter": [("Regular", 400), ("Medium", 500), ("SemiBold", 600), ("Bold", 700)],
        "JetBrainsMono": [("Regular", 400), ("Bold", 700)],
    }

    for familia, pesos in mapa.items():
        for nome, peso in pesos:
            ttf_path = fontes_dir / f"{familia}-{nome}.ttf"
            if not ttf_path.exists():
                continue
            ttf_b64 = base64.b64encode(ttf_path.read_bytes()).decode("ascii")
            mime = "font/ttf"
            family_css = "Inter" if familia == "Inter" else "JetBrains Mono"
            declaracoes.append(f"""
@font-face {{
    font-family: '{family_css}';
    src: url('data:{mime};base64,{ttf_b64}') format('truetype');
    font-weight: {peso};
    font-style: normal;
    font-display: swap;
}}
""")
    return "<style>" + "\n".join(declaracoes) + "</style>"


# No app.py:main(), antes de _carregar_css():
st.markdown(_carregar_fontes_inline(), unsafe_allow_html=True)
```

### 5.4 baixar_fontes.py esqueleto

```python
"""Baixa Inter + JetBrains Mono e verifica SHA256."""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

URLS = {
    "Inter-Regular.ttf": "https://github.com/rsms/inter/releases/download/v4.1/Inter-Desktop.zip#Inter-Regular.ttf",
    # ... ajustar para URLs realmente diretas. Pode exigir extração de zip.
}

HASHES_ESPERADOS: dict[str, str] = {
    # Preencher após primeiro download bem-sucedido
}

def baixar_e_verificar(nome: str, url: str, destino: Path) -> bool:
    if destino.exists():
        sha = hashlib.sha256(destino.read_bytes()).hexdigest()
        if HASHES_ESPERADOS.get(nome) == sha:
            print(f"[fontes] {nome}: já presente, hash OK")
            return True
    print(f"[fontes] baixando {nome} de {url}")
    # ... download ...
    return True

def main() -> int:
    dir_fontes = Path("src/hemiciclo/dashboard/static/fonts")
    dir_fontes.mkdir(parents=True, exist_ok=True)
    for nome, url in URLS.items():
        baixar_e_verificar(nome, url, dir_fontes / nome)
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### 5.5 Passo a passo

1. Confirmar branch.
2. Criar `src/hemiciclo/dashboard/static/fonts/` + `LICENSE` + `README.md`.
3. Implementar `scripts/baixar_fontes.py` com URLs oficiais de Inter v4.1 e JetBrainsMono v2.304.
4. Rodar script localmente, capturar SHA256 dos 6 TTFs, fixar em `HASHES_ESPERADOS`.
5. Atualizar `style.css` com 6 `@font-face`.
6. Atualizar `app.py` com `_carregar_fontes_inline()`.
7. Adicionar Makefile target `fonts`.
8. Atualizar `pyproject.toml` package_data.
9. Escrever `docs/adr/ADR-021-fontes-auto-hospedadas.md`.
10. Atualizar `docs/adr/README.md`.
11. Escrever `docs/arquitetura/ui_design_tokens.md`.
12. Escrever `tests/unit/test_dashboard_fontes.py` (5 testes).
13. Atualizar `CHANGELOG.md`.
14. Smoke local: subir Streamlit via `./run.sh`, verificar visualmente que tipografia Inter está aplicada.
15. `make check` ≥ 90%.
16. Atualizar `sprints/ORDEM.md`: S23.1 → DONE.

## 6. Testes (resumo)

- 5 unit + smoke visual (Streamlit) = **5 testes novos**
- Total: 496 + 5 = 501 testes

## 7. Proof-of-work runtime-real

```bash
$ make check
$ ls -la src/hemiciclo/dashboard/static/fonts/
$ uv run python scripts/baixar_fontes.py
$ uv run streamlit run src/hemiciclo/dashboard/app.py --server.headless=true --server.port=8501 &
sleep 5 && curl -s http://localhost:8501/_stcore/health
```

**Saída esperada:**

- `make check`: 501 testes verdes, cobertura ≥ 90%
- `ls`: 6 TTFs presentes + LICENSE + README
- baixar_fontes: hashes OK
- Streamlit: health endpoint retorna `ok`

**Critério de aceite:**

- [ ] 6 TTFs em `src/hemiciclo/dashboard/static/fonts/` versionados no git
- [ ] LICENSE SIL OFL 1.1 incluída
- [ ] `style.css` com 6 `@font-face` apontando para path relativo
- [ ] `app.py` inline base64 das fontes no boot
- [ ] `make check` 501 testes verdes, cobertura ≥ 90%
- [ ] Smoke visual: Streamlit renderiza com Inter aplicado
- [ ] `pyproject.toml` package_data inclui TTFs
- [ ] ADR-021 + ui_design_tokens.md documentados
- [ ] Mypy/ruff zero, CI verde

## 8. Riscos

| Risco | Mitigação |
|---|---|
| URL de download mudar (Google rsms.me cair) | Hashes SHA256 fixos validam integridade independente da URL; fallback documentado |
| TTFs >1MB engordam o repo | 1.7MB é razoável; LFS desnecessário |
| Inline base64 no Streamlit causa lag de boot >500ms | Cache `@st.cache_resource` no `_carregar_fontes_inline()` |
| Licença SIL OFL incompatível com GPL v3 | SFL OFL 1.1 é compatível (FSF aprovado), documentado em ADR-021 |
| package_data não inclui TTFs no build via uv | Verificar `uv build && uv pip show hemiciclo` antes de fechar |

## 9. Validação multi-agente

Padrão. Validador atenção a:
- Skill `validacao-visual` ATIVADA (diff toca dashboard/) — capturar screenshot validando que tipografia Inter está aplicada visivelmente
- I1 (tudo local) reforçado: zero URL externa em `style.css`/`app.py`
- I9 cobertura nos arquivos novos
- LICENSE SIL OFL 1.1 presente

## 10. Próximo passo após DONE

S36 (Windows install.bat + run.bat) — terceiro e último bloqueante de release público amplo.
