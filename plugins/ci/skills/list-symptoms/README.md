# List Symptoms

List, search, and inspect Sippy Symptoms and Labels via the public Sippy API.

## Overview

Sippy Symptoms are known-failure signatures for OpenShift CI. A symptom is a rule made of a file pattern (a glob over a CI job run's artifact files, e.g. `**/build-log.txt`) and a matcher (`string` = substring, `regex` = regular expression, `none` = file merely exists, `cel` = a compound CEL expression over other label names). When a symptom matches a job run's artifacts, Sippy applies one or more **Labels** — human-readable tags like `InfraFailure` — to that run. Labels appear in the Sippy UI and Spyglass and help everyone quickly recognize known failure modes without re-debugging them. You do not need any prior Sippy knowledge to use this skill.

This skill lets you:
- List or search all symptoms (by text, label, or matcher type)
- Fetch a single symptom or label by ID
- List all labels with their explanations

## Usage

```bash
# List all symptoms
python3 plugins/ci/skills/list-symptoms/list_symptoms.py --format summary

# Search symptoms by text (case-insensitive over id/summary/match_string)
python3 plugins/ci/skills/list-symptoms/list_symptoms.py --search "credentials" --format summary

# List all labels with explanations
python3 plugins/ci/skills/list-symptoms/list_symptoms.py --labels --format summary
```

**Options**:
- `--id <id>`: fetch a single symptom (or label with `--labels`) by ID
- `--search <text>`: case-insensitive text search
- `--label <label_id>`: only symptoms that apply this label
- `--matcher-type {string,regex,none,cel}`: filter by matcher type
- `--labels`: list labels instead of symptoms
- `--format`: `json` (default) or `summary`

## Authentication

None required — this skill uses the public, read-only Sippy API at `https://sippy.dptools.openshift.org`.

## See Also

- [SKILL.md](SKILL.md) - Complete implementation guide
- Related: `manage-symptoms` skill (create/update/delete symptoms)
- Related: `manage-labels` skill (create/update/delete labels)
- Related: `diagnose-job-run-symptoms` skill (explain which symptoms apply to a job run)
- Related: `/ci:list-symptoms` command (invokes this skill)
