---
name: assess-pr-risk
description: Assess a PR's risk level and recommend which e2e and payload CI jobs to run. Takes a GitHub PR URL, scores risk across repo profile, complexity, code factors, and historical signals, then outputs a structured report with specific job recommendations.
---

The user provides a PR URL (e.g. `https://github.com/openshift/machine-config-operator/pull/1234`). Extract the org, repo, and PR number.

Create the directory with `mkdir -p .work/pr-risk` on first use.

## Step 1: Gather PR Data

```bash
# PR metadata
gh pr view <url> --json number,title,body,author,files,labels,state,additions,deletions,changedFiles,baseRefName,headRefName,statusCheckRollup

# Diff summary (always fetch this first for large PRs)
gh pr diff <url> --stat

# Full diff (for code analysis — skip if >2000 lines changed, use stat + selective reads instead)
gh pr diff <url>

# PR comments — look for reviewer feedback and CodeRabbit analysis
gh api repos/<org>/<repo>/pulls/<pr_number>/comments --paginate --jq '.[] | {user: .user.login, body: .body}' 2>/dev/null
gh api repos/<org>/<repo>/issues/<pr_number>/comments --paginate --jq '.[] | {user: .user.login, body: .body}' 2>/dev/null

# Recent reverts in the same repo (last 6 months)
# Calculate the date 6 months ago as YYYY-MM-DD and use GitHub's merged: search qualifier
gh pr list --repo <org>/<repo> --search "revert in:title merged:>$(date -v-6m +%Y-%m-%d)" --state merged --limit 50 --json number,title,mergedAt
```

For very large PRs (>100 files or >2000 LOC), use `gh pr diff --stat` to identify the highest-risk files, then fetch only those diffs selectively.

### Reading PR Comments

Pay special attention to comments from:

- **CodeRabbit** (`coderabbitai` user): CodeRabbit performs automated code review and may recommend additional testing. Look for suggestions about e2e tests, upgrade testing, or platform-specific concerns. Incorporate these into your testing recommendation.
- **Human reviewers**: Reviewers may flag risk areas, request specific tests, or express concerns about the change. Factor these into your assessment.
- **CI bot comments**: Look for `/payload-job` or `/payload-with-prs` commands that reviewers have already triggered — this tells you what testing is already underway.

## Step 2: Calculate Risk Score

Evaluate four categories and sum the points (0-100 total).

### A. Repository Risk Profile (0-25 points)

Classify the repository by examining its role in the OpenShift payload:

| Repository Type    | Points | How to Identify                                                                                           |
| ------------------ | ------ | --------------------------------------------------------------------------------------------------------- |
| Core platform      | 25     | Repos like `openshift/kubernetes`, `openshift/api`, `openshift/library-go` — foundational to the platform |
| Core operators     | 20     | Repos owning a ClusterOperator (e.g. `cluster-*-operator`, `machine-config-operator`)                     |
| Installers and CLI | 15     | `openshift/installer`, `openshift/oc`, `openshift/console`                                                |
| Payload components | 10     | Ships an image in the payload but not a core operator                                                     |
| Peripheral/tooling | 5      | Test frameworks, CI config, documentation repos                                                           |

Heuristics for classification:

- Check for `Dockerfile` or `Dockerfile.rhel` → likely ships in payload
- Check for `manifests/` or `install/` directories → likely an operator
- Repo name contains `operator` → likely a core operator
- Repo is `openshift/release`, `openshift/origin`, or test-focused → peripheral

If unsure, default to 10 points.

### B. PR Complexity (0-25 points)

| Signal                                         | Points        |
| ---------------------------------------------- | ------------- |
| 1-3 files changed                              | 5             |
| 4-10 files changed                             | 10            |
| 11-30 files changed                            | 15            |
| 30+ files changed                              | 20            |
| Multiple distinct packages/directories touched | +5            |
| Code changes with zero test file changes       | +5            |
| Docs-only changes                              | -20 (floor 0) |

**Test-only PRs are NOT automatically low risk.** Do not apply a blanket discount for test-only changes. Tests run across the entire CI system — a bad test can cause widespread job failures and trigger the revert-first policy just like production code. Score test-only PRs using the test risk factors in section C below.

