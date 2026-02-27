---
description: Analyze recent PR reverts to identify patterns and recommend preventive measures
argument-hint: <path-to-reverts.csv>
---

## Name

ci:analyze-pr-reverts

## Synopsis

```
/ci:analyze-pr-reverts <path-to-reverts.csv>
```

## Description

The `ci:analyze-pr-reverts` command analyzes a CSV of recently reverted pull requests to identify common failure patterns, the most affected repositories, and recommends concrete preventive measures such as new presubmit jobs, org-wide CodeRabbit review rules, or process changes.

This command is intended to be run periodically (e.g., monthly) to track revert trends over time.

### Generating the Input CSV

The input CSV is generated from the Sippy database using:

```bash
psql $DSN_PROD --csv -c "SELECT merged_at, link, author, title FROM prow_pull_requests WHERE title LIKE '%revert%' OR title LIKE '%Revert%' ORDER BY created_at DESC LIMIT 50" > reverts.csv
```

Where `$DSN_PROD` is a read-only connection string for the Sippy production PostgreSQL database.

## Implementation

1. **Parse Arguments**: Extract the path to the CSV file.

   - The CSV must have columns: `merged_at`, `link`, `author`, `title`
   - Validate the file exists and has the expected format
   - Read and parse all rows

2. **Deduplicate**: Remove duplicate entries (same PR URL appearing multiple times).

3. **Scrape PR Details**: For each unique PR URL, fetch details using `gh`:

   ```bash
   gh pr view <url> --json title,body,files,labels
   ```

   Extract from each PR:
   - **Repository**: Parse org/repo from the URL
   - **Description**: The PR body explaining why the revert was needed
   - **Files changed**: What areas of code were affected
   - **Root cause category**: Classify based on the description (see categories below)

   If a PR cannot be fetched (permissions, deleted, etc.), note it and continue.

4. **Categorize Each Revert**: Classify each revert into one or more of these root cause categories based on the PR description and the original PR that was reverted:

   - **Test/platform coverage gap**: New or migrated tests that fail on untested platforms (microshift, single-node, IPv6, FIPS, real-time, upgrade jobs). Look for mentions of specific failing job profiles.
   - **IPv6/network incompatibility**: Changes that work on IPv4 but break IPv6/dual-stack clusters. Look for hardcoded IPv4 addresses, network bind issues.
   - **Operator/controller regression**: Core operator logic changes causing CrashLoopBackOff, degraded states, install failures, or functional breakage.
   - **Build/CI tooling**: Renovate configs, dependency automation, build pipeline changes that break CI.
   - **API/validation side effects**: API changes, CRD validation changes, or policy enforcement that has unexpected downstream impact.
   - **Feature flag/config change**: Premature feature gate removal, default value changes, config toggles.
   - **Cross-component dependency**: Change that depends on another component's change that hasn't landed or built yet.
   - **Flaky/unstable new test**: New test that passes sometimes but flakes at a high enough rate to block payloads.

5. **Generate Statistics**:

   - **Reverts by repository**: Count and rank repos by number of reverts
   - **Reverts by category**: Count and rank root cause categories
   - **Repeat offenders**: PRs that were reverted, re-merged, and reverted again
   - **Most common failing job profiles**: Which CI job profiles appear most in revert descriptions (e.g., `e2e-metal-ipi-ovn-ipv6`, `e2e-aws-ovn-microshift`)
   - **Reverts by author**: Identify if certain authors/teams have recurring patterns
   - **TRT-initiated vs. author-initiated**: How many were quick-reverts by TRT (Revertomatic) vs. self-reverts

