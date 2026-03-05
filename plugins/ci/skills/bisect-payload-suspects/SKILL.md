---
name: Bisect Payload Suspects
description: Experimentally bisect medium-confidence payload suspects by opening draft revert PRs and triggering payload jobs
---

# Bisect Payload Suspects

This skill experimentally tests medium-confidence suspect PRs by opening draft revert PRs, triggering payload jobs, and evaluating results. It operates in two phases separated by a CI wait period.

## When to Use This Skill

Use this skill when the `payload-agent` orchestrator identifies suspect PRs with medium confidence (score 60-84) that cannot be conclusively attributed to a failure through static analysis alone. The bisect creates real experiments to determine causality.

**Inputs** (passed in-context by the caller):

- `payload_tag`: The full payload tag being analyzed
- `version`, `stream`, `architecture`: Parsed from the payload tag
- `release_controller_url`: URL to the payload on the release controller
- `suspects`: List of medium-confidence PRs to bisect, each with:
  - `pr_url`, `pr_number`, `component`, `title`, `confidence_score`
  - `failing_jobs`: List of `{job_name, prow_url, is_aggregated, underlying_job_name}`

## Prerequisites

1. **GitHub CLI (`gh`)**: Installed and authenticated
2. **JIRA MCP**: Configured for creating TRT issues (needed in Phase 2 for confirmed causes)
3. **Repository Access**: User must have push access to their fork of each target repository

## Implementation Steps

### Phase 1: Set Up Experiments

For each medium-confidence suspect, launch a **parallel subagent** (Task tool, `subagent_type: "general-purpose"`, do NOT set the `model` parameter):

#### 1.1: Check for Merge Conflicts

Before opening a revert PR, preemptively check whether the revert will have merge conflicts:

```bash
# Clone the repo (shallow for speed)
git clone -b <base_branch> --depth 50 "https://github.com/<org>/<repo>.git" /tmp/bisect-check-<pr_number>
cd /tmp/bisect-check-<pr_number>

# Attempt the revert without committing
git revert -m1 --no-commit <merge_sha>

# Check for conflicts
git status --porcelain
```

If conflicts exist:
- Record `status: skipped_conflict` in the tracking data
- Skip to the next suspect
- Do NOT attempt to resolve conflicts for bisect experiments

If no conflicts, abort the dry-run revert and proceed:

```bash
git revert --abort 2>/dev/null || git checkout -- .
```

#### 1.2: Open Draft Revert PR

Load the `revert-pr` skill and follow its workflow with `--draft`:

- PR URL: the suspect PR
- JIRA ticket: use a placeholder like `NO-JIRA` (real ticket is created in Phase 2 only for confirmed causes)
- `--draft`: Create as a draft PR
- `--context`: "Bisect experiment for {stream} {architecture} payload {payload_tag}. Testing whether reverting this PR resolves blocking job failures."
- Do NOT prompt the user for any input

Record the draft revert PR URL.

#### 1.3: Trigger Payload Jobs and Collect Run URLs

Use the `trigger-payload-job` skill (`plugins/ci/skills/trigger-payload-job/SKILL.md`) to trigger payload validation jobs on the draft revert PR and collect the resulting URLs. Pass:

- `pr_url`: The draft revert PR URL
- `jobs`: The `failing_jobs` list for this suspect (includes `job_name`, `is_aggregated`, `underlying_job_name` for each job)

#### 1.4: Record Experiment

Record the experiment data for the tracking YAML (see schema below).

**Throttling**: Never bisect more than 5 suspects. If there are more than 5, test only the top 5 by confidence score. Record the remainder as `deferred_suspects` in the tracking YAML.

### Write Tracking YAML

After all Phase 1 subagents complete, write `<payload-tag>-bisect.yaml` to the current working directory with all experiment data:

