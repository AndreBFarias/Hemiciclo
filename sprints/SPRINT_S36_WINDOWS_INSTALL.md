# Sprint S36 -- Paridade Windows: install.bat + run.bat + smoke CI windows-2022

**Projeto:** Hemiciclo
**Versão alvo:** v2.1.0 (terceira sprint do nível 1 anti-débito, depois de S27.1 e S23.1)
**Data criação:** 2026-04-28
**Autor:** @AndreBFarias
**Status:** READY (a executar)
**Depende de:** S23 (DONE), S23.1 (DONE), S37 (DONE -- CI multi-OS já existe)
**Bloqueia:** release público amplo (~1/3 dos cidadãos brasileiros usa Windows; sem `install.bat` o produto fica inacessível a esse público)
**Esforço:** P (1-2 dias)
**ADRs vinculados:** ADR-014 (Python pré-instalado, scripts não tentam instalar Python automaticamente)
**Branch:** feature/s36-windows-install

---

## 1. Objetivo

Entregar `install.bat` e `run.bat` na raiz do repo com **paridade funcional 1:1** com `install.sh`/`run.sh`, executáveis em **CMD ou PowerShell** de uma máquina Windows 10/11 limpa que tenha Python 3.11+ pré-instalado. O usuário Windows comum executa:

```cmd
install.bat
run.bat
```

E vê o navegador abrir em `http://localhost:8501` mostrando o dashboard Streamlit do Hemiciclo, idêntico ao fluxo Linux/macOS da S23.

Esta é a **terceira e última sprint bloqueante** de release público amplo do Hemiciclo 2.1.x (após S27.1 que destravou recall de votos e S23.1 que bundlou fontes locais). A partir do `merge` desta sprint, o produto é instalável em todos os SOs majoritários sem WSL nem container.

## 2. Contexto

A S23 entregou shell visível Streamlit + `install.sh`/`run.sh` Linux/macOS, declarando explicitamente em §3.2 (out-of-scope): *"`install.bat` e `run.bat` Windows -- fica em S36 (paridade Windows)"*. O `install.sh` (linha 30) também documenta: *"Para Windows, aguarde a sprint S36 (install.bat)."* O guia `docs/usuario/instalacao.md` (linhas 1-3) instrui usuário Windows a usar WSL2 enquanto a S36 não saísse.

O CI da S37 já roda em `windows-2022` (matriz `os: [ubuntu-22.04, macos-14, windows-2022]` em `.github/workflows/ci.yml:23`), confirmando que `pytest`, `ruff` e `mypy --strict` passam nativamente no Windows. Falta validar o caminho do **usuário final**: clonar o repo + rodar `install.bat` em CMD limpo + ver Streamlit subir.

A S23.1 já bundlou as fontes TTF localmente (`src/hemiciclo/dashboard/static/fonts/`), eliminando dependência de Google Fonts -- isso garante que o dashboard tem identidade visual íntegra também no Windows, mesmo em redes corporativas que bloqueiam CDNs externas.

`.gitattributes` (linha 5) **já está configurado** com `*.bat text eol=crlf` desde a S22/S37. Esta sprint só precisa **respeitar** essa convenção ao versionar os arquivos -- nada para mudar no `.gitattributes`.

