# Sprint S22 -- Bootstrap Python + estrutura repo + uv + Makefile + pre-commit

**Projeto:** Hemiciclo
**Versão alvo:** v2.0.0
**Data criação:** 2026-04-27
**Autor:** @AndreBFarias
**Status:** DONE (2026-04-27)
**Depende de:** --
**Bloqueia:** S23, S24, S25, S29, S37
**Esforço:** P (1-2 dias)
**ADRs vinculados:** ADR-001, ADR-016, ADR-017, ADR-019
**Branch:** feature/s22-bootstrap

---

## 1. Objetivo

Criar a infraestrutura mínima do projeto Python (estrutura de diretórios, `pyproject.toml`, `uv.lock`, `Makefile`, `pre-commit`, `.editorconfig`, `.gitignore`, devcontainer, ADRs canônicos) preservando o código R em branch `legacy-r`.

## 2. Contexto

O repo está em R. Antes de qualquer feature, precisa virar projeto Python com tooling moderno. Sem isso, sprints subsequentes não têm onde executar.

Setup de coordenação já feito (fora do escopo de implementação do executor):

- Branch `legacy-r` criado e empurrado pra origin (preserva R).
- Branch `feature/s22-bootstrap` criado a partir de `main`.
- `VALIDATOR_BRIEF.md` na raiz com invariantes do projeto.
- Plano R2 versionado em `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md`.
- `sprints/README.md` e `sprints/ORDEM.md` criados.
- Esta spec.

O executor implementa o restante.

## 3. Escopo

### 3.1 In-scope

- [ ] `pyproject.toml` PEP 621 com:
  - Metadata (nome, versão `0.1.0`, descrição, autores, license GPL-3.0-or-later, requires-python `>=3.11`)
  - Deps mínimas: `typer>=0.12`, `rich>=13`, `pydantic>=2.7`, `loguru>=0.7`
  - `[project.optional-dependencies].dev`: `pytest>=8`, `pytest-cov>=5`, `pytest-asyncio>=0.23`, `ruff>=0.6`, `mypy>=1.10`, `pre-commit>=3.7`, `hypothesis>=6.100`
  - `[project.scripts]`: `hemiciclo = "hemiciclo.cli:app"`
  - `[tool.ruff]` configurado (line-length 100, target 3.11, regras E/F/I/N/UP/B/SIM/PT)
  - `[tool.ruff.format]`: quote-style `"double"`
  - `[tool.mypy]`: `strict = true`, `python_version = "3.11"`
  - `[tool.pytest.ini_options]`: `markers = ["slow"]`, `addopts = "-ra"`
  - `[tool.coverage.run]`: `branch = true`, `source = ["src/hemiciclo"]`
  - `[tool.coverage.report]`: `fail_under = 90`, `show_missing = true`
- [ ] `uv.lock` determinístico gerado por `uv sync --all-extras`
- [ ] `.python-version` com `3.11`
- [ ] Estrutura `src/hemiciclo/`:
  - `__init__.py` exportando `__version__ = "0.1.0"`
  - `__main__.py` chamando `cli.app()`
  - `cli.py` Typer com comandos stub: `hemiciclo --version`, `hemiciclo info`
  - `config.py` Pydantic Settings com `HEMICICLO_HOME` (`~/hemiciclo`), `LOG_LEVEL`, `RANDOM_STATE` (default 42), métodos pra criar diretórios se faltam
- [ ] Estrutura `tests/`:
  - `__init__.py`
  - `conftest.py` (fixtures globais: `tmp_hemiciclo_home` que cria home temporário)
  - `unit/test_sentinela.py` cobrindo: versão, help, config paths, criação de diretórios
- [ ] `Makefile` literal da seção 8.1 do plano R2
- [ ] `.pre-commit-config.yaml` literal da seção 6.4 do plano R2 (sem hooks locais ainda -- `validar_topicos.py` e `validar_adr.py` ficam pra sprints que os criam)
- [ ] `.editorconfig` literal da seção 8.3 do plano R2
- [ ] `.gitignore` Python expandido + manter padrões R existentes
- [ ] `.gitattributes` com normalização de line endings
- [ ] `.devcontainer/devcontainer.json` + `Dockerfile` com Python 3.11 slim + uv pré-instalado
- [ ] `.vscode/settings.json`, `launch.json`, `extensions.json` (Ruff formatter, Mypy, pytest discovery, configs Streamlit + CLI debug)
- [ ] `scripts/bootstrap.sh` (Linux/macOS) -- detecta SO, valida Python 3.11+, instala uv se faltar, sincroniza deps, instala pre-commit
- [ ] `scripts/bootstrap.bat` (Windows) -- equivalente Windows
- [ ] `docs/adr/README.md` -- índice de ADRs
- [ ] `docs/adr/ADR-001-migracao-para-python.md` até `ADR-011-classificacao-multicamada.md` -- 11 ADRs no formato MADR (template seção 4.1 do plano R2), cada um curto (contexto + decisão + consequências), vinculando D1-D11
- [ ] `CHANGELOG.md` Keep-a-Changelog com entrada `## [Unreleased]` listando o bootstrap
- [ ] `README.md` atualizado com seção "Migração para Python 2.0 em andamento" + link pra `docs/manifesto.md` (manifesto.md fica pra S38)
- [ ] CLI `hemiciclo --version` retorna exit 0 com `hemiciclo 0.1.0`
- [ ] CLI `hemiciclo info` mostra paths configurados, modelo base instalado (vai dizer "nenhum"), número de sessões

