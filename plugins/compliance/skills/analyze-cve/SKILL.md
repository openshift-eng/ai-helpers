---
name: analyze-cve
description: |
  Full Go CVE analysis workflow. Given a CVE identifier -- supplied directly, or
  resolved from a Jira ticket or JQL batch -- resolves and clones the affected
  repository, gathers vulnerability intelligence, analyzes codebase impact with
  govulncheck and call-graph reachability, generates a risk report, and optionally
  applies a fix and opens a GitHub pull request.
  Use when the user gives a CVE ID (CVE-YYYY-NNNNN), a Jira ticket (--jira=), or a
  JQL query (--jql=) for Go CVE triage; wants call-graph proof that a vulnerable
  function is reachable; or wants an automated fix and PR for a Go dependency
  vulnerability.
  Triggers on: 'analyze CVE', 'CVE impact', 'is this repo affected by CVE',
  'Go vulnerability analysis', 'triage this Jira CVE ticket', 'fix this CVE and
  open a PR', or a bare CVE-YYYY-NNNNN identifier.
---

# analyze-cve

Performs comprehensive security vulnerability analysis for Go projects. Given a CVE identifier — supplied directly, or resolved from a Jira ticket — it resolves and clones the affected repository, gathers vulnerability intelligence, analyzes the codebase for impact, generates a risk report, optionally applies fixes, and optionally opens a GitHub pull request after a verified fix.

Explicit invocation uses the following argument syntax:

```
/compliance:analyze-cve <CVE-ID> [--repo=<url-or-component>] [--algo=vta|rta|cha|static] [--auto-approve=yes|no]
/compliance:analyze-cve --jira=<PROJ-NNN> [--repo=...] [--algo=...] [--auto-approve=yes|no]
/compliance:analyze-cve --jql="<JQL query>" [--repo=...] [--algo=...] [--auto-approve=yes|no]
```

Repository resolution works in four ways, in priority order: (1) an explicit `--repo=` (full URL or short image/component name), (2) in direct-CVE mode only, exactly one pre-cloned repository already present in this workspace's `repos/` directory when `--repo=` was not passed — in Jira/JQL mode that sole candidate is instead validated against the ticket's resolved image/branch before reuse, never assumed, (3) an image name extracted from a Jira ticket's summary/labels/custom fields when `--jira=`/`--jql=` was used, or (4) an interactive prompt for the repository URL or image name. See [Phase 0.7](references/implementation.md#phase-07-repository-resolution-and-cloning) in the implementation reference for the full resolution and cloning logic.

Designed for both interactive use and headless execution (e.g. `claude --print "/compliance:analyze-cve --jira=OCPBUGS-12345 --auto-approve=yes"`) for scheduled/periodic runs.

## Arguments

Exactly one of the following input modes is required:

