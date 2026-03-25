---
name: Generate Cascade Report
description: Generate interactive HTML, Markdown, or JSON reports from confirmed cascade data with similarity analysis results
---

# Generate Cascade Report

This skill generates final reports from confirmed cascade data, including similarity analysis results. It supports multiple output formats: interactive HTML, Markdown, and JSON.

## When to Use This Skill

Use this skill when you need to:

- Generate a final report of confirmed backport cascades
- Create an interactive HTML report for web browser viewing
- Export cascade data in Markdown or JSON format
- Present cascade analysis results to stakeholders

## Prerequisites

1. **Input file**: `.work/detect-backport-regressions/confirmed_cascades.json` from `analyze-cascade-similarity` skill
2. **Output format** specified via `--format` parameter (html, markdown, or json)

## Implementation Steps

### Step 1: Load Confirmed Cascades

Read the JSON output from the `analyze-cascade-similarity` skill:

```bash
confirmed_cascades=$(cat .work/detect-backport-regressions/confirmed_cascades.json)
```

Parse the data:

```python
import json
data = json.loads(confirmed_cascades)
confirmed = data["confirmed_cascades"]
false_positives = data["false_positives"]
unable_to_analyze = data["unable_to_analyze"]
```

### Step 2: Determine Output Format

Check the `--format` parameter (default: html):

```python
format = args.format  # "html", "markdown", or "json"

if format == "html":
    generate_html_report(data)
elif format == "markdown":
    generate_markdown_report(data)
elif format == "json":
    # Pass through the JSON data
    print(json.dumps(data, indent=2))
```

### Step 3: Generate HTML Report (Default)

**HTML Report Features**:
- Self-contained (all CSS/JS embedded)
- Interactive collapsible sections
- Color-coded severity levels
- GitHub-style dark theme
- Similarity analysis visualization
- Direct links to Sippy and JIRA

