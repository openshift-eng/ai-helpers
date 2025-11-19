# Test Structure Analysis Skill

This skill provides test structure analysis capabilities for Go projects **without running tests**.

## Features

- **Test Structure Analysis**: Analyzes test code directly without running tests
- **Go Support**: Supports Go test files and source files
- **E2E/Integration Focus**: Identifies e2e and integration tests
- **Gap Identification**: Finds files and functions without tests
- **Rich Reports**: Generates interactive HTML, JSON, and text reports
- **Priority-based**: Categorizes gaps by priority (high, medium, low)
- **Fast**: Analyzes code in seconds without test execution

## Usage

```bash
# Analyze test structure for a Go project
python3 test_structure_analyzer.py /path/to/project

# Analyze with custom output directory
python3 test_structure_analyzer.py /path/to/project --output reports/gaps/

# Analyze only high-priority gaps
python3 test_structure_analyzer.py /path/to/project --priority high

# Analyze single test file structure
python3 test_structure_analyzer.py ./test/e2e/networking/infw.go --test-structure-only
```

## Output

Generates three report formats:
- **HTML Report** (`test-coverage-report.html`) - Interactive web-based report
- **JSON Summary** (`test-structure-gaps.json`) - Machine-readable for CI/CD
- **Text Summary** (`test-structure-summary.txt`) - Terminal-friendly summary

See [SKILL.md](SKILL.md) for detailed output format documentation.

## Supported Language

| Language | Test Patterns | Description |
|----------|---------------|-------------|
| Go | `*_test.go` | Go test files (focuses on e2e/integration tests by default) |

## File Structure

```
analyze/
├── test_structure_analyzer.py  # Main test structure analyzer
├── test_structure_reports.py   # Report generators
├── test_gap_reports.py         # Gap report generators
├── SKILL.md                    # Detailed implementation guide
└── README.md                   # This file
```

## Dependencies

- Python 3.8+ (standard library only)
- Go toolchain (for target Go projects)

See [SKILL.md](SKILL.md) for detailed prerequisites and installation instructions.

## Examples

### Example 1: Basic Test Structure Analysis

```bash
# Analyze Go project test structure
python3 test_structure_analyzer.py /path/to/project --output .work/coverage/

# Output:
# Language: go
# Discovered 45 source files, 32 test files
# Function coverage: 80.8% (189/234 functions tested)
# High priority gaps: 8 files without tests
```

### Example 2: High Priority Gaps Only

```bash
# Analyze only high-priority gaps
python3 test_structure_analyzer.py /path/to/project --priority high
```

### Example 3: Single Test File Structure

```bash
# Analyze structure of a single test file
python3 test_structure_analyzer.py ./test/e2e/networking/infw.go --test-structure-only
```

## Output Example

```
================================================================================
Test Structure Analysis Complete
================================================================================

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
  JSON Report:    .work/test-coverage/analyze/test-structure-gaps.json
  Text Summary:   .work/test-coverage/analyze/test-structure-summary.txt

Recommendations:
  - Create test files for 15 untested source files
  - Add tests for 45 untested functions
  - Focus on high-priority gaps first
```

## See Also

- [Test Coverage Plugin README](../../README.md) - User guide and command usage
- [SKILL.md](SKILL.md) - Detailed implementation guide for AI agents