Lição empírica do CI multi-OS (S37): testes Windows quebraram inicialmente por uso de path separator `\` vs `/` (`test_dashboard_invoca_streamlit_run`). Esta sprint deve ser explícita sobre encoding (`chcp 65001`) e separadores em mensagens.

## 3. Escopo

### 3.1 In-scope

- [ ] **`install.bat`** na raiz do repo (CRLF + UTF-8 com `chcp 65001`):
  - Linha 1: `@echo off` (suprime echo de cada comando)
  - Linha 2: `chcp 65001 >nul 2>&1` (UTF-8 PT-BR sem cp1252; `>nul` esconde "Active code page: 65001")
  - Linha 3: `setlocal enabledelayedexpansion` (variáveis dinâmicas em loops e conds)
  - Cabeçalho REM com mesmo conteúdo que `install.sh` linhas 2-16: propósito, pré-requisitos, modo `--check`, link `python.org`
  - Detecta diretório do script: `set DIR=%~dp0` (com trailing backslash)
  - **Detecção de Python 3.11+ em cascata** (3 fallbacks):
    1. `where python >nul 2>&1 && for /f "tokens=2" %%v in ('python --version') do set PY_VER=%%v` -- Python no PATH
    2. Se ausente ou versão < 3.11, tenta `py -3.11 --version` (Python launcher Windows oficial)
    3. Se ambos falharem: imprime mensagem PT-BR clara apontando `https://python.org/downloads` (release "Windows installer (64-bit)") + instrução de marcar checkbox "Add Python to PATH" + `exit /b 1`
  - Parsing de versão: `for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (set PY_MAJOR=%%a & set PY_MINOR=%%b)`
  - Validação `if %PY_MAJOR% LSS 3 (...) else if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 11 (...)` -- aborta com mensagem PT-BR + link
  - Modo `--check`: se `%1`=="--check" imprime "Modo --check: validação OK, sem instalar." e `exit /b 0` (espelha `install.sh:57-60`)
  - **Detecção/instalação de uv**:
    - `where uv >nul 2>&1` -- se já presente, segue
    - Se ausente: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` (instalador oficial do uv para Windows; equivalente ao `curl | sh` do Linux). Após instalar, ajusta PATH temporário: `set PATH=%USERPROFILE%\.local\bin;%PATH%`
    - Re-checa: se `where uv` ainda falhar, aborta com mensagem e instrução de adicionar `%USERPROFILE%\.local\bin` ao PATH
  - **Idempotência**: se `.venv\` já existe, imprime "Ambiente .venv já existe, sincronizando..." e segue (não recria; `uv sync` é idempotente). Se quiser recriar do zero, instrução para `rmdir /s /q .venv`
  - `cd /d %DIR%` (muda drive + dir; `/d` necessário se script invocado de drive diferente)
  - Cronometragem: usa `set START=%TIME%` antes e calcula delta no fim. Implementação simples: aceita imprecisão sub-segundo. Alternativa robusta: `powershell -c "[int]([datetime]::Now - [datetime]'%START%').TotalSeconds"` -- escolher essa para precisão consistente com `install.sh`
  - Comando central: `uv sync --all-extras` (idêntico ao Linux/macOS)
  - Mensagens finais PT-BR consistentes com `install.sh` linhas 84-86: "Instalação concluída em XXs.", "Para iniciar o dashboard: run.bat", "Para sanidade do CLI: uv run hemiciclo info"
  - `exit /b 0` final
- [ ] **`run.bat`** na raiz do repo (CRLF + UTF-8 com `chcp 65001`):
  - `@echo off` + `chcp 65001 >nul 2>&1`
  - Cabeçalho REM com mesmo conteúdo que `run.sh` linhas 2-5
  - `set DIR=%~dp0` + `cd /d %DIR%`
  - Validação `if not exist .venv\ (echo [Hemiciclo] Erro: ambiente .venv nao existe. Rode install.bat primeiro. & exit /b 1)`
  - Mensagens: "Subindo Streamlit em http://localhost:8501" e "Ctrl+C para encerrar."
  - Comando central: `uv run streamlit run src\hemiciclo\dashboard\app.py --server.headless=false --server.port=8501`
  - Não precisa abrir browser explicitamente: o Streamlit com `--server.headless=false` já abre o default browser do Windows. Caso o usuário queira forçar, pode-se usar `start "" http://localhost:8501` em paralelo, mas isso causa double-open -- **decisão: deixar Streamlit abrir sozinho** (mesmo comportamento do `run.sh`)
  - Sem trap de SIGINT (Windows trata Ctrl+C nativamente; `setlocal` ajuda)
