# Test Scenario Gap Analysis Skill

Identify missing test scenarios, platforms, protocols, and coverage gaps in e2e tests.

## Usage

This skill is invoked via the `/test-coverage:gaps` command:

```bash
/test-coverage:gaps <test-file-path>
```

## What It Does

- Detects component type automatically
- Analyzes platform coverage (AWS, Azure, GCP, etc.)
- Checks protocol coverage (TCP, UDP, SCTP)
- Identifies scenario gaps (error handling, upgrades, RBAC)
- Assigns priority to gaps (high/medium/low)
- Generates HTML, JSON, and text reports

## Output

All reports are generated in `.work/test-coverage/gaps/`:
- `test-gaps-report.html` - Interactive, filterable report
- `test-gaps-report.json` - Machine-readable gap data
- `test-gaps-summary.txt` - Terminal-friendly summary

See [SKILL.md](SKILL.md) for detailed implementation guide.
