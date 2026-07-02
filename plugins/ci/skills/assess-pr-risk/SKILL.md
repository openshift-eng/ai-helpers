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
- **CI bot comments**: Look for `/payload-job` commands that reviewers have already triggered — this tells you what testing is already underway.

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
| 1–3%        | Moderate   | 5      | p25 to p75       |
| 3–5%        | Elevated   | 10     | p75 to p90       |
| 5–10%       | High       | 15     | p90 to p95       |
| >10%        | Critical   | 20     | Above p95        |

Include the revert rate and its risk level in the report output so the user can see the repo's historical stability at a glance.

## Step 3: Determine Risk Tier

| Score  | Tier     | Meaning                                                               |
| ------ | -------- | --------------------------------------------------------------------- |
| 0-20   | LOW      | Presubmit tests are sufficient. Expensive e2e testing can be skipped. |
| 21-45  | MEDIUM   | Run presubmits + targeted e2e for affected components.                |
| 46-70  | HIGH     | Run full e2e suite including upgrade and platform-specific jobs.      |
| 71-100 | CRITICAL | Full e2e + manual review gate. Flag for TRT review.                   |

## Step 4: Recommend Testing

Your job is to decide the complete set of `/test` commands to run for this PR. Imagine a future where no e2e jobs run by default — you must recommend every test that should run, and explicitly call out every test you would skip with a reason.

### Step 4a: Fetch the Repo's CI Job Configuration

The repo's presubmit jobs are defined in the `openshift/release` repo. Fetch the CI config for the PR's target branch:

```bash
# Determine the branch (e.g., "main", "release-4.19")
branch="<baseRefName from PR metadata>"

# Fetch the CI config YAML
gh api repos/openshift/release/contents/ci-operator/config/<org>/<repo>/<org>-<repo>-${branch}.yaml --jq '.content' | base64 -d > /tmp/ci-config.yaml

# Parse all presubmit test jobs with their optional/always_run status
python3 -c "
import sys, yaml
data = yaml.safe_load(open('/tmp/ci-config.yaml'))
tests = data.get('tests', [])
for t in tests:
    name = t.get('as', 'unknown')
    optional = t.get('optional', False)
    always = t.get('always_run', True)
    kind = 'optional' if optional else 'required'
    print(f'{name}  ({kind}, always_run={always})')
"
```

This gives you the complete list of jobs the team has configured, split into:

- **Required jobs** (`optional: false`): These run on every PR by default. The team considers these essential, but only because they did not have AI to make more intelligent decisions. Assume these are important, but you will need to decide if they should run or not.
- **Optional jobs** (`optional: true`): These do NOT run automatically but can be triggered with `/test <job-name>`. The team defined these for situational use — your job is to decide when they should be triggered.

