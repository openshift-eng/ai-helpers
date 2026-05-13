---
description: "Automated pre-commit code quality review with language-aware analysis and project-specific profiles"
argument-hint: "[--language <lang>] [--profile <name>] [--skip-build] [--skip-tests] [--html <path>]"
---

## Name
code-review:pre-commit-review

## Synopsis
```
/code-review:pre-commit-review [--language <lang>] [--profile <name>] [--skip-build] [--skip-tests] [--html <path>]
```

## Description
The `code-review:pre-commit-review` command performs a comprehensive code quality review of staged and unstaged changes before committing. It analyzes unit test coverage, idiomatic code patterns, DRY compliance, SOLID principles, and build verification.

The command supports two layers of customization:

1. **Language skills** (`--language <lang>`): Load language-specific guidance for idiomatic code review, test conventions, and build commands. Currently shipped: `go`. Planned: `python`, `rust`, `typescript`, `java`. If not specified, the language is auto-detected from changed file extensions.

2. **Profile skills** (`--profile <name>`): Load project-specific guidance that layers on top of language checks. Profiles add project conventions, shared utilities, build targets, and additional review criteria. Profiles reference the project's own agents and skills rather than embedding them.

The two layers compose: `--language go --profile hypershift` applies both Go idioms and HyperShift project conventions.

## Implementation

### Step 0 — Parse Arguments & Load Skills

- Parse `$ARGUMENTS` for the following flags:
  - `--language <lang>`: Language skill to load (e.g., `go`, `python`, `rust`, `typescript`, `java`)
  - `--profile <name>`: Project profile skill to load (e.g., `hypershift`)
  - `--skip-build`: Skip build verification step
  - `--skip-tests`: Skip unit test coverage review step
  - `--html <path>`: Generate an HTML report file at the specified path (e.g., `--html ./review.html`). The text report is still produced; the HTML report is generated as an additional output.
- If `--language` is not specified, auto-detect the primary language from the file extensions of changed files:
  - `.go` -> `go`
  - `.py` -> `python`
  - `.rs` -> `rust`
  - `.ts`, `.tsx` -> `typescript`
  - `.java` -> `java`
  - If mixed or unrecognized, proceed without a language skill
- Check for the language skill file at `skills/lang-<lang>/SKILL.md` relative to the plugin root directory. If the skill exists, read it and store its content for use by sub-agents. If it does not exist, inform the user and proceed with a generic review.
- If `--profile` is specified, check for the profile skill file at `skills/profile-<name>/SKILL.md` relative to the plugin root directory. If the skill exists, read it and store its content for use by sub-agents. If it does not exist, warn the user and proceed without profile-specific checks.

### Step 1 — Identify Changed Files

This step is language-agnostic.

- Run `git diff --name-only` to identify unstaged changes.
- Run `git diff --cached --name-only` to identify staged changes.
- Combine and deduplicate the file lists.
- Focus the review exclusively on changed files. Do not review unchanged files.
- Categorize files by type: source code, test files, configuration, documentation.
- If no source code files are changed (e.g., only docs or config), note this and adjust the review scope accordingly.
- Store the changed file list — it is passed to every sub-agent in the next step.

### Step 2 — Launch Parallel Review Sub-Agents

After identifying changed files, launch the following reviews concurrently. Launch ALL sub-agents in parallel (single message with multiple Task tool calls) for maximum speed. Each sub-agent should be given `subagent_type: "general-purpose"`. Do NOT set the `model` parameter — let sub-agents inherit the parent model, as these analysis tasks require a capable model. Pass each sub-agent the list of changed files, the loaded language skill content (if any), and the loaded profile skill content (if any) in its prompt.

**If `--html` is specified**, instruct each sub-agent to return its findings in a structured format. Each finding must include:
- **Finding text**: A clear description of the issue and recommended fix.
- **Severity**: One of `Blocking`, `Medium`, or `Low`.
- **File path and line number(s)**: The specific `file:line` reference (e.g., `path/to/file.go:42` or `path/to/file.go:42-50`). Use `N/A` if not applicable.
- **Agent name**: The name of the sub-agent producing the finding (e.g., `Idiomatic Go`, `Unit Test Coverage`, `DRY Compliance`, `SOLID Compliance`, or the profile SME agent name).
- **Agent verdict**: The sub-agent's overall verdict for its review area (e.g., `PASS`, `RECOMMENDATIONS`, `JUSTIFIED`, `FAIL`).

Each sub-agent should return its output as plain text with the structured findings clearly delimited so the parent agent can parse them. The plain text narrative is still included for the text report.

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

