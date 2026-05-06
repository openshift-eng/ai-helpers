---
name: Detect Potential Cascades
description: Identify regressions that appear across multiple releases by matching test names and checking temporal ordering
---

# Detect Potential Cascades

This skill identifies regressions that have potentially cascaded backward from the current development release to older stable releases due to problematic backports. It performs test name matching across releases and checks temporal ordering to find potential cascades.

## When to Use This Skill

Use this skill when you need to:

- Identify regressions that started in a development branch and later appeared in older releases
- Find tests that are failing across multiple releases (test name matching only)
- Generate a list of potential cascade candidates for further similarity analysis
- Get initial cascade detection results quickly without deep root cause analysis

## Prerequisites

1. **Python 3.6+**: Required to run the helper skills
2. **Network Access**: Must be able to reach Sippy API endpoints
3. **Installed skills**:
   - `ci:fetch-releases` - Auto-detect current development release
   - `teams:list-regressions` - Fetch regression data for each release

## Implementation Steps

### Step 1: Determine Release Scope

**Auto-detect current development release** or use provided `--current-release`:

```bash
# Auto-detect latest release
release=$(python3 plugins/ci/skills/fetch-releases/fetch_releases.py --latest)
echo "Current development release: $release"
```

**Calculate lookback releases** from the current release:

```python
# Example: If current is 4.22 and lookback is 4
# Previous releases: 4.21, 4.20, 4.19, 4.18
major, minor = 4, 22
lookback_releases = [f"4.{minor - i}" for i in range(1, 5)]
# Result: ["4.21", "4.20", "4.19", "4.18"]
```

### Step 2: Fetch Regression Data for All Releases

Use `teams:list-regressions` to fetch regression data for the development release and all lookback releases. **Run these in parallel** for better performance.

**Calculate start date** if `--days` parameter is provided:

```bash
# For --days 45
start_date=$(date -d '45 days ago' +%Y-%m-%d)
```

**Fetch development release regressions** (include both open and closed):

```bash
python3 plugins/teams/skills/list-regressions/list_regressions.py \
  --release "$current_release" \
  --start "$start_date" \
  > .work/detect-backport-regressions/${current_release}.json
```

**Fetch older release regressions** (in parallel):

```bash
for release in 4.21 4.20 4.19 4.18; do
  python3 plugins/teams/skills/list-regressions/list_regressions.py \
    --release "$release" \
    --start "$start_date" \
    > .work/detect-backport-regressions/${release}.json &
done
wait
```

If `--component` is specified, add `--components "$component_name"` to the commands.

### Step 3: Build Development Release Regression Map

Parse the development release regression data and build a map keyed by test name:

```python
dev_regressions = {}  # test_name -> regression info

# Process both open and closed regressions in dev release
for component_name, component_data in dev_data["components"].items():
    for status in ["open", "closed"]:
        for regression in component_data[status]:
            test_name = regression["test_name"]

            # Filter: Exclude install failures if --exclude-install is true
            if exclude_install and (
                test_name.startswith("install should succeed") or
                regression["component"] == "cluster install"
            ):
                continue

            # Filter: Exclude Monitor/invariant tests (default: true)
            # Monitor tests are test framework invariant checks, not functional tests
            # They are prone to false positives as they fail for many different reasons
            if exclude_monitor and "Monitor:" in test_name:
                continue

            # Store earliest occurrence of this test in dev release
            if test_name not in dev_regressions:
                dev_regressions[test_name] = {
                    "release": current_release,
                    "test_name": test_name,
                    "component": regression["component"],
                    "capability": regression["capability"],
                    "opened": regression["opened"],  # ISO timestamp
                    "triages": regression["triages"],
                    "variants": regression["variants"],
                    "regression_id": regression["id"]
                }
            else:
                # If test appears multiple times, keep earliest opened timestamp
                # and merge triages from all occurrences
                if parse_timestamp(regression["opened"]) < parse_timestamp(dev_regressions[test_name]["opened"]):
                    dev_regressions[test_name]["opened"] = regression["opened"]
                    dev_regressions[test_name]["regression_id"] = regression["id"]

                # Merge triages
                for triage in regression["triages"]:
                    if triage not in dev_regressions[test_name]["triages"]:
                        dev_regressions[test_name]["triages"].append(triage)
```

