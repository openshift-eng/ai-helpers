#!/bin/bash
# Fix a single incompatible dependency during k8s-rebase.
# Usage: bash scripts/k8s-rebase-depfix.sh <module>[@version]
# Exempted from block-module-ops.sh via script-invocation regex.
set -euo pipefail

[[ $# -eq 1 ]] || { echo "Usage: k8s-rebase-depfix.sh <module>[@version]" >&2; exit 1; }

MODULE="$1"
[[ "$MODULE" == *@* ]] || MODULE="${MODULE}@latest"

echo ":: depfix: go get ${MODULE}"
go get "$MODULE"

echo ":: depfix: go mod tidy"
go mod tidy

if [[ -d vendor ]]; then
  echo ":: depfix: go mod vendor"
  go mod vendor
fi
