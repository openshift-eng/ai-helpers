# Payload Analysis Eval Framework

Reproducible evaluation framework for the `analyze-payload` skill. Uses archived
CI artifacts and cached API responses so evaluations produce consistent results
independent of live infrastructure state.

## Quick Start

```bash
# 1. Set up environment (only two variables needed)
export EVAL_ARCHIVES_DIR="/path/to/archives"
export PATH="$(pwd)/eval/shims:$PATH"

# 2. Run all cases
/eval-run --model claude-opus-4-6

# 3. Run a specific case
/eval-run --case case-006 --model claude-opus-4-6

# 4. Log results to MLflow
/eval-mlflow --action log-results --run-id <id>
```

## Problem

The analyze-payload skill queries live external systems:
- **GCS** (`gcloud storage ls/cp/cat`) for Prow job artifacts (JUnit XML, build logs, must-gather bundles)
- **Release Controller API** via `fetch_payloads.py` for payload metadata and blocking job results
- **Sippy API** via `fetch_new_prs_in_payload.py` for PR lists per payload
- **GitHub API** via `gh` for revert PR searches

GCS artifacts are garbage-collected after 30-90 days, and API responses change
as new payloads are created. This makes eval cases non-reproducible over time.

## Solution

Archive everything the skill needs into local directories, then intercept
external calls with shims and cached responses:

```
archives/{payload-tag}/
├── api-responses/
│   ├── fetch-payloads-{arch}-{version}-{stream}.json
│   ├── fetch-new-prs-{payload-tag}.json
│   ├── curl-rc-*.json                 # release controller API responses
│   └── curl-sippy-*.json              # Sippy API responses
├── gh-cache/
│   ├── {org}/{repo}/{pr_number}.json  # gh pr view responses
│   ├── {repo}/pr-list-*.json          # gh pr list responses
│   ├── api/*.json                     # gh api responses
│   └── raw/*                          # raw.githubusercontent.com content
├── test-platform-results/
│   └── logs/
│       ├── {job-name}/{build-id}/     # full artifact trees for each failed job
│       └── ...
├── reference/                         # gold-standard outputs from original analysis
│   ├── payload-results-*.yaml
│   ├── payload-analysis-*-summary.html
│   └── payload-analysis-*-autodl.json
├── failed-direct-jobs.txt
└── failed-aggregated-jobs.txt
```

### Shims

All shims use a single environment variable: `EVAL_ARCHIVES_DIR`. When set,
they search `$EVAL_ARCHIVES_DIR/*/` for matching cached data.

**`eval/shims/gcloud`** — intercepts `gcloud storage ls/cp/cat` commands.
Serves files from local archive directories. Supports transparent extraction
of `.tar.gz` archives on demand.

**`eval/shims/curl`** — intercepts curl calls to gcsweb (serves local files
or generates HTML directory listings), release controller API, Sippy API, and
GitHub raw content. Falls through to real curl for other URLs.

**`eval/shims/gh`** — intercepts `gh pr view`, `gh pr list`, and `gh api`
commands. Serves cached responses or returns empty results.

### Cached API Responses

`fetch_payloads.py` and `fetch_new_prs_in_payload.py` check `EVAL_ARCHIVES_DIR`
for cached JSON files matching their arguments before making API calls.
Multiple caches are automatically merged (deduplicated by tag) to support
multi-case evaluation.

## Creating an Archive

### From a Claude Session Tarball

When the payload agent has already analyzed a payload, extract the API responses
from the session tarball and download GCS artifacts:

