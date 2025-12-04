# BigQuery Plugin

BigQuery cost analysis and optimization utilities for Google Cloud Platform projects.

## Overview

This plugin helps analyze BigQuery usage patterns, identify expensive queries, and provide optimization recommendations to reduce costs. It's particularly useful for:

- Monitoring BigQuery spending and usage trends
- Identifying top consumers (users, service accounts, queries)
- Finding optimization opportunities
- Generating usage reports for stakeholders
- Debugging cost overruns and threshold violations

## Prerequisites

- Google Cloud SDK installed (`gcloud` and `bq` CLI tools)
- Authenticated to GCP: `gcloud auth login`
- BigQuery read access to the projects you want to analyze
- At minimum, `bigquery.jobs.list` permission

### Installation

**macOS (Homebrew):**
```bash
brew install google-cloud-sdk
```

**Other platforms:**
Visit https://cloud.google.com/sdk/docs/install

**Verify installation:**
```bash
bq version
gcloud auth list
```

## Commands

### `/bigquery:analyze-usage`

Analyze BigQuery usage and costs for a project.

**Usage:**
```
/bigquery:analyze-usage <project-id> <timeframe>
```

**Arguments:**
- `project-id`: GCP project ID (e.g., `openshift-ci-data-analysis`)
- `timeframe`: Time period to analyze (e.g., "24 hours", "7 days", "30 days")

**Examples:**
```
/bigquery:analyze-usage openshift-ci-data-analysis "24 hours"
/bigquery:analyze-usage my-project "7 days"
/bigquery:analyze-usage prod-data-warehouse "30 days"
```

**Output:**
- Executive summary (total usage, costs, key findings)
- Usage by user/service account (top consumers)
- Top query patterns with optimization recommendations
- Top individual queries by cost
- Prioritized optimization recommendations
- Option to save report to markdown file

## Skills

### `bigquery:analyze-usage`

Core analysis skill that:
- Queries INFORMATION_SCHEMA.JOBS for usage data
- Analyzes query patterns and identifies optimization opportunities
- Calculates costs and usage metrics
- Generates actionable recommendations

This skill is automatically invoked by the `/bigquery:analyze-usage` command.

## Features

### Usage Analysis
- Total queries executed
- Total data scanned (TB/GB)
- Estimated costs (on-demand pricing)
- Breakdown by user and service account
- Query frequency and patterns

### Query Pattern Detection
- Groups similar queries together
- Identifies high-frequency patterns
- Calculates aggregate costs per pattern
- Highlights optimization opportunities

### Optimization Recommendations
- Tables needing partitioning or clustering
- Queries using `SELECT *` instead of column pruning
- Full table scans without WHERE clauses
- High-frequency queries that could benefit from caching
- Scheduled queries running too often
- Estimated savings per recommendation

### Report Generation
- Clean, readable markdown format
- Tables for easy comparison
- Detailed analysis with context
- Exportable for sharing with teams

## Cost Calculation

Costs are estimated using Google Cloud on-demand pricing:
- **$6.25 per TB** of data scanned

**Note:** Actual costs may differ if you have:
- Flat-rate pricing
- Reserved capacity
- Committed use discounts
- Different regional pricing

The reports note this and focus on relative costs for comparison.

## Common Use Cases

### 1. Daily Cost Monitoring
```
/bigquery:analyze-usage my-project "24 hours"
```
Monitor daily usage and catch cost spikes early.

### 2. Weekly Review
```
/bigquery:analyze-usage my-project "7 days"
```
Review weekly trends and identify optimization opportunities.

### 3. Monthly Reporting
```
/bigquery:analyze-usage my-project "30 days"
```
Generate monthly reports for stakeholders.

### 4. Debugging Cost Overruns
```
/bigquery:analyze-usage my-project "1 hour"
```
When you see a cost spike, analyze the last hour to identify the culprit.

### 5. Service Account Auditing
Identify which service accounts are driving costs and whether their usage is expected.

## Optimization Tips

Common issues the plugin identifies:

### 1. SELECT * Queries
**Problem:** Scanning entire tables when only a few columns are needed.
**Fix:** Specify only required columns.
**Savings:** Often 50-90% reduction in bytes scanned.

### 2. Missing Partitioning
**Problem:** Full table scans on large time-series data.
**Fix:** Partition tables by date column, use partition filters.
**Savings:** 90-99% reduction in bytes scanned.

### 3. Missing Clustering
**Problem:** Scanning entire partitions when querying by specific values.
**Fix:** Cluster tables by frequently filtered columns.
**Savings:** 50-90% reduction in bytes scanned.

### 4. Unfiltered Queries
**Problem:** No WHERE clause, scanning entire table.
**Fix:** Add appropriate WHERE clauses with date/ID filters.
**Savings:** 80-99% reduction in bytes scanned.

### 5. High-Frequency Queries
**Problem:** Running the same expensive query repeatedly.
**Fix:** Use query result caching, reduce frequency, or materialize results.
**Savings:** Depends on frequency, often 70-95% reduction.

### 6. Scheduled Query Frequency
**Problem:** Scheduled queries running more often than necessary.
**Fix:** Reduce frequency if data doesn't change that often.
**Savings:** Linear with frequency reduction.

## Troubleshooting

### Authentication Issues
```bash
gcloud auth login
gcloud config set project <project-id>
```

### Permission Issues
Ensure you have BigQuery Job User role:
```bash
gcloud projects get-iam-policy <project-id> --flatten="bindings[].members" --filter="bindings.members:user:YOUR_EMAIL"
```

### "bq command not found"
Install Google Cloud SDK (see Prerequisites section).

### No Data Returned
- Verify queries ran in the timeframe
- Check you're using the correct region (`region-us` vs `US` vs `EU`)
- Ensure project ID is correct (not project name)

### Slow Analysis
Longer timeframes (30 days) analyze more data and take longer. For very large projects, consider shorter timeframes or analyzing specific users.

## Region Support

By default, queries use `region-us` for INFORMATION_SCHEMA. If your project uses a different region, you may need to adjust queries:

- US multi-region: `region-us` or `US`
- EU multi-region: `region-eu` or `EU`
- Asia multi-region: `region-asia`

The plugin will attempt to detect the correct region automatically.

## Privacy and Security

- All analysis is read-only
- No data is modified or exported outside your environment
- Query text is truncated (first 200-300 chars) in reports
- Sensitive data in query text is not filtered - review reports before sharing
- Reports are saved locally only

## Contributing

This plugin is part of the ai-helpers repository. Contributions welcome!

## License

Same as parent ai-helpers repository.
