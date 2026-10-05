# BigQuery CI Data Plugin

Query and analyze OpenShift CI data stored in BigQuery across multiple datasets and tables.

## Overview

This plugin provides structured knowledge about CI data tables in BigQuery, enabling ad-hoc investigation of test failures, job health, risk analysis, operator behavior, and more. It covers:

- **Jobs and tests** — prow job runs, junit test results, variant classifications, and infrastructure failure labels in `openshift-gce-devel.ci_analysis_us`
- **Autodl data** — automatically collected data from test runs including risk analysis, retry statistics, operator state, CPU metrics, kube-apiserver audit analysis, and more in `openshift-ci-data-analysis.ci_data_autodl`
- **Agent decisions** — chain presubmit override decision log in `openshift-gce-devel.ci_analysis_us`

## Prerequisites

- Google Cloud SDK installed (`bq` CLI)
- Authenticated: `gcloud auth login`
- BigQuery read access to `openshift-gce-devel` and `openshift-ci-data-analysis` projects

## Commands

### `/bigquery-ci-data:query`

General-purpose entry point. Describe what you want to know about CI data and the agent routes to the appropriate tables and builds a cost-safe query.

```
/bigquery-ci-data:query what is the pass rate for periodic aws jobs on 4.22 this week?
/bigquery-ci-data:query which tests have the most retries?
/bigquery-ci-data:query show operator degraded time for etcd
```

## Skills

| Skill | Purpose |
|-------|---------|
| `foundations` | Shared cost safety protocol, `bq` CLI patterns, caching workflow |
| `jobs-and-tests` | `ci_analysis_us` tables: junit, jobs, job_variants, job_labels |
| `autodl` | `ci_data_autodl` tables: risk analysis, retries, operator state, CPU, audit logs, disruption |
| `chai-presubmit-override-decisions` | `ci_analysis_us.chai_presubmit_decision_log`: presubmit override decisions |

## Cost Safety

All queries follow a strict cost protocol: dry-run first, estimate cost at $6.25/TB, confirm with user if over $1.00. Results are cached locally to avoid re-querying.
