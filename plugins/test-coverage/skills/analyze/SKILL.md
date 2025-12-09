---
name: Test Structure Analysis
description: Analyze test code structure directly to provide coverage analysis
---

# Test Structure Analysis Skill

This skill provides the ability to analyze test code structure **directly from test files** without running tests. It examines test files and source files to identify what is tested and what is not.

## When to Use This Skill

Use this skill when you need to:
- Analyze test code organization without running tests
- Identify files and functions without tests
- Understand what e2e/integration tests cover
- Find coverage gaps by examining test structure
- Generate comprehensive test structure reports
- Fast analysis (seconds, not minutes)

## Prerequisites

### Required Tools

- **Python 3.8+** for test structure analysis
- **Go toolchain** for the target Go project

### Installation

```bash
# Ensure Python 3.8+ is installed
python3 --version

# Go toolchain for target project
go version
```

## How It Works

**Note: This skill currently supports Go projects only.**

### Step 1: Discover Test and Source Files

The analyzer discovers test and source files based on Go conventions:

**Test Files:**
- Files ending with `_test.go`
- E2E/integration tests identified by:
  - File naming patterns: `*e2e*_test.go`, `*integration*_test.go`
  - Directory location: `test/e2e/`, `test/integration/`, `e2e/`, `integration/`
  - Content markers: Ginkgo markers like `[Serial]`, `[Disruptive]`, `g.Describe(`, `g.It(`

**Source Files:**
- Files ending with `.go` (excluding test files)
- Optionally exclude vendor, generated code, etc.

### Step 2: Parse Test Files

For each test file, extract:

1. **Test functions/methods**:
   - Function name
   - Line number range
   - Test framework (Go testing, Ginkgo)
   - Test type (unit, integration, e2e)

2. **Test targets** (what the test is testing):
   - Imports and references to source files
   - Function calls and instantiations
   - Inferred from test names

3. **Test metadata**:
   - Test descriptions/documentation
   - Test tags/markers
   - Helper functions

**Example for Go:**
```go
// File: pkg/handler_test.go
package handler_test

import (
    "testing"
    "myapp/pkg/handler"
)

func TestHandleRequest(t *testing.T) {  // ← Test function
    h := handler.New()                   // ← Target: handler.New
    result := h.HandleRequest("test")    // ← Target: handler.HandleRequest
    // ...
}
```

**Extraction result:**
```json
{
  "test_file": "pkg/handler_test.go",
  "source_file": "pkg/handler.go",
  "tests": [
    {
      "name": "TestHandleRequest",
      "lines": [6, 10],
      "targets": ["handler.New", "handler.HandleRequest"],
      "type": "unit"
    }
  ]
}
```

### Step 3: Parse Source Files

For each source file, extract:

1. **Functions/methods**:
   - Function name
   - Line number range
   - Visibility (public/private/exported)
   - Parameters and return types
   - Complexity metrics

2. **Classes/structs**:
   - Type definitions
   - Methods
   - Fields

**Example for Go:**
```go
// File: pkg/handler.go
package handler

type Handler struct {
    config Config
}

func New() *Handler {              // ← Function: New
    return &Handler{}
}

func (h *Handler) HandleRequest(req string) (string, error) {  // ← Function: HandleRequest
    if req == "" {
        return "", errors.New("empty request")
    }
    return process(req), nil
}
```

**Extraction result:**
```json
{
  "source_file": "pkg/handler.go",
  "functions": [
    {
      "name": "New",
      "lines": [8, 10],
      "visibility": "exported",
      "complexity": 1
    },
    {
      "name": "HandleRequest",
      "lines": [12, 20],
      "visibility": "exported",
      "complexity": 3,
      "receiver": "Handler"
    }
  ]
}
```

### Step 4: Map Tests to Source Code

Create a mapping between tests and source code:

1. **Direct mapping** (test file → source file):
   - `handler_test.go` → `handler.go`

2. **Function-level mapping** (test → function):
   - `TestHandleRequest` tests `HandleRequest`

3. **Import-based mapping**:
   - Analyze imports in test files to identify tested modules

**Mapping result:**
```json
{
  "pkg/handler.go": {
    "test_file": "pkg/handler_test.go",
    "functions": {
      "New": {
        "tested": true,
        "tests": ["TestHandleRequest"],
        "test_count": 1
      },
      "HandleRequest": {
        "tested": true,
        "tests": ["TestHandleRequest"],
        "test_count": 1
      }
    },
    "overall_tested_functions": 2,
    "overall_untested_functions": 0,
    "function_test_coverage": 100.0
  }
}
```

### Step 5: Identify Coverage Gaps

Identify what is **not tested**:

1. **Untested source files**:
   - Source files with no corresponding test file
   - Priority: Based on file importance (exported functions)

2. **Untested functions**:
   - Functions not referenced in any tests
   - Priority: Exported/public functions > private functions

3. **Partially tested files**:
   - Files with test file but missing tests for some functions

**Gap categorization:**

```json
{
  "gaps": {
    "untested_files": [
      {
        "file": "pkg/config.go",
        "functions": 5,
        "exported_functions": 3,
        "priority": "high",
        "reason": "No corresponding test file found"
      }
    ],
    "untested_functions": [
      {
        "file": "pkg/handler.go",
        "function": "process",
        "visibility": "private",
        "priority": "low",
        "reason": "Not referenced in any tests"
      }
    ]
  },
  "summary": {
    "total_source_files": 45,
    "files_with_tests": 30,
    "files_without_tests": 15,
    "total_functions": 234,
    "tested_functions": 189,
    "untested_functions": 45,
    "function_coverage_percentage": 80.8
  }
}
```

### Step 6: Generate Reports

**IMPORTANT:** Claude Code generates all three report formats at runtime based on the analyzer's structured output. The analyzer script returns structured data (as JSON to stdout or via Python data structures), and Claude Code is responsible for generating all report files.

The analyzer generates structured data containing full analysis results. Claude Code reads this data and generates three report formats:

#### 1. JSON Report (`test-structure-report.json`)

**Generated by:** Claude Code at runtime based on analyzer output

Machine-readable format containing full analysis data. See Step 5 for structure.

**How to generate:**
- Read structured data from analyzer (returned as JSON to stdout)
- Write to JSON file with `indent=2` for readability

#### 2. Text Summary (`test-structure-summary.txt`)

**Generated by:** Claude Code at runtime based on analyzer output

Terminal-friendly summary showing:
- Overall statistics (files with/without tests, function coverage)
- High-priority gaps
- Recommendations

**Format Structure:**
```text
============================================================
Test Structure Analysis
============================================================

File: {filename}
Language: {language}
Analysis Date: {timestamp}

============================================================
Coverage Summary
============================================================

Total Source Files:    {count}
Files With Tests:      {count} ({percentage}%)
Files Without Tests:   {count} ({percentage}%)

Total Functions:       {count}
Tested Functions:      {count} ({percentage}%)
Untested Functions:    {count} ({percentage}%)

============================================================
High Priority Gaps
============================================================

UNTESTED FILES:
  1. {filepath} - {reason} ({function_count} functions, {exported_count} exported)
  ...

UNTESTED FUNCTIONS:
  1. {filepath}::{function} - {reason} (visibility: {visibility})
  ...

============================================================
Recommendations
============================================================

Current Coverage: {current}%
Target Coverage: {target}%

Focus on addressing HIGH priority gaps first to maximize
test coverage and ensure production readiness.
```

#### 3. HTML Report (`test-structure-report.html`)

**Generated by:** Claude Code at runtime based on analyzer output

Interactive HTML report with:

**Required Sections:**

1. **Header** with project info, language, and generation timestamp
2. **Summary Dashboard** with score cards showing:
   - Total source files and files with/without tests
   - Function coverage percentage
   - High-priority gap count
3. **Untested Files Table** with columns:
   - File path
   - Function count
   - Exported function count
   - Priority (high/medium/low)
4. **Untested Functions Table** with columns:
   - File path
   - Function name
   - Visibility (exported/private)
   - Complexity score
   - Priority
5. **Recommendations Section** grouped by priority

**Styling:**
- Use the same CSS as gaps skill (modern gradient, cards, tables)
- Priority badges: high (red), medium (orange), low (blue)
- Escape all content with `html.escape()`

## Implementation Steps

When implementing this skill in a command:

### Step 0: Generate Analyzer Script at Runtime

**CRITICAL:** Before running any analysis, generate the analyzer script from the reference implementation.

```bash
# Create output directory
mkdir -p .work/test-coverage/analyze/

# Generate the analyzer script from the specification below
# Claude Code will write test_structure_analyzer.py based on the Analyzer Specification section
```

**Analyzer Specification:**

Generate a Python script (`test_structure_analyzer.py`) that analyzes Go test structure without running tests:

**Input:** Path or URL to a Go test file or directory
**Output:** Structured JSON data printed to stdout, plus optional text summary to stderr

**Core Algorithm:**

0. **Input Processing** (handle URLs and local paths):
   - Check if input starts with `http://` or `https://`
   - If URL: Use `urllib.request.urlopen()` to fetch content, save to temp file
   - If local path: Use directly
   - After analysis: Clean up temp file if created
   - Note: Directory URLs not supported, only single file URLs

