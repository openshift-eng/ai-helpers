# Test Coverage Plugin

Analyze e2e/integration test code structure without running tests to identify coverage gaps. Quickly understand what code has e2e tests, what doesn't, and prioritize testing efforts.

## Overview

The `test-coverage` plugin provides tools for analyzing **e2e/integration test structure** and identifying coverage gaps in software projects. It helps QE or Dev teams:

- **Focus on E2E Tests**: By default, analyzes e2e/integration tests (not unit tests) to ensure real-world scenario coverage
- **Understand test structure**: Analyze e2e test organization without running tests
- **Identify coverage gaps**: Find files and functions without e2e tests
- **Prioritize testing efforts**: Focus on high-priority untested code paths
- **Track test coverage**: Monitor e2e test structure across releases
- **Fast feedback**: Get insights in seconds without test execution

## Installation

### From Marketplace

```bash
# Add the ai-helpers marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install the test-coverage plugin
/plugin install test-coverage@ai-helpers

# Verify installation
/test-coverage:analyze --help
```

### Manual Installation

```bash
# Clone the repository
git clone git@github.com:openshift-eng/ai-helpers.git
cd ai-helpers/plugins/test-coverage

# Link to Claude Code
ln -s $(pwd) ~/.claude/plugins/test-coverage
```

## Commands

### 1. `/test-coverage:analyze` - Analyze E2E Test Structure

Analyze e2e/integration test code structure **without running tests** to identify coverage gaps.

**Usage:**
```bash
/test-coverage:analyze <source-directory> [options]
```

**Key Features:**
- **E2E Test Focus**: Analyzes e2e/integration tests by default (excludes unit tests)
- Works without running tests
- Supports Go projects
- Identifies files and functions without e2e tests
- Prioritizes gaps (high/medium/low)
- Fast analysis (seconds, not minutes)
- Use `--include-unit-tests` to also analyze unit tests

**Example:**
```bash
# Basic analysis - e2e tests only
/test-coverage:analyze ./pkg/

# Show only high-priority e2e test gaps
/test-coverage:analyze ./pkg/ --priority high

# Include unit tests in analysis (not just e2e)
/test-coverage:analyze ./pkg/ --include-unit-tests

# With filters
/test-coverage:analyze ./pkg/ --exclude "vendor/*" --exclude "*/generated/*"

# Custom output directory
/test-coverage:analyze ./pkg/ --output reports/test-gaps/
```

**Output:**
- `.work/test-coverage/analyze/test-structure-gaps.json` - JSON gap data for automation
- `.work/test-coverage/analyze/test-structure-summary.txt` - Text summary

---

### 2. `/test-coverage:gaps` - Identify E2E Test Scenario Gaps

Intelligent analysis to identify missing test coverage in OpenShift/Kubernetes test files. **Component-agnostic** - works for any OpenShift/K8s component (networking, storage, ETCD, Kube API, operators, etc.).

**Usage:**
```bash
/test-coverage:gaps <test-file> [options]
```

**Key Features:**
- **OpenShift/Kubernetes-specific** gap analysis
- **Component-agnostic** - works for any OpenShift/K8s component:
  - Networking (ingress, egress, SDN, OVN)
  - Storage (volumes, storage classes, CSI)
  - Kube API, ETCD, Auth/RBAC
  - Operators, controllers, and more
- **Always analyzes**:
  - **Platform coverage**: AWS, Azure, GCP, vSphere, Bare Metal, etc.
  - **Scenario coverage**: Error handling, upgrades, security, scale, performance
- Automatically detects component type for informational purposes
- Assigns priority levels (high, medium, low) based on production importance
- Provides actionable test recommendations
- Generates comprehensive gap reports (HTML, JSON, Text)

**Examples:**
```bash
# Analyze any OpenShift/K8s test file
/test-coverage:gaps ./test/extended/networking/egressip_test.go

# Analyze storage component tests
/test-coverage:gaps ./test/e2e/storage/csi_volumes.go

# Analyze Kube API tests
/test-coverage:gaps ./test/e2e/kube-api/api_server_test.go

# Filter by priority
/test-coverage:gaps ./test/e2e/etcd/backup_test.go --priority high

# Analyze remote test file
/test-coverage:gaps https://github.com/openshift/origin/blob/master/test/extended/storage/volume.go

# Custom output directory
/test-coverage:gaps ./test/e2e/operator_test.go --output ./reports/gaps/
```

**Output:**
- `.work/test-coverage/gaps/test-gaps-report.html` - Interactive gap analysis report
- `.work/test-coverage/gaps/test-gaps.json` - JSON gap data
- `.work/test-coverage/gaps/test-gaps-summary.txt` - Prioritized gap summary

**Priority Levels:**
- **High**: Major cloud providers, core component features, error handling, operator upgrades
- **Medium**: Secondary platforms, RBAC, scale, performance tests
- **Low**: Edge case scenarios

---

## E2E Test Detection

The plugin uses multiple heuristics to identify e2e/integration tests and exclude unit tests:

### File Naming Patterns
- `*e2e*_test.go`, `*integration*_test.go`

### Directory Location
E2E tests are typically located in:
- `test/e2e/`, `test/integration/`
- `e2e/`, `integration/`
- `tests/e2e/`, `tests/integration/`

Unit test directories are excluded:
- `test/unit/`, `unit/`, `tests/unit/`

