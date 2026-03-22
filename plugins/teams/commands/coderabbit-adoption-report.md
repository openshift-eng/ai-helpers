---
description: Report on CodeRabbit adoption across OCP payload repos
argument-hint: "[--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]"
---

## Name

teams:coderabbit-adoption-report

## Synopsis

```
/teams:coderabbit-adoption-report
/teams:coderabbit-adoption-report --start-date 2026-02-01 --end-date 2026-02-28
```

## Description

The `teams:coderabbit-adoption-report` command measures CodeRabbit adoption across a curated list of ~160 OCP payload repositories by calculating what percentage of merged PRs received comments or reviews from the `coderabbitai[bot]` app.

The list of repos to scan is defined in `plugins/teams/skills/coderabbit-adoption/allowed-repos.txt`.

It uses a Python script that calls the GitHub search API via `gh` CLI. The script always produces per-repo breakdowns. It first does an efficient org-wide query to identify which repos have CodeRabbit activity (~10 API calls), then fetches per-repo total PR counts only for active repos (~30-50 additional API calls with 2-second sleeps). **Takes a few minutes to complete** but shows progress as it goes.

### How CodeRabbit Adoption Works

CodeRabbit requires **two things** to review a PR:

1. **Repo-level enablement**: CodeRabbit must be enabled on the repository (via org-level config or a per-repo `.coderabbit.yaml`).
2. **User license**: The PR author must have a CodeRabbit license/seat assigned.

If a repo has **some PRs with CodeRabbit comments and some without**, the repo is enabled but not all PR authors have licenses. This is the primary adoption gap we want to track and close — the goal is to get the bulk of engineers to sign up for their license.

## Arguments

- `--start-date YYYY-MM-DD` (optional): Start of the date range for merged PRs. Defaults to 7 days ago.
- `--end-date YYYY-MM-DD` (optional): End of the date range for merged PRs. Defaults to today.

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

   ```bash
   # Default (last 7 days)
   python3 plugins/teams/skills/coderabbit-adoption/coderabbit_adoption.py

   # With date range
   python3 plugins/teams/skills/coderabbit-adoption/coderabbit_adoption.py \
     --start-date 2026-02-01 --end-date 2026-02-28
   ```

   The script handles all GitHub API orchestration:
   - **Phase 1** (1 API call): Queries org-wide for CodeRabbit-commented PR count.
   - **Phase 2** (~10 API calls): Paginates CR results to get per-repo CR counts, filtered to the allowed repo list.
   - **Phase 3** (~50-80 API calls): Fetches total PR counts and PR authors per repo that had CR activity, with 2-second sleeps between calls. Identifies unlicensed users by comparing all PR authors against CR PR authors. Shows progress to stderr.

3. **Parse the JSON output** and format the report. Build the unlicensed users table by inverting the per-repo `unlicensed_users` arrays from `repo_breakdown` to show which repos each user was active in. The top-level `unlicensed_users` array has the deduplicated list. Bot accounts are already filtered out.

   ```
   ## CodeRabbit Adoption Report

   **Date Range**: <start_date> to <end_date>

   ### Summary
   - Repos scanned: <total_allowed_repos>
   - Repos with CodeRabbit activity: <repos_with_cr_count>
   - Total merged PRs (active repos): <total>
   - PRs with CodeRabbit comments: <with_cr>
   - Adoption rate (active repos): <percentage>%

   ### Repos with CodeRabbit Activity
   | Repository | PRs with CodeRabbit | Total Merged PRs | Adoption % |
   |---|---|---|---|
   | openshift/console | 39 | 40 | 97.5% |
   | ... | ... | ... | ... |

   ### Repos with No CodeRabbit Activity (<count>)
   <collapsed list of repo names>

   ### Potentially Unlicensed Users (<count>)
   Users who authored merged PRs in CodeRabbit-enabled repos but whose PRs did not receive CodeRabbit comments.
   This likely indicates they do not have a CodeRabbit license/seat assigned.
   Bot accounts (usernames ending in `[bot]` or known bots like `openshift-merge-robot`) are excluded — bots cannot hold CodeRabbit licenses and should not be counted as adoption gaps.
   | User | Repos |
   |---|---|
   | @username | openshift/repo-a, openshift/repo-b |
   | ... | ... |
   ```

4. **Offer to copy report to clipboard**: After presenting the report, ask the user if they'd like the full markdown report copied to their clipboard. If they accept, use `pbcopy` (macOS) or `xclip`/`xsel` (Linux) to copy the complete report.

5. **AI Analysis**: After presenting the data, provide:
   - **License gap analysis** (most important): All repos in the breakdown are already enabled for CodeRabbit. PRs that did *not* get CodeRabbit comments represent engineers without licenses. Highlight repos with the largest absolute gap (total - cr_count) as the highest-impact targets for getting more engineers to sign up. Call out the unlicensed users list — these are the specific people who should be asked to sign up for their CodeRabbit license. Note that bot accounts (e.g. `openshift-merge-robot`, `dependabot[bot]`, `openshift-ci[bot]`) cannot have licenses and are already filtered out of the unlicensed users list — do not flag them as needing licenses. If any remaining `[bot]` suffixed users appear in the data, exclude them from the analysis.
   - Observations on adoption trends (which areas are using CodeRabbit most)
   - Distinguish between repos that need to be **enabled** (in the "no activity" list) vs repos where engineers need to **get their license** (in the breakdown but with less than full coverage)
   - Any notable patterns (e.g., team-level adoption clusters)

## Return Value

- **Markdown report**: Summary statistics and per-repo breakdown table
- **Adoption percentage**: Overall adoption rate across active payload repos
- **Analysis**: Observations and recommendations for increasing adoption

## Examples

1. **Default (last 7 days)**:
   ```
   /teams:coderabbit-adoption-report
   ```

2. **Specific month**:
   ```
   /teams:coderabbit-adoption-report --start-date 2026-02-01 --end-date 2026-02-28
   ```

## Notes

- **Scoped to payload repos**: Only repos listed in `plugins/teams/skills/coderabbit-adoption/allowed-repos.txt` are included. Edit that file to change scope. The list can be regenerated from a release payload with:
  ```bash
  oc adm release info --commits 4.12.0 -o json | \
    jq '.references.spec.tags[].annotations["io.openshift.build.source-location"]' -r | \
    uniq | sort -u > plugins/teams/skills/coderabbit-adoption/allowed-repos.txt
  ```
- **API usage**: ~60-100 API calls total with 2-second sleeps (GitHub search API limit is 30 requests/minute). Takes a few minutes but shows progress. The additional calls are for fetching PR authors per active repo to identify unlicensed users.
- The Python script uses `gh api -X GET` for all GitHub API calls (the `-X GET` flag is required for the search endpoint).
- Uses org-wide search with pagination to efficiently identify which repos have CodeRabbit activity, then only queries per-repo totals for active repos.
- The per-repo CR counts come from paginating org-wide results (up to 1000 items). If more than 1000 PRs have CodeRabbit comments, per-repo counts are approximate (indicated by `per_repo_approximate: true` in the JSON output).
- The `commenter:coderabbitai[bot]` filter matches any PR where the CodeRabbit app left a comment (including review summaries, inline suggestions, and walkthrough comments).
- The adoption percentage is calculated only across repos with CodeRabbit activity, since we don't fetch total PR counts for inactive repos (to save API calls).

## See Also

- Related Command: `/teams:coderabbit-inheritance-scanner` - Scan repos for CodeRabbit config inheritance
- Global CodeRabbit config: https://github.com/openshift/coderabbit