1. **File Discovery**:
   - Test files: `*_test.go` (exclude vendor, generated code)
   - E2E tests: Files in `test/e2e/`, `test/integration/`, or containing `[Serial]`, `[Disruptive]` markers
   - Source files: `*.go` (exclude `*_test.go`, vendor)

2. **Test Parsing** (regex-based):
   - Ginkgo: `(?:g\.|o\.)?It\(\s*["']([^"']+)["']` → extract test name, line number
   - Standard Go: `func (Test\w+)\(t \*testing\.T\)` → extract test function name
   - Extract targets (functions called): regex for `\w+\([^)]*\)` inside test body

3. **Source File Analysis**:
   - Parse function definitions: `func (\w+)\(` or `func \(\w+ \*?\w+\) (\w+)\(`
   - Track exported vs unexported (capitalized vs lowercase first letter)

4. **Test-to-Source Mapping**:
   - Convention: `handler_test.go` → `handler.go`
   - Function-level: Match test names to source function names (e.g., `TestHandleRequest` → `HandleRequest`)
   - Import analysis: Parse `import` statements in test files

5. **Single File Mode** (when input is a file, not directory):
   - Analyze only the test file structure
   - Extract: test count, test names, imports, line numbers
   - Skip source file mapping and gap detection
   - Output: Test structure analysis only

6. **Output Format** (JSON to stdout):
```json
{
  "language": "go",
  "source_dir": "/path/to/src",
  "test_only_mode": false,
  "summary": {
    "total_source_files": 45,
    "total_test_files": 32,
    "untested_files_count": 8
  },
  "test_file_details": {
    "path": "/path/to/test.go",
    "test_count": 15,
    "tests": [
      {"name": "TestFoo", "line_start": 10, "line_end": 20, "targets": ["Foo", "Bar"]}
    ],
    "imports": ["testing", "github.com/onsi/ginkgo"]
  }
}
```

**Command-line Interface:**
```
python3 .work/test-coverage/analyze/test_structure_analyzer.py <source-path> [--test-structure-only] [--output <dir>]
```

**Why Runtime Generation:**
- Claude Code generates the analyzer from this specification
- No separate `.py` file to maintain
- SKILL.md is the single source of truth
- Simpler and more maintainable

### Step 1: Validate Inputs

Check that source directory exists and detect language if not specified.

### Step 2: Execute Test Structure Analyzer

```bash
# Run analyzer (outputs structured JSON to stdout)
python3 .work/test-coverage/analyze/test_structure_analyzer.py \
    <source-directory> \
    --priority <priority> \
    --output-json
```

The analyzer will output structured JSON to stdout containing:
- Test file analysis
- Source file analysis
- Test-to-source mappings
- Coverage gaps
- Summary statistics

### Step 3: Generate All Three Report Formats at Runtime

**IMPORTANT:** Claude Code generates all three report formats based on the analyzer's structured output.

#### 3.1: Capture and Parse Analyzer Output

```python
import json
import subprocess

# Run analyzer and capture JSON output
result = subprocess.run(
    ['python3', '.work/test-coverage/analyze/test_structure_analyzer.py', source_dir, '--output-json'],
    capture_output=True,
    text=True
)

# Parse structured data
analysis_data = json.loads(result.stdout)
```

#### 3.2: Generate JSON Report

```python
json_path = '.work/test-coverage/analyze/test-structure-report.json'
with open(json_path, 'w') as f:
    json.dump(analysis_data, f, indent=2)
```

#### 3.3: Generate Text Summary Report

Follow the text format specification in Step 6 to generate a terminal-friendly summary.

```python
text_path = '.work/test-coverage/analyze/test-structure-summary.txt'
# Generate text content following format in Step 6
with open(text_path, 'w') as f:
    f.write(text_content)
```

#### 3.4: Generate HTML Report

Follow the HTML specification in Step 6 to generate an interactive report.

```python
html_path = '.work/test-coverage/analyze/test-structure-report.html'
# Generate HTML content following specification in Step 6
with open(html_path, 'w') as f:
    f.write(html_content)
```

### Step 4: Display Results

Show summary and report locations to user:

```
Test Structure Analysis Complete

Reports Generated:
  ✓ HTML:  .work/test-coverage/analyze/test-structure-report.html
  ✓ JSON:  .work/test-coverage/analyze/test-structure-report.json
  ✓ Text:  .work/test-coverage/analyze/test-structure-summary.txt
```

## ⚠️ MANDATORY PRE-COMPLETION VALIDATION

**CRITICAL:** Before declaring this skill complete, you MUST execute ALL validation checks below. Failure to validate is considered incomplete execution.

### Validation Checklist

