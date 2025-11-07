---
name: Component-Aware Test Gap Analysis
description: Intelligently identify missing test coverage based on component type
---

# Component-Aware Test Gap Analysis Skill

This skill **automatically detects component type** (networking, storage, API, etc.) and provides **context-aware gap analysis**. It analyzes e2e test files to identify missing test coverage specific to the component being tested.

## When to Use This Skill

Use this skill when you need to:
- **Automatically detect component type** from test file path and content
- **Component-specific gap analysis**:
  - **Networking**: Identify missing protocol tests (TCP, UDP, SCTP), service type coverage, IP stack testing
  - **Storage**: Find gaps in storage class coverage, volume mode testing, provisioner tests
  - **Generic**: Analyze platform coverage and common scenarios for other components
- **Always analyze**: Cloud platform coverage (AWS, Azure, GCP, etc.) and scenario testing (error handling, upgrades, RBAC, scale)
- Prioritize testing efforts based on component-specific production importance
- Generate comprehensive component-aware gap analysis reports

## ⚠️ CRITICAL REQUIREMENT

**This skill MUST ALWAYS generate all three report formats (HTML, JSON, and Text) by executing the gap analyzer script.**

Do NOT perform manual gap analysis without running the script. The gap analyzer script (`skills/gaps/gap_analyzer.py`) is the authoritative source for gap analysis and must be executed in all cases.

**Required Actions:**
1. ✅ **Execute**: `python3 skills/gaps/gap_analyzer.py <test-file> --output <output-dir>`
2. ✅ **Verify**: All three reports are generated (HTML, JSON, Text)
3. ✅ **Display**: Show report locations and summary to the user

**Failure to generate reports** should be treated as a skill execution failure.

## Prerequisites

### Required Tools

- **Python 3.8+** for test structure analysis
- **Go toolchain** for the target project

### Installation

```bash
# Python dependencies (standard library only, no external packages required)
# Ensure Python 3.8+ is installed

# Optional Go analysis tools
go install golang.org/x/tools/cmd/guru@latest
go install golang.org/x/tools/cmd/goimports@latest
```

## How It Works

**Note: This skill currently supports E2E/integration test files for OpenShift/Kubernetes components written in Go (Ginkgo framework).**

### Current Implementation

The analyzer performs **single test file analysis** using regex-based pattern matching to identify coverage gaps. It does **not** perform repository traversal, Go AST parsing, or test-to-source mapping.

### Analysis Flow

#### Step 1: Component Type Detection

The analyzer automatically detects the component type from:

1. **File path patterns**:
   - `/networking/` → networking component
   - `/storage/` → storage component
   - `/kapi/`, `/api/` → kube-api component
   - `/etcd/` → etcd component
   - `/auth/`, `/rbac/` → auth component

2. **File content patterns**:
   - Keywords like `sig-networking`, `networkpolicy`, `egressip` → networking
   - Keywords like `sig-storage`, `persistentvolume` → storage
   - Keywords like `sig-api`, `apiserver` → kube-api

#### Step 2: Extract Test Cases

Parses the test file using regex to extract:

- **Test names** from Ginkgo `g.It("test name")` patterns
- **Line numbers** where tests are defined
- **Test tags** like `[Serial]`, `[Disruptive]`, `[NonPreRelease]`
- **Test IDs** from patterns like `-12345-` in test names

**Example:**
```go
g.It("egressip-12345-should work on AWS [Serial]", func() {
    // Test implementation
})
```

Extracted:
- Name: `egressip-12345-should work on AWS [Serial]`
- ID: `12345`
- Tags: `[Serial]`
- Line: 42

#### Step 3: Analyze Coverage Using Regex

For each component type, the analyzer searches the file content for specific keywords to determine what is tested:

**Networking components:**
- **Platforms**: `vsphere`, `AWS`, `azure`, `GCP`, `baremetal`
- **Protocols**: `TCP`, `UDP`, `SCTP`
- **Service types**: `NodePort`, `LoadBalancer`, `ClusterIP`
- **Scenarios**: `invalid`, `upgrade`, `concurrent`, `performance`, `rbac`

**Storage components:**
- **Platforms**: `vsphere`, `AWS`, `azure`, `GCP`, `baremetal`
- **Storage classes**: `gp2`, `gp3`, `csi`
- **Volume modes**: `ReadWriteOnce`, `ReadWriteMany`, `ReadOnlyMany`
- **Scenarios**: `invalid`, `upgrade`, `concurrent`, `performance`, `rbac`

