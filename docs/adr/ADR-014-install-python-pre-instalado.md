# ADR-014 -- install.sh / install.bat exigem Python 3.11+ pré-instalado

- **Status:** accepted
- **Data:** 2026-04-28
- **Decisores:** @AndreBFarias
- **Tags:** instalacao, infra

## Contexto e problema

O Hemiciclo precisa ser instalável pelo "João comum" com poucos comandos.
A pergunta de design é: o instalador deve **trazer** um Python embutido
(via PyInstaller, Nuitka, conda-pack) ou **exigir** que o usuário tenha
Python 3.11+ no sistema?

Ambas as abordagens têm custos. Empacotar Python infla artefato (~80MB+),
quebra com atualização de SO, e dificulta auditoria. Exigir Python pré-instalado
adiciona um passo de pré-requisito mas mantém o produto pequeno e auditável.

## Drivers de decisão

- Tamanho do artefato distribuído (auditabilidade, simplicidade).
- Reprodutibilidade (`uv lock`).
- Compatibilidade com gerenciadores de pacote do SO.
- Filosofia local (ADR-006): usar o Python do usuário, não o "nosso".

## Opções consideradas

### Opção A -- PyInstaller / single-file binary

- Prós: zero pré-requisito.
- Contras: artefato 80-200MB, opaco, frágil cross-OS, sem `uv lock`.

### Opção B -- Conda-pack ou venv pré-pronto

- Prós: ambiente isolado pronto.
- Contras: tamanho similar, dependência de conda no host.

### Opção C -- Exigir Python 3.11+ + `uv` para criar venv local

- Prós: instalador minúsculo (KB), reproduzível via `uv.lock`, transparente,
  fácil de auditar, integra com gerenciadores nativos do SO.
- Contras: usuário precisa instalar Python antes (mitigável por mensagem
  clara em `install.sh`).

## Decisão

Escolhida: **Opção C**.

`install.sh` (Linux/macOS, S23) e `install.bat` (Windows, S36) seguem este
fluxo:

1. Verificam `python3 --version` >= 3.11.
2. Se ausente, imprimem instruções específicas por SO e abortam.
3. Instalam `uv` (gerenciador rápido) se necessário.
4. `uv sync --frozen` cria venv local em `.venv/` reproduzível.

## Consequências

**Positivas:**

- Repo enxuto. Instalador transparente (script shell auditável).
- `uv.lock` garante reprodutibilidade.
- Atualização do Python do SO não quebra o Hemiciclo (venv isolado).

**Negativas / custos assumidos:**

- Documentação precisa cobrir os 3 SOs.
- "Python ausente" é o erro mais provável de bootstrap (mensagem clara).

## Pendências / follow-ups

- [x] S23 entrega install.sh (Linux/macOS).
- [ ] S36 entrega install.bat (Windows nativo).
- [ ] S23.2 detecta Python via `uv python find` quando uv presente.

## Links

- Sprint relacionada: S23, S36
- Documentação: `docs/usuario/instalacao.md`
