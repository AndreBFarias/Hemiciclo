# Sprint S21 -- Higienização do Hemiciclo (4/10 -> 10/10)

**Projeto:** Hemiciclo (ex-Ranking-Congressistas)
**Data:** 2026-04-16
**Saúde anterior:** 4/10
**Saúde final:** 10/10

---

## Escopo

Higienização completa seguindo o padrão de referência do portfólio: reestruturação em `src/`, extração de funções puras para biblioteca testável, remoção de comentários dramáticos, criação de documentação comunitária, testes `testthat`, CI em GitHub Actions, `DESCRIPTION` e scripts de instalação.

---

## Entregas

### Estrutura
- [x] `src/lib/rtf.R` -- decode_rtf extraída do código legado
- [x] `src/lib/ranking.R` -- normalizar_minmax, calcular_score_conversao, juntar_ranking
- [x] `src/lib/api.R` -- wrappers de APIs (Câmara/Senado) e gerar_intervalos_mensais
- [x] `src/coleta/camara.R` -- refatorado com imports relativos e paralelismo configurável
- [x] `src/coleta/senado.R` -- refatorado
- [x] `src/ranking/deputados.R` -- refatorado usando lib
- [x] `src/ranking/senadores.R` -- refatorado usando lib
- [x] Removido `README.md.final` (duplicata)
- [x] Removido `setwd("~/Desktop/DiscursosCongresso")` hardcoded
- [x] Limpos cabeçalhos "Ritual de Magia Negra Digital" dos 4 scripts originais

### Testes
- [x] `tests/testthat.R` -- bootstrap
- [x] `tests/testthat/helper-raiz.R` -- helper para localizar raiz do projeto
- [x] `tests/testthat/test-rtf.R` -- 3 testes (null/vazio, marcadores RTF, acentuação)
- [x] `tests/testthat/test-ranking.R` -- 6 testes (min-max, amplitude zero, vazio, score, validação, join)
- [x] `tests/testthat/test-api.R` -- 5 testes (URL senador, URL câmara, intervalos, validações)
- **Total: 14 testes** (supera o mínimo de 3-5 previsto no plano)

### Documentação
- [x] `README.md` reescrito com nova estrutura, badge CI, metodologia, remoção de referências a "Ranking Congressistas"
- [x] `CONTRIBUTING.md` adaptado para stack R (style guide tidyverse, testthat)
- [x] `CODE_OF_CONDUCT.md` com escopo adicional sobre dados parlamentares
- [x] `SECURITY.md` adaptado (APIs públicas, dados não sensíveis)
- [x] `CHANGELOG.md` atualizado com entrada 2.0.0

### Metadata
- [x] `DESCRIPTION` -- metadados R padrão com Depends/Imports/Suggests
- [x] `.mailmap` -- unificação de identidade
- [x] `.gitignore` expandido com renv/, *.rds, evidências de desenvolvimento

### CI/CD
- [x] `.github/workflows/ci.yml` -- setup-r, install deps, lintr, testthat, validação DESCRIPTION

### Packaging
- [x] `install.sh` -- instala pacotes R
- [x] `uninstall.sh` -- remove pacotes R (com confirmação)

---

## Checklist 13 itens (padrão do portfólio)

| # | Item | Status |
|---|------|--------|
| 1 | LICENSE GPLv3 | já existia |
| 2 | README.md (PT-BR, zero emoji/IA) | feito |
| 3 | CONTRIBUTING.md | criado |
| 4 | CODE_OF_CONDUCT.md | criado |
| 5 | SECURITY.md | criado |
| 6 | CHANGELOG.md | atualizado |
| 7 | Estrutura src/ | reorganizado |
| 8 | Testes (testthat) | 14 testes |
| 9 | CI/CD GitHub Actions | criado |
| 10 | .gitignore | expandido |
| 11 | .mailmap | criado |
| 12 | DESCRIPTION | criado |
| 13 | install.sh / uninstall.sh | criados |

**13/13 completos. Saúde: 10/10.**

---

## Próximos Passos

- Sprint S22: TerritorialGuard (3/10 -> 10/10)

---

*"A palavra pública é o solo onde a liberdade se enraíza." -- Hannah Arendt*
