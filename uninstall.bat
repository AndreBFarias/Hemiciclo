@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM uninstall.bat -- Remove Hemiciclo da máquina (Windows 10/11).
REM
REM Modo interativo por padrão: pergunta antes de cada remoção destrutiva.
REM Modo --yes assume sim em tudo (útil para scripts/CI).
REM
REM O que é removido (com confirmação):
REM   1. .venv\ no diretório do repo
REM   2. %USERPROFILE%\hemiciclo\ (sessões, cache, modelos, logs)
REM
REM O que NÃO é removido:
REM   - O próprio repositório git clonado
REM   - Python 3.11+
REM   - uv (em %USERPROFILE%\.local\bin\uv.exe)
REM   - Modelo bge-m3 em %USERPROFILE%\.cache\huggingface\

set "DIR=%~dp0"
set "HEMICICLO_HOME=%USERPROFILE%\hemiciclo"

set "ASSUMIR_SIM=false"
if /i "%~1"=="--yes" set "ASSUMIR_SIM=true"
if /i "%~1"=="-y" set "ASSUMIR_SIM=true"

echo [Hemiciclo] Desinstalador -- Windows.
echo.
echo Este script remove -- com confirmacao --:
echo   1. %DIR%.venv\          ambiente virtual Python
echo   2. %HEMICICLO_HOME%\    sessoes, cache, modelos, logs
echo.
echo NAO remove: o repositorio git, Python, uv, ou bge-m3 em
echo %USERPROFILE%\.cache\huggingface\. Para limpeza total, faca manualmente.
echo.

REM 1. Remove .venv
if exist "%DIR%.venv\" (
    set "REMOVER_VENV=false"
    if "!ASSUMIR_SIM!"=="true" (
        set "REMOVER_VENV=true"
    ) else (
        set /p "RESPOSTA=[Hemiciclo] Remover %DIR%.venv\? [s/N] "
        if /i "!RESPOSTA!"=="s" set "REMOVER_VENV=true"
    )
    if "!REMOVER_VENV!"=="true" (
        rmdir /s /q "%DIR%.venv"
        echo [Hemiciclo] .venv\ removido.
    ) else (
        echo [Hemiciclo] .venv\ preservado.
    )
) else (
    echo [Hemiciclo] .venv\ nao existe -- nada a fazer.
)

echo.

REM 2. Remove %HEMICICLO_HOME%
if exist "%HEMICICLO_HOME%\" (
    echo [Hemiciclo] %HEMICICLO_HOME%\ contem sessoes, cache e modelos.
    set "REMOVER_HOME=false"
    if "!ASSUMIR_SIM!"=="true" (
        set "REMOVER_HOME=true"
    ) else (
        set /p "RESPOSTA=[Hemiciclo] Remover %HEMICICLO_HOME%\? [s/N] "
        if /i "!RESPOSTA!"=="s" set "REMOVER_HOME=true"
    )
    if "!REMOVER_HOME!"=="true" (
        rmdir /s /q "%HEMICICLO_HOME%"
        echo [Hemiciclo] %HEMICICLO_HOME%\ removido.
    ) else (
        echo [Hemiciclo] %HEMICICLO_HOME%\ preservado.
    )
) else (
    echo [Hemiciclo] %HEMICICLO_HOME%\ nao existe -- nada a fazer.
)

echo.
echo [Hemiciclo] Desinstalacao concluida.
echo.
echo Se tambem quiser remover:
echo   - uv:           del %USERPROFILE%\.local\bin\uv.exe
echo   - bge-m3:       rmdir /s /q %USERPROFILE%\.cache\huggingface\hub\models--BAAI--bge-m3
echo   - repositorio:  rmdir /s /q %DIR%  -- apos sair dele

exit /b 0
