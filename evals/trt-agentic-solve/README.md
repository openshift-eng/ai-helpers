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

Case directories are named `case-NNN` only, with no descriptive slug, so the
name does not reveal the fix to the agent under test. This index records what
each case tests.

Each case corresponds to a real JIRA issue that was solved by the agent and
merged. The eval repo has two branches per case:

- `eval/case-NNN-base` — repo state before the fix (PR target)
- `eval/case-NNN-expected` — repo state after the known-good fix

| Case | JIRA | Difficulty | Description |
|------|------|-----------|-------------|
| case-001 | TRT-2698 | Medium | Add MCP server tests to make target |
| case-002 | TRT-2753 | Easy | Fix trailing slash routing |
| case-003 | TRT-2660 | Easy-Medium | Fix null explanations crash (Go+JS) |
| case-004 | TRT-2678 | Medium | MCP server ready check |
| case-005 | TRT-2795 | Easy | Fix variant filter comparison |
| case-006 | TRT-2824 | Hard | Expand Sippy database seed coverage |

## Adding a new case

1. Find a merged PR that solved a JIRA issue on sippy
2. Get the base SHA: `git rev-parse <merge-commit>^1`
3. Get the expected SHA: the merge commit, so the branches represent the
   coherent repository state immediately before and after the fix
4. Push branches to the eval repo:
   ```bash
   cd /path/to/sippy-eval
   git branch eval/case-NNN-base <base-sha>
   git branch eval/case-NNN-expected <expected-sha>
   git push origin eval/case-NNN-base eval/case-NNN-expected
   ```
5. Pick the next free `case-NNN` number and snapshot the JIRA issue into it:
   ```bash
   mkdir -p cases/case-NNN
   curl -sf "https://redhat.atlassian.net/rest/api/2/issue/TRT-XXXX?fields=summary,description,status,labels,comment,issuetype,priority" \
     > cases/case-NNN/jira-issue.json
   ```
6. Create `input.yaml` and `annotations.yaml` following the existing cases
7. Register the case in the **Cases** table above

### case-006 fixture preparation

The `case-006` branches are created manually in `openshift-trt/sippy-eval`.
Use the exact pre/post-merge trees; pairing the merge parent with the older PR
head would include unrelated changes:

```bash
git branch eval/case-006-base da64344f0d33e0b775a2bb57630401abb22360bf
git branch eval/case-006-expected 706919e16426e173b3b144e941009796bdd5679d
git diff --stat eval/case-006-base..eval/case-006-expected
```

The diff must contain five files with 888 insertions and 12 deletions. The
expected branch has executable e2e checks for non-empty release tag, release
job run, release pull request, and periodic test output API responses. The
other requirements in the case description are behavioral expectations; this
case does not add separate held-out assertions for them.

## Running the eval

Trigger via Gangway with case and model overrides:

```bash
# Run a specific case with a specific model
gangway trigger --job periodic-ci-openshift-release-main-jira-solver-eval-jira-solver-eval \
  --env MULTISTAGE_PARAM_OVERRIDE_EVAL_CASE=case-002 \
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
- `file_overlap` — Jaccard similarity of files changed (default cases)
- `golden_files_covered` — golden-branch file coverage (`case-002` only; extra test files OK)
- `diff_size_ratio` — ratio of Claude's diff size to expected
- `function_overlap` — overlap of modified functions/methods

Results are written to `${ARTIFACT_DIR}/junit_jira-solver-eval.xml` and
`${ARTIFACT_DIR}/eval-summary.yaml`.