```bash
# 1. Download session tarball from GCS
gcloud storage cp "gs://test-platform-results/logs/periodic-ci-openshift-release-main-claude-payload-agent/{build-id}/artifacts/.../claude-sessions-*.tar" /tmp/

# 2. Extract API responses and job lists
python3 plugins/ci/skills/archive-payload-result/extract_session_data.py /tmp/claude-sessions-*.tar eval/archives/{payload-tag}

# 3. Download GCS artifacts for failed jobs
while read p; do
  mkdir -p "eval/archives/{payload-tag}/$p"
  gcloud storage cp -r "gs://$p/*" "eval/archives/{payload-tag}/$p/" &
done < eval/archives/{payload-tag}/failed-direct-jobs.txt
wait

# 4. Download aggregated job artifacts
while read p; do
  mkdir -p "eval/archives/{payload-tag}/$p"
  gcloud storage cp -r "gs://$p/*" "eval/archives/{payload-tag}/$p/" &
done < eval/archives/{payload-tag}/failed-aggregated-jobs.txt
wait

# 5. Download reference outputs (gold standard from original analysis)
gcloud storage cp "gs://test-platform-results/logs/periodic-ci-openshift-release-main-claude-payload-agent/{build-id}/artifacts/.../payload-results-*.yaml" eval/archives/{payload-tag}/reference/
gcloud storage cp "gs://test-platform-results/logs/periodic-ci-openshift-release-main-claude-payload-agent/{build-id}/artifacts/.../payload-analysis-*-summary.html" eval/archives/{payload-tag}/reference/
gcloud storage cp "gs://test-platform-results/logs/periodic-ci-openshift-release-main-claude-payload-agent/{build-id}/artifacts/.../payload-analysis-*-autodl.json" eval/archives/{payload-tag}/reference/
```

### Using the Archive Skill

For payloads still within the API's rolling window, invoke the skill:

```
/ci:archive-payload-result 4.22.0-0.nightly-2026-03-20-053450
```

This automatically fetches API responses, discovers failed jobs, downloads
GCS artifacts, finds and extracts the Claude session tarball for cached tool
responses, saves reference outputs, and compresses the archive.

### Creating the Test Case

After archiving, create a case directory:

```
eval/cases/{case-name}/
├── input.yaml         # payload_tag field
└── annotations.yaml   # expected outcomes and revert candidates
```

**input.yaml:**
```yaml
payload_tag: "4.22.0-0.ci-2026-03-31-170515"
```

**annotations.yaml:**
```yaml
expected_phase: Rejected
expected_failed_job_count: 2
has_revert_candidates: true
force_accept_expected: false

expected_candidates:
  - pr_url: "https://github.com/openshift/hypershift/pull/7790"
    component: "hypershift"
    min_confidence: 85
    expected_confidence: 95
    description: "Brief description of what the PR changed"
    expected_failing_jobs:
      - "job-name-1"
      - "job-name-2"

notes: >
  Free-text description of the test case.
```

## Archive Compression

Payload archives can be large. The `compress-archives.sh` script compresses
archive directories into `.tar.gz` files to save disk space, and the gcloud
shim transparently extracts them on demand during eval runs.

### Compressing Archives

```bash
# Compress all uncompressed archive directories (removes originals)
eval/scripts/compress-archives.sh

# Compress but keep the original directories
eval/scripts/compress-archives.sh --keep

# Specify a custom archives directory
eval/scripts/compress-archives.sh --archives-dir /path/to/archives
```

Directories that already have a corresponding `.tar.gz` are skipped. The script
reports before/after sizes for each archive.

### Decompressing Archives

```bash
# Extract all .tar.gz files that don't have a corresponding directory
eval/scripts/compress-archives.sh --decompress
```

### Transparent Extraction

The gcloud shim automatically extracts compressed archives when needed. If a
GCS path lookup fails against existing directories, the shim checks for
`.tar.gz` files, extracts the matching archive (using `flock` to prevent
concurrent extraction races), and retries the lookup. No manual decompression
is required before running evals.

### Example Workflow

```bash
# After creating archives, compress them to save space
eval/scripts/compress-archives.sh --archives-dir eval/archives

# Run evals as normal — compressed archives are extracted transparently
/eval-run --case archived --model claude-opus-4-6

# To manually decompress all archives (e.g., for inspection)
eval/scripts/compress-archives.sh --decompress --archives-dir eval/archives
```

## Running an Eval

### Environment Setup

Set environment variables before starting Claude Code:

```bash
export PATH="$(pwd)/eval/shims:$PATH"
export EVAL_ARTIFACT_ARCHIVE="$(pwd)/eval/archives"
export EVAL_ARCHIVES_DIR="$(pwd)/eval/archives"
export EVAL_CACHED_RESPONSES="$(pwd)/eval/archives"
export EVAL_GH_CACHE="$(pwd)/eval/archives"
```

### Run