### 3.2 Out-of-scope (explícito)

- Coleta real de APIs -- fica em S24/S25
- Streamlit dashboard -- fica em S23
- Validador de YAML de tópico (`scripts/validar_topicos.py`) -- fica em S27
- Validador de ADR (`scripts/validar_adr.py`) -- fica em S37 ou S38
- CI no GitHub Actions -- fica em S37 (mas pre-commit local já está ativo)
- `manifesto.md`, demo gif, polish final de docs -- fica em S38
- Imports/exports da pasta `topicos/` -- fica em S27

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `pyproject.toml` | metadata + deps + tools config |
| `uv.lock` | lock determinístico |
| `.python-version` | trava Python 3.11 |
| `Makefile` | atalhos universais (bootstrap, install, test, lint, format, check, run, cli, seed, clean, release) |
| `.pre-commit-config.yaml` | portão local (Ruff + Mypy + checks padrão) |
| `.editorconfig` | ergonomia |
| `.gitattributes` | normalização line endings |
| `.devcontainer/devcontainer.json` | ambiente reproduzível VS Code |
| `.devcontainer/Dockerfile` | imagem Python 3.11 + uv |
| `.vscode/settings.json` | Ruff formatter + Mypy + pytest |
| `.vscode/launch.json` | debug Streamlit + CLI |
| `.vscode/extensions.json` | Ruff, Mypy, Python, Streamlit |
| `src/hemiciclo/__init__.py` | export `__version__` |
| `src/hemiciclo/__main__.py` | python -m hemiciclo |
| `src/hemiciclo/cli.py` | Typer entry-point com `--version`, `info` |
| `src/hemiciclo/config.py` | Pydantic Settings |
| `tests/__init__.py` | marker package |
| `tests/conftest.py` | fixtures globais (tmp_hemiciclo_home) |
| `tests/unit/__init__.py` | marker |
| `tests/unit/test_sentinela.py` | testes versão, help, config |
| `scripts/bootstrap.sh` | bootstrap Linux/macOS |
| `scripts/bootstrap.bat` | bootstrap Windows |
| `docs/adr/README.md` | índice de ADRs |
| `docs/adr/ADR-001-migracao-para-python.md` | ADR D1 |
| `docs/adr/ADR-002-voto-nominal-espinha-dorsal.md` | ADR D2 |
| `docs/adr/ADR-003-mapeamento-topico-hibrido.md` | ADR D3 |
| `docs/adr/ADR-004-assinatura-7-eixos.md` | ADR D4 |
| `docs/adr/ADR-005-caminho-indutivo.md` | ADR D5 |
| `docs/adr/ADR-006-arquitetura-100-local.md` | ADR D6 |
| `docs/adr/ADR-007-sessao-pesquisa-primeira-classe.md` | ADR D7 |
| `docs/adr/ADR-008-modelo-base-mais-ajuste-local.md` | ADR D8 |
| `docs/adr/ADR-009-embeddings-bge-m3.md` | ADR D9 |
| `docs/adr/ADR-010-shell-visivel-primeiro.md` | ADR D10 |
| `docs/adr/ADR-011-classificacao-multicamada.md` | ADR D11 |
| `CHANGELOG.md` | Keep-a-Changelog |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `.gitignore` | adiciona padrões Python/uv/streamlit/coverage/mypy/ruff/pytest sem remover padrões R |
| `README.md` | adiciona seção "Migração para Python 2.0 em andamento" + link pra plano em `docs/superpowers/specs/` |

### 4.3 Arquivos removidos

Nenhum nesta sprint. R fica intacto até sprints futuras (preservado em `legacy-r` independentemente).

## 5. Implementação detalhada

### 5.1 Passo a passo

