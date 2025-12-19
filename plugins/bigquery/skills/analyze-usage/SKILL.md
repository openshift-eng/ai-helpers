---
name: Analyze BigQuery Usage
description: Comprehensive analysis of BigQuery usage patterns, costs, and query performance
---

# Analyze BigQuery Usage

This skill performs comprehensive analysis of BigQuery usage patterns, costs, and query performance for a given project. It identifies expensive queries, heavy users, and provides actionable optimization recommendations.

## When to Use This Skill

This skill is automatically invoked by the `/bigquery:analyze-usage` command to perform usage analysis.

## Prerequisites

- Google Cloud SDK (`bq` command-line tool) must be installed
- User must have BigQuery read access to the project
- User must be authenticated (`gcloud auth login`)
- User needs `bigquery.jobs.list` permission at minimum

## Parameters

When invoked, this skill expects:
- **Project ID**: The GCP project ID to analyze (required)
- **Timeframe**: Time period for analysis in hours (e.g., 24, 168 for 7 days)

## Analysis Workflow

### 1. Validate Prerequisites

First, verify the environment is ready:
- Check if `bq` command is available
- Verify project access
- Parse timeframe into hours

### 2. Collect Usage Data

Execute the following BigQuery queries against INFORMATION_SCHEMA:

#### Total Usage Summary
```sql
SELECT
  COUNT(*) as total_queries,
  ROUND(SUM(total_bytes_processed) / POW(10, 12), 2) as total_tb_scanned,
  ROUND(SUM(total_bytes_processed) / POW(10, 12) * 6.25, 2) as estimated_cost_usd
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @hours HOUR)
  AND job_type = 'QUERY'
  AND state = 'DONE'
  AND statement_type != 'SCRIPT'
```

#### Usage by User/Service Account
```sql
SELECT
  user_email,
  COUNT(*) as query_count,
  ROUND(SUM(total_bytes_processed) / POW(10, 12), 2) as total_tb_scanned,
  ROUND(SUM(total_bytes_processed) / POW(10, 12) * 6.25, 2) as estimated_cost_usd,
  ROUND(AVG(total_bytes_processed) / POW(10, 9), 2) as avg_gb_per_query
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @hours HOUR)
  AND job_type = 'QUERY'
  AND state = 'DONE'
  AND statement_type != 'SCRIPT'
GROUP BY user_email
ORDER BY total_tb_scanned DESC
LIMIT 20
```

#### Top Individual Queries by Cost
```sql
SELECT
  creation_time,
  user_email,
  job_id,
  ROUND(total_bytes_processed / POW(10, 12), 3) as tb_scanned,
  ROUND(total_bytes_processed / POW(10, 12) * 6.25, 2) as cost_usd,
  SUBSTR(query, 1, 200) as query_preview
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @hours HOUR)
  AND job_type = 'QUERY'
  AND state = 'DONE'
  AND statement_type != 'SCRIPT'
  AND total_bytes_processed > 0
ORDER BY total_bytes_processed DESC
LIMIT 20
```

#### Query Pattern Analysis
```sql
SELECT
  SUBSTR(query, 1, 200) as query_pattern,
  COUNT(*) as execution_count,
  ROUND(SUM(total_bytes_processed) / POW(10, 12), 3) as total_tb_scanned,
  ROUND(AVG(total_bytes_processed) / POW(10, 9), 2) as avg_gb_per_execution,
  ANY_VALUE(user_email) as sample_user
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @hours HOUR)
  AND job_type = 'QUERY'
  AND state = 'DONE'
  AND statement_type != 'SCRIPT'
  AND total_bytes_processed > 0
GROUP BY query_pattern
HAVING execution_count > 10
ORDER BY total_tb_scanned DESC
LIMIT 15
```

### 3. Per-User Deep Dive Analysis

For the top 2-3 users by data scanned, perform detailed query pattern analysis:

```sql
SELECT
  SUBSTR(query, 1, 300) as query_pattern,
  COUNT(*) as execution_count,
  ROUND(SUM(total_bytes_processed) / POW(10, 12), 3) as total_tb_scanned,
  ROUND(AVG(total_bytes_processed) / POW(10, 9), 2) as avg_gb_per_execution,
  MIN(creation_time) as first_execution,
  MAX(creation_time) as last_execution
FROM `region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @hours HOUR)
  AND job_type = 'QUERY'
  AND state = 'DONE'
  AND statement_type != 'SCRIPT'
  AND user_email = @user_email
  AND total_bytes_processed > 0
GROUP BY query_pattern
ORDER BY total_tb_scanned DESC
LIMIT 20
```

This reveals:
- What each heavy user is querying
- Patterns in their query behavior
- Opportunities for user-specific optimizations
- Whether queries are automated (service accounts) or manual (humans)

### 4. Analyze Results and Identify Patterns

Look for common issues:

**Query Anti-Patterns:**
- `SELECT *` on large tables
- Full table scans without WHERE clauses
- High-frequency queries that could be cached
- Queries scanning data unnecessarily (e.g., counting rows by scanning 40GB)
- Missing partitioning filters
- Repeated identical queries

**User Behavior Patterns:**
- Service accounts with high query volume (automation candidates)
- Deduplication checks that scan large amounts of data
- Dashboard queries hitting raw tables instead of materialized views
- Scheduled queries running too frequently

**Cost Drivers:**
- Single expensive queries
- High-volume low-cost queries (death by a thousand cuts)
- Inefficient aggregations
- Missing indexes/clustering

### 5. Generate Optimization Recommendations

For each issue found, provide:

1. **What**: Describe the issue clearly
2. **Why**: Explain why it's expensive
3. **How**: Provide specific fix instructions
4. **Savings**: Estimate potential cost reduction
5. **Difficulty**: Rate implementation effort (easy/medium/hard)
6. **Priority**: Based on impact and ease

**Prioritization Framework:**
- Priority 1: High impact, easy wins (>$5/day saved, easy implementation)
- Priority 2: Medium impact (>$2/day saved)
- Priority 3: Architectural improvements (long-term benefits)

### 6. Format Comprehensive Report

Structure the output as:

```markdown
# BigQuery Usage Analysis Report
**Project:** <project-id>
**Analysis Period:** Last <timeframe>
**Generated:** <timestamp>

