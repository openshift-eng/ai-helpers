---
name: PR to Jira Candidate Matcher
description: Implementation guide for /jira:candidates-from-pr — analyze a GitHub PR and surface ranked open Jira candidates filtered by component and target release
---

# PR to Jira Candidate Matcher

Implementation for `/jira:candidates-from-pr`. Inverse direction of `extract-prs`: input is a GitHub PR, output is a ranked, triage-ready table of open Jira issues the PR may fix.

**IMPORTANT FOR AI**: This skill delegates all mechanical work to the scripts under `scripts/`. When invoked you MUST:

- Run the scripts as shown in the "Implementation" section. Do NOT replace them with inline `gh` / `jq` / `grep` calls.
- Make exactly the MCP calls listed in steps 2, 3 (conditional), and 4 — no more, no less.
- Treat `fetch_pr.py` as the single entry point for PR data; never call `gh pr view` or `gh pr diff` directly.
- Pipe data through the scripts using temp files in `.work/candidates-from-pr/{pr-number}/`.

The skill caller (this AI) is responsible only for the steps that need MCP tool calls or natural-language judgment (rationales).

## Scripts

All scripts read JSON on stdin or via `--` flags and write JSON/text to stdout. None of them call APIs except `fetch_pr.py` (which shells out to `gh`).

| Script | Purpose |
|---|---|
| `scripts/fetch_pr.py` | Resolve PR URL/number + run `gh pr view` and `gh pr diff`; emit normalized PR JSON. Caps the diff (default 4000 lines). |
| `scripts/extract_jira_keys.py` | Regex over PR title/body/branch/commits; emit deduplicated `[{key, sources[]}]` filtered by `--projects`. |
| `scripts/derive_filters.py` | Map repo + base ref to `components[]` + `target_release` (with sources and warnings). Sets `target_release_source=needs_lookup` when base ref is `main`/`master`. |
| `scripts/build_jql.py` | Assemble the final JQL from the filters JSON. Component and version clauses are conditional. |
| `scripts/extract_signals.py` | Local signal extraction — symbols, error strings, log messages, title keywords, file-path tags. No API calls. |
| `scripts/score_candidates.py` | Apply the scoring rubric + penalties to candidate Jiras and emit ranked JSON with `verdict` and `matched_signals`. |
| `scripts/render_report.py` | Render the final text table or canonical JSON payload. Accepts an optional `rationales.json` produced by the caller. |

## When to Use This Skill

- A PR is opened without a Jira reference and a triager needs to identify what it fixes.
- A PR mentions a Jira but you suspect it also addresses other open bugs in the same target release.
- Preparing a release-readiness report and want to map merged PRs to closeable Jiras.

**Read-only**: the skill never mutates Jira or GitHub state.

## Prerequisites

- `gh` CLI authenticated with read access to the target repo.
- Jira MCP server configured (`plugins/jira/README.md`).
- Python 3.10+ (no third-party deps; standard library only).
- `jq` CLI for JSON field extraction in shell snippets.

## Output Format

Schema version `1.0`, produced by `render_report.py --format json`:

```json
{
  "schema_version": "1.0",
  "metadata": { "generated_at": "...", "command": "candidates-from-pr", "jql": "..." },
  "pr": { "url": "...", "number": 0, "title": "...", "base_ref": "...", "head_ref": "...", "labels": [], "files_changed": 0 },
  "derived": { "components": [], "target_release": "...", "component_source": "...", "target_release_source": "..." },
  "explicit_references": [
    { "key": "...", "summary": "...", "status": "...", "target_release": "...", "assignee": "...", "url": "..." }
  ],
  "candidates": [
    {
      "key": "OCPBUGS-22222", "summary": "...", "url": "...",
      "status": "...", "issuetype": "...", "priority": "...",
      "assignee": { "display_name": "Jane Doe", "email": "..." },
      "components": [], "target_release": "...", "fix_versions": [],
      "score": 78, "verdict": "likely",
      "rationale": "Optional 1-2 sentence prose written by the caller.",
      "matched_signals": [{ "type": "error_string", "value": "..." }]
    }
  ]
}
```

The text format renders the same data as a markdown-style table; the **assignee column is required** and prints `unassigned` when null.

## Implementation

Work in `.work/candidates-from-pr/{pr}/` for intermediate JSON. All paths below are relative to that working directory unless stated.

### 1. Fetch PR

```bash
scripts/fetch_pr.py "$PR_ARG" ${REPO:+--repo "$REPO"} > pr.json
```

If `pr.diff_truncated` is `true`, mention it in the final report (the rest of the pipeline is unaffected — signals are extracted from the capped diff only). If `pr.diff_unavailable_reason` is set (e.g., `gh` returned HTTP 406 because the PR is too large), `extract_signals.py` automatically falls back to commit headlines/bodies; mention the fallback in the report so the user knows scoring is weaker.

