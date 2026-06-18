# CI Extras Plugin

Extended OpenShift CI tooling, providing an MCP server for direct access to CI data APIs.

## Commands

### check-release-health

> **Example command** — demonstrates how to use the bundled openshift-ci-mcp server tools directly from a plugin command.

Fetches live CI health data for a given OpenShift release and produces a concise summary covering payload acceptance, test regressions, and recent failures.

**Usage:**
```bash
/ci-extras:check-release-health <release version>
```

**Example:**
```bash
/ci-extras:check-release-health 4.18
```

**What it does:**
- Fetches overall release health metrics and pass rate trends
- Checks recent payload acceptance status
- Summarizes active regressions
- Highlights notable recent test failures

**Prerequisites:** Requires the openshift-ci-mcp server (bundled with this plugin).

## MCP Server

This plugin bundles the [openshift-ci-mcp](https://github.com/openshift-eng/openshift-ci-mcp) server, which exposes OpenShift CI data directly as tools.

**Prerequisites:** Go toolchain (`go` must be on your `PATH`). The server is fetched and compiled on first use.

**Tools enabled by default:**

| Group | Tool | Description |
|-------|------|-------------|
| core | `get_releases` | OpenShift releases with availability and dev cycle dates |
| core | `get_release_health` | Health data for a release: success rates, variant summary, payload acceptance |
| core | `get_variants` | Variants and their possible values (arch, topology, platform, network) |
| core | `get_tool_fields` | Discover field names returned by a tool |
| payload | `get_payload_status` | Recent payload acceptance status from the Release Controller |
| payload | `get_payload_diff` | PR changes between payload tags |
| payload | `get_payload_test_failures` | Test failures for payload job runs |
| payload | `get_component_readiness` | Component readiness report for the current dev cycle |
| payload | `get_regressions` | Tests performing significantly worse than the previous release |
| payload | `get_regression_detail` | Regression detail with triages and Jiras |
| jobs | `get_job_report` | Job pass rates with filtering and pagination |
| jobs | `get_job_runs` | Results, timings, and risk analysis for recent job runs |
| jobs | `get_job_run_summary` | Test failures and cluster operator status for a single job run |
| tests | `get_ci_test_report` | Pass/fail/flake rates for tests with optional filtering |
| tests | `get_test_details` | Pass rates broken down by variant and job |
| tests | `get_recent_test_failures` | Tests that recently started failing |
| prs | `get_release_prs` | Pull requests for a specific release or presubmits |
| prs | `get_pr_impact` | Test failure impact for a specific PR (rate-limited: 20 req/hr) |
| search | `search_ci_logs` | Search logs and JUnit output across OpenShift CI |

**Proxy tools (disabled by default):**

Raw API passthroughs to Sippy, the Release Controller, and search.ci. Enable with `ENABLE_PROXY_TOOLS=true`:

```bash
export ENABLE_PROXY_TOOLS=true
```

> **Note:** Restart the MCP server after setting this variable for the proxy tools to become available.

| Tool | Description |
|------|-------------|
| `sippy_api` | Raw passthrough to any Sippy API endpoint |
| `release_controller_api` | Raw passthrough to the Release Controller API |
| `search_ci_api` | Raw passthrough to the Search.CI API |
