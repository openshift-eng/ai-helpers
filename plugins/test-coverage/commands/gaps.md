---
description: Identify E2E test scenario gaps in OpenShift/Kubernetes tests (component-agnostic)
argument-hint: <test-file-or-url> [--output <path>]
---

## Name
test-coverage:gaps

## Synopsis
```bash
/test-coverage:gaps <test-file-or-url> [--output <path>]
```

## Description

The `test-coverage:gaps` command **intelligently analyzes OpenShift/Kubernetes test files to identify missing test coverage**. It is **component-agnostic** and works for any OpenShift/K8s component (networking, storage, ETCD, Kube API, operators, etc.). **This command always generates three report formats: HTML (interactive), JSON (machine-readable), and Text (terminal-friendly).**

**Component-Agnostic Analysis** (works for all OpenShift/K8s components):
- **Platform Coverage**: Which platforms (AWS, Azure, GCP, vSphere, Bare Metal, etc.) lack tests
- **Scenario Coverage**: Missing error handling, upgrade, security/RBAC, scale, performance tests
- **Priority-based recommendations**: Focus on high-impact gaps first
- **Component detection**: Automatically detects component type (networking, storage, kube-api, etcd, etc.) for informational purposes

**Supported Components:**
- Networking (ingress, egress, SDN, OVN, network policies)
- Storage (volumes, storage classes, CSI, PV/PVC)
- Kube API, ETCD
- Auth/RBAC, OAuth
- Operators, controllers
- Observability, monitoring
- Image registry, builds
- Any other OpenShift/K8s component

**Language Support:** This command currently supports Go projects only.

This command helps OpenShift/Kubernetes QE or Dev teams focus testing efforts on the most critical untested scenarios.

## Arguments

- `$1` (test-file-or-url): Path or URL to OpenShift/Kubernetes test file
  - **Local path**: `./test/extended/networking/ingress.go`, `/path/to/storage_test.go`
  - **GitHub URL**: `https://github.com/openshift/origin/blob/master/test/extended/storage/volume.go`
  - **URL**: Any HTTP(S) URL to a test file
  - URLs are automatically downloaded and cached in `.work/test-coverage/cache/`

### Optional Arguments

- `--output <path>`: Output directory for gap analysis reports (default: `.work/test-coverage/gaps/`)

## Implementation

### Step 1: Resolve Test File Input

1. **Resolve test file path or URL**:
   - If input is a URL:
     - Download test file to `.work/test-coverage/cache/`
     - Use cached version if already downloaded
   - If input is a local path:
     - Convert to absolute path and validate existence
     - Verify file is a Go test file (contains `g.It`, `g.Describe`, or `Test` functions)

### Step 2: Detect Component Type and Parse Test File

1. **Detect component type** from file path and content:
   - **Networking**: `/networking/`, network policy, ingress, egress patterns
   - **Storage**: `/storage/`, volume, PV, PVC, storage class patterns
   - **KAPI**: `/kapi/`, `/api/`, apiserver patterns
   - **Auth**: `/auth/`, RBAC, OAuth patterns
   - **Generic**: Fallback for unrecognized components

2. **Extract test cases** using regex patterns:
   - Ginkgo tests: `g.It(`, `g.Describe(`, `g.Context(`
   - Standard Go tests: `func Test*`
   - Extract test metadata from names (priority, bug IDs, tags)

3. **Analyze component-specific coverage**:
   - **For Networking**: Protocols, service types, IP stacks
   - **For Storage**: Storage classes, volume modes, provisioners
   - **For All Components**: Platforms, scenarios

4. **Build coverage matrices**:
   - Track component-specific dimensions
   - Track platform coverage
   - Track scenario coverage (error handling, upgrades, RBAC, scale)

### Step 3: Identify Component-Aware Gaps

1. **Compare tested vs. expected**:
   - For each component-specific dimension, identify what's not tested
   - Categorize gaps by priority based on production importance

2. **Calculate priority scores** (component-specific):
   - **High Priority**:
     - Major cloud providers (AWS, Azure, GCP)
     - Core component features (protocols for networking, storage classes for storage)
     - Error handling scenarios
     - Operator upgrades
   - **Medium Priority**:
     - Secondary platforms (Bare Metal, OpenStack)
     - RBAC, scale, performance scenarios
   - **Low Priority**:
     - Edge case scenarios

3. **Generate component-aware recommendations**:
   - For each gap, provide specific test recommendation
   - Estimate impact of gap
   - Suggest test case to fill gap

### Step 4: Generate Reports

**Execute:** `python3 skills/gaps/gap_analyzer.py <test-file> --output <output-dir>`

Generate all three report formats:

1. **HTML Report** (`test-gaps-report.html`):
   - Coverage scores dashboard
   - What's tested vs. not tested matrices
   - Priority-sorted gap list with recommendations
   - Visual charts for protocol/platform coverage

2. **JSON Report** (`test-gaps.json`):
   - Test case metadata
   - Coverage matrices
   - Gap list with priorities
   - Machine-readable for CI/CD

3. **Text Summary** (`test-gaps-summary.txt`):
   - Coverage percentages
   - High priority gaps
   - Recommendations
   - Terminal-friendly format

