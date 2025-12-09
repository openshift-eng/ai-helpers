---
description: Analyze test code structure without running tests to identify coverage gaps
argument-hint: <path-or-url> [--output <path>] [--priority <level>] [--test-structure-only]
---

## Name
test-coverage:analyze

## Synopsis
```
/test-coverage:analyze <path-or-url> [--output <path>] [--priority <level>] [--test-structure-only]
```

## Description

The `test-coverage:analyze` command analyzes test code structure **without running tests**. This command examines test files and source files to identify:
- What e2e/integration tests exist in the codebase
- What source code has corresponding tests
- What source code lacks tests
- Test organization and coverage gaps

**Focus on E2E Tests:** By default, this command focuses on e2e (end-to-end) and integration tests, excluding unit tests. This ensures analysis targets higher-level test coverage gaps that validate real-world scenarios and system integration.

**Language Support:** This command currently supports Go projects only.

This command is the foundation for QE or Dev teams to understand their e2e test coverage baseline and identify areas requiring additional testing.

## Arguments

- `<source-directory>`: Path or URL to source code directory/file to analyze
  - **Local path**: `./pkg/`, `/home/user/project/test/e2e/networking/infw.go`
  - **GitHub URL**: `https://github.com/owner/repo/blob/main/test/file_test.go`
  - **GitHub raw URL**: `https://raw.githubusercontent.com/owner/repo/main/test/file_test.go`
  - **GitLab URL**: `https://gitlab.com/owner/repo/-/blob/main/test/file_test.go`
  - **HTTP(S) URL**: Any direct file URL
  - URLs are automatically downloaded and cached in `.work/test-coverage/cache/`

- `--output <path>`: Output directory for generated reports (default: `.work/test-coverage/analyze/`)
  - Generates HTML report, JSON summary, and text summary

- `--priority <level>`: Filter results by priority (optional)
  - Values: `all`, `high`, `medium`, `low`
  - Default: `all`

- `--include-test-utils`: Include test utility/helper files in analysis (optional)
  - By default, utility files are excluded (*_util.go, *_utils.go, *_helper.go, helpers.go, etc.)
  - Use this flag to analyze test utility functions for e2e test coverage
  - Useful for auditing test infrastructure code

- `--include-unit-tests`: Include unit tests in analysis (optional)
  - By default, only e2e/integration tests are analyzed
  - Use this flag to include unit tests in the coverage analysis
  - E2E tests are identified by:
    - File naming patterns (e.g., *e2e*_test.go, *integration*_test.go)
    - Directory location (e.g., test/e2e/, test/integration/)
    - Test markers (e.g., [Serial], [Disruptive] for Ginkgo)

- `--test-pattern <pattern>`: Custom test file pattern (optional)
  - Example: `--test-pattern "**/*Test.java,**/Test*.java"`

- `--test-structure-only`: Analyze only test file structure, skip source file analysis (optional)
  - When enabled, analyzes ONLY test files to document what tests exist and what they cover
  - Does NOT look for corresponding source files or identify coverage gaps
  - Useful for:
    - Understanding test organization and structure
    - Documenting test cases in existing test files
    - Quick analysis of a single test file or test directory
    - Generating test documentation (test cases, helper functions, resource types)
  - Generates reports focused on test structure:
    - Test cases and their purpose
    - Helper functions used in tests
    - Resource types and test utilities
    - Protocol/feature coverage matrices
  - Much faster than full coverage analysis
  - Example: `/test-coverage:analyze ./test/extended/networking/infw.go --test-structure-only`

## Implementation

The command uses test structure analysis (backend) to analyze test files and source files without running tests.

**Two Analysis Modes:**

1. **Full Coverage Analysis (default):** Analyzes both test files AND source files to identify coverage gaps
   - Maps tests to source code
   - Identifies untested files and functions
   - Generates coverage gap reports
   - Follows Steps 1-8 below

2. **Test Structure Only (--test-structure-only):** Analyzes ONLY test files to document their structure
   - Extracts test cases, helper functions, resource types
   - Documents what each test covers
   - Does NOT analyze source files or identify gaps
   - Much faster, useful for test documentation
   - Follows Steps 1, 2 (test files only), 3, 7 (test-focused reports)

### Step 1: Resolve Input

