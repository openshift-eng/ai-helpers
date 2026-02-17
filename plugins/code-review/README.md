# code-review Plugin

Automated code quality review with language-aware analysis for pre-commit verification.

## Commands

### `/code-review:pre-commit-review`

Performs a comprehensive code quality review of staged and unstaged changes before committing. Analyzes unit test coverage, idiomatic code patterns, DRY compliance, SOLID principles, and build verification.

**Usage:**
```bash
/code-review:pre-commit-review [--language <lang>] [--profile <name>] [--skip-build] [--skip-tests]
```

**Arguments:**
- `--language <lang>`: Language skill to load. Currently shipped: `go`. Planned: `python`, `rust`, `typescript`, `java`. Auto-detected if omitted.
- `--profile <name>`: Project profile to load for project-specific conventions.
- `--skip-build`: Skip build verification.
- `--skip-tests`: Skip unit test coverage review.

## Language Skills

Language skills provide language-specific guidance for idiomatic code review, test conventions, and build commands. They are stored in `skills/lang-<lang>/SKILL.md`.

### Available Languages

| Language | Skill Directory | Key Features |
|----------|----------------|--------------|
| Go | `skills/lang-go/` | Table-driven tests, `gofmt`, error wrapping, race detection |

### Adding a New Language

1. Create a directory: `skills/lang-<lang>/`
2. Create `SKILL.md` with the following sections:
   - **When to Use This Skill**: Describe when this skill is loaded.
   - **Test Conventions**: Language-specific test patterns, file organization, and best practices.
   - **Idiomatic Code Checklist**: Language-specific code quality checks (formatting, naming, error handling, idioms).
   - **Build Commands**: Priority-ordered build, test, and verification commands.
3. Use the frontmatter format:
   ```yaml
   ---
   name: "<Language> Language Review"
   description: "Language-specific review guidance for <Language> code"
   ---
   ```

## Profile Skills

Profile skills provide project-specific conventions that layer on top of language checks. They are stored in `skills/profile-<name>/SKILL.md`.

### Available Profiles

| Profile | Skill Directory | Key Features |
|---------|----------------|--------------|
| HyperShift | `skills/profile-hypershift/` | controller-runtime patterns, `support/upsert/`, `make api`, structured logging |

### Adding a New Profile

1. Create a directory: `skills/profile-<name>/`
2. Create `SKILL.md` with the following sections:
   - **When to Use This Skill**: Describe when this profile is loaded.
   - **Additional Test Conventions**: Project-specific test patterns that supplement the language conventions.
   - **Project-Specific Patterns**: Architectural patterns, framework usage, and coding conventions specific to the project.
   - **Project Utilities**: Shared packages or utilities that should be used instead of reimplementing.
   - **Build Commands**: Project-specific build, test, and verification commands.
   - **Additional Checks**: Any project-specific checks (e.g., API generation, commit format).
3. Use the frontmatter format:
   ```yaml
   ---
   name: "<Project> Project Profile"
   description: "Project-specific review profile for <project>"
   ---
   ```
4. All guidance must be self-contained within the SKILL.md. Do not reference external paths that may not exist in every repository.

## How It Works

The command runs in a defined sequence of steps:

1. **Parse arguments** and load applicable language and profile skills.
2. **Identify changed files** from `git diff`.
3. **Unit test coverage review** with language and profile conventions applied.
4. **Idiomatic code review** with language-specific checklist.
5. **DRY principle review** with profile-aware utility checks.
6. **SOLID principles review** with profile-aware structural patterns.
7. **Build verification** using profile, language, or auto-detected build commands.
8. **Project-specific checks** from the profile (if loaded).
9. **Generate report** with verdict and actionable findings.

## Examples

```bash
# Auto-detect language, no profile
/code-review:pre-commit-review

# Go code with HyperShift conventions
/code-review:pre-commit-review --language go --profile hypershift

# Skip build for docs-only changes
/code-review:pre-commit-review --skip-build

# Python review without test checks
/code-review:pre-commit-review --language python --skip-tests
```
