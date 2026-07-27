# Jira Solver Eval

Benchmark for the TRT agentic jira-solver pipeline. Tests whether Claude can
correctly solve JIRA issues by creating PRs, using real historical issues with
known-good solutions.

## Architecture

| Component | Location |
|-----------|----------|
| Case definitions | `evals/jira-solver/cases/` (this directory) |
| Base/expected code | `openshift-trt/sippy-eval` repo (git branches) |
| Eval workflow | `release/step-registry/openshift/agentic/trt/eval/` |
| Prow job config | `release/ci-operator/config/openshift/release/openshift-release-main__jira-solver-eval.yaml` |

## How it works

1. **eval-init** checks out the eval repo at a historical commit (the base branch)
2. **jira-solver** (the actual production step, reused) reads the JIRA snapshot and solves the issue
3. **eval-judge** compares Claude's solution against the known-good expected branch

The eval reuses the real jira-solver step — in a release repo presubmit, CI
operator picks up the PR's version of the script, so prompt changes are tested
automatically.

## Cases

Each case corresponds to a real JIRA issue that was solved by the agent and
merged. The eval repo has two branches per case:

- `eval/case-N-base` — repo state before the fix (PR target)
- `eval/case-N-expected` — repo state after the known-good fix

| Case | JIRA | Difficulty | Description |
|------|------|-----------|-------------|
| 001 | TRT-2698 | Medium | Add MCP server tests to make target |
| 002 | TRT-2753 | Easy | Fix trailing slash routing |
| 003 | TRT-2660 | Easy-Medium | Fix null explanations crash (Go+JS) |
| 004 | TRT-2678 | Medium | MCP server ready check |
| 005 | TRT-2795 | Easy | Fix variant filter comparison |

## Adding a new case

1. Find a merged PR that solved a JIRA issue on sippy
2. Get the base SHA: `git rev-parse <merge-commit>^1`
3. Get the expected SHA: the PR head commit (last commit on the PR branch)
4. Push branches to the eval repo:
   ```bash
   cd /path/to/sippy-eval
   git branch eval/case-N-base <base-sha>
   git branch eval/case-N-expected <expected-sha>
   git push origin eval/case-N-base eval/case-N-expected
   ```
5. Snapshot the JIRA issue:
   ```bash
   curl -sf "https://redhat.atlassian.net/rest/api/2/issue/TRT-XXXX?fields=summary,description,status,labels,comment,issuetype,priority" \
     > cases/case-N-<slug>/jira-issue.json
   ```
6. Create `input.yaml` and `annotations.yaml` following the existing cases

## Running the eval

Trigger via Gangway with case and model overrides:

```bash
# Run a specific case with a specific model
gangway trigger --job periodic-ci-openshift-release-master-jira-solver-eval \
  --env MULTISTAGE_PARAM_OVERRIDE_EVAL_CASE=case-002-trt-2753-trailing-slash \
  --env MULTISTAGE_PARAM_OVERRIDE_CLAUDE_MODEL=claude-sonnet-4-6
```

## Judging

The eval-judge step produces:

**Hardcoded checks (pass/fail):**
- `branch_created` — Claude created a feature branch
- `code_compiles` — `make build` succeeds
- `tests_pass` — `make test` succeeds
- `pr_created` — PR exists on the eval repo
- `pr_description_exists` — PR description file is non-empty

**Diff-based scoring (0.0-1.0):**
- `file_overlap` — Jaccard similarity of files changed
- `diff_size_ratio` — ratio of Claude's diff size to expected
- `function_overlap` — overlap of modified functions/methods

Results are written to `${ARTIFACT_DIR}/junit_jira-solver-eval.xml` and
`${ARTIFACT_DIR}/eval-summary.yaml`.
