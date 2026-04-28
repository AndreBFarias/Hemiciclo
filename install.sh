#!/usr/bin/env bash
# install.sh -- Bootstrap do Hemiciclo 2.0 (Linux/macOS).
#
# Pré-requisitos:
#   - Python 3.11 ou superior já instalado e disponível como ``python3``.
#   - Conexão de internet (para baixar uv e dependências).
#
# O que faz:
#   1. Detecta o SO via ``uname -s``.
#   2. Valida ``python3 --version`` >= 3.11.
#   3. Instala ``uv`` no diretório do usuário se ausente.
#   4. Roda ``uv sync --all-extras`` para popular ``.venv``.
#   5. Imprime tempo decorrido e o comando ``./run.sh``.
#
# Flags suportadas:
#   --check         Valida ambiente sem instalar (útil para CI smoke).
#   --com-modelo    Após instalar deps, baixa o modelo BAAI/bge-m3 (~2GB).
#                   Alias: --com-bge.
#   --dry-run       Imprime plano de execução e sai. Combinável com
#                   --com-modelo para inspecionar o passo de download
#                   sem efetivar o sync nem o download.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SO="$(uname -s)"

CHECK_ONLY=0
COM_MODELO=0
DRY_RUN=0

for arg in "$@"; do
    case "${arg}" in
        --check)
            CHECK_ONLY=1
            ;;
        --com-modelo|--com-bge)
            COM_MODELO=1
            ;;
        --dry-run)
            DRY_RUN=1
            ;;
        -h|--help)
            sed -n '1,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "[Hemiciclo] Aviso: argumento desconhecido '${arg}' ignorado." >&2
            ;;
    esac
done

echo "[Hemiciclo] Sistema operacional detectado: ${SO}"

case "${SO}" in
    Linux*|Darwin*) ;;
    *)
        echo "[Hemiciclo] Erro: SO ${SO} não suportado por este script." >&2
        echo "  Para Windows, use install.bat (paridade desde S36)." >&2
        exit 1
        ;;
esac

echo "[Hemiciclo] Verificando Python 3.11+..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "[Hemiciclo] Erro: python3 não encontrado." >&2
    echo "  Instale Python 3.11+ de https://python.org/downloads" >&2
    echo "  Ubuntu/Debian:  sudo apt-get install python3.11 python3.11-venv" >&2
    echo "  Fedora:         sudo dnf install python3.11" >&2
    echo "  macOS (Homebrew): brew install python@3.11" >&2
    exit 1
fi

PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_MAJOR="$(echo "${PY_VER}" | cut -d. -f1)"
PY_MINOR="$(echo "${PY_VER}" | cut -d. -f2)"

if [ "${PY_MAJOR}" -lt 3 ] || { [ "${PY_MAJOR}" -eq 3 ] && [ "${PY_MINOR}" -lt 11 ]; }; then
    echo "[Hemiciclo] Erro: Python ${PY_VER} detectado, requer 3.11+." >&2
    echo "  Instale Python 3.11+ de https://python.org/downloads" >&2
    exit 1
fi

echo "[Hemiciclo] Python ${PY_VER} OK."

if [ "${CHECK_ONLY}" -eq 1 ]; then
    echo "[Hemiciclo] Modo --check: validação OK, sem instalar."
    if [ "${COM_MODELO}" -eq 1 ]; then
        echo "[Hemiciclo] (--com-modelo ignorado em --check)"
    fi
    exit 0
fi

if [ "${DRY_RUN}" -eq 1 ]; then
    echo "[Hemiciclo] Modo --dry-run: plano de execução"
    echo "  1. Instalar uv (se ausente)"
    echo "  2. uv sync --all-extras"
    if [ "${COM_MODELO}" -eq 1 ]; then
        echo "  3. Baixar BAAI/bge-m3 via FlagEmbedding (~2GB, 5-15min)"
    else
        echo "  3. (sem --com-modelo: bge-m3 não será baixado)"
    fi
    echo "[Hemiciclo] --dry-run: nenhuma ação efetuada."
    exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "[Hemiciclo] Instalando uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Instalador padrão do uv coloca o binário em ~/.local/bin.
    export PATH="${HOME}/.local/bin:${PATH}"
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "[Hemiciclo] Erro: uv não disponível mesmo após instalação." >&2
    echo "  Adicione ${HOME}/.local/bin ao PATH e tente novamente." >&2
    exit 1
fi

cd "${DIR}"

START=$(date +%s)
echo "[Hemiciclo] Sincronizando dependências (pode levar 3-5 min)..."
uv sync --all-extras
END=$(date +%s)
DECORRIDO=$((END - START))

echo ""
echo "[Hemiciclo] Instalação concluída em ${DECORRIDO}s."

if [ "${COM_MODELO}" -eq 1 ]; then
    echo ""
    echo "[Hemiciclo] --com-modelo: baixando BAAI/bge-m3 (~2GB, pode levar 5-15min)..."
    echo "[Hemiciclo] O modelo é cacheado em ~/.cache/huggingface/hub e reutilizado entre sessões."
    set +e
    uv run python -c "
import sys
try:
    from FlagEmbedding import BGEM3FlagModel
    BGEM3FlagModel('BAAI/bge-m3', use_fp16=False)
    print('[Hemiciclo] bge-m3 baixado e validado com sucesso.')
except ImportError as exc:
    print(f'[Hemiciclo] Erro: FlagEmbedding indisponível ({exc}).', file=sys.stderr)
    print('  Verifique se uv sync --all-extras concluiu sem erro.', file=sys.stderr)
    sys.exit(2)
except Exception as exc:
    print(f'[Hemiciclo] Falha graciosa no download de bge-m3: {exc}', file=sys.stderr)
    print('  Causas comuns: sem internet, Hugging Face Hub fora do ar, espaço em disco.', file=sys.stderr)
    print('  Você pode tentar de novo manualmente com:', file=sys.stderr)
    print(\"    uv run python -c 'from FlagEmbedding import BGEM3FlagModel; BGEM3FlagModel(\\\"BAAI/bge-m3\\\", use_fp16=False)'\", file=sys.stderr)
    sys.exit(3)
"
    DOWNLOAD_RC=$?
    set -e
    if [ "${DOWNLOAD_RC}" -ne 0 ]; then
        echo "[Hemiciclo] Aviso: download de bge-m3 falhou (exit ${DOWNLOAD_RC})." >&2
        echo "  A instalação base está OK. Você pode rodar o dashboard sem o modelo;" >&2
        echo "  a camada de embeddings (C3) ficará em skip silencioso até o download." >&2
    fi
fi

echo "[Hemiciclo] Para iniciar o dashboard: ./run.sh"
echo "[Hemiciclo] Para sanidade do CLI: uv run hemiciclo info"
