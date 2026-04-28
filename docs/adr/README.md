# Architecture Decision Records (ADRs) -- Hemiciclo 2.0

Este diretório contém as decisões arquiteturais imutáveis do projeto. Mudar uma decisão exige criar um novo ADR no estado `superseded by ADR-XXX`, nunca editar o anterior.

Formato: [MADR](https://adr.github.io/madr/) adaptado, conforme seção 4.1 do plano R2 em `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md`.

## Índice

| ADR | Título | Status | Vincula |
|---|---|---|---|
| [ADR-001](ADR-001-migracao-para-python.md) | Migração de R para Python 3.11+ com Streamlit | accepted | D1 |
| [ADR-002](ADR-002-voto-nominal-espinha-dorsal.md) | Voto nominal como fonte primária de posição parlamentar | accepted | D2 |
| [ADR-003](ADR-003-mapeamento-topico-hibrido.md) | Mapeamento tópico → proposições via híbrido (regex + categoria + YAML) | accepted | D3 |
| [ADR-004](ADR-004-assinatura-7-eixos.md) | Assinatura multidimensional com 7 eixos definidos | accepted | D4 |
| [ADR-005](ADR-005-caminho-indutivo.md) | Caminho indutivo data-driven (não dedutivo-teórico) | accepted | D5 |
| [ADR-006](ADR-006-arquitetura-100-local.md) | Arquitetura 100% local, sem servidor central | accepted | D6 |
| [ADR-007](ADR-007-sessao-pesquisa-primeira-classe.md) | Sessão de Pesquisa como cidadão de primeira classe | accepted | D7 |
| [ADR-008](ADR-008-modelo-base-mais-ajuste-local.md) | Modelo base global + ajuste fino local (híbrido) | accepted | D8 |
| [ADR-009](ADR-009-embeddings-bge-m3.md) | Embeddings BAAI/bge-m3 como default | accepted | D9 |
| [ADR-010](ADR-010-shell-visivel-primeiro.md) | Shell visível antes de ETL real (UX-first) | accepted | D10 |
| [ADR-011](ADR-011-classificacao-multicamada.md) | Classificação multicamada em cascata, cada camada desligável | accepted | D11 |
| [ADR-012](ADR-012-duckdb-parquet.md) | DuckDB + Parquet como storage analítico local | accepted | implicado por D6 |
| [ADR-013](ADR-013-subprocess-pid-lock.md) | Subprocess detached + status.json + pid.lock como modelo de execução | accepted | implicado por D7 |
| [ADR-014](ADR-014-install-python-pre-instalado.md) | install.sh/.bat exigem Python 3.11+ pré-instalado | accepted | implicado por D1, D6 |
| [ADR-015](ADR-015-ci-multi-os.md) | CI multi-OS Linux + macOS + Windows × Python 3.11 + 3.12 | accepted | infra |
| [ADR-016](ADR-016-uv-lock.md) | Dependências fixadas em pyproject.toml com uv lock | accepted | reprodutibilidade |
| [ADR-017](ADR-017-conventional-commits.md) | Conventional Commits + branches feature/fix/docs/chore | accepted | workflow |
| [ADR-018](ADR-018-random-state-fixo.md) | random_state fixo em todos os modelos estatísticos | accepted | implicado por D8 |
| [ADR-019](ADR-019-ruff-mypy-pytest.md) | Ruff + Mypy strict + pytest --cov 90 como portões de qualidade | accepted | qualidade |
| [ADR-020](ADR-020-logs-loguru.md) | Logs estruturados via Loguru, arquivo rotacionado por sessão | accepted | observabilidade |
| [ADR-021](ADR-021-fontes-auto-hospedadas.md) | Fontes auto-hospedadas (Inter + JetBrains Mono) sob SIL OFL 1.1 | accepted | ux, infra, licenca |

## Como adicionar um novo ADR

1. Copie o template da seção 4.1 do plano R2 (mesmo formato dos ADRs 012-020).
2. Numeração sequencial: próximo número livre.
3. Filename: `ADR-NNN-titulo-com-hifens.md` (ASCII puro, sem acentos).
4. Adicione linha na tabela acima, em ordem.
5. Vincule o ADR à sprint que o origina via campo `Sprint relacionada`.
6. Rode `uv run python scripts/validar_adr.py` para confirmar aderência ao schema MADR.
