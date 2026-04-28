@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM install.bat -- Bootstrap do Hemiciclo 2.0 (Windows 10/11).
REM
REM Pré-requisitos:
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
REM Flags suportadas:
REM   --check        Valida ambiente sem instalar (útil para CI smoke).
REM   --com-modelo   Após instalar deps, baixa o modelo BAAI/bge-m3 (~2GB).
REM                  Alias: --com-bge.
REM   --dry-run      Imprime plano de execução e sai. Combinável com
REM                  --com-modelo para inspecionar o passo de download
REM                  sem efetivar o sync nem o download.

set "DIR=%~dp0"

set "CHECK_ONLY=0"
set "COM_MODELO=0"
set "DRY_RUN=0"

:parse_args
if "%~1"=="" goto :end_parse
if /i "%~1"=="--check" set "CHECK_ONLY=1"
if /i "%~1"=="--com-modelo" set "COM_MODELO=1"
if /i "%~1"=="--com-bge" set "COM_MODELO=1"
if /i "%~1"=="--dry-run" set "DRY_RUN=1"
shift
goto :parse_args
:end_parse

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
if !PY_MAJOR! EQU 3 (
    if !PY_MINOR! LSS 11 (
        echo [Hemiciclo] Erro: Python !PY_VER! detectado, requer 3.11+. >&2
        echo   Instale Python 3.11+ de https://python.org/downloads >&2
        exit /b 1
    )
)

echo [Hemiciclo] Python !PY_VER! OK.

if "!CHECK_ONLY!"=="1" (
    echo [Hemiciclo] Modo --check: validação OK, sem instalar.
    if "!COM_MODELO!"=="1" (
        echo [Hemiciclo] ^(--com-modelo ignorado em --check^)
    )
    exit /b 0
)

if "!DRY_RUN!"=="1" (
    echo [Hemiciclo] Modo --dry-run: plano de execução
    echo   1. Instalar uv ^(se ausente^)
    echo   2. uv sync --all-extras
    if "!COM_MODELO!"=="1" (
        echo   3. Baixar BAAI/bge-m3 via FlagEmbedding ^(~2GB, 5-15min^)
    ) else (
        echo   3. ^(sem --com-modelo: bge-m3 nao sera baixado^)
    )
    echo [Hemiciclo] --dry-run: nenhuma acao efetuada.
    exit /b 0
)

where uv >nul 2>&1
if !errorlevel! neq 0 (
    echo [Hemiciclo] Instalando uv...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=!USERPROFILE!\.local\bin;!PATH!"
)

where uv >nul 2>&1
if !errorlevel! neq 0 (
    echo [Hemiciclo] Erro: uv nao disponivel mesmo apos instalacao. >&2
    echo   Adicione !USERPROFILE!\.local\bin ao PATH e tente novamente. >&2
    exit /b 1
)

cd /d "%DIR%"

if exist ".venv\" (
    echo [Hemiciclo] Ambiente .venv ja existe, sincronizando dependências...
) else (
    echo [Hemiciclo] Sincronizando dependências -- pode levar 3-5 min...
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

if "!COM_MODELO!"=="1" (
    echo.
    echo [Hemiciclo] --com-modelo: baixando BAAI/bge-m3 ^(~2GB, pode levar 5-15min^)...
    echo [Hemiciclo] O modelo e cacheado em %%USERPROFILE%%\.cache\huggingface\hub e reutilizado entre sessoes.
    REM Gera script temporário para evitar pegadinhas de escape multilinha em CMD.
    set "DL_SCRIPT=%TEMP%\hemiciclo_baixar_bge_m3.py"
    > "!DL_SCRIPT!" echo import sys
    >> "!DL_SCRIPT!" echo try:
    >> "!DL_SCRIPT!" echo     from FlagEmbedding import BGEM3FlagModel
    >> "!DL_SCRIPT!" echo     BGEM3FlagModel^('BAAI/bge-m3', use_fp16=False^)
    >> "!DL_SCRIPT!" echo     print^('[Hemiciclo] bge-m3 baixado e validado com sucesso.'^)
    >> "!DL_SCRIPT!" echo except ImportError as exc:
    >> "!DL_SCRIPT!" echo     print^(f'[Hemiciclo] Erro: FlagEmbedding indisponivel ^({exc}^).', file=sys.stderr^)
    >> "!DL_SCRIPT!" echo     sys.exit^(2^)
    >> "!DL_SCRIPT!" echo except Exception as exc:
    >> "!DL_SCRIPT!" echo     print^(f'[Hemiciclo] Falha graciosa no download de bge-m3: {exc}', file=sys.stderr^)
    >> "!DL_SCRIPT!" echo     sys.exit^(3^)
    uv run python "!DL_SCRIPT!"
    set "DOWNLOAD_RC=!errorlevel!"
    del "!DL_SCRIPT!" >nul 2>&1
    if !DOWNLOAD_RC! neq 0 (
        echo [Hemiciclo] Aviso: download de bge-m3 falhou ^(exit !DOWNLOAD_RC!^). >&2
        echo   A instalacao base esta OK. Voce pode rodar o dashboard sem o modelo; >&2
        echo   a camada de embeddings ^(C3^) ficara em skip silencioso ate o download. >&2
    )
)

echo [Hemiciclo] Para iniciar o dashboard: run.bat
echo [Hemiciclo] Para sanidade do CLI: uv run hemiciclo info
exit /b 0