Execute these verification steps in order. ALL must pass:

#### 1. File Existence Check

```bash
# Verify all three reports exist
test -f .work/test-coverage/analyze/test-structure-report.html && echo "✓ HTML exists" || echo "✗ HTML MISSING"
test -f .work/test-coverage/analyze/test-structure-report.json && echo "✓ JSON exists" || echo "✗ JSON MISSING"
test -f .work/test-coverage/analyze/test-structure-summary.txt && echo "✓ Text exists" || echo "✗ Text MISSING"
```

**Required:** All three files must exist. If any are missing, regenerate them.

#### 2. Test Case Extraction Verification

```bash
# Verify test cases were extracted
python3 << 'EOF'
import json
try:
    with open('.work/test-coverage/analyze/test-structure-report.json', 'r') as f:
        data = json.load(f)

    test_count = data.get('summary', {}).get('test_cases_count', 0)

    if test_count > 0:
        print(f"✓ Test cases extracted: {test_count}")
    else:
        print("✗ NO TEST CASES FOUND - verify test file contains Ginkgo tests")
        exit(1)
except Exception as e:
    print(f"✗ ERROR: {e}")
    exit(1)
EOF
```

**Required:** Test cases must be extracted. Zero test cases indicates a parsing issue.

#### 3. HTML Report Structure Verification

```bash
# Verify HTML has required sections
grep -q "<h2>Test Cases" .work/test-coverage/analyze/test-structure-report.html && \
  echo "✓ Test Cases section present" || \
  echo "✗ MISSING: Test Cases section"

grep -q "<h2>Coverage Summary" .work/test-coverage/analyze/test-structure-report.html && \
  echo "✓ Coverage Summary section present" || \
  echo "✗ MISSING: Coverage Summary section"
```

**Required:** HTML must have all structural sections.

#### 4. JSON Structure Verification

```python
# Verify JSON has all required fields
python3 << 'EOF'
import json
try:
    with open('.work/test-coverage/analyze/test-structure-report.json', 'r') as f:
        data = json.load(f)

    required_fields = [
        ('summary.language', lambda d: d['summary']['language']),
        ('summary.test_cases_count', lambda d: d['summary']['test_cases_count']),
        ('test_cases', lambda d: d['test_cases']),
    ]

    missing = []
    for name, getter in required_fields:
        try:
            getter(data)
            print(f"✓ {name}")
        except (KeyError, TypeError):
            print(f"✗ MISSING: {name}")
            missing.append(name)

    if not missing:
        print("\n✓ All required JSON fields present")
    else:
        print(f"\n✗ INCOMPLETE: Missing {len(missing)} required fields")
        exit(1)
except Exception as e:
    print(f"✗ ERROR: {e}")
    exit(1)
EOF
```

**Required:** All required JSON fields must be present.

### Validation Summary

**Before declaring this skill complete:**

1. ✓ All three report files exist
2. ✓ Test cases successfully extracted (count > 0)
3. ✓ HTML has all required sections
4. ✓ JSON contains all required fields

**If ANY check fails:** Fix the issue and re-run all validation checks. Do NOT declare the skill complete until ALL checks pass.

## Error Handling

### Common Issues and Solutions

1. **Unable to parse test/source files**:
   - Use fallback regex-based parsing
   - Log warnings for unparseable files
   - Continue with partial analysis

2. **No test files found**:
   - Check if test patterns are correct for the Go project
   - Ensure test files follow `*_test.go` naming convention

3. **Complex project structures**:
   - Allow excluding certain directories via `--exclude`

## Examples

### Example 1: Go Project - Basic Analysis

```bash
# Analyze test structure for Go project
python3 .work/test-coverage/analyze/test_structure_analyzer.py /path/to/go/project

# Output:
# Language: go
# Discovered 45 source files, 32 test files
# Function coverage: 80.8% (189/234 functions tested)
# High priority gaps: 8 files without tests
```

### Example 2: Go Project with Filters

```bash
# Analyze only high-priority gaps
python3 .work/test-coverage/analyze/test_structure_analyzer.py /path/to/go/project \
    --priority high \
    --exclude "*/vendor/*" \
    --output reports/test-gaps/
```

### Example 3: Single Test File Analysis

```bash
# Analyze single test file structure
python3 .work/test-coverage/analyze/test_structure_analyzer.py ./test/e2e/networking/infw.go \
    --test-structure-only \
    --output ./reports/
```

## Integration with Claude Code Commands

This skill is used by:
- `/test-coverage:analyze <source-dir>`

The command invokes this skill to perform test structure analysis without running tests.

## See Also

- [Test Coverage Plugin README](../../README.md) - User guide and installation