### C. Code Risk Factors (0-30 points)

Examine the diff for these patterns. Points are additive but capped at 30:

| Factor                                   | Points | What to Look For                                                                                                      |
| ---------------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------- |
| API type or CRD schema changes           | +10    | Changes in `types.go`, `*_types.go`, CRD YAML, `zz_generated*`                                                        |
| Admission/validating webhook changes     | +8     | Webhook configurations, admission handlers                                                                            |
| RBAC / ClusterRole changes               | +7     | `role.yaml`, `clusterrole.yaml`, RBAC-related Go code                                                                 |
| Operator reconciliation logic            | +7     | Changes in `pkg/operator/`, reconcile functions, sync loops                                                           |
| Upgrade/migration path changes           | +8     | Version-gated logic, migration functions, `upgradeable` conditions                                                    |
| Feature gate additions/removals          | +6     | FeatureGate references, feature set changes                                                                           |
| Vendor/dependency bumps                  | +3     | Changes only in `vendor/`, `go.mod`, `go.sum`                                                                         |
| New e2e/integration tests added          | +7     | New test files or new `It()`/`Describe()` blocks — a flaky or broken new test will fail across every job that runs it |
| Test framework/infrastructure changes    | +6     | Changes to test helpers, fixtures, setup/teardown, test utilities — affects many tests downstream                     |
| Existing test modified to be more stable | -3     | Reducing flakiness, adding retries, loosening timing — low risk, helpful                                              |
| Tests removed or skipped                 | -2     | Removing dead tests or adding `Skip()` — low risk                                                                     |
| Generated code only                      | -5     | Only `zz_generated*`, `bindata.go` (with no manual changes)                                                           |
| Pure documentation/comments              | -10    | Only `.md`, comments, godoc                                                                                           |

**Why test changes can be high risk:** OpenShift has a massive CI system. A new test that is flaky or always-failing will run across hundreds of presubmit and periodic jobs, blocking merges and triggering the revert-first policy. The blast radius of a bad test is often larger than a bug in production code because it affects every contributor, not just one component.

### D. Historical Risk (0-20 points)

This category uses **revert rate** (reverts / total merged PRs) over the last 6 months, not raw revert counts. A repo with 3 reverts out of 500 PRs is healthy; 3 reverts out of 30 PRs is a red flag.

**Step D1: Gather revert and merge data (last 6 months)**

```bash
# Count reverts (last 6 months)
gh pr list --repo <org>/<repo> --search "revert in:title merged:>$(date -v-6m +%Y-%m-%d)" --state merged --limit 100 --json number | jq length

# Count total merged PRs (last 6 months)
gh pr list --repo <org>/<repo> --search "merged:>$(date -v-6m +%Y-%m-%d)" --state merged --limit 1000 --json number | jq length
```

**Step D2: Calculate revert rate**

```
revert_rate = reverts / total_merged_prs * 100
```

If the repo has fewer than 5 merged PRs in 6 months, skip revert rate scoring (insufficient data) and score 0 for this sub-category.

**Step D3: Score revert rate risk**

These thresholds are calibrated from percentile analysis of revert rates across OpenShift repos (repos with at least 1 revert and 5 merged PRs):

| Revert Rate | Risk Level | Points | Percentile Range |
| ----------- | ---------- | ------ | ---------------- |
| ≤1%         | Low        | 0      | Below p25        |
| 1–3%        | Moderate   | 3      | p25 to p75       |
| 3–5%        | Elevated   | 6      | p75 to p90       |
| 5–10%       | High       | 9      | p90 to p95       |
| >10%        | Critical   | 12     | Above p95        |

**Step D4: Score active regressions**

| Signal                          | Points                    | How to Check                                                        |
| ------------------------------- | ------------------------- | ------------------------------------------------------------------- |
| Active regressions in component | +4 per regression (max 8) | Use `ci:fetch-regression-details` for the component, or check Sippy |

Include the revert rate and its risk level in the report output so the user can see the repo's historical stability at a glance.

## Step 3: Determine Risk Tier

