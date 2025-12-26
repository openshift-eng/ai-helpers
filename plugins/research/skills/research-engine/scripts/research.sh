#!/usr/bin/env bash
#
# Research Plugin Wrapper
# Automatically creates and uses a Python 3.12 virtual environment
# to avoid compatibility issues with bleeding-edge Python versions.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${SCRIPT_DIR}/../../../../../.work/research"
VENV_DIR="${WORK_DIR}/venv"
PYTHON_SCRIPT="${SCRIPT_DIR}/build_context.py"

# Find a compatible Python (3.10, 3.11, or 3.12)
find_python() {
    for py in python3.12 python3.11 python3.10; do
        if command -v "$py" &>/dev/null; then
            echo "$py"
            return 0
        fi
    done
    # Fallback to python3
    echo "python3"
}

# Create venv if needed
setup_venv() {
    if [[ ! -f "${VENV_DIR}/bin/python" ]]; then
        echo "🔧 Creating virtual environment..." >&2
        mkdir -p "${WORK_DIR}"
        
        PYTHON_CMD=$(find_python)
        echo "   Using: ${PYTHON_CMD}" >&2
        
        "${PYTHON_CMD}" -m venv "${VENV_DIR}"
        
        echo "📦 Installing dependencies..." >&2
        "${VENV_DIR}/bin/pip" install --quiet --upgrade pip
        "${VENV_DIR}/bin/pip" install --quiet \
            chromadb \
            sentence-transformers \
            trafilatura \
            beautifulsoup4 \
            requests \
            yt-dlp
        
        echo "✅ Environment ready!" >&2
    fi
}

# Main
case "${1:-}" in
    build|"")
        setup_venv
        shift 2>/dev/null || true
        exec "${VENV_DIR}/bin/python" "${PYTHON_SCRIPT}" "$@"
        ;;
    query)
        setup_venv
        shift
        exec "${VENV_DIR}/bin/python" "${SCRIPT_DIR}/query.py" "$@"
        ;;
    context|list)
        setup_venv
        shift
        exec "${VENV_DIR}/bin/python" "${SCRIPT_DIR}/list_context.py" "$@"
        ;;
    help|-h|--help)
        echo "Usage: research.sh <command> [options]"
        echo ""
        echo "Commands:"
        echo "  build   - Build context from sources (default)"
        echo "  query   - Query the knowledge base"
        echo "  context - List indexed sources"
        echo ""
        echo "Examples:"
        echo "  ./research.sh build https://docs.example.com/"
        echo "  ./research.sh build --include-cwd"
        echo "  ./research.sh query 'How does X work?'"
        echo "  ./research.sh context"
        ;;
    *)
        # Assume it's a URL/source, pass to build
        setup_venv
        exec "${VENV_DIR}/bin/python" "${PYTHON_SCRIPT}" "$@"
        ;;
esac

