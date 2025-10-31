---
name: List Regressions
description: Fetch and analyze component health regressions for OpenShift releases
---

# List Regressions

This skill provides functionality to fetch regression data for OpenShift components across different releases. It uses a Python script to query a component health API and retrieve regression information.

## When to Use This Skill

Use this skill when you need to:

- Analyze component health for a specific OpenShift release
- Track regressions across releases
- Filter regressions by their open/closed status
- Generate reports on component stability

## Prerequisites

1. **Python 3 Installation**

   - Check if installed: `which python3`
   - Python 3.6 or later is required
   - Comes pre-installed on most systems

2. **Network Access**

   - The script requires network access to reach the component health API
   - Ensure you can make HTTPS requests

3. **API Endpoint Configuration**
   - The script includes a placeholder API endpoint that needs to be updated
   - Update the `base_url` in `list_regressions.py` with the actual component health API endpoint

## Implementation Steps

### Step 1: Verify Prerequisites

First, ensure Python 3 is available:

```bash
python3 --version
```

If Python 3 is not installed, guide the user through installation for their platform.

### Step 2: Locate the Script

The script is located at:

```
plugins/component-health/skills/list-regressions/list_regressions.py
```

### Step 3: Run the Script

Execute the script with appropriate arguments:

```bash
# Basic usage - all regressions for a release
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.17

# Filter by specific components
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.21 \
  --components Monitoring "kube-apiserver"

# Filter by multiple components
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.21 \
  --components Monitoring etcd "kube-apiserver"

# Filter by development window (GA'd release - both start and end)
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.17 \
  --start 2024-05-17 \
  --end 2024-10-01

# Filter by development window (in-development release - start only)
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.21 \
  --start 2025-09-02
```

### Step 4: Process the Output

The script outputs JSON data with the following structure:

```json
{
  "summary": {
    "total": <number>,
    "triaged": <number>,
    "triage_percentage": <number>,
    "time_to_triage_hrs_avg": <number or null>,
    "time_to_triage_hrs_max": <number or null>,
    "time_to_close_hrs_avg": <number or null>,
    "time_to_close_hrs_max": <number or null>,
    "open": {
      "total": <number>,
      "triaged": <number>,
      "triage_percentage": <number>,
      "time_to_triage_hrs_avg": <number or null>,
      "time_to_triage_hrs_max": <number or null>,
      "open_hrs_avg": <number or null>,
      "open_hrs_max": <number or null>
    },
    "closed": {
      "total": <number>,
      "triaged": <number>,
      "triage_percentage": <number>,
      "time_to_triage_hrs_avg": <number or null>,
      "time_to_triage_hrs_max": <number or null>,
      "time_to_close_hrs_avg": <number or null>,
      "time_to_close_hrs_max": <number or null>,
      "time_triaged_closed_hrs_avg": <number or null>,
      "time_triaged_closed_hrs_max": <number or null>
    }
  },
  "components": {
    "ComponentName": {
      "summary": {
        "total": <number>,
        "triaged": <number>,
        "triage_percentage": <number>,
        "time_to_triage_hrs_avg": <number or null>,
        "time_to_triage_hrs_max": <number or null>,
        "time_to_close_hrs_avg": <number or null>,
        "time_to_close_hrs_max": <number or null>,
        "open": {
          "total": <number>,
          "triaged": <number>,
          "triage_percentage": <number>,
          "time_to_triage_hrs_avg": <number or null>,
          "time_to_triage_hrs_max": <number or null>,
          "open_hrs_avg": <number or null>,
          "open_hrs_max": <number or null>
        },
        "closed": {
          "total": <number>,
          "triaged": <number>,
          "triage_percentage": <number>,
          "time_to_triage_hrs_avg": <number or null>,
          "time_to_triage_hrs_max": <number or null>,
          "time_to_close_hrs_avg": <number or null>,
          "time_to_close_hrs_max": <number or null>,
          "time_triaged_closed_hrs_avg": <number or null>,
          "time_triaged_closed_hrs_max": <number or null>
        }
      },
      "open": [...],
      "closed": [...]
    }
  }
}
```

**CRITICAL**: The output includes pre-calculated counts and health metrics:

