# MicroShift Prow Jobs Plugin

A Claude Code plugin for analyzing MicroShift Prow CI job executions, test results, and scenarios.

## Overview

The `microshift-prow-job` plugin provides commands to fetch and analyze detailed information from MicroShift CI jobs running on OpenShift's Prow CI infrastructure. It helps developers and QE engineers understand test results, diagnose failures, and track MicroShift version testing across different configurations.

## Features

- **Comprehensive Job Analysis**: Get detailed information about any MicroShift CI job execution
- **Scenario-Level Testing Details**: Analyze individual test scenarios with structured JSON output
- **Version Detection**: Automatically extract MicroShift versions being tested
- **Build Type Classification**: Identify nightly, RC, EC, and stable builds
- **Test Result Parsing**: Parse JUnit XML and extract pass/fail statistics
- **Artifact Access**: Direct links to all logs, test reports, and artifacts

## Commands

### `/microshift-prow-job:analyze-job`

Analyzes a complete MicroShift Prow CI job execution, providing:
- Job metadata (status, timing, architecture, image type)
- MicroShift version being tested (with build type detection)
- Comprehensive test scenario results with pass/fail statistics
- Failure analysis with detailed error messages
- Build information
- Direct links to all logs and artifacts

**Usage:**
```
/microshift-prow-job:analyze-job <job-url>
```

**Arguments:**
- `job-url`: URL to the Prow CI job (supports Prow dashboard URLs, GCS web URLs, or job ID)

**Example:**
```
/microshift-prow-job:analyze-job https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-microshift-release-4.20-periodics-e2e-aws-tests-bootc-release-periodic/1979744605507162112
```

**Output:** Comprehensive Markdown report with job overview, MicroShift version details, test scenario results with pass/fail counts, failure analysis, build information, and artifact links.

---

### `/microshift-prow-job:analyze-test-scenario`

Retrieves comprehensive information about a specific test scenario within a MicroShift CI job in structured JSON format.

**Usage:**
```
/microshift-prow-job:analyze-test-scenario <job-url> [scenario-name]
```

**Arguments:**
- `job-url`: URL to the Prow CI job (required)
- `scenario-name`: Name of the scenario to analyze (e.g., `el96-lrel@standard1`)
  - If omitted, lists all available scenarios

**Examples:**

1. **Get detailed scenario information:**
```
/microshift-prow-job:analyze-test-scenario https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-microshift-release-4.20-periodics-e2e-aws-tests-bootc-release-periodic/1979744605507162112 el96-lrel@standard1
```

2. **List all scenarios in a job:**
```
/microshift-prow-job:analyze-test-scenario https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-microshift-release-4.20-periodics-e2e-aws-tests-bootc-release-periodic/1979744605507162112
```

**Output:** Structured JSON object containing scenario configuration, test results, MicroShift version, execution timing, and artifact links.

## Helper Scripts

### `extract_microshift_version.py`

A Python script that extracts the exact MicroShift version being tested from Prow CI job logs.

**Location:** `plugins/microshift-prow-job/skills/extract-microshift-version/extract_microshift_version.py`

**Usage:**
```bash
python3 plugins/microshift-prow-job/skills/extract-microshift-version/extract_microshift_version.py <job_id> <version> <job_type>
```

**Arguments:**
- `job_id`: The Prow CI job ID (e.g., "1982281180531134464")
- `version`: The release version (e.g., "4.20")
- `job_type`: The job type identifier:
  - `e2e-aws-tests-bootc-release-periodic` (bootc x86_64)
  - `e2e-aws-tests-bootc-release-arm-periodic` (bootc aarch64)
  - `e2e-aws-tests-release-periodic` (rpm-ostree x86_64)
  - `e2e-aws-tests-release-arm-periodic` (rpm-ostree aarch64)

**Example:**
```bash
python3 plugins/microshift-prow-job/skills/extract-microshift-version/extract_microshift_version.py \
  1979744605507162112 \
  4.20 \
  e2e-aws-tests-bootc-release-periodic
```

**Output:**
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
- `nightly`: Nightly development builds
- `ec`: Engineering Candidate
- `rc`: Release Candidate
- `zstream`: Stable/zstream release

## Installation

### From Claude Code Marketplace

```bash
# Add the ai-helpers marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install the plugin
/plugin install microshift-prow-job@ai-helpers
```

### Manual Installation

```bash
# Clone the repository
git clone git@github.com:openshift-eng/ai-helpers.git

# Link to Claude Code plugins directory
cd ~/.claude/plugins
ln -s /path/to/ai-helpers/plugins/microshift-prow-job microshift-prow-job
```

## Common Use Cases

### 1. Investigate a Failed CI Job

```
/microshift-prow-job:analyze-job https://prow.ci.openshift.org/view/gs/test-platform-results/logs/...
```

This provides a complete overview of what failed, which scenarios had issues, detailed failure messages, and links to relevant logs.

### 2. Compare Test Results Across Scenarios

```
# First, list all scenarios
/microshift-prow-job:analyze-test-scenario <job-url>

# Then analyze specific scenarios
/microshift-prow-job:analyze-test-scenario <job-url> el96-lrel@standard1
/microshift-prow-job:analyze-test-scenario <job-url> el96-lrel@lvm
```

### 3. Track Version Testing

Use the version extraction to understand exactly what MicroShift version was tested:

```bash
python3 plugins/microshift-prow-job/skills/extract-microshift-version/extract_microshift_version.py \
  1979744605507162112 4.20 e2e-aws-tests-bootc-release-periodic
```

### 4. Automated Analysis

The JSON output from `analyze-test-scenario` can be piped to other tools for automated analysis:

