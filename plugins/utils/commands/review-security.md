---
description: Orchestrate security scanners and provide contextual triage of findings
argument-hint: "[file-paths-or-patterns]"
---

## Name
utils:review-security

## Synopsis
```
/utils:review-security [file-paths-or-patterns]
```

## Description
The `utils:review-security` command is a security analysis orchestrator that combines deterministic scanning tools with AI-powered contextual reasoning. Unlike traditional security scanners that produce noisy, context-free alerts, this command:

**Orchestrates proven tools** (when available):
- `gitleaks` or `trufflehog` - Secret detection with maintained pattern databases
- `gosec` - Go AST-aware security analysis
- `bandit` - Python-specific security scanner
- `semgrep` - Cross-language semantic analysis

**Adds intelligence layer**:
- Triages tool findings to reduce false positives
- Explains exploitability in plain language for non-security developers
- Traces data flow to assess reachability from user input
- Identifies if findings are in test/dead code
- Suggests concrete fixes with code examples

**Analyzes what tools miss**:
- Business logic flaws spanning multiple files
- Authentication/authorization design issues
- Context-dependent vulnerabilities
- Security controls removed in diffs

**Scope**: Without arguments, analyzes `git diff` changes (ideal for PR reviews). With file paths/patterns, analyzes specified files.

**Important**: This is NOT a replacement for CI/CD security gates. Deterministic tools should still run in your pipeline. This command helps developers understand and act on findings during development.

## Implementation

### 1. Determine Analysis Scope

**Diff mode (default - no arguments)**:
- Run `git diff --name-only` to identify changed files
- Run `git diff` to capture what actually changed (for context analysis)
- If no diff exists, fall back to `git status --porcelain` for unstaged changes
- Extract change intent: refactor vs new feature vs bugfix (from commit messages/branch name, or the added inline comments or even the changed code, if necessary)

**File mode (arguments provided)**:
- Use Glob tool to expand patterns: `/utils:review-security "pkg/**/*.go"`
- Validate files exist and are readable
- Note: In file mode, analyze entire file content (no diff context)

**Filter scope**:
- Exclude: vendored code (`vendor/`, `node_modules/`, etc.), generated code (protobuf, etc.)
- Analyze all other files in scope

### 2. Run Security Scanning Tools

**CRITICAL**: Only scan files in scope to avoid performance issues:
- In diff mode: scan only changed files (from `git diff --name-only`)
- In file mode: scan only specified files (from arguments)

Create `.work/security-review/` directory. Collect the list of files to scan and detect languages:

```bash
# FILES already determined in step 1
# Detect languages from file extensions
GO_FILES=$(echo "$FILES" | grep '\.go$' || true)
PY_FILES=$(echo "$FILES" | grep '\.py$' || true)
```

**Tool availability checking and installation**:

Before running scans, check which tools are needed based on detected languages:
- Language-specific: `gosec` (for Go; only check if Go files are in scope), `bandit` (for Python; only check if Python files are in scope)
- Language-agnostic: `gitleaks` or `trufflehog`
- Multi-language: `semgrep`

Detect OS. For each missing tool:
1. Provide platform-aware installation commands (`dnf`/`apt`/`brew`/`go install`/`pip install`)
2. **Let user choose if to install it - WAIT for response before proceeding**
Do not use AskUserQuestion tool. Just ask for one tool, let user type yes/no, then ask for another tool for user to type yes/no, et al.

After asking all missing tools and collecting user's choices, install selected tools via Bash, then inform user which tools will run (e.g., "Running: gosec ✓, gitleaks ✓, semgrep ✗")

Execute all available tools (all language-specific, language-agnostic and multi-language)

**Go analysis** (only if `.go` files in scope):
```bash
# IMPORTANT: Do NOT use ./... which scans entire codebase
# Get unique directories containing changed .go files
GO_DIRS=$(echo "$GO_FILES" | xargs -n1 dirname 2>/dev/null | sort -u || true)

# Run gosec only on directories with changed files
if [ -n "$GO_DIRS" ]; then
  gosec -fmt json -out .work/security-review/gosec.json $GO_DIRS 2>/dev/null
fi
```

**Python analysis** (only if `.py` files in scope):
```bash
# IMPORTANT: Do NOT use -r . which scans entire directory tree
# Run bandit only on specific Python files
if [ -n "$PY_FILES" ]; then
  bandit -f json -o .work/security-review/bandit.json $PY_FILES 2>/dev/null
fi
```

