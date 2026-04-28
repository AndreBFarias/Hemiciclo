# ADR-016 -- Dependências fixadas em pyproject.toml com uv lock

- **Status:** accepted
- **Data:** 2026-04-28
- **Decisores:** @AndreBFarias
- **Tags:** infra, dependencias, reprodutibilidade

## Contexto e problema

Hemiciclo é um produto cidadão que precisa **funcionar igual** na máquina de
qualquer pessoa, em qualquer momento. Dependências flutuantes (`requirements.txt`
sem hash, `setup.py` sem lock, intervalo aberto `>=`) quebram reprodutibilidade:
um usuário em janeiro recebe um conjunto de bibliotecas, outro em junho
recebe outro, e os bugs do segundo não reproduzem no primeiro.

## Drivers de decisão

- Reprodutibilidade exata cross-tempo, cross-máquina, cross-OS.
- Velocidade de instalação (`uv` é 10-100× mais rápido que pip).
- Padrão moderno PEP 621 (`pyproject.toml`).
- Compatível com PyPI quando a sprint S38+ liberar.

## Opções consideradas

### Opção A -- requirements.txt com pip-tools

- Prós: padrão histórico, conhecido.
- Contras: ferramental fragmentado (pip + pip-tools + venv), lento, formato
  legado.

### Opção B -- Poetry

- Prós: tudo em um, lock determinístico.
- Contras: lento em projetos grandes, `pyproject.toml` com seção
  proprietária `[tool.poetry]` (não 100% PEP 621).

### Opção C -- uv (Astral)

- Prós: Rust-native, 10-100× mais rápido, lock determinístico, 100% PEP 621,
  compat total com `pip install`, gera `.venv/` standard.
- Contras: ferramenta nova (1.x estabilizado em 2024).

## Decisão

Escolhida: **Opção C**.

- `pyproject.toml` declara dependências runtime e dev, com pinning conservador.
- `uv.lock` (commitado) contém o grafo resolvido com SHA256 por wheel.
- `uv sync --frozen` em CI e `install.sh` garante exatamente o mesmo grafo.
- `uv add` / `uv remove` é a interface canônica para mudar deps.

## Consequências

**Positivas:**

- `uv sync --frozen` garante grafo idêntico bit-a-bit cross-máquina.
- Velocidade transforma a UX do contribuidor (segundos, não minutos).
- Dependabot (S37) abre PR semanal com bumps; merge regenera lock.

**Negativas / custos assumidos:**

- Contribuidor precisa instalar `uv` (mitigado por `install.sh` que faz isso).
- Ferramenta nova; bugs eventuais (rastreados upstream).

## Pendências / follow-ups

- [x] S22 estabelece pyproject.toml + uv.lock.
- [x] S37 integra dependabot.

## Links

- Sprint relacionada: S22
- Documentação: `docs/dev/workflow.md`
- Site oficial: https://docs.astral.sh/uv/
