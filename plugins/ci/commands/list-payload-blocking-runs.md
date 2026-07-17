---
description: List a PR's blocking /payload runs and analyze coverage against the release blocking jobs
argument-hint: "<org/repo#pr> [--since YYYY-MM-DD] [--streams stream1 stream2 ...]"
---

## Name

ci:list-payload-blocking-runs

## Synopsis

```
/ci:list-payload-blocking-runs <org/repo#pr> [--since YYYY-MM-DD] [--streams stream1 stream2 ...]
```

## Description

The `ci:list-payload-blocking-runs` command finds the `/payload` test runs that were triggered on a pull request and analyzes them against the release's **blocking jobs**. It uses the `payload-blocking-runs` skill to query the CI analytics BigQuery table and cross-reference the release controller's current blocking-job set, then reasons about which blocking jobs have been exercised and where coverage is missing.

Use this command to answer questions like:

- "Has this PR been tested against all the blocking jobs before we merge it?"
- "Which blocking jobs still need a passing /payload run?"
- "Give me the artifact URLs for this PR's blocking payload runs."

## Implementation

**Important: Avoiding user permission prompts when running scripts**

Run the skill script directly with the Bash tool (e.g. `python3 payload_blocking_runs.py ...`). Do not pipe its output through inline Python (`python3 -c "..."`); parse and analyze the output using your own reasoning.

### Step 1: Parse the argument

Split `<org/repo#pr>` into its parts:

- `org` = text before `/` (default to `openshift` if the user gave only `repo#pr`)
- `repo` = text between `/` and `#`
- `pr` = the integer after `#`

Collect the optional flags:

- `--since YYYY-MM-DD` → the skill's `--start`. If omitted, default to 14 days ago (`date -u -d '14 days ago' +%F`) and tell the user which start date you used.
- `--streams ...` → the skill's `--streams`. If omitted, determine the relevant release stream(s) for the PR (from its target branch / current development version) or ask the user. As a fallback, `--all-jobs` lists every payload run, but it disables coverage analysis, which requires `--streams` to define the target set of blocking jobs.

### Step 2: Locate and run the skill script

```bash
PAYLOAD_BLOCKING="${CLAUDE_PLUGIN_ROOT}/skills/payload-blocking-runs/payload_blocking_runs.py"
if [ ! -f "$PAYLOAD_BLOCKING" ]; then
  PAYLOAD_BLOCKING=$(find ~/.claude/plugins -type f -path "*/ci/skills/payload-blocking-runs/payload_blocking_runs.py" 2>/dev/null | sort | head -1)
fi
if [ -z "$PAYLOAD_BLOCKING" ] || [ ! -f "$PAYLOAD_BLOCKING" ]; then echo "ERROR: payload_blocking_runs.py not found" >&2; exit 2; fi

python3 "$PAYLOAD_BLOCKING" \
  --org <org> --repo <repo> --pr <pr> \
  --start <since> \
  --streams <stream> [<stream> ...] \
  --verbose --show-jobs
```

`--verbose` prints (to stderr) the extracted blocking-job suffixes and which BigQuery rows did/did not match; `--show-jobs` prints the unique matched job names. The gcsweb URL list is on stdout. Capture both streams so you can reason over them.

### Step 3: Analyze coverage (AI reasoning)

Using the script output, reason about:

1. **What ran**: How many blocking payload runs were found? Group the matched runs by blocking job (suffix) so you can see which blocking jobs were exercised and how many times each.
2. **Coverage gaps**: Compare the full set of blocking-job suffixes (from the `--verbose` output) against the suffixes that actually have matched runs. Any blocking job with **zero** matched runs is a coverage gap — call these out explicitly by name.
3. **Anomalies**: Note runs the script listed as not matching any blocking suffix (they may be informing jobs, retries, or renamed jobs), and any streams that failed to fetch.
4. **Next steps**: Suggest concrete actions, e.g.:
   - Re-run the missing blocking jobs via the `/payload` command on the PR.
   - Feed the emitted artifact URLs into `/ci:check-kubelet-versions` (or other per-run analysis) to inspect results.
   - Widen `--since` if the run list looks incomplete.

### Step 4: Present the results

Give the user:

- The list of gcsweb artifact URLs (or a saved file path if the list is large).
- A short coverage summary: `N of M` blocking jobs exercised, with the missing ones named.
- Your recommended next steps.

## Arguments

- `<org/repo#pr>` (required): The pull request, e.g. `openshift/machine-config-operator#5509`.
- `--since YYYY-MM-DD` (optional): Earliest run start date (UTC). Defaults to 14 days ago.
- `--streams stream1 stream2 ...` (optional): Release stream name(s) whose blocking jobs define the coverage target, e.g. `4.20.0-0.nightly 4.20.0-0.ci`.

## Examples

1. **Analyze blocking coverage for a PR (explicit streams)**:
   ```
   /ci:list-payload-blocking-runs openshift/machine-config-operator#5509 --since 2026-01-01 --streams 4.20.0-0.nightly 4.20.0-0.ci
   ```

2. **Use the default lookback window**:
   ```
   /ci:list-payload-blocking-runs openshift/origin#29000 --streams 4.20.0-0.nightly
   ```

## Skills Used

- `payload-blocking-runs`: Queries BigQuery for the PR's payload runs and filters them to the release controller's current blocking jobs, emitting gcsweb artifact URLs.