**Secret detection** (try both, use whichever is available):
```bash
# Option 1: gitleaks (scan specific files only, not entire repo)
echo "$FILES" | tr '\n' '\0' | xargs -0 gitleaks detect --no-git --report-format json --report-path .work/security-review/gitleaks.json 2>/dev/null

# Option 2: trufflehog (scan specific files only)
echo "$FILES" | tr '\n' '\0' | xargs -0 trufflehog filesystem --json 2>/dev/null > .work/security-review/trufflehog.json
```

**General SAST** (if semgrep available):
```bash
# Run semgrep only on files in scope
if command -v semgrep >/dev/null 2>&1; then
  semgrep --config auto --json --output .work/security-review/semgrep.json $FILES 2>/dev/null
fi
```

**Track execution**:
- Log which tools executed successfully vs which were unavailable
- Note which findings come from which tool
- Continue with gap analysis even if no tools available

### 3. Contextual Triage of Tool Findings

**Important**: Language-specific tools (e.g. gosec, bandit), language-agnostic tools (e.g. gitleaks) and multi-language tools (e.g. semgrep) may report overlapping findings. This is normal and indicates higher confidence in the issue.

For each finding from the tools, perform AI-powered analysis:

**Deduplication**:
- Group findings by file + line number + issue type
- If multiple tools report the same issue (e.g., gosec + semgrep both find SQL injection at line 45):
  - Treat as **high confidence** finding
  - Note all tools that detected it in the report
  - Only analyze it once (don't duplicate the triage work)
- Example: "SQL injection in handlers/user.go:145 (detected by: gosec, semgrep)"

**A. Read Sufficient Context**
- Read the complete function containing the finding
- If file < 500 lines: read entire file
- If file ≥ 500 lines: read ±50 lines or to function boundaries (whichever is larger)
- If still unclear about data flow, trace back through function callers and imports until you can determine if user input reaches the vulnerability

**B. False Positive Detection**
- Assess: Is this a true positive or false positive?
- Examples of false positives to catch (including but not limited to):
  - Secrets in test fixtures or example configurations
  - SQL concatenation in logging/debugging code (not executed)
  - Hardcoded keys that are actually public API identifiers
  - Weak crypto used for non-security purposes (checksums)
- Provide reasoning for classification

**C. Exploitability Analysis**
For confirmed issues, answer:
- **Reachability**: Is this code path reachable from user input? Trace data flow
- **Impact**: What's the actual blast radius if exploited?
- **Likelihood**: Is exploitation trivial or requires complex conditions?
- **Context**: Is this in production code, test code, or dead code?

Reclassify severity based on context, including but not limited to below examples:
- Tool says CRITICAL → Actually in unreachable test helper → Downgrade to INFO
- Tool says MEDIUM → User input flows directly with no validation → Upgrade to HIGH

**D. Exploitability Narratives**
Write 2-3 sentence attack scenario for each confirmed HIGH/CRITICAL:

Example:
> "An attacker could submit a malicious `user_id` parameter containing `'; DROP TABLE users;--`. Because this value is concatenated directly into the SQL query at line 45 without parameterization, the database would execute the injected command, potentially deleting all user records."

This helps non-security developers understand the real-world impact.

**E. Concrete Fix Suggestions**
For each finding, provide:
- Explanation of WHY it's vulnerable
- Code example showing the fix
- Link to relevant documentation (OWASP, language security guides)

### 4. Gap Analysis (AI's Unique Value)

Review code for issues deterministic tools cannot detect:

**Business Logic Flaws**:
- Authorization checks in wrong order
- Race conditions in security-critical sections
- Time-of-check-time-of-use (TOCTOU) vulnerabilities
- Insufficient validation of complex business rules

**Design Issues**:
- Authentication missing before sensitive operations
- Privilege escalation via parameter manipulation
- Session fixation vulnerabilities
- Insecure state management across requests

**Multi-File Context**:
- Data flow vulnerabilities spanning multiple files
- Inconsistent security controls across similar endpoints
- Global state manipulation affecting security

**Diff-Specific Analysis** (when in diff mode):
- Flag if a security control was REMOVED (e.g., auth check deleted)
- Identify new attack surface introduced by changes
- Detect if refactoring inadvertently bypassed validation
- Note: Tools scan whole files; understanding "this line moved vs new" requires reasoning

### 5. Generate Actionable Report

Create a report at `.work/security-review/report-{timestamp}.md` with:

**Executive Summary**:
- Tools executed (which ran successfully, which were unavailable)
- Total findings: {count by severity}
- Scope analyzed (diff vs full files)

**Tool Findings (Triaged)**:
For each finding from `gitleaks`, `trufflehog`, `gosec`, `bandit`, `semgrep`:
```markdown
### [HIGH] SQL Injection in handlers/user.go:145
**Source**: gosec (G201)
**AI Assessment**: TRUE POSITIVE - High severity confirmed

**Exploitability**:
An attacker could submit a malicious `user_id` parameter containing `'; DROP TABLE users;--`.
Because this value is concatenated directly into the SQL query without parameterization, the
database would execute the injected command, potentially deleting all user records.

**Reachability**: User input flows directly from HTTP handler → database query with no validation

**Fix**:
\```go
// Before (vulnerable)
query := "SELECT * FROM users WHERE id = " + userInput

// After (secure)
query := "SELECT * FROM users WHERE id = ?"
rows, err := db.Query(query, userInput)
\```

**Reference**: https://owasp.org/www-community/attacks/SQL_Injection
```

Clearly mark which findings are:
- **Tool Found + AI Confirmed**: High confidence issues
- **Tool Found + AI Downgraded**: False positives with reasoning
- **AI Identified (Gap Analysis)**: Issues tools missed

**Gap Analysis Section**:
List issues found via manual review that tools cannot detect (business logic, design flaws, diff-specific concerns)

**Summary Statistics**:
- X tool findings triaged (Y confirmed, Z false positives)
- N gap analysis issues identified
- Top 3 most critical issues to address first

## Return Value

**Console Output**:
- Summary of tools executed (available vs missing)
- Count of findings by severity (after AI triage)
- Top 3 critical issues with file:line references
- Path to detailed report

**Report File**: `.work/security-review/report-{timestamp}.md`
- Tool findings with AI triage and exploitability analysis
- Gap analysis for issues tools missed
- Concrete fix suggestions with code examples

**Format**: Markdown optimized for reading and sharing with team

## Examples

### Example 1: Review changes in current PR/branch (default)
```
/utils:review-security
```

**Output**:
```
Security Review - Diff Mode
Tools: gitleaks ✓ | gosec ✓ | bandit ✗ (not installed) | semgrep ✗

Analyzed: 3 changed files (24 lines modified)
Findings: 1 CRITICAL, 2 HIGH, 1 FALSE POSITIVE

Top Issues:
1. [CRITICAL] Hardcoded AWS key in config/aws.go:23 (gitleaks)
2. [HIGH] SQL injection in handlers/user.go:145 (gosec - confirmed)
3. [HIGH] Removed auth check in api/delete.go:67 (AI - gap analysis)

Report: .work/security-review/report-20241216-143022.md
```

### Example 2: Review specific files
```
/utils:review-security pkg/handlers/*.go config.yaml
```

### Example 3: Review all Python files
```
/utils:review-security "**/*.py"
```

## Arguments

**`$@`** (optional): File paths or glob patterns
- **No arguments**: Analyzes `git diff` (changed files only) - ideal for PR reviews
- **With arguments**: Analyzes specified files/patterns
  - Single file: `config.go`
  - Multiple files: `main.go config.go utils.go`
  - Glob pattern: `"pkg/**/*.go"` `"**/*.py"`

## What This Command Does NOT Do

- **Replace CI/CD security gates**: Deterministic tools (`gosec`, `snyk`, etc.) should still run in pipelines
- **Provide deterministic results**: AI analysis is contextual and may vary
- **Scan dependencies**: Use `npm audit`, `snyk`, `trivy`, or `safety` for dependency vulnerabilities
- **Guarantee complete coverage**: This is a development aid, not a compliance certification tool

## Notes

**Tool Installation**:
The command provides platform-aware installation suggestions when tools are missing. Common installation methods:
- `gitleaks`: Package manager (`dnf`, `apt`, `brew`) or https://github.com/gitleaks/gitleaks
- `trufflehog`: Package manager or https://github.com/trufflesecurity/trufflehog
- `gosec`: `go install github.com/securego/gosec/v2/cmd/gosec@latest`
- `bandit`: `pip install bandit`
- `semgrep`: Package manager or `pip install semgrep`

**Best Practices**:
- Run this command before creating PRs to catch issues early
- Review AI triage reasoning - it may miss edge cases
- Use in combination with peer code review, not as replacement
- For compliance/audit needs, rely on deterministic tool output in CI/CD
