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

**This skill MUST ALWAYS generate all three report formats (HTML, JSON, and Text) at runtime.**

The gap analyzer script (generated at runtime to `.work/test-coverage/gaps/gap_analyzer.py`) performs the analysis and returns structured data. Claude Code is responsible for generating all three report formats based on this data.

**Required Actions:**
1. ✅ **Execute**: `python3 .work/test-coverage/gaps/gap_analyzer.py <test-file> --output-json` (outputs structured JSON to stdout)
2. ✅ **Generate**: Create all three report files (HTML, JSON, Text) at runtime
3. ✅ **Verify**: All three reports are generated successfully
4. ✅ **Display**: Show report locations and summary to the user

**Failure to generate any of the three report formats** should be treated as a skill execution failure.

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

The analyzer performs **single test file analysis** with two analysis layers:

1. **Generic Coverage Analysis** (keyword-based)
   - Platforms, protocols, IP stacks, service types
   - Uses regex pattern matching on file content

2. **Feature-Based Analysis** (runtime extraction)
   - Dynamically extracts features from test names
   - Infers missing features based on patterns
   - No hardcoded feature matrices - works for ANY component

It does **not** perform repository traversal, Go AST parsing, or test-to-source mapping.

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

#### Step 5a: Dynamic Feature Extraction (Runtime Analysis)

In addition to the keyword-based coverage analysis above, the analyzer performs **dynamic feature extraction** to identify component-specific features from test names at runtime, without any hardcoded feature matrices.

**How Runtime Feature Extraction Works:**

1. **Extract Features from Test Names**

   Parse test names to identify features being tested:

   **Example Test Name:**
   ```
   "Validate egressIP with mixed of multiple non-overlapping UDNs and default network(layer3/2 and IPv4 only)"
   ```

   **Extracted Features:**
   - ✓ Non-overlapping configuration
   - ✓ Multiple resource configuration
   - ✓ Mixed configuration
   - ✓ User Defined Networks (UDN)
   - ✓ Default network
   - ✓ Layer 3 networking

2. **Group Features into Categories**

   Features are automatically categorized:

   - **Configuration Patterns**: overlapping, non-overlapping, single, multiple, mixed
   - **Network Topology**: UDN, default network, layer2, layer3, gateway modes
   - **Lifecycle Operations**: creation, deletion, recreation, assignment
   - **Network Features**: failover, load balancing, isolation
   - **Resilience & Recovery**: reboot, restart, node deletion

3. **Infer Missing Features**

   Based on patterns, infer what's missing:

   - **Opposite patterns**: If "overlapping" tested → suggest "non-overlapping"
   - **Single vs Multiple**: If "single resource" tested → suggest "multiple resources"
   - **Completeness**: If "deletion" tested → suggest "recreation"
   - **Layer coverage**: If "layer2" tested → suggest "layer3"

**Benefits of Runtime Feature Extraction:**

✅ **No Hardcoding** - Works for ANY component without configuration
✅ **Intelligent Gap Detection** - Infers missing features based on patterns
✅ **Component-Agnostic** - Automatically adapts to any component type
✅ **Always Current** - Extracts from actual test names, not assumed features

**Example: EgressIP Test Analysis**

**Input (Test Names):**
```
1. Validate egressIP with mixed of multiple non-overlapping UDNs
2. Validate egressIP with mixed of multiple overlapping UDNs
3. Validate egressIP Failover with UDNs
4. egressIP after UDN deleted then recreated
5. egressIP after OVNK restarted
6. Traffic is load balanced between egress nodes
```

**Output (Extracted Features):**
```
Configuration Patterns:
  ✓ Non-overlapping configuration
  ✓ Overlapping configuration
  ✓ Multiple resource configuration
  ✓ Mixed configuration

Network Topology:
  ✓ User Defined Networks (UDN)

Lifecycle Operations:
  ✓ Resource deletion
  ✓ Resource recreation

Network Features:
  ✓ Failover
  ✓ Load balancing

Resilience & Recovery:
  ✓ OVN-Kubernetes restart
```

**Output (Inferred Feature Gaps):**
```
[HIGH] Single resource configuration
  - Pattern suggests "multiple" tested but not "single"
  - Recommendation: Add single resource baseline tests

[HIGH] Layer 2 networking
  - Layer 3 tested but Layer 2 missing
  - Recommendation: Add Layer 2 network topology tests

[MEDIUM] Local gateway mode
  - Gateway mode mentioned but local vs shared not clear
  - Recommendation: Add explicit gateway mode tests
```

