# UI Design Tokens -- Hemiciclo

Documento de referência sobre paleta, tipografia, espaçamento e fontes auto-hospedadas do dashboard Streamlit. Fonte canônica em código: `src/hemiciclo/dashboard/tema.py`.

## 1. Paleta institucional

Inspirada em institucional sóbrio, **não-partidária**: nada que evoque diretamente vermelho de partido A ou azul de partido B. A escolha é uma combinação azul-marinho/ouro/terra-cota que sinaliza Estado/serviço público sem gramática partidária explícita.

| Token | Hex | Uso |
|---|---|---|
| `AZUL_HEMICICLO` | `#1E3A5F` | Primary -- títulos, header, eixos primários |
| `AZUL_CLARO` | `#4A7BAB` | Primary-light -- volatilidade, links secundários |
| `AMARELO_OURO` | `#D4A537` | Accent -- intensidade, destaque cidadão (Brasil sem ser kitsch) |
| `VERDE_FOLHA` | `#3D7A3D` | Success / a-favor / centralidade |
| `VERMELHO_ARGILA` | `#A8403A` | Danger / contra / hipocrisia |
| `CINZA_PEDRA` | `#4A4A4A` | Neutral-strong, texto base, enquadramento |
| `CINZA_AREIA` | `#E8E4D8` | Neutral-light, fundos de seção |
| `BRANCO_OSSO` | `#FAF8F3` | Background principal (não branco puro) |

Cor adicional para o eixo de **convertibilidade**: `#8B5A3C` (marrom terra, neutro complementar -- evita brigar com posição/intensidade no radar).

**Acessibilidade:** combinações texto/fundo do dashboard mantêm contraste mínimo WCAG AA. Cores nunca são canal único de informação -- todo gráfico colorido tem rótulo textual ou ícone redundante.

## 2. Tipografia

| Função | Família CSS | Peso default |
|---|---|---|
| Título | `Inter, system-ui, sans-serif` | 700 (Bold) |
| Corpo | `Inter, system-ui, sans-serif` | 400 (Regular) / 500 (Medium) / 600 (SemiBold) |
| Mono / código / versão / hashes | `JetBrains Mono, monospace` | 400 / 700 |

### 2.1 Por que Inter + JetBrains Mono

- **Inter** (Rasmus Andersson, 2016+) -- sem-serifa humanista pensada para UI em telas pequenas; estado-da-arte em legibilidade; SIL OFL 1.1.
- **JetBrains Mono** (JetBrains, 2020+) -- monoespaçada com ligaduras opcionais; otimizada para código/dados; SIL OFL 1.1.

### 2.2 Auto-hospedagem (S23.1)

ADR-021 decidiu **bundlar TTFs locais** em `src/hemiciclo/dashboard/static/fonts/`, embedando-os inline via base64 dentro do HTML do Streamlit. Motivos:

1. **Invariante I1 do BRIEF: tudo local.** Zero `@import` para Google Fonts em runtime -- nenhum IP do usuário sangra para CDN externa só por abrir o dashboard.
2. **Manifesto político.** Produto cidadão sem rastreio de terceiros.
3. **Estética consistente** entre Linux/macOS/Windows -- mesma tipografia em qualquer máquina.
4. **Licença redistribuível.** SIL Open Font License 1.1 é compatível com GPL v3 do projeto.

Os 6 TTFs (4 pesos Inter + 2 pesos JetBrains Mono) são lidos uma vez por sessão, codificados em base64 e injetados como `<style>@font-face ...</style>` no header do Streamlit. Cache via `@st.cache_resource` paga o custo de leitura+encoding apenas uma vez por processo. Fallback `system-ui` permanece no `style.css` como defesa em profundidade.

### 2.3 Verificação de integridade

`scripts/baixar_fontes.py` valida SHA256 de cada TTF contra tabela embedada. Origens oficiais:

- Inter v4.0 -- https://github.com/rsms/inter/releases (extras/ttf/)
- JetBrains Mono v2.304 -- https://www.jetbrains.com/lp/mono/

Comando: `make fonts` ou `uv run python scripts/baixar_fontes.py`.

## 3. Espaçamento (escala 4-base)

| Token | px | Uso |
|---|---|---|
| `xs` | 4 | Gap mínimo (badges, ícone+texto) |
| `sm` | 8 | Padding compacto |
| `md` | 16 | Padding default de cards |
| `lg` | 24 | Margem entre seções |
| `xl` | 32 | Margem entre blocos principais |
| `xxl` | 48 | Margem topo/rodapé do dashboard |

## 4. Storytelling por aba

Cada aba do dashboard começa com uma frase-pergunta de tom direto, no espírito do projeto referência `stilingue-energisa-etl`. Mantidas em `STORYTELLING` no `tema.py` -- uma única fonte de verdade.

## 5. Mapa de cores por aba

Para coerência entre header, navegação e ênfase visual:

| Aba | Cor principal |
|---|---|
| `intro` | `AZUL_HEMICICLO` |
| `lista_sessoes` | `AZUL_CLARO` |
| `nova_pesquisa` | `AMARELO_OURO` (call-to-action cidadã) |
| `sobre` | `CINZA_PEDRA` (texto institucional) |

## 6. Cores dos 7 eixos (assinatura indutiva D4)

Mantêm a paleta institucional sem inventar gramática nova; cada eixo recebe uma cor dedicada para legibilidade no radar e nos heatmaps.

| Eixo | Cor | Token |
|---|---|---|
| Posição | `#1E3A5F` | `AZUL_HEMICICLO` |
| Intensidade | `#D4A537` | `AMARELO_OURO` |
| Hipocrisia | `#A8403A` | `VERMELHO_ARGILA` |
| Volatilidade | `#4A7BAB` | `AZUL_CLARO` |
| Centralidade | `#3D7A3D` | `VERDE_FOLHA` |
| Convertibilidade | `#8B5A3C` | (marrom terra) |
| Enquadramento | `#4A4A4A` | `CINZA_PEDRA` |

## 7. Como evoluir

- Cores e tipografia mudam **apenas via ADR**. Trocar paleta sem ADR é vazamento de identidade visual.
- Adições à paleta (ex.: cor de aviso laranja) entram primeiro em `tema.py` e só depois aparecem em `style.css`.
- Atualização das fontes: rodar `scripts/baixar_fontes.py` após upstream lançar nova versão; recalcular `HASHES_ESPERADOS`; abrir PR vinculado a sprint nova de "atualização de fontes".

## Links

- `src/hemiciclo/dashboard/tema.py` -- fonte canônica dos tokens
- `src/hemiciclo/dashboard/style.css` -- aplicação CSS dos tokens
- `src/hemiciclo/dashboard/static/fonts/README.md` -- TTFs versionados, origens e licença
- ADR-021 -- decisão de auto-hospedagem das fontes
- Plano R2 §10.2 -- design tokens originais
