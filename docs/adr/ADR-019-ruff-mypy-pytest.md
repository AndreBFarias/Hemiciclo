# ADR-019 -- Ruff + Mypy strict + pytest --cov 90 como portões de qualidade

- **Status:** accepted
- **Data:** 2026-04-28
- **Decisores:** @AndreBFarias
- **Tags:** qualidade, ci, ferramental

## Contexto e problema

Projeto local cidadão, escrito em parte por agentes Claude, em parte por
contribuidores humanos, precisa de portões automatizados que rejeitem
código ruim **antes** do merge. Sem isso, o produto vira frankenstein e
o "João comum" fica sem garantia de qualidade.

Os portões devem ser:
- Rápidos (rodam em pre-commit + CI).
- Determinísticos (mesmo resultado cross-OS, ADR-015).
- Estritos (sem `Any` em assinatura pública, sem `# type: ignore` sem motivo).
- Mensuráveis (cobertura ≥ 90%, zero violações Ruff, zero erros Mypy).

## Drivers de decisão

- Tipagem estrita desde o dia 1 (Mypy strict).
- Lint + format unificados (Ruff substitui Black + isort + Flake8 + pylint).
- Cobertura mínima como contrato de regressão.
- Tempo total dos portões < 30s local.

## Opções consideradas

### Opção A -- Black + isort + Flake8 + Mypy

- Prós: stack estabelecida.
- Contras: 4 ferramentas, lentas, configuração fragmentada.

### Opção B -- Ruff (lint+format) + Mypy --strict + pytest --cov

- Prós: Ruff substitui 4 ferramentas em 1 binário Rust 100× mais rápido,
  Mypy strict bloqueia `Any` solto, pytest --cov falha o build se cobertura
  < 90%.
- Contras: Ruff é jovem (1.x estável em 2024), regras às vezes mudam.

## Decisão

Escolhida: **Opção B**.

- `ruff check src tests` (lint, ~1s).
- `ruff format --check src tests` (formato canônico, ~1s).
- `mypy --strict src` (tipagem, ~10s).
- `pytest --cov=src/hemiciclo --cov-fail-under=90` (testes + cobertura).

Tudo executável via `make check`. Pre-commit hook (S22) roda Ruff antes do
commit. CI multi-OS (S37, ADR-015) roda os 4 em todos os jobs.

## Consequências

**Positivas:**

- PR sem `make check` verde é rejeitado em revisão (I7-I9 do BRIEF).
- Tipagem estrita captura ~30% dos bugs antes de runtime.
- Cobertura como contrato impede "fast feature, slow test".

**Negativas / custos assumidos:**

- Override de mypy para libs sem stub (FlagEmbedding, sklearn, networkx, etc.).
- Cobertura 90% pode forçar testes triviais em código glue (aceito).
- Ruff format pode entrar em conflito raro com escolha estilística humana
  (resolve-se aceitando o formato canônico).

## Pendências / follow-ups

- [x] S22 estabelece configuração inicial.
- [x] S37 integra em CI multi-OS.

## Links

- Sprint relacionada: S22, S37
- Invariantes: I7, I8, I9 do `VALIDATOR_BRIEF.md`
- Configuração: `pyproject.toml` seções `[tool.ruff]`, `[tool.mypy]`,
  `[tool.pytest.ini_options]`
