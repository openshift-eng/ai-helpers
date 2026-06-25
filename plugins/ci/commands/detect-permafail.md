---
description: Detect permafail patterns in consecutive job failures
argument-hint: --job-urls="<urls>" --job-name="<name>" --pr="<owner/repo#123>"
---

## Name
ci:detect-permafail

## Synopsis
```text
/ci:detect-permafail --job-urls="[url1,url2,...]" --job-name="job-name" --pr="owner/repo#123"
```

## Description
Analyzes 2-10 consecutive failures of the same job to determine if they represent a systematic/permanent failure (permafail) versus a flaky failure. This is critical for CI/CD pipeline analysis to distinguish between:

- **Permafail**: A systematic failure affecting the same test(s) or infrastructure issue, detected by analyzing comparable runs (same failure type):
  - Separates test failures from infrastructure failures
  - Applies thresholds based on comparable run count (not total URLs)
  - 2-3 comparable runs: All must match (100% required)
  - 4-5 comparable runs: At least 4 must match (80% required)
  - 6-10 comparable runs: At least ceil(count×0.7) must match (70% required)
  - Example: 7 URLs where 5 are test failures and 4 of those 5 have same test → 4/5 = 80% → PERMAFAIL
- **Flaky**: Non-deterministic failures with varying root causes, or failures that don't meet the permafail thresholds

### How It Works

The command uses a deterministic Python classifier script for artifact-based failure classification, compares failure signatures across runs, and returns a JSON result with the permafail verdict, confidence score, failure type, and detailed signatures for each run.

## Implementation
- Load the "detect-permafail" skill
- Pass the job URLs, job name, and PR info to the skill
- The skill handles all analysis including:
  - Artifact fetching and classification via `plugins/ci/scripts/classify-job-failures.py`
  - Signature comparison and pattern detection
  - Threshold-based permafail determination

## Arguments
- `--job-urls`: JSON array of 2-10 consecutive Prow job URLs (required, newest first)
- `--job-name`: Name of the job being analyzed (required, e.g., "e2e-aws-ovn")
- `--pr`: PR identifier (required, format: "owner/repo#number")

## Prerequisites
- Access to Prow CI job artifacts via gcsweb URLs
- Access to Bash for running the classifier script
- Python with the `requests` package available