### Test Markers and Annotations
The plugin also detects e2e tests by examining file content for Ginkgo test patterns:
- Ginkgo-style markers (e.g., `[Serial]`, `[Disruptive]`, `[Feature:...]`, `[Suite:...]`, etc.)
- Ginkgo BDD functions: `g.Describe(`, `g.Context(`, `g.It(`

**Note:** To include unit tests in the analysis, use the `--include-unit-tests` flag.

---

## Supported Languages

**Currently supports Go projects only.**

| Language | E2E Test Patterns | All Test Patterns | Description |
|----------|------------------|-------------------|-------------|
| Go | `*e2e*_test.go`, `*integration*_test.go` | `*_test.go` | Go test files with e2e/integration focus |

## Common Workflows

### Workflow 1: Quick Gap Assessment

```bash
# Step 1: Analyze test structure
/test-coverage:analyze ./pkg/

# Step 2: Focus on high-priority gaps
/test-coverage:analyze ./pkg/ --priority high

# Step 3: Analyze specific test file for scenario gaps
/test-coverage:gaps ./test/e2e/networking/infw.go --priority high
```

### Workflow 2: Analysis with Filters

```bash
# Analyze with exclusions
/test-coverage:analyze ./pkg/ --exclude "vendor/*" --exclude "*/generated/*"

# Analyze specific priority
/test-coverage:analyze ./pkg/ --priority high

# Custom output location
/test-coverage:analyze ./pkg/ --output ./reports/coverage/
```

### Workflow 3: Code Review Integration

```bash
# Before code review: Check test structure for changes
/test-coverage:analyze ./pkg/utils/ --priority high

# Identify what needs tests before merging
/test-coverage:analyze ./pkg/utils/ --output /tmp/review-gaps/

# Review JSON output for CI/CD integration
cat /tmp/review-gaps/test-structure-gaps.json
```

## Prerequisites

### Required

- **Python 3.8+**
- **Go toolchain** (for target Go projects)

### Optional (for enhanced analysis)

- **Go complexity tools**:
  ```bash
  go install golang.org/x/tools/cmd/gocyclo@latest
  go install github.com/fzipp/gocyclo/cmd/gocyclo@latest
  ```

## Best Practices

### 1. Run Analysis Early and Often
Run test structure analysis during development, not just before release. It's fast and doesn't require running tests.

### 2. Focus on High-Priority Gaps First
Use `--priority high` to focus on critical gaps:
```bash
/test-coverage:analyze ./pkg/ --priority high
```

Priority levels:
- **High**: Files without tests, untested public APIs
- **Medium**: Partially tested files
- **Low**: Private functions with some test coverage

### 3. Use Filters to Exclude Non-Critical Code
Exclude generated code, vendor dependencies, and build artifacts:
```bash
/test-coverage:analyze ./pkg/ --exclude "vendor/*" --exclude "*/generated/*" --exclude "*/mocks/*"
```

### 4. Integrate with Code Review
Check test structure before merging PRs. Use JSON output for automation:
```bash
/test-coverage:analyze ./pkg/ --output /tmp/gaps/
# Parse /tmp/gaps/test-structure-gaps.json in CI/CD
```

### 5. Analyze Test Scenarios
Test structure analysis shows what code has tests. Use the gaps command to analyze test scenarios:
```bash
/test-coverage:gaps ./test/e2e/networking/infw.go --priority high
```

### 6. Regular Gap Reviews
Schedule weekly "gap review" sessions to address untested code identified by the analyzer.

## Troubleshooting

### Issue: Non-Go files being analyzed

**Solution:**
The plugin is designed for Go projects. Use `--exclude` to filter out non-Go files:
```bash
/test-coverage:analyze ./pkg/ --exclude "*.py" --exclude "*.js"
```

### Issue: No gaps found but code is clearly untested

**Solution:**
Check that you're pointing to source directory (not test directory):
```bash
# Wrong: pointing to test directory
/test-coverage:analyze ./test/

# Right: pointing to source directory
/test-coverage:analyze ./pkg/
```

### Issue: Analysis includes generated/vendor code

**Solution:**
Use `--exclude` to filter out unwanted files:
```bash
/test-coverage:analyze ./pkg/ --exclude "vendor/*" --exclude "*/generated/*"
```

### Issue: Missing Python

**Solution:**
Ensure Python 3.8+ is installed:
```bash
python3 --version
# If not installed: sudo apt install python3  # Ubuntu/Debian
```

### Issue: Custom test patterns not recognized

**Solution:**
Use `--test-pattern` to specify custom patterns:
```bash
/test-coverage:analyze ./src/ --test-pattern "**/*Spec.java,**/IT*.java"
```

## Contributing

Contributions are welcome! Please see the main repository's contributing guidelines.

## Support

- **Issues**: https://github.com/openshift-eng/ai-helpers/issues
- **Documentation**: https://github.com/openshift-eng/ai-helpers
- **Examples**: See `examples/` directory in the repository

## License

See the main repository for license information.

## Related Plugins

- **`jira`**: Create bug reports with coverage gap context
- **`ci`**: Integrate with OpenShift CI for coverage tracking
- **`git`**: Analyze coverage impact of commits and PRs
- **`utils`**: Generate test plans based on coverage gaps

## Version History

- **v0.0.1** (2025-11-05): Initial release
  - `/test-coverage:analyze` - Analyze test structure without running tests
  - `/test-coverage:gaps` - Identify untested code paths
