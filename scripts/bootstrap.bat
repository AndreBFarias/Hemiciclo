@echo off
rem Bootstrap do ambiente Hemiciclo (Windows).
rem
rem - Valida Python 3.11+.
rem - Instala uv se faltar.
rem - Sincroniza dependencias.
rem - Instala hooks de pre-commit.
rem
rem Uso:
rem   scripts\bootstrap.bat

setlocal enableextensions enabledelayedexpansion

pushd "%~dp0.."
set "RAIZ=%CD%"
echo [bootstrap] Raiz: %RAIZ%

where python >nul 2>nul
if errorlevel 1 (
    echo [erro] Python nao encontrado no PATH.
    echo [erro] Instale Python 3.11+ antes de continuar.
    popd
    exit /b 1
)

for /f "tokens=*" %%v in ('python -c "import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")"') do set "PY_VERSAO=%%v"
echo [bootstrap] Python detectado: %PY_VERSAO%

for /f "tokens=*" %%v in ('python -c "import sys; print(sys.version_info.major)"') do set "PY_MAJOR=%%v"
for /f "tokens=*" %%v in ('python -c "import sys; print(sys.version_info.minor)"') do set "PY_MINOR=%%v"

if %PY_MAJOR% LSS 3 (
    echo [erro] Python 3.11+ obrigatorio.
    popd
    exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 11 (
    echo [erro] Python 3.11+ obrigatorio. Detectado %PY_VERSAO%.
    popd
    exit /b 1
)
echo [ok] Python %PY_VERSAO% valido.

where uv >nul 2>nul
if errorlevel 1 (
    echo [bootstrap] uv nao encontrado. Instalando via PowerShell...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    where uv >nul 2>nul
    if errorlevel 1 (
        echo [erro] Falha ao instalar uv. Adicione %USERPROFILE%\.local\bin ao PATH.
        popd
        exit /b 1
    )
)
for /f "tokens=*" %%v in ('uv --version') do echo [ok] %%v

echo [bootstrap] Sincronizando dependencias...
uv sync --all-extras
if errorlevel 1 (
    echo [erro] uv sync falhou.
    popd
    exit /b 1
)
echo [ok] Dependencias sincronizadas.

echo [bootstrap] Instalando hooks de pre-commit...
uv run pre-commit install
if errorlevel 1 (
    echo [erro] pre-commit install falhou.
    popd
    exit /b 1
)
echo [ok] Hooks instalados.

echo [bootstrap] Concluido.
echo [bootstrap] Use: uv run hemiciclo --version

popd
endlocal
