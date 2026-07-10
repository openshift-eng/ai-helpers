---
description: Triage all open CVEs for OpenShift Node team components with reachability analysis
argument-hint: "[--component <name>] [--notify-jira] [--notify-slack] [--days N]"
---

## Name
node-cve:triage

## Synopsis
```text
/node-cve:triage [--component "Node / CRI-O"] [--notify-jira] [--notify-slack] [--days 7]
```

## Description

Queries all open CVE vulnerability issues in OCPBUGS for Node team components, deduplicates across version trackers, clones affected repositories, and analyzes source code for CVE reachability. Optionally posts analysis comments to Jira trackers and sends a Slack summary.

Designed for both interactive use and headless execution via `claude --print`.

## Prerequisites

- `jira` CLI ([ankitpokhrel/jira-cli](https://github.com/ankitpokhrel/jira-cli)) configured with Jira credentials
- Environment variables: `JIRA_API_TOKEN`
- `git` (for cloning repos)
- Optional: `curl` and either `SLACK_API_TOKEN` + `SLACK_CHANNEL` or `SLACK_WEBHOOK` (for `--notify-slack`)

## Implementation

### Phase 0: Setup and Argument Parsing

1. **Parse Arguments**
   - `--component <name>`: Filter to a specific OCPBUGS component (e.g., "Node / CRI-O"). Optional.
   - `--notify-jira`: Post analysis results as comments on Jira tracker issues. Default: off.
   - `--notify-slack`: Send summary to Slack. Requires either `$SLACK_API_TOKEN` + `$SLACK_CHANNEL` (enables threading) or `$SLACK_WEBHOOK` (simpler, no threading). Default: off.
   - `--days N`: Only include CVEs created or updated in the last N days. Default: all open.

2. **Validate Tools**

   ```bash
   which jira 2>/dev/null || echo "MISSING: jira CLI"
   which git 2>/dev/null || echo "MISSING: git"
   ```

   If any required tool is missing, display installation instructions and exit.

3. **If `--notify-slack`**, verify Slack credentials. Either `$SLACK_API_TOKEN` + `$SLACK_CHANNEL` (preferred, enables threaded messages) or `$SLACK_WEBHOOK` (simpler, no threading). Exit with error if neither is configured. If `$SLACK_CHANNEL` is not set, default to `GK6BJJ1J5` (`#team-node`).

4. **Create work directory**: `mkdir -p .work/node-cve/repos .work/node-cve/triage-$(date +%Y-%m-%d)`

---

### Phase 1: Query Open CVEs

- **Skill**: [query-open-cves](../skills/query-open-cves/SKILL.md)
- **Input**: Optional `--component` filter, optional `--days` filter
- **Output**: Deduplicated list of CVEs with metadata

**Steps:**

1. Build the JQL query using the CVE-tracked component list from the [node-team shared components reference](../../node-team/skills/node/references/shared/components.md) (the full Jira component list plus Driver Toolkit and Machine Config Operator):

   ```bash
   jira issue list -q "project = OCPBUGS AND type = Vulnerability AND component in (<components from shared reference>) AND status not in (Closed, Done, Verified)" --plain --no-headers --columns KEY,SUMMARY,COMPONENT,STATUS,ASSIGNEE,LABELS
   ```

   If `--component` is specified, replace the component list with the single component.
   If `--days N` is specified, add `AND updated >= -${N}d` to the query.

2. Parse results and extract CVE IDs from summaries (regex: `CVE-[0-9]{4}-[0-9]+`).

3. Deduplicate: group tracker issues by CVE ID. For each unique CVE, collect:
   - All tracker keys (e.g., OCPBUGS-85948, OCPBUGS-85932, ...)
   - Affected OCP versions (extracted from summary brackets, e.g., `[openshift-4.19]`)
   - Component names (a CVE may span multiple components)
   - Assignee (from the highest version tracker)
   - Status

4. Print intermediate summary: "Found N unique CVEs across M tracker issues."

**Decision Point:**
- IF 0 CVEs found -> Print "No open CVEs for Node team components." -> Exit
- IF CVEs found -> Continue to Phase 2

---

### Phase 1.5: Check for Prior Analysis (Cache Check)

Before cloning repos and running analysis, check for existing results from prior runs. This avoids redundant reanalysis when the tool is run repeatedly.

For each unique CVE from Phase 1, check two cache sources in order:

**1. Local artifacts** (always available): Look for existing analysis files in `.work/node-cve/triage-*/`:

```bash
ls .work/node-cve/triage-*/<CVE-ID>-*-analysis.md 2>/dev/null | sort -r | head -1
```

If prior analysis files exist, extract the classification and date from the filename/content. If the analysis is recent (within the last 30 days), reuse the cached result for that branch.

Compare the affected versions from Phase 1 against cached branches. If new OCP versions have appeared for a CVE since the last run (e.g., 4.20 trackers added after a run that covered 4.14-4.19), only the uncovered branches need analysis. Branches with valid cached results are reused.

**2. Jira comments** (if `--notify-jira` was used on a prior run): Check the primary tracker issue for existing comments:

```bash
jira issue comment list OCPBUGS-XXXXX --plain --no-headers
```

Search for comments containing `[node-cve:triage|`. This pattern anchors on the Jira wiki-markup link syntax and matches both the current and legacy footer formats. If a prior analysis comment exists and is recent (within 30 days), reuse the cached result. If a follow-up comment after the analysis contains a `[reanalyze]` tag, force re-analysis for that CVE (all branches).

**Cache invalidation:**
- Analysis older than 30 days: re-analyze
- Jira comment with `[reanalyze]` tag posted after the analysis: re-analyze all branches
- New CVEs (no prior result): always get full analysis
- New branches for an existing CVE (no cached analysis for that branch): analyze only the new branches

Print which CVEs are skipped or partially cached: "CVE-XXXX-XXXXX: reusing prior analysis (Reachable)" or "CVE-XXXX-XXXXX: cached for 5 branches, analyzing 1 new branch (release-1.33)"

---

### Phase 2: Clone Repos and Analyze CVEs in Parallel

- **Skill**: [analyze-cve-repos](../skills/analyze-cve-repos/SKILL.md)
- **Input**: List of unique CVEs from Phase 1
- **Output**: Reachability results per CVE

#### Step 1: Determine affected repos, branches, and clone

Analysis must target the release branch that corresponds to each affected OpenShift version. The `main` branch may have newer dependencies or Go versions that mask vulnerabilities present in older release branches. Analysis targets downstream forks only. If the downstream fork or branch does not exist, classify as Uncertain with note "downstream fork/branch not found" and skip analysis.

**Component to repository mapping:** Read from the [node-team shared components reference](../../node-team/skills/node/references/shared/components.md). Use the "Component to Repository Mapping" table for downstream forks and branch patterns, and the "pscomponent Label Mapping" table for label-based repo resolution.

**OpenShift version to release branch mapping:** Read from the [node-team shared version map](../../node-team/skills/node/references/shared/version-map.md). For OCP 4.Y, the formula is `K8s/CRI-O minor = Y + 13`. Use the formula and branch naming conventions to derive the correct release branch for each repo.

**Clone strategy:**

For each CVE, determine ALL affected OCP versions from its tracker summaries (e.g., `[openshift-4.16]`, `[openshift-4.18]`). Clone the repo at each corresponding release branch. Features can be added, removed, or refactored across releases, so a CVE may be reachable on one version but not affected on another. Analyzing only the oldest branch would miss these differences.

For each affected version's release branch, clone the downstream fork:

```bash
timeout 600 git clone --depth 1 --branch <release-branch> <downstream-fork-url> .work/node-cve/repos/<repo-name>-<branch>/
```

If the clone fails (timeout, branch not found, or fork does not exist), mark that version as Uncertain with note "downstream fork/branch not found" and skip analysis for it.

Use `--depth 1` for speed. Multiple CVEs sharing the same repo and branch reuse the same clone. All clones must complete before proceeding to Step 2.

#### Step 2: Analyze CVEs across all affected branches in parallel

Spawn a concurrent analysis agent for each unique CVE and release branch combination. For example, if CVE-2026-32281 affects OCP 4.15 through 4.19, spawn separate agents for release-1.28, release-1.29, release-1.30, release-1.31, and release-1.32. Each agent runs the [analyze-cve-repos](../skills/analyze-cve-repos/SKILL.md) skill independently:

1. **Gather CVE intelligence**: fetch vulnerability details from public sources (NVD, advisories, Jira issue description/comments) to identify the affected package, vulnerable functions, and attack vector. This step is shared across branches for the same CVE (gather once, reuse).

2. **Check dependency presence**: search dependency files (`go.mod`, `Cargo.toml`, build files, vendored code) for the affected package. If not present, classify as Unaffected for this branch.

3. **Analyze source code for reachability**: search the codebase for imports and calls to the vulnerable function. Read the relevant source files to trace call paths from entry points to the vulnerable function. Assess whether attacker-controlled input reaches the vulnerable code path and identify any mitigating controls (input validation, size limits, feature flags, authentication).

4. **Classify result per branch**:
   - **Reachable** (high confidence): vulnerable function called with attacker-controlled input, no mitigations
   - **Reachable** (medium confidence): vulnerable function called, but input is partially validated
   - **Present but not exploitable** (high confidence): vulnerable function called, but only with trusted/internal data
   - **Present but not reachable** (high confidence): package imported but vulnerable function not called
   - **Unaffected** (high confidence): package not in dependency tree
   - **Uncertain** (low confidence): repo too large to fully analyze, or CVE details insufficient

5. **Save analysis** to `.work/node-cve/triage-$(date +%Y-%m-%d)/<CVE-ID>-<branch>-analysis.md` with file paths, call sites, and evidence.

Wait for all agents to complete, then collect results. A CVE's overall classification is the most severe across all analyzed branches (e.g., if Reachable on release-1.28 but Unaffected on release-1.32, the overall result is Reachable). Print progress for each: "Analyzed CVE-XXXX-XXXXX against <repo> (<branch>): <result>"

The per-branch results are preserved in the report so reviewers can see which versions are affected. Post the version-specific result to each version's Jira tracker (e.g., the 4.18 tracker gets the release-1.31 analysis result).

---

### Phase 3: Report Findings

- **Skill**: [report-findings](../skills/report-findings/SKILL.md)
- **Input**: Analysis results from Phase 2, notification flags
- **Output**: Report file, optional Jira comments, optional Slack message

1. **Generate report** at `.work/node-cve/triage-$(date +%Y-%m-%d)/report.md`:

   ```markdown
   # Node CVE Triage Report - YYYY-MM-DD

   ## Summary

   | Metric | Count |
   |--------|-------|
   | Total unique CVEs | N |
   | Reachable | N |
   | Present | N |
   | Unaffected | N |
   | Uncertain | N |

   ## Detailed Findings

   ### CVE-XXXX-XXXXX: <description>

   | Field | Value |
   |-------|-------|
   | Component | Node / CRI-O |
   | Repository | openshift/cri-o |
   | Overall classification | Reachable |
   | Overall confidence | High |
   | Assignee | <name or "Unassigned"> |
   | Affected versions | 4.12.z - 4.19 |
   | Tracker issues | OCPBUGS-XXXXX, OCPBUGS-XXXXX, ... |

   **Per-branch results:**

   | Branch | OCP Version | Classification | Confidence |
   |--------|-------------|----------------|------------|
   | release-1.28 | 4.15 | Reachable | High |
   | release-1.29 | 4.16 | Reachable | High |
   | release-1.30 | 4.17 | Unaffected | High |

   **Evidence (worst-case branch):** <source code analysis summary>
   **Recommended action:** <update dependency / apply patch / monitor / investigate>
   ```

2. **If `--notify-jira`**: For each CVE, post a comment on ALL its tracker issues. Each tracker receives the analysis result specific to its OCP version/branch.

   Use Atlassian wiki markup (not Markdown), matching the format in [report-findings](../skills/report-findings/SKILL.md) Step 2. The comment includes per-branch results across all analyzed versions so reviewers can see the full picture.

   Before posting, check for existing `node-cve:triage` comments on the issue. If a prior comment exists with the same classification, skip it. If the classification changed, edit the existing comment instead of adding a new one. See [report-findings](../skills/report-findings/SKILL.md) Step 2 for the deduplication logic.

   Rate limit: wait 1 second between Jira API calls to avoid throttling.

3. **If `--notify-slack`**: Post a summary to the webhook:

   Post using Slack Block Kit format (see [report-findings](../skills/report-findings/SKILL.md) Step 3 for the full payload structure).

---

### Phase 4: Summary Output

Print a final summary grouped by classification with bold section headings. This makes it easy to scan and jump to the section that matters:

```text
Node CVE Triage (N CVEs analyzed)
🔴 Reachable: N (M unassigned)
🟡 Present: N (M unassigned)
🟢 Unaffected: N (M unassigned)
⚠️ Uncertain: N (M unassigned)

(In Slack, each count and "M unassigned" links to a JQL filter
with the corresponding tracker keys. The unassigned filter uses
`AND (assignee is EMPTY OR assignee = "ocp-sustaining-blocked-trackers")`
to also count placeholder assignees. Each CVE ID in the thread reply
links to a JQL filter showing all its tracker issues.
See report-findings skill.)

**Reachable (action required):**
• CVE-XXXX-XXXXX - <short description>. (CRI-O, high confidence, N trackers[, M unassigned])

**Present (no action needed):**
• CVE-XXXX-XXXXX - <short description>. (CRI-O, high confidence, N trackers[, M unassigned])

**Unaffected:**
• CVE-XXXX-XXXXX - <short description>. (CRI-O, high confidence, N trackers[, M unassigned])

**Uncertain (needs manual investigation):**
• CVE-XXXX-XXXXX - <short description>. (CRI-O, low confidence, N trackers[, M unassigned])

Report: .work/node-cve/triage-YYYY-MM-DD/report.md
```

Omit empty sections (e.g., if there are no Uncertain CVEs, skip that heading). Each section heading must be bold or visually distinct from the CVE entries beneath it. The "Present" section groups both "Present but not exploitable" and "Present but not reachable" analysis results together, since both mean no urgent action is needed. The detailed classification is preserved in the per-CVE report and Jira comments. Only show the "(M unassigned)" count when M > 0.

The headline format depends on whether cached results were used. On first run (all CVEs are new): "Node CVE Triage (N CVEs analyzed)". On subsequent runs with cached results: "Node CVE Triage (N CVEs, M new)" where M is the number of CVEs without a prior `node-cve:triage` Jira comment. If classifications changed since the last run, also show "K updated": "Node CVE Triage (N CVEs, M new, K updated)".

## Arguments

- `--component <name>`: Filter to a specific OCPBUGS component. Must match a Node team component name exactly (e.g., "Node / CRI-O"). Optional.
- `--notify-jira`: Post analysis as a comment on each Jira tracker issue. Requires `JIRA_API_TOKEN`. Also enables cross-run caching via Jira comments.
- `--notify-slack`: Send a summary to Slack. Requires either `$SLACK_API_TOKEN` + `$SLACK_CHANNEL` (enables threading) or `$SLACK_WEBHOOK` (no threading).
- `--days N`: Only include CVEs created or updated in the last N days. Default: all open CVEs.

## Examples

1. **List all open Node CVEs with reachability analysis**:
   ```text
   /node-cve:triage
   ```

2. **Triage CRI-O CVEs only and post to Jira**:
   ```text
   /node-cve:triage --component "Node / CRI-O" --notify-jira
   ```

3. **Headless run with Jira and Slack notification**:
   ```bash
   claude --print "/node-cve:triage --notify-jira --notify-slack"
   ```

4. **Recent CVEs only (last 7 days)**:
   ```text
   /node-cve:triage --days 7 --notify-slack
   ```

## Notes

- The Jira query uses OCPBUGS component names from the [node-team shared components reference](../../node-team/skills/node/references/shared/components.md).
- Each CVE typically has multiple tracker issues (one per OCP version). The command deduplicates by CVE ID and analyzes ALL affected release branches. Features can be added, removed, or refactored across releases, so a CVE may be reachable on one version but not affected on another.
- Analysis targets downstream forks only (e.g., openshift/cri-o). If the downstream fork or branch does not exist, the CVE is classified as Uncertain. Dependency versions and Go toolchain versions differ across releases, so version-specific branches are used.
- Each version tracker receives the analysis result specific to its release branch. The overall classification for a CVE is the most severe result across all analyzed branches.
- Large repos like openshift/kubernetes may take longer to analyze. The command uses `--depth 1` clones for speed.
- Reachability analysis is performed by Claude reading the source code directly, not by external tools. This works across Go, Rust, and C codebases.
- Jira comments use Atlassian wiki markup (not Markdown).
- The command does not modify any code or create PRs. It only reads, analyzes, and reports.
- Reports and artifacts are saved to `.work/node-cve/` (gitignored).