1. Confirmar branch atual: `git rev-parse --abbrev-ref HEAD` deve retornar `feature/s22-bootstrap`.
2. Garantir uv instalado: `command -v uv` ou `curl -LsSf https://astral.sh/uv/install.sh | sh`.
3. `uv init --no-readme --package` (cuidado pra não sobrescrever; se já criou pyproject base, editar).
4. Editar `pyproject.toml` com configuração da seção 3.1.
5. Criar estrutura `src/hemiciclo/` e `tests/`.
6. Escrever `cli.py`, `config.py`, `__init__.py`, `__main__.py`.
7. Escrever `tests/conftest.py` e `tests/unit/test_sentinela.py`.
8. Criar `Makefile`, `.pre-commit-config.yaml`, `.editorconfig`, `.gitattributes`, `.python-version`.
9. Atualizar `.gitignore`.
10. Criar `.devcontainer/` e `.vscode/`.
11. Escrever scripts em `scripts/`.
12. Escrever 11 ADRs em `docs/adr/` no formato MADR (template na seção 4.1 do plano R2). Cada um curto: contexto curto, drivers, opção escolhida, consequências.
13. Criar `CHANGELOG.md`.
14. Atualizar `README.md`.
15. `uv sync --all-extras` gera `uv.lock`.
16. `uv run pre-commit install`.
17. `make check` deve passar.
18. `uv run hemiciclo --version` deve imprimir `hemiciclo 0.1.0`.
19. `uv run hemiciclo info` deve listar paths.
20. Atualizar `sprints/ORDEM.md` mudando S22 status pra DONE com data.
21. Commits Conventional pequenos e atômicos.

### 5.2 Decisões técnicas

- **uv** como gerenciador de deps -- velocidade + lock determinístico.
- **Mypy strict** desde o dia 1 -- adiar piora.
- **Pre-commit obrigatório** local -- espelha CI, falha rápido.
- **Pydantic Settings** com `model_config = SettingsConfigDict(env_prefix="HEMICICLO_")` pra config via env.
- **Ruff line-length 100** -- prática moderna, melhor que 79.

### 5.3 Trecho de código de referência -- `cli.py`

```python
"""CLI Hemiciclo via Typer."""

from __future__ import annotations

import typer
from rich.console import Console

from hemiciclo import __version__
from hemiciclo.config import Configuracao

app = typer.Typer(
    name="hemiciclo",
    help="Plataforma cidada de perfilamento parlamentar.",
    no_args_is_help=True,
)
console = Console()


def _versao_callback(value: bool) -> None:
    if value:
        console.print(f"hemiciclo {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_versao_callback,
        is_eager=True,
        help="Mostra versao e sai.",
    ),
) -> None:
    """Hemiciclo -- inteligencia politica aberta, soberana, local."""


@app.command()
def info() -> None:
    """Mostra paths configurados e estado do ambiente."""
    cfg = Configuracao()
    cfg.garantir_diretorios()
    console.print(f"[bold]Hemiciclo[/bold] {__version__}")
    console.print(f"Home: {cfg.home}")
    console.print(f"Modelos: {cfg.modelos_dir}")
    console.print(f"Sessoes: {cfg.sessoes_dir}")
    console.print(f"Cache: {cfg.cache_dir}")
    console.print(f"Logs: {cfg.logs_dir}")
    console.print(f"Random state: {cfg.random_state}")
```

### 5.4 Trecho de código de referência -- `config.py`

```python
"""Configuracao centralizada via Pydantic Settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    """Configuracao do Hemiciclo. Carrega env HEMICICLO_*."""

    model_config = SettingsConfigDict(env_prefix="HEMICICLO_", env_file=".env")

    home: Path = Field(default=Path.home() / "hemiciclo")
    log_level: str = Field(default="INFO")
    random_state: int = Field(default=42)

    @property
    def modelos_dir(self) -> Path:
        return self.home / "modelos"

    @property
    def sessoes_dir(self) -> Path:
        return self.home / "sessoes"

    @property
    def cache_dir(self) -> Path:
        return self.home / "cache"

    @property
    def logs_dir(self) -> Path:
        return self.home / "logs"

    @property
    def topicos_dir(self) -> Path:
        return self.home / "topicos"

    def garantir_diretorios(self) -> None:
        for diretorio in (
            self.home,
            self.modelos_dir,
            self.sessoes_dir,
            self.cache_dir,
            self.logs_dir,
            self.topicos_dir,
        ):
            diretorio.mkdir(parents=True, exist_ok=True)
```

Nota: `pydantic-settings` exige adicionar `pydantic-settings>=2.4` em deps.

## 6. Testes

### 6.1 Unit (`tests/unit/test_sentinela.py`)

- `test_versao` -- `runner.invoke(app, ["--version"])` retorna exit 0 e stdout contém `hemiciclo 0.1.0`.
- `test_help` -- `runner.invoke(app, ["--help"])` retorna exit 0 e contém `Usage`.
- `test_info_cria_diretorios` -- usando `tmp_hemiciclo_home`, chama `info`, verifica que os 5 diretórios foram criados.
- `test_config_random_state_default` -- `Configuracao().random_state == 42`.
- `test_config_env_override` -- monkeypatch `HEMICICLO_RANDOM_STATE=99`, instancia `Configuracao()`, verifica `random_state == 99`.