**Integration in gap_analyzer.py:**

The dynamic feature extractor is built into the analyzer (no separate import needed):

```python
# After extracting test cases
feature_analysis = extract_features_from_tests(test_cases)

# Results included in analysis output
tested_features = feature_analysis['tested_features']
# {'Configuration Patterns': ['Overlapping', 'Non-overlapping', ...],
#  'Network Topology': ['UDN', 'Layer3', ...]}

feature_gaps = feature_analysis['feature_gaps']
# [{'feature': 'Multiple resources', 'priority': 'high', ...}]

coverage_stats = feature_analysis['coverage_stats']
# {'features_tested': 14, 'features_missing': 5}
```

**Report Integration:**

Feature analysis is included in all three report formats:

- **HTML Reports**: Feature sections with tested/missing features
- **Text Reports**: Feature lists grouped by category
- **JSON Reports**: Structured feature data for CI/CD integration

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

The analyzer generates three report formats. You should generate Python code at runtime to create these reports.

#### 1. HTML Gap Report (`test-gaps-report.html`)

**Purpose:** Interactive, filterable HTML report for visual gap analysis with professional styling

**HTML Document Structure:**

Generate a complete HTML5 document with the following structure:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Coverage Gap Analysis - {filename}</title>
    <style>
        /* Inline all CSS styles here - see CSS Styles section below */
    </style>
</head>
<body>
    <div class="container">
        <!-- Content sections -->
    </div>
    <script>
        /* JavaScript for gap filtering - see JavaScript section below */
    </script>
