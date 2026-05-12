---
name: Detect Backport Regressions
description: Detect regressions that have cascaded from newer releases to older releases due to problematic backports
---

# Detect Backport Regressions

**NOTE: This skill has been refactored into three focused sub-skills for better modularity and maintainability.**

## New Skill-Based Implementation

The backport regression detection functionality has been split into three focused skills:

1. **`detect-potential-cascades`** - Identifies potential cascades by test name matching
   - Fast, test-name-only matching
   - Temporal ordering analysis
   - Severity calculation

2. **`analyze-cascade-similarity`** - Performs deep root cause analysis
   - Fetches Prow job URLs
   - Launches parallel subagents for failure analysis
   - Compares root causes to confirm real cascades vs false positives

3. **`generate-cascade-report`** - Generates final reports
   - Interactive HTML reports
   - Markdown and JSON output
   - Similarity visualization

## When to Use This Skill

Use the `/ci:detect-backport-regressions` command, which orchestrates all three sub-skills automatically.

Alternatively, you can use the individual skills if you need just one step:

- Use `detect-potential-cascades` alone for fast test-name matching without similarity analysis
- Use `analyze-cascade-similarity` to analyze existing potential_cascades.json
- Use `generate-cascade-report` to regenerate reports from existing data

## Prerequisites

1. **Network Access**: Must be able to reach Sippy API endpoints and GCS (for Prow artifacts)
2. **Installed plugins**:
   - `ci` plugin (for fetch-releases, fetch-regression-details, prow-job-analyze-test-failure)
   - `teams` plugin (for list-regressions)

## Quick Start

**Recommended**: Use the command which handles all orchestration:

```bash
/ci:detect-backport-regressions --days 45 --min-cascade 2
```

**Advanced**: Use individual skills for more control:

```bash
# Step 1: Detect potential cascades (fast)
# Load skill: detect-potential-cascades
# Parameters: --current-release 4.22 --lookback 4 --days 45

# Step 2: Analyze similarity (slow, thorough)
# Load skill: analyze-cascade-similarity
# Reads: .work/detect-backport-regressions/potential_cascades.json

# Step 3: Generate report
# Load skill: generate-cascade-report --format html
# Reads: .work/detect-backport-regressions/confirmed_cascades.json
```

### Step 2: Analyze Test Failure Similarity with Parallel Subagents

**IMPORTANT**: This skill **always** launches **parallel subagents** to perform deep failure analysis for each release version, then compares the root causes to determine if the cascade is real or a false positive.

**How Similarity Analysis Works**:

For each potential cascade (a test that fails in both the dev release and one or more older releases):

1. **Fetch Prow job URLs** for representative failures in each release:
   - Use `fetch-regression-details` to get the test_id
   - Use `fetch-test-runs` to get failed job runs for that test in each release
   - Extract the most recent Prow job URL for each release

2. **Launch parallel subagents** to analyze each failure independently:
   - Launch one subagent per release (dev release + all cascade releases)
   - All subagents run in parallel for maximum speed
   - Each subagent receives the prompt: `"Analyze <TEST_NAME> in this Prow job: <PROW_URL>"`
   - This prompt format triggers the `ci:prow-job-analyze-test-failure` skill

3. **Subagent analysis requirements**:
   - **Trace to root cause**: Never stop at symptoms like "0 nodes ready", "operator degraded", or "crash-looping". Download log bundles, pod logs, and container previous logs. Cite specific error messages.
   - **Return structured results**: Each subagent MUST include an `ANALYSIS_RESULT` block at the end:
     ```
     ANALYSIS_RESULT:
     - root_cause_summary: <one-line summary>
     - affected_components: <comma-separated list of affected operators/components>
     - key_error_patterns: <comma-separated key error strings for matching>
     - known_symptoms: <comma-separated symptom summaries, or "none">
     - test_name: <the name of the failing test>
     - confidence_level: <1-5, where 5 is highest confidence in the root cause>
     ```

