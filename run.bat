@echo off
chcp 65001 >nul 2>&1
setlocal

REM run.bat -- Sobe o dashboard Streamlit do Hemiciclo em localhost:8501.
REM
REM Por padrão Streamlit abre o navegador automaticamente
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
