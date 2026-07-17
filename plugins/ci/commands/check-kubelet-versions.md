---
description: Check kubelet versions across a list of /payload runs and analyze consistency and version/status correlation
argument-hint: <payload-runs.txt>
---

## Name

ci:check-kubelet-versions

## Synopsis

```
/ci:check-kubelet-versions <payload-runs.txt>
```

## Description

The `ci:check-kubelet-versions` command reports the kubelet (node) version and job result for every `/payload` run in a list of gcsweb artifact URLs, then analyzes the results. It uses the `kubelet-version-check` skill to gather the data and adds reasoning about version consistency and any correlation between kubelet version and pass/fail outcome.

Use this command to answer questions like:

- "Did every run use the kubelet version I expected?"
- "Which runs are on an unexpected version, or are missing node data?"
- "Do the failures cluster on a particular kubelet version?"

The input file is typically produced by the `payload-blocking-runs` skill or the `/ci:list-payload-blocking-runs` command.

## Implementation

**Important: Avoiding user permission prompts when running scripts**

Run the skill script directly with the Bash tool (e.g. `python3 get_kubestat.py payload-runs.txt`). Do not pipe its output through inline Python (`python3 -c "..."`); parse and analyze the table using your own reasoning.

### Step 1: Validate the input

Confirm the argument is a readable file whose non-empty lines are gcsweb artifact URLs of the form:

```text
https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/<job-name>/<build-id>/
```

If the file is missing or empty, tell the user how to generate one (e.g. `/ci:list-payload-blocking-runs`).

### Step 2: Locate and run the skill script

```bash
KUBELET_CHECK="${CLAUDE_PLUGIN_ROOT}/skills/kubelet-version-check/get_kubestat.py"
if [ ! -f "$KUBELET_CHECK" ]; then
  KUBELET_CHECK=$(find ~/.claude/plugins -type f -path "*/ci/skills/kubelet-version-check/get_kubestat.py" 2>/dev/null | sort | head -1)
fi
if [ -z "$KUBELET_CHECK" ] || [ ! -f "$KUBELET_CHECK" ]; then echo "ERROR: get_kubestat.py not found" >&2; exit 2; fi

python3 "$KUBELET_CHECK" <payload-runs.txt>
```

The script prints progress to stderr and a `JOB / BUILD_ID / STATUS / KUBELET_VERSION` table to stdout.

### Step 3: Analyze the table (AI reasoning)

1. **Determine the expected version**: If the user stated an expected kubelet version, use it. Otherwise infer it as the dominant (most common) `v1.3x` version across the runs, and say which one you chose and why.
2. **Flag deviations**: List every run whose version differs from the expected one, and every run with a non-version note (`unexpected: <value>`, `no nodes file`, `no e2e step`) or a `STATUS` of `unknown` — these indicate missing or malformed data worth investigating.
3. **Correlate version with status**: Cross-tabulate `KUBELET_VERSION` against `STATUS`. Do failures concentrate on a particular version? Is one version passing while another fails? State whether the data suggests a version-related problem or not.
4. **Summarize**: Give counts — how many runs, how many on the expected version, how many passed/failed, how many with missing data.

### Step 4: Present the results

Provide:

- A concise summary of version consistency (e.g. "18/20 runs on `v1.35.0`, 2 on `v1.34.9`").
- A clearly-labeled list of the anomalous runs (with their build IDs / URLs).
- Your assessment of any kubelet-version-to-outcome correlation, and suggested next steps (e.g. inspect a specific failing run, or re-trigger a run that is missing node data).

## Arguments

- `<payload-runs.txt>` (required): Path to a text file containing gcsweb artifact URLs, one per line.

## Examples

1. **Check a run list produced by the payload-blocking-runs skill**:
   ```
   /ci:check-kubelet-versions payload-runs.txt
   ```

2. **End-to-end from a PR** (run the two commands in sequence):
   ```
   /ci:list-payload-blocking-runs openshift/machine-config-operator#5509 --streams 4.20.0-0.nightly
   # save the emitted URLs to payload-runs.txt, then:
   /ci:check-kubelet-versions payload-runs.txt
   ```

## Skills Used

- `kubelet-version-check`: Reads the gcsweb URL list and reports each run's status (from `finished.json`) and kubelet version (from the nodes artifact) as a table.