**HTML Structure**:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Backport Regression Detection Report</title>
    <style>
        /* Embedded CSS with dark theme */
        body { background: #0d1117; color: #c9d1d9; }
        .severity-critical { border-left: 4px solid #f85149; }
        .severity-high { border-left: 4px solid #d29922; }
        /* ... full CSS ... */
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <h1>Backport Regression Detection Report</h1>
            <div class="meta">
                Generated: {timestamp}
                Current Release: {current_release}
                Scanned Releases: {releases}
            </div>
        </header>

        <!-- Executive Summary -->
        <div class="summary">
            <div class="summary-card critical">
                <div class="summary-label">Critical</div>
                <div class="summary-value">{count}</div>
            </div>
            <!-- ... more cards ... -->
        </div>

        <!-- Confirmed Cascades Section -->
        <h2>Confirmed Cascades</h2>
        {for each confirmed cascade}
        <div class="cascade {severity} expanded">
            <div class="cascade-header" onclick="toggle()">
                <span class="severity-badge">{severity}</span>
                <div class="test-name">{test_name}</div>
                <div class="similarity-score">
                    Similarity: {similarity_score * 100}%
                </div>
            </div>
            <div class="cascade-body">
                <!-- Origin Section -->
                <div class="origin-section">
                    <h3>Origin ({origin.release})</h3>
                    <div class="analysis-result">
                        <strong>Root Cause:</strong> {root_cause_summary}
                        <strong>Affected Components:</strong> {affected_components}
                        <strong>Confidence:</strong> {confidence_level}/5
                    </div>
                </div>

                <!-- Cascade Timeline -->
                <div class="timeline-section">
                    <h3>Cascade Timeline</h3>
                    <table>
                        <tr>
                            <th>Release</th>
                            <th>Root Cause</th>
                            <th>Similarity</th>
                            <th>Status</th>
                        </tr>
                        {for each cascade_release}
                        <tr>
                            <td>{release}</td>
                            <td>{root_cause_summary}</td>
                            <td>
                                <span class="similarity-badge">
                                    {similarity_to_origin * 100}%
                                    {if similarity >= 0.6: ✓}
                                </span>
                            </td>
                            <td><span class="badge {status}">{status}</span></td>
                        </tr>
                    </table>
                </div>

                <!-- Similarity Analysis Details -->
                <div class="similarity-details">
                    <h4>Similarity Analysis</h4>
                    <div class="comparison-matrix">
                        <!-- Show component overlap, pattern matching, etc. -->
                    </div>
                </div>
            </div>
        </div>

        <!-- False Positives Section -->
        <h2>False Positives (Different Root Causes)</h2>
        {for each false_positive}
        <div class="cascade false-positive">
            <!-- Similar structure, but highlight differences -->
            <div class="why-different">
                <strong>Why this is a false positive:</strong>
                Origin: {origin.root_cause_summary}
                4.21: {release_4.21.root_cause_summary}
                4.20: {release_4.20.root_cause_summary}
                → Different components and error patterns
            </div>
        </div>
    </div>

    <script>
        // Interactive toggle functionality
        function toggle() {
            this.parentElement.classList.toggle('expanded');
        }
        // Auto-expand critical/high on load
        document.addEventListener('DOMContentLoaded', function() {
            document.querySelectorAll('.cascade.critical, .cascade.high')
                .forEach(el => el.classList.add('expanded'));
        });
    </script>
</body>
</html>
```

**Save HTML to file**:

```bash
timestamp=$(date +%Y%m%d_%H%M%S)
output_file="backport-regression-report_${timestamp}.html"
echo "$html_content" > "$output_file"
echo "Report saved to: $output_file"
```

### Step 4: Generate Markdown Report

**Markdown Report Structure**:

```markdown
# Backport Regression Detection Report

**Generated**: 2026-04-02 22:30:00 UTC
**Current Release**: 4.22
**Scanned Releases**: 4.21, 4.20, 4.19, 4.18
**Analysis Type**: Root Cause Comparison with Similarity Analysis

## Executive Summary

- **Total Confirmed Cascades**: 3
- **Critical** (3+ releases, triaged): 1
- **High** (2 releases, triaged): 1
- **Medium** (1 release, triaged): 1
- **False Positives Detected**: 2

---

## Confirmed Cascades

### 🚨 CRITICAL: etcd data loss during upgrade

**Test**: `[sig-etcd] etcd should not lose quorum during upgrade`
**Severity**: CRITICAL
**Similarity Score**: 85%
**Component**: etcd, storage

#### Origin (4.22)
- **First Detected**: 2026-02-15 10:30:00Z
- **Root Cause**: etcd data corruption due to fsync failures on XFS filesystem
- **Affected Components**: etcd, storage, machine-config
- **Key Error Patterns**: `failed to fsync`, `etcd data corruption`, `leveldb: corrupted`
- **JIRA**: [OCPBUGS-75000](https://issues.redhat.com/browse/OCPBUGS-75000)
- **Confidence**: 5/5

#### Cascade Timeline

| Release | First Detected | Days After | Root Cause | Similarity | Status |
|---------|----------------|------------|------------|------------|--------|
| **4.21** | 2026-03-10 | 23 days | etcd data corruption due to fsync failures | ✓ 85% | OPEN |
| **4.20** | 2026-03-15 | 28 days | etcd data corruption due to fsync failures | ✓ 82% | OPEN |
| **4.19** | 2026-03-18 | 31 days | etcd data corruption due to fsync failures | ✓ 88% | OPEN |

**Analysis**: All releases show the **same root cause** - etcd fsync failures on XFS filesystems. This is a confirmed backport cascade likely caused by a machine-config or storage layer change that was backported from 4.22 to older releases.

**Recommended Action**:
1. Halt all backports to etcd, machine-config, and storage components
2. Review recent backports to identify the problematic change
3. File blocker bugs for all affected releases
4. Link to origin JIRA: OCPBUGS-75000

---

### ⚠️  FALSE POSITIVE: Cluster upgrade test failures

**Test**: `[sig-arch][Feature:ClusterUpgrade] Cluster should remain functional during upgrade`
**Severity**: CRITICAL (by test name matching)
**Similarity Score**: 15%
**Why this is a false positive**: Different root causes across releases

#### Origin (4.22)
- **Root Cause**: Local registry ImagePullBackOff on bare metal (dev-scripts specific)
- **Components**: local-image-registry, worker-node-image-pull
- **Confidence**: 4/5

#### 4.21 - Different Root Cause ✗
- **Root Cause**: CNI configuration loss during upgrade causing NetworkPluginNotReady
- **Components**: network (OVN-Kubernetes), machine-config, etcd
- **Similarity to Origin**: 10%
- **Confidence**: 5/5

#### 4.20 - Different Root Cause ✗
- **Root Cause**: External quay.io registry HTTP 502 errors (infrastructure outage)
- **Components**: External/quay.io, Test Framework
- **Similarity to Origin**: 20%
- **Confidence**: 5/5

**Analysis**: While the **same test** failed across all three releases, the **root causes are completely different**:
- 4.22: Bare metal local registry issue
- 4.21: OVN-Kubernetes CNI configuration bug (REAL PRODUCT BUG)
- 4.20: External registry outage (NOT ACTIONABLE)

This is NOT a backport cascade. These are independent failures.

**Recommended Action**:
1. Remove from cascade report - false positive
2. Escalate 4.21 CNI issue separately as critical networking bug
3. 4.22 bare metal registry issue needs investigation
4. 4.20 was transient external issue - no action needed

---

## Summary

### Confirmed True Cascades: 3
1. etcd data loss (CRITICAL) - 3 releases affected
2. kube-apiserver graceful termination (HIGH) - 2 releases
3. DNS operator pod scheduling (MEDIUM) - 1 release

### False Positives: 2
1. Cluster upgrade test (different root causes)
2. Network pod creation (different infrastructure issues)

### Unable to Analyze: 1
1. Storage provisioning test (no Prow job URLs available)
```

**Output markdown**:

```bash
# Output to stdout (can be redirected to file)
echo "$markdown_content"
```

### Step 5: JSON Output

For JSON format, simply pass through the confirmed_cascades.json data with proper formatting:

```bash
cat .work/detect-backport-regressions/confirmed_cascades.json | jq '.'
```

Or add additional metadata:

```json
{
  "report_generated": "2026-04-02T22:30:00Z",
  "report_format": "json",
  "summary": {
    "total_confirmed": 3,
    "total_false_positives": 2,
    "by_severity": {
      "CRITICAL": 1,
      "HIGH": 1,
      "MEDIUM": 1
    }
  },
  "confirmed_cascades": [ /* from input */ ],
  "false_positives": [ /* from input */ ],
  "unable_to_analyze": [ /* from input */ ]
}
```

## Output Formats

### HTML (Default)
- **File**: `backport-regression-report_YYYYMMDD_HHMMSS.html`
- **Location**: Current working directory
- **Features**: Interactive, self-contained, no external dependencies

### Markdown
- **Output**: stdout
- **Usage**: Can be redirected to file or piped to other tools
- **Features**: Human-readable, GitHub-compatible

### JSON
- **Output**: stdout
- **Usage**: For automation, CI/CD integration, data processing
- **Features**: Machine-readable, structured data

## Severity Color Coding

- **CRITICAL**: Red (#f85149) - 3+ releases, triaged
- **HIGH**: Orange (#d29922) - 2 releases, triaged
- **MEDIUM**: Yellow (#d4a72c) - 1 release, triaged
- **LOW**: Blue (#58a6ff) - Untriaged

## Similarity Visualization

**Checkmarks in reports**:
- ✓ (green checkmark): Similarity >= 60% (confirmed same root cause)
- ✗ (red X): Similarity < 60% (different root cause)

**Similarity badges**:
- 80-100%: "Excellent match"
- 60-79%: "Good match"
- 40-59%: "Moderate match"
- 0-39%: "Poor match"

## Example Usage

This skill is typically invoked after `analyze-cascade-similarity`:

```bash
# Generate HTML report (default)
# Skill: generate-cascade-report with --format html

# Generate Markdown report to stdout
# Skill: generate-cascade-report with --format markdown

# Generate JSON for automation
# Skill: generate-cascade-report with --format json > output.json
```

## See Also

- `detect-potential-cascades` - Identify potential cascades by test name matching
- `analyze-cascade-similarity` - Perform root cause analysis and similarity comparison