```yaml
metadata:
  payload_tag: "4.22.0-0.nightly-2026-02-25-152806"
  version: "4.22"
  stream: "nightly"
  architecture: "amd64"
  release_controller_url: "https://amd64.ocp.releases.ci.openshift.org/..."
  phase1_completed_at: "<ISO 8601 timestamp>"
  phase2_completed_at: ""

experiments:
  - suspect_pr:
      url: "https://github.com/openshift/cluster-network-operator/pull/2037"
      number: 2037
      component: "cluster-network-operator"
      title: "Fix OVN gateway mode selection"
      confidence_score: 60
    revert_pr:
      url: "https://github.com/user/cluster-network-operator/pull/15"
      number: 15
      state: "draft"
    triggered_jobs:
      - job_name: "periodic-ci-...-e2e-aws-ovn"
        type: "non-aggregated"
        command: "/payload-job periodic-ci-...-e2e-aws-ovn"
        payload_test_url: "https://pr-payload-tests.ci.openshift.org/runs/ci/9ed573a0-..."
        prow_url: "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/..."
    failing_jobs_attributed:
      - "periodic-ci-...-e2e-aws-ovn"
    status: "pending"
    result_summary: ""
    jira_key: ""
    jira_url: ""

deferred_suspects:
  - url: "https://github.com/openshift/mco/pull/5509"
    number: 5509
    component: "machine-config-operator"
    confidence_score: 42
```

---

### Phase 2: Collect Results and Act

Phase 2 is invoked after a CI wait period (typically 1-4 hours). The caller passes the path to the tracking YAML.

#### 2.1: Read Tracking YAML

Read the `<payload-tag>-bisect.yaml` file from the current working directory.

#### 2.2: Check Job Results

For each experiment with `status: pending`:

1. Fetch the `payload_test_url` from the tracking YAML
2. Check for "AllJobsFinished" status on the page
3. If not finished, mark as `status: inconclusive` with a note that jobs are still running
4. If finished, check individual prow job results (pass/fail) by fetching each `prow_url`

#### 2.3: Act on Results

For each completed experiment:

**PASS** (payload jobs pass with the revert applied — the revert fixed the problem):

The suspect PR is confirmed as the cause. Execute:

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
3. Record `status: passed`, `jira_key`, `jira_url` in tracking data

**FAIL** (payload jobs still fail with the revert applied — the PR is innocent):

1. Post a comment on the draft PR explaining the result:
   ```
   Bisect result: payload jobs still fail with this PR reverted. This PR is not the cause of the
   blocking job failures in {payload_tag}. Closing this draft.
   ```
2. Close the draft PR:
   ```bash
   gh pr close <draft_pr_url>
   ```
3. Record `status: failed` in tracking data

**ALL FAIL** (no single revert fixes the problem):

If all experiments fail, close all remaining draft PRs and note in the tracking data that the failures may be caused by an interaction between multiple PRs or by infrastructure issues.

#### 2.4: Update Tracking YAML

Update the tracking YAML with:
- `phase2_completed_at` timestamp
- Updated `status`, `result_summary`, `jira_key`, `jira_url` for each experiment

Return results to the caller for inclusion in the final report.

## Error Handling

- If a revert PR cannot be created (e.g., fork issues), skip that suspect and record the error.
- If payload job triggering fails, record the error but keep the draft PR open for manual testing.
- If the pr-payload-tests URL cannot be extracted, record the draft PR URL and note manual checking is required.
- Do not let one failed experiment block processing of others.

## See Also

- Related Skill: `revert-pr` - The git revert workflow (`plugins/ci/skills/revert-pr/SKILL.md`)
- Related Skill: `trigger-payload-job` - Triggers payload jobs and collects URLs (`plugins/ci/skills/trigger-payload-job/SKILL.md`)
- Related Skill: `stage-payload-reverts` - Stages high-confidence reverts (`plugins/ci/skills/stage-payload-reverts/SKILL.md`)
- Related Command: `/ci:payload-agent` - Autonomous orchestrator that uses this skill (`plugins/ci/commands/payload-agent.md`)