4. **Compare analysis results** across releases:
   - Extract the `ANALYSIS_RESULT` block from each subagent response
   - Compare `root_cause_summary`, `affected_components`, and `key_error_patterns`
   - Determine similarity:
     - **Same root cause**: Components and error patterns match (even if timestamps/UUIDs differ)
     - **Different root cause**: Different components or fundamentally different error patterns
     - **Low confidence**: If any subagent reports `confidence_level` < 3, flag for manual review

5. **Filter cascades**:
   - **Keep**: Cascades where all releases show the same root cause
   - **Discard**: Cascades where releases show different root causes (false positive)
   - **Flag**: Cascades with low confidence or incomplete analysis data

### Step 3: Parse and Present Results

The script automatically:
1. Auto-detects the current development release (or uses `--current-release`)
2. Calculates lookback releases based on `--lookback` parameter
3. Fetches regression data for all releases using the `list-regressions` skill
4. Matches regressions by test name across releases
5. Outputs the list of potential cascades in JSON format (before similarity analysis)

**After the script completes**, you (the Claude agent) must:
1. Read the script's JSON output to identify potential cascades
2. For each cascade, follow Step 2 to launch parallel subagents and analyze failures
3. Compare the ANALYSIS_RESULT blocks from each subagent
4. Determine which cascades are confirmed (same root cause) vs false positives (different root causes)
5. Generate the final report with the requested format:
   - **HTML report** (`--format html`, default): Self-contained HTML with collapsible sections, GitHub-style dark theme
   - **Markdown report** (`--format markdown`): Human-readable report with severity levels, timelines, and actionable recommendations
   - **JSON output** (`--format json`): Machine-readable format for automation
6. Include only confirmed cascades in the final report, with similarity analysis details

### Command-Line Arguments

All arguments are optional:

- `--current-release <version>`: Override auto-detection (e.g., `4.22`)
- `--lookback N`: Number of previous releases to scan (default: 4, range: 1-6)
- `--days N`: Time window for cascade detection (default: 30)
- `--exclude-install true|false`: Exclude installation failures (default: true)
- `--component <name>`: Filter by component name
- `--min-cascade N`: Minimum cascade count to report (default: 1)
- `--format html|markdown|json`: Output format for the final report (default: html). **Note**: The script always outputs JSON; the agent generates the final report in the requested format.
- `--include-resolved`: Include closed regressions in stable releases (default: false)

### Error Handling

The script handles common errors gracefully:

**No current release detected**:
```
ERROR: Could not auto-detect current development release
HINT: Use --current-release to manually specify (e.g., --current-release 4.22)
```

**API failures**: Retries failed requests and continues with available data

**No cascades found**:
```
✅ No cascading regressions detected - system is healthy!
```

### Exit Codes

- `0`: Success (cascades found or no cascades)
- `1`: General error
- `2`: Missing dependencies or configuration error
- `3`: Critical cascades detected (3+ releases affected)
- `130`: Interrupted by user (Ctrl+C)

## Example Output Structure

### Markdown Example (truncated)

