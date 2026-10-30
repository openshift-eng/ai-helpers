---
name: foundations
description: Use when executing any BigQuery CI data query — provides the shared safety protocol, cost controls, bq CLI patterns, and caching workflow
---

# BigQuery CI Data Foundations

Shared foundations for all CI data BigQuery skills. Every skill in this plugin follows these protocols.

## Prerequisites

- `bq` CLI installed and authenticated (`gcloud auth login`)
- BigQuery read access to the relevant projects

## Projects and Datasets

| Project | Dataset | Purpose |
|---------|---------|---------|
| `openshift-gce-devel` | `ci_analysis_us` | Primary engineering CI data (jobs, junit, variants, labels) |
| `openshift-gce-devel` | `ci_analysis_qe` | QE CI data (same schema as `ci_analysis_us`, smaller) |
| `openshift-ci-data-analysis` | `ci_data_autodl` | Auto-collected data from test runs (disruption, CPU, audit logs, risk analysis, etc.) |

Always pass `--project_id=<project>` explicitly to all `bq` commands.

## Cost Safety Protocol

**Non-negotiable.** Every query follows this flow:

1. **Show the query** to the user before doing anything
2. **Dry-run** to get bytes scanned:
   ```bash
   bq query --project_id=<project> --dry_run --use_legacy_sql=false '<query>'
   ```
3. **Calculate cost**: `bytes / 10^12 * $6.25` (on-demand pricing)
4. **If cost > $1.00**: show estimated cost and bytes, ask user to confirm
5. **If cost <= $1.00**: proceed, report cost in results
6. **Never loop or repeat queries.** Run once, cache locally, analyze from cached data.

## Partition and Clustering Filters

When a table is partitioned, every query MUST include a filter on the partition column to avoid full-table scans. Use tight date ranges. Not all tables are partitioned (e.g. `job_variants` is small and unpartitioned).

When a table is clustered, filter on the clustering column too for major cost reduction.

## Caching Results Locally

After executing a query, save results to `.work/bigquery-ci-data/` as JSON or CSV. Name files descriptively.

**Always query fresh** — never skip a query because a cached file with a similar name already exists. CI data changes continuously; stale cache files produce misleading results. Use cached files only for follow-up analysis of the same data within the same conversation, and re-query if more than 4 hours have passed since the cache was written.

## Execution Workflow

For every user request:

### Step 1: Understand the Question
Identify which table(s), date range, and filters are needed. Ask if date range is not specified — suggest a narrow range.

### Step 2: Build the Query
- Include partition column filter with tight date range
- Include clustering filters when applicable
- Use `--use_legacy_sql=false`
- Select only needed columns on large tables

### Step 3: Show, Dry-Run, Confirm Cost
Present query, run dry-run, calculate and report cost. Confirm with user if over $1.00. Strongly recommend narrowing if over $10.00.

### Step 4: Execute and Cache
```bash
mkdir -p .work/bigquery-ci-data
bq query --project_id=<project> --use_legacy_sql=false --format=json --max_rows=10000 '<query>' > .work/bigquery-ci-data/<descriptive-name>.json
```

**Row limit caveat**: `--max_rows=10000` truncates output. Prefer SQL-level aggregation (`GROUP BY`, `COUNT`, `AVG`) or `LIMIT` so the query returns complete results within the cap. If raw rows are needed and the result hits 10,000 rows, increase `--max_rows` or add tighter filters before reporting totals or rankings from the output.

### Step 5: Analyze and Report
Parse cached results. Include summary statistics, notable patterns, links to prow jobs when relevant, and suggestions for follow-up queries.

## Autodl Loader Columns

All tables in `ci_data_autodl` automatically include three columns added by the ci-data-loader (not in the Go source schemas):

| Column | Type | Notes |
|--------|------|-------|
| JobRunName | STRING | Prow job run identifier |
| PartitionTime | TIMESTAMP | Partition column — always filter on this |
| Source | STRING | Data source identifier |

## Query Optimization Tips

- **Narrow date ranges first**: Start with 7 days. Widen only if needed.
- **Select only needed columns**: Don't `SELECT *` on large tables.
- **Filter early**: Put the most selective filters in the WHERE clause.
- **Avoid repeated queries**: Cache results and analyze locally.
- **Use exact match over LIKE**: When you have exact IDs, use `=` not `LIKE`.

## Error Handling

- **"BigQuery not enabled"**: Pass `--project_id=<project>` explicitly
- **Authentication errors**: Ask user to run `! gcloud auth login`
- **Timeout on large queries**: Suggest narrowing the date range
- **No results**: Verify names/IDs exist, check date range
