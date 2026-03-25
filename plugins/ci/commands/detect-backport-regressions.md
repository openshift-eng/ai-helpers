---
description: Detect regressions that have cascaded from newer releases to older releases due to problematic backports
argument-hint: "[--current-release <version>] [--lookback N] [--days N]"
---

## Name

ci:detect-backport-regressions

## Synopsis

```
/ci:detect-backport-regressions [--current-release <version>] [--lookback N] [--days N] [--exclude-install] [--exclude-monitor] [--component <name>] [--min-cascade N] [--include-resolved]
```

## Description

The `ci:detect-backport-regressions` command identifies regressions that have cascaded backward from the current development release to older stable releases due to problematic backports.

**Problem Pattern**: When a regression is discovered in the active development branch (e.g., 4.22-main) and a bug is filed, the underlying code change that caused the regression may be backported to previous release branches. This creates a cascading effect where the same regression appears in older releases over time.

**Real-World Example**: [OCPBUGS-75200](https://issues.redhat.com/browse/OCPBUGS-75200) - A systemd change from the MCO team exposed a problem with kube-apiserver graceful termination. The regression was found in 4.22, a bug was filed, but the cause was backported all the way to 4.18 before anyone noticed.

### Detection Strategy

The command:
1. Fetches open regressions from the current development release
2. Walks backward through previous N releases (n-1, n-2, n-3, etc.)
3. Identifies matching test failures (by test name) that appeared AFTER the dev branch regression
4. **Analyzes test failure similarity** using `ci:analyze-prow-job-test-failure` to confirm failures are happening for the **same reason**
5. Filters out false positives where the same test fails for different reasons
6. Highlights cases where a triaged regression is spreading backward with the same root cause
7. Provides actionable alerts to halt further backports

### Key Features

- **Test name matching**: Matches regressions across releases by test name to identify potential cascades
- **Similarity analysis**: Uses `ci:analyze-prow-job-test-failure` to compare actual error messages and root causes
- **Temporal analysis**: Detects when older release regressions appeared AFTER dev branch regression
- **False positive filtering**: Excludes cases where the same test fails for different, unrelated reasons
- **Triage linkage**: Prioritizes regressions that already have JIRA bugs filed
- **Smart filtering**: Excludes installation/infrastructure noise and Monitor tests by default
  - Monitor tests are invariant checks that fail for many different reasons
  - Excluding them reduces typical cascade count from ~25 to ~6, focusing on real functional failures
- **Actionable output**: Provides specific recommendations to halt problematic backports with similarity evidence

## Implementation

This command orchestrates three focused skills in sequence:

### Step 1: Detect Potential Cascades

Load the **"Detect Potential Cascades"** skill (`detect-potential-cascades`):

1. Auto-detect the current development release or use provided `--current-release`
2. Calculate the list of previous releases to scan based on `--lookback` parameter
3. Fetch regression data for all releases using `teams:list-regressions` skill
4. Match regressions by test name across releases
5. Check temporal ordering (older release regression appeared AFTER dev release)
6. Calculate severity based on cascade extent and triage status
7. Output potential cascades to `.work/detect-backport-regressions/potential_cascades.json`

### Step 2: Analyze Cascade Similarity

Load the **"Analyze Cascade Similarity"** skill (`analyze-cascade-similarity`):

1. Read potential cascades from Step 1
2. For each cascade, fetch Prow job URLs using `ci:fetch-regression-details`
3. Launch parallel Task agents to analyze each failure with `ci:prow-job-analyze-test-failure --fast`
4. Extract ANALYSIS_RESULT blocks from each agent
5. Compare root causes across releases (components, error patterns, summaries)
6. Calculate similarity scores and determine if same root cause
7. Output confirmed cascades and false positives to `.work/detect-backport-regressions/confirmed_cascades.json`

### Step 3: Generate Report

Load the **"Generate Cascade Report"** skill (`generate-cascade-report`):

1. Read confirmed cascades from Step 2
2. Generate report in requested format (HTML, Markdown, or JSON)
3. Include similarity analysis results and visualizations
4. Save HTML report to current working directory or output to stdout

## Return Value
**Converting `test_details_url` to UI URL**: The `test_details_url` from the API is an API endpoint not suitable for display or bug reports. Convert it to the UI URL by replacing the base path. The query parameters are identical:

   ```bash
   # Convert API URL to UI URL
   test_details_ui_url=$(echo "$test_details_url" | sed 's|https://sippy.dptools.openshift.org/api/component_readiness/test_details|https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/test_details|')
   ```

   Always use the converted `test_details_ui_url` when displaying the link in the report or including it in bug descriptions.

   See `plugins/ci/skills/fetch-regression-details/SKILL.md` for complete implementation details.

**Default Output**: Interactive HTML report saved to current working directory

**Available Formats**:
- **`--format html`** (default): Generates attractive, self-contained HTML file saved to current working directory
- **`--format markdown`**: Prints markdown report to stdout
- **`--format json`**: Prints JSON data to stdout for automation

### HTML Report Features

The default HTML report is an interactive, self-contained file generated with:
- **Executive Summary Dashboard**: Color-coded severity cards with total cascade counts
- **Collapsible Sections**: Click to expand/collapse each regression (critical/high auto-expanded)
- **Color-Coded Severity**: Visual indicators (red=critical, orange=high, yellow=medium, blue=low)
- **Interactive Tables**: Hover effects and clear data presentation
- **Embedded Links**: Direct links to Sippy regression details and JIRA bugs
- **Similarity Analysis**: Visual checkmarks showing confirmed matches across releases
- **Responsive Design**: Works on desktop and mobile browsers
- **Self-Contained**: All CSS and JavaScript embedded, no external dependencies

**Report Contents**:
- Executive summary with cascade statistics
- Per-regression cascade timelines showing progression from dev → older releases
- **Similarity analysis results** showing how failures match across releases
- Sample error messages and root causes from each release
- JIRA bug links and triage information
- Severity classification (CRITICAL/HIGH/MEDIUM/LOW)
- Recommended actions (halt specific backports, review recent changes)
- Component analysis showing which teams are affected

**Severity Levels**:
- **CRITICAL**: Triaged regression cascaded to 3+ older releases
- **HIGH**: Triaged regression cascaded to 2 older releases
- **MEDIUM**: Triaged regression cascaded to 1 older release
- **LOW**: Untriaged regression showing cascade pattern

## Examples

1. **Basic scan of current dev release and last 4 releases**:
   ```
   /ci:detect-backport-regressions
   ```

2. **Focus on specific component with extended lookback**:
   ```
   /ci:detect-backport-regressions --component kube-apiserver --lookback 6
   ```

3. **Only show critical cascades (2+ releases)**:
   ```
   /ci:detect-backport-regressions --min-cascade 2
   ```

4. **Include install failures, scan last 60 days**:
   ```
   /ci:detect-backport-regressions --exclude-install false --days 60
   ```

5. **Manual release override**:
   ```
   /ci:detect-backport-regressions --current-release 4.22 --lookback 3
   ```

6. **Show historical cascade patterns including resolved regressions**:
   ```
   /ci:detect-backport-regressions --include-resolved
   ```

7. **Generate markdown report to stdout**:
   ```
   /ci:detect-backport-regressions --format markdown --days 45
   ```

8. **Include Monitor tests (not recommended)**:
   ```
   /ci:detect-backport-regressions --exclude-monitor false
   ```
   Note: This will include Monitor/invariant tests which often create false positives

## Arguments

- `--current-release <version>` (optional): Override auto-detection of current dev release
  - Default: Auto-detect from Sippy API
  - Format: "4.22"

- `--lookback N` (optional): Number of previous releases to scan
  - Default: 4 (e.g., scan 4.21, 4.20, 4.19, 4.18)
  - Range: 1-6

- `--days N` (optional): Time window for cascade detection
  - Default: 30 days
  - Only flag older release regressions that appeared within last N days

- `--exclude-install` (optional): Exclude installation/infrastructure failures
  - Default: true
  - Set to `false` to include all failure types

- `--exclude-monitor` (optional): Exclude Monitor/invariant tests
  - Default: true
  - Set to `false` to include Monitor tests
  - Monitor tests are test framework invariant checks like `[Monitor:pod-network-availability]`
  - These tests fail for many different platform-specific and transient reasons
  - Excluding them reduces typical cascade count from ~25 to ~6, focusing on functional tests
  - **Recommended**: Keep this enabled (default) for most use cases

- `--component <name>` (optional): Focus on specific component
  - Example: `--component kube-apiserver`
  - Uses fuzzy matching (same as list-regressions)

- `--min-cascade N` (optional): Minimum number of releases cascade must affect
  - Default: 1
  - Example: `--min-cascade 2` only shows regressions in 2+ older releases

- `--format <html|markdown|json>` (optional): Output format
  - Default: html (saves interactive report to current working directory as `backport-regression-report_YYYYMMDD_HHMMSS.html`)
  - `markdown`: Plain text markdown report printed to stdout
  - `json`: Machine-readable output for automation (prints to stdout)

- `--include-resolved` (optional): Include resolved (closed) regressions in stable releases
  - Default: false (only show active cascades)
  - Set to `true` to see historical cascade patterns even if resolved
  - Note: Development release always includes both open and closed to find origin regressions

- `--analyze-similarity <true|false>` (optional): Enable automated similarity analysis
  - Default: true
  - When enabled, analyzes test failure outputs to confirm same root cause
  - Filters out false positives where same test fails for different reasons
  - Use `--analyze-similarity false` to skip similarity analysis and only match by test name

- `--similarity-threshold N` (optional): Minimum similarity score (0.0-1.0)
  - Default: 0.6
  - Only used when `--analyze-similarity` is enabled
  - Higher values require stricter matching (fewer false positives, more false negatives)

## Skills Used

This command orchestrates three main skills:

1. **`detect-potential-cascades`** - Identifies potential cascades by test name matching
   - Uses: `ci:fetch-releases`, `teams:list-regressions`
   - Output: `.work/detect-backport-regressions/potential_cascades.json`

2. **`analyze-cascade-similarity`** - Performs root cause analysis and similarity comparison
   - Uses: `ci:fetch-regression-details`, `ci:prow-job-analyze-test-failure` (via parallel Task agents)
   - Output: `.work/detect-backport-regressions/confirmed_cascades.json`
   - Skipped if `--analyze-similarity false` is specified

3. **`generate-cascade-report`** - Generates final report in requested format
   - Output: HTML file, Markdown to stdout, or JSON to stdout

## Prerequisites

1. **Python 3.6+**: Required to run the detection script
2. **Network access**: Must reach Sippy API endpoints
3. **Installed plugins**:
   - `ci` plugin (for fetch-releases skill)
   - `teams` plugin (for list-regressions skill)