```bash
# Extract JSON and process with jq
/microshift-prow-job:analyze-test-scenario <job-url> <scenario> | jq '.test_results.summary'
```

## Understanding Test Scenarios

MicroShift CI tests run across multiple scenarios, each testing different configurations:

### Scenario Naming Convention

Format: `{source-os}@{target-os}@{test-type}` or `{os}@{test-type}`

Examples:
- `el96-lrel@standard1`: RHEL 9.6 Latest Release - Standard Tests (variant 1)
- `el94-y2@el96-lrel@standard1`: Upgrade from RHEL 9.4 (Y-2) to 9.6 - Standard Tests
- `el96-lrel@lvm`: RHEL 9.6 Latest Release - LVM Storage Tests

### Common Test Categories

| Test Type | Description |
|-----------|-------------|
| `standard1`, `standard2` | Basic functionality tests (different variants) |
| `lvm` | LVM storage configuration tests |
| `storage` | Storage subsystem tests including CSI and snapshotter |
| `dual-stack` | Dual-stack IPv4/IPv6 networking tests |
| `ipv6` | IPv6-only networking tests |
| `multi-nic` | Multiple network interface tests |
| `router` | OpenShift router and ingress tests |
| `osconfig` | OS configuration and system settings tests |
| `optional` | Optional component functionality tests |
| `telemetry` | Telemetry and monitoring tests |
| `low-latency` | Low-latency kernel and configuration tests |
| `ginkgo-tests` | OpenShift Ginkgo integration tests |
| `ai-model-serving-online` | AI model serving capability tests |

### Job Types

MicroShift CI runs tests across different configurations:

| Configuration | Architecture | Image Type | Job Type Identifier |
|--------------|-------------|------------|---------------------|
| Bootc x86_64 | x86_64 | bootc | `e2e-aws-tests-bootc-release-periodic` |
| Bootc ARM | aarch64 | bootc | `e2e-aws-tests-bootc-release-arm-periodic` |
| RPM-OSTree x86_64 | x86_64 | rpm-ostree | `e2e-aws-tests-release-periodic` |
| RPM-OSTree ARM | aarch64 | rpm-ostree | `e2e-aws-tests-release-arm-periodic` |

## Requirements

- **Claude Code**: Latest version with plugin support
- **Python 3**: Required for the `extract_microshift_version.py` helper script
- **Internet Access**: Required to fetch data from Prow CI and GCS

## Output Examples

### Job Info Output (Markdown)

```markdown
# MicroShift CI Job Analysis

## Job Overview
- **Job ID**: 1977207773863088128
- **Job Name**: periodic-ci-openshift-microshift-release-4.20-periodics-e2e-aws-tests-bootc-release-periodic
- **Status**: ✗ FAILURE
- **Architecture**: x86_64
- **Image Type**: bootc
- **Version**: 4.20
- **Duration**: 1h 30m 40s
- **Started**: 2025-10-12 03:00:46 UTC
- **Finished**: 2025-10-12 04:31:26 UTC

## MicroShift Version
- **Full Version**: `4.20.0~rc.3-202509290606.p0.g1c4675a.assembly.rc.3.el9.x86_64`
- **Build Type**: RC (Release Candidate) - zstream
- **Base Version**: 4.20.0-rc.3
- **Build Date**: 2025-09-29 06:06
- **Commit**: g1c4675a

## Test Results Summary

**Overall**: 14 scenarios passed, 1 failed, 1 not available

| Status | Count |
|--------|-------|
| ✓ Passed | 14 |
| ✗ Failed | 1 |
| **Total Tests** | **205** |
| **Total Passed** | **204** |
| **Total Failed** | **1** |

## Test Scenarios

### ✓ el96-lrel@standard1
**RHEL 9.6 Latest Release - Standard Tests Set 1**
- **Status**: PASSED
- **Tests**: 33 total (33 passed, 0 failed)
- **Duration**: 22m 9s
- **JUnit**: [View XML](https://storage.googleapis.com/...)

### ✗ el96-lrel@storage
**RHEL 9.6 Latest Release - Storage Tests**
- **Status**: FAILED
- **Tests**: 4 total (3 passed, 1 failed)
- **Duration**: 8m 32s

**Failed Tests**:
1. **Snapshotter Smoke Test**
   - Type: AssertionError
   - Message: Setup failed: 1 != 0

## Failure Analysis

The job failed due to 1 test failure in the `el96-lrel@storage` scenario:
- Snapshotter Smoke Test failed during setup and teardown
- This indicates an issue with CSI snapshotter functionality

...
```

## Troubleshooting

### Job Not Found (404)

If you get a 404 error:
1. Verify the job ID is correct
2. Check if the job is still running (artifacts may not be available yet)
3. Ensure you're using the correct job URL format

### Missing Artifacts

Some jobs may not have all artifacts available:
- The command will gracefully handle missing files
- Check the job status - failed jobs may have incomplete artifacts
- Look at the build log to understand why artifacts are missing

### SSL Certificate Errors

The helper script handles SSL certificate issues automatically, but if you encounter problems:
- Ensure you have internet connectivity
- Check if corporate proxies are blocking GCS access
- Try accessing the GCS URLs directly in a browser first

## Contributing

Contributions are welcome! Please see the main [ai-helpers repository](https://github.com/openshift-eng/ai-helpers) for contribution guidelines.

## Support

- **Issues**: Report issues at [ai-helpers/issues](https://github.com/openshift-eng/ai-helpers/issues)
- **Documentation**: See individual command files in `commands/` for detailed implementation notes

## Author

- **Alejandro Gullón** (agullon@redhat.com)
- GitHub: [@agullon](https://github.com/agullon)

## License

This plugin is part of the ai-helpers project and follows the same license.