</body>
</html>
```

**CSS Styles (Inline in `<style>` tag):**

Generate comprehensive CSS with the following style rules:

1. **Reset and Base Styles:**
   - `*`: box-sizing: border-box, margin: 0, padding: 0
   - `body`: font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; background: #f5f5f5; padding: 20px

2. **Container and Layout:**
   - `.container`: max-width: 1400px, margin: 0 auto, background: white, padding: 30px, border-radius: 8px, box-shadow: 0 2px 10px rgba(0,0,0,0.1)
   - `h1`: color: #2c3e50, margin-bottom: 10px, font-size: 2em
   - `h2`: color: #34495e, margin-top: 30px, margin-bottom: 15px, padding-bottom: 10px, border-bottom: 2px solid #e74c3c, font-size: 1.5em
   - `h3`: color: #34495e, margin-top: 20px, margin-bottom: 10px, font-size: 1.2em

3. **Metadata Section:**
   - `.metadata`: background: #ecf0f1, padding: 15px, border-radius: 5px, margin-bottom: 25px
   - `.metadata p`: margin: 5px 0

4. **Score Cards:**
   - `.score-grid`: display: grid, grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)), gap: 15px, margin: 20px 0
   - `.score-card`: padding: 20px, border-radius: 8px, text-align: center, color: white
   - `.score-card.excellent`: background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%) (score >= 80)
   - `.score-card.good`: background: linear-gradient(135deg, #3498db 0%, #2980b9 100%) (score >= 60)
   - `.score-card.fair`: background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%) (score >= 40)
   - `.score-card.poor`: background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%) (score < 40)
   - `.score-card .number`: font-size: 2.5em, font-weight: bold, margin: 10px 0
   - `.score-card .label`: font-size: 0.9em, opacity: 0.9

5. **Gap Cards:**
   - `.gap-card`: background: #fff, border-left: 4px solid #e74c3c, padding: 20px, margin: 15px 0, border-radius: 5px, box-shadow: 0 2px 5px rgba(0,0,0,0.1)
   - `.gap-card.high`: border-left-color: #e74c3c
   - `.gap-card.medium`: border-left-color: #f39c12
   - `.gap-card.low`: border-left-color: #3498db
   - `.gap-card h4`: color: #2c3e50, margin-bottom: 10px, font-size: 1.1em
   - `.gap-card .gap-id`: font-family: "Courier New", monospace, font-size: 0.85em, color: #7f8c8d, margin-bottom: 5px
   - `.priority`: display: inline-block, padding: 4px 12px, border-radius: 12px, font-size: 0.75em, font-weight: bold, margin-right: 8px
   - `.priority.high`: background: #e74c3c, color: white
   - `.priority.medium`: background: #f39c12, color: white
   - `.priority.low`: background: #3498db, color: white
   - `.gap-card .impact`: background: #fff3cd, border-left: 3px solid #ffc107, padding: 10px, margin: 10px 0, border-radius: 3px
   - `.gap-card .recommendation`: background: #d4edda, border-left: 3px solid #28a745, padding: 10px, margin: 10px 0, border-radius: 3px

6. **Tables:**
   - `table`: width: 100%, border-collapse: collapse, margin: 20px 0
   - `th, td`: padding: 12px, text-align: left, border-bottom: 1px solid #ddd
   - `th`: background: #34495e, color: white, font-weight: 600
   - `tr:hover`: background: #f5f5f5
   - `.tested`: background: #d4edda, color: #155724, font-weight: bold, text-align: center
   - `.not-tested`: background: #f8d7da, color: #721c24, font-weight: bold, text-align: center

7. **Summary Boxes:**
   - `.summary-box`: background: #e3f2fd, border-left: 4px solid #2196f3, padding: 15px, margin: 20px 0, border-radius: 5px
   - `.warning-box`: background: #fff3cd, border-left: 4px solid #ffc107, padding: 15px, margin: 20px 0, border-radius: 5px
   - `.success-box`: background: #d4edda, border-left: 4px solid #28a745, padding: 15px, margin: 20px 0, border-radius: 5px

8. **Filter Buttons:**
   - `.filter-buttons`: margin: 20px 0
   - `.filter-btn`: padding: 10px 20px, margin-right: 10px, border: none, border-radius: 5px, cursor: pointer, font-weight: bold
   - `.filter-btn.active`: box-shadow: 0 0 0 3px rgba(0,0,0,0.2)
   - `.filter-btn.all`: background: #95a5a6, color: white
   - `.filter-btn.high`: background: #e74c3c, color: white
   - `.filter-btn.medium`: background: #f39c12, color: white
   - `.filter-btn.low`: background: #3498db, color: white

**HTML Content Sections:**

1. **Metadata Section:**
   ```html
   <div class="metadata">
       <p><strong>File:</strong> <code>{escaped_filename}</code></p>
       <p><strong>Path:</strong> <code>{escaped_filepath}</code></p>
       <p><strong>Component:</strong> {escaped_component_title}</p>
       <p><strong>Analysis Date:</strong> {YYYY-MM-DD}</p>
       <p><strong>Total Test Cases:</strong> {count}</p>
   </div>
   ```

2. **Coverage Scores Section:**
   - Display score cards in a grid
   - Show scores dynamically based on what's calculated for the component
   - Score display order and labels:
     ```python
     SCORE_DISPLAY = {
         'overall': {'order': 1, 'label': 'Overall Coverage'},
         'platform_coverage': {'order': 2, 'label': 'Platform Coverage'},
         'ip_stack_coverage': {'order': 3, 'label': 'IP Stack Coverage'},
         'topology_coverage': {'order': 4, 'label': 'Topology Coverage'},
         'network_layer_coverage': {'order': 5, 'label': 'Network Layer Coverage'},
         'gateway_mode_coverage': {'order': 6, 'label': 'Gateway Mode Coverage'},
         'protocol_coverage': {'order': 5, 'label': 'Protocol Coverage'},
         'service_type_coverage': {'order': 6, 'label': 'Service Type Coverage'},
         'storage_class_coverage': {'order': 7, 'label': 'Storage Class Coverage'},
         'volume_mode_coverage': {'order': 8, 'label': 'Volume Mode Coverage'},
         'scenario_coverage': {'order': 99, 'label': 'Scenario Coverage'},
     }
     ```
   - Sort scores by order, render only non-zero/non-None scores
   - Apply CSS class based on score value: `get_score_class(score)`
   - If overall < 60%, add a warning box with key findings

3. **What's Tested Section:**
   - Generate tables showing tested vs not-tested items
   - For networking components: platforms, protocols, service types, IP stacks, topologies, scenarios
   - For storage components: platforms, storage classes, volume modes, scenarios
   - For other components: platforms, scenarios only
   - Table format:
     ```html
     <table>
       <tr>
         <th>Item</th>
         <th>Status</th>
       </tr>
       <tr>
         <td>AWS</td>
         <td class="tested">✓ Tested</td>
       </tr>
     </table>
     ```

4. **Coverage Gaps Section:**
   - Summary box with gap counts by priority
   - Filter buttons for All/High/Medium/Low priority
   - Gap cards with data-priority attribute for filtering:
     ```html
     <div class="gap-card {priority}" data-priority="{priority}">
         <div class="gap-id">GAP-{001}</div>
         <h4>
             <span class="priority {priority}">{PRIORITY} PRIORITY</span>
             <span class="category">{Category}</span>
             {gap_name}
         </h4>
         <div class="impact"><strong>Impact:</strong> {impact_description}</div>
         <div class="recommendation"><strong>Recommendation:</strong> {recommendation_text}</div>
     </div>
     ```
   - Assign sequential GAP IDs: GAP-001, GAP-002, etc.
   - Sort gaps by priority (high, medium, low)

5. **Recommendations Section:**
   - Success box with top 5 high-priority gaps listed
   - Bulleted list of immediate actions

**JavaScript for Filtering (Inline in `<script>` tag):**

```javascript
function filterGaps(priority) {
    const cards = document.querySelectorAll('.gap-card');
    const buttons = document.querySelectorAll('.filter-btn');

    buttons.forEach(btn => btn.classList.remove('active'));
    document.querySelector(`.filter-btn.${priority}`).classList.add('active');

    cards.forEach(card => {
        if (priority === 'all' || card.dataset.priority === priority) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}
```

**Security Requirements:**
- Use `html.escape()` for all user-provided content (filenames, test names, gap descriptions)
- Sanitize priority values to only allow: 'high', 'medium', 'low'
- Never inject raw HTML from analysis data

**Helper Functions to Implement:**

1. `get_score_class(score)`:
   - score >= 80: return 'excellent'
   - score >= 60: return 'good'
   - score >= 40: return 'fair'
   - else: return 'poor'

2. Escape all strings using `from html import escape`

**Component-Specific Behavior:**

- **Networking components** (networking, router, dns, network-observability):
  - Show: platforms, protocols, service types, IP stacks, topologies, network layers, gateway modes, scenarios

- **Storage components** (storage, csi):
  - Show: platforms, storage classes, volume modes, volumes, CSI drivers, snapshots, scenarios

- **Other components**:
  - Show: platforms, scenarios only

#### 2. JSON Report (`test-gaps-report.json`)

**Generated by:** Claude Code at runtime based on analyzer output

**Purpose:** Machine-readable format for CI/CD integration

**Structure:**
```json
{
  "analysis": {
    "file": "path/to/test/file.go",
    "component_type": "networking",
    "test_count": 15,
    "test_cases": [
      {
        "name": "test name",
        "line": 42,
        "id": "12345",
        "tags": ["Serial", "Disruptive"]
      }
    ],
    "coverage": {
      "platforms": {
        "tested": ["AWS", "GCP"],
        "not_tested": ["Azure", "vSphere", "Bare Metal"]
      },
      "protocols": {
        "tested": ["TCP"],
        "not_tested": ["UDP", "SCTP"]
      }
    },
    "gaps": {
      "platforms": [
        {
          "platform": "Azure",
          "priority": "high",
          "impact": "Major cloud provider",
          "recommendation": "Add Azure tests"
        }
      ],
      "protocols": [],
      "scenarios": []
    }
  },
  "scores": {
    "overall": 45.0,
    "platform_coverage": 33.3,
    "protocol_coverage": 33.3,
    "scenario_coverage": 40.0
  },
  "generated_at": "2025-11-10T10:00:00Z"
}
```

**Implementation:** Use `json.dump()` with `indent=2` for readable output

#### 3. Text Summary (`test-gaps-summary.txt`)

**Generated by:** Claude Code at runtime based on analyzer output

**Purpose:** Terminal-friendly summary for quick review

**Format Structure:**
```text
============================================================
Test Coverage Gap Analysis
============================================================

File: {filename}
Component: {component_type}
Test Cases: {count}
Analysis Date: {timestamp}

============================================================
Coverage Scores
============================================================

Overall Coverage:          {score}%
Platform Coverage:         {score}%
[Component-specific scores based on type]
Scenario Coverage:         {score}%

============================================================
What's Tested
============================================================

Platforms:
  ✓ {platform1}
  ✓ {platform2}

[Additional tested items based on component type]

============================================================
Identified Gaps
============================================================

PLATFORM GAPS:
  [PRIORITY] {platform}
    Impact: {impact}
    Recommendation: {recommendation}

[Additional gap sections based on component type]

============================================================
Recommendations
============================================================

Current Coverage: {current}%
Target Coverage: {target}%

Focus on addressing HIGH priority gaps first to maximize
test coverage and ensure production readiness.
```

**Component-Specific Sections:**
- **Networking components**: Include protocol, service type, IP stack, topology gaps
- **Storage components**: Include storage class, volume mode gaps
- **Other components**: Only include platform and scenario gaps

**Implementation:** Use `'\n'.join(lines)` to build the text content

## Implementation Steps

When implementing this skill in a command:

### Step 0: Generate Analyzer Script at Runtime

**CRITICAL:** Before running any analysis, generate the analyzer script from the reference implementation.

```bash
# Create output directory
mkdir -p .work/test-coverage/gaps/

# Generate the analyzer script from the specification below
# Claude Code will write gap_analyzer.py based on the Analyzer Specification section
```

**Analyzer Specification:**

Generate a Python script (`gap_analyzer.py`) that performs component-aware E2E test gap analysis:

**Input:** Path or URL to a Go test file (Ginkgo framework)
**Output:** JSON to stdout with analysis results and coverage scores

**Core Algorithm:**

0. **Input Processing** (handle URLs and local paths):
   - Check if input starts with `http://` or `https://`
   - If URL: Use `urllib.request.urlopen()` to fetch content, save to temp file
   - If local path: Use directly
   - After analysis: Clean up temp file if created

1. **Component Detection** (auto-detect from file path/content):
   - Networking: `/networking/`, `egressip`, `networkpolicy` → component_type='networking'
   - Storage: `/storage/`, `persistentvolume` → component_type='storage'
   - Other components: etcd, apiserver, mco, operators, etc.

2. **Test Extraction** (regex-based):
   - Pattern: `(?:g\.|o\.)?It\(\s*["']([^"']+)["']`
   - Extract: test name, line number, tags ([Serial], [Disruptive]), test ID (pattern: `-\d+-`)

3. **Coverage Analysis** (keyword search in file content):
   - **Platforms**: Search for `aws|azure|gcp|vsphere|baremetal|rosa` (case-insensitive)
   - **Protocols**: Search for `\bTCP\b`, `\bUDP\b`, `\bSCTP\b`, `curl|wget|http` (TCP via HTTP)
   - **IP Stacks**: Search for `ipv4`, `ipv6`, `dualstack`
   - **Service Types**: Search for `NodePort`, `LoadBalancer`, `ClusterIP`
   - **Network Layers** (networking only): `layer2|l2`, `layer3|l3`, `default network`
   - **Gateway Modes** (networking only):
     - Search for `local.gateway|lgw` → if found, Local Gateway is tested
     - Shared Gateway is DEFAULT in OVN-K: if tests exist but no local gateway pattern found → Shared Gateway is tested
     - If no tests exist → neither is tested
   - **Topologies**: `sno|single-node`, `multi-node|HA cluster`, `hypershift|hcp`, check NonHyperShiftHOST tag
   - **Scenarios**: `failover`, `reboot`, `restart`, `delete`, `invalid`, `upgrade`, `concurrent`, `performance`, `rbac`, `traffic disruption`

4. **Gap Identification**:
   - For each category, items NOT found = gaps
   - Assign priority: high (production-critical), medium (important), low (nice-to-have)
   - Platform gaps: Azure/GCP/AWS = high, vSphere/Bare Metal = medium
   - Protocol gaps: UDP = high, SCTP = medium, TCP non-HTTP = low
   - Service type gaps: LoadBalancer = high, others = medium
   - Scenario gaps: Error Handling = high, Traffic Disruption = high (networking only)

5. **Coverage Scoring** (component-aware):
   - Networking: avg(platform, protocol, service_type, ip_stack, network_layer, gateway_mode, topology, scenario)
   - Storage: avg(platform, storage_class, volume_mode, scenario)
   - Other: avg(platform, scenario)
   - Each dimension: (tested_count / total_count) × 100

6. **Output Format** (JSON to stdout):
```json
{
  "analysis": {
    "file": "/path/to/test.go",
    "component_type": "networking",
    "test_count": 15,
    "test_cases": [...],
    "coverage": {
      "platforms": {"tested": [...], "not_tested": [...]},
      "protocols": {"tested": [...], "not_tested": [...]},
      ...
    },
    "gaps": {
      "platforms": [{"platform": "Azure", "priority": "high", "impact": "...", "recommendation": "..."}],
      ...
    }
  },
  "scores": {
    "overall": 62.0,
    "platform_coverage": 100.0,
    ...
  }
}
```

**Why Runtime Generation:**
- Claude Code generates the analyzer from this specification
- No separate `.py` file to maintain
- SKILL.md is the single source of truth
- Claude Code is excellent at generating code from specifications

### Step 1: Execute Gap Analyzer Script (MANDATORY)

**Execute the gap analyzer script to perform analysis and return structured data:**

```bash
# Run gap analyzer (outputs structured JSON to stdout)
python3 .work/test-coverage/gaps/gap_analyzer.py <test-file-path> --output-json
```

The analyzer will output structured JSON to stdout containing:
- Component type detection
- Test case extraction
- Coverage analysis
- Gap identification
- Priority scoring
- Component-specific recommendations

**IMPORTANT:** Do not skip this step. Do not attempt manual analysis. The script is the authoritative implementation.

### Step 2: Capture and Parse Analyzer Output

```python
import json
import subprocess

# Run analyzer and capture JSON output
result = subprocess.run(
    ['python3', '.work/test-coverage/gaps/gap_analyzer.py', test_file, '--output-json'],
    capture_output=True,
    text=True
)

# Parse structured data
analysis_data = json.loads(result.stdout)
```

### Step 3: Generate All Three Report Formats at Runtime (MANDATORY)

**IMPORTANT:** Claude Code generates all three report formats based on the analyzer's structured output.

#### 3.1: Generate JSON Report

```python
json_path = '.work/test-coverage/gaps/test-gaps-report.json'
with open(json_path, 'w') as f:
    json.dump(analysis_data, f, indent=2)
```

#### 3.2: Generate Text Summary Report

Follow the text format specification in Step 6 to generate a terminal-friendly summary.

```python
text_path = '.work/test-coverage/gaps/test-gaps-summary.txt'
# Generate text content following format in Step 6
with open(text_path, 'w') as f:
    f.write(text_content)
```

#### 3.3: Generate HTML Report

Follow the HTML specification in Step 6 to generate an interactive report.

```python
html_path = '.work/test-coverage/gaps/test-gaps-report.html'
# Generate HTML content following specification in Step 6
# Include all CSS styles, JavaScript filtering, and component-specific sections
with open(html_path, 'w') as f:
    f.write(html_content)
```

**Key Requirements:**
- Generate HTML following the exact structure in "Step 6: Generate Reports" above
- Include all CSS styles inline in `<style>` tag
- Include JavaScript filtering function in `<script>` tag
- Escape all user-provided content with `html.escape()`
- Apply component-specific sections based on component type

### Step 4: Display Results

After generating all three reports, display the results to the user:

```python
# Display summary (from text report or analysis_data)
print(f"Component detected: {analysis_data['analysis']['component_type']}")
print(f"Overall coverage: {analysis_data['scores']['overall']}%")
print(f"High-priority gaps: {high_priority_count}")

# Provide report locations
print("\nReports Generated:")
print("  ✓ HTML:  .work/test-coverage/gaps/test-gaps-report.html")
print("  ✓ JSON:  .work/test-coverage/gaps/test-gaps-report.json")
print("  ✓ Text:  .work/test-coverage/gaps/test-gaps-summary.txt")
```

### Step 5: Parse Analysis Data (Optional)

For programmatic access to gap data, use the `analysis_data` from Step 2:

```python
# Access analysis results (from analysis_data captured in Step 2)
component_type = analysis_data['analysis']['component_type']
test_count = analysis_data['analysis']['test_count']
overall_score = analysis_data['scores']['overall']

# Access gaps
platform_gaps = analysis_data['analysis']['gaps']['platforms']
protocol_gaps = analysis_data['analysis']['gaps'].get('protocols', [])
scenario_gaps = analysis_data['analysis']['gaps']['scenarios']

# Filter high-priority gaps
high_priority_gaps = [
    gap for category in analysis_data['analysis']['gaps'].values()
    for gap in category if gap.get('priority') == 'high'
]
```

## ⚠️ MANDATORY PRE-COMPLETION VALIDATION

**CRITICAL:** Before declaring this skill complete, you MUST execute ALL validation checks below. Failure to validate is considered incomplete execution.

### Validation Checklist

Execute these verification steps in order. ALL must pass:

#### 1. File Existence Check

```bash
# Verify all three reports exist
test -f .work/test-coverage/gaps/test-gaps-report.html && echo "✓ HTML exists" || echo "✗ HTML MISSING"
test -f .work/test-coverage/gaps/test-gaps-report.json && echo "✓ JSON exists" || echo "✗ JSON MISSING"
test -f .work/test-coverage/gaps/test-gaps-summary.txt && echo "✓ Text exists" || echo "✗ Text MISSING"
```

**Required:** All three files must exist. If any are missing, regenerate them.

#### 2. Dynamic Feature Extraction Verification

```bash
# Verify HTML has "Tested Features (Dynamic Feature Extraction)" section
grep -q "Tested Features (Dynamic Feature Extraction)" .work/test-coverage/gaps/test-gaps-report.html && \
  echo "✓ Feature extraction section present" || \
  echo "✗ MISSING: Dynamic Feature Extraction section"

# Verify JSON has feature data
grep -q '"tested_features"' .work/test-coverage/gaps/test-gaps-report.json && \
grep -q '"feature_gaps"' .work/test-coverage/gaps/test-gaps-report.json && \
  echo "✓ Feature data in JSON" || \
  echo "✗ MISSING: Feature data in JSON"

# Verify Text has feature section
grep -q "Tested Features" .work/test-coverage/gaps/test-gaps-summary.txt && \
  echo "✓ Feature section in Text" || \
  echo "✗ MISSING: Feature section in Text"
```

**Required:** Dynamic Feature Extraction must be present in all three reports. This is a critical requirement from Step 5a (lines 163-280).

#### 3. HTML Coverage Dimension Verification

**CRITICAL:** The HTML report must display ALL coverage dimension tables based on component type.

```bash
# For networking components, verify ALL 8 dimension tables exist
grep -c "<h3>Platforms</h3>" .work/test-coverage/gaps/test-gaps-report.html
grep -c "<h3>Protocols</h3>" .work/test-coverage/gaps/test-gaps-report.html
grep -c "<h3>Service Types</h3>" .work/test-coverage/gaps/test-gaps-report.html
grep -c "<h3>IP Stacks</h3>" .work/test-coverage/gaps/test-gaps-report.html
grep -c "<h3>Network Layers</h3>" .work/test-coverage/gaps/test-gaps-report.html
grep -c "<h3>Gateway Modes</h3>" .work/test-coverage/gaps/test-gaps-report.html
grep -c "<h3>Topologies</h3>" .work/test-coverage/gaps/test-gaps-report.html
grep -c "<h3>Scenarios</h3>" .work/test-coverage/gaps/test-gaps-report.html
```

**Expected Results:**
- **Networking components:** 8 dimension tables (Platforms, Protocols, Service Types, IP Stacks, Network Layers, Gateway Modes, Topologies, Scenarios)
- **Storage components:** 5 dimension tables (Platforms, Storage Classes, Volume Modes, Provisioners, Scenarios)
- **Other components:** 2 dimension tables (Platforms, Scenarios)

**Verification Command:**
```bash
# Count total coverage dimension tables
TABLE_COUNT=$(grep -E "<h3>(Platforms|Protocols|Service Types|IP Stacks|Network Layers|Gateway Modes|Topologies|Scenarios|Storage Classes|Volume Modes|Provisioners)</h3>" .work/test-coverage/gaps/test-gaps-report.html | wc -l)
echo "Coverage dimension tables found: $TABLE_COUNT"

# Verify based on component type
COMPONENT=$(grep -oP 'Component:</strong> \K[^<]+' .work/test-coverage/gaps/test-gaps-report.html | head -1 | tr -d '</p>')
echo "Component type: $COMPONENT"

case "$COMPONENT" in
  Networking)
    [ "$TABLE_COUNT" -eq 8 ] && echo "✓ All 8 networking dimensions present" || echo "✗ INCOMPLETE: Expected 8 tables, found $TABLE_COUNT"
    ;;
  Storage)
    [ "$TABLE_COUNT" -eq 5 ] && echo "✓ All 5 storage dimensions present" || echo "✗ INCOMPLETE: Expected 5 tables, found $TABLE_COUNT"
    ;;
  *)
    [ "$TABLE_COUNT" -eq 2 ] && echo "✓ All 2 generic dimensions present" || echo "✗ INCOMPLETE: Expected 2 tables, found $TABLE_COUNT"
    ;;
esac
```

**Required:** All component-specific dimension tables must be present. Missing tables indicate incomplete HTML generation.

#### 4. Effort Estimates Verification

```bash
# Verify gaps include effort estimates
grep -q "Effort Required" .work/test-coverage/gaps/test-gaps-report.html && \
  echo "✓ Effort estimates in HTML" || \
  echo "✗ MISSING: Effort estimates"
```

**Required:** Gaps must include effort estimates (Low, Medium, High) as specified in Step 5a.

#### 5. Gap Analyzer Implementation Verification

```bash
# Verify analyzer has feature extraction function
grep -q "def extract_features_from_tests" .work/test-coverage/gaps/gap_analyzer.py && \
  echo "✓ Feature extraction function exists" || \
  echo "✗ MISSING: extract_features_from_tests() function"

# Verify all 5 feature categories are defined
grep -q "Configuration Patterns" .work/test-coverage/gaps/gap_analyzer.py && \
grep -q "Network Topology" .work/test-coverage/gaps/gap_analyzer.py && \
grep -q "Lifecycle Operations" .work/test-coverage/gaps/gap_analyzer.py && \
grep -q "Network Features" .work/test-coverage/gaps/gap_analyzer.py && \
grep -q "Resilience & Recovery" .work/test-coverage/gaps/gap_analyzer.py && \
  echo "✓ All 5 feature categories defined" || \
  echo "✗ MISSING: Some feature categories not implemented"
```

**Required:** The gap analyzer must implement Dynamic Feature Extraction with all 5 categories.

#### 6. JSON Structure Verification

```python
# Verify JSON has all required fields
python3 << 'EOF'
import json
try:
    with open('.work/test-coverage/gaps/test-gaps-report.json', 'r') as f:
        data = json.load(f)

    required_fields = [
        ('analysis.file', lambda d: d['analysis']['file']),
        ('analysis.component_type', lambda d: d['analysis']['component_type']),
        ('analysis.test_count', lambda d: d['analysis']['test_count']),
        ('analysis.tested_features', lambda d: d['analysis']['tested_features']),
        ('analysis.feature_gaps', lambda d: d['analysis']['feature_gaps']),
        ('scores.overall', lambda d: d['scores']['overall']),
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
2. ✓ Dynamic Feature Extraction present in all reports
3. ✓ HTML shows ALL component-specific coverage dimension tables
4. ✓ Effort estimates included in gaps
5. ✓ Gap analyzer implements feature extraction function
6. ✓ JSON contains all required fields

**If ANY check fails:** Fix the issue and re-run all validation checks. Do NOT declare the skill complete until ALL checks pass.

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
python3 .work/test-coverage/gaps/gap_analyzer.py \
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
#   JSON: .work/gaps/test-gaps-report.json
#   Text: .work/gaps/test-gaps-summary.txt
```

### Example 2: Analyze Storage Test File

```bash
# Run gap analyzer on a storage test file
python3 .work/test-coverage/gaps/gap_analyzer.py \
  /path/to/test/extended/storage/persistent_volumes_test.go \
  --output .work/gaps/

# Output:
# Component detected: storage
# Test cases found: 18
# Overall coverage: 52.0%
# High-priority gaps: ReadWriteMany volumes, CSI storage class, Snapshot scenarios
```

### Example 3: Analyze from GitHub URL

```bash
# Analyze file from GitHub raw URL
python3 .work/test-coverage/gaps/gap_analyzer.py \
  https://raw.githubusercontent.com/openshift/origin/master/test/extended/networking/egressip.go \
  --output .work/gaps/
```

The analyzer automatically detects URLs and downloads the file for analysis.

## Integration with Claude Code Commands

This skill is used by:
- `/test-coverage:gaps <test-file-or-url>` - Analyze E2E test scenario gaps

The command invokes this skill to perform component-aware gap analysis on the specified test file.

## See Also

- [Test Coverage Plugin README](../../README.md) - User guide and installation
