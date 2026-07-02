#!/bin/bash
# Prepare the environment for prow-job-analysis eval runs.
#
# Unlike payload-analysis, this eval needs no pre-staged snapshot: the
# prow-job-analysis skill reads artifacts live from the PUBLIC
# test-platform-results GCS bucket (no auth required). This script therefore
# verifies the required tooling is present and prepares the working directory
# so eval cases can run deterministically.
#
# Usage: ./plugins/ci/evals/scripts/setup-prow-job-analysis.sh [prow_job_url]
#   With no argument: verify tooling and prepare .work/prow-job-analysis/.
#   With a Prow URL:  additionally best-effort pre-warm the artifact cache by
#                     listing the job's top-level GCS path (never fatal).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
WORK_DIR="$REPO_ROOT/.work/prow-job-analysis"

log() { echo "$@" >&2; }

missing=0
for tool in gcloud python3 jq; do
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

mkdir -p "$WORK_DIR"
log "Prepared working directory: $WORK_DIR"

# The bucket is public; confirm read access without requiring credentials.
if gcloud storage ls "gs://test-platform-results/" >/dev/null 2>&1; then
    log "OK: public GCS bucket test-platform-results is reachable"
else
    log "WARN: could not list gs://test-platform-results/ (network restricted?); cases may not fetch artifacts"
fi

url="${1:-}"
if [[ -n "$url" ]]; then
    # Best-effort pre-warm: derive the bucket path and list it. Never fatal.
    bucket_path="${url#*test-platform-results/}"
    bucket_path="${bucket_path%%\?*}"
    if [[ -n "$bucket_path" && "$bucket_path" != "$url" ]]; then
        log "Pre-warming: gs://test-platform-results/${bucket_path}/"
        gcloud storage ls "gs://test-platform-results/${bucket_path}/" >/dev/null 2>&1 \
            || log "WARN: could not list artifacts for this job (URL may be synthetic); analysis will report what is missing"
    fi
fi

# Emit the working directory on stdout for callers that want to capture it.
echo "$WORK_DIR"