- [ ] **`docs/usuario/instalacao.md`** -- seção Windows expandida substituindo o aviso WSL atual:
  - Remove o callout "Para Windows, aguarde a sprint S36" (linhas 1-3)
  - Adiciona seção **"Windows 10/11"** abaixo da seção macOS:
    - Pré-requisitos Windows: Python 3.11+ via instalador oficial python.org com checkbox "Add Python to PATH" marcado, OU via Microsoft Store (`python` 3.11+), OU via `winget install Python.Python.3.11`
    - Comandos passo-a-passo: `git clone`, `cd Hemiciclo`, `install.bat`, `run.bat`
    - Diferenças notáveis vs Linux/macOS: separador `\`, ativação de venv via `.venv\Scripts\activate.bat` (mas script já cuida), Defender Windows pode quarentenar `uv.exe` (mitigação: liberar via SmartScreen ou clicar "Mais informações > Executar assim mesmo")
    - Troubleshooting Windows-específico:
      - `'python' is not recognized as an internal or external command`: PATH não inclui Python; reinstalar com checkbox PATH ou usar `py -3.11`
      - `chcp 65001` falha em CMD legado: atualizar para Windows Terminal (Microsoft Store) ou PowerShell 7
      - Acentuação aparece como `?` ou `??`: terminal não está em UTF-8; trocar para Windows Terminal
      - `uv: command not found` após install: `set PATH=%USERPROFILE%\.local\bin;%PATH%` ou logout/login para PATH propagar
      - Antivírus bloqueia download do uv: liberar `astral.sh` na whitelist temporariamente
  - Mantém seção WSL como **alternativa** (não exclusiva), com nota: "Se preferir ambiente Linux dentro do Windows, WSL2 + Ubuntu 22.04 também funciona com `install.sh`."
- [ ] **CI: novo job `smoke-install-windows` em `.github/workflows/ci.yml`**:
  - Roda em `windows-2022` runner (mesmo da matriz existente)
  - Independente do job `test` (não bloqueia matriz Python; valida apenas que `install.bat --check` passa em ambiente limpo)
  - Steps:
    1. `actions/checkout@v4`
    2. `actions/setup-python@v5` com `python-version: "3.11"` (garante Python no PATH)
    3. Run: `install.bat --check` -- modo seco que valida ambiente sem rodar `uv sync` (~2s); deve sair com `exit /b 0`
    4. (opcional, custo aceitável) Run: `install.bat` completo + `uv run hemiciclo --version` + asserção que stdout contém `hemiciclo 2.0.0`
  - **Decisão: incluir (4) com timeout 10min**. O `uv sync` no Windows leva ~3min (cache do uv ajuda); validar a paridade real vale o custo. Se runner CI estiver lento, fallback para apenas `--check`.
  - Job adicional `smoke-run-windows` é **out-of-scope** (Streamlit é processo de longa duração; não cabe smoke não-interativo barato em CI; runtime real fica para release manual)
- [ ] **`tests/unit/test_install_bat.py`** novo (rodável em qualquer SO; valida o **arquivo** versionado):
  - `test_install_bat_existe` -- `Path("install.bat").exists()`
  - `test_run_bat_existe` -- `Path("run.bat").exists()`
  - `test_install_bat_tem_chcp_utf8` -- bytes contêm `chcp 65001` nas primeiras 200 linhas
  - `test_install_bat_tem_echo_off` -- primeira linha é `@echo off`
  - `test_install_bat_crlf_line_endings` -- `open("install.bat", "rb").read()` contém `b"\r\n"` e nenhum `b"\n"` órfão (sem CR antes)
  - `test_run_bat_crlf_line_endings` -- idem para `run.bat`
  - `test_install_bat_referencia_python_3_11` -- bytes contêm `3.11` (validação mínima de versão)
  - `test_install_bat_referencia_uv_sync_all_extras` -- bytes contêm `uv sync --all-extras`
  - `test_install_bat_referencia_python_org` -- bytes contêm `python.org` (mensagem de erro com link)
  - `test_install_bat_modo_check_documentado` -- bytes contêm `--check`
  - `test_run_bat_referencia_streamlit_run` -- bytes contêm `streamlit run src\hemiciclo\dashboard\app.py` (com backslash Windows)
  - `test_run_bat_porta_8501` -- bytes contêm `8501`
  - `test_bats_acentuacao_pt_br_consistente` -- decode UTF-8 + assert que palavras canônicas aparecem com acento (`instalação`, `dependências`, `validação`, `não`, `começando`) e nunca sem acento (`instalacao`, `dependencias`)
- [ ] **`tests/integracao/test_install_bat_smoke.py`** novo (rodável apenas em Windows; pula com `pytest.skip` em outros SOs):
  - Fixture `pytest.skipif(sys.platform != "win32", reason="install.bat smoke roda apenas em Windows")`
  - `test_install_bat_check_mode_exit_zero` -- `subprocess.run(["install.bat", "--check"], check=False, capture_output=True)` retorna `returncode == 0`
  - `test_install_bat_check_mode_imprime_python_ok` -- stdout contém `Python` e `OK`
  - `test_install_bat_check_mode_imprime_em_pt_br` -- stdout contém `validação` (não `validacao`) -- garante I2 do BRIEF
  - **Não roda `install.bat` completo** (custo de CI; coberto pelo job `smoke-install-windows`)
- [ ] **`README.md`** atualizado:
  - Seção "Instalação rápida" ganha sub-seção Windows ao lado de Linux/macOS:
    ```markdown
    **Linux / macOS:**
    ```bash
    git clone https://github.com/AndreBFarias/Hemiciclo.git
    cd Hemiciclo
    ./install.sh && ./run.sh
    ```
    **Windows 10/11:**
    ```cmd
    git clone https://github.com/AndreBFarias/Hemiciclo.git
    cd Hemiciclo
    install.bat && run.bat
    ```
    ```
  - Badge novo (opcional): `Windows | macOS | Linux` (já presente, só confirmar)
- [ ] **`CHANGELOG.md`** entrada `[2.1.0-dev]` (já existente após S23.1) com bullet:
  - `feat(install): paridade Windows com install.bat + run.bat (S36) -- usuário Windows agora roda Hemiciclo nativamente sem WSL`
- [ ] **`sprints/ORDEM.md`** -- transição S36: `DEPENDS` → `IN_PROGRESS` no scaffolding, depois `DONE` ao concluir; histórico de transição com sumário do PR

### 3.2 Out-of-scope (declare explicitamente)

- **PyInstaller / executável único** -- empacotar `hemiciclo.exe` standalone fica para v2.2+ (decisão do usuário fundador: Hemiciclo prefere transparência do código sobre conveniência de double-click)
- **WSL** -- usuário Windows que quiser rodar dentro de WSL2 já tem instruções no `instalacao.md` para usar `install.sh`. Não precisa de script separado.
- **Auto-install do Python** -- ADR-014 já decidiu que o usuário precisa pré-instalar Python 3.11+. Scripts apenas detectam e abortam com mensagem clara, nunca baixam Python automaticamente. Isso preserva soberania do usuário sobre o ambiente.
- **Suporte a Windows 8.1 ou anterior** -- mínimo Windows 10 (build 1809+, suporte nativo a UTF-8 no console), Windows 11 ideal
- **Suporte a CMD legado pré-Windows 10** -- assume `chcp 65001` funcional (Windows 10+)
- **Atalho na área de trabalho** -- v2.2+ pode adicionar `criar_atalho.bat` ou instalador MSI
- **Scripts PowerShell `.ps1`** -- decisão: `.bat` cobre CMD + PowerShell (PowerShell executa `.bat` nativamente). Manter um único script reduz superfície de manutenção.

## 4. Entregas

### 4.1 Arquivos criados

| Caminho | Propósito |
|---|---|
| `install.bat` | Bootstrap usuário final Windows 10/11 (paridade com install.sh) |
| `run.bat` | Atalho rodar Streamlit no Windows (paridade com run.sh) |
| `tests/unit/test_install_bat.py` | Validação estrutural dos `.bat` (cross-OS) -- 13 testes |
| `tests/integracao/test_install_bat_smoke.py` | Smoke `install.bat --check` em Windows (skipif outros SOs) -- 3 testes |

### 4.2 Arquivos modificados

| Caminho | Mudança |
|---|---|
| `docs/usuario/instalacao.md` | Remove aviso WSL; adiciona seção Windows 10/11 completa + troubleshooting |
| `.github/workflows/ci.yml` | Novo job `smoke-install-windows` em windows-2022 |
| `README.md` | Sub-seção Windows ao lado de Linux/macOS na "Instalação rápida" |
| `CHANGELOG.md` | Entrada [2.1.0-dev] com bullet S36 |
| `sprints/ORDEM.md` | S36: DEPENDS → IN_PROGRESS → DONE com histórico |

### 4.3 Arquivos NÃO tocados (invariantes confirmadas)

- `.gitattributes` -- já contém `*.bat text eol=crlf` (linha 5) desde S22; **NÃO modificar**
- `install.sh` / `run.sh` -- referência canônica; **NÃO modificar** (paridade significa replicar o comportamento, não alterar o original)
- `pyproject.toml`, `uv.lock` -- nenhuma dep nova; **NÃO modificar**
- Qualquer arquivo em `src/hemiciclo/` -- esta sprint é puro scripting + docs + CI; **NÃO toca código Python de produção**

## 5. Implementação detalhada

### 5.1 Passo a passo do executor

1. Confirmar branch `feature/s36-windows-install` (criar via `git checkout -b feature/s36-windows-install` se ausente).
2. Confirmar `.gitattributes:5` ainda contém `*.bat text eol=crlf` (precondição). Se ausente, **abortar** e abrir sprint corretiva (anti-débito).
3. Criar `install.bat` na raiz com **line endings CRLF** -- editor deve salvar com `\r\n`. Validar: `python -c "data=open('install.bat','rb').read(); assert b'\r\n' in data and not (b'\n' in data and b'\r\n' not in data); print('CRLF OK')"`.
4. Criar `run.bat` na raiz com mesma convenção CRLF.
5. Validar formato: `python -c "import io; raw=open('install.bat','rb').read(); txt=raw.decode('utf-8'); assert 'chcp 65001' in txt and '@echo off' in txt and 'uv sync --all-extras' in txt; print('estrutura OK')"`.
6. Escrever `tests/unit/test_install_bat.py` com 13 testes da §3.1 (rodar antes de prosseguir: `uv run pytest tests/unit/test_install_bat.py -v`).
7. Escrever `tests/integracao/test_install_bat_smoke.py` com 3 testes Windows-only (skipif).
8. Atualizar `docs/usuario/instalacao.md`: remover blockquote linhas 1-3, adicionar seção "Windows 10/11" com pré-requisitos, comandos, troubleshooting.
9. Editar `.github/workflows/ci.yml`: adicionar job `smoke-install-windows` em paralelo ao job `test`. Steps: checkout + setup-python 3.11 + run `install.bat --check` + run `install.bat` completo + asserção `uv run hemiciclo --version`.
10. Atualizar `README.md` com sub-seção Windows na "Instalação rápida".
11. Adicionar bullet `[2.1.0-dev]` em `CHANGELOG.md`.
12. Atualizar `sprints/ORDEM.md` mudando S36 de DEPENDS para IN_PROGRESS no início e DONE ao final, com histórico.
13. **Smoke local Linux dev** (operacional): rodar testes unit (cross-OS) `uv run pytest tests/unit/test_install_bat.py -v` -- devem passar 13/13.
14. **Smoke local manual Windows** (se executor tiver acesso a máquina/VM Windows): `git pull`, `install.bat --check`, depois `install.bat` completo, depois `run.bat`, abrir `localhost:8501` e validar visualmente. Reportar saída no PR.
15. `make check` deve passar com cobertura ≥ 90% nos arquivos novos.
16. Branch sem push automático -- orquestrador integra após validação.

### 5.2 Decisões técnicas

- **CMD-only, não PowerShell-script.** PowerShell executa `.bat` nativamente, mas o inverso não é true. Cobrir o denominador comum (`.bat`) maximiza compatibilidade. PowerShell users podem rodar `cmd /c install.bat` ou simplesmente `.\install.bat`.
- **`chcp 65001` no topo, não em cada comando.** UTF-8 cobre PT-BR perfeitamente em Windows 10+. Sem isso, mensagens com `ç`, `ã`, `é` viram `?` em CMD legado.
- **`@echo off` antes de `chcp` para suprimir "Active code page: 65001".** Ordem: `@echo off` → `chcp 65001 >nul 2>&1` → `setlocal enabledelayedexpansion`.
- **Detecção de Python em cascata `where python` → `py -3.11`.** Cobre instalações via python.org (PATH) e via Microsoft Store (apenas `py` launcher). Nunca tenta instalar Python (ADR-014).
- **uv via PowerShell `irm | iex`** -- instalador oficial do uv para Windows; equivalente ao `curl | sh` do Linux. Path resultante: `%USERPROFILE%\.local\bin\uv.exe`.
- **Idempotência por checagem `if exist .venv\`**: se `.venv` existe, não recria; apenas re-roda `uv sync --all-extras` (que é idempotente). Se quiser limpar, instrução manual: `rmdir /s /q .venv`.
- **Sem trap de Ctrl+C em `run.bat`**. Windows trata Ctrl+C nativamente; `setlocal` garante que variáveis não vazem.
- **Cronometragem via PowerShell para precisão segundos** (alternativa: aceitar imprecisão sub-segundo do `%TIME%`). PowerShell já está em todo Windows 10+, custo zero.
- **CI smoke roda `install.bat` completo** (não apenas `--check`): valida que `uv sync` funciona em runner Windows limpo. Custo ~3min, justificável dado que esta sprint é bloqueante de release.
- **Testes estruturais `.bat` cross-OS** (`tests/unit/test_install_bat.py`): roda em Linux/macOS/Windows; valida bytes do arquivo versionado, não execução. Garante regressão se alguém editar `install.bat` e quebrar CRLF/UTF-8/`chcp`.
- **Testes de execução Windows-only** (`tests/integracao/test_install_bat_smoke.py`): `pytest.skipif` deixa Linux/macOS verdes; runner Windows do CI roda os 3 testes Windows-only.

### 5.3 Esqueleto de `install.bat` (referência)

```batch
@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM install.bat -- Bootstrap do Hemiciclo 2.0 (Windows 10/11).
REM
REM Pre-requisitos:
REM   - Python 3.11 ou superior já instalado e disponível como ``python`` ou ``py -3.11``.
REM   - Conexão de internet (para baixar uv e dependências).
REM
REM O que faz:
REM   1. Detecta Python via ``where python`` ou ``py -3.11``.
REM   2. Valida versão >= 3.11.
REM   3. Instala ``uv`` em %USERPROFILE%\.local\bin se ausente.
REM   4. Roda ``uv sync --all-extras`` para popular ``.venv\``.
REM   5. Imprime tempo decorrido e o comando ``run.bat``.
REM
REM Modo ``--check``: valida ambiente sem instalar (útil para CI smoke).
REM NÃO baixa o modelo bge-m3 (~2GB). Isso fica para a sprint S28.