| Score  | Tier     | Meaning                                                               |
| ------ | -------- | --------------------------------------------------------------------- |
| 0-20   | LOW      | Presubmit tests are sufficient. Expensive e2e testing can be skipped. |
| 21-45  | MEDIUM   | Run presubmits + targeted e2e for affected components.                |
| 46-70  | HIGH     | Run full e2e suite including upgrade and platform-specific jobs.      |
| 71-100 | CRITICAL | Full e2e + manual review gate. Flag for TRT review.                   |

## Step 4: Recommend Testing

### Understanding the CI Job Landscape

OpenShift PRs have several categories of CI jobs:

- **Cheap/fast jobs** (unit tests, image builds, lint, verify): These always run automatically on every PR. They are not expensive and should never be skipped. Do not include these in your recommendations — they are a given.
- **e2e jobs** (any job with `e2e` in the name): These are the expensive, long-running e2e tests that provision real clusters. Currently presubmit e2e jobs are fixed per repo, but the future direction is for this agent to recommend which e2e jobs to run. Your recommendations should focus exclusively on e2e jobs. Always recommend the full set of jobs you feel is required, do not alter it based on what presubmits are already configured for the repo. (as in the future, we would like the agent to decide fully what to run)
- **Optional presubmit jobs**: Some repos have optional e2e jobs that can be triggered by PR comments (e.g., `/test <job-name>`).
- **Payload jobs**: Full release payload testing triggered via `/payload-job` or `/payload-with-prs` comments on the PR.

### Platform Cost Awareness

**vsphere e2e jobs are extremely expensive.** The infrastructure for vsphere testing is severely capacity-constrained. Do NOT recommend vsphere e2e jobs unless the PR directly modifies vsphere-specific code (e.g., vsphere cloud provider, vsphere CSI driver, vsphere-specific installer code, machine API vsphere provider), or contains new tests that might not work on vsphere. Generic operator or API changes do not warrant vsphere testing even at high risk tiers.

When recommending platform-specific e2e jobs, prefer lower-cost platforms first:

1. **AWS** — lowest cost, highest capacity, default recommendation
2. **GCP** — moderate cost, good capacity
3. **Azure** — moderate cost, good capacity
4. **Metal/bare-metal** — moderate cost, use when the change affects bare-metal-specific paths
5. **vSphere** — high cost, constrained capacity, only when directly relevant

### Recommendation by Risk Tier

**LOW (0-20)**:

- No e2e testing needed beyond what is already configured
- Explicitly state that expensive e2e testing can be skipped
- If test-only or docs-only, say so clearly
- If CodeRabbit or reviewers flagged specific concerns, note them but still recommend skipping e2e if the code analysis supports it

**MEDIUM (21-45)**:

- Recommend 1-2 targeted e2e jobs relevant to the changed component
- Use the repo name and changed packages to suggest specific job names (e.g., if networking code changed, suggest an `e2e-aws-ovn` job)
- Prefer AWS-based e2e jobs unless the change is platform-specific
- If an upgrade path is affected, recommend one upgrade e2e job
- Note any testing suggestions from CodeRabbit or reviewers and incorporate if relevant

**HIGH (46-70)**:

- Recommend a broader set of e2e jobs:
  - Standard: `e2e-aws-ovn`
  - Upgrade: `e2e-aws-ovn-upgrade` (if upgrade paths could be affected)
  - Platform-specific: only if the change directly affects that platform's code
  - Multi-arch: only if the change affects arch-specific code paths
- Suggest payload testing via `/payload-with-prs` to catch integration issues
- Note specific areas of the code that warrant careful review

**CRITICAL (71-100)**:

- Everything from HIGH
- Recommend payload testing as essential, not optional
- Recommend blocking merge until e2e and payload results are reviewed
- Flag for TRT (Technical Release Team) attention
- Identify specific risks that make this critical
- Recommend manual review of the diff by a domain expert

### E2E Jobs That Could Be Skipped

After determining which e2e jobs you would recommend, check which e2e presubmit jobs are actually configured to run on this PR (from the `statusCheckRollup` data or `gh pr checks`). Identify any e2e jobs that ran (or are running) but that you would NOT have recommended based on your risk analysis. List these in a **"E2E Jobs We Would Not Have Run"** section of the report with a brief reason for each (e.g., "vsphere e2e — no vsphere-specific code changes", "metal-ipi e2e — change is limited to AWS cloud provider").

