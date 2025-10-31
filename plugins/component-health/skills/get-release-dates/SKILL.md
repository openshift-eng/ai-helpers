---
name: Get Release Dates
description: Fetch OpenShift release dates and metadata from Sippy API
---

# Get Release Dates

This skill provides functionality to fetch OpenShift release information including GA dates and development start dates from the Sippy API.

## When to Use This Skill

Use this skill when you need to:

- Get GA (General Availability) date for a specific OpenShift release
- Find when development started for a release
- Identify the previous release in the sequence
- Validate if a release exists in Sippy
- Determine if a release is in development or has GA'd

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
plugins/component-health/skills/get-release-dates/get_release_dates.py
```

### Step 3: Run the Script

Execute the script with the release parameter:

```bash
# Get dates for release 4.21
python3 plugins/component-health/skills/get-release-dates/get_release_dates.py \
  --release 4.21

# Get dates for release 4.20
python3 plugins/component-health/skills/get-release-dates/get_release_dates.py \
  --release 4.20
```

### Step 4: Process the Output

The script outputs JSON data with the following structure:

```json
{
  "release": "4.21",
  "found": true,
  "ga": "2026-02-17T00:00:00Z",
  "development_start": "2025-09-02T00:00:00Z",
  "previous_release": "4.20"
}
```

**Field Descriptions**:

- `release`: The release identifier that was queried
- `found`: Boolean indicating if the release exists in Sippy
- `ga`: GA (General Availability) date. **If null, the release is still in development.**
- `development_start`: When development started for this release
- `previous_release`: The previous release in the sequence (empty string if none)

**If Release Not Found**:

```json
{
  "release": "99.99",
  "found": false
}
```

**Release Status - Development vs GA'd**:

- **In Development**: If `ga` is `null`, the release is still under active development
  ```json
  {
    "release": "4.21",
    "found": true,
    "development_start": "2025-09-02T00:00:00Z",
    "previous_release": "4.20"
  }
  ```
- **GA'd (Released)**: If `ga` has a timestamp, the release has reached General Availability
  ```json
  {
    "release": "4.17",
    "found": true,
    "ga": "2024-10-01T00:00:00Z",
    "development_start": "2024-05-17T00:00:00Z",
    "previous_release": "4.16"
  }
  ```

### Step 5: Use the Information

Based on the release dates:

1. **Determine release status**: Check if release is in development or GA'd
   - If `ga` is `null`: Release is still in development
   - If `ga` has a timestamp: Release has reached General Availability
2. **Determine release timeline**: Use `development_start` and `ga` dates
   - Calculate time in development: `ga` - `development_start`
   - For in-development releases: Calculate time since `development_start`
3. **Find related releases**: Use `previous_release` to navigate the release sequence
4. **Validate release**: Check `found` field before using the release in other operations

## Error Handling

The script handles several error scenarios:

1. **Network Errors**: If unable to reach Sippy API

   ```
   Error: URL Error: [reason]
   ```

2. **HTTP Errors**: If API returns an error status

   ```
   Error: HTTP Error 404: Not Found
   ```

3. **Invalid Release**: Script returns exit code 1 with `found: false` in output

4. **Parsing Errors**: If API response is malformed
   ```
   Error: Failed to fetch release dates: [details]
   ```

## Output Format

The script outputs JSON to stdout with:

- **Success**: Exit code 0, JSON with `found: true`
- **Release Not Found**: Exit code 1, JSON with `found: false`
- **Error**: Exit code 1, error message to stderr

## API Details

The script queries the Sippy releases API:

- **URL**: https://sippy.dptools.openshift.org/api/releases
- **Method**: GET
- **Response**: JSON containing all releases and their metadata

The full API response includes:

- `releases`: Array of all available release identifiers
- `ga_dates`: Simple mapping of release to GA date
- `dates`: Detailed mapping with GA and development_start dates
- `release_attrs`: Extended attributes including previous release

## Examples

### Example 1: Get Current Development Release

```bash
python3 plugins/component-health/skills/get-release-dates/get_release_dates.py \
  --release 4.21
```

Output:

```json
{
  "release": "4.21",
  "found": true,
  "development_start": "2025-09-02T00:00:00Z",
  "previous_release": "4.20"
}
```

### Example 2: Get GA'd Release

```bash
python3 plugins/component-health/skills/get-release-dates/get_release_dates.py \
  --release 4.17
```

Output:

```json
{
  "release": "4.17",
  "found": true,
  "ga": "2024-10-01T00:00:00Z",
  "development_start": "2024-05-17T00:00:00Z",
  "previous_release": "4.16"
}
```

### Example 3: Query Non-Existent Release

```bash
python3 plugins/component-health/skills/get-release-dates/get_release_dates.py \
  --release 99.99
```

Output:

```json
{
  "release": "99.99",
  "found": false
}
```

Exit code: 1

## Integration with Other Commands

This skill can be used in conjunction with other component-health skills:

1. **Before analyzing regressions**: Verify the release exists
2. **Timeline context**: Understand how long a release has been in development
3. **Release status**: Determine if a release is in development or has GA'd
4. **Release navigation**: Find previous/next releases in the sequence

## Notes

- The script uses Python's standard library only (no external dependencies)
- API responses are cached by Sippy, so repeated calls are fast
- Release identifiers are case-sensitive (use "4.21" not "4.21.0")
- OKD releases are suffixed with "-okd" (e.g., "4.21-okd")
- ARO releases have special identifiers (e.g., "aro-production")
- "Presubmits" is a special release for pull request data

## See Also

- Skill Documentation: `plugins/component-health/skills/list-regressions/SKILL.md`
- Sippy API: https://sippy.dptools.openshift.org/api/releases
- Component Health Plugin: `plugins/component-health/README.md`
