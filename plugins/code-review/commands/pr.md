---
description: "Automated PR code quality review with language-aware analysis and project-specific profiles"
argument-hint: "<pr-url-or-number> [--language <lang>] [--profile <name>] [--skip-build] [--skip-tests] [--serial]"
example: "/code-review:pr https://github.com/openshift/hypershift/pull/8262 --language golang --profile hypershift"
---

## Name
code-review:pr

## Synopsis
```
/code-review:pr <pr-url-or-number> [--language <lang>] [--profile <name>] [--skip-build] [--skip-tests] [--serial]
```

## Description
The `code-review:pr` command performs a comprehensive code quality review of the changes in a GitHub Pull Request. It analyzes unit test coverage, idiomatic code patterns, DRY compliance, SOLID principles, and build verification.

The command supports two layers of customization:

1. **Language skills** (`--language <lang>`): Load language-specific guidance for idiomatic code review, test conventions, and build commands. Currently shipped: `go`. Planned: `python`, `rust`, `typescript`, `java`. If not specified, the language is auto-detected from changed file extensions.

2. **Profile skills** (`--profile <name>`): Load project-specific guidance that layers on top of language checks. Profiles add project conventions, shared utilities, build targets, and additional review criteria. Profiles reference the project's own agents and skills rather than embedding them.

The two layers compose: `--language go --profile hypershift` applies both Go idioms and HyperShift project conventions.

## Implementation

### Step 0 — Parse Arguments & Load Skills

