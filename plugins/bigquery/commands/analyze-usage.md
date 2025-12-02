---
description: Analyze BigQuery usage and costs for a project
argument-hint: <project-id> <timeframe>
---

## Name
bigquery:analyze-usage

## Synopsis
```
/bigquery:analyze-usage <project-id> <timeframe>
/bigquery:analyze-usage openshift-ci-data-analysis "24 hours"
/bigquery:analyze-usage my-project "7 days"
```

## Description

The `analyze-usage` command provides comprehensive analysis of BigQuery usage patterns, costs, and query performance for a given project. It identifies expensive queries, heavy users, and provides actionable optimization recommendations.

This command helps answer questions like:
- Which users or service accounts are consuming the most data?
- What are the most expensive queries?
- Which query patterns are running most frequently?
- How can we reduce BigQuery costs?
- Are we over any usage thresholds?

The analysis includes:
- Total usage summary (queries, data scanned, estimated costs)
- Usage breakdown by user/service account
- Per-user deep dive analysis for top 2-3 users
- Top individual queries by cost
- Query pattern analysis to identify optimization opportunities
- Specific, actionable optimization recommendations
- Optional markdown report generation

## Implementation

This command uses the `bigquery:analyze-usage` skill to perform the analysis.

### Prerequisites
- Google Cloud SDK (`bq` command-line tool) must be installed
- User must have BigQuery read access to the project
- User must be authenticated (`gcloud auth login`)

### Steps

1. **Parse and Validate Arguments**:
   - If project-id is missing: Use AskUserQuestion to prompt for it
   - If timeframe is missing: Use AskUserQuestion to prompt for it (options: "1 hour", "6 hours", "24 hours", "7 days", "30 days")
   - Parse timeframe into hours (e.g., "24 hours" → 24, "7 days" → 168)

2. **Invoke the analyze-usage Skill**:
   ```
   Use the Skill tool to invoke "bigquery:analyze-usage"
   ```
   The skill will handle all the data collection and analysis.

3. **Present Results**:
   The skill returns a comprehensive report. Present it to the user in a clear, readable format with:
   - Executive summary at the top
   - Tables for user usage and top queries
   - Per-user deep dive for top 2-3 users showing their specific query patterns
   - Detailed query pattern analysis
   - Prioritized optimization recommendations

4. **Offer to Save Report**:
   After presenting the analysis, ask the user if they want to save it to a markdown file:
   - Suggest filename: `bigquery-usage-<project-id>-<timestamp>.md`
   - If user agrees, use Write tool to save the formatted report
   - Include timestamp and all analysis details in the file

## Return Value
- **Success**: Comprehensive usage analysis report
- **Error**: Authentication errors, missing permissions, invalid project, or bq tool not found

**Important for Claude**:
1. **REQUIRED**: You MUST invoke the `bigquery:analyze-usage` skill using the Skill tool
2. Always validate both arguments before proceeding
3. If arguments are missing, use AskUserQuestion to collect them
4. Present the report in a clean, readable format
5. Always offer to save the report to a markdown file at the end
6. Handle errors gracefully with helpful suggestions

## Examples

1. **Analyze last 24 hours for a project**:
   ```
   /bigquery:analyze-usage openshift-ci-data-analysis "24 hours"
   ```
   Returns comprehensive report showing:
   - Total of 9.76 TB scanned
   - Top users: openshift-ci-data-writer (4.12 TB), job-run-big-query-writer (3.89 TB)
   - Most expensive query pattern: TestRuns_Summary_Last200Runs (3.05 TB)
   - Specific optimization recommendations
   - Offer to save to `bigquery-usage-openshift-ci-data-analysis-20251202.md`

2. **Analyze last 7 days**:
   ```
   /bigquery:analyze-usage my-project "7 days"
   ```
   Provides weekly usage analysis with trends and patterns.

3. **Missing arguments - prompts user**:
   ```
   /bigquery:analyze-usage
   ```
   Claude asks:
   - "Which project would you like to analyze?"
   - "What timeframe should I analyze?" (with options)

4. **Partial arguments**:
   ```
   /bigquery:analyze-usage openshift-ci-data-analysis
   ```
   Claude asks: "What timeframe should I analyze?" (with options: 1 hour, 6 hours, 24 hours, 7 days, 30 days)

## Arguments

- **project-id** (required): The GCP project ID to analyze
  - Example: `openshift-ci-data-analysis`
  - Must be a valid BigQuery project the user has access to

- **timeframe** (required): Time period for analysis
  - Supported formats:
    - "1 hour", "6 hours", "24 hours"
    - "1 day", "7 days", "30 days"
    - Or just numbers for hours: "24", "168"
  - Default if not specified: Prompt user with options

## Timeframe Conversion
- "1 hour" → 1 hour
- "6 hours" → 6 hours
- "24 hours" or "1 day" → 24 hours
- "7 days" → 168 hours (7 × 24)
- "30 days" → 720 hours (30 × 24)
- Numeric values are treated as hours

## Report Contents

The generated report includes:

### 1. Executive Summary
- Analysis timeframe
- Total queries executed
- Total data scanned (in TB/GB)
- Estimated cost (using $6.25/TB on-demand pricing)
- Key findings (top 3 issues)

### 2. Usage by User/Service Account
Table showing top 10-20 users:
- User email or service account
- Number of queries
- Total data scanned
- Estimated cost
- Average data per query

### 3. Top Query Patterns
Detailed breakdown of top 5-10 query patterns:
- Query preview (first 200 chars)
- Execution count
- Total data scanned across all executions
- Average data per execution
- Sample user who ran it
- Specific optimization recommendation

### 4. Per-User Analysis (Top 2-3 Users)
For each top user by data scanned:
- User email and total usage summary
- What this user/service account does (inferred from queries)
- Breakdown of primary query types with:
  - Data scanned per pattern
  - Execution count
  - Behavior patterns (automation, time windows, etc.)
  - Specific optimization recommendations for this user

### 5. Top Individual Queries
Table of top 20 queries by bytes scanned:
- Timestamp
- User
- Data scanned
- Query preview
- Job ID

### 6. Optimization Recommendations
Prioritized list of actions:
- What to optimize
- Why it's expensive
- How to fix it
- Estimated savings
- Implementation difficulty

## Notes

- **Pricing**: Cost estimates use on-demand pricing ($6.25/TB). Projects with flat-rate pricing will have different actual costs.
- **Region**: Queries assume `region-us` INFORMATION_SCHEMA. May need adjustment for other regions.
- **Authentication**: User must be authenticated via `gcloud auth login`
- **Permissions**: User needs `bigquery.jobs.list` permission at minimum
- **Performance**: Analysis queries are read-only and lightweight (use INFORMATION_SCHEMA)
- **Timeframes**: Longer timeframes (30 days) may take longer to analyze due to more data

## Troubleshooting

**"bq command not found"**
- Install Google Cloud SDK: `brew install google-cloud-sdk` (macOS) or visit cloud.google.com/sdk

**"Access Denied" errors**
- Run `gcloud auth login` to authenticate
- Verify you have access to the project: `bq ls --project_id=<project-id>`
- Check you have BigQuery Job User role or higher

**"Invalid project ID"**
- Verify project ID is correct (not project name)
- Check project exists: `gcloud projects list`

**No data returned**
- Verify queries have run in the specified timeframe
- Check the region (try `region-us`, `US`, `EU`, etc.)
- Ensure you're querying the right project
