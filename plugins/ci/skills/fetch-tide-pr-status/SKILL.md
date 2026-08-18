---
name: fetch-tide-pr-status
description: Fetch PR merge status — labels, required jobs, and Tide verdict
---

# Fetch Tide PR Status

CLI equivalent of the [Prow PR Status page](https://prow.ci.openshift.org/pr). Focuses on labels and required jobs — the most common merge blockers. Tide also checks other things (author, milestone) which may appear in the `tide` verdict but are not broken out here.

Only outputs open, non-draft PRs.

## Prerequisites

- `gh` CLI authenticated
- `python3` with `pyyaml` (`pip install pyyaml`)

## Usage

```bash
# All open PRs by an author
python3 "${SKILL_DIR}/fetch_tide_pr_status.py" openshift/cluster-monitoring-operator machine424

# Specific PRs
python3 "${SKILL_DIR}/fetch_tide_pr_status.py" openshift/cluster-monitoring-operator 3057,3044
```

## Output

JSON array, one object per PR:

```json
[
  {
    "number": 3044,
    "title": "OCPBUGS-105305: [release-4.21] wrap ...",
    "author": "machine424",
    "url": "https://github.com/openshift/cluster-monitoring-operator/pull/3044",
    "branch": "release-4.21",
    "state": "open",
    "mergeable": true,
    "tide": "Not mergeable. Needs jira/valid-bug label.",
    "tide_details": [
      "missing required label: jira/valid-bug",
      "has forbidden label: jira/invalid-bug",
      "job not passing: ci/prow/e2e-aws-ovn (running)"
    ],
    "labels": {
      "met": false,
      "required": {
        "have": ["lgtm", "approved"],
        "missing": ["jira/valid-bug"]
      },
      "forbidden": {
        "have": ["jira/invalid-bug"],
        "clear": ["needs-rebase", "do-not-merge/hold"]
      }
    },
    "required_jobs": [
      {"name": "ci/prow/unit", "state": "success"},
      {"name": "ci/prow/e2e-aws-ovn", "state": "running", "description": "Job triggered."}
    ]
  }
]
```

**`tide`** — Tide's own verdict. **`tide_details`** — everything preventing merge (empty = ready). **`required_jobs`** — non-optional jobs from openshift/release config. If the config could not be fetched, contains a single `{"error": "..."}` entry.

Job states: `success`, `failure` (+ `url`), `running` (+ `description`), `awaiting_pipeline`, `error` (+ `description`).

## Data Sources

- `https://prow.ci.openshift.org/tide.js` — required/forbidden labels (public)
- `gh api repos/{o}/{r}/pulls/{n}` — PR metadata
- `gh api repos/{o}/{r}/commits/{sha}/status` — job statuses + Tide context
- `raw.githubusercontent.com/openshift/release/master/ci-operator/jobs/...` — presubmit config (required vs optional)
