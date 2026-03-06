---
description: Report on CodeRabbit adoption across OpenShift org PRs
argument-hint: "[--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--detailed]"
---

## Name

teams:coderabbit-adoption-report

## Synopsis

```
/teams:coderabbit-adoption-report
/teams:coderabbit-adoption-report --start-date 2026-02-01 --end-date 2026-02-28
/teams:coderabbit-adoption-report --detailed
```

## Description

The `teams:coderabbit-adoption-report` command measures CodeRabbit adoption across the `openshift` GitHub organization by calculating what percentage of merged PRs received comments or reviews from the `coderabbitai[bot]` app.

It uses a Python script that calls the GitHub search API via `gh` CLI. By default it produces a lightweight org-wide summary using only 2 API calls. Use `--detailed` for per-repo breakdowns with adoption percentages and a "no activity" check on well-known repos (~50 extra API calls, prone to rate limiting).

### How CodeRabbit Adoption Works

CodeRabbit requires **two things** to review a PR:

1. **Repo-level enablement**: CodeRabbit must be enabled on the repository (via org-level config or a per-repo `.coderabbit.yaml`).
2. **User license**: The PR author must have a CodeRabbit license/seat assigned.

If a repo has **some PRs with CodeRabbit comments and some without**, the repo is enabled but not all PR authors have licenses. This is the primary adoption gap we want to track and close — the goal is to get the bulk of engineers to sign up for their license.

## Arguments

- `--start-date YYYY-MM-DD` (optional): Start of the date range for merged PRs. Defaults to 30 days ago.
- `--end-date YYYY-MM-DD` (optional): End of the date range for merged PRs. Defaults to today.
- `--detailed` (optional): Fetch per-repo breakdowns with adoption percentages and check well-known repos for missing CodeRabbit activity. Makes ~50 additional API calls with 2-second sleeps between each to respect the GitHub search API rate limit (30 requests/minute). **Takes several minutes to complete and is still prone to hitting rate limits.** Only use when the user explicitly requests it. Never add `--detailed` automatically.

## Implementation

### Prerequisites
- **GitHub CLI (`gh`)**: Must be installed and authenticated with access to the `openshift` org.
- **Python 3**: Python 3.6 or later is required.

### Steps

1. **Verify prerequisites**:

   ```bash
   gh auth status
   python3 --version
   ```

2. **Run the Python script** with arguments passed through from the command.

   **IMPORTANT**: Only pass `--detailed` if the user explicitly requested it. Never add it automatically — it makes ~50 extra GitHub API calls and is prone to hitting rate limits even with built-in 2-second sleeps.

   ```bash
   # Default (last 30 days, lightweight — always use this unless user asks for --detailed)
   python3 plugins/teams/skills/coderabbit-adoption/coderabbit_adoption.py

   # With date range
   python3 plugins/teams/skills/coderabbit-adoption/coderabbit_adoption.py \
     --start-date 2026-02-01 --end-date 2026-02-28

   # Detailed mode — ONLY when user explicitly requests --detailed
   python3 plugins/teams/skills/coderabbit-adoption/coderabbit_adoption.py --detailed
   ```

   The script handles all GitHub API orchestration:
   - **Default** (2 API calls): Queries total merged PRs and CodeRabbit-commented PRs. No per-repo querying. Fast and safe from rate limits.
   - **With `--detailed`** (~50 API calls): Paginates for per-repo CR counts, fetches total PR counts per top repo for adoption percentages, and checks well-known high-volume repos for missing CodeRabbit activity. Uses 2-second sleeps between calls to respect the GitHub search API rate limit (30 requests/minute) but may still hit limits. Takes several minutes to complete.

3. **Parse the JSON output** and format the report.

   **Default mode** (no `--detailed`):
   ```
   ## CodeRabbit Adoption Report

   **Date Range**: <start_date> to <end_date>

   ### Summary
   - Total merged PRs: <total>
   - PRs with CodeRabbit comments: <with_cr>
   - Adoption rate: <percentage>%
   ```

   **Detailed mode** (with `--detailed`):
   ```
   ### Top Repos by CodeRabbit Activity
   | Repository | PRs with CodeRabbit | Total Merged PRs | Adoption % |
   |---|---|---|---|
   | openshift/assisted-installer | 60 | 65 | 92.3% |
   | ... | ... | ... | ... |

   ### Repos with No CodeRabbit Activity
   | Repository | Total Merged PRs |
   |---|---|
   | openshift/release | 1072 |
   | ... | ... |
   ```

4. **AI Analysis**: After presenting the data, provide:
   - **License gap analysis** (most important): Any repo appearing in `repo_breakdown` is already enabled for CodeRabbit. PRs in those repos that did *not* get CodeRabbit comments represent engineers without licenses. In detailed mode, highlight repos with the largest absolute gap (total - cr_count) as the highest-impact targets for getting more engineers to sign up. In default mode, note that all listed repos are enabled and the overall gap (total_merged_prs - prs_with_coderabbit) across enabled repos represents the user license opportunity.
   - Observations on adoption trends (which areas of the org are using CodeRabbit most)
   - Distinguish between repos that need to be **enabled** (not appearing in repo_breakdown at all) vs repos where engineers need to **get their license** (appearing in repo_breakdown but with less than full coverage)
   - Any notable patterns (e.g., team-level adoption clusters)
   - If running in default mode, mention that `--detailed` is available for per-repo adoption percentages but warn it is prone to GitHub API rate limits

## Return Value

- **Markdown report**: Summary statistics and per-repo breakdown table
- **Adoption percentage**: Overall adoption rate (per-repo percentages only with `--detailed`)
- **Analysis**: Observations and recommendations for increasing adoption

## Examples

1. **Default (last 30 days, lightweight)**:
   ```
   /teams:coderabbit-adoption-report
   ```

2. **Specific month**:
   ```
   /teams:coderabbit-adoption-report --start-date 2026-02-01 --end-date 2026-02-28
   ```

3. **Detailed with per-repo adoption percentages**:
   ```
   /teams:coderabbit-adoption-report --detailed
   ```

## Notes

- **API usage**: Default mode uses only 2 API calls and is safe from rate limits. `--detailed` adds ~50 more with 2-second sleeps between each (GitHub search API limit is 30 requests/minute for authenticated users). Even with throttling, `--detailed` may still hit rate limits. **Never use `--detailed` unless the user explicitly asks for it.**
- The Python script uses `gh api -X GET` for all GitHub API calls (the `-X GET` flag is required for the search endpoint).
- Uses GitHub search API `total_count` for the summary, which is accurate beyond the 1000-result pagination limit.
- The per-repo breakdown (detailed mode only) is limited to the first 1000 CodeRabbit-commented PRs due to GitHub search pagination limits. If more than 1000 PRs have CodeRabbit comments, the per-repo table is approximate but the overall percentage is still accurate (indicated by `per_repo_approximate: true` in the JSON output).
- The `commenter:coderabbitai[bot]` filter matches any PR where the CodeRabbit app left a comment (including review summaries, inline suggestions, and walkthrough comments).
- Private repos are included if the `gh` token has access; otherwise they are silently excluded.
- The "no activity" list (detailed mode only) checks well-known high-volume openshift repos and only shows those with 10+ merged PRs.

## See Also

- Related Command: `/teams:coderabbit-inheritance-scanner` - Scan repos for CodeRabbit config inheritance
- Global CodeRabbit config: https://github.com/openshift/coderabbit