- Parse the arguments provided by the user (available as `$ARGUMENTS`, `$INPUT`, or directly in the user's message) for the following:
  - **PR identifier** (required, first positional argument): Either a full GitHub PR URL (e.g., `https://github.com/owner/repo/pull/123`) or a PR number (e.g., `123`). When only a number is provided, the current repository's remote is used.
  - `--language <lang>`: Language skill to load (e.g., `go`, `python`, `rust`, `typescript`, `java`)
  - `--profile <name>`: Project profile skill to load (e.g., `hypershift`)
  - `--skip-build`: Skip build verification step
  - `--skip-tests`: Skip unit test coverage review step
  - `--serial`: Force serial inline execution mode regardless of available tools. Useful for testing or when running on models with small context windows.
- If no PR identifier is provided, ask the user for one.
- If `--language` is specified, load the language skill now (before Step 1). Search by directory name pattern (not file content):
  ```bash
  find ~/.agents ~/.pi/agent ~/.claude -type d \( -name "lang-<lang>" -o -name "<lang>-code-review" \) 2>/dev/null
  ```
  Replace `<lang>` with the actual language value (e.g., `go`, `python`). If a directory is found, read its `SKILL.md`. If multiple matches, prefer the one under a `code-review` path.
  If no directory is found, print: `⚠ Language skill for '<lang>' not found. Proceeding with generic review.` and continue without language-specific guidance.
- If `--language` is NOT specified, **defer** language detection to after Step 1 — the auto-detection needs the changed file list. After Step 1 completes, auto-detect the primary language from the file extensions of changed files:
  - `.go` -> `go`
  - `.py` -> `python`
  - `.rs` -> `rust`
  - `.ts`, `.tsx` -> `typescript`
  - `.java` -> `java`
  - If mixed or unrecognized, proceed without a language skill
  Then search for the language skill using the same `find` command above.
- If `--profile` is specified, search for the profile skill the same way:
  ```bash
  find ~/.agents ~/.pi/agent ~/.claude -type d \( -name "profile-<name>" -o -name "<name>-code-review" \) 2>/dev/null
  ```
  Replace `<name>` with the actual profile value (e.g., `hypershift`). If found, read its `SKILL.md`.
  If no directory is found, print: `⚠ Profile skill for '<name>' not found. Proceeding without profile-specific checks.` and continue.

### Step 1 — Fetch PR Diff & Identify Changed Files

- Fetch the PR metadata: `gh pr view <pr-identifier> --json title,body,baseRefName,headRefName,author`.
- Fetch the list of changed files: `gh pr view <pr-identifier> --json files --jq '.files[].path'`.
- Fetch the full PR diff: `gh pr diff <pr-identifier>`.
- **Always** write the outputs to disk (serial mode needs them on disk, and the auto-fallback to serial in Step 2 also reads from disk):
  ```bash
  mkdir -p /tmp/code-review-<pr-number>
  gh pr view <pr-identifier> --json files --jq '.files[].path' > /tmp/code-review-<pr-number>/files.txt
  gh pr diff <pr-identifier> > /tmp/code-review-<pr-number>/diff.patch
  ```
- Focus the review exclusively on changed files. Do not review unchanged files.
- Categorize files by type: source code, test files, configuration/generated, documentation.
- If no source code files are changed (e.g., only docs or config), note this and adjust the review scope accordingly.
- Store the changed file list and the full diff — they are passed to every review dimension in the next step.

**Diff filtering (serial and subagent modes)**: Large PRs often include generated artifacts (CRDs, `zz_generated` files, vendored code) that inflate the diff without adding review value. In serial and subagent modes, where context or prompt size is constrained, split the diff by category after categorizing files:

1. Write categorized file lists: `source-files.txt`, `test-files.txt`, `generated-files.txt`, `docs-files.txt`
2. Extract source-only diff using `awk` (POSIX, no dependencies):
   ```bash
   awk '
     BEGIN { while((getline f < "source-files.txt")>0) files[f]=1 }
     /^diff --git/ { found=0; path=$NF; sub(/^b\//, "", path); if(path in files) found=1 }
     found
   ' diff.patch > diff-source.patch
   ```
3. Repeat for `test-files.txt` → `diff-tests.patch` if needed
4. Pass `diff-source.patch` (+ `diff-tests.patch` for the Unit Test dimension) to each dimension instead of the full diff

In Agent mode (Claude Code), the full diff can be passed directly since sub-agents have their own context windows.

**Important**: The review is performed against the PR diff, not the local working tree. Each review dimension should analyze the diff content to understand what changed. However, it may read local files for additional context (e.g., to understand how a changed function fits into the broader codebase), as long as the local checkout is on the PR branch or a compatible state.

### Step 2 — Run Review Dimensions

After identifying changed files, run the following review dimensions. Each dimension produces findings as structured text. Pass each dimension the list of changed files, the PR diff (filtered `diff-source.patch` in serial/subagent modes, full diff in Agent mode), the loaded language skill content (if any), and the loaded profile skill content (if any).

#### Execution mode — detect and adapt

If `--serial` is specified, skip detection and use mode 3 (serial inline) directly.

Otherwise, detect which execution mode is available, then run all dimensions using that mode. Check in this order and use the **first** that matches:

1. **Parallel sub-agents (Agent tool)** — If the `Agent` tool is available (Claude Code, Claude Desktop), launch ALL dimensions in parallel in a single message with multiple Agent tool calls. Use `subagent_type: "general-purpose"`. Do NOT set the `model` parameter — let sub-agents inherit the parent model.

2. **Parallel sub-agents (subagent tool)** — If the `Agent` tool is NOT available but the `subagent` tool IS available (Pi with pi-subagents extension), launch all dimensions in parallel using `runs.all()`. Each worker starts with zero context, so embed ALL required data in each worker's prompt: the filtered diff (`diff-source.patch`, or `diff-tests.patch` for the unit-test dimension), changed file list, language skill content, profile skill content, and the dimension-specific instructions.
   ```javascript
   subagent({
     agents: [
       { type: "worker", prompt: "Review this PR diff for unit test coverage.\n\n## Changed files\n<file-list>\n\n## Diff\n<diff-tests-patch>\n\n## Language guidance\n<lang-skill-content>\n\n## Instructions\n<dimension-instructions>" },
       { type: "worker", prompt: "Review this PR diff for idiomatic code.\n\n## Changed files\n<file-list>\n\n## Diff\n<diff-source-patch>\n\n..." },
       { type: "worker", prompt: "Review this PR diff for DRY compliance.\n\n## Changed files\n..." },
       { type: "worker", prompt: "Review this PR diff for SOLID principles.\n\n## Changed files\n..." },
       // ...profile dimensions if applicable
     ]
   })
   ```
   Collect all results from the returned array.

3. **Serial inline (no sub-agents)** — If neither `Agent` nor `subagent` tools are available, OR if `--serial` was specified. You MUST follow these exact steps in order:

   **3.1** The temp directory, diff, and file list were already written to disk in Step 1. Verify they exist:
   ```bash
   ls /tmp/code-review-<pr-number>/diff.patch /tmp/code-review-<pr-number>/files.txt
   ```

   **3.2** Filter the diff to source-only. Exclude files that are clearly generated or vendored by **path pattern**, not by extension (e.g., `features.md` is source code in some repos):
   ```bash
   # Exclude generated/vendored/build artifacts by path pattern
   grep -v -E '(zz_generated|vendor/|payload-manifests/|node_modules/|\.lock$|\.sum$|go\.sum|package-lock)' \
       /tmp/code-review-<pr-number>/files.txt > /tmp/code-review-<pr-number>/source-files.txt

   # Extract source-only diff
   awk '
     BEGIN { while((getline f < "/tmp/code-review-<pr-number>/source-files.txt")>0) files[f]=1 }
     /^diff --git/ { found=0; path=$NF; sub(/^b\//, "", path); if(path in files) found=1 }
     found
   ' /tmp/code-review-<pr-number>/diff.patch > /tmp/code-review-<pr-number>/diff-source.patch
   ```
   If `diff-source.patch` is empty (no source files after filtering), use `diff.patch` as fallback.

   **3.3** For EACH dimension (unit-tests, idiomatic, dry, solid), do the following loop:
   1. Read `/tmp/code-review-<pr-number>/diff-source.patch` (use `diff.patch` as fallback if `diff-source.patch` is empty)
   2. Perform the dimension analysis
   3. Write the findings to `/tmp/code-review-<pr-number>/<dimension-name>.md` using the Write tool. File names: `unit-tests.md`, `idiomatic.md`, `dry.md`, `solid.md`, `profile-<sme-name>.md`
   4. Move to the next dimension

   **3.4** After ALL dimensions are done, proceed to Step 3 (Build Verification). Do NOT skip writing the temp files — Step 4 reads them back.

The dimension definitions and output format are the same regardless of execution mode. Only the dispatch mechanism changes.

#### Dimension: Unit Test Coverage
Skip if `--skip-tests` is specified.
- For each new or modified source file, check if a corresponding test file exists.
- For each new exported/public function with non-trivial logic, verify that tests exist.
- Evaluate test quality: Are tests testing meaningful behavior or just achieving coverage?
- Check for edge cases, error paths, and boundary conditions in tests.
- **If a language skill is loaded**, apply its test conventions (e.g., Go: table-driven tests, `t.Run()`, `t.Parallel()`).
- **If a profile is loaded**, apply its additional test conventions.
- Return findings as structured text.

#### Dimension: Idiomatic Code
- **If a language skill is loaded**, apply its idiomatic code guidance to the changed files.
- **If no language skill is loaded**, perform a general review: error handling, naming, clarity, complexity.
- **If a profile is loaded**, follow the profile's instructions to discover and apply any repo-local agents or skills it references. For example, the hypershift profile points to `.claude/agents/` — read the agents, pick the relevant ones based on changed files, and use their guidance.
- Return findings as structured text.

#### Dimension: DRY Principle
- Check for code duplication within and across changed files.
- Look for repeated patterns that could be extracted into shared functions or utilities.
- Identify copy-paste code that introduces maintenance risk.
- Flag magic numbers and string literals that should be constants.
- **If a profile is loaded**, check for proper use of project-specific shared utilities (e.g., hypershift's `support/` package).
- Return findings as structured text.

#### Dimension: SOLID Principles
- Apply SOLID principles proportionally to the scope of the changes:
  - **SRP**: Does each new function/type/module have one clear responsibility?
  - **OCP**: Are changes extending behavior without modifying stable abstractions?
  - **LSP**: Do new implementations honor the contracts of their interfaces?
  - **ISP**: Are interfaces focused and minimal?
  - **DIP**: Do high-level modules depend on abstractions rather than concrete implementations?
- **If a profile is loaded**, apply any project-specific structural patterns it defines.
- Return findings as structured text.

#### Dimension: Profile-Specific Reviews (only if profile is loaded)
  - Read the profile skill to discover which SME agents are required.
  - In **Agent mode**: launch **one sub-agent per SME agent** listed in the profile, each using the corresponding `subagent_type`. All run in parallel with each other and with the other dimensions.
  - In **subagent mode**: add one `{ type: "worker", prompt: "..." }` entry per SME to the `runs.all()` call alongside the other dimensions.
  - In **serial mode**: run each SME review sequentially inline after the core dimensions.
  - Each SME review must receive:
    - The complete diff
    - PR title and description (if available)
    - The Jira ticket context (if available)
    - A prompt asking it to review the changes from its domain perspective.

### Step 3 — Build Verification

This step can run in parallel with Step 2 (in Agent/subagent mode) or after it (in serial mode), since it is independent. Skip if `--skip-build` is specified.

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

After all review dimensions and build verification complete, aggregate findings into a structured report.

**In serial mode**, you MUST follow these steps:

**4.1** Read each dimension's findings from the temp files. Only read files that were actually produced in this run — skip absent files rather than failing:
```
Read /tmp/code-review-<pr-number>/unit-tests.md   (skip if --skip-tests was specified or file absent)
Read /tmp/code-review-<pr-number>/idiomatic.md
Read /tmp/code-review-<pr-number>/dry.md
Read /tmp/code-review-<pr-number>/solid.md
Read /tmp/code-review-<pr-number>/profile-*.md     (only files written in step 3.3 of THIS run)
```
If a file does not exist, note "skipped" in the corresponding report section rather than failing.

**4.2** Assemble the final report with the following sections, using the content read from the temp files:

1. **PR Info**: PR title, author, base branch, and link.
2. **Files Reviewed**: List all files reviewed, categorized by type.
3. **Unit Test Coverage**: Content from `unit-tests.md`. Note if skipped.
4. **Idiomatic [Language] Code**: Content from `idiomatic.md` (use detected/specified language name, or "Code" if no language).
5. **DRY Compliance**: Content from `dry.md`.
6. **SOLID Compliance**: Content from `solid.md`.
7. **Build Verification**: Build result (pass/fail/skipped).
8. **Profile-Specific Checks**: Content from `profile-*.md` files (only if profile loaded).
9. **Overall Verdict**: PASS, FAIL, or PASS WITH RECOMMENDATIONS.
10. **Required Actions**: Issues that must be fixed before merging (blocking).
11. **Recommended Improvements**: Suggestions that are not blocking but would improve code quality.

**4.3** Write the final assembled report to `/tmp/code-review-<pr-number>/report.md` using the Write tool.

**4.4** Do NOT delete the temp directory. Leave `/tmp/code-review-<pr-number>/` intact so the user can inspect the intermediate findings and the final report.

In **Agent/subagent mode**, findings are already available from tool responses — skip 4.1, assemble the report directly from the responses using the same section structure.

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
- `--skip-tests`: Skip the unit test coverage review dimension. Useful when changes do not affect testable code.
- `--serial`: Force serial inline execution mode (mode 3) regardless of available tools. Dimensions run sequentially with findings persisted to temp files. Useful for testing or on models with small context windows.