## Return Value

- **Format**: Terminal output with summary + generated report files

**Terminal Output (Networking Component Example):**
```text
Detected component: networking

Test Coverage Gap Analysis Complete

Summary:
  Test Cases:        15
  Overall Coverage:  20.8%

Coverage Scores:
  Protocol Coverage:     0.0%
  Platform Coverage:     83.3%
  Service Type:          0.0%
  Scenario Coverage:     0.0%

High Priority Gaps (5):
  1. TCP - Most common protocol not tested
  2. UDP - Common protocol for DNS, streaming not tested
  3. LoadBalancer - External traffic not tested
  4. Error handling - Invalid configs not validated
  5. Operator upgrades - Upgrade path not tested

Reports Generated:
  ✓ HTML:  .work/test-coverage/gaps/test-gaps-report.html
  ✓ JSON:  .work/test-coverage/gaps/test-gaps.json
  ✓ Text:  .work/test-coverage/gaps/test-gaps-summary.txt

Recommendation:
  Add 5-7 test cases to address high-priority gaps
  Target: Improve coverage from 21% to 41%
```

**Terminal Output (Storage Component Example):**
```text
Detected component: storage

Test Coverage Gap Analysis Complete

Summary:
  Test Cases:        12
  Overall Coverage:  35.0%

Coverage Scores:
  Storage Class Coverage:     33.3%
  Volume Mode Coverage:       66.7%
  Platform Coverage:          50.0%
  Scenario Coverage:          20.0%

High Priority Gaps (4):
  1. gp2/gp3 - AWS EBS storage not tested
  2. CSI - CSI drivers not tested
  3. ReadWriteOnce - Single-node write access not tested
  4. Error handling - Invalid configs not validated
```

**Exit Status:**
- 0: Analysis successful
- 1: Analysis failed (parsing error, missing file)

## Examples

### Example 1: Analyze networking test file

```bash
/test-coverage:gaps ./test/extended/networking/egressip_udn.go
```

Detects networking component and analyzes protocol coverage (TCP, UDP, SCTP), service types, and scenarios.

**Output:** Component: networking, 20.8% overall coverage, identifies gaps in TCP/UDP protocols, LoadBalancer service type, error handling, operator upgrades.

### Example 2: Analyze storage test file

```bash
/test-coverage:gaps ./test/e2e/storage/csi.go
```

Detects storage component and analyzes storage class coverage, volume modes, and provisioners.

**Output:** Component: storage, identifies gaps in gp2/gp3 storage classes, ReadWriteMany volume mode, CSI drivers.

### Example 3: Analyze remote test file

```bash
/test-coverage:gaps https://github.com/openshift/origin/blob/master/test/extended/storage/volume.go
```

Downloads test file from GitHub and analyzes component-specific coverage gaps.

### Example 5: Custom output directory

```bash
/test-coverage:gaps ./test/e2e/auth/rbac.go --output ./reports/e2e-gaps/
```

Generates component-aware gap reports in custom directory.

## Prerequisites

**General Requirements**:
- Python 3.8+
- Access to test files
- Go test files (Ginkgo or standard Go tests)

### Checking Prerequisites

The command will check for required tools and suggest installation if missing.

## Notes

### General

- **Test Scenario Analysis**: This command identifies missing test scenarios, platforms, and protocols in your e2e test suite
- **CRITICAL**: This command MUST always generate all three report formats (HTML, JSON, and Text). Failing to generate any report format should be treated as a command failure.
- **URL Support:** Test files can be URLs
  - Supports GitHub, GitLab, and any HTTP(S) URLs
  - Downloaded files are cached in `.work/test-coverage/cache/`
  - GitHub blob URLs are automatically converted to raw URLs
  - Clear cache with `rm -rf .work/test-coverage/cache/` to force re-download

### Component-Aware Gap Analysis Notes

- **Context-Aware Analysis**: The tool automatically detects component type and provides relevant recommendations
- **Component Types Supported**:
  - **Networking**: Analyzes protocols, service types, IP stacks
  - **Storage**: Analyzes storage classes, volume modes, provisioners
  - **Generic**: Analyzes platforms and scenarios for unrecognized components
- **Focus on Production Readiness**: Gaps highlight missing scenarios that could impact production deployments
- **Platform Coverage Critical**: Missing tests for major cloud providers (AWS, Azure, GCP) are production blockers
- **Component-Specific Coverage**: Each component type has specific dimensions analyzed (protocols for networking, storage classes for storage, etc.)
- **Scenario Coverage**: Error handling, upgrades, RBAC, and scale tests are often overlooked but critical
- **Coverage Scores**: Overall coverage below 50% indicates significant e2e testing gaps
- Re-run after adding test cases to track improvement in component-specific coverage

### Report Format Notes

- The HTML report provides the best interactive experience with expandable details, sortable tables, and visual charts
- The JSON report is ideal for CI/CD integration and automated issue creation
- The Text report is useful for email summaries and terminal display
- JSON output can be integrated with issue tracking systems to create testing tasks
- Re-run this command after adding tests to measure progress

## See Also

- `/test-coverage:analyze` - Analyze test structure and organization