```bash
# Run all archived cases
/eval-run --case archived --model claude-opus-4-6

# Run a specific case
/eval-run --case case-008 --model claude-opus-4-6

# Run without LLM judges (faster, inline checks only)
/eval-run --case case-006 --model claude-opus-4-6 --no-judge
```

### How the Eval Harness Connects

The `eval.yaml` `execution.env` block passes environment variables into the
skill's workspace via `.claude/settings.json`. The harness resolves `$VAR`
from the caller's `os.environ`. PATH is automatically forwarded.

## Test Cases

| Case | Payload | Stream | Failures | Key Revert Candidate |
|------|---------|--------|----------|---------------------|
| 006 | 4.22.0-0.nightly-2026-03-20-053450 | nightly | 3 jobs | cluster-ingress-operator#1354 (95), oc#2232 (90) |
| 007 | 4.22.0-0.ci-2026-03-31-050515 | ci | 3 jobs | cloud-credential-operator#978 (95) |
| 008 | 4.22.0-0.ci-2026-03-31-170515 | ci | 2 jobs | hypershift#7790 (95), hypershift#8138 (50) |
| 009 | 4.22.0-0.nightly-2026-03-18-161724 | nightly | 3 jobs | cluster-version-operator#1309 (95) |
| 010 | 5.0.0-0.ci-2026-05-07-142711 | ci | 2 jobs | cluster-network-operator#2959 (90) |
| 011 | 5.0.0-0.nightly-2026-04-27-183150 | nightly | 2 jobs | cluster-monitoring-operator#2814 (95) |
| 012 | 5.0.0-0.ci-2026-04-14-085906 | ci | 1 job | **FALSE POSITIVE** — no valid candidates |
| 013 | 5.0.0-0.nightly-2026-05-08-191551 | nightly | 2 jobs | cluster-node-tuning-operator#1499 (95) |
| 014 | 5.0.0-0.ci-2026-05-14-181709 | ci | 1 job | **INFRA ONLY** — no candidates expected |

### Case 006: Nightly GatewayAPI + oc mirror failures

Payload rejected with 3 failed blocking jobs. Two high-confidence revert
candidates: cluster-ingress-operator#1354 (Sail Library migration broke
GatewayAPIController) and oc#2232 (in-memory manifest reading caused nil
pointer in `oc adm release mirror`).

### Case 007: CI CCO Progressing invariant violation

Payload rejected with 3 failed jobs. cloud-credential-operator#978 introduced
`Progressing=True` during pod identity webhook updates, violating the CVO
invariant that CCO stays `Progressing=False` while MCO is rolling. Failed
on both AWS and GCP upgrade jobs. Third failure (hypershift-e2e-aws) is
infrastructure (teardown timeout), not code regression.

### Case 008: CI Hypershift metrics forwarder

Payload rejected with 2 failed hypershift jobs. hypershift#7790 introduced
both the metrics forwarder feature and its test — HCCO silently skips
deployment creation when prerequisites are missing. Secondary candidate
hypershift#8138 reduced cleanup timeout.

### Case 009: Nightly CVO test binary klog corruption

Payload rejected with 3 failed blocking jobs. cluster-version-operator#1309
introduced a new CVO test binary that imports klog, which emits INFO lines
to stdout. This corrupts the JSON output stream expected by openshift-tests,
causing test discovery failures on both metal-ipi-ovn-ipv4 and ipv6. The
third failure (aggregated-hypershift-ovn-conformance) is infrastructure:
AWS lease exhaustion, not a code regression. The skill must correctly
distinguish infrastructure failures from code-caused failures.

### Case 010: CI CNO NetworkPolicy regression

Payload rejected with 2 failed jobs. cluster-network-operator#2959 added
NetworkPolicies that blocked egress from cloud-network-config-controller,
causing CrashLoopBackOff across all platforms (AWS, Azure, GCP). 0% pass
rate vs 100% historical. Textbook true positive — reverted by #2999.

### Case 011: Nightly CMO monitoring regression

Payload with 2 failed jobs. cluster-monitoring-operator#2814 introduced
monitoring test regressions. Flagged across 2 consecutive payloads with
score 95. Multi-payload persistence was always a true positive signal.
Reverted by #2901.

### Case 012: CI HyperShift builder image (FALSE POSITIVE)

