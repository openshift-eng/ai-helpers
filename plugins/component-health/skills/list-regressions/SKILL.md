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
```

### Step 4: Process the Output

The script outputs JSON data with the following structure:

```json
{
  "summary": {
    "total": <number>,
    "open": <number>,
    "closed": <number>
  },
  "components": {
    "ComponentName": {
      "summary": {
        "total": <number>,
        "open": <number>,
        "closed": <number>
      },
      "regressions": [...]
    }
  }
}
```

**CRITICAL**: The output includes pre-calculated counts:

- `summary`: Overall statistics across all components
  - `summary.total`: Total number of regressions
  - `summary.open`: Number of open regressions (where `closed` is null)
  - `summary.closed`: Number of closed regressions (where `closed` is not null)
- `components`: Dictionary mapping component names to objects containing:
  - `summary`: Per-component statistics (total, open, closed)
  - `regressions`: Array of regression objects for that component

**ALWAYS use these summary counts** rather than attempting to count the regression arrays yourself. This ensures accuracy even when the output is truncated due to size.

The script automatically simplifies time fields (`closed` and `last_failure`):

- Original API format: `{"Time": "2025-09-27T12:04:24.966914Z", "Valid": true}`
- Simplified format: `"closed": "2025-09-27T12:04:24.966914Z"` (if Valid is true)
- Or: `"closed": null` (if Valid is false)
- Same applies to `last_failure` field

Parse this JSON output to extract relevant information for analysis.

### Step 5: Generate Analysis (Optional)

Based on the regression data:

1. **Use the summary counts** from the `summary` and `components.*.summary` objects (do NOT count the arrays)
2. Identify most affected components using `components.*.summary`
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
    "open": 2,
    "closed": 60
  },
  "components": {
    "Monitoring": {
      "summary": {
        "total": 15,
        "open": 1,
        "closed": 14
      },
      "regressions": [
        {
          "id": 12893,
          "view": "4.21-main",
          "release": "4.21",
          "base_release": "4.18",
          "component": "Monitoring",
          "capability": "operator-conditions",
          "test_id": "...",
          "test_name": "...",
          "variants": [...],
          "opened": "2025-09-26T00:02:51.385944Z",
          "closed": "2025-09-27T12:04:24.966914Z",
          "triages": [],
          "last_failure": "2025-09-25T14:41:17Z",
          "max_failures": 9,
          "links": {...}
        }
      ]
    },
    "etcd": {
      "summary": {
        "total": 20,
        "open": 0,
        "closed": 20
      },
      "regressions": [...]
    },
    "kube-apiserver": {
      "summary": {
        "total": 27,
        "open": 1,
        "closed": 26
      },
      "regressions": [...]
    }
  }
}
```

**Important - Summary Objects**:

- The `summary` object contains overall pre-calculated counts for accuracy
- Each component in the `components` object has its own `summary` with per-component counts
- The `components` object maps component names (sorted alphabetically) to objects containing:
  - `summary`: Statistics for this component (total, open, closed)
  - `regressions`: Array of regression objects for that component
- **ALWAYS use `summary.*` and `components.*.summary.*`** for counts
- Do NOT attempt to count the `components.*.regressions` arrays yourself

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
