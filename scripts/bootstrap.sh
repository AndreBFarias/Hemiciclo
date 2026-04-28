#!/usr/bin/env bash
# Bootstrap do ambiente Hemiciclo (Linux / macOS).
#
# - Detecta SO.
# - Valida Python 3.11+.
# - Instala uv se faltar.
# - Sincroniza dependencias (`uv sync --all-extras`).
# - Instala hooks de pre-commit.
#
# Uso:
#   ./scripts/bootstrap.sh

set -euo pipefail

cd "$(dirname "$0")/.."
RAIZ="$(pwd)"

cor_info() { printf '\033[1;34m[bootstrap]\033[0m %s\n' "$*"; }
cor_ok()   { printf '\033[1;32m[ok]\033[0m %s\n' "$*"; }
cor_erro() { printf '\033[1;31m[erro]\033[0m %s\n' "$*" >&2; }

case "$(uname -s)" in
    Linux*)  SO="linux" ;;
    Darwin*) SO="macos" ;;
    *)       SO="desconhecido" ;;
esac
cor_info "SO detectado: ${SO}"

if ! command -v python3 >/dev/null 2>&1; then
    cor_erro "Python 3 não encontrado no PATH."
    cor_erro "Instale Python 3.11+ antes de continuar."
    exit 1
fi

PY_VERSAO="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
cor_info "Python detectado: ${PY_VERSAO}"

PY_MAJOR="$(python3 -c 'import sys; print(sys.version_info.major)')"
PY_MINOR="$(python3 -c 'import sys; print(sys.version_info.minor)')"
if [ "${PY_MAJOR}" -lt 3 ] || { [ "${PY_MAJOR}" -eq 3 ] && [ "${PY_MINOR}" -lt 11 ]; }; then
    cor_erro "Python 3.11+ obrigatorio. Detectado ${PY_VERSAO}."
    exit 1
fi
cor_ok "Python ${PY_VERSAO} valido."

if ! command -v uv >/dev/null 2>&1; then
    cor_info "uv não encontrado. Instalando..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="${HOME}/.local/bin:${PATH}"
    if ! command -v uv >/dev/null 2>&1; then
        cor_erro "Falha ao instalar uv. Adicione ~/.local/bin ao PATH manualmente."
        exit 1
    fi
fi
cor_ok "uv: $(uv --version)"

cor_info "Sincronizando dependencias (uv sync --all-extras)..."
uv sync --all-extras
cor_ok "Dependencias sincronizadas."

cor_info "Instalando hooks de pre-commit..."
uv run pre-commit install
cor_ok "Hooks instalados."

cor_info "Bootstrap concluido em ${RAIZ}."
cor_info "Ative o venv com: source .venv/bin/activate"
cor_info "Ou use:           uv run hemiciclo --version"
