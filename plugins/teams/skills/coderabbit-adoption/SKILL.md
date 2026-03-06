---
name: CodeRabbit Adoption Report
description: Report on CodeRabbit adoption across OpenShift org PRs
---

# CodeRabbit Adoption Report

This skill queries the GitHub search API to measure what percentage of merged PRs in the `openshift` GitHub organization received comments from the `coderabbitai[bot]` app.

## When to Use This Skill

Use this skill when you need to:

- Measure CodeRabbit adoption rates across the openshift org
- Identify repos with high or low CodeRabbit usage
- Generate adoption reports for stakeholders
- Track adoption trends over time

## Prerequisites

1. **GitHub CLI (`gh`)**: Must be installed and authenticated with access to the `openshift` org.

   ```bash
   gh auth status
   ```

2. **Python 3**: Python 3.6 or later is required.

## Implementation Steps

### Step 1: Verify Prerequisites

```bash
gh auth status
python3 --version
```

### Step 2: Run the Script

The script is located at:

```
plugins/teams/skills/coderabbit-adoption/coderabbit_adoption.py
```

Execute with appropriate arguments:

```bash
# Default: last 30 days, org-wide summary only (2 API calls)
python3 plugins/teams/skills/coderabbit-adoption/coderabbit_adoption.py

# Specific date range
python3 plugins/teams/skills/coderabbit-adoption/coderabbit_adoption.py \
  --start-date 2026-02-01 --end-date 2026-02-28

# Detailed mode: per-repo breakdowns (~50 API calls, prone to rate limiting)
# ONLY use when user explicitly requests --detailed
python3 plugins/teams/skills/coderabbit-adoption/coderabbit_adoption.py --detailed
```

### Step 3: Parse the Output

The script outputs JSON to stdout with the following structure:

**Default mode** (2 API calls, no per-repo data):

```json
{
  "start_date": "2026-02-04",
  "end_date": "2026-03-06",
  "total_merged_prs": 7950,
  "prs_with_coderabbit": 1445,
  "adoption_pct": 18.2,
  "detailed": false,
  "repo_breakdown": [],
  "no_coderabbit_activity": []
}
```

**Detailed mode** (~50 API calls, with per-repo data):

```json
{
  "start_date": "2026-02-04",
  "end_date": "2026-03-06",
  "total_merged_prs": 7950,
  "prs_with_coderabbit": 1445,
  "adoption_pct": 18.2,
  "detailed": true,
  "per_repo_approximate": true,
  "repo_breakdown": [
    {
      "repo": "openshift/cincinnati-graph-data",
      "cr_count": 150,
      "total": 196,
      "adoption_pct": 76.5
    }
  ],
  "no_coderabbit_activity": [
    {
      "repo": "openshift/release",
      "total": 1072
    }
  ]
}
```

**Field Descriptions**:

- `start_date`, `end_date`: The date range queried
- `total_merged_prs`: Total merged PRs in the openshift org
- `prs_with_coderabbit`: PRs where coderabbitai[bot] commented
- `adoption_pct`: Overall adoption percentage
- `detailed`: Whether detailed mode was used
- `per_repo_approximate`: (detailed only) True if per-repo breakdown is approximate (>1000 CodeRabbit PRs)
- `repo_breakdown`: (detailed only) Array of top repos sorted by CR count descending
- `no_coderabbit_activity`: (detailed only) High-volume repos with zero CodeRabbit comments

### Step 4: Format and Present the Report

- **Default mode**: Present the summary stats (total PRs, CodeRabbit PRs, adoption %)
- **Detailed mode**: Also include per-repo table and no-activity list

### Step 5: AI Analysis

After presenting the data, provide:

- License gap analysis: repos in `repo_breakdown` are enabled; missing reviews = engineers without licenses
- Observations on adoption trends
- In default mode, mention `--detailed` is available but warn it is prone to GitHub API rate limits

## Notes

- **API usage**: Default mode uses only 2 API calls. `--detailed` makes ~50 calls with 2-second sleeps between each to respect GitHub's search API rate limit (30 requests/minute). Even with throttling, `--detailed` may hit rate limits and takes several minutes.
- The script uses `gh` CLI with `-X GET` for all GitHub API calls (required for the search endpoint)
- Uses Python's standard library only (no external dependencies)
- Diagnostic messages go to stderr, JSON data to stdout
- Never use `--detailed` unless the user explicitly asks for it
