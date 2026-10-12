# CI Extras Plugin

Extended OpenShift CI tooling, providing an MCP server for direct access to CI data APIs.

## Payload informing-job analysis

Use `$ci-extras:analyze-payload-informing-jobs 5.1 --architecture amd64
--stream nightly` to rank non-blocking verification jobs across a frozen set of
recent, relatively healthy payloads. The workflow separates current-release and
verified previous-release history, deduplicates Prow runs, routes prioritized
failures through `prow-job-analysis`, and exports portable repair, retirement,
and unresolved findings.

The [analyze-payload-informing-jobs skill](skills/analyze-payload-informing-jobs/SKILL.md)
defaults to a 14-day window, at most 10 healthy payloads, a ceiling of 10 validated
recommendations, 100 candidate cohorts, and a 120-minute workflow budget. Release, architecture, and
stream are required; the population and evidence thresholds are configurable.
Its Python helpers use public Sippy and Prow/GCS data. User-selected workspace
paths are supported; the default is `~/tmp/analyze-payload-informing-jobs/<UTC timestamp>`.

The report links a readable summary for every ranked cohort. Investigated jobs
use the reliability handoff format with impact, mechanism, source status, next
action and owner, validation, limits, review, and evidence. Pending jobs have
short metrics-and-status summaries; current and historical rankings stay separate.
Finding no fix in early investigations does not stop exploration. Persistent
history advances later runs through pending cohorts; changed evidence or feasible
follow-ups can reopen prior investigations. Reports state the stopping reason,
remaining queue, and historical context without renewing old conclusions or reviews.

Retirement output is a recommendation with an unapplied configuration change,
cross-stream impact, coverage risk, restoration criteria, and a separate review.
For an informing job unable to run its intended tests with no supported repair,
a yearly retirement recommendation must also propose setting `disabled: true`
on its payload verification entry, even if the periodic is already yearly.
The entry and its job mapping are retained. The periodic job remains available for
yearly and manual runs, subject to the existing retirement gates.
The skill never edits CI configuration, changes schedules, opens issues or PRs,
decides payloads, or triggers jobs without a separate request.

## Reliability investigations

Use `/investigate-ci-reliability 5.1 --max-issues 10` to investigate **all release
jobs plus presubmits from the last 24 hours**. Narrow by scope (`all`, `release`,
`presubmits`, `blocking`), exact job, substring, variant, or time window.

The [investigate-ci-reliability skill](skills/investigate-ci-reliability/SKILL.md) includes public
Sippy collection, bounded Prow artifacts, an independent proof-review stage, and a portable
issue exporter. Review challenges each proposed fix before publication. The bundled scripts
require Python 3.10+ and HTTPS access, without MCP; JUnit parsing additionally requires
Expat 2.7.2+. Failed-job debugging uses `prow-job-analysis` from the `ci` plugin, declared
as a dependency in the plugin manifest.

Output `issues/` contains only independently validated current defects, including evidence,
source state, owners, proposed fixes, acceptance criteria, and causal limitations. Unresolved
and already-fixed findings stay in a separate appendix. Maximum issues is a ceiling, not
a promise; automated validation checks evidence integrity, not causal truth.

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
