---
name: fetch-prow-job-runs
description: List Prow job runs from the Sippy API using its real filter syntax — find run IDs by job name, variant, result, or time window
---

# Fetch Prow Job Runs

Sippy Symptoms are known-failure signatures for OpenShift CI. A symptom is a rule made of a file pattern (a glob over a CI job run's artifact files, e.g. `**/build-log.txt`) and a matcher (`string` = substring, `regex` = regular expression, `none` = file merely exists, `cel` = a compound CEL expression over other label names). When a symptom matches a job run's artifacts, Sippy applies one or more **Labels** — human-readable tags like `InfraFailure` — to that run. Labels appear in the Sippy UI and Spyglass and help everyone quickly recognize known failure modes without re-debugging them. You do not need any prior Sippy knowledge to use this skill.

This skill finds Prow job **runs** (and their `prow_id` values) via the Sippy `/api/jobs/runs` endpoint. It exists because this API does **not** accept ad-hoc query parameters like `?job_name=` or `?period=` — those do not exist and will be silently ignored or rejected. Filtering is done through a JSON `filter` parameter with a fixed set of column fields and operators (listed below), and this skill's script builds that JSON with verified fields and operators so you never have to guess.

## When to Use This Skill

Use this skill when you need to:

- Find run IDs (`prow_id`) to feed into `reevaluate-job-runs` after creating or updating a symptom
- Check how widespread a failure is (e.g. all failed runs of a job family in the last day)
- List recent runs matching a platform/network/etc. variant
- Get the Prow URL of recent runs of a given job

## Prerequisites

1. **Network Access**: The Sippy API must be accessible at `https://sippy.dptools.openshift.org`
   - No authentication required
2. **Python 3**: Python 3.6 or later, standard library only

## Implementation Steps

Invoke the script with flags matching the question:

```bash
script_path="plugins/ci/skills/fetch-prow-job-runs/fetch_prow_job_runs.py"

# Metal-platform runs in the last 24 hours
python3 "$script_path" --release 5.0 --variant Platform:metal --since-hours 24 --format summary

# Failed runs of jobs whose name contains e2e-metal
python3 "$script_path" --release 5.0 --job-contains e2e-metal --result F --format summary

# Pipe run IDs into symptom reevaluation
python3 "$script_path" --release 5.0 --job-contains e2e-metal --result F --since-hours 48 --ids-only \
  | xargs python3 plugins/ci/skills/reevaluate-job-runs/reevaluate_job_runs.py --dry-run
```

Flags:
- `--release <release>` (required): OpenShift release, e.g. `5.0`
- `--job-contains <substr>` (repeatable): job name must contain each substring
- `--variant <Key:Value>` (repeatable): run must have each variant entry, e.g. `Platform:metal`
- `--result <code>`: overall result code (`S` success, `F` failure, `n` infra failure — lowercase n)
- `--since-hours <n>`: only runs newer than N hours ago
- `--filter-json <raw>`: escape hatch — raw JSON array of extra filter items merged with the generated ones
- `--limit <n>`: max rows (default 100)
- `--ids-only`: print just `prow_id` per line (pipeline-friendly)
- `--format {json,summary}`: output format (default `json`)

All filter items are combined with `AND`.

## API Details

### Endpoint

```text
GET https://sippy.dptools.openshift.org/api/jobs/runs?release={release}&filter={urlencoded_json}&limit={n}&sortField=timestamp&sort=desc
```

No authentication required.

### Filter JSON Shape

```json
{"items": [{"columnField": "name", "operatorValue": "contains", "value": "e2e-metal"}], "linkOperator": "and"}
```

### Verified Column Fields and Operators

Do NOT invent other query parameters or fields — only these are verified to work:

| columnField | operatorValue | value |
|---|---|---|
| `name` | `contains` | job-name substring |
| `variants` | `has entry` | `Key:Value`, e.g. `Platform:metal` |
| `timestamp` | `>` / `<` | epoch **milliseconds** as a string |
| `overall_result` | `equals` | `S` (success), `F` (failure), `n` (infra failure — lowercase) |

An unknown `columnField` yields HTTP 400 with a "column does not exist" message; the script surfaces that message verbatim.

### Response Row Fields

`{"rows": [...]}`; each row has `prow_id` (string), `job`, `url`, `variants[]`, `overall_result`, `failed`, `succeeded`, `infrastructure_failure`, `test_failures`, `timestamp` (epoch millis), `cluster`.

## Error Handling

### Case 1: Unknown Column (HTTP 400)

```text
Error: HTTP 400 from Sippy API: {"code":400,"message":"could not filter or sort data: error updating query for filter ... column does not exist"}
```

Use only the column fields in the table above. Exits 1.

### Case 2: Network Error

```text
Error: failed to connect to Sippy API: [Errno -2] Name or service not known
```

Exits 1. Check connectivity to `sippy.dptools.openshift.org`.

### Case 3: Empty Results

No matching runs prints `[]` (JSON), `Total: 0` (summary), or nothing (`--ids-only`) and exits 0 — not an error.

**Exit Codes:**
- `0`: Success (including empty results)
- `1`: Error (HTTP error, network error, invalid `--filter-json`)

## Examples

### Example 1: Metal Runs in the Last 24 Hours

```bash
python3 plugins/ci/skills/fetch-prow-job-runs/fetch_prow_job_runs.py \
  --release 5.0 --variant Platform:metal --since-hours 24 --limit 5 --format summary
```

**Expected Output (excerpt):**
```text
n  periodic-ci-openshift-release-main-nightly-5.0-e2e-metal-ovn-ha-cert-rotation-shutdown-5y-age-90d  2080684960133419008  1784908873000
Total: 5
```

### Example 2: Failed Runs of a Job Family

```bash
python3 plugins/ci/skills/fetch-prow-job-runs/fetch_prow_job_runs.py \
  --release 5.0 --job-contains e2e-metal --result F --format summary
```

### Example 3: Feed Run IDs to Reevaluation

```bash
python3 plugins/ci/skills/fetch-prow-job-runs/fetch_prow_job_runs.py \
  --release 5.0 --job-contains e2e-metal --since-hours 48 --ids-only \
  | xargs python3 plugins/ci/skills/reevaluate-job-runs/reevaluate_job_runs.py --dry-run
```

## Notes

- Results are sorted newest-first (`sortField=timestamp&sort=desc`)
- `timestamp` filter values must be epoch **milliseconds** (the script computes this for `--since-hours`)
- Repeatable flags AND together; there is no OR support in this script (use `--filter-json` if you need custom items)

## See Also

- Related Skill: `reevaluate-job-runs` (re-run symptom detection on the run IDs found here)
- Related Skill: `diagnose-job-run-symptoms` (explain which symptoms/labels apply to a run)
- Related Skill: `list-symptoms` (browse the symptom/label catalog)
- Related Skill: `fetch-regression-details` (another source of job run IDs, from regressions)
