---
description: Review code for common security vulnerabilities and issues
argument-hint: [file-paths-or-patterns]
---

## Name
utils:review-security

## Synopsis
```
/utils:review-security [file-paths-or-patterns]
```

## Description
The `utils:review-security` command performs automated security analysis on code changes or specified files, identifying common security vulnerabilities and providing actionable recommendations. When invoked without arguments, it analyzes all modified files in the current git working directory. When provided with file paths or glob patterns, it analyzes the specified files.

This command helps developers and security engineers identify potential security issues early in the development cycle, including:
- Hardcoded secrets and credentials (API keys, passwords, tokens)
- SQL injection vulnerabilities
- Command injection risks
- Cross-site scripting (XSS) vulnerabilities
- Insecure cryptographic practices
- Sensitive data exposure in logs
- Path traversal vulnerabilities
- Insecure file permissions
- Use of deprecated or insecure functions
- Common OWASP Top 10 vulnerabilities

The security review is language-aware and adapts its analysis based on file types (Go, Python, JavaScript, etc.).

## Implementation

### 1. Determine Scope
- If file paths or patterns are provided:
  - Use Glob to expand patterns and find matching files
  - Validate that specified files exist
- If no arguments provided:
  - Run `git status --porcelain` to find modified/added files
  - Run `git diff --name-only` to find changed files in current branch
  - If no git changes found, ask user to specify files or patterns

### 2. File Collection and Filtering
- Collect all files to be analyzed from the determined scope
- Filter to relevant code files based on extensions:
  - Source code: `.go`, `.py`, `.js`, `.ts`, `.php`, `.sh`, `.bash`
  - Configuration: `.yaml`, `.yml`, `.json`, `.xml`, `.toml`, `.env`
  - Infrastructure as Code: `.tf`, `.dockerfile`, `Dockerfile`
- Exclude common non-security-relevant files:
  - Test files (unless explicitly requested)
  - Vendored dependencies
  - Generated code (protobuf, swagger, etc.)
  - Binary files, images, documentation
- Group files by language/type for efficient analysis

### 3. Security Analysis by Category

For each file, perform comprehensive security checks:

#### A. Secrets and Credentials Detection
- **Patterns to detect**:
  - API keys: `api[_-]?key`, high-entropy strings near "key"/"token"
  - Passwords: `password\s*=\s*["'][^"']+["']`, `pwd`, `passwd`
  - Private keys: `BEGIN.*PRIVATE KEY`, `BEGIN RSA PRIVATE KEY`
  - OAuth tokens: `oauth.*token`, `bearer.*token`
  - AWS credentials: `AKIA[0-9A-Z]{16}`, `aws_access_key_id`, `aws_secret_access_key`
  - Database URLs: Connection strings with embedded credentials
  - Generic secrets: High-entropy strings (base64, hex) in assignments
- **Context analysis**:
  - Distinguish between actual secrets and placeholder/example values
  - Check if values are from environment variables (safer)
  - Identify if secrets are in test fixtures (lower risk but still flag)
- **Exceptions**:
  - Skip known test credentials (e.g., "changeme", "test123")
  - Ignore comments showing example format

#### B. Injection Vulnerabilities

**SQL Injection**:
- Detect string concatenation in SQL queries
- Flag unsafe query builders without parameterization
- Language-specific patterns:
  - Go: `db.Query("SELECT * FROM users WHERE id = " + userInput)`
  - Python: `cursor.execute("SELECT * FROM users WHERE id = " + user_id)`
  - JavaScript: Template literals in SQL without sanitization

**Command Injection**:
- Detect unsafe shell command execution with user input
- Flag patterns like:
  - Go: `exec.Command("sh", "-c", userInput)`, `os.system()`
  - Python: `os.system(user_input)`, `subprocess.shell=True` with user input
  - JavaScript: `child_process.exec()` with unsanitized input
- Check for missing input validation/sanitization

**Path Traversal**:
- Detect file operations with user-controlled paths
- Flag missing path sanitization (e.g., no check for `..`, absolute path validation)
- Patterns: `os.path.join()`, `filepath.Join()` with external input

#### C. Cryptographic Issues
- **Weak algorithms**:
  - MD5, SHA1 for security purposes (acceptable for checksums)
  - DES, RC4, ECB mode
- **Hardcoded IVs/salts**: Look for static initialization vectors
- **Insufficient key lengths**: RSA < 2048 bits, AES < 128 bits
- **Insecure random**: `math/rand` instead of `crypto/rand` in Go, `random` vs `secrets` in Python
- **Missing TLS verification**: `InsecureSkipVerify: true`, disabled certificate validation

#### D. Data Exposure and Logging
- Detect logging of sensitive data:
  - Password fields in log statements
  - Credit card numbers, SSNs (pattern matching)
  - Authorization headers, tokens
  - Personal Identifiable Information (PII)
  - Any structure type variables which may contain child or nested fields that are sensitive
- Flag overly verbose error messages exposing internal details
- Check for debug mode enabled in production code

#### E. Authentication and Authorization
- Missing authentication checks before sensitive operations
- Hardcoded user roles or permissions
- Insecure session management (predictable session IDs)
- Missing CSRF protection in web frameworks
- Weak password policies in validation code

