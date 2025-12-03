---
description: Run golangci-lint and fix all reported issues
---

## Name
golangci-linter:lint-fix

## Synopsis
```
/golangci-linter:lint-fix
```

## Description
The `golangci-linter:lint-fix` command runs golangci-lint and systematically fixes all reported issues in the codebase. It creates a todo list to track progress and fixes issues by category until all linter checks pass.

This command handles common linter categories including goconst, gocyclo, prealloc, revive, staticcheck, and unparam with appropriate fix strategies for each.

## Implementation

Follow this process:

1. **Run `make lint`** to identify all issues

2. **Create a todo list** to track fixing each category of issues

3. **Fix all issues systematically** using these strategies:
   - **goconst**: Add constants for repeated strings (3+ occurrences)
   - **gocyclo**: Add `//nolint:gocyclo` comments for complex test functions with justification
   - **prealloc**: Pre-allocate slices when capacity is known using `make([]T, 0, capacity)`
   - **revive**: Fix comment spacing issues (add space after `//`)
   - **staticcheck**: Fix deprecated code, remove redundant checks, fix naming conventions (ErrFoo for errors)
   - **unparam**: Remove unused parameters or always-nil error returns

4. **Re-run `make lint`** after each category to verify fixes

5. **Continue until all issues are resolved**

### Important Guidelines

- For test files with high cyclomatic complexity, add `//nolint:gocyclo` with reason "Table-driven test with inherent complexity"
- For generated files, add `//nolint` comments rather than modifying the code
- For Ginkgo/Gomega dot imports, add `//nolint:staticcheck,revive` with reason "Ginkgo/Gomega DSL convention"
- When creating constants, check if one already exists in the package before adding a new one
- Use existing constants from other packages when appropriate
- For functions that always return nil error, remove the error return and update all callers
- For unused parameters, either remove them or add `//nolint:unparam` if they're needed for interface compatibility

### Final Step

Run `make lint` one last time to confirm all issues are resolved (0 issues).

## Return Value
- **Format**: Progress updates and final confirmation
- **Success**: Confirmation that all linter issues are resolved with 0 issues remaining
- **Partial**: List of remaining issues if some could not be automatically fixed

## Examples

1. **Basic usage**:
   ```text
   /golangci-linter:lint-fix
   ```
   Output:
   ```text
   Running make lint... Found 23 issues

   Creating todo list:
   ☐ Fix goconst issues (8)
   ☐ Fix staticcheck issues (7)
   ☐ Fix gocyclo issues (4)
   ☐ Fix revive issues (4)

   Fixing goconst issues...
   ✓ Added constant APIContentType for "application/json"
   ✓ Added constant DefaultTimeout for "30s"
   ...

   Running make lint... 15 issues remaining
   ...

   ✓ All linter issues resolved (0 issues)
   ```

2. **Already clean codebase**:
   ```text
   /golangci-linter:lint-fix
   ```
   Output:
   ```text
   Running make lint... 0 issues found
   ✓ Code already passes all linter checks
   ```

## Arguments
This command takes no arguments.