- `summary`: Overall statistics across all components
  - `summary.total`: Total number of regressions
  - `summary.triaged`: Total number of regressions triaged (open + closed)
  - **`summary.triage_percentage`**: Percentage of all regressions that have been triaged (KEY HEALTH METRIC)
  - **`summary.time_to_triage_hrs_avg`**: Overall average hours to triage (combining open and closed, KEY HEALTH METRIC)
  - `summary.time_to_triage_hrs_max`: Overall maximum hours to triage
  - **`summary.time_to_close_hrs_avg`**: Overall average hours to close regressions (closed only, KEY HEALTH METRIC)
  - `summary.time_to_close_hrs_max`: Overall maximum hours to close regressions (closed only)
  - `summary.open.total`: Number of open regressions (where `closed` is null)
  - `summary.open.triaged`: Number of open regressions that have been triaged to a JIRA bug
  - `summary.open.triage_percentage`: Percentage of open regressions triaged
  - `summary.open.time_to_triage_hrs_avg`: Average hours from opened to first triage (open only)
  - `summary.open.time_to_triage_hrs_max`: Maximum hours from opened to first triage (open only)
  - `summary.open.open_hrs_avg`: Average hours that open regressions have been open (from opened to current time)
  - `summary.open.open_hrs_max`: Maximum hours that open regressions have been open (from opened to current time)
  - `summary.closed.total`: Number of closed regressions (where `closed` is not null)
  - `summary.closed.triaged`: Number of closed regressions that have been triaged to a JIRA bug
  - `summary.closed.triage_percentage`: Percentage of closed regressions triaged
  - `summary.closed.time_to_triage_hrs_avg`: Average hours from opened to first triage (closed only)
  - `summary.closed.time_to_triage_hrs_max`: Maximum hours from opened to first triage (closed only)
  - `summary.closed.time_to_close_hrs_avg`: Average hours from opened to closed timestamp (null if no valid data)
  - `summary.closed.time_to_close_hrs_max`: Maximum hours from opened to closed timestamp (null if no valid data)
  - `summary.closed.time_triaged_closed_hrs_avg`: Average hours from first triage to closed (null if no triaged closed regressions)
  - `summary.closed.time_triaged_closed_hrs_max`: Maximum hours from first triage to closed (null if no triaged closed regressions)
- `components`: Dictionary mapping component names to objects containing:
  - `summary`: Per-component statistics (includes same fields as overall summary)
  - `open`: Array of open regression objects for that component
  - `closed`: Array of closed regression objects for that component

**Time to Triage Calculation**:

The `time_to_triage_hrs_avg` field is calculated as:

1. For each triaged regression, find the earliest `created_at` timestamp in the `triages` array
2. Calculate the time difference between the regression's `opened` timestamp and the earliest triage timestamp
3. Convert the difference to hours and round to the nearest hour
4. Only include positive time differences (zero or negative values are skipped - these occur when triages are reused across regression instances)
5. Average all valid time-to-triage values for open regressions separately from closed regressions
6. Return `null` if no regressions have valid time-to-triage data in that category

**Time to Close Calculation**:

The `time_to_close_hrs_avg` and `time_to_close_hrs_max` fields (only for closed regressions) are calculated as:

1. For each closed regression, calculate the time difference between `opened` and `closed` timestamps
2. Convert the difference to hours and round to the nearest hour
3. Only include positive time differences (skip data inconsistencies)
4. Calculate average and maximum of all valid time-to-close values
5. Return `null` if no closed regressions have valid time data

**Open Duration Calculation**:

The `open_hrs_avg` and `open_hrs_max` fields (only for open regressions) are calculated as:

1. For each open regression, calculate the time difference between `opened` timestamp and current time
2. Convert the difference to hours and round to the nearest hour
3. Only include positive time differences
4. Calculate average and maximum of all open duration values
5. Return `null` if no open regressions have valid time data

**Time Triaged to Closed Calculation**:

The `time_triaged_closed_hrs_avg` and `time_triaged_closed_hrs_max` fields (only for triaged closed regressions) are calculated as:

1. For each closed regression that has been triaged, calculate the time difference between earliest `triages.created_at` timestamp and `closed` timestamp
2. Convert the difference to hours and round to the nearest hour
3. Only include positive time differences
4. Calculate average and maximum of all triaged-to-closed values
5. Return `null` if no triaged closed regressions have valid time data

**ALWAYS use these summary counts** rather than attempting to count the regression arrays yourself. This ensures accuracy even when the output is truncated due to size.

The script automatically simplifies and optimizes the response:

**Time field simplification** (`closed` and `last_failure`):

- Original API format: `{"Time": "2025-09-27T12:04:24.966914Z", "Valid": true}`
- Simplified format: `"closed": "2025-09-27T12:04:24.966914Z"` (if Valid is true)
- Or: `"closed": null` (if Valid is false)
- Same applies to `last_failure` field

**Field removal for response size optimization**:

- `links`: Removed from each regression (reduces response size significantly)
- `test_id`: Removed from each regression (large field, can be reconstructed from test_name if needed)

**Date filtering (optional)**:

