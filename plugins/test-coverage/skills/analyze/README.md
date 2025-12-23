# Test Structure Analysis Skill

Analyze test code structure without running tests to identify coverage gaps.

## Usage

This skill is invoked via the `/test-coverage:analyze` command:

```bash
/test-coverage:analyze <test-file-or-directory>
```

## What It Does

- Analyzes test file structure (Go projects only)
- Identifies e2e and integration tests
- Finds files and functions without tests
- Generates HTML, JSON, and text reports

## Output

All reports are generated in `.work/test-coverage/analyze/`:
- `test-structure-report.html` - Interactive report
- `test-structure-report.json` - Machine-readable data
- `test-structure-summary.txt` - Terminal-friendly summary

See [SKILL.md](SKILL.md) for detailed implementation guide.
