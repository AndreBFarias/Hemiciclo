# Workflow de desenvolvimento -- Hemiciclo 2.0

Este documento descreve o ciclo completo de contribuição: do clone do repositório à fusão do PR em `main`. Leia em conjunto com `VALIDATOR_BRIEF.md` (invariantes) e `sprints/ORDEM.md` (status global das sprints).

## 1. Pré-requisitos

- Python 3.11 ou superior (`python --version`)
- Git 2.40+
- `uv` (instalado automaticamente por `scripts/bootstrap.sh` ou `scripts/bootstrap.bat`)
- Conta GitHub com 2FA habilitado para abrir PRs
- Editor compatível com `.editorconfig` e `pyproject.toml` (VS Code recomendado, configuração já em `.vscode/`)

## 2. Clone e setup inicial

```bash
git clone https://github.com/AndreBFarias/Hemiciclo.git
cd Hemiciclo
./scripts/bootstrap.sh        # Linux / macOS
scripts\bootstrap.bat         # Windows
make check                    # confirma ambiente saudável
```

`make check` deve terminar com `tests passing` e cobertura ≥ 90%. Se falhar logo após o clone, abra issue com a saída completa antes de prosseguir.

## 3. Convenção de branches

| Prefixo | Uso | Exemplo |
|---|---|---|
| `feature/sNN-<slug>` | Sprint do roadmap | `feature/s37-ci` |
| `fix/<id>-<slug>` | Correção pontual | `fix/124-mypy-windows` |
| `docs/<slug>` | Apenas documentação | `docs/atualiza-readme` |
| `chore/<slug>` | Infraestrutura sem produto | `chore/limpa-caches` |

Branches são criadas a partir de `main` atualizada:

```bash
git checkout main
git pull origin main
git checkout -b feature/s37-ci
```

Branches são apagadas após merge (não reaproveitadas para outras sprints).

## 4. Conventional Commits (I10)

Toda mensagem segue `<tipo>(<escopo>): descrição` em PT-BR direto, sem emojis, sem menções a IA. Tipos válidos: `feat`, `fix`, `refactor`, `docs`, `test`, `perf`, `chore`, `style`, `ci`, `build`, `release`.

```
feat(s37): scripts/validar_adr.py validador MADR
fix(s27): regex de meio-ambiente cobre acentuação composta
ci(s37): adiciona workflow ci.yml com matriz multi-OS
docs(adr): adiciona ADR-012 sobre cache transversal
```

Commits atômicos pequenos são preferíveis a um commit único gigante. PRs com 3-8 commits coerentes ajudam a revisão. Cada commit deve manter `make check` verde -- nunca faça commit em estado quebrado deliberadamente.

## 5. Ciclo de mudança

1. Criar branch (seção 3).
2. Implementar a mudança em commits atômicos (seção 4).
3. Rodar `make check` localmente; corrigir até passar.
4. Atualizar `CHANGELOG.md` adicionando bullet em `## [Unreleased]` (I12).
5. `git push -u origin feature/sNN-<slug>`.
6. Abrir PR usando o template em `.github/PULL_REQUEST_TEMPLATE.md`.

## 6. CI -- o que roda em cada PR

Cada PR aciona `.github/workflows/ci.yml` com matriz `{ubuntu-22.04, macos-14, windows-2022} x {Python 3.11, Python 3.12}` -- 6 jobs em paralelo, `fail-fast: false`.

Cada job executa, em sequência:

1. `uv sync --frozen --all-extras` (falha se `uv.lock` divergir de `pyproject.toml`)
2. `uv run python scripts/validar_adr.py` (formato MADR dos ADRs)
3. `uv run ruff check src tests` (I8)
4. `uv run ruff format --check src tests` (I8)
5. `uv run mypy --strict src` (I7)
6. `uv run pytest tests/unit tests/integracao --cov=src/hemiciclo --cov-report=xml`

