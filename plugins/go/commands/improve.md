---
description: Analyze and fix Go code quality issues using gopls and go vet
argument-hint: [path]
---

## Name

go:improve - Identify and automatically fix Go code quality issues

## Synopsis

```
/go:improve [path]
```

## Description

The `go:improve` command analyzes Go code using `gopls check` and `go vet` to identify code quality issues that are typically only visible in an editor. It categorizes findings by severity, automatically applies fixes, and verifies changes with tests.

Issues detected include:
- **Modernization**: Deprecated APIs, outdated patterns, type inference opportunities
- **Potential Bugs**: Printf format mismatches, mutex copies, unreachable code, shadowed variables
- **Code Quality**: Unnecessary complexity, missing error checks, inefficient patterns

The command automatically applies all fixes, rebuilds the project, runs tests, and provides a comprehensive summary of changes.

## Arguments

- `[path]` (optional): Target path to analyze
  - If provided: Analyze specific path (e.g., `pkg/operator`, `./pkg/controllers/...`)
  - If omitted: Analyze entire repository (`./...`)
  - **Note**: The `vendor/` directory is always excluded from analysis and modifications

## Implementation

### Step 1: Parse Arguments

Extract the target path from `$ARGUMENTS`:

- If arguments provided: Use as target path
- If no arguments: Use `./...` for entire repository
- Always exclude `vendor/` directory from analysis

### Step 2: Run Analysis Tools in Parallel

Execute both analysis tools simultaneously:

**Tool 1: gopls check** - Go language server modernization checks
```bash
find [path] -name "*.go" -not -path "./vendor/*" -exec gopls check -severity=hint {} \;
```

Notes:
- Replace `[path]` with target path (use `.` if target is `./...`)
- `-severity=hint` shows all issues including hints
- `find` processes individual .go files and excludes vendor/

**Tool 2: go vet** - Official Go static analysis
```bash
go vet [path]
```

### Step 3: Analyze and Categorize Findings

Parse output from both tools and organize issues by severity:

**Severity Levels:**

1. **Critical (Potential Bugs)** - Issues likely to cause runtime errors
   - Printf format mismatches
   - Mutex copy issues
   - Unreachable code
   - Invalid struct tags
   - Shadowed variables

2. **High Priority (Deprecated APIs)** - APIs scheduled for removal
   - Deprecated package usage (e.g., `io/ioutil`)
   - Deprecated function calls
   - Outdated patterns with replacements

3. **Medium Priority (Modernization)** - Code improvements
   - Simplifications (e.g., `s[a:len(s)]` → `s[a:]`)
   - Type inference opportunities
   - Unused code

4. **Low Priority (Code Quality)** - Style and efficiency
   - Unnecessary complexity
   - Missing error checks
   - Inefficient patterns

**Presentation Format:**

Group findings by:
1. Severity (Critical → High → Medium → Low)
2. File/Package location
3. Issue type

For each finding display:
- File path and line number (format: `file:line`)
- Issue description
- Current code snippet
- Suggested fix

### Step 4: Apply Fixes

After presenting all findings:

1. **Announce intent**: "I'll now apply all fixes automatically."

2. **Apply fixes systematically** in severity order:
   - Critical issues (potential bugs)
   - Deprecated APIs
   - Modernization improvements
   - Code quality improvements

3. **For each fix**:
   - Read the file
   - Apply change using Edit tool
   - Track modifications

4. **Use gopls automatic fixes** when available:
   ```bash
   find [path] -name "*.go" -not -path "./vendor/*" -exec gopls check -fix {} \;
   ```
   - If automatic fixes unavailable, apply manually based on diagnostics

### Step 5: Verify Changes

After applying all fixes:

1. **Rebuild project**:
   ```bash
   go build ./...
   ```

2. **Run tests**:
   ```bash
   go test ./...
   ```
   - Report pass/fail status
   - If tests fail, analyze if failures are related to fixes
   - Clearly note any fix that broke tests

3. **Re-run analysis**:
   ```bash
   find [path] -name "*.go" -not -path "./vendor/*" -exec gopls check -severity=hint {} \;
   go vet [path]
   ```

4. **Generate summary report**:
   - Issues fixed count
   - Issues remaining count
   - Build status (success/failure)
   - Test status (pass/fail)
   - List of all modified files

## Return Value

**Format**: Analysis report followed by fix summary

