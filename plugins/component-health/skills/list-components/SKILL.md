---
name: List Components
description: Fetch component names from Sippy component readiness API
---

# List Components

This skill provides functionality to fetch a list of all component names tracked in the Sippy component readiness system for a specific OpenShift release.

## When to Use This Skill

Use this skill when you need to:

- Get a complete list of components for a specific release
- Validate component names before querying regression or bug data
- Discover available components for analysis
- Generate component lists for reports or documentation
- Understand which teams/components are tracked in Sippy
- Provide autocomplete suggestions for component names

## Prerequisites

1. **Python 3 Installation**

   - Check if installed: `which python3`
   - Python 3.6 or later is required
   - Comes pre-installed on most systems

2. **Network Access**

   - The script requires network access to reach the Sippy API
   - Ensure you can make HTTPS requests to `sippy.dptools.openshift.org`

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
plugins/component-health/skills/list-components/list_components.py
```

### Step 3: Run the Script

Execute the script with the release parameter:

```bash
# Get components for release 4.21
python3 plugins/component-health/skills/list-components/list_components.py \
  --release 4.21

# Get components for release 4.20
python3 plugins/component-health/skills/list-components/list_components.py \
  --release 4.20
```

**Important**: The script automatically appends "-main" to the release version to construct the view parameter (e.g., "4.21" becomes "4.21-main").

### Step 4: Process the Output

The script outputs JSON data with the following structure:

```json
{
  "release": "4.21",
  "view": "4.21-main",
  "component_count": 42,
  "components": [
    "API",
    "Build",
    "Cloud Compute",
    "Cluster Version Operator",
    "Etcd",
    "Image Registry",
    "Installer",
    "Kubernetes",
    "Management Console",
    "Monitoring",
    "Networking",
    "OLM",
    "Storage",
    "etcd",
    "kube-apiserver",
    "..."
  ]
}
```

**Field Descriptions**:

- `release`: The release identifier that was queried
- `view`: The constructed view parameter used in the API call (release + "-main")
- `component_count`: Total number of unique components found
- `components`: Alphabetically sorted array of unique component names

**If View Not Found**:

If the release view doesn't exist, the script will return an HTTP 404 error:

```
HTTP Error 404: Not Found
View '4.99-main' not found. Please check the release version.
```

### Step 5: Use the Component List

Based on the component list, you can:

1. **Validate component names**: Check if a component exists before querying data
2. **Generate documentation**: Create component lists for reports
3. **Filter queries**: Use component names to filter regression or bug queries
4. **Autocomplete**: Provide suggestions when users type component names
5. **Discover teams**: Understand which components/teams are tracked

## Error Handling

The script handles several error scenarios:

1. **Network Errors**: If unable to reach Sippy API

   ```
   Error: URL Error: [reason]
   ```

2. **HTTP Errors**: If API returns an error status

   ```
   Error: HTTP Error 404: Not Found
   View '4.99-main' not found. Please check the release version.
   ```

3. **Invalid Release**: Script returns exit code 1 with error message

4. **Parsing Errors**: If API response is malformed
   ```
   Error: Failed to fetch components: [details]
   ```

## Output Format

The script outputs JSON to stdout with:

- **Success**: Exit code 0, JSON with component list
- **Error**: Exit code 1, error message to stderr

Diagnostic messages (like "Fetching components from...") are written to stderr, so they don't interfere with JSON parsing.

## API Details

The script queries the Sippy component readiness API:

- **URL**: `https://sippy.dptools.openshift.org/api/component_readiness?view={release}-main`
- **Method**: GET
- **Response**: JSON containing component readiness data with rows

The API response structure includes:

```json
{
  "rows": [
    {
      "component": "Networking",
      ...
    },
    {
      "component": "Monitoring",
      ...
    }
  ],
  ...
}
```

The script:

1. Extracts the `component` field from each row
2. Filters out empty/null component names
3. Returns unique components, sorted alphabetically

## Examples

### Example 1: Get Components for 4.21

```bash
python3 plugins/component-health/skills/list-components/list_components.py \
  --release 4.21
```

Output:

```json
{
  "release": "4.21",
  "view": "4.21-main",
  "component_count": 42,
  "components": ["API", "Build", "Etcd", "..."]
}
```

### Example 2: Query Non-Existent Release

```bash
python3 plugins/component-health/skills/list-components/list_components.py \
  --release 99.99
```

Output (to stderr):

```
Fetching components from: https://sippy.dptools.openshift.org/api/component_readiness?view=99.99-main
HTTP Error 404: Not Found
View '99.99-main' not found. Please check the release version.
Failed to fetch components: HTTP Error 404: Not Found
```

Exit code: 1

## Integration with Other Commands

This skill can be used in conjunction with other component-health skills:

1. **Before analyzing components**: Validate component names exist
2. **Component discovery**: Find available components for a release
3. **Autocomplete**: Provide component name suggestions to users
4. **Batch operations**: Iterate over all components for comprehensive analysis

**Example Integration**:

```bash
# Get all components for 4.21
COMPONENTS=$(python3 plugins/component-health/skills/list-components/list_components.py \
  --release 4.21 | jq -r '.components[]')

# Analyze each component
for component in $COMPONENTS; do
  echo "Analyzing $component..."
  # Use component in other commands
done
```

## Notes

- The script uses Python's standard library only (no external dependencies)
- The script automatically appends "-main" to the release version
- Component names are case-sensitive
- Component names are returned in alphabetical order
- Duplicate component names are automatically removed
- Empty or null component names are filtered out
- The script has a 30-second timeout for HTTP requests
- Diagnostic messages go to stderr, JSON output goes to stdout

## See Also

- Related Skill: `plugins/component-health/skills/list-regressions/SKILL.md`
- Related Skill: `plugins/component-health/skills/get-release-dates/SKILL.md`
- Related Command: `/component-health:list-regressions` (for regression data)
- Related Command: `/component-health:analyze` (for health grading)
- Sippy API: https://sippy.dptools.openshift.org/api/component_readiness
- Component Health Plugin: `plugins/component-health/README.md`