1. **Resolve input path or URL**:
   - If input is a URL:
     - Convert GitHub/GitLab blob URLs to raw URLs
     - Download file to `.work/test-coverage/cache/`
     - Use cached version if already downloaded
     - Extract to temporary directory if it's an archive (zip, tar.gz)
   - If input is a local path:
     - Convert to absolute path
     - Validate that path exists and is readable
2. Load Go-specific configuration (test patterns, source patterns, parsers)

### Step 2: Discover Test and Source Files

**Note:** If `--test-structure-only` is used, only test files are discovered; source file discovery is skipped.

1. Walk directory tree, excluding common directories:
   - `vendor/`, `node_modules/`, `__pycache__/`, `.git/`, etc.
   - Unit test directories (e.g., `test/unit/`, `unit/`) unless `--include-unit-tests` is specified
2. Identify e2e/integration test files based on:
   - **File naming patterns:**
     - `*e2e*_test.go`, `*integration*_test.go`
   - **Directory location:**
     - `test/e2e/`, `test/integration/`, `e2e/`, `integration/`
   - **Content markers (if file can be read):**
     - Ginkgo markers: `[Serial]`, `[Disruptive]`, `g.Describe(`, `g.It(`
3. Identify source files based on language patterns
4. Filter out test utility/helper files unless `--include-test-utils` is specified:
   - `*_util.go`, `*_utils.go`, `*_helper.go`, `helpers.go`
5. Apply `--exclude` patterns if specified

### Step 3: Parse Test Files

For each test file:
1. Extract test functions using Go patterns:
   - Functions matching `func Test*`, `func Benchmark*`
2. Extract imports to identify tested modules
3. Extract function calls within tests (potential test targets)
4. Infer corresponding source file:
   - `handler_test.go` → `handler.go`

### Step 4: Parse Source Files

**Note:** This step is skipped when `--test-structure-only` is used.

For each source file:
1. Extract functions/methods using Go patterns
2. Determine function visibility:
   - Exported (capitalized) vs private (lowercase)
3. Calculate cyclomatic complexity (count decision points)
4. Record line ranges for each function

### Step 5: Map Tests to Source Code

**Note:** This step is skipped when `--test-structure-only` is used.

1. Create mapping between test files and source files
2. For each function in source files:
   - Find tests that reference this function
   - Mark as tested/untested
   - Count number of tests covering it
3. Calculate file-level statistics:
   - Total functions
   - Tested functions
   - Untested functions
   - Function coverage percentage

### Step 6: Identify Coverage Gaps

**Note:** This step is skipped when `--test-structure-only` is used.

1. **Untested Files**: Source files with no corresponding test file
   - Priority: High if file has exported/public functions
2. **Untested Functions**: Functions not referenced in any tests
   - Priority: High for exported/public, Low for private
3. **Partially Tested Files**: Files with some but not all functions tested
   - Priority: Based on percentage of untested functions
4. Apply `--priority` filter if specified

### Step 7: Generate Reports

**In test-structure-only mode**, generates test-focused reports:
- `test-structure-report.html` - Interactive report with test cases, helper functions, resource types
- `test-structure-analysis.json` - Machine-readable test metadata
- `test-structure-summary.txt` - Terminal-friendly test summary

**In full coverage mode**, generates coverage gap reports:

1. **HTML Report** (`test-coverage-report.html`):
   - Interactive web-based report combining structure summary and gaps
   - Includes collapsible sections for test cases, helper functions, and gaps
   - Color-coded priority indicators (High=red, Medium=yellow, Low=blue)
   - Coverage matrices for protocols and IP stacks
   - Filterable gaps by priority
   - Recommendations section
   - Best viewed in a web browser

2. **JSON Report** (`test-structure-report.json`):
   - Complete gap data with file paths, functions, priorities
   - Machine-readable format for automation and CI/CD integration

3. **Text Summary** (`test-structure-summary.txt`):
   - Overall statistics (files with/without tests, function coverage)
   - High-priority gaps
   - Recommendations
   - Plain text format for console viewing

4. **Console Output**:
   - Summary of findings
   - Paths to all generated reports

### Step 8: Invoke Test Structure Analyzer

Execute the test structure analyzer Python script:
```bash
python skills/analyze/test_structure_analyzer.py \
    <source-directory> \
    --priority <priority> \
    --output <output-dir>
```

## Return Value

- **Format**: Terminal output with summary + generated report files