#### F. Language-Specific Vulnerabilities

**Go-specific**:
- Unsafe use of `unsafe` package
- Missing error checks (especially in security-critical code)
- Race conditions in security checks (missing mutex locks)

**Python-specific**:
- Use of `pickle` with untrusted data
- `eval()` or `exec()` with user input
- YAML unsafe loading: `yaml.load()` without `Loader`

**JavaScript/TypeScript**:
- `eval()`, `Function()` constructor with user input
- `dangerouslySetInnerHTML` in React
- Prototype pollution vulnerabilities

### 4. Severity Classification
For each finding, assign a severity level:
- **CRITICAL**: Hardcoded secrets, direct SQL injection, RCE vulnerabilities
- **HIGH**: Command injection, authentication bypasses, weak crypto
- **MEDIUM**: Potential XSS, path traversal, sensitive data logging
- **LOW**: Deprecated functions, missing input validation in non-critical paths
- **INFO**: Security best practices, recommendations

### 5. Report Generation
Create a comprehensive security report with:

#### Report Structure:
```markdown
# Security Review Report

**Analyzed**: {number} files
**Generated**: {timestamp}
**Scope**: {git changes | specified files}

## Executive Summary
- Total findings: {count}
- Critical: {count}
- High: {count}
- Medium: {count}
- Low: {count}

## Critical Findings

### [CRITICAL] Hardcoded API Key in config.go:45
**File**: `config.go:45`
**Issue**: Hardcoded API key detected in source code
**Code**:
apiKey := "sk-1234567890abcdef"

**Risk**: Exposed credentials can be extracted from source code and used for unauthorized access
**Recommendation**:
- Move API key to environment variable
- Use secret management service (HashiCorp Vault, AWS Secrets Manager)
- Rotate the exposed key immediately

**Example Fix**:
apiKey := os.Getenv("API_KEY")
if apiKey == "" {
    return fmt.Errorf("API_KEY environment variable not set")
}

## High Findings
...

## Medium Findings
...

## Low Findings
...

## Best Practices & Recommendations
- General security improvements
- Additional tools to consider (gosec, bandit, semgrep)
- Security testing recommendations

## Clean Files
Files with no security issues:
- file1.go
- file2.py
```

Save report to: `.work/security-review/report-{timestamp}.md`

### 6. Interactive Feedback
After analysis:
- Display summary of findings by severity
- Show the report file path
- Highlight the top 3 most critical issues
- Offer to:
  - Show detailed findings for specific severity levels
  - Generate fixes for specific issues
  - Create JIRA/GitHub issues for tracking
  - Re-run analysis on specific files

### 7. False Positive Handling
- Provide context for each finding (surrounding code)
- Allow filtering by confidence level
- Suggest inline comments to suppress false positives:
  - Go: `// #nosec G101` (gosec format)
  - Python: `# nosec` (bandit format)
  - Generic: `// security: ignore` with justification

## Return Value
- **Markdown Report**: Detailed security analysis saved to `.work/security-review/report-{timestamp}.md`
- **Summary**: Console output showing count of findings by severity
- **Exit Status**: Number of critical/high severity findings (for CI/CD integration)

## Examples

1. **Review all changed files in current branch**:
   ```
   /utils:review-security
   ```
   Output:
   ```
   Security Review Complete

   Analyzed: 8 files
   Findings:
   - Critical: 2
   - High: 3
   - Medium: 5
   - Low: 1

   Report: .work/security-review/report-2024-12-04-143022.md

   Top Issues:
   1. [CRITICAL] Hardcoded AWS credentials in config/aws.go:23
   2. [CRITICAL] SQL injection vulnerability in db/query.go:156
   3. [HIGH] Command injection risk in utils/exec.go:45
   ```

2. **Review specific files**:
   ```
   /utils:review-security cmd/server/main.go pkg/api/*.go
   ```

3. **Review all Go files in a directory**:
   ```
   /utils:review-security "pkg/**/*.go"
   ```

4. **Review configuration files**:
   ```
   /utils:review-security "**/*.yaml" "**/*.env"
   ```

## Arguments
- `$@`: Optional file paths or glob patterns to analyze
  - If not provided: Analyzes all modified files in git working directory
  - Supports glob patterns: `"pkg/**/*.go"`, `"*.py"`
  - Multiple arguments: Space-separated list of files/patterns
  - Examples:
    - Single file: `config.go`
    - Multiple files: `main.go config.go utils.go`
    - Pattern: `"cmd/**/*.go"`
    - Mixed: `main.go "pkg/**/*.go" config.yaml`

## Notes
- This is a complementary tool to specialized security scanners (gosec, bandit, semgrep)
- For production use, integrate dedicated security scanning tools into CI/CD
- Review findings manually - automated tools may have false positives
- Consider running `/compliance:analyze-cve` for dependency vulnerability scanning
- Some language-specific issues require specialized tools for complete coverage

## Integration with Other Tools
The command can suggest running:
- `gosec` for Go-specific security analysis
- `bandit` for Python security issues
- `npm audit` for JavaScript dependency vulnerabilities
- `safety` for Python dependency vulnerabilities
- `trivy` for container image scanning
