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

The `teams:coderabbit-adoption-report` command measures CodeRabbit Pro adoption across a curated list of ~160 OCP payload repositories by calculating what percentage of merged PRs received a Pro-tier CodeRabbit review (identified by `"Plan: Pro"` in the comment body).

The list of repos to scan is defined in `plugins/teams/skills/coderabbit-adoption/allowed-repos.txt`.

It uses a Python script that calls the GitHub search API via `gh` CLI. The script does one org-wide query for PRs with Pro reviews, then batched queries (20 repos per batch) for all merged PRs. Per-repo breakdowns are calculated in Python. **Takes about a minute to complete** with progress shown.

### How CodeRabbit Pro Reviews Work

CodeRabbit was enabled across most OCP payload repos on **2026-03-09**. Since many of these repos are open source, CodeRabbit may leave comments on any PR — but only **Pro** reviews (indicated by `Plan: Pro` in the CodeRabbit comment) provide the full-quality analysis we want.

**CodeRabbit does not review bot PRs.** PRs authored by bot accounts (e.g., `dependabot[bot]`, `github-actions[bot]`, `openshift-monitoring-bot[bot]`) are intentionally skipped by CodeRabbit. Bot PRs appearing in the "missed" list are expected and should not be counted against adoption.

The script uses `"Plan: Pro"` as a search term combined with `commenter:coderabbitai[bot]` to directly identify Pro-reviewed PRs, then compares against all merged PRs to find the gap.

The script filters to PRs **created on or after the enablement date** (2026-03-09) to avoid counting old long-lived PRs that merged after enablement but were never seen by CodeRabbit.

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
   - **Query 1** (paginated, ~5 API calls): Org-wide search for PRs with `commenter:coderabbitai[bot] "Plan: Pro"`, filtered to allowed repos.
   - **Query 2** (~8 batched API calls): All merged PRs across allowed repos in batches of 20, with 3-second sleeps and retry logic for rate limits.

   All queries include a `created:>=2026-03-09` filter to exclude PRs opened before CodeRabbit was enabled.

3. **Parse the JSON output** and format the report. The script outputs all data needed: summary stats, missed PRs with URLs, and per-user breakdowns.

   **Detect partial data**: Check if `truncated` is `true`. When true, GitHub search pagination hit its limits (1000 items max). Insert a warning notice in the report.

   ```
   ## CodeRabbit Adoption Report

   **Date Range**: <start_date> to <end_date>
   **PRs created on or after**: <cr_enablement_date>

   ### Summary
   - Repos scanned: <total_allowed_repos>
   - Repos with activity: <repos_with_activity>
   - Total merged PRs: <total_merged_prs>
   - PRs with Pro review: <prs_with_pro_review>
   - Adoption rate: <adoption_pct>%

   ### PRs Without Pro Review (<missed_prs_count>)
   | Repository | PR | Author | Bot? |
   |---|---|---|---|
   | openshift/console | [#16138](https://github.com/openshift/console/pull/16138) | rhamilto | No |
   | openshift/ironic-image | [#816](https://github.com/openshift/ironic-image/pull/816) | github-actions[bot] | Yes |

   ### Users Without Pro Reviews (<count>)
   Users who authored merged PRs but whose PRs did not receive a Pro CodeRabbit review.
   Bot accounts are excluded.
   | User | Repos |
   |---|---|
   | @username | openshift/repo-a, openshift/repo-b |

   ### Repos with No Activity
   <repos_without_activity_count> repos had no merged PRs in this date range.
   ```

4. **Offer to copy report to clipboard**: After presenting the report, ask the user if they'd like the full markdown report copied to their clipboard. If they accept, use `pbcopy` (macOS) or `xclip`/`xsel` (Linux) to copy the complete report.

5. **AI Analysis**: After presenting the data, provide brief observations:
   - Highlight any non-bot missed PRs as the key action items
   - Note that bot PRs are intentionally not reviewed by CodeRabbit (by design, not a timing issue) and are expected in the missed list
   - Non-bot missed PRs are worth investigating (possible config gaps or other issues)
   - Any notable patterns in the missed PRs

## Return Value

- **Markdown report**: Summary statistics, missed PRs table, and user breakdown
- **Adoption percentage**: Overall Pro review adoption rate
- **Analysis**: Brief observations on missed PRs

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
- **Created-date filter**: The script automatically filters to PRs created on or after 2026-03-09 (when CodeRabbit was enabled on most repos). This is hardcoded in the script as `CR_ENABLEMENT_DATE` and prevents old long-lived PRs from skewing adoption numbers.
- **API usage**: ~15 API calls total with 3-second sleeps and retry logic for rate limits. One org-wide paginated query for Pro reviews, plus 8 batched queries for all merged PRs (20 repos per batch).
- The Python script uses `gh api -X GET` for all GitHub API calls (the `-X GET` flag is required for the search endpoint).
- Uses `"Plan: Pro"` as a search term combined with `commenter:coderabbitai[bot]` to directly identify Pro-reviewed PRs via GitHub's full-text search.
- The adoption percentage is calculated across all repos with merged PRs in the date range.

## See Also

- Related Command: `/teams:coderabbit-inheritance-scanner` - Scan repos for CodeRabbit config inheritance
- Global CodeRabbit config: https://github.com/openshift/coderabbit
