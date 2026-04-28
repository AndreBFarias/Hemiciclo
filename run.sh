#!/usr/bin/env bash
# run.sh -- Sobe o dashboard Streamlit do Hemiciclo em localhost:8501.
#
# Por padrão Streamlit abre o navegador automaticamente
# (``--server.headless=false``). Use Ctrl+C para encerrar.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${DIR}"

if [ ! -d ".venv" ]; then
    echo "[Hemiciclo] Erro: ambiente .venv não existe. Rode ./install.sh primeiro." >&2
    exit 1
fi

echo "[Hemiciclo] Subindo Streamlit em http://localhost:8501"
echo "[Hemiciclo] Ctrl+C para encerrar."

trap 'echo ""; echo "[Hemiciclo] Encerrando..."; exit 0' INT

uv run streamlit run src/hemiciclo/dashboard/app.py \
    --server.headless=false \
    --server.port=8501
