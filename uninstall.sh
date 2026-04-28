#!/usr/bin/env bash
# uninstall.sh -- Remove Hemiciclo da máquina (Linux/macOS).
#
# Modo interativo por padrão: pergunta antes de cada remoção destrutiva.
# Modo --yes assume sim em tudo (útil para scripts/CI).
#
# O que é removido (com confirmação):
#   1. .venv/ no diretório do repo
#   2. ~/hemiciclo/ (sessões, cache, modelos, logs)
#
# O que NÃO é removido (cabe ao usuário decidir):
#   - O próprio repositório git clonado
#   - Python 3.11+
#   - uv (em ~/.local/bin/uv)
#   - Modelo bge-m3 baixado em ~/.cache/huggingface/

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEMICICLO_HOME="${HEMICICLO_HOME:-${HOME}/hemiciclo}"

ASSUMIR_SIM=false
if [ "${1:-}" = "--yes" ] || [ "${1:-}" = "-y" ]; then
    ASSUMIR_SIM=true
fi

echo "[Hemiciclo] Desinstalador (Python)."
echo ""
echo "Este script remove (com confirmação):"
echo "  1. ${DIR}/.venv/         (ambiente virtual Python)"
echo "  2. ${HEMICICLO_HOME}/    (sessões, cache, modelos, logs)"
echo ""
echo "NÃO remove: o próprio repositório git, Python, uv, ou bge-m3 em"
echo "~/.cache/huggingface/. Para limpeza total, faça manualmente."
echo ""

confirmar() {
    if [ "${ASSUMIR_SIM}" = true ]; then
        return 0
    fi
    local pergunta="${1}"
    read -r -p "[Hemiciclo] ${pergunta} [s/N] " resposta
    [[ "${resposta,,}" == "s" ]]
}

# 1. Remove .venv
if [ -d "${DIR}/.venv" ]; then
    if confirmar "Remover ${DIR}/.venv/?"; then
        rm -rf "${DIR}/.venv"
        echo "[Hemiciclo] .venv/ removido."
    else
        echo "[Hemiciclo] .venv/ preservado."
    fi
else
    echo "[Hemiciclo] .venv/ não existe (nada a fazer)."
fi

# 2. Remove ~/hemiciclo/
if [ -d "${HEMICICLO_HOME}" ]; then
    tamanho=$(du -sh "${HEMICICLO_HOME}" 2>/dev/null | cut -f1 || echo "?")
    echo ""
    echo "[Hemiciclo] ${HEMICICLO_HOME}/ ocupa ${tamanho} (sessões, cache, modelos)."
    if confirmar "Remover ${HEMICICLO_HOME}/?"; then
        rm -rf "${HEMICICLO_HOME}"
        echo "[Hemiciclo] ${HEMICICLO_HOME}/ removido."
    else
        echo "[Hemiciclo] ${HEMICICLO_HOME}/ preservado."
    fi
else
    echo "[Hemiciclo] ${HEMICICLO_HOME}/ não existe (nada a fazer)."
fi

echo ""
echo "[Hemiciclo] Desinstalação concluída."
echo ""
echo "Se também quiser remover:"
echo "  - uv:           rm ~/.local/bin/uv ~/.local/bin/uvx ~/.local/bin/uvw"
echo "  - bge-m3:       rm -rf ~/.cache/huggingface/hub/models--BAAI--bge-m3"
echo "  - o repositório: rm -rf ${DIR}  (após sair dele)"