**Other components:**
- **Platforms**: `vsphere`, `AWS`, `azure`, `GCP`, `baremetal`
- **Scenarios**: `invalid`, `upgrade`, `concurrent`, `performance`, `rbac`

#### Step 4: Identify Gaps

For each coverage dimension, if a keyword is **not found** in the file, it's flagged as a gap:

**Example:**
```python
# If file content doesn't contain "azure" (case-insensitive)
gaps.append({
    'platform': 'Azure',
    'priority': 'high',
    'impact': 'Major cloud provider - production blocker',
    'recommendation': 'Add Azure platform-specific tests'
})
```

#### Step 5: Calculate Component-Aware Coverage Scores

Scoring is component-specific to avoid penalizing components for irrelevant metrics:

**Networking components:**
- Overall = avg(platform_score, protocol_score, service_type_score, scenario_score)

**Storage components:**
- Overall = avg(platform_score, storage_class_score, volume_mode_score, scenario_score)

**Other components:**
- Overall = avg(platform_score, scenario_score)

Each dimension score = (items_found / total_items) × 100

### Limitations

The current implementation has the following limitations:

❌ **No repository traversal** - Analyzes only the single test file provided as input
❌ **No Go AST parsing** - Uses regex pattern matching instead of parsing Go syntax trees
❌ **No test-to-source mapping** - Cannot map test functions to source code functions
❌ **No function-level coverage** - Cannot determine which source functions are tested
❌ **No project-wide analysis** - Cannot analyze multiple test files or aggregate results
❌ **Keyword-based detection only** - Gap detection relies on keyword presence in test file
❌ **Single file focus** - Reports cover only the analyzed test file, not the entire codebase

These limitations mean the analyzer provides **scenario and platform coverage analysis** for a single E2E test file, not structural code coverage across a codebase.

#### Step 6: Generate Reports

The analyzer generates three report formats:

#### 1. HTML Gap Report (`test-gaps-report.html`)

Interactive HTML report with:
- **Component-aware coverage scores**: Overall, platform, protocol/storage, service type/volume mode, scenario coverage
- **Coverage matrices**: Visual tables showing what platforms/protocols/services are tested
- **Identified gaps**: Categorized by platform, protocol, service type, storage class, volume mode, and scenario
- **Priority indicators**: High/medium/low priority badges for each gap
- **Test cases list**: All test cases found in the file with tags and line numbers
- **Recommendations**: Prioritized list of gaps to address first

#### 2. JSON Report (`test-gaps.json`)

Machine-readable format for CI/CD integration:
```json
{
  "analysis": {
    "file": "test/e2e/networking/egressip_test.go",
    "component_type": "networking",
    "test_count": 15,
    "test_cases": [...],
    "coverage": {
      "platforms": {"tested": ["AWS", "GCP"], "not_tested": ["Azure", ...]},
      "protocols": {"tested": ["TCP"], "not_tested": ["UDP", "SCTP"]},
      ...
    },
    "gaps": {
      "platforms": [...],
      "protocols": [...],
      "scenarios": [...]
    }
  },
  "scores": {
    "overall": 45.0,
    "platform_coverage": 33.3,
    "protocol_coverage": 33.3,
    ...
  },
  "generated_at": "2025-11-10T10:00:00Z"
}
```

#### 3. Text Summary (`test-gaps-summary.txt`)

Terminal-friendly summary:
```text
Test Coverage Gap Analysis
════════════════════════════════════════════════════════════

File: test/e2e/networking/egressip_test.go
Component: networking
Test Cases: 15
Analysis Date: 2025-11-10 10:00:00

Coverage Scores
════════════════════════════════════════════════════════════

Overall Coverage:          45.0%
Platform Coverage:         33.3%
Protocol Coverage:         33.3%
Service Type Coverage:     66.7%
Scenario Coverage:         40.0%

Identified Gaps
════════════════════════════════════════════════════════════

PLATFORM GAPS:
  [HIGH] Azure
    Impact: Major cloud provider - production blocker
    Recommendation: Add Azure platform-specific tests

PROTOCOL GAPS:
  [HIGH] UDP
    Impact: Common protocol for DNS, streaming not tested
    Recommendation: Add UDP protocol tests

SCENARIO GAPS:
  [HIGH] Error Handling
    Impact: Invalid configs not validated
    Recommendation: Add negative test cases for invalid configurations
```