set "DIR=%~dp0"

echo [Hemiciclo] Sistema operacional detectado: Windows

echo [Hemiciclo] Verificando Python 3.11+...

set "PY_CMD="
where python >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>&1
    if !errorlevel! equ 0 (
        set "PY_CMD=py -3.11"
    )
)

if "!PY_CMD!"=="" (
    echo [Hemiciclo] Erro: Python 3.11+ nao encontrado. >&2
    echo   Instale Python 3.11+ de https://python.org/downloads >&2
    echo   Marque a opcao "Add Python to PATH" no instalador. >&2
    echo   Alternativa: winget install Python.Python.3.11 >&2
    exit /b 1
)

for /f "tokens=2" %%v in ('!PY_CMD! --version 2^>^&1') do set "PY_VER=%%v"
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)

if !PY_MAJOR! LSS 3 (
    echo [Hemiciclo] Erro: Python !PY_VER! detectado, requer 3.11+. >&2
    echo   Instale Python 3.11+ de https://python.org/downloads >&2
    exit /b 1
)
if !PY_MAJOR! EQU 3 if !PY_MINOR! LSS 11 (
    echo [Hemiciclo] Erro: Python !PY_VER! detectado, requer 3.11+. >&2
    echo   Instale Python 3.11+ de https://python.org/downloads >&2
    exit /b 1
)

