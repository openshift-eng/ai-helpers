---
name: analyze-disruption
description: Analyze disruption from a DisruptionRegression alert, a Grafana disruption dashboard URL, or Prow CI job runs by examining interval data, audit logs, pod logs, and CPU metrics
---

# Analyze Disruption

This skill analyzes disruption events recorded in Prow CI job runs. It downloads interval/timeline data,
audit logs, and pod logs, then correlates disruption across backends and job runs to identify root causes.

## Prerequisites

1. **gcloud CLI Installation**
   - Check if installed: `which gcloud`
   - The `test-platform-results-public` bucket is public. Do not run `gcloud auth login` for these artifacts, and do not change the user's gcloud config.
   - `download_timelines.py` sets `CLOUDSDK_AUTH_DISABLE_CREDENTIALS=true` on each gcloud subprocess (listing and copying, including parallel workers). That avoids refreshing expired local credentials.
   - Any direct `gcloud storage` command in this skill uses the same variable. Anonymous access still needs network execution when the command runs in a sandbox.

2. **Python 3** (3.7 or later)

## Input Format

The user will provide one of the following as input:

**Option A — Prow job URLs (direct analysis):**

1. **One or more Prow job URLs** (at least 1)
   - Example: `https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/periodic-ci-openshift-release-master-ci-4.21-e2e-aws-ovn/1983307151598161920`

**Option B — Grafana disruption dashboard URL (run discovery + analysis):**

1. **A Grafana disruption dashboard URL** — the skill extracts filter parameters, finds
   matching job runs via Sippy, and presents candidates for the user to select before analysis
   - Example: `https://grafana-loki.ci.openshift.org/d/gEdw_aLvk/disruption-for-5-0-os-agnostic?var-platform=gcp&var-backend=host-to-host-new-connections&var-upgrade_type=micro&var-architectures=amd64&var-topologies=ha&var-networks=ovn&var-releases=5.0`
   - Recognized by hostname `grafana-loki.ci.openshift.org` and path starting with `/d/`
   - Every `var-backend` value is an exact backend name. Pass that full list as `--backends` unless the user overrides it. Do not reduce it to one API backend or to a stripped base name

**Option C — disruption regression alert text (run discovery + analysis):**

1. **A pasted `DisruptionRegression` alert** — `DisruptionRegressionP50`, `DisruptionRegressionP50Azure`, `DisruptionRegressionP75`, or `DisruptionRegressionP95`, or a label block that contains `alertname` and `backend`
   - Example labels: `backend`, `platform`, `upgrade_type`, `master_nodes_updated`, `architecture`, `topology`, `network`, `release`, `delta`, `feature_set`, `os`, `compare_release`
   - A `link:` annotation, when present, is the dashboard URL. Pass the alert text through unchanged. Do not rebuild the URL, and do not drop `master_nodes_updated`, `feature_set`, or `os`
   - With no link, the finder uses the alert labels and a 3-day lookback, which is the regression window these alerts measure

**Optional flags (all input options):**

2. **`--backends` flag** (optional) — comma-separated exact backend names to focus on
   - Example: `--backends kube-api-new-connections,oauth-api-new-connections,openshift-api-new-connections`
   - If omitted, analyze all backends that show disruption (Option A) or use every Grafana
     `var-backend` / alert `backend` value (Option B or C)

3. **`--skip-jira` flag** (optional) — skip the Jira search for known disruption cards
   - By default, the skill searches TRT and OCPBUGS for existing disruption cards after analysis

## Bundled Resources

Load these only at the step that needs them — not up front:

- **`references/run-discovery.md`** — Grafana URL and alert resolution into Prow job runs (Step 1.5)
- **`references/artifacts.md`** — timeline download and optional audit/etcd/PromQL deep dive (Steps 2 and 4)
- **`references/timeline-analysis.md`** — parser modes, signal interpretation, and extra diagnostic checks (Steps 3 and 5)
- **`references/cross-run-comparison.md`** — multi-run pattern detection and same-job clean comparison (Step 6)
- **`references/report-guide.md`** — deep-link shapes, inline linking rules, and report structure (Step 7)
- **`references/known-issues.md`** — Jira search and bug filing (Step 8)

## Implementation Steps

### Step 1: Parse and Validate Input

1. **Extract URLs and flags**
   - Parse `--backends` flag if present, split on comma to get backend filter list
   - Parse `--skip-jira` flag as a boolean option (default: false)
   - Collect all positional URL arguments

2. **Detect input type**:
   - **Alert text**: `alertname` is `DisruptionRegressionP50`, `DisruptionRegressionP50Azure`, `DisruptionRegressionP75`, or `DisruptionRegressionP95`, or the text is a label block with `alertname` and `backend`
     → proceed directly to **Step 1.5** and pass the alert text as `--alert-text`.
     Skip item 3 (it runs after Step 1.5 resolves Prow URLs).
   - **Grafana URL**: hostname is `grafana-loki.ci.openshift.org` and path starts with `/d/`
     → proceed directly to **Step 1.5** to parse URL parameters and find job runs via Sippy.
     Do NOT fetch the URL, do NOT open or access the dashboard — it is behind SSO.
     Skip item 3 (it runs after Step 1.5 resolves Prow URLs).
   - **Prow URL**: any other URL (e.g., `prow.ci.openshift.org`, `gcsweb-ci`)
     → continue to step 3 below
   - Validate at least one URL or one alert is provided