### 2. Extract explicit Jira references

```bash
scripts/extract_jira_keys.py --projects "$PROJECTS" < pr.json > explicit_keys.json
```

For each `key` in the output, call:

```text
mcp__atlassian__jira_get_issue(
  issue_key=<KEY>,
  fields="summary,status,issuetype,components,fixVersions,customfield_10855,assignee"
)
```

On success, project the result to `{key, summary, status, target_release, assignee, url}` and append to `explicit.json`. On 404, drop the key with a warning.

### 3. Derive filters

```bash
scripts/derive_filters.py \
  ${COMPONENTS_OVERRIDE[@]/#/--component } \
  ${TARGET_RELEASE:+--target-release "$TARGET_RELEASE"} \
  < pr.json > filters.json
```

If `filters.json.target_release_source == "needs_lookup"`:

```text
mcp__atlassian__jira_get_project_versions(project_key=<KEY>)
```

Pick the **highest** unreleased numeric version where `released == false` (the current development release for `main`/`master`) and rewrite `filters.json` with it (set `target_release_source = "project_versions"`).

### 4. Build JQL and search

```bash
scripts/build_jql.py --project "$PROJECT" < filters.json > jql.txt
```

Run the search:

```text
mcp__atlassian__jira_search(
  jql=<contents of jql.txt>,
  fields="summary,status,issuetype,priority,assignee,components,fixVersions,customfield_10855,description,updated,labels",
  limit=50
)
```

Project each issue to the input shape expected by `score_candidates.py` (see its docstring) and write to `candidates_raw.json`. Drop any keys also present in `explicit.json` unless `--include-explicit` was passed.

### 5. Extract signals (local)

```bash
scripts/extract_signals.py < pr.json > signals.json
```

### 6. Score candidates (local)

```bash
COMPS=$(jq -r '.components | join(",")' filters.json)
COMP_FLAG=$([ -n "$COMPS" ] && echo --component-filter-used)
scripts/score_candidates.py \
  --signals signals.json \
  --candidates candidates_raw.json \
  --components-derived "$COMPS" $COMP_FLAG \
  --min-score "$MIN_SCORE" \
  --limit "$LIMIT" \
  > scored.json
```

### 7. Write rationales (caller, optional)

For each candidate in `scored.json`, write a 1–2 sentence rationale referencing the **top three** entries in `matched_signals`. Save to `rationales.json` as `{"OCPBUGS-1234": "..."}`. If you skip this step, `render_report.py` falls back to a comma-joined list of matched signal values.

### 8. Render

```bash
scripts/render_report.py \
  --pr pr.json --filters filters.json --jql "$(cat jql.txt)" \
  --explicit explicit.json --candidates scored.json \
  ${RATIONALES:+--rationales rationales.json} \
  --format "$FORMAT"
```

## Scoring Rubric (implemented in `score_candidates.py`)

| Signal | Weight |
|---|---|
| Error string from PR diff appears verbatim in Jira summary or description | +35 |
| Symbol from PR diff (function/struct) appears in Jira summary or description | +25 per unique match, capped at +40 |
| ≥ 2 PR title keywords overlap Jira summary/description | +15 |
| Component agreement (Jira components ∩ derived components ≠ ∅) | +10 (required for non-zero when component filter active) |
| Recency: Jira `updated` within last 90 days | +5 |
| File-path tag overlaps Jira summary/description | +5 each, capped at +10 |
| Penalty: Jira issuetype is Epic/Feature/Initiative | −15 |
| Penalty: derived component empty AND no symbol/error-string overlap | −20 |
| Drop: Jira status is Verified/Closed | drop |

Final score is clamped to [0, 100]. Verdict mapping: `≥75` likely, `≥50` possible, `≥min_score` unlikely, otherwise dropped.

## Error Handling

- **PR not found / private** — `fetch_pr.py` propagates the `gh` error and exits non-zero. Surface verbatim to the user and stop.
- **MCP unavailable** — direct the user to `plugins/jira/README.md` and stop.
- **No candidates after scoring** — print explicit references (if any), the JQL, and suggest `--component`, `--target-release`, or `--min-score 0`.
- **Diff truncated** — keep going; mention truncation in the report.
- **Project not OCPBUGS** — works as long as the project has either `Target Version` or `fixVersions`; the JQL combines both.

## Companion Skills

- `plugins/jira/skills/extract-prs/SKILL.md` — opposite direction (Jira → PRs).
- `plugins/teams/skills/list-components/SKILL.md` — component lookup helpers.
- `plugins/jira/reference/mcp-tools.md` — MCP field reference, including `customfield_10855` for Target Version.