echo [Hemiciclo] Python !PY_VER! OK.

if "%~1"=="--check" (
    echo [Hemiciclo] Modo --check: validação OK, sem instalar.
    exit /b 0
)

where uv >nul 2>&1
if !errorlevel! neq 0 (
    echo [Hemiciclo] Instalando uv...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

where uv >nul 2>&1
if !errorlevel! neq 0 (
    echo [Hemiciclo] Erro: uv nao disponivel mesmo apos instalacao. >&2
    echo   Adicione %USERPROFILE%\.local\bin ao PATH e tente novamente. >&2
    exit /b 1
)

cd /d "%DIR%"

if exist ".venv\" (
    echo [Hemiciclo] Ambiente .venv ja existe, sincronizando dependencias...
) else (
    echo [Hemiciclo] Sincronizando dependências (pode levar 3-5 min)...
)

set "START=%TIME%"
uv sync --all-extras
if !errorlevel! neq 0 (
    echo [Hemiciclo] Erro: uv sync falhou. Verifique conexao de internet. >&2
    exit /b 1
)

REM Cronometragem precisa via PowerShell (Windows 10+).
for /f %%t in ('powershell -NoProfile -c "[int]([datetime]::Now - [datetime]'%START%').TotalSeconds"') do set "DECORRIDO=%%t"

echo.
echo [Hemiciclo] Instalação concluída em !DECORRIDO!s.
echo [Hemiciclo] Para iniciar o dashboard: run.bat
echo [Hemiciclo] Para sanidade do CLI: uv run hemiciclo info
exit /b 0
```

### 5.4 Esqueleto de `run.bat` (referência)

```batch
@echo off
chcp 65001 >nul 2>&1
setlocal