3. **Parse each Prow URL** to extract bucket path, job name, and build ID
   - Use the same URL parsing logic as the "prow-job-analysis" skill
   - Accept both `prow.ci.openshift.org` and `gcsweb-ci` URL formats
   - Extract `build_id` and `job_name` from each URL

   Deep-link shapes for the report are in `references/report-guide.md`. Construct them when writing the report (Step 7), not as a separate links table.

### Step 1.5: Resolve a Grafana URL or Alert to Job Runs

Skip this step if the input is Prow job URL(s).

Read `references/run-discovery.md` (in this skill's directory) and follow it. Pass the Grafana URL or the alert text through unchanged, including every exact backend name. Do not fetch or open the Grafana URL, and do not query Sippy by hand. Do not strip names to a base such as `kube-api` or substitute derived probes.

The resolved Prow URLs proceed to Step 1, item 3, and then Step 2.

### Step 2: Download Artifacts for All Runs

Read `references/artifacts.md` and follow **Timeline download**. Write files under `.work/disruption-analysis/{date}/`.

The downloader uses anonymous access to the public `test-platform-results-public` bucket. Do not run `gcloud auth login`. On exit 2, continue with the runs that downloaded. On exit 1, stop and report each run's error.

### Step 3: Analyze Interval/Timeline Data

Read `references/timeline-analysis.md` and follow sections 3.1 through 3.4. Pass exact backend names as `--backends`. A shortened name is not the selected backend.

### Step 4: Deep-Dive Artifact Download (Optional)

Only if the parser output from Step 3 is insufficient for root cause determination, read the **Deep-dive artifact download** section of `references/artifacts.md` and follow it. Prefix any direct `gcloud storage` command with `CLOUDSDK_AUTH_DISABLE_CREDENTIALS=true`. Do not run `gcloud auth login`.

### Step 5: Additional Diagnostic Checks

`references/timeline-analysis.md` includes the node-shutdown and endpoint-slice checks. Do them when disruption coincides with node events.

### Step 6: Cross-Run Comparison (Multiple Runs Only)

When multiple job runs were provided, read `references/cross-run-comparison.md` and follow it.

Runs where `ci-cluster-network-liveness` is disrupted have unreliable disruption data. Keep them in the analysis and note the caveat. Do not draw conclusions solely from an unreliable run's disruption counts.

### Step 7: Generate Report

Read `references/report-guide.md` and follow it. Save the report at `.work/disruption-analysis/{date}/{backend_names}-analysis.md`. The filename rule is in that guide.

Links go inline where the evidence is discussed. Do not add an Artifacts or Links table. Do not truncate job names.

### Step 8: Known Disruption Issue Lookup

Skip this step if `--skip-jira` was passed. Otherwise read `references/known-issues.md` and follow it.

## Error Handling

1. **No disruption found** — If interval files show no disruption events, report that the run is clean and no disruption was detected. This is a valid result, not an error.

2. **Audit logs not available** — Some jobs may not have audit logs. Note this in the report and continue analysis with available data.

3. **etcd logs not available** — If etcd pod logs are not present in gather-extra, note this and skip etcd analysis.

4. **Interval files not found** — If no interval/timeline files are found for a job run, this is a critical error for that run. Report it and skip that run if analyzing multiple runs.

5. **gcloud errors** — Public-bucket commands use `CLOUDSDK_AUTH_DISABLE_CREDENTIALS=true` and do not require `gcloud auth login`. When a download fails, report the run's `error` text (it includes the gcloud diagnostic, with credential-like values removed). Exit 2 means some timeline files were saved: continue with those runs. Exit 1 means nothing was downloaded. A sandbox that blocks the network is separate from an auth failure; request network execution and run the downloader again.

6. **Jira MCP unavailable** — If the Jira MCP tools are not available or authentication fails, skip Step 8 and note "Jira search skipped (MCP unavailable)" in the Known Disruption Issues section. Do not block the disruption analysis on Jira availability.

7. **Grafana URL or alert missing required parameters** — If `var-releases` / `release` or `var-backend` / `backend` are missing, prompt the user for the missing values rather than failing.

7a. **`master_nodes_updated` requested but absent from the disruption API** — The finder keeps no runs and prints that the field was missing. Report that warning. Do not analyze the unfiltered job list.

8. **No Sippy results for Grafana filters** — If no runs match the variant filters from the Grafana URL, suggest widening the time window or relaxing filters. Report the exact query parameters that were attempted so the user can diagnose the mismatch.

9. **No disruption test failures in matching runs** — If matching runs exist but none have disruption test failures for the target backend, note this (disruption may be within threshold but elevated compared to baseline). Offer to analyze the most recent runs anyway.

10. **Sippy API unavailable** — If the Sippy API is unreachable during Grafana URL resolution, report the error and suggest providing Prow job URLs directly as a fallback.

## Performance Considerations

- Download artifacts for multiple runs in parallel when analyzing more than one run
- When analyzing multiple runs, process each run independently first, then perform cross-run comparison
- Use `--max-bytes` limits when fetching large log files to avoid excessive downloads
- Filter audit logs by timestamp range rather than downloading and scanning entire files when possible
