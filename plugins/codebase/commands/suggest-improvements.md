---
description: Review codebase and generate a file with summarized improvement suggestions
argument-hint: "[output-file]"
---

## Name
codebase:suggest-improvements

## Synopsis
```
/codebase:suggest-improvements [output-file]
```

## Description
The `codebase:suggest-improvements` command analyzes the current repository and generates a comprehensive file containing actionable improvement suggestions. It reviews code quality, project structure, documentation, and adherence to best practices.

This command is useful for:
- New team members wanting to understand areas for improvement
- Tech debt identification and prioritization
- Preparing for code reviews or audits
- Continuous improvement initiatives

## Implementation

Analyze the current repository thoroughly and generate a markdown file with improvement suggestions. Follow these steps:

### Step 1: Gather Repository Context

1. **Identify the project type and tech stack**:
   - Check for package.json (Node.js/JavaScript/TypeScript)
   - Check for go.mod (Go)
   - Check for requirements.txt, setup.py, pyproject.toml (Python)
   - Check for pom.xml, build.gradle (Java)
   - Check for Cargo.toml (Rust)
   - Check for Makefile, Dockerfile, docker-compose.yml

2. **Understand project structure**:
   - List top-level directories and key files
   - Identify source code directories (src/, lib/, pkg/, cmd/, etc.)
   - Identify test directories (test/, tests/, *_test.go, *.spec.ts, etc.)

### Step 2: Review Documentation Quality

1. **README.md Analysis**:
   - Check if README.md exists at the root
   - Verify it contains: project description, installation instructions, usage examples, contribution guidelines
   - Check for badges (CI status, coverage, version, license)
   - Assess clarity and completeness

2. **Additional Documentation**:
   - Check for CONTRIBUTING.md
   - Check for CHANGELOG.md or HISTORY.md
   - Check for LICENSE file
   - Check for API documentation (docs/, api/, swagger, openapi)
   - Check for architecture decision records (ADR)

### Step 3: Analyze Code Quality and Best Practices

1. **Project Configuration**:
   - Check for linter configuration (.eslintrc, .golangci.yml, .pylintrc, etc.)
   - Check for formatter configuration (.prettierrc, .editorconfig, etc.)
   - Check for pre-commit hooks (.pre-commit-config.yaml, .husky/)
   - Check for CI/CD configuration (.github/workflows/, .gitlab-ci.yml, Jenkinsfile)

2. **Code Organization**:
   - Assess if code follows standard project layout for the language
   - Check for clear separation of concerns (MVC, clean architecture, etc.)
   - Look for overly large files (>500 lines) that might need splitting
   - Check for consistent naming conventions

3. **Dependency Management**:
   - Check if dependencies are pinned to specific versions
   - Look for outdated or deprecated dependencies (check lock files)
   - Check for security vulnerability scanning setup (dependabot, snyk, etc.)

4. **Error Handling**:
   - Sample a few source files to assess error handling patterns
   - Check for proper error propagation vs swallowing errors
   - Look for TODO/FIXME/HACK comments indicating technical debt

### Step 4: Review Testing Practices

1. **Test Coverage**:
   - Check if tests exist
   - Assess test organization (unit tests, integration tests, e2e tests)
   - Check for test configuration files
   - Look for coverage reporting setup

2. **Test Quality Indicators**:
   - Check for test utilities and fixtures
   - Look for mocking/stubbing setup
   - Assess if tests follow naming conventions

### Step 5: Security Best Practices

1. **Basic Security Checks**:
   - Check for .gitignore including sensitive files (.env, secrets, credentials)
   - Look for hardcoded secrets or API keys in source files (sample check)
   - Check for security scanning in CI/CD
   - Verify HTTPS usage in any URLs found in config

2. **Authentication/Authorization** (if applicable):
   - Check for secure session handling
   - Look for input validation patterns

### Step 6: Generate Improvement Report

Create the output file (default: `IMPROVEMENTS.md`) with the following structure:

```markdown
# Codebase Improvement Suggestions

**Generated on**: {current date}
**Repository**: {repo name from git remote or folder name}

## Executive Summary
{2-3 sentence overview of the codebase health and top priorities}

## Priority Improvements

### 🔴 High Priority
{Critical issues that should be addressed immediately}

### 🟡 Medium Priority
{Important improvements for code quality and maintainability}

### 🟢 Low Priority (Nice to Have)
{Enhancements that would improve developer experience}

## Detailed Findings

### Documentation
{Specific findings and recommendations}

### Code Quality
{Specific findings and recommendations}

### Testing
{Specific findings and recommendations}

### Security
{Specific findings and recommendations}

### Project Structure
{Specific findings and recommendations}

## Quick Wins
{List of small, easy-to-implement improvements}

## Recommended Next Steps
1. {First actionable step}
2. {Second actionable step}
3. {Third actionable step}
```

### Step 7: Present Results

1. Write the report to the specified output file (or `IMPROVEMENTS.md` if not specified)
2. Display a summary to the user:
   - Number of high/medium/low priority items found
   - Path to the generated report
   - Top 3 recommended actions

## Return Value
- **File Output**: Markdown file with structured improvement suggestions
- **Console Output**: Summary of findings and path to the generated report

## Examples

1. **Basic usage (generates IMPROVEMENTS.md)**:
   ```
   /codebase:suggest-improvements
   ```

2. **Custom output file**:
   ```
   /codebase:suggest-improvements code-review-2025.md
   ```

3. **Output to a specific directory**:
   ```
   /codebase:suggest-improvements docs/improvements.md
   ```

## Arguments
- $1: Output file path (optional, defaults to `IMPROVEMENTS.md` in the current directory)

## Notes
- The command analyzes the repository in the current working directory
- Large repositories may take longer to analyze
- Suggestions are based on common best practices and may need to be adapted to your specific context
- The generated file can be committed to track improvement progress over time