## Executive Summary
- Total Queries Executed: <count>
- Total Data Scanned: <TB>
- Estimated Cost: $<amount>

### Key Findings
1. <Top issue with data/cost>
2. <Second major issue>
3. <Third issue>

## Usage by User/Service Account
<Table with top 10-20 users>

## Top Query Patterns
<Detailed breakdown of top patterns with recommendations>

## Per-User Analysis

### Top User 1: <user_email> (<TB> scanned, $<cost>)
<Summary of what this user does>

**Primary Query Types:**
1. <Pattern description> (<data scanned>)
   - Execution count
   - Average per query
   - Specific optimization recommendation

### Top User 2: <user_email> (<TB> scanned, $<cost>)
<Summary of what this user does>

**Primary Query Types:**
1. <Pattern description> (<data scanned>)
   - Execution count
   - Average per query
   - Specific optimization recommendation

## Top Individual Queries
<Table of most expensive queries>

## Optimization Recommendations

### Priority 1: High Impact, Easy Wins
1. **<Recommendation title>**
   - Issue: <description>
   - Fix: <specific steps>
   - Estimated Savings: <$/day or %>
   - Difficulty: Easy/Medium/Hard

### Priority 2: Medium Impact
...

### Priority 3: Architectural Improvements
...

## Cost Breakdown Summary
- Service Accounts: $<amount> (<percentage>)
- Human Users: $<amount> (<percentage>)
```

### 7. Offer to Save Report

After presenting the analysis, ask the user if they want to save it to a markdown file:
- Suggest filename: `bigquery-usage-<project-id>-<YYYYMMDD>.md`
- Include all analysis details
- Format with proper markdown tables and sections

## Error Handling

Handle common issues gracefully:

**"bq command not found"**
- Provide installation instructions for user's platform
- macOS: `brew install google-cloud-sdk`
- Linux: Point to cloud.google.com/sdk
- Verify PATH configuration

**"Access Denied" errors**
- Guide user through `gcloud auth login`
- Verify project access: `bq ls --project_id=<project-id>`
- Check IAM permissions (need BigQuery Job User role minimum)

**"Invalid project ID"**
- Verify project ID vs project name
- List available projects: `gcloud projects list`
- Check for typos

**No data returned**
- Verify queries have run in the specified timeframe
- Check region (try `region-us`, `US`, `EU`, etc.)
- Ensure querying correct project

**Query execution errors**
- Check INFORMATION_SCHEMA availability
- Verify region-specific schema locations
- Adjust queries for project's BigQuery setup

## Implementation Notes

### Cost Calculation
- Use on-demand pricing: $6.25/TB (as of 2024-2025)
- Note in report if project may have flat-rate pricing
- Savings estimates are based on on-demand pricing

### Region Handling
- Default to `region-us` INFORMATION_SCHEMA
- If queries fail, try `US` or `EU`
- Consider making region configurable in future

### Performance Considerations
- All analysis queries are read-only
- Use INFORMATION_SCHEMA (metadata only, very efficient)
- Queries should complete in seconds
- Longer timeframes (30 days) may take longer but still fast

### Query Optimization
- Use `--format=json` for easy parsing
- Use `--use_legacy_sql=false` for standard SQL
- Limit result sets appropriately
- Filter to completed queries only (state = 'DONE')

## Example Output Insights

**Good User Analysis Example:**

```
### openshift-ci-data-writer (4.07 TB, $25.41)
This service account runs test run analysis and backend disruption monitoring.

**Primary Query Types:**
1. **TestRuns_Summary_Last200Runs** (3.02 TB - 74% of usage)
   - 96 executions using SELECT *
   - 31.41 GB per query
   - **Recommendation:** Replace SELECT * with specific columns.
     Estimated savings: $9-15/day

2. **BackendDisruption Lookups** (0.68 TB - 17% of usage)
   - 4,165 queries checking for job run names
   - **Recommendation:** Add clustering on JobName + JobRunStartTime.
     Implement result caching.
```

This level of detail helps users understand exactly what's driving their costs and how to fix it.

## Success Criteria

A successful analysis should:
1. Identify all queries scanning >100GB per execution
2. Find high-frequency query patterns (>100 executions)
3. Provide at least 3 actionable optimization recommendations
4. Include cost estimates for top recommendations
5. Offer clear next steps for the user
6. Be formatted clearly and professionally

## Future Enhancements

Consider adding:
- Trend analysis (compare current period to previous periods)
- Query performance metrics (execution time, slot usage)
- Automatic detection of partitioning opportunities
- Cost anomaly detection (unusual spikes)
- Integration with BigQuery Reservations data
- Historical cost tracking over time
