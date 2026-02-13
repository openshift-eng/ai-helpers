---
description: "Automated PR code quality review with language-aware analysis and project-specific profiles"
argument-hint: "<pr-url-or-number> [--language <lang>] [--profile <name>] [--skip-build] [--skip-tests]"
---

## Name
code-review:pr

## Synopsis
```
/code-review:pr <pr-url-or-number> [--language <lang>] [--profile <name>] [--skip-build] [--skip-tests]
```

## Description
The `code-review:pr` command performs a comprehensive code quality review of the changes in a GitHub Pull Request. It analyzes unit test coverage, idiomatic code patterns, DRY compliance, SOLID principles, and build verification.

The command supports two layers of customization:

1. **Language skills** (`--language <lang>`): Load language-specific guidance for idiomatic code review, test conventions, and build commands. Currently shipped: `go`. Planned: `python`, `rust`, `typescript`, `java`. If not specified, the language is auto-detected from changed file extensions.

2. **Profile skills** (`--profile <name>`): Load project-specific guidance that layers on top of language checks. Profiles add project conventions, shared utilities, build targets, and additional review criteria. Profiles reference the project's own agents and skills rather than embedding them.

The two layers compose: `--language go --profile hypershift` applies both Go idioms and HyperShift project conventions.

## Implementation

### Step 0 — Parse Arguments & Load Skills

- Parse `$ARGUMENTS` for the following:
  - **PR identifier** (required, first positional argument): Either a full GitHub PR URL (e.g., `https://github.com/owner/repo/pull/123`) or a PR number (e.g., `123`). When only a number is provided, the current repository's remote is used.
  - `--language <lang>`: Language skill to load (e.g., `go`, `python`, `rust`, `typescript`, `java`)
  - `--profile <name>`: Project profile skill to load (e.g., `hypershift`)
  - `--skip-build`: Skip build verification step
  - `--skip-tests`: Skip unit test coverage review step
- If no PR identifier is provided, ask the user for one.
- If `--language` is not specified, auto-detect the primary language from the file extensions of changed files (determined in Step 1):
  - `.go` -> `go`
  - `.py` -> `python`
  - `.rs` -> `rust`
  - `.ts`, `.tsx` -> `typescript`
  - `.java` -> `java`
  - If mixed or unrecognized, proceed without a language skill
- Check for the language skill file at `skills/lang-<lang>/SKILL.md` relative to the plugin root directory. If the skill exists, read it and store its content for use by sub-agents. If it does not exist, inform the user and proceed with a generic review.
- If `--profile` is specified, check for the profile skill file at `skills/profile-<name>/SKILL.md` relative to the plugin root directory. If the skill exists, read it and store its content for use by sub-agents. If it does not exist, warn the user and proceed without profile-specific checks.

### Step 1 — Fetch PR Diff & Identify Changed Files

- Use `gh pr diff <pr-identifier>` to fetch the full PR diff.
- Use `gh pr view <pr-identifier> --json files --jq '.files[].path'` to get the list of changed files.
- Also fetch the PR metadata for context: `gh pr view <pr-identifier> --json title,body,baseRefName,headRefName,author`.
- Focus the review exclusively on changed files. Do not review unchanged files.
- Categorize files by type: source code, test files, configuration, documentation.
- If no source code files are changed (e.g., only docs or config), note this and adjust the review scope accordingly.
- Store the changed file list and the full diff — they are passed to every sub-agent in the next step.

**Important**: The review is performed against the PR diff, not the local working tree. Sub-agents should analyze the diff content to understand what changed. However, they may read local files for additional context (e.g., to understand how a changed function fits into the broader codebase), as long as the local checkout is on the PR branch or a compatible state.

### Step 2 — Launch Parallel Review Sub-Agents

After identifying changed files, launch the following reviews concurrently. **Use the Task tool to launch all of these in parallel in a single message with multiple tool calls.** Pass each sub-agent the list of changed files, the full PR diff, the loaded language skill content (if any), and the loaded profile skill content (if any) in its prompt.

