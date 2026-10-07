#!/bin/bash
# Module repair helper for k8s-rebase. Run in the affected module.
# Usage: bash scripts/k8s-rebase-depfix.sh <module>[@version]  # bump, then sync
#        bash scripts/k8s-rebase-depfix.sh --sync              # sync after a replace
# Sync runs go mod tidy, then go mod vendor when vendor/ exists.
# Exempted from block-module-ops.sh via script-invocation regex.
# It does not enforce Kubernetes pins; verify them afterward.
set -euo pipefail

[[ $# -eq 1 ]] || { echo "Usage: k8s-rebase-depfix.sh <module>[@version] | --sync" >&2; exit 1; }

if [[ "$1" != --sync ]]; then
  [[ "$1" != -* ]] || { echo "ERROR: unknown option: $1" >&2; exit 1; }
  MODULE="$1"
  [[ "$MODULE" == *@* ]] || MODULE="${MODULE}@latest"
  echo ":: depfix: go get ${MODULE}"
  go get "$MODULE"
fi

echo ":: depfix: go mod tidy"
go mod tidy

if [[ -d vendor ]]; then
  echo ":: depfix: go mod vendor"
  go mod vendor
fi