6. **Generate Preventive Recommendations**: Based on the patterns found, produce actionable recommendations in three areas:

   ### a. New Presubmit Jobs / CI Coverage

   For each pattern of reverts caused by missing platform coverage, recommend specific presubmit or payload jobs that should be added. Common recommendations include:

   - If IPv6 reverts are frequent: Recommend repos add `/payload-job e2e-metal-ipi-ovn-ipv6` to presubmit or require it before merge
   - If microshift reverts are frequent: Recommend repos add microshift conformance jobs
   - If single-node reverts are frequent: Recommend single-node upgrade jobs
   - If upgrade reverts are frequent: Recommend upgrade-from-previous-version jobs
   - If FIPS reverts are frequent: Recommend FIPS-specific jobs

   Be specific about which repos need which jobs based on the data.

   ### b. CodeRabbit Review Rules

   Recommend new review rules for the [openshift/coderabbit](https://github.com/openshift/coderabbit) repository's `.coderabbit.yaml` configuration. The coderabbit repo contains org-wide review guidelines that apply to all OpenShift repositories.

   The existing `.coderabbit.yaml` already has checks for:
   - Stable/deterministic test names
   - Test structure and quality
   - MicroShift compatibility

   Based on the revert patterns, recommend NEW `pre_merge_checks.custom_checks` entries. For example:

   - **IPv6 compatibility check**: Flag hardcoded IPv4 addresses (`0.0.0.0`, `127.0.0.1`) in network-related code, recommend dual-stack testing
   - **Multi-node assumptions check**: Flag tests that assume multiple nodes without checking node count
   - **Feature gate removal check**: Flag removal of feature gates without verifying downstream consumers
   - **Cross-component dependency check**: Flag changes that import or depend on unreleased changes in other repos
   - **Upgrade compatibility check**: Flag changes to operator behavior that could break upgrade paths

   For each recommendation, provide the complete YAML block that could be added to `.coderabbit.yaml` in the same format as the existing checks (name, mode, instructions).

   ### c. Process / Documentation Recommendations

   - Recommend documentation updates, team process changes, or other non-automated improvements
   - Identify if specific teams need targeted guidance
   - Suggest improvements to the revert process itself if patterns indicate issues

7. **Format the Report**: Output a well-structured markdown report with the following sections:

   ```
   ## PR Revert Analysis Report
   ### Date Range: [earliest] to [latest merged_at]
   ### Summary
   ### Reverts by Repository
   ### Reverts by Root Cause Category
   ### Repeat Reverts (PRs reverted more than once)
   ### Most Common Failing Job Profiles
   ### Detailed Revert List (table with: repo, PR link, category, brief reason)
   ### Recommendations
   #### New Presubmit Jobs
   #### New CodeRabbit Review Rules
   #### Process Improvements
   ```

   All PR links in the report MUST use full GitHub URLs (e.g., `https://github.com/openshift/machine-config-operator/pull/5703`), never shorthand references like `#5703` which would resolve relative to whatever repo the reader is viewing.

## Return Value

- **Markdown report**: Full analysis report as described above
- **Recommended CodeRabbit YAML**: Ready-to-use YAML blocks for `.coderabbit.yaml`
- **Summary statistics**: Key numbers (total reverts, top repo, top category)

## Examples

1. **Basic usage**:
   ```
   /ci:analyze-pr-reverts ~/reverts.csv
   ```

2. **With freshly generated data**:
   ```bash
   # First, generate the CSV:
   psql $DSN_PROD --csv -c "SELECT merged_at, link, author, title FROM prow_pull_requests WHERE title LIKE '%revert%' OR title LIKE '%Revert%' ORDER BY created_at DESC LIMIT 50" > reverts.csv

   # Then analyze:
   /ci:analyze-pr-reverts reverts.csv
   ```

## Arguments

- `$1` (required): Path to the CSV file containing revert PR data
  - Must have columns: `merged_at`, `link`, `author`, `title`
  - Generated via the psql query documented above

## Prerequisites

1. **GitHub CLI (`gh`)**: Must be installed and authenticated
   - Check: `gh auth status`
   - Needed to fetch PR details (description, files, labels) for each revert

2. **CSV input file**: Generated from the Sippy production database
   - Requires access to `$DSN_PROD` for the psql query

## Notes

- Some PRs may not be fetchable via `gh` (private repos, deleted PRs, permission issues). These are noted in the report but don't block analysis.
- The query captures PRs with "revert" or "Revert" in the title. Some legitimate non-revert PRs may be included (e.g., "unrevert" PRs that restore previously reverted changes). Filter these out during analysis.
- PRs from non-openshift orgs (e.g., `Azure/ARO-HCP`) may have limited `gh` access. Include them in stats but note if details couldn't be fetched.
- The recommended CodeRabbit rules should be conservative (mode: `warning` not `error`) to avoid blocking legitimate PRs while the rules are tuned.

## See Also

- Related Command: `ci:revert-pr` - Create a revert PR for a breaking change
- CodeRabbit Config: https://github.com/openshift/coderabbit
- OpenShift Quick Revert Policy: https://github.com/openshift/enhancements/blob/master/enhancements/release/improving-ci-signal.md#quick-revert
- Revertomatic: https://github.com/stbenjam/revertomatic
