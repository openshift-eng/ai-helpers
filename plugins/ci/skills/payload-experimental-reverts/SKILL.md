---
name: Payload Experimental Reverts
description: Experimentally test medium-confidence payload candidates by opening draft revert PRs and triggering payload jobs
---

# Payload Experimental Reverts

This skill experimentally tests medium-confidence candidate PRs by opening draft revert PRs, triggering payload jobs, and evaluating results. It operates in two phases separated by a CI wait period. All state is tracked in the payload results YAML file via the `payload-results-yaml` skill — no separate tracking file is created.

## When to Use This Skill

Use this skill when the `/ci:payload-experiment` command identifies candidate PRs with medium confidence (score 60-84) that cannot be conclusively attributed to a failure through static analysis alone. The experiment creates real tests to determine causality.

**Inputs** (passed in-context by the caller):

- `results_yaml_path`: Path to the payload results YAML file (e.g., `./payload-results-{tag}.yaml`)
- `candidates`: List of medium-confidence PRs to test experimentally, each with:
  - `pr_url`, `pr_number`, `component`, `title`, `confidence_score`
  - `failing_jobs`: List of `{job_name, prow_url, is_aggregated, underlying_job_name}`

## Prerequisites

1. **GitHub CLI (`gh`)**: Installed and authenticated
2. **JIRA MCP**: Configured for creating TRT issues (needed in Phase 2 for confirmed causes)
3. **Repository Access**: User must have push access to their fork of each target repository

## Implementation Steps

### Phase 1: Set Up Experiments

For each medium-confidence candidate, launch a **parallel subagent** (do NOT set the `model` parameter):

#### 1.1: Check for Merge Conflicts

Before opening a revert PR, preemptively check whether the revert will have merge conflicts:

```bash
# Clone the repo (shallow for speed)
git clone -b <base_branch> --depth 50 "https://github.com/<org>/<repo>.git" /tmp/experiment-check-<pr_number>
cd /tmp/experiment-check-<pr_number>

# Attempt the revert without committing
git revert -m1 --no-commit <merge_sha>

# Check for conflicts
git status --porcelain
```

If conflicts exist:
- Append an action entry with `type: "experiment"`, `status: "skipped_conflict"` to this candidate's `actions` array
- Skip to the next candidate
- Do NOT attempt to resolve conflicts for experimental reverts

If no conflicts, abort the dry-run revert and proceed:

```bash
git revert --abort 2>/dev/null || git checkout -- .
```

#### 1.2: Open Draft Revert PR

Load the `revert-pr` skill and follow its workflow with `--draft`:

- PR URL: the candidate PR
- JIRA ticket: use a placeholder like `NO-JIRA` (real ticket is created in Phase 2 only for confirmed causes)
- `--draft`: Create as a draft PR
- `--context`: "Experimental revert for {stream} {architecture} payload {payload_tag}. Testing whether reverting this PR resolves blocking job failures."
- Do NOT prompt the user for any input

Record the draft revert PR URL.

#### 1.3: Trigger Payload Jobs and Collect Run URLs

Use the `trigger-payload-job` skill (`plugins/ci/skills/trigger-payload-job/SKILL.md`) to trigger payload validation jobs on the draft revert PR and collect the resulting URLs. Pass:

- `pr_url`: The draft revert PR URL
- `jobs`: The `failing_jobs` list for this candidate (includes `job_name`, `is_aggregated`, `underlying_job_name` for each job)

#### 1.4: Record Experiment

Use the `payload-results-yaml` skill to append an action entry to the candidate's `actions` array:

- `type`: `"experiment"`
- `status`: `"pending"`
- `revert_pr_url`, `revert_pr_state: "draft"`, `payload_jobs`, `result_summary: ""`, `jira_key: ""`, `jira_url: ""`

See the `payload-results-yaml` skill for the full schema.

**Throttling**: Never test more than 5 candidates. If there are more than 5, test only the top 5 by confidence score.

**Job triggering limits**: Across all experiments combined: trigger at most 5 non-aggregated jobs and at most 1 aggregated job. Prioritize jobs from higher-confidence candidates.

When a candidate is processed but **all** of its jobs were skipped due to these limits (i.e., none were actually triggered), do NOT leave it with `status: "pending"`. Instead set:
- `status`: `"deferred"`
- `payload_jobs`: one entry per skipped job with `command` set and `test_url`, `test_prow_url` all set to `"skipped_due_to_limits"`
- `result_summary`: `"All jobs skipped due to cross-experiment triggering limits"`

