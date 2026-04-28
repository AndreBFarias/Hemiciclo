# ADR-021 -- Fontes auto-hospedadas (Inter + JetBrains Mono) sob SIL OFL 1.1

- **Status:** accepted
- **Data:** 2026-04-28
- **Decisores:** @AndreBFarias
- **Tags:** ux, infra, licenca

## Contexto e problema

S23 entregou design tokens em `tema.py` declarando `Inter` (texto) e `JetBrains Mono` (código), originalmente importadas via Google Fonts (`@import url('https://fonts.googleapis.com/...')`).

**Validador-sprint da S23 reprovou criticamente** porque cada visita ao dashboard sangrava IP do usuário pra Google Fonts -- violação direta de I1 do BRIEF ("Tudo local. Nunca chamada a servidor central proprietário em código de produção"). Fix inline: `@import` removido, fallback `system-ui` no tema.py.

Resultado: estética degrada em sistemas sem Inter/JetBrains Mono no fallback de sistema (Linux puro = DejaVu Sans, Windows pré-Win11 = Segoe UI antigo). Dashboard fica visualmente inconsistente entre máquinas de usuários cidadãos.

## Drivers de decisão

- **I1** (tudo local): zero dependência de CDN externa em runtime.
- **Manifesto político**: produto cidadão sem rastreio de terceiros.
- **Estética consistente** entre Linux/macOS/Windows.
- **Licença** redistribuível compatível com GPL v3 do projeto.
- **Tamanho razoável** do repo (não inflar via git LFS desnecessário).

## Opções consideradas

### Opção A -- system-ui puro (sem fonte custom)

- Prós: zero overhead, nenhum arquivo extra.
- Contras: estética degrada em sistemas sem Inter; tipografia inconsistente arruína storytelling sóbrio do tema institucional.

### Opção B -- Bundlar TTFs locais sob OFL

- Prós: estética garantida em qualquer sistema; offline; auditável.
- Contras: ~2.2 MB extras no repo; processo de atualização manual via `scripts/baixar_fontes.py`.

### Opção C -- Variable fonts + WOFF2

- Prós: ainda menor que TTF separados.
- Contras: maior complexidade, sem ganho perceptível; Streamlit aceita TTF nativamente via base64.

### Opção D -- WOFF2 separados em static/fonts/

- Prós: ~30% menor que TTF.
- Contras: incompatibilidade com browsers antigos é hoje irrelevante, mas TTF é mais universal e diff entre formatos não compensa.

## Decisão

Escolhida: **Opção B** -- Bundlar TTFs Inter + JetBrains Mono em `src/hemiciclo/dashboard/static/fonts/` sob SIL OFL 1.1, expostos no Streamlit via `_carregar_fontes_inline()` que injeta `@font-face` com `data: URLs` base64.

Justificativa:

1. **Tudo local definitivamente** -- TTF embedados base64 inline no HTML, sem nem mesmo I/O para `static/fonts/` em runtime. Cache `@st.cache_resource` evita custo recorrente.
2. **SIL OFL 1.1** é compatível com GPL v3 do projeto (FSF aprovou explicitamente). Permite redistribuição + modificação + uso comercial.
3. **2.2 MB no repo** é aceitável (`< 5 MB threshold`); git LFS desnecessário.
4. **Origem oficial verificada via SHA256** em `scripts/baixar_fontes.py:HASHES_ESPERADOS` -- defesa contra bit-flip ou tampering.
5. **Fallback `system-ui`** mantido como defesa em profundidade caso TTFs não carreguem (cinto + suspensório).

## Consequências

### Positivas

- Hemiciclo passa a ser **autossuficiente esteticamente** em qualquer máquina Linux/macOS/Windows sem internet.
- Zero rastreio de Google sobre quem visita o dashboard.
- LICENSE clara + auditável.
- Atualização determinística via `make fonts` ou `python scripts/baixar_fontes.py`.

### Negativas / custos assumidos

- Repo cresce ~2.2 MB.
- HTML do dashboard cresce ~3 MB (base64 overhead 37%) -- mas `@st.cache_resource` paga só uma vez por sessão.
- Atualização das fontes exige rodar script manualmente quando upstream lançar nova versão.
- Mantém binários em git (não em LFS); operações `git clone` levam ~2 segundos extras.

## Pendências / follow-ups

- [ ] Variable fonts: avaliar em sprint dedicada se overhead de pesos discretos virar problema.
- [ ] Subset Latin-Extended-A: pode reduzir TTF em ~40% se ficar limitante.
- [ ] WOFF2 em paralelo aos TTFs: ainda menor; só vale se otimização de boot virar prioridade.

## Links

- Spec: `sprints/SPRINT_S23_1_FONTES_TTF_LOCAIS.md`
- Plano R2: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md`
- SIL OFL 1.1: https://scripts.sil.org/cms/scripts/page.php?item_id=OFL_web
- ADR anterior relacionado: ADR-010 (shell visível primeiro -- onde Streamlit foi escolhido)
