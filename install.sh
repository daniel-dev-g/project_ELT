#!/bin/bash
set -e

if ! command -v uv &>/dev/null; then
    echo "uv no encontrado — instalando..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

uv sync

echo ""
echo "Instalación completa."
echo "Lanza la interfaz con:  uv run python gui.py"
