# Phase 7: PR feedback

### Phase 7: PR Feedback (Actions)

**Mode check**: Before executing any action in this phase, check the execution mode:
- If `--dry-run` (or no flag specified): **Do NOT execute** `gh pr comment` or `gh pr edit`. Instead, determine which action *would* be taken, compose the comment body, include it in the output JSON under `action_taken.comment_body`, and prefix `action_taken.type` with `dry_run:`.
- If `--execute`: Execute the `gh pr comment` command to post the comment to the downstream PR.

**In both modes**: Always **display the comment body** to the user in the console output so they can review what was (or would be) posted.

Based on the analysis, determine **ONE** of these actions for the **downstream PR**.

#### Comment Structure Rules

All comments follow a consistent structure with **per-bug sections**. Each Jira key discovered gets its own section. The comment uses the following layout:

1. **Header** — action-specific title (e.g., `## Test Coverage Report`)
2. **Per-bug sections** — one `### {jira_key}` section for each Jira bug, containing:
   - Bug metadata (PR links, change type)
   - Test coverage breakdown with clear **New Tests** vs **Existing Tests** distinction
   - Jira Test Context table (test type requirements, coverage sources, manual verification notes)
   - CI results
3. **CI Summary** — overall CI check counts
4. **Footer** — automation attribution

**GitHub table formatting**: When composing markdown tables for `gh pr comment`, ensure proper rendering by:
- Using a blank line before and after every table
- Aligning the header separator row with consistent dashes (e.g., `| --- | --- | --- | --- |`)
- Keeping cell content concise — truncate error messages to ~80 characters and append `...` if longer
- Not nesting code blocks inside table cells — use inline backticks only
- Testing that pipe characters (`|`) in cell content are escaped as `\|`

#### Test Coverage Categories

When reporting test coverage, clearly distinguish between these categories:

- **New tests (added in this PR)**: Test files and functions that were **added or modified** in the PR diff. These are tests written specifically as part of the code fix. Identified by:
  - New `_test.go` files appearing in the PR's changed file list
  - New `func Test*` / `func Benchmark*` lines in the diff (lines starting with `+`)
  - Modifications to existing test files in the PR

- **Existing tests (already in the repo)**: Test files that were **NOT modified** in this PR but already exist in the same package or test the same component. These are pre-existing tests that exercise the modified code. Identified by:
  - `_test.go` files in the same package directory that are not in the PR's changed file list
  - Test functions in the repo that reference the changed function names (found via `gh search code`)
  - E2E tests in `openshift/origin` that cover the component

This distinction matters because:
- New tests demonstrate the PR author intentionally added coverage for the fix
- Existing tests indicate the change is exercised by pre-existing infrastructure, but no new regression-specific test was written

#### 7a. Tests found AND CI passing

Comment body template:

```markdown
## Test Coverage Report

### {jira_key}

**PR**: {downstream_pr_url}
**Upstream PR**: {upstream_pr_url} (state: {upstream_state})
**Change type**: {change_type}
**Code changes**: {list of changed packages}

#### New Tests (added in this PR)

The following test functions were **added as part of the code fix**:

| Test Function | Test File | Job | Result |
| --- | --- | --- | --- |
| `{test_function_1}` | `{test_file}` | `{job_name}` | PASSED |
| `{test_function_2}` | `{test_file}` | `{job_name}` | PASSED |

#### Existing Tests (already in repo)

The following pre-existing tests also exercise the modified code:

- `{existing_test_file}` in package `{package}` — covers `{function_name}`
- E2E: `{e2e_test_name}` — **PASSED** in `{job_name}` ([link]({prow_url}))

#### Jira Test Context

| Test Type | Required | Coverage | Source |
| --- | --- | --- | --- |
| {test_type} | {Yes/No} | {coverage_description} | {PR diff / Jira comment / N/A} |

{If has_manual_verification:}
**Manual testing performed** (not automated):
- {performed_by} {details}

#### Suggested Test Automation

| # | Test Idea | Source | Type | Suggested Location | What to Assert |
| --- | --- | --- | --- | --- | --- |
| 1 | {test_idea} | {Jira manual / Jira description / Code diff} | {unit/e2e/perf} | `{file_path}` | {assertion} |

### CI Summary

| Total | Passed | Failed | Pending |
| --- | --- | --- | --- |
| {total} | {passed} | {failed} | {pending} |

All relevant tests passed. Code change is validated.

---
_Automated verification by check-pr-tests skill_
```

**If `--execute`**:
```bash
gh pr comment "$downstream_pr_url" --body "$comment_body"
```

**Label**: Label adding is disabled for initial testing. When ready, uncomment:
```bash
# gh pr edit "$downstream_pr_url" --add-label "verified"
```

#### 7b. Tests found BUT CI failing

Comment body template:

```markdown
## Test Coverage Report

### {jira_key}

**PR**: {downstream_pr_url}
**Upstream PR**: {upstream_pr_url} (state: {upstream_state})
**Change type**: {change_type}
**Code changes**: {list of changed packages}

#### New Tests (added in this PR)

The following test functions were **added as part of the code fix**:

| Test Function | Test File | Job | Result |
| --- | --- | --- | --- |
| `{test_function_1}` | `{test_file}` | `{job_name}` | PASSED |

#### Failing Tests

The following tests related to this change are **failing**:

| Test | Test File | Job | Result | Error |
| --- | --- | --- | --- | --- |
| `{test_name}` | `{test_file}` | `{job_name}` | FAILED | `{error_snippet}` |

**Failed job links**:
- [`{job_name}`]({prow_url})

#### Existing Tests (already in repo)

{If existing tests were found, list them here. If none, omit this section.}

#### Jira Test Context

| Test Type | Required | Coverage | Source |
| --- | --- | --- | --- |
| {test_type} | {Yes/No} | {coverage_description} | {PR diff / Jira comment / N/A} |

{If has_manual_verification:}
**Manual testing performed** (not automated):
- {performed_by} {details}

#### Suggested Test Automation

| # | Test Idea | Source | Type | Suggested Location | What to Assert |
| --- | --- | --- | --- | --- | --- |
| 1 | {test_idea} | {Jira manual / Jira description / Code diff} | {unit/e2e/perf} | `{file_path}` | {assertion} |

### CI Summary

| Total | Passed | Failed | Pending |
| --- | --- | --- | --- |
| {total} | {passed} | {failed} | {pending} |

@{pr_author} — please investigate the test failures above.

---
_Automated verification by check-pr-tests skill_
```

**If `--execute`**:
```bash
gh pr comment "$downstream_pr_url" --body "$comment_body"
```

#### 7c. No tests found AND test is required

Comment body template:

```markdown
## Test Coverage Report

### {jira_key}

**PR**: {downstream_pr_url}
**Change type**: {bug_fix|new_feature|api_change}
**Code changes**: {list of changed packages}

#### New Tests (added in this PR)

None. No test files were added or modified in this PR.

#### Existing Tests (already in repo)

No existing tests found that exercise the changed functions.

#### Modified Code Without Test Coverage

| Changed File | Functions Modified |
| --- | --- |
| `{changed_file_1}` | `{func1}`, `{func2}` |
| `{changed_file_2}` | `{func3}` |

Given that this is a **{change_type}**, test coverage is recommended to prevent regressions.

**Suggested test locations**:
- Unit tests: `{package_dir}/{suggested_test_file}`
- E2E tests: consider adding a case under `[sig-{sig}]` in openshift-tests

#### Jira Test Context

| Test Type | Required | Coverage | Source |
| --- | --- | --- | --- |
| {test_type} | {Yes/No} | {coverage_description} | {PR diff / Jira comment / N/A} |

{If has_manual_verification:}
**Manual testing performed** (not automated):
- {performed_by} {details}

#### Suggested Test Automation

| # | Test Idea | Source | Type | Suggested Location | What to Assert |
| --- | --- | --- | --- | --- | --- |
| 1 | {test_idea} | {Jira manual / Jira description / Code diff} | {unit/e2e/perf} | `{file_path}` | {assertion} |

### CI Summary

| Total | Passed | Failed | Pending |
| --- | --- | --- | --- |
| {total} | {passed} | {failed} | {pending} |

@{pr_author} — please consider adding test coverage for this change.

---
_Automated verification by check-pr-tests skill_
```

**If `--execute`**:
```bash
gh pr comment "$downstream_pr_url" --body "$comment_body"
```

#### 7d. No new tests BUT existing tests cover the change

Comment body template:

```markdown
## Test Coverage Report

### {jira_key}

**PR**: {downstream_pr_url}
**Change type**: {dependency_bump|refactor|config}
**Code changes**: {list of changed packages}

#### New Tests (added in this PR)

None. No test files were added or modified in this PR.

#### Existing Tests (already in repo)

The change is covered by pre-existing test infrastructure:

| Test File / Name | Package | Covers |
| --- | --- | --- |
| `{existing_test_file}` | `{package}` | Functions in same package |
| `{e2e_test_name}` | e2e | Component-level coverage |

{If e2e results are available:}
- E2E test `{e2e_test_name}` — **PASSED** in `{job_name}` ([link]({prow_url}))

#### Jira Test Context

| Test Type | Required | Coverage | Source |
| --- | --- | --- | --- |
| {test_type} | {Yes/No} | {coverage_description} | {PR diff / Jira comment / N/A} |

{If has_manual_verification:}
**Manual testing performed** (not automated):
- {performed_by} {details}

#### Suggested Test Automation

| # | Test Idea | Source | Type | Suggested Location | What to Assert |
| --- | --- | --- | --- | --- | --- |
| 1 | {test_idea} | {Jira manual / Jira description / Code diff} | {unit/e2e/perf} | `{file_path}` | {assertion} |

### CI Summary

| Total | Passed | Failed | Pending |
| --- | --- | --- | --- |
| {total} | {passed} | {failed} | {pending} |

No new tests required — existing test infrastructure covers this change.

---
_Automated verification by check-pr-tests skill_
```

**If `--execute`**:
```bash
gh pr comment "$downstream_pr_url" --body "$comment_body"
```

**Label**: Label adding is disabled for initial testing. When ready, uncomment:
```bash
# gh pr edit "$downstream_pr_url" --add-label "verified"
```