When a candidate has **some** jobs triggered and some skipped, mark the triggered jobs normally and add entries for skipped jobs with the `"skipped_due_to_limits"` marker so the record is complete. The action's `status` should be `"pending"` in this case (it has real jobs to check).

Candidates beyond the top 5 that were never processed at all should get an action entry with:
- `type`: `"experiment"`
- `status`: `"deferred"`
- `result_summary`: `"Deferred — exceeded maximum of 5 experimental candidates"`

### Update Payload Results YAML

After all Phase 1 subagents complete, use the `payload-results-yaml` skill to update the results file at `results_yaml_path` with the action entries for each candidate that was processed or deferred.

---

### Phase 2: Collect Results and Act

Phase 2 is invoked after a CI wait period (typically 1-4 hours). If the results YAML contains any action entry with `type: "experiment"` and `status: "pending"`, enter Phase 2. Phase 2 processes only pending experiments — candidates with other statuses are left unchanged.

#### 2.1: Read Payload Results YAML

Read the results YAML at `results_yaml_path` using the `payload-results-yaml` skill. Find all candidates that have an action entry with `type: "experiment"` and `status: "pending"`. Skip actions with `status: "deferred"` — these had no jobs triggered and cannot be evaluated.

#### 2.2: Check Job Results

For each pending experiment action:

1. Fetch the `test_url` from the action's `payload_jobs`
2. Check for "AllJobsFinished" status on the page
3. If not finished, leave the action's `status` as `"pending"` — do NOT change it. The caller can invoke Phase 2 again later to re-check.
4. If finished, check individual prow job results (pass/fail) by fetching each `test_prow_url`

#### 2.3: Act on Results

For each completed experiment:

**PASS** (payload jobs pass with the revert applied — the revert fixed the problem):

The candidate PR is confirmed as the cause. Execute:

1. **Create TRT JIRA bug**: Same format as `stage-payload-reverts` Substep 1
2. **Promote draft to real PR**:
   ```bash
   gh pr ready <draft_pr_url>
   ```
   Update the PR title to include the JIRA key and remove any "NO-JIRA" placeholder:
   ```bash
   gh pr edit <draft_pr_url> --title "<jira_key>: Revert #<pr_number> \"<pr_title>\""
   ```
   Update the PR body to include the JIRA reference and full Revertomatic template.
3. Update the action entry: `status: "passed"`, `revert_pr_state: "open"`, `jira_key`, `jira_url`

**FAIL** (payload jobs still fail with the revert applied — the PR is innocent):

1. Post a comment on the draft PR explaining the result:
   ```
   Experiment result: payload jobs still fail with this PR reverted. This PR is not the cause of the
   blocking job failures in {payload_tag}. Closing this draft.
   ```
2. Close the draft PR:
   ```bash
   gh pr close <draft_pr_url>
   ```
3. Update the action entry: `status: "failed"`, `revert_pr_state: "closed"`

**ALL FAIL** (no single revert fixes the problem):

If all experiments fail, close all remaining draft PRs and note in the result summaries that the failures may be caused by an interaction between multiple PRs or by infrastructure issues.

#### 2.4: Update Payload Results YAML

Use the `payload-results-yaml` skill to update the results file at `results_yaml_path`:
- For each completed candidate, update the relevant action entry's `status`, `result_summary`, `revert_pr_state`, `jira_key`, `jira_url`
- Candidates whose jobs are still running keep their action entry's `status: "pending"` (unchanged)

Return results to the caller. If any candidates remain `pending`, inform the caller that Phase 2 should be re-invoked later to collect remaining results.

## Error Handling

- If a revert PR cannot be created (e.g., fork issues), skip that candidate and record the error.
- If payload job triggering fails, record the error but keep the draft PR open for manual testing.
- If the pr-payload-tests URL cannot be extracted, record the draft PR URL and note manual checking is required.
- Do not let one failed experiment block processing of others.

## See Also

- Related Skill: `payload-results-yaml` - Schema and operations for the payload results YAML
- Related Skill: `revert-pr` - The git revert workflow (`plugins/ci/skills/revert-pr/SKILL.md`)
- Related Skill: `trigger-payload-job` - Triggers payload jobs and collects URLs (`plugins/ci/skills/trigger-payload-job/SKILL.md`)
- Related Skill: `stage-payload-reverts` - Stages high-confidence reverts (`plugins/ci/skills/stage-payload-reverts/SKILL.md`)
- Related Command: `/ci:payload-experiment` - Command for experimental reverts (`plugins/ci/commands/payload-experiment.md`)