### 6.2 Fixture global (`tests/conftest.py`)

```python
"""Fixtures globais."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_hemiciclo_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Cria home temporario do Hemiciclo e exporta HEMICICLO_HOME."""
    home = tmp_path / "hemiciclo_home"
    monkeypatch.setenv("HEMICICLO_HOME", str(home))
    return home
```

## 7. Proof-of-work runtime-real

**Comando que valida a sprint:**

```bash
$ make bootstrap && make check && uv run hemiciclo --version
```

**Saída esperada:**

```
hemiciclo 0.1.0
```

E `make check` deve:

- Ruff zero violações
- Ruff format check zero diferenças
- Mypy --strict zero erros
- Pytest passa todos os testes (>= 5 testes)
- Cobertura >= 90% em `src/hemiciclo/`

**Critério de aceite (checkbox):**

- [ ] `git branch -a` lista `legacy-r` no remoto
- [ ] `feature/s22-bootstrap` é a branch ativa
- [ ] `uv run hemiciclo --version` retorna exit 0 com `hemiciclo 0.1.0`
- [ ] `uv run hemiciclo info` lista 5 paths existentes em `~/hemiciclo`
- [ ] `make check` passa integralmente
- [ ] `pre-commit run --all-files` passa zero alterações
- [ ] `uv.lock` commitado e determinístico
- [ ] 11 ADRs presentes em `docs/adr/ADR-001-*.md` até `ADR-011-*.md`
- [ ] `VALIDATOR_BRIEF.md` na raiz (já criado no scaffold)
- [ ] `docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` (já criado no scaffold)
- [ ] `CHANGELOG.md` com entrada `## [Unreleased]` listando bootstrap
- [ ] `README.md` aponta pra plano e manifesto
- [ ] `sprints/ORDEM.md` atualizado com S22 = DONE quando finalizado

## 8. Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| `uv` não disponível no ambiente | M | A | `scripts/bootstrap.sh` instala uv se faltar |
| Mypy strict gera fricção desnecessária no início | B | M | Aceitável -- projeto novo, custo é zero |
| `pydantic-settings` não está em deps default do Pydantic v2 | A | A | Adicionar explicitamente em `pyproject.toml` |
| `.env` carregado por engano em testes | B | A | Usar `monkeypatch.setenv` em fixtures, não escrever `.env` real |
| Pre-commit hooks pesados travam commit | M | M | Apenas Ruff + Mypy + checks essenciais; sem hooks locais ainda |
| Acentuação periférica em ADRs | M | M | Validar manualmente no review; PT-BR com acento OK em conteúdo, sem acento em paths |

## 9. Validação multi-agente

**Executor (`executor-sprint`):**

1. Lê `VALIDATOR_BRIEF.md`.
2. Lê este spec.
3. Confirma branch `feature/s22-bootstrap`.
4. Implementa entregas conforme passo a passo.
5. Roda `make check`.
6. Roda proof-of-work.
7. Reporta saída literal do proof-of-work.

**Validador (`validador-sprint`):**

1. Lê `VALIDATOR_BRIEF.md`.
2. Lê este spec.
3. Verifica branch ativo + `legacy-r` no remoto.
4. Roda `make bootstrap && make check && uv run hemiciclo --version` independentemente.
5. Confirma saída literal `hemiciclo 0.1.0`.
6. Verifica I1-I12 do BRIEF:
   - I1: nenhuma chamada a servidor central proprietário em `src/`
   - I2: PT-BR sem perda em ADRs e textos
   - I3: `random_state` declarado em `config.py`
   - I4: zero `print(` em `src/`
   - I5: zero `# TODO` sem `(SXX)` em `src/`
   - I6: Sessão/Params via Pydantic (placeholder OK em S22)
   - I7: Mypy --strict zero erros
   - I8: Ruff zero violações
   - I9: Cobertura >= 90% em arquivos novos
   - I10: commits Conventional
   - I11: N/A nesta sprint (sem YAMLs ainda)
   - I12: CHANGELOG `## [Unreleased]` presente
7. Inspeciona acentuação periférica em arquivos modificados.
8. Decide APROVADO / APROVADO_COM_RESSALVAS / REPROVADO.
9. Se REPROVADO, escreve patch-brief e reposta executor.

## 10. Próximo passo após DONE

S37 (CI multi-OS) e S23 (shell visível Streamlit) podem iniciar em paralelo (sub-agentes paralelos via dispatching-parallel-agents).
