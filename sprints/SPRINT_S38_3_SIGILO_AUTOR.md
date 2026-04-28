# Sprint S38.3 -- Remover identificação do ex-empregador na aba Sobre (P0 LEGAL)

**Projeto:** Hemiciclo
**Versão alvo:** v2.1.1 (hotfix imediato)
**Data criação:** 2026-04-28
**Revisão:** 2026-04-28 (planejador-sprint -- complementos pós-grep em main)
**Autor:** @AndreBFarias
**Status:** READY
**Depende de:** --
**Bloqueia:** divulgação pública do projeto, qualquer release com manifesto longo, tag v2.1.1
**Esforço:** P (≤ 1h)
**ADRs vinculados:** --
**Branch sugerida:** `feature/s38-3-sigilo-autor` (NÃO usar nome do ex-empregador no slug da branch -- vaza via reflog e push)
**Prioridade:** **P0 -- BLOQUEANTE LEGAL**

---

## 1. Objetivo

Remover toda identificação de empregador, cliente ou contrato traceável do repositório Hemiciclo. Manter o **espírito político** do manifesto (inverter o vetor lobista→cidadão, crítica estrutural ao mercado de inteligência política privada) sem antecedente pessoal específico que permita identificar o ex-empregador do autor.

## 2. Contexto

O autor tem cláusula de NDA de 6 anos com ex-empregador (não nomear o ex-empregador neste spec; tratar sempre como "ex-empregador"). Multa potencial alta. Ferramenta vai a público; risco real de litigation. Bloqueia distribuição pública e qualquer release que inclua o manifesto longo.

Verificado em `main` em 2026-04-28 via grep do nome do ex-empregador (case-insensitive) em `docs/`, `src/`, `README.md`, `CHANGELOG.md` e `sprints/`:

| Arquivo | Linhas | Natureza |
|---|---|---|
| `docs/manifesto.md` | 18 (e §contexto inicial) | Autobiografia identificadora -- "passou anos no [ex-empregador] entregando perfilamento" |
| `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` | 52, 1732 | §1.4 "Lente do autor" + conclusão equiparando rigor metodológico |
| `sprints/SPRINT_S38_RELEASE_V2.md` | 46, 143 | Spec da release v2.0.0 cita histórico do autor como conteúdo do manifesto |
| `sprints/ORDEM.md` | 62, 133 | Linha desta própria sprint (62) + entrada de log (133) descrevendo a expansão do manifesto na S38 |
| `CHANGELOG.md` | 13, 527 | Entrada `[Unreleased]` desta sprint (13) + entrada histórica `[2.0.0]` (527) descrevendo histórico do autor |

A página `src/hemiciclo/dashboard/paginas/sobre.py` carrega `docs/manifesto.md`; saneamento do markdown propaga automaticamente, mas a página deve ser smoke-testada após o edit.

## 3. Escopo

### 3.1 In-scope

Sanitizar **todos os 5 arquivos da tabela acima**:

- **`docs/manifesto.md`** -- reescrever §contexto autobiográfico removendo nome do ex-empregador e qualquer frase em primeira pessoa que identifique vínculo empregatício específico ("passou anos no X", "trabalhei em Y", "cientista de dados no Z"). Manter:
  - Crítica estrutural ao mercado de inteligência política privada como produto vendido a poucos.
  - Manifesto técnico-político de tornar essa inteligência um bem comum.
  - Tom direto, sóbrio, sem ressentimento pessoal.
  - As 3 voltas concretas e a justificativa GPL v3.
- **`docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` §1.4 ("Lente do autor") + conclusão linha 1732** -- reescrever em terceira pessoa genérica ("o autor traz experiência prévia em perfilamento comportamental quantitativo aplicado a clientes corporativos") sem nomear ex-empregador. A força argumentativa do design fica preservada.
- **`sprints/SPRINT_S38_RELEASE_V2.md` linhas 46 e 143** -- spec histórica de release; substituir token do ex-empregador por "ex-empregador" / "experiência prévia do autor". Não reescrever a sprint inteira.
- **`sprints/ORDEM.md` linhas 62 e 133** -- linha 62 é desta sprint (renomear título para "Sigilo: sanitiza manifesto.md + paginas/sobre.py + specs"); linha 133 é log histórico que cita o token, sanear in-place trocando por "ex-empregador".
- **`CHANGELOG.md` linhas 13 e 527** -- linha 13 é entrada `[Unreleased]` desta sprint (atualizar título); linha 527 é entrada histórica `[2.0.0]`, sanear in-place.

Validar `src/hemiciclo/dashboard/paginas/sobre.py` -- se renderiza markdown direto via `Path.read_text()`, automático; se tem strings hardcoded com identificador, ajustar.

### 3.2 Out-of-scope

- Reformatar visualmente a aba Sobre (S38.5 cobre tema)
- Conteúdo educativo/onboarding (sprint futura)
- Reescrita do manifesto além do necessário para sanitização (preservar o resto)
- **Saneamento do histórico git** -- decisão do autor (decisão registrada 2026-04-28: opção `b` -- reescrever histórico via `git filter-repo` OU recriação do repositório). Vira sprint **S38.3.1** dedicada, executada **antes da tag v2.1.1**.
- **GitHub Releases v2.0.0 e v2.1.0 já publicadas** -- decisão do autor (decisão registrada 2026-04-28: opção `c` -- saneia o markdown em `main` mas mantém release notes do GitHub intocadas). O conteúdo público das releases históricas fica como está; futuro fica saneado.