#### Sub-agent: Unit Test Coverage
Skip if `--skip-tests` is specified.
- For each new or modified source file, check if a corresponding test file exists.
- For each new exported/public function with non-trivial logic, verify that tests exist.
- Evaluate test quality: Are tests testing meaningful behavior or just achieving coverage?
- Check for edge cases, error paths, and boundary conditions in tests.
- **If a language skill is loaded**, apply its test conventions (e.g., Go: table-driven tests, `t.Run()`, `t.Parallel()`).
- **If a profile is loaded**, apply its additional test conventions.
- Return findings as structured text.

#### Sub-agent: Idiomatic Code
- **If a language skill is loaded**, apply its idiomatic code guidance to the changed files.
- **If no language skill is loaded**, perform a general review: error handling, naming, clarity, complexity.
- **If a profile is loaded**, follow the profile's instructions to discover and apply any repo-local agents or skills it references. For example, the hypershift profile points to `.claude/agents/` — read the agents, pick the relevant ones based on changed files, and use their guidance.
- Return findings as structured text.

#### Sub-agent: DRY Principle
- Check for code duplication within and across changed files.
- Look for repeated patterns that could be extracted into shared functions or utilities.
- Identify copy-paste code that introduces maintenance risk.
- Flag magic numbers and string literals that should be constants.
- **If a profile is loaded**, check for proper use of project-specific shared utilities (e.g., hypershift's `support/` package).
- Return findings as structured text.

#### Sub-agent: SOLID Principles
- Apply SOLID principles proportionally to the scope of the changes:
  - **SRP**: Does each new function/type/module have one clear responsibility?
  - **OCP**: Are changes extending behavior without modifying stable abstractions?
  - **LSP**: Do new implementations honor the contracts of their interfaces?
  - **ISP**: Are interfaces focused and minimal?
  - **DIP**: Do high-level modules depend on abstractions rather than concrete implementations?
- **If a profile is loaded**, apply any project-specific structural patterns it defines.
- Return findings as structured text.

#### Sub-agents: Profile-Specific Reviews (only if profile is loaded)
  - Read the profile skill to discover which SME agents are required.
  - Launch **one sub-agent per SME agent** listed in the profile. For example,
    if the profile lists control-plane-sme, data-plane-sme, api-sme,
    cloud-provider-sme, and hcp-architect-sme, launch five separate sub-agents
    in parallel, each using the corresponding `subagent_type`.
  - Each sub-agent must receive:
    - The complete diff
    - PR title and description (if available)
    - The Jira ticket context (if available)
    - A prompt asking it to review the changes from its domain perspective.
  - All profile sub-agents run in parallel with each other and with the other
    Step 2 sub-agents.

### Step 3 — Build Verification

This step can run in parallel with the review sub-agents in Step 2 since it is independent. Skip if `--skip-build` is specified.

**Important**: Before running a build, ensure the local checkout matches the PR state. Use `gh pr checkout <pr-identifier>` to check out the PR branch locally if needed. Ask the user for confirmation before switching branches.

Run build verification in the following priority order:

1. **If a profile skill is loaded**, use the profile's build commands first. If the profile doesn't define build commands, fall back to step 2.
2. **Else if a language skill is loaded**, use the language skill's build commands.
3. **Otherwise**, auto-detect from project files. Check in the following priority order and use the first match found:
   1. `Makefile` -> `make build` or `make`
   2. `go.mod` -> `go build ./...`
   3. `Cargo.toml` -> `cargo build`
   4. `package.json` -> `npm run build` or `yarn build`
   5. `pyproject.toml` or `setup.py` -> `python -m py_compile` on changed files

- Run the build command and capture output.
- If the build fails, report the failure with full output and mark the review as failing.
- If the build succeeds, note this in the report.

### Step 4 — Collect Results & Generate Report

After all sub-agents and build verification complete, aggregate findings into a structured report:

1. **PR Info**: PR title, author, base branch, and link.
2. **Files Reviewed**: List all files reviewed, categorized by type.
3. **Unit Test Coverage**: Findings from the Unit Test Coverage sub-agent. Note if skipped.
4. **Idiomatic [Language] Code**: Findings from the Idiomatic Code sub-agent (use detected/specified language name, or "Code" if no language).
5. **DRY Compliance**: Findings from the DRY Principle sub-agent.
6. **SOLID Compliance**: Findings from the SOLID Principles sub-agent.
7. **Build Verification**: Build result (pass/fail/skipped).
8. **Profile-Specific Checks**: Findings from the Profile-Specific Review sub-agent (only if profile loaded).
9. **Overall Verdict**: PASS, FAIL, or PASS WITH RECOMMENDATIONS.
10. **Required Actions**: Issues that must be fixed before merging (blocking).
11. **Recommended Improvements**: Suggestions that are not blocking but would improve code quality.

### Critical Rules

- **Never approve without build verification** unless `--skip-build` is explicitly specified.
- **Every new exported/public function with non-trivial logic must have tests** unless `--skip-tests` is specified.
- **Be specific**: Always reference findings with `file:line` when possible.
- **Be actionable**: Every finding should include a clear recommendation for how to fix it.
- **Be proportional**: Review scope should match the scope of changes. A one-line fix does not need a full architectural review.
- **Respect existing patterns**: When the codebase has established conventions, follow them rather than imposing new ones.
- **Fix proactively when possible**: For simple issues (formatting, missing error checks), offer to fix them directly rather than just reporting.
- **Do not review unchanged code**: Focus exclusively on the PR diff. Do not flag pre-existing issues in unchanged code.

## Return Value
- **Format**: Structured text report with sections as described in Step 4.
- **Success**: Report generated with all applicable sections. Verdict is PASS or PASS WITH RECOMMENDATIONS.
- **Failure**: Report generated with failing sections identified. Verdict is FAIL with Required Actions listing blocking issues.

## Examples

1. **Review a PR by number (in current repo)**:
   ```
   /code-review:pr 456
   ```
   Fetches PR #456 from the current repo, auto-detects language, and runs a full review.

2. **Review a PR by URL**:
   ```
   /code-review:pr https://github.com/openshift/hypershift/pull/789
   ```
   Fetches the PR from the specified repo and runs a full review.

3. **Review with Go language and HyperShift profile**:
   ```
   /code-review:pr 456 --language go --profile hypershift
   ```
   Applies Go idiomatic checks plus HyperShift project conventions to PR #456.

4. **Skip build for a docs-only PR**:
   ```
   /code-review:pr 456 --skip-build
   ```
   Runs all review steps except build verification.

5. **Python review without tests**:
   ```
   /code-review:pr 456 --language python --skip-tests
   ```
   Applies Python idiomatic checks but skips unit test coverage review.

6. **Full review with explicit language, no profile**:
   ```
   /code-review:pr 456 --language rust
   ```
   Applies Rust idiomatic checks with no project-specific profile.

## Arguments:
- `$1` (required): PR identifier — either a full GitHub PR URL (e.g., `https://github.com/owner/repo/pull/123`) or a PR number (e.g., `123`). When a number is provided, the current repository's remote is used.
- `--language <lang>`: Language skill to load. Currently shipped: `go`. Planned: `python`, `rust`, `typescript`, `java`. If omitted, auto-detected from changed file extensions.
- `--profile <name>`: Project profile skill to load. Loads `skills/profile-<name>/SKILL.md` for project-specific conventions. If omitted, no profile-specific checks are applied.
- `--skip-build`: Skip the build verification step (Step 3). Useful for documentation-only changes or when build infrastructure is not available locally.
- `--skip-tests`: Skip the unit test coverage review step (Unit Test Coverage sub-agent). Useful when changes do not affect testable code.
