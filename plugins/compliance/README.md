# Compliance Plugin

Security compliance and vulnerability analysis tools for Go projects.

## Command

### `/compliance:analyze-cve <CVE-ID> | --jira=<PROJ-NNN> | --jql="..." [--repo=<url-or-component>] [--algo=vta|rta|cha|static] [--auto-approve=yes|no]`

Resolves and clones the affected Go repository, then analyzes it to determine CVE impact with multi-level confidence assessment. Can be driven directly by a CVE ID, or resolve the CVE (and the affected repository/branch) from a Jira ticket — single ticket or a JQL-selected queue — and, with approval, apply a fix and open a GitHub pull request.

**Examples:**
```text
/compliance:analyze-cve CVE-2024-24783 --repo=https://github.com/golang/net
/compliance:analyze-cve --jira=OCPBUGS-12345
/compliance:analyze-cve --jql="project = OCPBUGS AND labels = needs-cve-analysis ORDER BY created ASC"
```

**Unattended run** (e.g. scheduled/periodic), applying fixes and opening a PR without prompts:
```bash
claude --print "/compliance:analyze-cve --jql=\"project = OCPBUGS AND labels = needs-cve-analysis\" --auto-approve=yes"
```

**Features:**
- Resolves and clones the affected repository — via `--repo=`, a Jira ticket's image name (`image-repo-mapping` skill), or a repo already cloned by a previous run — with correct branch mapping (including release repos with git submodules)
- Fetches CVE details from NVD, MITRE, and the Go Vulnerability Database
- Optionally resolves the CVE and enrichment context (CVSS, CWE, priority, workarounds) from a Jira ticket, directly or via a JQL-selected queue
- Multi-level verification (dependency check → static analysis → govulncheck → **call graph reachability**)
- Generates reports with confidence levels (HIGH/MEDIUM/LOW/NEEDS_REVIEW)
- Provides exact remediation commands
- Optionally applies fixes with approval, then opens a GitHub PR and posts the report/PR link back to the source Jira ticket
- `--auto-approve=yes` runs the full pipeline (analysis → fix → PR) without interactive prompts, for headless/scheduled use — hard-fail conditions (embargoed CVEs, ambiguous CVE matches, missing file allowlists) are never bypassed by this flag

**Output:**
- `.work/compliance/analyze-cve/repos/{repo-name}` - Cloned repository (`REPO_DIR`), reused across runs against the same repo
- `.work/compliance/analyze-cve/{CVE-ID}/report.md` - Full analysis with confidence assessment (gitignored, not committed)
- `.work/compliance/analyze-cve/{CVE-ID}/callgraph.svg` - Visual execution path (if call graph analysis performed)
- `.work/compliance/analyze-cve/{CVE-ID}/govulncheck-output.txt` - Scanner results
- `.work/compliance/analyze-cve/{CVE-ID}/phase5-files.txt` - Allowlist of files changed by an applied fix (used to scope the PR commit)
- A GitHub pull request (if a fix was applied, verified, and the user approved PR creation)
- A comment (+ `ai-cve-analyzed` label) on the source Jira ticket, if `--jira=`/`--jql=` was used

## Verification Levels

The command uses multiple methods with increasing confidence:

1. **Dependency check** → Confirms package presence
2. **Static analysis** → Finds function usage  
3. **govulncheck** → Official Go vulnerability scanner
4. **Call graph reachability** → Proves execution path (HIGHEST confidence)
5. **Context analysis** → Checks security controls

Reports include confidence level (HIGH/MEDIUM/LOW/NEEDS_REVIEW) based on verification methods used.

## Input Modes