REM run.bat -- Sobe o dashboard Streamlit do Hemiciclo em localhost:8501.
REM
REM Por padrao Streamlit abre o navegador automaticamente
REM (--server.headless=false). Use Ctrl+C para encerrar.

set "DIR=%~dp0"
cd /d "%DIR%"

if not exist ".venv\" (
    echo [Hemiciclo] Erro: ambiente .venv nao existe. Rode install.bat primeiro. >&2
    exit /b 1
)

echo [Hemiciclo] Subindo Streamlit em http://localhost:8501
echo [Hemiciclo] Ctrl+C para encerrar.

uv run streamlit run src\hemiciclo\dashboard\app.py ^
    --server.headless=false ^
    --server.port=8501

exit /b %errorlevel%
```

### 5.5 Esqueleto do job CI `smoke-install-windows`

```yaml
  smoke-install-windows:
    name: Smoke install.bat (windows-2022)
    runs-on: windows-2022
    timeout-minutes: 10
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: install.bat --check (modo seco)
        shell: cmd
        run: install.bat --check

      - name: install.bat completo
        shell: cmd
        run: install.bat

      - name: Sanidade CLI hemiciclo
        shell: cmd
        run: uv run hemiciclo --version

      - name: Asserção versão
        shell: pwsh
        run: |
          $output = uv run hemiciclo --version
          if ($output -notmatch "hemiciclo 2\.\d+\.\d+") {
            Write-Error "Versão inesperada: $output"
            exit 1
          }
          Write-Output "Versão OK: $output"