If the CI config YAML cannot be fetched (e.g., the repo doesn't exist in `openshift/release`, or uses a non-standard path), note it and fall back to the jobs visible in the PR's `statusCheckRollup`.

### Step 4b: Fetch Job Durations from Sippy

Presubmit job names in Sippy follow the pattern `pull-ci-<org>-<repo>-<branch>-<test-name>`. For example, the `/test e2e-gcp-ovn` job for `openshift/origin` on the `main` branch is `pull-ci-openshift-origin-main-e2e-gcp-ovn` in Sippy.

Query Sippy for the repo's presubmit e2e jobs to get actual `current_average_duration_minutes`:

```bash
python3 plugins/ci/skills/fetch-jobs/fetch_jobs.py \
  --release Presubmits --repo <repo> --name e2e --format json
```

Match each CI config job to its Sippy entry by constructing the Sippy name: `pull-ci-<org>-<repo>-<branch>-<job-name>`. Use `current_average_duration_minutes` for cost estimation in Step 4f. If a job has no Sippy data, estimate: standard e2e ~60 min, upgrade ~120 min, serial ~90 min.

### Step 4c: Classify Each E2e Job

Split the jobs from the CI config into two groups based on their name:

**Non-e2e jobs** (unit tests, image builds, lint, verify, bindata-check, etc. — any job without `e2e` in its name): These are assumed to always run as required presubmits. Do not include them in your recommendations — they are a given. Do not output `/test` commands for these jobs.

**E2e jobs** (any job with `e2e` in its name): These are the expensive jobs that provision real clusters. These are the sole focus of your recommendation. For each e2e job, decide **run** or **skip** with a reason, based on:

1. **What the job tests** — infer from the job name (e.g., `e2e-aws-ovn`, `e2e-upgrade`, `e2e-gcp-console-olm`)
2. **Whether the PR's changes are relevant** — does the code change touch areas that this job exercises?
3. **The risk tier** — higher risk warrants broader test coverage

Only output `/test` commands for e2e jobs. Never output `/test` for non-e2e jobs.

### Step 4d: Hotspot Awareness

Beyond the repo's configured jobs, watch for these common revert patterns. If the repo's CI config does not already include a matching job, recommend the specific `/payload-job` command listed below. These job names use a release version placeholder — substitute the current development release (e.g., `4.22` → `5.0`).

**HyperShift / External topology**: HyperShift clusters run the control plane as pods in a separate management cluster — there are no control plane nodes in the hosted cluster. This is a frequent source of reverts when a change assumes a self-hosted control plane. Flag and recommend testing when the PR touches control plane components, operators, networking, ingress, node lifecycle, machine API, or any code that assumes control plane nodes exist or are accessible.
```
/payload-job periodic-ci-openshift-release-main-nightly-4.22-e2e-aws-ovn-hypershift
```

**Single Node OpenShift (SNO)**: SNO has all OpenShift APIs but only one node. Flag and recommend testing when the PR assumes multi-node/HA clusters — anti-affinity requiring multiple nodes, node drain/failover, cross-node scheduling, replica counts > 1 without topology awareness, or PDBs designed only for 3+ nodes.
```
/payload-job periodic-ci-openshift-release-master-ci-4.22-e2e-aws-upgrade-ovn-single-node
/payload-job periodic-ci-openshift-release-master-nightly-4.22-e2e-aws-ovn-single-node-serial
```

**MicroShift**: MicroShift is a minimal single-node OpenShift distribution with a very limited API surface — only Route and SecurityContextConstraints kube APIs are available. Flag and recommend testing when the PR adds new tests that use APIs or features unavailable on MicroShift (Project, Build, DeploymentConfig, ClusterOperator, ClusterVersion, OLM resources, Machine APIs, Console, Monitoring, ImageRegistry, Samples operator, etc.).
```
/payload-job periodic-ci-openshift-microshift-release-4.22-periodics-e2e-aws-ovn-ocp-conformance
/payload-job periodic-ci-openshift-microshift-release-4.22-periodics-e2e-aws-ovn-ocp-conformance-serial
```

**Upgrade paths**: Recommend upgrade jobs when the PR touches operator reconciliation, version-gated logic, migration functions, API types/CRD schemas, feature gates, or dependency bumps that change core algorithms (e.g., hashing, serialization). Look for jobs with `upgrade` in the repo's CI config first. If none exist, recommend:
```
/payload-job periodic-ci-openshift-release-master-ci-4.22-e2e-aws-upgrade-ovn-single-node
```

**IPv6 / Dual-stack / Disconnected**: Flag and recommend testing when the PR hardcodes IPv4 addresses, uses IPv4-only parsing, misses IPv6 bracket handling in URLs, or assumes external network connectivity (public registries, external APIs, DNS of public hostnames).
```
/payload-job periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-ovn-ipv6
/payload-job periodic-ci-openshift-release-master-nightly-4.22-e2e-metal-ipi-serial-ovn-ipv6
```

**Platform cost awareness**: When recommending platform-specific jobs, prefer lower-cost platforms:

1. **AWS** — lowest cost, highest capacity, default
2. **GCP** — moderate cost
3. **Azure** — moderate cost
4. **Metal** — moderate cost, use for bare-metal-specific paths
5. **vSphere** — high cost, constrained capacity. Do NOT recommend unless the PR directly modifies vsphere-specific code

### Step 4e: Recommendation by Risk Tier

**LOW (0-20)**:

- Recommend only the cheap/fast required jobs
- Skip all e2e jobs — explicitly state they can be skipped and why
- If docs-only or trivially safe, say so clearly

**MEDIUM (21-45)**:

- Run all required e2e jobs
- Selectively trigger optional jobs that match the affected component or platform
- If upgrade paths could be affected, trigger upgrade jobs if available

**HIGH (46-70)**:

- Run all required e2e jobs
- Trigger all optional jobs relevant to the change
- If no HyperShift/SNO/upgrade job exists in the repo's config but the change warrants it, note the gap and recommend `/payload-job` testing to cover it
- Note specific areas of the code that warrant careful review

**CRITICAL (71-100)**:

- Run all required e2e jobs
- Trigger all optional jobs
- Recommend `/payload-job` testing as essential for broader coverage beyond presubmit jobs
- Recommend blocking merge until test results are reviewed
- Flag for TRT (Technical Release Team) attention
- Recommend manual review of the diff by a domain expert

### Step 4f: Format the Recommendation

This skill does NOT trigger any tests. It recommends what should be run as `/test` commands the user can copy and paste.

For each e2e job (jobs with `e2e` in the name), output a decision:

**Jobs to run** — with a `/test` command and justification:

```
/test <job-name>  — <why this PR's changes warrant this job>
```

**Jobs to skip** — with a reason:

```
SKIP: <job-name>  — <why this job is not relevant to this PR>
```

If the hotspot analysis identified risks not covered by any configured job, add a **"Coverage Gaps"** section noting what additional testing would be ideal (e.g., "No HyperShift presubmit job is configured for this repo, but this change modifies control plane assumptions — consider `/payload-job` testing with a HyperShift job").

### Step 4g: Estimate Testing Cost and Savings

Write a JSON array of your e2e job decisions to `/tmp/pr-risk-jobs.json`, then run the cost estimator script. Each job needs `name`, `duration_minutes` (from Step 4b Sippy data), `decision` ("run" or "skip"), and `ci_status` ("required" or "optional" from the CI config).

```bash
cat > /tmp/pr-risk-jobs.json << 'JOBS_EOF'
[
  {"name": "<job-name>", "duration_minutes": <N>, "decision": "run|skip", "ci_status": "required|optional"},
  ...
]
JOBS_EOF

python3 plugins/ci/skills/prow-job-cost-estimator/estimate_cost.py \
  --input /tmp/pr-risk-jobs.json --format summary
```

For the state file, also get JSON output:

```bash
python3 plugins/ci/skills/prow-job-cost-estimator/estimate_cost.py \
  --input /tmp/pr-risk-jobs.json --format json > /tmp/pr-risk-costs.json
```

Use the output from this script directly in your report and state file. Do not recalculate costs yourself — use the exact numbers the script printed.

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
    "jobs_to_run": ["<job names with /test prefix>"],
    "jobs_to_skip": [{"name": "<job-name>", "reason": "<why>"}],
    "coverage_gaps": ["<areas not covered by configured jobs>"],
    "key_risks": ["<specific risks identified>"],
    "cost_estimate": {
      "recommended_cost_usd": <total cost of jobs to run>,
      "savings_from_skipped_required_usd": <cost of required e2e jobs skipped>,
      "added_cost_from_optional_usd": <cost of optional e2e jobs added>,
      "net_savings_usd": <savings minus added cost>
    },
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

**Jobs to run:**
```

/test <job-name> — <justification>
/test <job-name> — <justification>
...

```

**Jobs to skip:**
| Job | Reason for Skipping |
|-----|---------------------|
| `<job-name>` | <why this job is not relevant to this PR> |
| ... | ... |

**Coverage gaps:**
<areas of risk not covered by any configured job, with suggestions for /payload-job testing if applicable>

### Cost Estimate

| | Amount |
|---|--------|
| Recommended testing cost | $X.XX |
| Savings (skipped required e2e jobs) | -$X.XX |
| Added cost (optional e2e jobs triggered) | +$X.XX |
| **Net savings** | **$X.XX** |

### Historical Context
<repo revert rate and risk level>

---
State saved to `.work/pr-risk/<org>-<repo>-<number>.json`
```

## Constraints

- **You do not know what happened after this PR was merged.** Analyze presubmit results, payload job results, reviewer comments, and everything that occurred while the PR was open — that is all fair game. But you have no knowledge of whether the PR was later reverted or caused any post-merge issues. Do not search for reverts of this specific PR, do not mention revert PRs or Jira tickets related to this PR's post-merge outcome, and do not frame your analysis as a "retrospective" or "case study." Your report must read as a forward-looking risk assessment written at merge time. If you discover post-merge revert information incidentally, ignore it completely — do not reference it in your report. The repo-level revert rate in Section D is fine (that measures the repo's general stability), but never mention whether _this specific PR_ was reverted.
- **When in doubt, score higher.** A false-high is cheaper than a missed regression.
- **The scoring weights are v1.** They will be calibrated over time with real-world usage. If a score feels wrong based on your analysis, note the discrepancy and explain why.
- **Don't block on missing data.** If a skill call fails or data is unavailable, note it and proceed with what you have. Adjust confidence accordingly.
- **Be specific.** Don't say "this is risky" — say which files, which patterns, which historical signals led to the score.
- **Large PRs need selective analysis.** For PRs with >100 files, focus your code analysis on non-vendor, non-generated files. Use the diff stat to prioritize.

## Skills Available

| Skill | When to Use |
| ----- | ----------- |
| `ci:prow-job-cost-estimator` | Calculate cost estimates for e2e job decisions (Step 4g) |
