# Test Scenario Gap Analysis

Analyze e2e test files to identify missing test scenarios, platforms, protocols, and service types.

## Quick Start

```bash
# Analyze single test file
python3 gap_analyzer.py /path/to/test_file.go

# With custom output
python3 gap_analyzer.py /path/to/test_file.go --output ./reports/
```

## Features

- **Platform Gap Detection**: Identifies missing cloud provider tests (AWS, Azure, GCP, etc.)
- **Protocol Coverage**: Detects untested network protocols (TCP, UDP, ICMP, SCTP, etc.)
- **Service Type Coverage**: Finds gaps in Kubernetes service types (NodePort, LoadBalancer, ClusterIP)
- **Scenario Coverage**: Identifies missing test scenarios (error handling, upgrades, RBAC, scale)
- **Priority-Based**: Assigns high/medium/low priority to gaps based on production importance

## Output

The analyzer generates two report formats:
- **JSON Report** (`test-gaps-report.json`) - Machine-readable gap data
- **Text Summary** (`test-gaps-summary.txt`) - Terminal-friendly summary

Claude Code generates the HTML report at runtime based on the JSON data and SKILL.md specifications.

See [SKILL.md](SKILL.md) for detailed implementation guide.

## Usage

```bash
python3 gap_analyzer.py <test-file> [--output <dir>]
```

**Note:** The `<test-file>` argument must be a local file path. URL support (e.g., GitHub URLs) is not currently implemented.

## Language Support

Currently supports Go test files only:
- Ginkgo BDD tests (`g.It`, `g.Describe`)
- Standard Go tests

## Requirements

- Python 3.8+ (standard library only)

See [SKILL.md](SKILL.md) for detailed prerequisites.

## Examples

### Basic Analysis
```bash
python3 gap_analyzer.py ./test/extended/networking/infw.go
```

### Custom Output Directory
```bash
python3 gap_analyzer.py ./test/e2e/storage/csi.go --output ./gap-reports/
```

## See Also

- [Test Coverage Plugin README](../../README.md) - User guide and command usage
- [SKILL.md](SKILL.md) - Detailed implementation guide for AI agents
