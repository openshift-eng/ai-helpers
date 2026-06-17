#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .pre-commit-config.yaml ]; then
  exit 0
fi

if ! command -v pre-commit &>/dev/null; then
  echo "ERROR: pre-commit is required but not found on PATH" >&2
  exit 2
fi

pre-commit install --hook-type pre-commit >&2
pre-commit install --hook-type pre-push >&2
echo "pre-commit hooks installed" >&2
