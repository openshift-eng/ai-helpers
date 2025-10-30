---
name: Extract MicroShift Version
description: Extract MicroShift version and build type from Prow CI build logs
---

# Extract MicroShift Version

This skill provides a utility script for extracting the exact MicroShift version and build type from Prow CI job artifacts.

## When to Use This Skill

Use this skill whenever you need to:
- Extract the exact MicroShift version being tested in a Prow CI job
- Determine the build type (nightly, rc, ec, zstream) from a job
- Parse version information from build logs programmatically
- Retrieve version metadata for reporting purposes

This skill is used by commands that need to:
- Display version information in job summaries
- Correlate test results with specific MicroShift builds
- Generate release testing reports with version details

## Prerequisites

1. **Python 3 Installation**
   - Check if installed: `which python3`
   - The script uses only standard library modules (sys, json, re, urllib)
   - No additional dependencies required

2. **Network Access**
   - Scripts need access to `gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com`
   - Used to fetch build logs from Prow CI artifact storage

## Available Scripts

### Script: `extract_microshift_version.py`

Extracts the exact MicroShift version and build type from Prow CI job artifacts.

**Usage:**
```bash
python3 plugins/microshift-prow-job/skills/extract-microshift-version/extract_microshift_version.py <job_id> <version> <job_type>
```

**Parameters:**
- `job_id`: The Prow CI job ID (e.g., "1982281180531134464")
- `version`: The release version (e.g., "4.20")
- `job_type`: The job type (e.g., "e2e-aws-tests-bootc-release-periodic" or "e2e-aws-tests-release-periodic")

**Output:**
Returns a JSON object with the following structure:
```json
{
  "success": true,
  "version": "4.20.0-202510161342.p0.g17d1d9a.assembly.4.20.0.el9.x86_64",
  "build_type": "zstream",
  "url": "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/...",
  "error": null
}
```

**Build Types:**
- `nightly`: Nightly builds (contains "nightly" in version string)
- `rc`: Release candidate builds (contains "-rc." in version string)
- `ec`: Engineering candidate builds (contains "-ec." in version string)
- `zstream`: Z-stream/patch release builds (all other versions)

**How it works:**
1. Constructs the URL to the rf-debug.log artifact based on job parameters
2. Fetches the build log from GCS storage
3. Searches for the `${version_string_raw}` variable in the log
4. Extracts the full version string (e.g., "4.20.0-202510161342.p0.g17d1d9a.assembly.4.20.0.el9.x86_64")
5. Determines build type from version string patterns
6. Returns structured JSON with all metadata

**Example:**
```bash
# Extract version from a bootc release periodic job
python3 plugins/microshift-prow-job/skills/extract-microshift-version/extract_microshift_version.py \
  1982281180531134464 \
  4.20 \
  e2e-aws-tests-bootc-release-periodic

# Output:
{
  "success": true,
  "version": "4.20.0-202510161342.p0.g17d1d9a.assembly.4.20.0.el9.x86_64",
  "build_type": "zstream",
  "url": "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/periodic-ci-openshift-microshift-release-4.20-periodics-e2e-aws-tests-bootc-release-periodic/1982281180531134464/artifacts/e2e-aws-tests-bootc-release-periodic/openshift-microshift-e2e-metal-tests/artifacts/scenario-info/el96-lrel@standard1/rf-debug.log",
  "error": null
}
```

## Error Handling

The script provides clear error messages for common scenarios:

1. **Invalid arguments**
   ```json
   {
     "success": false,
     "error": "Usage: extract_microshift_version.py <job_id> <version> <job_type>"
   }
   ```

2. **Network errors / log not found**
   ```json
   {
     "success": false,
     "error": "Failed to fetch build log: HTTP Error 404: Not Found",
     "url": "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/..."
   }
   ```

3. **Version not found in log**
   ```json
   {
     "success": false,
     "error": "Could not find version string in build log",
     "url": "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/..."
   }
   ```

## Usage in Commands

Commands should parse the JSON output and check the `success` field:

```bash
# Example integration in a command
result=$(python3 plugins/microshift-prow-job/skills/extract-microshift-version/extract_microshift_version.py "$job_id" "$version" "$job_type")

# Check if extraction succeeded
success=$(echo "$result" | jq -r '.success')
if [ "$success" = "true" ]; then
  microshift_version=$(echo "$result" | jq -r '.version')
  build_type=$(echo "$result" | jq -r '.build_type')
  echo "MicroShift Version: $microshift_version ($build_type)"
else
  error=$(echo "$result" | jq -r '.error')
  echo "Failed to extract version: $error"
fi
```

## Implementation Details

### Version Extraction Logic

The script searches for the version string using this regex pattern:
```python
pattern = r'\$\{version_string_raw\}\s*=\s*(.+?)(?:\s|$)'
```

This matches lines in the rf-debug.log file like:
```
${version_string_raw} = 4.20.0-202510161342.p0.g17d1d9a.assembly.4.20.0.el9.x86_64
```

### SSL Handling

The script disables SSL certificate verification to handle environments with incomplete certificate chains:
```python
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
```

This is necessary because some internal OpenShift CI environments may not have complete SSL certificate chains.

### URL Construction

Build log URLs follow this pattern:
```
https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs/
  periodic-ci-openshift-microshift-release-{version}-periodics-{job_type}/
  {job_id}/
  artifacts/{job_type}/openshift-microshift-e2e-metal-tests/artifacts/scenario-info/el96-lrel@standard1/rf-debug.log
```

## Benefits

1. **Consistent Version Extraction**: Single source of truth for version parsing logic
2. **Structured Output**: JSON format makes it easy to integrate with other tools
3. **Error Handling**: Clear error messages with context (including attempted URL)
4. **Build Type Detection**: Automatically categorizes builds for reporting
5. **No External Dependencies**: Uses only Python standard library
