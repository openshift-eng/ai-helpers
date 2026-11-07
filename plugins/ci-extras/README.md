# CI Extras Plugin

Extended OpenShift CI tooling. Its example command uses the openshift-ci-mcp server bundled
with the ci plugin for direct access to CI data APIs.

## Payload job analysis

Use `$ci-extras:analyze-payload-jobs 5.1 informing --architecture amd64
--stream nightly` to rank non-blocking verification jobs across a frozen set of
recent, relatively healthy payloads. The workflow separates current-release and
verified previous-release history, deduplicates Prow runs, routes prioritized
failures through `prow-job-analysis`, and exports portable repair, retirement,
and unresolved findings.

Use `$ci-extras:analyze-payload-jobs 4.18 blocking --architecture amd64
--stream nightly --history-release none` for periodic blocking-job analysis of
older releases without informing jobs or a payload agent. Blocking analysis
includes completed rejected payloads regardless of blocker pass rate, so failing
gates remain visible. Both modes retain complete inventories and shared-failure
review; the selected role filters the jobs ranked and investigated.

The [analyze-payload-jobs skill](skills/analyze-payload-jobs/SKILL.md)
defaults to a 14-day window, at most 10 eligible payloads, a ceiling of 10 validated
recommendations, 100 candidate cohorts, and a 120-minute workflow budget. Release,
architecture, stream, and an explicit `informing` or `blocking` role are required; the population
and evidence thresholds are configurable (`--payloads`, `--min-payloads`).
Its Python helpers use public Sippy and Prow/GCS data. User-selected workspace
paths are supported; the default is `~/tmp/analyze-payload-jobs/<UTC timestamp>`.

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
For a selected job unable to run its intended tests with no supported repair,
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

> **Example command** — demonstrates how to use the openshift-ci-mcp server tools (bundled with the ci plugin) directly from a plugin command.

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

**Prerequisites:** Requires the openshift-ci-mcp server (bundled with the ci plugin).

## MCP Server

The [openshift-ci-mcp](https://github.com/openshift-eng/openshift-ci-mcp) server is bundled
with the [ci plugin](../ci/README.md#mcp-server-openshift-ci-mcp), a dependency of this
plugin, so installing ci-extras also installs it. Its tools are named
`mcp__plugin_ci_openshift-ci-mcp__<tool>`; see the ci plugin README for the tool list,
prerequisites, and private QE deck access.