Payload rejected with 1 failed AKS e2e job. Agent incorrectly flagged
hypershift#8194 (builder image update) at score 92, constructing a plausible
but incorrect causal chain to Azure Graph API auth failure. The failure was
an Azure-side issue that resolved without code changes. Tests FP detection
for cloud platform issues.

### Case 013: Nightly NTO testdata embedding

Payload with 2 failed jobs. cluster-node-tuning-operator#1499 embedded
testdata into the test binary, causing node tuning test failures. Non-obvious
build-system change — tests whether the agent can trace binary composition
to test execution failures. Reverted by #1511.

### Case 014: CI infrastructure-only rejection

Payload rejected due to Insights API Gateway HTTP 500 errors — pure
infrastructure, no code regression. The correct outcome is zero revert
candidates. Tests the agent's ability to classify and dismiss infrastructure
issues without producing false positive recommendations.

## Judges

Six judges evaluate skill output (defined in `eval.yaml`):

1. **output_files_exist** — all 3 required files produced (HTML, YAML, JSON)
2. **yaml_results_valid** — YAML has required schema (metadata, failing_jobs, candidates)
3. **json_data_valid** — autodl JSON is valid with required fields
4. **html_report_structure** — HTML has executive summary, table, verdict, CSS, details
5. **analysis_quality** — LLM judge scoring root cause depth and PR correlation (1-5)
6. **revert_scoring_accuracy** — LLM judge verifying correct revert candidates identified
   with accurate confidence scores compared to ground truth in annotations

## MLflow Integration

### Setup

```bash
pip install mlflow anthropic
mlflow server --host 127.0.0.1 --port 5000 \
  --backend-store-uri sqlite:///mlflow.db \
  --default-artifact-root ./mlruns &
```

### Viewing Results

After a run completes, results are logged automatically. Open http://127.0.0.1:5000
to view:
- **Metrics tab**: judge scores, cost, duration, cache hit rate
- **Quality tab**: per-trace judge feedback (populated via `mlflow.log_feedback()`)
- **Artifacts tab**: summary.yaml, per-case results table, input files
- **Traces**: execution traces with spans for each skill invocation

### Logging Manually

```
/eval-mlflow --action log-results --run-id <id>
```

## Expected Costs

A full 4-case eval run with claude-opus-4-6 costs approximately:

| Metric | Value |
|--------|-------|
| Total cost | ~$27 |
| Duration | ~46 minutes |
| Cost per case | ~$6-9 |
| Cache hit rate | ~92% |
| Total turns | ~385 |

Individual case costs vary: simple single-candidate cases (006, 007, 009) cost
$5-7, while multi-candidate cases (008) cost $8-9 due to more investigation.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `EVAL_ARCHIVES_DIR` | Root directory containing payload archive subdirectories |
| `PATH` | Must include `eval/shims/` before system gcloud/gh/curl |

All shims and fetch scripts use `EVAL_ARCHIVES_DIR` exclusively. The eval
harness sets both variables automatically via `eval.yaml`'s `execution.env`.

## Scripts

| Script | Purpose |
|--------|---------|
| `plugins/ci/skills/archive-payload-result/extract_session_data.py` | Extract API/curl/gh responses from Claude session tarballs |
| `eval/scripts/download-gcs-artifacts.sh` | Download GCS artifacts using rclone |
| `eval/scripts/compress-archives.sh` | Compress/decompress payload archive directories |
| `eval/shims/gcloud` | GCS storage command interceptor (with transparent extraction) |
| `eval/shims/curl` | HTTP request interceptor (gcsweb, release controller, Sippy, GitHub raw) |
| `eval/shims/gh` | GitHub CLI interceptor |

## File Layout

```
eval/
├── README.md                          # this file
├── cases/
│   ├── case-001-rejected-single-failure/
│   ├── ...
│   └── case-install-001-metal-ipi-ipv6-ckao/
├── scripts/
│   ├── download-gcs-artifacts.sh      # rclone-based GCS downloader
│   ├── compress-archives.sh           # archive compressor/decompressor
│   └── trim-archives.sh              # remove large unused files
└── shims/
    ├── gcloud                         # GCS storage command interceptor
    ├── curl                           # HTTP request interceptor
    └── gh                             # GitHub CLI interceptor
```

Archives live outside the repo (pointed to by `EVAL_ARCHIVES_DIR`).