**Terminal Output:**
```
Test Structure Analysis Complete

Summary:
  Total Source Files:    45
  Files With Tests:      30 (66.7%)
  Files Without Tests:   15 (33.3%)

  Total Functions:       234
  Tested Functions:      189 (80.8%)
  Untested Functions:    45 (19.2%)

High Priority Gaps:
  1. pkg/config.go - No test file (3 exported functions)
  2. pkg/validator.go - No test file (5 exported functions)
  3. cmd/server/auth.go - Partially tested (4/8 functions)

Reports Generated:
  HTML Report:    .work/test-coverage/analyze/test-coverage-report.html
  JSON Report:    .work/test-coverage/analyze/test-structure-report.json
  Text Summary:   .work/test-coverage/analyze/test-structure-summary.txt

Recommendations:
  - Create test files for 15 untested source files
  - Add tests for 45 untested functions
  - Focus on high-priority gaps first
```

**Exit Status:**
- 0: Analysis successful
- 2: Analysis failed (parsing error, invalid input)

## Examples

### Example 1: Analyze e2e test structure without running tests (Go project)

```
/test-coverage:analyze ./pkg/
```

Analyzes e2e/integration test file structure for a Go project to identify untested functions and files without running any tests. Unit tests are excluded by default.

### Example 2: Analyze test structure with high priority filter

```
/test-coverage:analyze ./pkg/ --priority high
```

Analyzes Go test structure and shows only high-priority gaps (files without tests, untested public functions).

### Example 3: Analyze with custom output directory

```
/test-coverage:analyze ./pkg/ --output reports/test-gaps/
```

Analyzes test structure and generates reports in custom output directory.

### Example 4: Analyze only test file structure (single file)

```
/test-coverage:analyze ./test/extended/networking/infw.go --test-structure-only
```

Analyzes ONLY the test file structure without looking for source files. Generates documentation showing:
- All test cases and what they cover
- Helper functions used in tests
- Resource types and test utilities
- Coverage matrices (protocols, IP stacks, platforms)

Useful for quickly understanding what a test file covers without analyzing source code.

### Example 5: Analyze test directory structure only

```
/test-coverage:analyze ./test/e2e/ --test-structure-only
```

Analyzes all test files in the e2e directory to document the test suite structure without source file analysis.

### Example 6: Analyze remote test file from GitHub

```
/test-coverage:analyze https://github.com/openshift/origin/blob/master/test/extended/networking/infw.go --test-structure-only
```

Downloads and analyzes a test file directly from GitHub. The command automatically converts the GitHub blob URL to a raw URL and caches the download.

### Example 7: Analyze remote test file using raw URL

```
/test-coverage:analyze https://raw.githubusercontent.com/openshift/origin/master/test/extended/networking/infw.go --test-structure-only
```

Analyzes a test file using the raw GitHub URL directly.

### Example 8: Analyze test file with forced re-download

To force re-downloading a cached URL, simply delete the cache and run again:

```
rm -rf .work/test-coverage/cache/
/test-coverage:analyze https://github.com/user/repo/blob/main/test/file_test.go --test-structure-only
```

## Prerequisites

### Python Dependencies

The command uses Python for parsing and report generation. No external packages are required - only standard library modules are used.

### Checking Prerequisites

The command will automatically check for Python 3.8+ and provide installation instructions if missing.

## Notes

- **URL Support:** The command accepts both local paths and URLs (GitHub, GitLab, or any HTTP(S) URL)
  - Remote files are automatically detected, downloaded, and cached
  - Downloaded files are cached in `.work/test-coverage/cache/` for reuse
  - GitHub blob URLs are automatically converted to raw URLs
  - Clear cache with `rm -rf .work/test-coverage/cache/` to force re-download
- **E2E Focus:** By default, this command focuses on e2e/integration tests. Use `--include-unit-tests` to include unit tests.
- **Two Modes:** Use `--test-structure-only` to analyze only test files (fast, for documentation), or omit it for full coverage gap analysis
- This command analyzes test structure without running tests, making it very fast
- Works even if tests are broken or code doesn't compile
- Useful for identifying e2e test coverage gaps during development and code review
- HTML report provides interactive visualization of e2e test coverage and gaps
- JSON output enables integration with CI/CD pipelines and dashboards
- Text summary is ideal for console viewing and quick reference
- **Test Structure Only mode** is perfect for:
  - Documenting existing test suites
  - Understanding what a test file covers
  - Quick analysis of a single test file
  - Generating test case reports for review

## See Also

- `/test-coverage:gaps` - Identify untested code paths with priority-based analysis