1. **Files Reviewed**: List all files reviewed, categorized by type.
2. **Unit Test Coverage**: Findings from the Unit Test Coverage sub-agent. Note if skipped.
3. **Idiomatic [Language] Code**: Findings from the Idiomatic Code sub-agent (use detected/specified language name, or "Code" if no language).
4. **DRY Compliance**: Findings from the DRY Principle sub-agent.
5. **SOLID Compliance**: Findings from the SOLID Principles sub-agent.
6. **Build Verification**: Build result (pass/fail/skipped).
7. **Profile-Specific Checks**: Findings from the Profile-Specific Review sub-agent (only if profile loaded).
8. **Overall Verdict**: PASS, FAIL, or PASS WITH RECOMMENDATIONS.
9. **Required Actions**: Issues that must be fixed before committing (blocking).
10. **Recommended Improvements**: Suggestions that are not blocking but would improve code quality.

#### Step 4a — Generate HTML Report (only if `--html <path>` is specified)

After generating the text report above, produce an HTML report file at the path specified by `--html`. The text report is always produced regardless of this flag.

##### Detect GitHub context

Run the following commands to gather context for links in the HTML report:

1. Run `gh pr view --json number,url,headRefName,baseRefName 2>/dev/null` to get the PR number, URL, head branch name, and base branch. Parse `owner/repo` from the URL (e.g., `https://github.com/openshift/hypershift/pull/123` yields `openshift/hypershift`).
2. Run `git rev-parse --short HEAD` to get the abbreviated commit SHA.
3. Run `git rev-parse HEAD` to get the full commit SHA (used for blob links if no PR exists).

If `gh pr view` fails (no PR exists yet), set `pr_number` to `null`. The report will omit PR file links and use blob links only.

##### Compute file anchors for PR links

For each file in the "Files Reviewed" list, compute the GitHub PR file tab anchor hash by running:

```
echo -n "<filepath>" | shasum -a 256 | cut -d' ' -f1
```

This produces the SHA-256 hash used in the `#diff-<hash>` fragment for PR file links. Store the hash for each file path.

##### Generate the HTML file

Use the **Write** tool to create the HTML file at the user-specified path. The HTML must follow this exact structure and styling:

**Document head:**
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pre-Commit Review — {PR_TITLE_OR_BRANCH}</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  code { font-size: 0.82rem; }
  .loc { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.82rem; }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 0.4rem; }
  .dot-pass { background: #198754; }
  .dot-warn { background: #ffc107; }
</style>
</head>
```

Use Bootstrap 5.3 light theme only (no dark theme). The container uses `max-width: 1200px`.

**Page structure (in this exact order):**

1. **Header**: `<h1>Pre-Commit Code Review</h1>` followed by a subtitle paragraph with PR/branch context and today's date. Below that, a verdict badge (`text-bg-success` for PASS, `text-bg-warning` for PASS WITH RECOMMENDATIONS, `text-bg-danger` for FAIL).

2. **Summary Grid**: A 4-column card grid (`row g-3 mb-4`) showing:
   - Files Reviewed (count)
   - Build (PASS/FAIL/SKIPPED, colored appropriately)
   - Blocking Issues (count, `text-success` if 0, `text-danger` otherwise)
   - Recommendations (count, `text-warning` if > 0, `text-success` if 0)

3. **Files Reviewed section**: `<h2 class="h5 border-bottom border-secondary pb-2 mb-2">Files Reviewed</h2>` with intro text. Inside a card, organize files into columns by category (Source, Tests, Docs, Config, etc.) using `<div class="row">` with `col-md-4` columns. Each file is a list item with a colored dot and a link:
   - If a PR exists: link to `https://github.com/{owner}/{repo}/pull/{pr_number}/files#diff-{sha256_hash}` with `target="_blank"`.
   - If no PR exists: link to `https://github.com/{owner}/{repo}/blob/{commit_sha}/{filepath}` with `target="_blank"`.
   - Dot colors: `#0d6efd` for source, `#198754` (use `dot-pass` class) for tests, `#bc8cff` for docs, `#6c757d` for config/other.

4. **Review Agents summary table**: `<h2 class="h5 ...">Review Agents</h2>` with intro text describing how many agents reviewed the change. Inside a card, a `<table class="table table-sm mb-0">` with columns: Agent, Verdict, Findings. Each agent name is an anchor link (`<a href="#agent-id">`) pointing to its detail section below. Verdict is a Bootstrap badge. Do NOT put badges on the detail section headers — only in this summary table.

5. **All Recommendations (Consolidated) table**: `<h2 class="h5 ..." id="all-recommendations">All Recommendations (Consolidated)</h2>` with intro text. A responsive table with columns: #, Severity, File:Line, Recommendation, Agent. Number findings sequentially starting at 1. Severity uses badges (`text-bg-danger` for Blocking, `text-bg-warning` for Medium, `text-bg-secondary` for Low). File:Line references are clickable links to blob view: `https://github.com/{owner}/{repo}/blob/{short_sha}/{filepath}#L{line}`. The Agent column contains anchor links back to the detail section. De-duplicate findings that appear in multiple agents (note both agents in the Agent column).

6. **Review Agent Output in Detail**: `<h2 class="h4 border-bottom border-dark pb-2 mt-5 mb-2">Review Agent Output in Detail</h2>` with intro text. Then one `<h3>` section per agent, each with:
   - An `id` attribute for anchor linking from the summary table (e.g., `id="build-verification"`, `id="unit-test-coverage"`, `id="idiomatic-go"`, `id="dry-compliance"`, `id="solid-compliance"`, and kebab-case IDs for profile SME agents).
   - `class="h5 border-bottom border-secondary pb-2 mb-2"` on the `<h3>`. No badges on these headers.
   - A `<p class="text-secondary small mb-3">` intro sentence describing what the agent checks.
   - A card with the agent's detailed output. Use tables, pass/fail dots, and narrative text as appropriate for each agent type.
   - Findings that appear in the consolidated recommendations table are rendered inside `<div class="alert alert-light border small mb-0">` boxes with the text `Finding (#N):` where N matches the consolidated table number.
   - Design notes and warnings use `<div class="alert alert-warning border small ...">` boxes.

7. **Footer**: `<footer class="text-center text-secondary small border-top border-secondary pt-3 mt-4">` with text like "Generated by Claude Code — N review agents + build command — PR link". If a PR exists, link to it. If not, show the branch name.

**Document closing:**
```html
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
```

##### Fallback when no PR context is available

If `gh pr view` failed (no PR exists):
- Use the branch name from `git rev-parse --abbrev-ref HEAD` for the subtitle.
- Use blob links (`https://github.com/{owner}/{repo}/blob/{commit_sha}/{filepath}`) instead of PR file links everywhere.
- Detect `owner/repo` from the git remote: `git remote get-url origin` and parse it from the URL (handles both HTTPS and SSH formats).
- The footer shows the branch name instead of a PR link.

After writing the file, inform the user of the path where the HTML report was saved.

### Critical Rules

- **Never approve without build verification** unless `--skip-build` is explicitly specified.
- **Every new exported/public function with non-trivial logic must have tests** unless `--skip-tests` is specified.
- **Be specific**: Always reference findings with `file:line` when possible.
- **Be actionable**: Every finding should include a clear recommendation for how to fix it.
- **Be proportional**: Review scope should match the scope of changes. A one-line fix does not need a full architectural review.
- **Respect existing patterns**: When the codebase has established conventions, follow them rather than imposing new ones.
- **Fix proactively when possible**: For simple issues (formatting, missing error checks), offer to fix them directly rather than just reporting.
- **Do not review unchanged code**: Focus exclusively on the diff. Do not flag pre-existing issues in unchanged code.

## Return Value
- **Format**: Structured text report with sections as described in Step 4.
- **Success**: Report generated with all applicable sections. Verdict is PASS or PASS WITH RECOMMENDATIONS.
- **Failure**: Report generated with failing sections identified. Verdict is FAIL with Required Actions listing blocking issues.

## Examples

1. **Basic usage with auto-detected language**:
   ```
   /code-review:pre-commit-review
   ```
   Auto-detects language from changed files and runs a full review.

2. **Go code review with HyperShift profile**:
   ```
   /code-review:pre-commit-review --language go --profile hypershift
   ```
   Applies Go idiomatic checks plus HyperShift project conventions.

3. **Skip build for a docs-only change**:
   ```
   /code-review:pre-commit-review --skip-build
   ```
   Runs all review steps except build verification.

4. **Python review without tests**:
   ```
   /code-review:pre-commit-review --language python --skip-tests
   ```
   Applies Python idiomatic checks but skips unit test coverage review.

5. **Full review with explicit language, no profile**:
   ```
   /code-review:pre-commit-review --language rust
   ```
   Applies Rust idiomatic checks with no project-specific profile.

6. **Go review with HyperShift profile and HTML report**:
   ```
   /code-review:pre-commit-review --language go --profile hypershift --html ./review.html
   ```
   Applies Go idiomatic checks plus HyperShift project conventions, and writes an HTML report to `./review.html`.

## Arguments:
- `--language <lang>`: Language skill to load. Currently shipped: `go`. Planned: `python`, `rust`, `typescript`, `java`. If omitted, auto-detected from changed file extensions.
- `--profile <name>`: Project profile skill to load. Loads `skills/profile-<name>/SKILL.md` for project-specific conventions. If omitted, no profile-specific checks are applied.
- `--skip-build`: Skip the build verification step (Step 3). Useful for documentation-only changes or when build infrastructure is not available locally.
- `--skip-tests`: Skip the unit test coverage review step (Unit Test Coverage sub-agent). Useful when changes do not affect testable code.
- `--html <path>`: Generate an HTML report file at the specified path in addition to the text report. The HTML report uses Bootstrap 5.3 styling with clickable file/line links to GitHub, a consolidated recommendations table, and detailed per-agent output sections. Requires `gh` CLI for PR context; falls back to blob links if no PR exists.
