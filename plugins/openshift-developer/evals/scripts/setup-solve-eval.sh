#!/bin/bash
# Setup script for the jira-solve eval.
#
# Installs the openshift-developer plugin and all its dependencies
# (jira, golang, code-review, etc.) system-wide so inner claude -p
# sessions spawned by run-solve.sh can resolve them.
#
# Called by the CI workflow via EVAL_SETUP_SCRIPT before the eval runs.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"

echo "Installing ai-helpers plugins from ${REPO_ROOT}..."
git config --global url."https://github.com/".insteadOf "git@github.com:" 2>/dev/null || true
claude plugin marketplace add "${REPO_ROOT}"
claude plugin install openshift-developer@ai-helpers

# Validate
if ! claude plugin list --json 2>/dev/null | jq -e '.[] | select(.id | test("^openshift-developer@"))' > /dev/null 2>&1; then
    echo "ERROR: openshift-developer plugin not found after installation"
    claude plugin list 2>/dev/null || true
    exit 1
fi

echo "Plugins installed and validated."