Coverage XML é enviado ao Codecov apenas pelo job `ubuntu-22.04 + python-3.11` para evitar uploads sobrepostos. PRs que tocam `docs/adr/**` também acionam `.github/workflows/adr-check.yml` separadamente.

Critério para merge: **todos os 6 jobs verdes** + revisão aprovada do CODEOWNER.

## 7. Validação de ADRs

Antes de criar/editar ADR:

- Numeração sequencial (próximo número livre em `docs/adr/`).
- Filename `ADR-NNN-titulo-com-hifens.md` em ASCII puro.
- Cabeçalho `# ADR-NNN -- titulo`.
- Metadados obrigatórios: `**Status:**`, `**Data:**`, `**Decisores:**`, `**Tags:**`.
- Seções: `## Contexto`, `## Decisão`, `## Consequências`.
- Atualizar `docs/adr/README.md` com a nova entrada.

Localmente:

```bash
uv run python scripts/validar_adr.py
```

Se retornar `[validar_adr] N ADRs validados em docs/adr/. Zero erros.`, pode commitar.

## 8. Code review

- Revisor avalia: clareza da mensagem de commit, aderência aos invariantes do `VALIDATOR_BRIEF.md`, consistência com ADRs vinculados, qualidade dos testes, ausência de débito técnico (princípio anti-débito).
- Sugestões grandes que excedem o escopo da sprint vão para spec de sprint nova (`sprints/SPRINT_S<N+1>_*.md`), não para o PR atual.
- Aprovação requer: ao menos 1 review do CODEOWNER + CI verde + checklist do PR template completo.

## 9. Merge strategy

- Estratégia oficial: **squash merge** ou **rebase merge** (escolha do mantenedor caso a caso).
- Squash: para sprints com muitos commits de iteração rápida.
- Rebase: para sprints com commits coerentes que merecem preservação histórica.
- Nunca usar merge commit (cria histórico em árvore desnecessariamente).
- Após merge: branch é deletada no GitHub e localmente (`git branch -d feature/sNN-<slug>`).

## 10. Branch protection (configuração manual no GitHub)

Esta sprint (S37) **não** automatiza as regras de proteção via API/CLI -- elas são configuradas manualmente no GitHub UI uma única vez. O mantenedor deve aplicar em `Settings > Branches > Add rule` para `main`:

- [x] Require a pull request before merging
- [x] Require approvals: 1
- [x] Dismiss stale pull request approvals when new commits are pushed
- [x] Require review from Code Owners
- [x] Require status checks to pass before merging:
  - `test (ubuntu-22.04, 3.11)` (mínimo obrigatório)
  - `test (ubuntu-22.04, 3.12)` (recomendado)
  - `validate-adr` (quando PR toca `docs/adr/**`)
- [x] Require branches to be up to date before merging
- [x] Require linear history
- [x] Restrict who can push to matching branches: somente `@AndreBFarias` (ajustar conforme equipe cresce)
- [ ] Allow force pushes: **NÃO**
- [ ] Allow deletions: **NÃO**

Documentado aqui em vez de automatizado para evitar dependência de token específico no CI desta sprint.

## 11. Releases

Releases são criadas via tag anotada `v<MAJOR>.<MINOR>.<PATCH>`:

```bash
make release VERSION=2.0.0
# expande para:
git tag -a v2.0.0 -m "Release v2.0.0"
git push origin v2.0.0
```

A tag aciona `.github/workflows/release.yml`, que reaproveita a matriz de CI antes de qualquer publicação. A etapa `publish` ainda é placeholder -- implementação completa fica para a sprint S38 (artefatos versionados, modelo base com hash SHA256).

## 12. Recurso para dúvidas

- Spec mestre: `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md`
- ADRs: `docs/adr/`
- Invariantes: `VALIDATOR_BRIEF.md`
- Status global: `sprints/ORDEM.md`
- Discussions: <https://github.com/AndreBFarias/Hemiciclo/discussions>

Para vulnerabilidades de segurança, **não abra issue pública**. Siga o procedimento descrito em `SECURITY.md`.