### 3.3 NÃO tocar

- ADRs (`docs/adr/`) -- já não citam ex-empregador (verificado: zero hits em `docs/adr/`)
- `README.md` -- já não cita ex-empregador (verificado: zero hits)
- Código `src/` fora de `dashboard/paginas/sobre.py` -- não menciona ex-empregador

## 4. Proof-of-work

### 4.1 Comandos de verificação (após edits, todos devem passar)

```bash
# (a) Token do ex-empregador zero hits no repo (exceto este próprio spec)
grep -rin "<TOKEN_DO_EX_EMPREGADOR>" docs/ src/ README.md CHANGELOG.md sprints/ \
  | grep -v "SPRINT_S38_3_SIGILO_AUTOR.md"
# esperado: zero linhas

# (b) Frases-tipo de autobiografia identificadora -- zero hits em manifesto e specs
grep -in "trabalhei\|passei anos\|cientista de dados no\|netnógrafo no" \
  docs/manifesto.md \
  docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md
# esperado: zero linhas (ou apenas contexto genérico, jamais primeira pessoa traceável)

# (c) Smoke do dashboard renderizando aba Sobre
uv run streamlit run src/hemiciclo/dashboard/app.py --server.headless true &
sleep 5
# abrir manualmente em browser, navegar para aba Sobre, confirmar render sem erro
# (validacao-visual skill: PNG + sha256 da aba Sobre saneada)

# (d) Suite completa continua verde
make check
# esperado: 477+ testes verdes, ruff/mypy zero violações, cobertura ≥ 90%

# (e) Lint específico em PT-BR (acentuação dos arquivos modificados)
# inspeção visual + grep por mojibake típico (Ã, Â seguidos de outros chars)
grep -n "Ã[^O]\|Â " docs/manifesto.md \
  docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md \
  CHANGELOG.md sprints/ORDEM.md sprints/SPRINT_S38_RELEASE_V2.md
# esperado: zero hits
```

### 4.2 Critérios de aceite (checklist)

- [ ] Comando (a) retorna zero linhas
- [ ] Comando (b) retorna zero linhas
- [ ] Comando (c): aba Sobre renderiza sem erro, screenshot anexado ao PR
- [ ] Comando (d): `make check` verde
- [ ] Comando (e): zero mojibake nos arquivos modificados
- [ ] Manifesto preserva crítica estrutural ao mercado de inteligência política (não foi sanitizado a ponto de virar texto técnico neutro)
- [ ] Branch nomeada `feature/s38-3-sigilo-autor` (sem token do ex-empregador no slug)
- [ ] Commits seguem Conventional Commits (`docs:` ou `chore:`); mensagem do commit também NÃO cita o ex-empregador pelo nome

## 5. Cláusula de merge (CRÍTICA)

**Orquestrador NÃO mergeia automaticamente.** PR aberto = entrega da sprint. Merge fica suspenso aguardando **aprovação textual explícita do autor** (`@AndreBFarias`) após leitura completa do manifesto e specs saneados. Nenhum agente Claude (executor, validador, orquestrador) pode mergear esta sprint sem aprovação textual no PR ou via instrução direta.

Razão: risco legal real (NDA 6 anos, multa potencial alta) torna esta a única sprint do projeto onde "CI verde + validador OK" é condição **necessária mas não suficiente** para merge.

## 6. Riscos

- **Risco principal:** sanitizar demais e perder a força política do manifesto. Mitigação: manter crítica estrutural ao mercado de inteligência política privada -- remover apenas autobiografia identificadora. O manifesto continua falando de "o que se vende a lobistas" no abstrato, sem confessar pertencimento.
- **Risco secundário:** vazamento do token via reflog/branch name/commit message. Mitigação: branch `feature/s38-3-sigilo-autor`, commits com mensagem genérica (`docs: sanitiza manifesto -- remoção de identificadores autobiográficos`).
- **Risco terciário:** PR aberto fica visível no GitHub mesmo sem merge. Mitigação: corpo do PR também não cita ex-empregador pelo nome; descreve a remoção em termos genéricos ("remoção de identificadores autobiográficos do manifesto e specs de design conforme S38.3").
- **Risco quaternário:** histórico do git (commits anteriores em main) já contém o token. Fora do escopo desta sprint -- coberto pela sprint **S38.3.1** (saneamento de histórico via `git filter-repo` ou recriação de repositório), decisão `b` do autor registrada 2026-04-28, a executar antes da tag `v2.1.1`.

## 7. Próximo passo após DONE

1. Sprint **S38.3.1** -- saneamento do histórico git (decisão `b`) **antes** da tag v2.1.1.
2. Bumpa para v2.1.1 junto com S38.4-S38.8 do plano hotfix. Tag e release notes não citam ex-empregador.

## 8. Referências

- BRIEF: `VALIDATOR_BRIEF.md` -- I2 (PT-BR), I10 (Conventional Commits), I12 (CHANGELOG atualizado)
- Plano v2.1.1: `dev-journey/06-sprints/...` (commit `14a737d`)
- Memória do projeto: `feedback_smoke_real_browser_obrigatorio.md` (justifica §4.1.c smoke real)
