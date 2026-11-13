#!/bin/bash
# Asserts each companion .sh has a matching EVIDENCE template in its .md,
# and every .md with an EVIDENCE template has a companion .sh.
# Run before shipping Phase 3 companions to catch missing template pastes.
set -euo pipefail

PLUGIN_ROOT=$(cd "$(dirname "$0")/.." && pwd)
GATES_DIR="$PLUGIN_ROOT/gates"

failures=0

# Forward: each .sh must have a matching .md with the template
while IFS= read -r sh_file; do
  gate=$(basename "$sh_file" .sh)
  md_file="$(dirname "$sh_file")/$gate.md"
  if [[ ! -f "$md_file" ]]; then
    echo "FAIL: $sh_file has no matching .md"
    ((failures++)) || true
    continue
  fi
  if ! grep -q 'EVIDENCE (read before judging):' "$md_file"; then
    echo "FAIL: $md_file missing EVIDENCE template (companion: $(basename "$sh_file"))"
    ((failures++)) || true
  fi
done < <(find "$GATES_DIR" -name '*.sh' | LC_ALL=C sort)

# Reverse: each .md with template must have a companion .sh
while IFS= read -r md_file; do
  gate=$(basename "$md_file" .md)
  sh_file="$(dirname "$md_file")/$gate.sh"
  if [[ ! -f "$sh_file" ]]; then
    echo "FAIL: $(basename "$md_file") has EVIDENCE template but no companion $gate.sh"
    ((failures++)) || true
  fi
done < <(grep -rl 'EVIDENCE (read before judging):' "$GATES_DIR" | LC_ALL=C sort)

if [[ "$failures" -gt 0 ]]; then
  echo "FAIL: $failures evidence-path mismatch(es)"
  exit 1
fi

total=$(find "$GATES_DIR" -name '*.sh' | wc -l | tr -d ' ')
if [[ "$total" -lt 8 ]]; then
  echo "FAIL: expected at least 8 companion/template pairs, found $total (mass deletion?)"
  exit 1
fi
echo "OK: $total companion/template pairs verified"