**Analysis Report Structure**:
```
## Analysis Results

Found N issues across M files:

### Critical (Potential Bugs) - X issues
- file:line: Issue description

### High Priority (Deprecated APIs) - X issues
- file:line: Issue description

### Medium Priority (Modernization) - X issues
- file:line: Issue description

### Low Priority (Code Quality) - X issues
- file:line: Issue description
```

**Fix Summary Structure**:
```
---

Applying all fixes...

✓ Fixed: Description [file:line]
✓ Fixed: Description [file:line]
...

---

## Summary

- Fixed: X/Y issues
- Modified files: N
- Build status: ✓ Success / ✗ Failed
- Test status: ✓ All tests passed / ✗ Tests failed
- Remaining issues: N
  - file:line: Reason not fixed (if any)
```

## Examples

### Example 1: Analyze Entire Repository

```
/go:improve
```

Analyzes all Go files in the repository (excluding `vendor/`), categorizes all findings, applies all fixes, and verifies with tests.

### Example 2: Analyze Specific Package

```
/go:improve pkg/operator
```

Analyzes only files in the `pkg/operator` directory and its subdirectories.

### Example 3: Analyze Multiple Packages

```
/go:improve ./pkg/controllers/...
```

Analyzes all packages under `pkg/controllers/` using Go's `...` wildcard pattern.

### Example 4: Sample Output

```
## Analysis Results

Found 15 issues across 8 files:

### Critical (Potential Bugs) - 2 issues
- pkg/operator/starter.go:142: Printf format %d with string argument
- pkg/controllers/deployment.go:89: Mutex copied by value

### High Priority (Deprecated APIs) - 3 issues
- pkg/util/crypto.go:45: Use of deprecated io/ioutil package
- pkg/auth/handler.go:67: Use of deprecated jwt.Parse (use jwt.ParseWithClaims)
- pkg/config/reader.go:23: Use of deprecated yaml.Unmarshal pattern

### Medium Priority (Modernization) - 8 issues
- pkg/operator/status.go:56: Slice expression can be simplified: s[a:len(s)] → s[a:]
- pkg/controllers/sync.go:123: Type inference available for make()
- pkg/util/strings.go:89: Unused variable 'result'
...

### Low Priority (Code Quality) - 2 issues
- pkg/util/helpers.go:34: Unused variable 'ctx'
- pkg/operator/main.go:78: Unnecessary else block

---

Applying all fixes...

✓ Fixed Printf format in pkg/operator/starter.go:142
✓ Fixed mutex copy in pkg/controllers/deployment.go:89
✓ Replaced io/ioutil with io/os in pkg/util/crypto.go
✓ Updated jwt.Parse call in pkg/auth/handler.go:67
✓ Simplified slice expression in pkg/operator/status.go:56
...

---

## Summary

- Fixed: 14/15 issues
- Modified files: 8
- Build status: ✓ Success
- Test status: ✓ All tests passed
- Remaining issues: 1 (needs manual review)
  - pkg/operator/complex.go:234: Complex refactoring needed for deprecation
```

## Important Guidelines

### Safety

- **NEVER** modify files in `vendor/` directory
- Always verify fixes don't break the build
- Preserve code behavior and functionality
- If unsure about a fix, skip it and mention in summary

### Efficiency

- Run analysis tools in parallel when possible
- Group related fixes in same file to minimize operations
- Use `gopls` built-in fixes instead of manual edits when available

### Thoroughness

- Address all findings or explain why they can't be fixed
- Apply complex fixes carefully or ask user for guidance
- Document any issues that can't be automatically fixed

### Output

- Provide clear descriptions of findings and changes
- Use `file:line` format for all references
- Summarize overall impact at the end

## Special Cases

**gopls check unavailable:**
- If `gopls check` fails or is not installed, skip it
- Use only `go vet` for analysis
- Mention this limitation in output
- Provide installation instructions: `go install golang.org/x/tools/gopls@latest`

**No issues found:**
- Report success
- Congratulate user on clean code
- Show analysis was thorough (tools used, files scanned)

**Too many issues (>50):**
- Present all findings categorized by severity
- Ask user: "Continue with all fixes, or focus on Critical/High priority only?"
- Respect user preference for scope

**Build or test failures:**
- If build fails after fixes, report which files were modified
- If tests fail, analyze if related to fixes
- Offer to revert problematic changes
- Provide details to help user debug
