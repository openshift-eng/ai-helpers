---
description: Query and analyze OpenShift CI data in BigQuery across jobs, tests, autodl, and agent decisions
argument-hint: <question about CI data>
---

## Name
bigquery-ci-data:query

## Synopsis
```
/bigquery-ci-data:query what is the pass rate for periodic aws jobs on 4.22 this week?
/bigquery-ci-data:query which tests have the most retries in the last 7 days?
/bigquery-ci-data:query show me operator degraded time trends for etcd this month
/bigquery-ci-data:query what override decisions has the chain presubmit agent made recently?
```

## Description

General-purpose entry point for querying OpenShift CI data stored in BigQuery. Understands multiple datasets and routes to the appropriate tables based on the question.

The command covers:
- **Jobs and tests** (`ci_analysis_us`): Prow job pass rates, junit test failures/flakes, variant analysis
- **Autodl data** (`ci_data_autodl`): Risk analysis, retry statistics, operator state, CPU metrics, audit logs, disruption
- **Agent decisions** (`ci_analysis_us`): Chain presubmit override decisions

## Implementation

### Steps

1. **Parse the question**: Determine which domain(s) and table(s) are needed:
   - Job pass rates, test failures, variant breakdowns → use `jobs-and-tests` skill
   - Risk analysis, retries, operator state, CPU, audit logs, disruption, instance types → use `autodl` skill
   - Presubmit override decisions → use `chai-presubmit-override-decisions` skill
   - Always load the `foundations` skill for cost safety protocol

2. **Identify parameters**: Extract or ask for:
   - Date range (suggest 7 days if not specified)
   - Release version (if relevant)
   - Specific job names, test names, operators, etc.

3. **Build and execute query** following the foundations workflow:
   - Show query to user
   - Dry-run for cost estimate
   - Confirm if over $1.00
   - Execute and cache results
   - Analyze and report findings

4. **Present results** with summary statistics, notable patterns, and suggestions for follow-up.

## Arguments

- **question** (required): Natural language description of what CI data to investigate

## Examples

1. **Test failure investigation**:
   ```
   /bigquery-ci-data:query how often is kube-apiserver readyz failing on 4.22 this week?
   ```

2. **Retry analysis**:
   ```
   /bigquery-ci-data:query which tests need the most retries to pass?
   ```

3. **Operator health**:
   ```
   /bigquery-ci-data:query which operators spend the most time degraded on vsphere?
   ```

4. **API server audit**:
   ```
   /bigquery-ci-data:query which service accounts make the most API requests?
   ```
