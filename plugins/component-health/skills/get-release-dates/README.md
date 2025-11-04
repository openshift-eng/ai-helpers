# Get Release Dates

Fetch OpenShift release dates and metadata from the Sippy API.

## Overview

This skill retrieves release information for OpenShift releases, including:

- GA (General Availability) dates
- Development start dates
- Previous release in the sequence
- Release status (in development vs GA'd)

## Usage

```bash
python3 plugins/component-health/skills/get-release-dates/get_release_dates.py \
  --release <release>
```

## Arguments

- `--release` (required): Release identifier (e.g., "4.21", "4.20", "4.17")

## Examples

### Get information for release 4.21

```bash
python3 plugins/component-health/skills/get-release-dates/get_release_dates.py \
  --release 4.21
```

### Get information for release 4.17

```bash
python3 plugins/component-health/skills/get-release-dates/get_release_dates.py \
  --release 4.17
```

## Output Format

### Successful Query (Release Found)

```json
{
  "release": "4.21",
  "found": true,
  "ga": "2026-02-17T00:00:00Z",
  "development_start": "2025-09-02T00:00:00Z",
  "previous_release": "4.20"
}
```

### Release Not Found

```json
{
  "release": "99.99",
  "found": false
}
```

Exit code: 1

## Output Fields

- `release`: The release identifier queried
- `found`: Boolean indicating if release exists in Sippy
- `ga`: GA date. **Null means release is still in development.**
- `development_start`: When development started
- `previous_release`: Previous release in sequence

**Note**: If the `ga` field is `null`, the release is still under active development and has not reached General Availability yet.

## Prerequisites

- Python 3.6 or later
- Network access to `sippy.dptools.openshift.org`

## API Endpoint

The script queries: https://sippy.dptools.openshift.org/api/releases

## Use Cases

### Verify Release Exists

Before analyzing a release, verify it exists in Sippy:

```bash
python3 get_release_dates.py --release 4.21
# Check "found": true in output
```

### Get Release Timeline

Understand the development timeline:

```bash
python3 get_release_dates.py --release 4.17
# Check "development_start" and "ga" dates
```

### Determine Release Status

Check if a release is in development or has GA'd:

```bash
python3 get_release_dates.py --release 4.21
# If "ga" is null -> still in development
# If "ga" has timestamp -> has reached GA
```

## Error Handling

The script handles:

- Network errors (connection failures)
- HTTP errors (404, 500, etc.)
- Release not found (exit code 1)
- Invalid JSON responses

## Notes

- Uses Python standard library only (no external dependencies)
- Release identifiers are case-sensitive
- OKD releases use "-okd" suffix (e.g., "4.21-okd")
- Special releases: "Presubmits", "aro-production", "aro-stage", "aro-integration"

## See Also

- SKILL.md: Detailed implementation guide
- Component Health Plugin: `plugins/component-health/README.md`
- List Regressions Skill: `plugins/component-health/skills/list-regressions/`