```

### 5.6 Trecho de teste -- `test_install_bat.py` (referência)

```python
"""Testes estruturais dos scripts .bat (rodam em qualquer SO)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
INSTALL_BAT = ROOT / "install.bat"
RUN_BAT = ROOT / "run.bat"


def test_install_bat_existe() -> None:
    assert INSTALL_BAT.is_file(), "install.bat deve existir na raiz do repo"


def test_run_bat_existe() -> None:
    assert RUN_BAT.is_file(), "run.bat deve existir na raiz do repo"


def test_install_bat_crlf_line_endings() -> None:
    raw = INSTALL_BAT.read_bytes()
    assert b"\r\n" in raw, "install.bat deve ter line endings CRLF"
    # Garantir que todo \n é precedido de \r (sem LF órfão)
    for i, byte in enumerate(raw):
        if byte == 0x0A and (i == 0 or raw[i - 1] != 0x0D):
            pytest.fail(f"LF órfão (sem CR) em offset {i}")


def test_install_bat_tem_chcp_utf8() -> None:
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    assert "chcp 65001" in txt[:300], "install.bat deve declarar chcp 65001 no topo"


def test_install_bat_tem_echo_off() -> None:
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    assert txt.lstrip().startswith("@echo off"), "primeira linha útil deve ser @echo off"


def test_install_bat_referencia_python_3_11() -> None:
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    assert "3.11" in txt, "install.bat deve referenciar versão mínima 3.11"


def test_install_bat_referencia_uv_sync() -> None:
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    assert "uv sync --all-extras" in txt, "install.bat deve invocar uv sync --all-extras"


def test_install_bat_referencia_python_org() -> None:
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    assert "python.org" in txt, "install.bat deve apontar python.org em mensagem de erro"


def test_install_bat_modo_check_documentado() -> None:
    txt = INSTALL_BAT.read_text(encoding="utf-8")
    assert "--check" in txt, "install.bat deve suportar modo --check"


def test_run_bat_referencia_streamlit_run() -> None:
    txt = RUN_BAT.read_text(encoding="utf-8")
    assert "streamlit run src\\hemiciclo\\dashboard\\app.py" in txt


def test_run_bat_porta_8501() -> None:
    txt = RUN_BAT.read_text(encoding="utf-8")
    assert "8501" in txt


def test_bats_acentuacao_pt_br_consistente() -> None:
    for path in (INSTALL_BAT, RUN_BAT):
        txt = path.read_text(encoding="utf-8")
        # Palavras canônicas PT-BR que devem aparecer com acento se aparecerem
        if "instalacao" in txt.lower() and "instalação" not in txt.lower():
            pytest.fail(f"{path.name}: 'instalacao' sem acento detectado")


def test_run_bat_crlf_line_endings() -> None:
    raw = RUN_BAT.read_bytes()
    assert b"\r\n" in raw, "run.bat deve ter line endings CRLF"
```

## 6. Testes

### 6.1 Unit (`tests/unit/test_install_bat.py` -- 13 testes cross-OS)

Lista completa em §3.1. Roda em Linux/macOS/Windows (validação por leitura de bytes; nada executa o `.bat`).

### 6.2 Integração (`tests/integracao/test_install_bat_smoke.py` -- 3 testes Windows-only)

```python
import sys
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="install.bat smoke roda apenas em Windows",
)


def test_install_bat_check_mode_exit_zero() -> None:
    result = subprocess.run(
        ["install.bat", "--check"],
        cwd=Path(__file__).parent.parent.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_install_bat_check_mode_imprime_python_ok() -> None:
    result = subprocess.run(
        ["install.bat", "--check"],
        cwd=Path(__file__).parent.parent.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert "Python" in result.stdout
    assert "OK" in result.stdout


def test_install_bat_check_mode_imprime_em_pt_br() -> None:
    result = subprocess.run(
        ["install.bat", "--check"],
        cwd=Path(__file__).parent.parent.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert "validação" in result.stdout, "I2 do BRIEF: PT-BR com acento"
```

### 6.3 CI (`smoke-install-windows`)

Job novo no `.github/workflows/ci.yml`:
- runs-on: `windows-2022`
- timeout: 10min
- Steps: checkout + setup-python 3.11 + `install.bat --check` + `install.bat` completo + asserção versão

### 6.4 Smoke manual (executor reporta saída no PR se tiver máquina Windows)

```cmd
C:\Users\foo> git clone https://github.com/AndreBFarias/Hemiciclo.git
C:\Users\foo> cd Hemiciclo
C:\Users\foo\Hemiciclo> install.bat
[Hemiciclo] Sistema operacional detectado: Windows
[Hemiciclo] Verificando Python 3.11+...
[Hemiciclo] Python 3.11.9 OK.
[Hemiciclo] Sincronizando dependências (pode levar 3-5 min)...
   Resolved XXX packages in 1.23s
   ...
[Hemiciclo] Instalação concluída em 187s.
[Hemiciclo] Para iniciar o dashboard: run.bat
[Hemiciclo] Para sanidade do CLI: uv run hemiciclo info

C:\Users\foo\Hemiciclo> run.bat
[Hemiciclo] Subindo Streamlit em http://localhost:8501
[Hemiciclo] Ctrl+C para encerrar.

  You can now view your Streamlit app in your browser.
  Local URL: http://localhost:8501
```

(Browser abre em `localhost:8501`, intro narrativo aparece, navegação funciona pelas 4 abas.)

## 7. Proof-of-work runtime-real

### 7.1 Em dev Linux (toda a suite cross-OS deve passar)

```bash
$ python -c "data=open('install.bat','rb').read(); assert b'\r\n' in data and b'chcp 65001' in data[:200]; print('format OK')"
$ python -c "data=open('run.bat','rb').read(); assert b'\r\n' in data and b'chcp 65001' in data[:200]; print('format OK')"
$ uv run pytest tests/unit/test_install_bat.py -v
$ make check
```

**Saída esperada:**
- `format OK` para ambos `.bat`
- 13 testes verdes em `test_install_bat.py`
- `make check` passa com cobertura ≥ 90% (testes novos cobrem 100% de si mesmos -- são leitura de arquivo)

### 7.2 Em CI windows-2022 (job `smoke-install-windows`)

```cmd
> install.bat --check
[Hemiciclo] Sistema operacional detectado: Windows
[Hemiciclo] Verificando Python 3.11+...
[Hemiciclo] Python 3.11.9 OK.
[Hemiciclo] Modo --check: validação OK, sem instalar.

> install.bat
[...]
[Hemiciclo] Instalação concluída em XXXs.

> uv run hemiciclo --version
hemiciclo 2.0.0
```

**Asserção no job:** stdout do último comando bate o regex `^hemiciclo 2\.\d+\.\d+$`.

### 7.3 Em smoke manual Windows (opcional; executor reporta no PR)

```cmd
> install.bat && run.bat
```

(Browser abre, intro, navegação funcional, form de Nova Pesquisa renderiza, fontes Inter aplicadas via S23.1.)

## 8. Critério de aceite (checkbox final)

- [ ] `install.bat` na raiz com CRLF + UTF-8 + `chcp 65001` + `@echo off`
- [ ] `run.bat` na raiz com CRLF + UTF-8 + `chcp 65001` + `@echo off`
- [ ] `install.bat --check` retorna `exit /b 0` em Windows com Python 3.11+
- [ ] `install.bat` completo cria `.venv\` e popula via `uv sync --all-extras`
- [ ] `install.bat` é idempotente (segunda execução não recria `.venv`)
- [ ] `run.bat` valida `.venv\` existe e sobe Streamlit em `localhost:8501`
- [ ] Detecção de Python em cascata: `where python` → `py -3.11` → erro com link `python.org`
- [ ] Mensagens PT-BR com acentuação correta (`instalação`, `dependências`, `validação`)
- [ ] CI job `smoke-install-windows` em `windows-2022` verde
- [ ] CI job assertion: `uv run hemiciclo --version` retorna `hemiciclo 2.0.0`
- [ ] 13 testes unit em `tests/unit/test_install_bat.py` verdes em todos SOs
- [ ] 3 testes integração Windows-only verdes no runner Windows do CI
- [ ] `docs/usuario/instalacao.md` cobre Windows 10/11 com troubleshooting específico
- [ ] `README.md` mostra Windows ao lado de Linux/macOS na "Instalação rápida"
- [ ] `CHANGELOG.md` entrada `[2.1.0-dev]` com bullet S36
- [ ] Mypy --strict zero erros (testes novos respeitam `--strict`)
- [ ] Ruff zero violações
- [ ] Cobertura ≥ 90% nos arquivos novos
- [ ] `make check` verde
- [ ] Acentuação periférica varrida em todos arquivos modificados (lição BRIEF)
- [ ] `sprints/ORDEM.md` atualizado: S36 → DONE com histórico

## 9. Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| `chcp 65001` falha em CMD legado pré-Windows 10 | B | M | Documentar em `instalacao.md` que Windows 10+ é mínimo; redirect "use Windows Terminal" no troubleshooting |
| `where python` retorna Python 2.x ou versão antiga preceder 3.11 no PATH | M | A | Cascata de detecção também tenta `py -3.11`; validação de versão aborta com link claro |
| Instalador uv via `irm \| iex` bloqueado por SmartScreen ou política corporativa | M | A | Documentar workaround: download manual de `astral.sh/uv/install.ps1` e execução com `-ExecutionPolicy Bypass` |
| Path com espaços (`C:\Users\Andre Farias\`) quebra `cd /d %DIR%` | M | A | Usar aspas: `cd /d "%DIR%"` em todos comandos; testar com path com espaços no smoke manual |
| Cronometragem via PowerShell falha em Windows 10 LTSC sem PS5 | B | B | Fallback: aceitar `set END=%TIME%` com cálculo simples (imprecisão <1s) |
| `uv sync` em CI windows-2022 leva > 5min e estoura timeout | M | M | Cache do uv via `actions/cache@v4` ou aceitar timeout 10min; fallback para apenas `--check` se necessário |
| Testes Windows-only não rodam em Linux dev (executor não detecta regressão) | M | M | Job CI smoke-install-windows é o gate definitivo; documentar no spec que dev Linux roda apenas testes cross-OS |
| `delayedexpansion` em `if errorlevel` não funciona como esperado | M | M | Usar `if !errorlevel! neq 0` (com `!` em vez de `%`) consistentemente; revisar antes de marcar DONE |
| Quebra de paridade futura (alguém edita install.sh sem editar install.bat) | M | M | Sprint corretiva trivial; não bloqueia esta sprint |
| Antivírus Windows quarentena `uv.exe` recém-baixado | B | A | Documentar no troubleshooting; mitigação é responsabilidade do usuário |
| LF órfão acidental em `.bat` se editor não respeitar `.gitattributes` | M | A | Teste `test_install_bat_crlf_line_endings` valida em CI cross-OS |

## 10. Validação multi-agente

**Executor (`executor-sprint`):**

1. Lê `VALIDATOR_BRIEF.md`.
2. Lê este spec.
3. Confirma branch `feature/s36-windows-install` + precondição `.gitattributes:5` com `*.bat text eol=crlf`.
4. Implementa entregas conforme passo a passo §5.1.
5. Roda proof-of-work §7.1 em dev Linux.
6. Reporta no PR a saída do `pytest` + `make check`.
7. Se tiver acesso a Windows, reporta também §7.3 manual.
8. NÃO push, NÃO PR -- orquestrador integra.

**Validador (`validador-sprint`):**

1. Lê BRIEF + spec.
2. Roda proof-of-work cross-OS (`pytest tests/unit/test_install_bat.py`).
3. Verifica I1-I12 do BRIEF:
   - I1: nenhum host proprietário em `.bat` (apenas `astral.sh/uv/install.ps1` que é open-source análogo a `astral.sh/uv/install.sh` do Linux)
   - I2: PT-BR com acento em mensagens (`instalação`, `dependências`, `validação`, `não`)
   - I4: nenhum `print()` em código Python -- N/A (sprint não toca Python de produção)
   - I9: cobertura ≥ 90% nos arquivos novos
   - I10: commits do PR seguem Conventional Commits
   - I12: `CHANGELOG.md` atualizado
4. Espera o job CI `smoke-install-windows` ficar verde antes de aprovar.
5. **NÃO aciona skill `validacao-visual`** (sprint não toca `src/hemiciclo/dashboard/`; UI inalterada).
6. Decide APROVADO / APROVADO_COM_RESSALVAS / REPROVADO.

## 11. Próximo passo após DONE

S36 sendo a **terceira e última sprint bloqueante de release público amplo** (após S27.1 e S23.1), com sua conclusão o Hemiciclo 2.1.0 fica pronto para tag pública. Próxima sprint sugerida: **S38.1 release v2.1.0** (análoga à S38 v2.0.0, fechando o ciclo com tag + push + manifesto atualizado).

Sprints READY remanescentes em `ORDEM.md` (S23.2, S23.3, S24b-f, S25.1, S25.3, S27.2, S29.1, S29.2, S28-polish, S30.1-3, S35a, S35b, S35c, S34b) podem entrar em qualquer ordem em v2.1.x ou v2.2 conforme priorização.

## 12. Referências

- BRIEF: `/home/andrefarias/Desenvolvimento/Hemiciclo/VALIDATOR_BRIEF.md`
- Plano R2: `/home/andrefarias/Desenvolvimento/Hemiciclo/docs/superpowers/specs/2026-04-27-hemiciclo-2-design.md` §12.1 e §13.2
- Spec precedente: `sprints/SPRINT_S23_SHELL_VISIVEL.md` (install.sh + run.sh Linux/macOS)
- Spec irmã: `sprints/SPRINT_S23_1_FONTES_TTF_LOCAIS.md` (auto-hospedagem para soberania)
- ADR-014: `docs/adr/ADR-014-python-pre-instalado.md` (justifica "não auto-instalar Python")
- CI multi-OS: `.github/workflows/ci.yml` (precedente windows-2022 já validado em S37)
- `.gitattributes:5` (precondição CRLF para `.bat`)