- Use `--start` and `--end` parameters to filter regressions to a specific time window
- `--start YYYY-MM-DD`: Excludes regressions that were closed before this date
- `--end YYYY-MM-DD`: Excludes regressions that were opened after this date
- Typical use case: Filter to the development window
  - `--start`: development_start date from get-release-dates skill (always applied)
  - `--end`: GA date from get-release-dates skill (only for GA'd releases)
- For GA'd releases: Both start and end filtering applied
- For in-development releases (null GA date): Only start filtering applied (no end date)
- Benefits: Focuses analysis on regressions during active development, excluding:
  - Regressions closed before the release development started (not relevant)
  - Regressions opened after GA (post-release, often not monitored/triaged - GA'd releases only)

Parse this JSON output to extract relevant information for analysis.

### Step 5: Generate Analysis (Optional)

Based on the regression data:

1. **Use the summary counts** from the `summary` and `components.*.summary` objects (do NOT count the arrays)
2. Identify most affected components using `components.*.summary.open.total`
3. Compare with previous releases
4. Analyze trends in open vs closed regressions per component
5. Create visualizations if needed

## Error Handling

### Common Errors

1. **Network Errors**

   - **Symptom**: `URLError` or connection timeout
   - **Solution**: Check network connectivity and firewall rules
   - **Retry**: The script has a 30-second timeout, consider retrying

2. **HTTP Errors**

   - **Symptom**: HTTP 404, 500, etc.
   - **Solution**: Verify the API endpoint URL is correct
   - **Check**: Ensure the release parameter is valid

3. **Invalid Release**

   - **Symptom**: Empty results or error response
   - **Solution**: Verify the release format (e.g., "4.17", not "v4.17")

4. **Invalid Boolean Value**
   - **Symptom**: `ValueError: Invalid boolean value`
   - **Solution**: Use only "true" or "false" for the --opened flag

### Debugging

Enable verbose output by examining stderr:

```bash
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.17 2>&1 | tee debug.log
```

## Script Arguments

### Required Arguments

- `--release`: Release version to query
  - Format: `"X.Y"` (e.g., "4.17", "4.16")
  - Must be a valid OpenShift release number

### Optional Arguments

- `--components`: Filter by component names
  - Values: Space-separated list of component names
  - Default: None (returns all components)
  - Case-insensitive matching
  - Examples: `--components Monitoring etcd "kube-apiserver"`
  - Filtering is performed after fetching data from the API

## Output Format

The script outputs JSON with summaries and regressions grouped by component:

```json
{
  "summary": {
    "total": 62,
    "triaged": 59,
    "triage_percentage": 95.2,
    "time_to_triage_hrs_avg": 68,
    "time_to_triage_hrs_max": 240,
    "time_to_close_hrs_avg": 168,
    "time_to_close_hrs_max": 480,
    "open": {
      "total": 2,
      "triaged": 1,
      "triage_percentage": 50.0,
      "time_to_triage_hrs_avg": 48,
      "time_to_triage_hrs_max": 48,
      "open_hrs_avg": 120,
      "open_hrs_max": 200
    },
    "closed": {
      "total": 60,
      "triaged": 58,
      "triage_percentage": 96.7,
      "time_to_triage_hrs_avg": 72,
      "time_to_triage_hrs_max": 240,
      "time_to_close_hrs_avg": 168,
      "time_to_close_hrs_max": 480,
      "time_triaged_closed_hrs_avg": 96,
      "time_triaged_closed_hrs_max": 240
    }
  },
  "components": {
    "Monitoring": {
      "summary": {
        "total": 15,
        "triaged": 13,
        "triage_percentage": 86.7,
        "time_to_triage_hrs_avg": 68,
        "time_to_triage_hrs_max": 180,
        "time_to_close_hrs_avg": 156,
        "time_to_close_hrs_max": 360,
        "open": {
          "total": 1,
          "triaged": 0,
          "triage_percentage": 0.0,
          "time_to_triage_hrs_avg": null,
          "time_to_triage_hrs_max": null,
          "open_hrs_avg": 72,
          "open_hrs_max": 72
        },
        "closed": {
          "total": 14,
          "triaged": 13,
          "triage_percentage": 92.9,
          "time_to_triage_hrs_avg": 68,
          "time_to_triage_hrs_max": 180,
          "time_to_close_hrs_avg": 156,
          "time_to_close_hrs_max": 360,
          "time_triaged_closed_hrs_avg": 88,
          "time_triaged_closed_hrs_max": 180
        }
      },
      "open": [
        {
          "id": 12894,
          "component": "Monitoring",
          "closed": null,
          ...
        }
      ],
      "closed": [
        {
          "id": 12893,
          "view": "4.21-main",
          "release": "4.21",
          "base_release": "4.18",
          "component": "Monitoring",
          "capability": "operator-conditions",
          "test_name": "...",
          "variants": [...],
          "opened": "2025-09-26T00:02:51.385944Z",
          "closed": "2025-09-27T12:04:24.966914Z",
          "triages": [],
          "last_failure": "2025-09-25T14:41:17Z",
          "max_failures": 9
        }
      ]
    },
    "etcd": {
      "summary": {
        "total": 20,
        "triaged": 19,
        "triage_percentage": 95.0,
        "time_to_triage_hrs_avg": 84,
        "time_to_triage_hrs_max": 220,
        "time_to_close_hrs_avg": 192,
        "time_to_close_hrs_max": 500,
        "open": {
          "total": 0,
          "triaged": 0,
          "triage_percentage": 0.0,
          "time_to_triage_hrs_avg": null,
          "time_to_triage_hrs_max": null,
          "open_hrs_avg": null,
          "open_hrs_max": null
        },
        "closed": {
          "total": 20,
          "triaged": 19,
          "triage_percentage": 95.0,
          "time_to_triage_hrs_avg": 84,
          "time_to_triage_hrs_max": 220,
          "time_to_close_hrs_avg": 192,
          "time_to_close_hrs_max": 500,
          "time_triaged_closed_hrs_avg": 108,
          "time_triaged_closed_hrs_max": 280
        }
      },
      "open": [],
      "closed": [...]
    },
    "kube-apiserver": {
      "summary": {
        "total": 27,
        "triaged": 27,
        "triage_percentage": 100.0,
        "time_to_triage_hrs_avg": 58,
        "time_to_triage_hrs_max": 168,
        "time_to_close_hrs_avg": 144,
        "time_to_close_hrs_max": 400,
        "open": {
          "total": 1,
          "triaged": 1,
          "triage_percentage": 100.0,
          "time_to_triage_hrs_avg": 36,
          "time_to_triage_hrs_max": 36,
          "open_hrs_avg": 96,
          "open_hrs_max": 96
        },
        "closed": {
          "total": 26,
          "triaged": 26,
          "triage_percentage": 100.0,
          "time_to_triage_hrs_avg": 60,
          "time_to_triage_hrs_max": 168,
          "time_to_close_hrs_avg": 144,
          "time_to_close_hrs_max": 400,
          "time_triaged_closed_hrs_avg": 84,
          "time_triaged_closed_hrs_max": 232
        }
      },
      "open": [...],
      "closed": [...]
    }
  }
}
```

**Important - Summary Objects**:

- The `summary` object contains overall pre-calculated counts for accuracy
- Each component in the `components` object has its own `summary` with per-component counts
- The `components` object maps component names (sorted alphabetically) to objects containing:
  - `summary`: Statistics for this component (total, open, closed)
  - `open`: Array of open regression objects (where `closed` is null)
  - `closed`: Array of closed regression objects (where `closed` has a timestamp)
- **ALWAYS use the `summary` and `components.*.summary` fields** for counts (including `total`, `open.total`, `open.triaged`, `closed.total`, `closed.triaged`)
- Do NOT attempt to count the `components.*.open` or `components.*.closed` arrays yourself

**Note**: Time fields are simplified from the API response:

- `closed`: If the regression is closed: `"closed": "2025-09-27T12:04:24.966914Z"` (timestamp string), otherwise `null`
- `last_failure`: If valid: `"last_failure": "2025-09-25T14:41:17Z"` (timestamp string), otherwise `null`

## Examples

### Example 1: List All Regressions

```bash
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.17
```

**Expected Output**: JSON containing all regressions for release 4.17

### Example 2: Filter by Component

```bash
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.21 \
  --components Monitoring etcd
```

**Expected Output**: JSON containing regressions for only Monitoring and etcd components in release 4.21

### Example 3: Filter by Single Component

```bash
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.21 \
  --components "kube-apiserver"
```

**Expected Output**: JSON containing regressions for the kube-apiserver component in release 4.21

## Customization

### Updating the API Endpoint

The script includes a placeholder API endpoint. Update it in `list_regressions.py`:

```python
# Current placeholder
base_url = f"https://component-health-api.example.com/api/v1/regressions"

# Update to actual endpoint
base_url = f"https://actual-api.example.com/api/v1/regressions"
```

### Adding Custom Filters

To add additional query parameters, modify the `fetch_regressions` function:

```python
def fetch_regressions(release: str, opened: Optional[bool] = None,
                     component: Optional[str] = None) -> dict:
    params = [f"release={release}"]
    if opened is not None:
        params.append(f"opened={'true' if opened else 'false'}")
    if component is not None:
        params.append(f"component={component}")
    # ... rest of function
```

## Integration with Commands

This skill is designed to be used by the `/component-health:analyze-regressions` command, but can also be invoked directly by other commands or scripts that need regression data.

## Related Skills

- Component health analysis
- Release comparison
- Regression tracking
- Quality metrics reporting

## Notes

- The script uses Python's built-in `urllib` module (no external dependencies)
- Output is always JSON format for easy parsing
- Diagnostic messages are written to stderr, data to stdout
- The script has a 30-second timeout for HTTP requests