```markdown
# Backport Regression Detection Report
**Generated**: 2026-03-23 14:30:00 UTC
**Current Release**: 4.22
**Scanned Releases**: 4.21, 4.20, 4.19, 4.18
**Time Window**: Last 30 days

## Summary
- **Total Cascading Regressions**: 3
- **Critical (3+ releases)**: 1
- **High (2 releases)**: 1
- **Medium (1 release)**: 1
- **Low (untriaged)**: 0
- **Affected Releases**: 4.21 (3), 4.20 (2), 4.19 (1), 4.18 (1)

---

## 🚨 CRITICAL: kube-apiserver - graceful termination failure

**Test**: `[sig-api-machinery] kube-apiserver should terminate gracefully within grace period`
**Test ID**: `openshift-tests:2bc0fe9de9a98831c20e569a21d7ded9`
**Component**: kube-apiserver

### Origin (4.22-main)
- **First Detected**: 2026-01-15 10:30:00Z (68 days ago)
- **JIRA Bug**: [OCPBUGS-75200](https://issues.redhat.com/browse/OCPBUGS-75200)
- **Triage Date**: 2026-01-16 08:00:00Z
- **Status**: OPEN - Assigned to API Server team

### Cascade Timeline
| Release | First Detected | Days After Origin | Status | Resolved | JIRA Links |
|---------|----------------|-------------------|--------|----------|------------|
| 4.21    | 2026-02-01 14:20:00Z | 17 days | OPEN   | -   | [OCPBUGS-75200](https://issues.redhat.com/browse/OCPBUGS-75200) |
| 4.20    | 2026-02-10 09:15:00Z | 26 days | ✅ RESOLVED | 2026-02-15 09:30:00Z | [OCPBUGS-75200](https://issues.redhat.com/browse/OCPBUGS-75200) |
| 4.19    | 2026-02-18 11:45:00Z | 34 days | OPEN   | -   | [OCPBUGS-75200](https://issues.redhat.com/browse/OCPBUGS-75200) |
| 4.18    | 2026-02-25 06:30:00Z | 41 days | OPEN   | -   | None |

### 🔴 Recommended Actions
1. **URGENT**: Stop all backports related to OCPBUGS-75200
2. Review recent MCO/systemd changes backported to 4.21, 4.20, 4.19, 4.18
3. Consider reverting problematic backports in stable branches
4. Link this cascade pattern to OCPBUGS-75200 for team visibility
5. Monitor for further spread to 4.17

---

## Quick Actions

### Immediate Stops
The following bugs have active cascade patterns and should have backports halted:
- OCPBUGS-75200 (4 releases affected)
- OCPBUGS-74833 (2 releases affected)

### Backport Review Needed
Review recent backports (last 30 days) for these components:
- kube-apiserver (1 cascading regression)
- MCO (1 cascading regression)

### Monitor List
Regressions showing early cascade pattern (1 release):
- OCPBUGS-75401: etcd leader election (4.22 → 4.21)
```

### JSON Example (truncated)

```json
{
  "generated": "2026-03-23T14:30:00Z",
  "current_release": "4.22",
  "scanned_releases": ["4.21", "4.20", "4.19", "4.18"],
  "time_window_days": 30,
  "summary": {
    "total_cascades": 3,
    "severity_counts": {
      "CRITICAL": 1,
      "HIGH": 1,
      "MEDIUM": 1,
      "LOW": 0
    },
    "affected_releases": {
      "4.21": 3,
      "4.20": 2,
      "4.19": 1,
      "4.18": 1
    }
  },
  "cascades": [
    {
      "test_id": "openshift-tests:2bc0fe9de9a98831c20e569a21d7ded9",
      "test_name": "[sig-api-machinery] kube-apiserver should terminate gracefully within grace period",
      "component": "kube-apiserver",
      "severity": "CRITICAL",
      "origin": {
        "release": "4.22",
        "opened": "2026-01-15T10:30:00Z",
        "triages": [
          {
            "jira_key": "OCPBUGS-75200",
            "url": "https://issues.redhat.com/browse/OCPBUGS-75200",
            "created_at": "2026-01-16T08:00:00Z"
          }
        ]
      },
      "cascade_releases": [
        {
          "release": "4.21",
          "opened": "2026-02-01T14:20:00Z",
          "closed": null,
          "days_after_origin": 17,
          "status": "open",
          "is_resolved": false
        },
        {
          "release": "4.20",
          "opened": "2026-02-10T09:15:00Z",
          "closed": "2026-02-15T09:30:00Z",
          "days_after_origin": 26,
          "status": "closed",
          "is_resolved": true
        }
      ]
    }
  ]
}
```
