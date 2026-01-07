# Codebase Plugin

A plugin to analyze codebases and generate improvement suggestions.

## Commands

### `/codebase:suggest-improvements`

Analyzes the current repository and generates a comprehensive markdown file with actionable improvement suggestions.

**What it checks:**
- 📄 **Documentation**: README quality, CONTRIBUTING.md, CHANGELOG, LICENSE
- 🧹 **Code Quality**: Linter/formatter setup, code organization, naming conventions
- 🧪 **Testing**: Test coverage, test organization, testing best practices
- 🔒 **Security**: .gitignore, secrets detection, security scanning setup
- 📦 **Dependencies**: Version pinning, outdated packages, vulnerability scanning
- 🏗️ **Project Structure**: Standard layout, separation of concerns

**Usage:**
```bash
# Generate IMPROVEMENTS.md in current directory
/codebase:suggest-improvements

# Specify custom output file
/codebase:suggest-improvements my-review.md
```

**Output:**
A structured markdown report with:
- Executive summary
- Prioritized improvements (High/Medium/Low)
- Detailed findings by category
- Quick wins list
- Recommended next steps

## Prerequisites

- Must be run from within a git repository
- Works with any programming language/framework

## Installation

### From the Claude Code Plugin Marketplace

```bash
/plugin marketplace add openshift-eng/ai-helpers
/plugin install codebase@ai-helpers
```

### Manual Installation (Cursor)

```bash
mkdir -p ~/.cursor/commands
git clone git@github.com:openshift-eng/ai-helpers.git
ln -s ai-helpers ~/.cursor/commands/ai-helpers
```

## Example Output

The command generates a file like:

```markdown
# Codebase Improvement Suggestions

**Generated on**: 2025-01-07
**Repository**: my-awesome-project

## Executive Summary
The codebase is well-structured but lacks comprehensive documentation 
and has gaps in test coverage. Priority should be given to adding 
a CONTRIBUTING.md and increasing unit test coverage.

## Priority Improvements

### 🔴 High Priority
- Add CONTRIBUTING.md with development setup instructions
- Configure dependabot for security updates

### 🟡 Medium Priority
- Add missing unit tests for utils/ directory
- Set up pre-commit hooks for linting

### 🟢 Low Priority (Nice to Have)
- Add badges to README (CI status, coverage)
- Create CHANGELOG.md

...
```

## Use Cases

- **Onboarding**: Help new team members understand improvement areas
- **Tech Debt**: Identify and prioritize technical debt
- **Audits**: Prepare for code reviews or compliance audits
- **Continuous Improvement**: Regular health checks of your codebase