### Step 4: Scan Older Releases for Matching Tests

For each older release, look for regressions with matching test names:

```python
cascades = {}  # test_name -> cascade info

for older_release in lookback_releases:
    # Parse regression data for this release
    older_data = load_json(f".work/detect-backport-regressions/{older_release}.json")

    # Check open regressions (and closed if --include-resolved is set)
    statuses_to_check = ["open", "closed"] if include_resolved else ["open"]

    for component_name, component_data in older_data["components"].items():
        for status in statuses_to_check:
            for regression in component_data[status]:
                test_name = regression["test_name"]

                # Skip if this test doesn't exist in dev release
                if test_name not in dev_regressions:
                    continue

                # Filter: Exclude Monitor/invariant tests (default: true)
                if exclude_monitor and "Monitor:" in test_name:
                    continue

                # Check temporal ordering: older release AFTER dev release?
                dev_opened = parse_timestamp(dev_regressions[test_name]["opened"])
                older_opened = parse_timestamp(regression["opened"])

                if older_opened <= dev_opened:
                    # Regression in older release appeared first or same time
                    # This is NOT a cascade - skip it
                    continue

                # Calculate time difference
                days_after_origin = (older_opened - dev_opened).days

                # Check if within time window
                if days_after_origin > days_window:
                    continue

                # This is a potential cascade!
                if test_name not in cascades:
                    cascades[test_name] = {
                        "origin": dev_regressions[test_name],
                        "cascade_releases": []
                    }

                # Add or update cascade release entry
                existing = find_cascade_release(cascades[test_name], older_release)
                if existing:
                    # Keep earliest timestamp for this release
                    if older_opened < parse_timestamp(existing["opened"]):
                        existing["opened"] = regression["opened"]
                        existing["days_after_origin"] = days_after_origin
                    # Merge triages
                    merge_triages(existing, regression["triages"])
                else:
                    cascades[test_name]["cascade_releases"].append({
                        "release": older_release,
                        "opened": regression["opened"],
                        "closed": regression.get("closed"),
                        "days_after_origin": days_after_origin,
                        "triages": regression["triages"],
                        "status": status,
                        "is_resolved": (status == "closed"),
                        "regression_id": regression["id"]
                    })
```

### Step 5: Calculate Severity and Filter

**Severity levels** based on cascade extent and triage status:

```python
def calculate_severity(num_cascade_releases, has_triage):
    if has_triage and num_cascade_releases >= 3:
        return "CRITICAL"  # Triaged + 3+ releases
    elif has_triage and num_cascade_releases >= 2:
        return "HIGH"      # Triaged + 2 releases
    elif has_triage and num_cascade_releases >= 1:
        return "MEDIUM"    # Triaged + 1 release
    else:
        return "LOW"       # No triage
```

**Filter by minimum cascade count** (if `--min-cascade` is specified):

```python
filtered_cascades = {
    test_name: info
    for test_name, info in cascades.items()
    if len(info["cascade_releases"]) >= min_cascade
}
```

### Step 6: Generate Output JSON

Create structured JSON output with all potential cascades:

```json
{
  "generated": "2026-04-02T21:09:32Z",
  "current_release": "4.22",
  "scanned_releases": ["4.21", "4.20", "4.19", "4.18"],
  "time_window_days": 45,
  "analysis_type": "test_name_matching",
  "similarity_analyzed": false,
  "potential_cascades": [
    {
      "test_name": "[sig-arch][Feature:ClusterUpgrade] Cluster should remain functional during upgrade",
      "severity": "CRITICAL",
      "origin": {
        "release": "4.22",
        "test_name": "...",
        "component": "Cluster Version Operator",
        "capability": "ClusterUpgrade",
        "opened": "2026-02-25T20:03:31.204512Z",
        "triages": [...],
        "variants": [...],
        "regression_id": 35926
      },
      "cascade_releases": [
        {
          "release": "4.21",
          "opened": "2026-03-25T08:05:05.990192Z",
          "closed": null,
          "days_after_origin": 27,
          "triages": [],
          "status": "open",
          "is_resolved": false,
          "regression_id": 36991
        },
        {
          "release": "4.20",
          "opened": "2026-03-31T00:05:27.771673Z",
          "closed": null,
          "days_after_origin": 33,
          "triages": [],
          "status": "open",
          "is_resolved": false,
          "regression_id": 37385
        }
      ],
      "regression_url": "https://sippy-auth.dptools.openshift.org/sippy-ng/component_readiness/regressions/35926",
      "needs_similarity_analysis": true
    }
  ]
}
```

**Save to file**:

```bash
cat > .work/detect-backport-regressions/potential_cascades.json <<< "$output_json"
```

## Output Format

The skill outputs JSON to stdout and saves it to `.work/detect-backport-regressions/potential_cascades.json`.

**Key fields**:
- `analysis_type`: Always "test_name_matching" for this skill
- `similarity_analyzed`: Always false (similarity analysis is done by separate skill)
- `potential_cascades`: Array of cascade objects
- `needs_similarity_analysis`: Always true for each cascade

## Parameters

These parameters should be passed from the command that invokes this skill:

- `--current-release <version>`: Override auto-detection (e.g., "4.22")
- `--lookback N`: Number of previous releases to scan (default: 4)
- `--days N`: Time window in days for cascade detection (default: 30)
- `--exclude-install true|false`: Exclude installation failures (default: true)
- `--exclude-monitor true|false`: Exclude Monitor/invariant tests (default: true)
  - Monitor tests are test framework invariant checks like `[Monitor:pod-network-availability]`
  - These tests are prone to false positives as they fail for many different reasons
  - Excluding them significantly reduces noise and focuses on functional test failures
- `--component <name>`: Filter by component name
- `--min-cascade N`: Minimum cascade count to report (default: 1)
- `--include-resolved`: Include closed regressions in stable releases (default: false)

## Exit Codes

- `0`: Success (cascades found or no cascades)
- `1`: General error
- `2`: Missing dependencies or configuration error
- `3`: Critical cascades detected (3+ releases affected)
- `130`: Interrupted by user (Ctrl+C)

## Example Usage

This skill is typically invoked by the `detect-backport-regressions` command, but can also be used standalone:

```bash
# Basic usage
# Agent reads this skill and executes the steps above

# With parameters
# --current-release 4.22 --lookback 4 --days 45 --min-cascade 2
```

## Notes

- This skill performs **test name matching only** - it does NOT analyze root causes
- All potential cascades have `needs_similarity_analysis: true`
- Use `analyze-cascade-similarity` skill to confirm which cascades are real
- The skill creates working directory `.work/detect-backport-regressions/` if it doesn't exist
- Regression data files are cached in `.work/detect-backport-regressions/{release}.json`
- **Monitor test exclusion** (enabled by default) significantly reduces false positives:
  - Reduces cascade count from ~25 to ~6 typical cases
  - Focuses on functional tests rather than invariant checks
  - Monitor tests fail for many platform-specific and transient reasons

## See Also

- `analyze-cascade-similarity` - Perform root cause analysis on potential cascades
- `generate-cascade-report` - Generate HTML/Markdown reports from confirmed cascades
- `ci:fetch-releases` - Get available OpenShift releases
- `teams:list-regressions` - Fetch regression data for a release
