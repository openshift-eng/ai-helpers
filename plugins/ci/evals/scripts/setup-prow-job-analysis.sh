#!/bin/bash
# Prepare the environment for prow-job-analysis eval runs.
#
# Unlike payload-analysis, this eval needs no pre-staged snapshot: the
# prow-job-analysis skill reads artifacts live from the PUBLIC
# test-platform-results GCS bucket (no auth required). This script therefore
# verifies the required tooling is present and prepares the working directory
# so eval cases can run deterministically.
#
# Artifact access works with the gcloud CLI when it is installed, and otherwise
# falls back to the public GCS HTTP API via the bundled
# prow_job_artifact_search.py (Python standard library only). gcloud is
# therefore OPTIONAL; python3 and jq are the only required tools.
#
# Usage: ./plugins/ci/evals/scripts/setup-prow-job-analysis.sh [prow_job_url]
#   With no argument: verify tooling and prepare .work/prow-job-analysis/.
#   With a Prow URL:  additionally best-effort pre-warm the artifact cache by
#                     listing the job's top-level GCS path (never fatal).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
WORK_DIR="$REPO_ROOT/.work/prow-job-analysis"
SEARCH_SCRIPT="$REPO_ROOT/plugins/ci/skills/prow-job-analysis/prow_job_artifact_search.py"

log() { echo "$@" >&2; }

# Required tools. gcloud is intentionally NOT in this list — the skill works
# without it via the public GCS HTTP API fallback.
missing=0
for tool in python3 jq; do
    if command -v "$tool" >/dev/null 2>&1; then
        log "OK: $tool -> $(command -v "$tool")"
    else
        log "MISSING: $tool is required by ci:prow-job-analysis"
        missing=1
    fi
done

if [[ "$missing" -ne 0 ]]; then
    log "ERROR: one or more required tools are missing; install them before running the eval."
    exit 2
fi

# Optional tool: gcloud. When absent, artifact access uses the public GCS HTTP
# API (no credentials needed), so its absence is informational, not an error.
if command -v gcloud >/dev/null 2>&1; then
    log "OK: gcloud -> $(command -v gcloud) (native GCS access)"
else
    log "INFO: gcloud not found; using the public GCS HTTP API fallback (no auth required)"
fi

mkdir -p "$WORK_DIR"
log "Prepared working directory: $WORK_DIR"

# The bucket is public; confirm read access without requiring credentials or
# gcloud. Uses python3 (already verified above) to hit the GCS JSON API.
probe_log=$(mktemp)
python3 - <<'PY' >"$probe_log" 2>&1 && probe_rc=0 || probe_rc=$?
import sys
import urllib.request

url = ("https://storage.googleapis.com/storage/v1/b/test-platform-results/o"
       "?prefix=logs/&delimiter=/&maxResults=1")
try:
    with urllib.request.urlopen(url, timeout=15) as resp:
        resp.read(1)
except Exception as e:
    print(f"GCS probe failed: {e}", file=sys.stderr)
    sys.exit(1)
PY
if [[ "$probe_rc" -eq 0 ]]; then
    log "OK: public GCS bucket test-platform-results is reachable"
else
    probe_err=$(cat "$probe_log")
    log "WARN: could not reach the public GCS API (network restricted?)${probe_err:+: ${probe_err}}; cases may not fetch artifacts"
fi
rm -f "$probe_log"

# Best-effort pre-warm using the bundled search script, which works with or
# without gcloud. Never fatal.
url="${1:-}"
if [[ -n "$url" ]]; then
    log "Pre-warming: listing top-level artifacts for the job"
    python3 "$SEARCH_SCRIPT" "$url" list >/dev/null 2>&1 \
        || log "WARN: could not list artifacts for this job (URL may be synthetic); analysis will report what is missing"
fi

# Emit the working directory on stdout for callers that want to capture it.
echo "$WORK_DIR"
