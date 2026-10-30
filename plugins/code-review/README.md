# code-review Plugin

Automated code quality review with language-aware analysis for pull requests and
pre-commit changes, plus an optional multi-specialist deep review skill.

## Pre-Commit Review Skill

`/code-review:pre-commit-review` reviews staged and unstaged changes for test
coverage, idiomatic code, duplication, design, and build verification. Its slash
invocation is unchanged from the former command.

```text
/code-review:pre-commit-review [--language <lang>] [--profile <name>] [--skip-build] [--skip-tests]
```

- `--language <lang>`: Load language-specific guidance. Go is currently available; other languages use general checks until guidance is added. If omitted, detect the language from changed-file extensions.
- `--profile <name>`: Load project-specific conventions and checks.
- `--skip-build`: Skip build verification.
- `--skip-tests`: Skip unit-test coverage review.

## PR Review Command

`/code-review:pr` reviews a GitHub pull request. It remains a plugin command.

```text
/code-review:pr <pr-url-or-number> [--language <lang>] [--profile <name>] [--skip-build] [--skip-tests]
```

## Deep Review Skill

Use `/code-review:deep-review` for a deeper multi-specialist panel review. It
checks bugs, security, architecture, consistency, and test coverage; verifies
blocking bug findings with runtime reproducers; and can optionally post a
pending review to GitHub or GitLab.

```text
/code-review:deep-review [--serial] [--comment] [--coderabbit] [--codex] [-reviewer,...] [pr-url-or-number]
```

## Language and Profile Skills

Language skills provide idiomatic code, test-convention, and build guidance.
Store them at `skills/<language>-code-review/SKILL.md`; Go is currently available
at `skills/go-code-review/`.

Profile skills add project-specific conventions, shared utilities, build
commands, and additional review criteria. Store them at
`skills/<profile>-code-review/SKILL.md`; the HyperShift profile is
`skills/hypershift-code-review/`.

### Adding language guidance

Add `skills/<language>-code-review/SKILL.md` with test conventions, idiomatic
code checks, and priority-ordered build commands.

### Adding a project profile

Add `skills/<profile>-code-review/SKILL.md` with project-specific test
conventions, architectural patterns, shared utilities, build commands, and
additional checks. Keep guidance self-contained when it refers to paths that
may not exist outside that project.

## OpenCode Installation

AI Helpers plugins can be installed for OpenCode with the Agent Package Manager
(APM). Add this dependency to your project's `apm.yml`, then run `apm install`:

```yaml
target: [opencode]
dependencies:
  - openshift-eng/ai-helpers/plugins/code-review
```

See the [AI Helpers installation guide](../../README.md#other-tools) for the full
manifest example and other supported agent targets.
