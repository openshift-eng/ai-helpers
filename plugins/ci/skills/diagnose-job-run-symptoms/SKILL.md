---
name: diagnose-job-run-symptoms
description: Explain which Sippy Symptoms and failure Labels apply to a Prow CI job run, in plain language, given only the Prow URL
---

# Diagnose Job Run Symptoms

Sippy Symptoms are known-failure signatures for OpenShift CI. A symptom is a rule made of a file pattern (a glob over a CI job run's artifact files, e.g. `**/build-log.txt`) and a matcher (`string` = substring, `regex` = regular expression, `none` = file merely exists, `cel` = a compound CEL expression over other label names). When a symptom matches a job run's artifacts, Sippy applies one or more **Labels** — human-readable tags like `InfraFailure` — to that run. Labels appear in the Sippy UI and Spyglass and help everyone quickly recognize known failure modes without re-debugging them. You do not need any prior Sippy knowledge to use this skill.

This skill takes a Prow job run URL and explains which symptoms matched the run and what each applied label means — including the exact file and line of text that matched.

## When to Use This Skill

Use this skill when:

- A CI job failed and you want to know if it is a **known failure mode** before debugging it from scratch
- You are about to create a new symptom and want to check what already matched the run (see `manage-symptoms`)
- You want a plain-language explanation of the labels shown on a run in the Sippy UI or Spyglass

## Prerequisites

1. **Default mode** (already-applied labels): only network access to public GCS (`https://storage.googleapis.com`) and the public Sippy API (`https://sippy.dptools.openshift.org`) — **no authentication required**.

2. **Deep mode** (`--deep`, server-side dry-run rescan): a Bearer token from the DPCR cluster.
   - Must be logged into the DPCR cluster via `oc login`
   - Cluster API: `https://api.cr.j7t7.p1.openshiftapps.com:6443`
   - Use the `oc-auth` skill to obtain the token (see the token-acquisition snippet in `reevaluate-job-runs/SKILL.md`)

3. **Python 3**: Python 3.6 or later, standard library only.

## Implementation Steps

### Step 1: Default mode — explain already-applied labels

```bash
python3 plugins/ci/skills/diagnose-job-run-symptoms/diagnose_job_run.py \
  "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/<job>/<build_id>"
```

For each applied label the summary output shows: the label title and explanation, the symptom that applied it (summary, matcher type, file pattern, match string), and the actual matched file and matched text from the run's artifacts.

### Step 2: Deep mode — server-side rescan

Use when the run predates the current symptom set or shows no labels. This asks Sippy to re-scan the run with `dry_run: true` — it **writes nothing** and reports what would match now:

```bash
python3 plugins/ci/skills/diagnose-job-run-symptoms/diagnose_job_run.py \
  "<prow_url>" --deep --token "$TOKEN"
```

### Step 3: Nothing matched?

If no labels are found and the user has identified the failure cause, guide them to the `manage-symptoms` skill to create a new symptom (and `reevaluate-job-runs` to apply it retroactively to past runs).

**Arguments**:
- `prow_url`: Prow job run URL (`https://prow.ci.openshift.org/view/gs/...`, positional, required)

**Options**:
- `--deep`: Server-side dry-run rescan via the reevaluate API (requires `--token`)
- `--token <token>`: Bearer token from the oc-auth skill (only needed with `--deep`)
- `--format json|summary`: Output format (default: summary)

## API Details

**Default mode** uses the public GCS JSON API (no auth):

- List label artifacts: `GET https://storage.googleapis.com/storage/v1/b/{bucket}/o?prefix={path}/artifacts/job_labels/`
- Download each object: `GET https://storage.googleapis.com/storage/v1/b/{bucket}/o/{object}?alt=media`

**GCS `job_labels` artifact schema (verified live 2026-07):** each `*.json` object under `artifacts/job_labels/` contains one wrapped entry (a `label-summary.html` file is also present and skipped):

```json
{
  "symptom_label_v1": {
    "symptom": {"id": "...", "summary": "...", "matcher_type": "string",
                "file_pattern": "...", "match_string": "...", "label_ids": ["..."]},
    "label": {"id": "...", "label_title": "...", "explanation": "..."},
    "file_match": "artifacts/.../nodes.json",
    "text_match": "the exact line that matched"
  }
}
```

The script also cross-references `GET /api/jobs/labels` and `GET /api/jobs/symptoms` on the public Sippy API to enrich entries with current explanations (embedded copies are snapshots from labeling time).

**Deep mode** calls `POST https://sippy-auth.dptools.openshift.org/api/jobs/runs/reevaluate` with `{"prow_job_build_ids": ["<build_id>"], "dry_run": true}` — same request/response as the `reevaluate-job-runs` skill.

## Error Handling

- **Bad / non-Prow URL**: Must contain `/view/gs/` and end in a numeric build ID (exit 1 client-side).
- **GCS 404 or no `job_labels` artifacts**: The run may be too old (artifacts pruned) or was never scanned — suggest `--deep` to rescan server-side.
- **No labels found**: Not an error — the script prints guidance to create a new symptom via `manage-symptoms`.
- **401/403 in deep mode**: Token missing/expired — refresh via the `oc-auth` skill.
- **Sippy API unreachable**: exit 1 with a clear message.

**Exit Codes**:
- `0`: Diagnosis completed (including "no labels found")
- `1`: Validation, network, or API error

## See Also

- Related Skill: `list-symptoms` (browse/search the symptom and label catalogs)
- Related Skill: `manage-symptoms` (create a new symptom when nothing matched)
- Related Skill: `reevaluate-job-runs` (apply symptoms retroactively to past runs)
- Related Skill: `oc-auth` (token for deep mode)
- Related Skill: `prow-job-analyze-test-failure` (deeper manual failure analysis)
- Related Command: `/ci:diagnose-job-symptoms` (invokes this skill)
