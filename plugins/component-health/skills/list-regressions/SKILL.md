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

# Filter for only open regressions
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.17 \
  --opened true

# Filter for closed regressions
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.16 \
  --opened false

# Filter by specific components
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.21 \
  --components Monitoring "kube-apiserver"

# Combine filters - open regressions for specific components
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.21 \
  --opened true \
  --components Monitoring etcd
```

### Step 4: Process the Output

The script outputs JSON data containing regression information. The output includes:

- Regression details
- Component information
- Status information
- Timestamps

The script automatically simplifies time fields (`closed` and `last_failure`):

- Original API format: `{"Time": "2025-09-27T12:04:24.966914Z", "Valid": true}`
- Simplified format: `"closed": "2025-09-27T12:04:24.966914Z"` (if Valid is true)
- Or: `"closed": null` (if Valid is false)
- Same applies to `last_failure` field

Parse this JSON output to extract relevant information for analysis.

### Step 5: Generate Analysis (Optional)

Based on the regression data:

1. Count total regressions
2. Identify most affected components
3. Compare with previous releases
4. Generate summary statistics
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

- `--opened`: Filter by regression status

  - Values: `"true"` or `"false"`
  - Default: None (returns all regressions)
  - `"true"`: Returns only open regressions
  - `"false"`: Returns only closed regressions

- `--components`: Filter by component names
  - Values: Space-separated list of component names
  - Default: None (returns all components)
  - Case-insensitive matching
  - Examples: `--components Monitoring etcd "kube-apiserver"`
  - Filtering is performed after fetching data from the API

## Output Format

The script outputs JSON as a list of regressions with the following structure:

```json
[
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
```

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

### Example 2: List Open Regressions Only

```bash
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.17 \
  --opened true
```

**Expected Output**: JSON containing only open regressions for release 4.17

### Example 3: List Closed Regressions

```bash
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.16 \
  --opened false
```

**Expected Output**: JSON containing only closed regressions for release 4.16

### Example 4: Filter by Component

```bash
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.21 \
  --components Monitoring etcd
```

**Expected Output**: JSON containing regressions for only Monitoring and etcd components in release 4.21

### Example 5: Combine Filters

```bash
python3 plugins/component-health/skills/list-regressions/list_regressions.py \
  --release 4.21 \
  --opened true \
  --components "kube-apiserver"
```

**Expected Output**: JSON containing only open regressions for the kube-apiserver component in release 4.21

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

This skill is designed to be used by the `/component-health:list-regressions` command, but can also be invoked directly by other commands or scripts that need regression data.

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
