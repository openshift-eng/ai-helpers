#!/usr/bin/env bash

set -euo pipefail

CODEX_BIN=/opt/codex/bin/codex

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    printf '%s' "${OPENAI_API_KEY}" \
        | env -u OPENAI_API_KEY "${CODEX_BIN}" login --with-api-key >/dev/null 2>&1
    unset OPENAI_API_KEY
fi

exec "${CODEX_BIN}" "$@"