## Implementation Steps

When implementing this skill in a command:

### Step 0: Execute Gap Analyzer Script (MANDATORY)

**Before doing anything else, execute the gap analyzer script to generate all reports:**

```bash
# Create output directory
mkdir -p .work/test-coverage/gaps/

# Run gap analyzer
python3 skills/gaps/gap_analyzer.py <test-file-path> --output .work/test-coverage/gaps/

# Verify all three reports were generated
ls -lh .work/test-coverage/gaps/test-gaps-report.html
ls -lh .work/test-coverage/gaps/test-gaps.json
ls -lh .work/test-coverage/gaps/test-gaps-summary.txt
```

**IMPORTANT:** Do not skip this step. Do not attempt manual analysis. The script is the authoritative implementation.

### Step 1: Display Results

After the script completes, display the results to the user:

```python
# Read the generated summary
with open('.work/test-coverage/gaps/test-gaps-summary.txt', 'r') as f:
    summary = f.read()
    print(summary)

# Provide report locations
print("\nReports generated:")
print("  HTML: .work/test-coverage/gaps/test-gaps-report.html")
print("  JSON: .work/test-coverage/gaps/test-gaps.json")
print("  Text: .work/test-coverage/gaps/test-gaps-summary.txt")
```

### Step 2: Parse JSON Output (Optional)

For programmatic access to gap data:

```python
import json

with open('.work/test-coverage/gaps/test-gaps.json', 'r') as f:
    data = json.load(f)

# Access analysis results
component_type = data['analysis']['component_type']
test_count = data['analysis']['test_count']
overall_score = data['scores']['overall']

# Access gaps
platform_gaps = data['analysis']['gaps']['platforms']
protocol_gaps = data['analysis']['gaps'].get('protocols', [])
scenario_gaps = data['analysis']['gaps']['scenarios']

# Filter high-priority gaps
high_priority_gaps = [
    gap for category in data['analysis']['gaps'].values()
    for gap in category if gap.get('priority') == 'high'
]
```

## Error Handling

### Common Issues and Solutions

1. **File not found**:
   - Verify the test file path is correct
   - Check that the file exists and is readable

2. **Invalid file format**:
   - Ensure the file is a Go test file (`.go`)
   - Check that the file uses Ginkgo framework (`g.It`, `g.Describe`)

3. **No test cases found**:
   - Verify the file contains Ginkgo test cases
   - Check for `g.It("...")` patterns

## Examples

### Example 1: Analyze Networking Test File

```bash
# Run gap analyzer on a networking test file
cd /home/anusaxen/git/ai-helpers/plugins/test-coverage
python3 skills/gaps/gap_analyzer.py \
  /path/to/test/extended/networking/egressip_test.go \
  --output .work/gaps/

# Output:
# Component detected: networking
# Test cases found: 25
# Overall coverage: 45.0%
# High-priority gaps: Azure platform, UDP protocol, Error handling scenarios
#
# Reports generated:
#   HTML: .work/gaps/test-gaps-report.html
#   JSON: .work/gaps/test-gaps.json
#   Text: .work/gaps/test-gaps-summary.txt
```

### Example 2: Analyze Storage Test File

```bash
# Run gap analyzer on a storage test file
python3 skills/gaps/gap_analyzer.py \
  /path/to/test/extended/storage/persistent_volumes_test.go \
  --output .work/gaps/

# Output:
# Component detected: storage
# Test cases found: 18
# Overall coverage: 52.0%
# High-priority gaps: ReadWriteMany volumes, CSI storage class, Snapshot scenarios
```

### Example 3: Analyze Local Test File

```bash
# Provide a local path to the test file
python3 skills/gaps/gap_analyzer.py \
  /path/to/local/test/extended/networking/egressip.go \
  --output .work/gaps/
```

**Note:** URL support (e.g., analyzing files directly from GitHub URLs) is not yet implemented. The script currently requires a local file path. URL resolution via PathHandler can be added in the future when gap_analyzer.py is updated to support it.

## Integration with Claude Code Commands

This skill is used by:
- `/test-coverage:gaps <test-file-or-url>` - Analyze E2E test scenario gaps

The command invokes this skill to perform component-aware gap analysis on the specified test file.

## See Also

- [Test Coverage Plugin README](../../README.md) - User guide and installation
- [gap_analyzer.py](gap_analyzer.py) - Analyzer implementation