- **`<CVE-ID>`** — Direct CVE identifier (format: `CVE-YYYY-NNNNN`, case-insensitive). Use when you already know the CVE.
- **`--jira=PROJ-NNN`** — Jira ticket key (e.g. `--jira=OCPBUGS-12345`). This skill fetches the ticket and extracts the CVE ID, affected image name, and enrichment context (CVSS, CWE, priority, workarounds) from it.
- **`--jql="..."`** — JQL query (e.g. `--jql="project = OCPBUGS AND labels = needs-cve-analysis"`). Fetches a batch of matching issues, filters out any already labeled `ai-cve-analyzed`, and processes exactly **one** of the remainder per run (see [Phase 0.3](references/implementation.md#phase-03-jql-resolution-only-when---jql-is-provided)). Re-running the same JQL periodically works through the queue over multiple invocations.

Optional flags:

- **`--repo=<url-or-component>`**: Repository to analyze. Accepts:
  - A full GitHub URL: `--repo=https://github.com/openshift/cert-manager-operator`
  - A short image/component name: `--repo=cert-manager-operator-rhel9` (resolved via the [image-repo-mapping](../image-repo-mapping/SKILL.md) skill)
  - If omitted, Phase 0.7 checks for exactly one pre-cloned repo in this workspace first, then resolves from the Jira ticket's image name (if `--jira`/`--jql` was used), then prompts the user.
- **`--algo`** (default: `vta`): Call graph construction algorithm.
  - `vta` — Most precise, fewest false positives (recommended)
  - `rta` — Good balance of precision and speed
  - `cha` — Fast, less precise
  - `static` — Fastest, least precise
- **`--auto-approve=yes|no`** (default: `no`): Run end-to-end without interactive approval prompts. See [Autonomous Mode](references/implementation.md#autonomous-mode---auto-approveyesno) in the implementation reference. Intended for scheduled/headless runs.

## Running This Skill

Read and follow [`references/implementation.md`](references/implementation.md) for the full phase-by-phase procedure once the arguments above are parsed — do not paraphrase or improvise it. It covers, in order:

1. **Autonomous Mode** — the full `AUTO_APPROVE` decision table (what's gated vs. what always hard-fails)
2. **Security — Credential Handling** — rules that apply to every command this skill runs
3. **Runtime Configuration** — `AI_HELPERS_WORKSPACE`, `FORK_ORG`
4. **Implementation** — Phase 0 (setup) through Phase 6 (PR creation), including the Repo Guard and each sub-skill's input/output contract
5. **Return Value** — the report format this skill produces

## Examples

1. **Basic CVE analysis against an explicit repo**:
   ```
   /compliance:analyze-cve CVE-2024-45338 --repo=https://github.com/openshift/cert-manager-operator
   ```

2. **With specific algorithm**:
   ```
   /compliance:analyze-cve CVE-2024-45338 --repo=https://github.com/openshift/cert-manager-operator --algo=rta
   ```

3. **Starting from a Jira ticket (repo/branch resolved automatically from the ticket's image name)**:
   ```
   /compliance:analyze-cve --jira=OCPBUGS-12345
   ```

4. **Unattended run from a JQL queue, applying fixes and opening a PR without prompts**:
   ```bash
   claude --print "/compliance:analyze-cve --jql=\"project = OCPBUGS AND labels = needs-cve-analysis ORDER BY created ASC\" --auto-approve=yes"
   ```

## Prerequisites

All tools below are **required**. This skill exits with an error if any are missing.

```bash
# Install all required Go tools
go install golang.org/x/vuln/cmd/govulncheck@latest
go install golang.org/x/tools/cmd/callgraph@latest
go install golang.org/x/tools/cmd/digraph@latest

# git is also required (Phase 0.7 repository cloning) — install via your OS package manager
```

**Optional**:
- `graphviz` for visual call graph generation (`brew install graphviz` or `sudo apt-get install graphviz`)
- `gh` (GitHub CLI, authenticated via `gh auth login`) for Phase 6 pull-request creation. Missing `gh` does **not** fail Phase 0 — analysis and local fixes still run; Phase 6 is skipped until it's available.
- An Atlassian MCP server (e.g. the `jira` plugin's bundled Rovo MCP) or `jira-cli` for `--jira=`/`--jql=` input modes and posting reports back to Jira

**Internet access** is recommended for CVE data fetching but not required if you can provide CVE details manually.

## Notes

- Focuses on Go-specific vulnerabilities.
- Resolves and clones the target repository automatically — via `--repo=`, Jira image-name mapping, or reusing a repo already cloned into `.work/compliance/analyze-cve/repos/` by a previous run — see [Phase 0.7](references/implementation.md#phase-07-repository-resolution-and-cloning). All analysis and fix-application phases run against that cloned `REPO_DIR`, not the directory this skill happened to be invoked from.
- Falls back to user-provided information if internet access fails.
- Does NOT make changes, commits, or pull requests without explicit approval — either interactive, or given once upfront via `--auto-approve=yes` (see [Autonomous Mode](references/implementation.md#autonomous-mode---auto-approveyesno)).
- Reports are saved locally (`.work/compliance/analyze-cve/`, gitignored) and not committed to git — see [Runtime Configuration](references/implementation.md#runtime-configuration) to relocate this base directory.
- Never process or disclose embargoed CVEs — if a Jira ticket's Embargo Status is `True`, this skill stops immediately and outputs nothing about the ticket.
