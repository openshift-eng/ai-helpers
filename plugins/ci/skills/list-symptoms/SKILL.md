---
name: list-symptoms
description: List, search, and inspect Sippy Symptoms and Labels — known CI failure signatures — via the public Sippy API
---

# List Symptoms

Sippy Symptoms are known-failure signatures for OpenShift CI. A symptom is a rule made of a file pattern (a glob over a CI job run's artifact files, e.g. `**/build-log.txt`) and a matcher (`string` = substring, `regex` = regular expression, `none` = file merely exists, `cel` = a compound CEL expression over other label names). When a symptom matches a job run's artifacts, Sippy applies one or more **Labels** — human-readable tags like `InfraFailure` — to that run. Labels appear in the Sippy UI and Spyglass and help everyone quickly recognize known failure modes without re-debugging them. You do not need any prior Sippy knowledge to use this skill.

This skill lists, searches, and fetches symptoms and labels using the public (read-only, no auth) Sippy API.

## When to Use This Skill

Use this skill when you need to:

- Browse the catalog of known CI failure signatures (symptoms)
- Check whether a failure pattern already has a symptom before creating a new one (avoid duplicates)
- Look up what a label like `InfraFailure` means (its title and explanation)
- Find which symptoms apply a given label
- Inspect a single symptom or label by its ID

## Prerequisites

1. **Network Access**: The Sippy API must be accessible at `https://sippy.dptools.openshift.org`
   - No authentication required
   - Check: `curl -s https://sippy.dptools.openshift.org/api/jobs/labels | head -c 200`

2. **Python 3**: Python 3.6 or later
   - Check: `python3 --version`
   - Uses only standard library (no external dependencies)

## Implementation Steps

Invoke the script with the flags that match the user's question:

```bash
script_path="plugins/ci/skills/list-symptoms/list_symptoms.py"

# List all symptoms (JSON by default)
python3 "$script_path"

# List all symptoms as a human-readable summary
python3 "$script_path" --format summary

# Search symptoms by text (matches id, summary, and match_string, case-insensitive)
python3 "$script_path" --search "credentials" --format summary

# Find all symptoms that apply a given label
python3 "$script_path" --label InfraFailure --format summary

# Fetch a single symptom by ID
python3 "$script_path" --id AWSCouldNotValidateAccessCredentials

# List all labels instead of symptoms
python3 "$script_path" --labels --format summary

# Fetch a single label by ID
python3 "$script_path" --labels --id InfraFailure
```

Flags:
- `--id <id>`: fetch a single symptom (or label with `--labels`) by ID
- `--search <text>`: case-insensitive text search over id/summary/match_string (for labels: id/label_title/explanation)
- `--label <label_id>`: only symptoms that apply this label ID
- `--matcher-type {string,regex,none,cel}`: only symptoms of this matcher type
- `--labels`: operate on labels instead of symptoms
- `--format {json,summary}`: output format (default `json`)

## API Details

### Endpoints

```text
GET https://sippy.dptools.openshift.org/api/jobs/symptoms
GET https://sippy.dptools.openshift.org/api/jobs/symptoms/{id}
GET https://sippy.dptools.openshift.org/api/jobs/labels
GET https://sippy.dptools.openshift.org/api/jobs/labels/{id}
```

### Example Symptom JSON

```json
{
  "id": "AWSCouldNotValidateAccessCredentials",
  "summary": "AWS could not validate access credentials",
  "matcher_type": "string",
  "file_pattern": "build-log.txt",
  "match_string": "api error AuthFailure: AWS was not able to validate the provided access credentials",
  "label_ids": ["InfraFailure"],
  "created_by": "kenzhang",
  "updated_by": "kenzhang",
  "updated_at": "2026-04-27T16:09:12.660547Z"
}
```

### Symptom Fields

| Field | Description |
|---|---|
| `id` | Immutable identifier (generated from the summary on create) |
| `summary` | Short, unique human-readable description (≤200 chars) |
| `matcher_type` | One of `string`, `regex`, `none` (file exists), `cel` (expression over label names) |
| `file_pattern` | Glob over the job run's artifact files, e.g. `**/build-log.txt` (not used for `cel`) |
| `match_string` | Substring, regular expression, or CEL expression depending on `matcher_type` |
| `label_ids` | Label IDs applied to a run when the symptom matches |
| `created_by`, `updated_by`, `updated_at` | Metadata about who created/last modified the symptom and when |

### Label Fields

| Field | Description |
|---|---|
| `id` | Immutable identifier (≤80 chars) |
| `label_title` | Unique human-readable title |
| `explanation` | Markdown explanation of what the label means |
| `hide_display_contexts` | UI contexts where the label is hidden (subset of `spyglass`, `metrics`, `jaq-options`) |

## Error Handling

### Case 1: Not Found (404)

```bash
python3 list_symptoms.py --id NoSuchSymptom
# Error: not found: https://sippy.dptools.openshift.org/api/jobs/symptoms/NoSuchSymptom (use list mode to see valid IDs)
```

Exits 1 and suggests listing symptoms/labels to find valid IDs.

### Case 2: Network Error

```bash
# Error: failed to connect to Sippy API: [Errno -2] Name or service not known
```

Exits 1. Check network connectivity to `sippy.dptools.openshift.org`.

### Case 3: Empty Results

Filters that match nothing print `[]` (JSON) or `No results.` (summary) and exit 0 — this is not an error.

**Exit Codes:**
- `0`: Success (including empty results)
- `1`: Error (404, network error, etc.)

## Examples

### Example 1: List All Symptoms

```bash
python3 plugins/ci/skills/list-symptoms/list_symptoms.py --format summary
```

**Expected Output (excerpt):**
```text
Symptom: AWSCouldNotValidateAccessCredentials
  Summary:      AWS could not validate access credentials
  Matcher:      string
  File pattern: build-log.txt
  Match string: api error AuthFailure: AWS was not able to validate the provided access credentials
  Labels:       InfraFailure
  Updated by:   kenzhang at 2026-04-27T16:09:12.660547Z

Total: 42
```

### Example 2: Search for an Existing Symptom Before Creating One

```bash
python3 plugins/ci/skills/list-symptoms/list_symptoms.py --search "credentials" --format summary
```

### Example 3: Symptoms That Apply a Label

```bash
python3 plugins/ci/skills/list-symptoms/list_symptoms.py --label InfraFailure --format summary
```

### Example 4: Fetch One Symptom by ID

```bash
python3 plugins/ci/skills/list-symptoms/list_symptoms.py --id AWSCouldNotValidateAccessCredentials
```

### Example 5: List All Labels

```bash
python3 plugins/ci/skills/list-symptoms/list_symptoms.py --labels --format summary
```

## Notes

- `--search`, `--label`, and `--matcher-type` filtering is performed **client-side**: the script fetches the full list and filters locally
- This skill is read-only; to create, update, or delete symptoms or labels use the `manage-symptoms` and `manage-labels` skills
- No authentication is required — the public Sippy instance serves all read endpoints

## See Also

- Related Skill: `manage-symptoms` (create/update/delete symptoms)
- Related Skill: `manage-labels` (create/update/delete labels)
- Related Skill: `diagnose-job-run-symptoms` (explain which symptoms/labels apply to a job run)