This data is critical for calibrating future CI configuration. It helps us understand the cost savings available if e2e job selection were driven by this agent's recommendations rather than a fixed per-repo list.

### Important: Recommendations Only

This skill does NOT trigger any tests. It only recommends what should be run. Output recommendations as a list of specific job names or `/payload-job` commands that a human can copy and invoke. Include a brief justification for each recommended job explaining why this PR's changes warrant it.

## Step 5: Write State File

Write the assessment to `.work/pr-risk/<org>-<repo>-<pr_number>.json`:

```json
{
  "pr_url": "<url>",
  "org": "<org>",
  "repo": "<repo>",
  "pr_number": <number>,
  "assessment": {
    "timestamp": "<ISO 8601>",
    "risk_score": <0-100>,
    "risk_tier": "<low|medium|high|critical>",
    "risk_breakdown": {
      "repo_risk": <0-25>,
      "pr_complexity": <0-25>,
      "code_risk_factors": <0-30>,
      "historical_risk": <0-20>
    },
    "testing_recommendation": "<presubmits_only|targeted_e2e|full_e2e|full_e2e_plus_review>",
    "recommended_jobs": ["<job names>"],
    "key_risks": ["<specific risks identified>"],
    "notes": "<free text>"
  }
}
```

## Step 6: Produce Report

Output a structured markdown report:

```
## PR Risk Assessment: <org>/<repo>#<number>

**Title:** <PR title>
**Author:** <author>
**Risk Score:** <score>/100 (<TIER>)

### Risk Breakdown

| Category | Score | Details |
|----------|-------|---------|
| Repository profile | X/25 | <reason> |
| PR complexity | X/25 | <reason> |
| Code risk factors | X/30 | <reason> |
| Historical risk | X/20 | <reason> |

### Key Risk Factors
- <bullet list of specific risks found in the code>

### Testing Recommendation

**Recommended e2e jobs:**
| Job | Justification |
|-----|---------------|
| `<specific-job-name>` | <why this PR's changes warrant this job> |
| ... | ... |

**Payload testing:** <Required / Recommended / Not needed> — <reason>

<any additional testing notes, e.g. manual review areas>

### E2E Jobs We Would Not Have Run
<list of e2e jobs currently configured to run on this PR that are unnecessary based on the risk analysis, with reason for each>

### Historical Context
<repo revert rate and risk level, active regressions if any>

---
State saved to `.work/pr-risk/<org>-<repo>-<number>.json`
```

## Constraints

- **You do not know what happened after this PR was merged.** Analyze presubmit results, payload job results, reviewer comments, and everything that occurred while the PR was open — that is all fair game. But you have no knowledge of whether the PR was later reverted or caused any post-merge issues. Do not search for reverts of this specific PR, do not mention revert PRs or Jira tickets related to this PR's post-merge outcome, and do not frame your analysis as a "retrospective" or "case study." Your report must read as a forward-looking risk assessment written at merge time. If you discover post-merge revert information incidentally, ignore it completely — do not reference it in your report. The repo-level revert rate in Section D is fine (that measures the repo's general stability), but never mention whether *this specific PR* was reverted.
- **When in doubt, score higher.** A false-high is cheaper than a missed regression.
- **The scoring weights are v1.** They will be calibrated over time with real-world usage. If a score feels wrong based on your analysis, note the discrepancy and explain why.
- **Don't block on missing data.** If a skill call fails or data is unavailable, note it and proceed with what you have. Adjust confidence accordingly.
- **Be specific.** Don't say "this is risky" — say which files, which patterns, which historical signals led to the score.
- **Large PRs need selective analysis.** For PRs with >100 files, focus your code analysis on non-vendor, non-generated files. Use the diff stat to prioritize.

## Skills Available

Use these skills when needed (invoke via their skill names):

| Skill                                 | When to Use                                            |
| ------------------------------------- | ------------------------------------------------------ |
| `ci:fetch-regression-details`         | Check for active regressions in a component            |