- **Direct CVE**: `<CVE-ID>` — analyze a known CVE, resolving the repo via `--repo=` (see [Repository Resolution](#repository-resolution) below).
- **Jira ticket**: `--jira=PROJ-NNN` — fetch the ticket, extract the CVE ID, affected image name, and internal context (CVSS, CWE, priority, workarounds, embargo status), then resolve the repo/branch and analyze.
- **JQL queue**: `--jql="..."` — fetch a batch of matching tickets, skip any already labeled `ai-cve-analyzed`, and process exactly one per run. Re-running the same JQL periodically works through the queue over time.

Jira/PR features require an Atlassian MCP server (or `jira-cli`) and, for PR creation, an authenticated `gh` CLI. These are optional — direct CVE analysis (with `--repo=`) works without them.

## Repository Resolution

The command always analyzes a **cloned repository** (`REPO_DIR`, under `.work/compliance/analyze-cve/repos/`) — it does not analyze whatever directory it happens to be invoked from. Resolution order (see [Phase 0.7](commands/analyze-cve.md#phase-07-repository-resolution-and-cloning) for full detail):

1. A repo already cloned into `.work/compliance/analyze-cve/repos/` by a previous run (used automatically if there's exactly one, and `--repo=` wasn't passed)
2. `--repo=<url>` — a full GitHub URL, used directly
3. `--repo=<short-name>` or a Jira ticket's extracted image name — resolved to a repo URL + branch via the [image-repo-mapping](skills/image-repo-mapping/SKILL.md) skill's static component table (including release repos that pin components as git submodules)
4. Otherwise, the command prompts for a repo URL or image name (or hard-fails under `--auto-approve=yes`, since guessing a repo is a correctness risk, not a convenience trade-off)

The [image-repo-mapping](skills/image-repo-mapping/SKILL.md) table is scoped to the components this command has been validated against — extend it as new components come up.

## Runtime Configuration

- **`AI_HELPERS_WORKSPACE`** (optional, default: cwd): relocates the base directory for cloned repos, reports, and Phase 5/6 artifacts (all under `${AI_HELPERS_WORKSPACE}/.work/compliance/analyze-cve/`). Set this when running somewhere the invocation directory isn't a stable, writable location — e.g. `AI_HELPERS_WORKSPACE=/workspace` on a Remote Workspace pod.
- **`FORK_ORG`** (optional): if set, Phase 6 pushes the fix branch to a fork under this org and opens a cross-repo PR instead of pushing directly to the resolved repo's `origin`. Use this for a bot identity that isn't a direct collaborator on every repo `image-repo-mapping` might resolve to (e.g. an unattended CI/RWS runner). See [create-fix-pr's Fork Mode](skills/create-fix-pr/SKILL.md#fork-mode-fork_org-set).

## Prerequisites

**Required for all modes.** The command exits with an error if any are missing.

```bash
# Install all required Go tools
go install golang.org/x/vuln/cmd/govulncheck@latest
go install golang.org/x/tools/cmd/callgraph@latest
go install golang.org/x/tools/cmd/digraph@latest

# Optional: For visual call graphs
brew install graphviz  # macOS
```

**Required:**
- Go toolchain (`go version`)
- `git` - repository cloning (Phase 0.7)
- `govulncheck` - vulnerability scanner
- `callgraph` - call graph analysis
- `digraph` - graph traversal

**Optional (feature-gated, warn-only if missing):**
- `gh` (authenticated via `gh auth login`) - required only to create/update a GitHub PR (Phase 6)
- An Atlassian MCP server or `jira-cli` - required only for `--jira=`/`--jql=` input modes and posting reports back to Jira

The command validates required tools in Phase 0 and provides installation instructions if any are missing.

## Fallback Mode

If internet access fails, the command prompts for manual CVE information (description, affected packages, versions, fixes). Analysis proceeds with user-provided data, clearly marked in the report. In `--auto-approve=yes` mode there is no one to prompt, so this case exits with an error instead of fabricating CVE details.

## Autonomous Mode

`--auto-approve=yes` answers every yes/no approval prompt in the pipeline (proceed past `NEEDS_REVIEW`, apply fixes, create a PR, post to Jira with reduced visibility if restricted posting isn't available) so the command can run end-to-end unattended. It never bypasses hard-fail safety checks: embargoed Jira tickets, ambiguous CVE matches within a ticket, or a fix-file allowlist that can't be determined all stop the run regardless of this flag. See the [`analyze-cve` command's Autonomous Mode section](commands/analyze-cve.md#autonomous-mode---auto-approveyesno) for the full decision table.

## Report Includes

- **Executive Summary**: Risk level (HIGH/MEDIUM/LOW/NEEDS REVIEW) with confidence
- **Jira Context** (if applicable): ticket link, priority, status, assignee, target versions, internal notes
- **Analysis Methodology**: Which verification methods were used
- **Impact Assessment**: Evidence from codebase, call chains (if found)
- **Remediation Steps**: Exact commands and fixes
- **Visual Artifacts**: Call graph SVG, scanner outputs

## Examples

### Basic usage
```text
/compliance:analyze-cve CVE-2024-24783 --repo=https://github.com/golang/go
```
Clones the repo, analyzes it for the crypto/x509 vulnerability, provides upgrade command if affected.

### High-confidence analysis
```text
/compliance:analyze-cve CVE-2024-45338 --repo=https://github.com/golang/net
```
**Result:**
- Finds `golang.org/x/net/html v0.21.0` (vulnerable)
- Proves execution path: `main → HTTPHandler → ParseHTML → html.Parse`
- **Risk Level**: HIGH
- Generates `callgraph.svg` showing call chain
- Recommends: `go get golang.org/x/net@v0.23.0`

### Jira-driven analysis with automatic fix and PR
```text
/compliance:analyze-cve --jira=OCPBUGS-12345 --auto-approve=yes
```
**Result:**
- Extracts `CVE-2024-45338` and internal context from the ticket
- Runs the same verification pipeline as above
- Applies the dependency bump, verifies build/tests pass
- Opens a GitHub PR titled `CVE-2024-45338: bump golang.org/x/net to v0.23.0 [OCPBUGS-12345]`
- Posts the report and PR link back to `OCPBUGS-12345`, labels it `ai-cve-analyzed`
