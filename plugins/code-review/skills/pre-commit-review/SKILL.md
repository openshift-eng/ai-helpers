---
name: "pre-commit-review"
description: "Review staged and unstaged changes before committing. Use when asked for a pre-commit review, a code-quality review of the current diff, or when a solve workflow requests an independent review."
argument-hint: "[--language <lang>] [--profile <name>] [--skip-build] [--skip-tests]"
user-invocable: true
slash: true
---

## Name
code-review:pre-commit-review

## Synopsis
```text
/code-review:pre-commit-review [--language <lang>] [--profile <name>] [--skip-build] [--skip-tests]
```

## Purpose

Review the current staged and unstaged changes before committing. Assess test coverage, idiomatic code, duplication, design, and build verification. Review only the current diff; do not report pre-existing issues in unchanged code.

The same-named skill replaces the former plugin command, so the `/code-review:pre-commit-review` invocation remains available in Claude Code. Install the plugin through APM to expose this skill to OpenCode and other supported clients.

## Workflow

### 1. Resolve options and review guidance

Read options from the skill invocation or the user's request:

| Option | Behavior |
|--------|----------|
| `--language <lang>` | Apply language-specific review guidance. If omitted, detect from changed-file extensions. |
| `--profile <name>` | Apply project-specific conventions and checks. |
| `--skip-build` | Skip build verification and report it as skipped. |
| `--skip-tests` | Skip unit-test coverage review and report it as skipped. |

Detect the primary language from changed-file extensions: `.go` → Go, `.py` → Python, `.rs` → Rust, `.ts`/`.tsx` → TypeScript, and `.java` → Java. If files are mixed or the language has no guidance, continue with a general review.

Load optional guidance from sibling skill directories, relative to this `SKILL.md`:

- Language: `../<language>-code-review/SKILL.md` (currently available: `../go-code-review/SKILL.md`).
- Profile: `../<name>-code-review/SKILL.md` (for example, `../hypershift-code-review/SKILL.md`).

If requested guidance is absent, say so and continue without it. Give loaded guidance to each relevant review pass.

**Completion criterion:** all supplied options are accounted for, and each available language/profile guide has been loaded before reviewing.

### 2. Establish the diff

Collect and deduplicate changed paths from both `git diff --name-only` and `git diff --cached --name-only`. Categorize them as source, tests, configuration, or documentation. If the diff is empty, report that and stop. If no source files changed, narrow the review accordingly.

**Completion criterion:** the complete staged and unstaged file list is recorded, with no unchanged files added to scope.

### 3. Review the changes

Run these independent review passes:

1. **Test coverage** — unless `--skip-tests` was supplied, check for tests covering changed behavior, new public functions, edge cases, and error paths. A missing test for a new public function with non-trivial logic is blocking. Apply language and profile test conventions.
2. **Idiomatic code** — apply language guidance when available; otherwise assess error handling, naming, clarity, and complexity. Follow relevant project guidance.
3. **DRY** — find duplication, repeated patterns, copy-paste code, and values that should be named constants. Apply profile guidance about shared project utilities.
4. **Design** — assess responsibilities, extensibility, interface contracts, interface size, and dependency direction in proportion to the change.
5. **Profile-specific review** — apply extra checks and reviewer perspectives named by the profile.

Keep each pass independent until findings are collected. When the host supports agent delegation, delegate independent passes concurrently and provide each reviewer with the changed-file list and relevant guidance. Otherwise, perform the passes sequentially in this session. If the profile names specialist reviewers, use the host's available delegation mechanism; without delegation, apply each specialist perspective as a separate pass. Provide the full diff and available PR or issue context to profile-specific reviewers.

**Completion criterion:** every applicable pass has examined every in-scope change, and skipped passes are recorded with the supplied option that skipped them.

### 4. Verify the build

Unless `--skip-build` was supplied, run the most specific available build/verification command in this order:

1. Profile guidance.
2. Language guidance.
3. Project detection: `make build` (or the documented default `make`) when a `Makefile` is present; `go build ./...` for Go; `cargo build` for Rust; `npm run build` or `yarn build` for JavaScript/TypeScript; `python -m py_compile` on changed files for Python.

Run this alongside review passes when the host supports concurrent work. Record the command and result. On failure, include the relevant output and mark the overall review as `FAIL`. If explicitly skipped, report it as skipped; do not imply that the build was verified.

**Completion criterion:** build verification is recorded as passed, failed, or explicitly skipped; no result is implied.

### 5. Report findings

Return a structured report with:

1. Files reviewed, categorized by type.
2. Unit-test coverage findings, or that the pass was skipped.
3. Idiomatic code findings, naming the language when applicable.
4. DRY and design findings.
5. Build command and result.
6. Profile-specific findings, if applicable.
7. Overall verdict: `PASS`, `FAIL`, or `PASS WITH RECOMMENDATIONS`.
8. Required actions (blocking) and recommended improvements (non-blocking).

Make findings specific and actionable, with `file:line` references where possible. Match review depth to change risk. Offer to fix straightforward issues rather than silently expanding the review into implementation.

**Completion criterion:** every finding is tied to changed code, has an actionable recommendation, and the verdict reflects all review and build results.

## Examples

```text
/code-review:pre-commit-review
/code-review:pre-commit-review --language go --profile hypershift
/code-review:pre-commit-review --skip-build
/code-review:pre-commit-review --language python --skip-tests
```
