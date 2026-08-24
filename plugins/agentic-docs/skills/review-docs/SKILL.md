---
name: review-docs
description: Review agentic documentation — verify claims locally against source code first, then use chai-bot for cross-repo and cross-functional verification
trigger: explicit
---

# Documentation Review & Verification

Reviews agentic documentation using **two-tier verification**: local codebase checks first, then cross-repo verification via **Chai Bot** for claims that can't be resolved locally. Chai Bot access may be provided directly by its hosted workspace or through an external MCP connection. Verify locally when possible, escalate to Chai Bot when necessary.

## Prerequisites

**Recommended** (for cross-repo verification): Chai Bot access through its hosted workspace or an external MCP connection. External access requires a configured bearer token and Red Hat VPN connection. Without either access path, cross-repo claims (enhancements, platform terminology, convention compliance, non-vendored API types) are flagged as "unverified" but local verification still runs fully.

External MCP setup instructions: See [plugin README](../../README.md#setup) for Chai Bot configuration steps.

## Chai Bot Access

Before any Chai Bot-assisted operation, select exactly one access path:

1. **Hosted** — If explicit host context indicates execution inside Chai Bot's hosted workspace, use the capabilities provided by the host directly. Do not configure or call a Chai Bot MCP server.
2. **External** — Otherwise, use the configured Chai Bot MCP connection through `mcp__chai-bot__ask_persona` when that tool is available.
3. **Unavailable** — If neither path is available, report which Chai Bot-assisted work could not be performed. Do not infer or fabricate results.

Resolve the access path once per run and reuse it. Do not infer hosted execution merely from a missing MCP tool, repository name, or working directory.

## When to Use

- After `/component-docs` or `/update-platform-docs`
- Before documentation PRs
- When docs may contain outdated/incorrect information

## Limitations

This skill verifies **factual accuracy** of what's documented. It does NOT detect:
- **Missing documentation** — incomplete coverage, absent sections
- **Low information density** — generic placeholders instead of repo-specific details
- **Misleading by omission** — technically correct but useless (e.g., "uses controllers" without specifying which framework)

For completeness and specificity, rely on the Implementation Pattern Discovery checklist in `/component-docs` and SME review.

## Claim Classification

Classify each claim by **what it asserts**. A single doc sentence may contain both a local fact and a cross-repo assertion — extract these as separate claims.

### Local: "Can this be verified from the current repo?"

Verifiable by reading the repo's own source code, **including `vendor/`**:
- File/directory paths exist
- Makefile targets exist
- Go version — check both the `go` directive (minimum version) and `toolchain` directive (actual toolchain) in `go.mod`
- Default branch name
- Import statements present (which frameworks a controller imports)
- Code patterns present (apply/update/patch calls, webhook registration code, feature gate checks)
- Go symbols referenced in examples exist
- YAML examples parse without errors
- Internal doc links resolve
- External links return HTTP 200 (with caveats — see Phase 3)
- Cross-file consistency (same concept not contradicted across doc files)
- Test directories and framework imports exist
- **API/CRD field names, types, defaults** — if `vendor/github.com/openshift/api` exists, verify struct definitions from vendored `types.go` files
- **Feature gate definitions** — if `vendor/github.com/openshift/library-go` or `vendor/github.com/openshift/api` exists, verify gate names and stages from vendored code
- **API group/version** — if vendored, check `register.go` for `GroupName` and `SchemeGroupVersion`

### Cross-repo: "Is this correct against external sources?"

Claims that cannot be resolved from local code or `vendor/`:
- API/CRD fields, feature gates, API group/version **when not vendored**, or when checking whether the vendored version is current
- Enhancement existence and status (in `openshift/enhancements`)
- Official terminology (must match `openshift-docs`)
- Cross-component interactions (how other operators behave)
- Platform convention compliance (whether a locally-verified pattern follows platform norms)
- Platform pattern references (whether linked platform docs are accurate)
- Historical context (design decisions in Slack/Jira, not code)

### Examples

| Documentation Says | Local Claim | Cross-Repo Claim (chai-bot) |
|-------------------|---------------------|--------------------------|
| "Uses admission webhooks" | Webhook registration code exists in repo | Webhooks follow platform conventions |
| "Applies resources via SSA" | SSA apply calls exist in controller code | Field manager names match platform norms |
| "Feature gate TechPreviewNoUpgrade controls X" | Code checks for this gate name | Gate exists in `openshift/api` with claimed stage (if not vendored) |

Always run the local check first. If a claim fails locally, report it — no need to query chai-bot.

## Execution Workflow

### Phase 1: Document Discovery
- [ ] Identify doc type (component or platform) and determine component repo from git remote or current working directory
- [ ] Scope discovery to the generated documentation structure — do not crawl the entire repo:
  - **Component docs**: `AGENTS.md`, `CLAUDE.md` (symlink), `REVIEW.md`, `.coderabbit.yaml`, `ai-docs/` tree (`ARCHITECTURE.md`, `DEVELOPMENT.md`, `TESTING.md`, `ENHANCEMENTS.md` if present)
  - **Platform docs** (when running inside openshift/enhancements): `dev-guide/`, `guidelines/`, `CONVENTIONS.md`
  - If `--path` is specified, scope to that path instead
- [ ] Use `find` within the scoped paths to catalog ALL markdown files
- [ ] Read EVERY file found — do not skip any

### Phase 2: Extract & Classify Claims

For each file, systematically extract every verifiable claim and track it internally as a **claims inventory** — the running list of assertions that drives all subsequent verification. For each claim, note: the source file, line number or range, what is being asserted, and whether it is local or cross-repo.

**Extraction rules**:
- A "claim" is any assertion that can be confirmed or refuted against source code, APIs, or external references. This includes prose statements, code snippet comments, numeric values, symbol names in instructions, enum constraints, and command/target names.
- Treat every line of documentation content as potentially containing one or more claims. If a line contains no verifiable assertion, skip it — but err on the side of extraction.
- A doc file with N lines of substantive content should typically yield claims proportional to its density. If a 40-line section yields only 3 claims, re-read it — something was missed.

**Cross-file consistency**: After extracting claims from all files, check for internal contradictions — the same concept described differently across files (e.g., AGENTS.md says "uses SSA" while ARCHITECTURE.md says "strategic merge"). Flag these before any verification queries.

The claims inventory is internal — it is not written to a file or shown to the user. But every claim in it must receive a verification status (verified, failed, or skipped) before the review can proceed, and the final report must include coverage totals derived from it.

### Phase 3: Local Codebase Verification

Verify all local claims from the Phase 2 claims inventory against the current repo's source code. Every local claim must receive a status: **verified**, **failed**, or **skipped** (with justification). Do not proceed to Phase 4 until all local claims have a status.

**Build & toolchain**:
- [ ] Read Makefile — extract all target names, compare against documented build/test commands
- [ ] Read `go.mod` — compare both `go` and `toolchain` directives to documented version
- [ ] Check default branch: discover the remote first, then inspect its HEAD:
  ```bash
  _remote=$(git remote | head -1)
  git symbolic-ref "refs/remotes/${_remote}/HEAD" # may need: git remote set-head "$_remote" --auto
  ```

**Directory & file structure**:
- [ ] Verify all claimed file and directory paths exist

**Framework & pattern claims**:
- [ ] For each controller claimed to use a specific framework: grep for the framework's import path in that controller's source files
- [ ] For each apply method claim: grep for the specific apply/update/patch patterns in the controller's code
- [ ] For webhook claims: grep for admission webhook registration (`admissionregistration`, `WebhookServer`, webhook manifests)
- [ ] For feature gate claims: grep for the gate name being checked in code

**Vendored API types & feature gates** (if `vendor/github.com/openshift/api` or `vendor/github.com/openshift/library-go` exists):
- [ ] For API/CRD field claims: find the relevant `types.go` in vendored `openshift/api`, compare struct field names, types, and defaults against documented claims
- [ ] For API group/version claims: check vendored `register.go` for `GroupName` and `SchemeGroupVersion`
- [ ] For feature gate claims: find gate definitions in vendored code, verify gate names and stages
- [ ] If claims reference fields or gates not present in the vendored version, flag as potential version mismatch — escalate to chai-bot in Phase 4 to check if the vendored version is outdated

**Code examples**:
- [ ] Validate YAML snippets parse without errors
- [ ] For Go examples: grep that referenced function names, type names, and constants exist in the repo

**Naming conventions**:
- [ ] For each claimed env var pattern: grep for matching env vars in the codebase
- [ ] For each claimed label/annotation pattern: grep for matching keys

**Test organization**:
- [ ] Verify claimed test directories exist
- [ ] Verify claimed test framework imports appear in test files

**REVIEW.md & .coderabbit.yaml** (if present):
- [ ] For each skip path glob (e.g., `**/clientset/**`): verify the base directory exists in the repo (`test -d`)
- [ ] For each platform rule citation (e.g., "dev-guide/api-conventions.md"): verify the cited file exists in openshift/enhancements
- [ ] For each path-specific rule: verify the glob matches actual directories and the described pattern exists in code
- [ ] Verify .coderabbit.yaml `path_filters` match the "Do not report" globs in REVIEW.md
- [ ] Verify .coderabbit.yaml `path_instructions` match the "Path-specific rules" sections in REVIEW.md
- [ ] Verify .coderabbit.yaml `filePatterns` includes "REVIEW.md" and "AGENTS.md" but NOT "CLAUDE.md"

**Links**:
- [ ] Check ALL internal file references resolve locally
- [ ] Verify external HTTPS links with curl (timeout 10s). Some sites return non-200 for automated requests — GitHub rate-limits, `docs.openshift.com` blocks curl. Treat 403/429 as "needs manual check" not automatic failure

**Cross-file consistency**:
- [ ] Compare claims about the same concept across doc files — flag contradictions

### Phase 3.5: Self-Audit Re-Read

Re-read each documentation file and compare it against the claims inventory from Phase 2. The goal is to catch claims that were missed during initial extraction — lines that contain verifiable assertions but were not included in the inventory.

For each missed claim found: add it to the inventory, verify it immediately (local or cross-repo classification), and update its status. This step addresses the pattern where category-level verification feels complete but individual claims within those categories were never extracted.

### Phase 4: Cross-Repo Verification via chai-bot

- [ ] Use the Chai Bot access path selected above
- [ ] If hosted or external access is available: read and follow `guides/CHAI-BOT-VERIFICATION.md` using that path — verify all cross-repo claims
- [ ] If Chai Bot is unavailable: inform user, mark all cross-repo claims as "unverified", skip to Phase 5

### Phase 5: Report Findings

**Severity guide**:
- **Critical** — factually wrong; would cause an agent to produce incorrect code (wrong fields, wrong methods, wrong framework)
- **Warning** — outdated, imprecise, or missing reference; won't cause broken code but degrades trust
- **Cross-file inconsistency** — same concept described differently across files
- **Unverified** — couldn't confirm or deny (chai-bot uncertain or unavailable for cross-repo claims)

Summarize findings directly to the user with:
1. **Coverage metrics**: Total claims extracted, total verified, total failed, total skipped — broken down by local vs cross-repo. This gives the user a concrete signal of review thoroughness.
2. **Verification source breakdown**: Local codebase vs chai-bot vs unverified.
3. **Issues by severity**: Listed per the severity guide above.
4. **Issues must include corrections**: Each issue must state what the doc says (incorrect claim with file and line), what the verified-correct value is, and the verification source when available (chai-bot response, local file path + line, or authoritative doc reference). If no citable source exists, state the basis for the correction (e.g., "well-known Kubernetes convention" or "standard Go pattern"). This ensures the fixer applies a single verified-correct value across all files rather than re-deriving the answer and arriving at a different interpretation.

### Phase 6: Offer Fixes

- [ ] Ask user: "Auto-fix verified issues, or manual review?"
- [ ] **Investigate full scope before editing**: For each issue, before making any edit:
  1. Grep the entire doc set for all occurrences of the incorrect claim
  2. Check whether the same file has summary, diagram, or overview sections that repeat the claim in simplified form
  3. Collect ALL locations, then fix them all in one pass — never fix a single file and move on
- [ ] If auto-fix, for each issue:
  - **Local-verified fixes**: use the codebase as source of truth to rewrite incorrect claims
  - **Chai-bot-verified fixes** (confirmed responses only): use chai-bot's response as source of truth for factual claims (wrong field names, non-existent enhancements, incorrect terminology). Never auto-fix based on unverified or hedged chai-bot responses — leave those for SME review
  - **Convention mismatches require manual review** — if local code intentionally diverges from platform convention, the docs should describe what the code does, not what convention says. Flag these for the user rather than auto-fixing
  - Update outdated conventions (branch names, versions, commands) to match verified facts
  - Fix broken internal links
  - **Do not** remove content that couldn't be verified — flag as unverified instead
  - **Stick to verified facts** — do not embellish or add interpretation beyond what was confirmed
- [ ] **Re-verify changed claims**: re-run local checks on modified content; re-query chai-bot on modified cross-repo claims to confirm fixes didn't introduce new errors
- [ ] **Post-fix consistency grep**: After all fixes, grep for each corrected term across all doc files. Confirm every file that mentions the concept uses the same corrected wording. Fix stragglers before proceeding.
- [ ] Re-run link validation on modified files

## Success Criteria

- All scoped documentation files reviewed (not sampled)
- Claims inventory tracked internally with every verifiable assertion extracted — coverage metrics reported
- Every local claim in the inventory has a verification status (verified, failed, or skipped with justification)
- Self-audit re-read completed — no unextracted claims remain
- Links valid, cross-file consistency confirmed
- All cross-repo claims verified via chai-bot or flagged as unverified

## Arguments

```bash
/review-docs [--path <docs-path>] [--auto-fix] [--local-only]
```

- `--path`: Path to documentation file(s) to review (defaults to current directory)
- `--auto-fix`: Automatically fix issues found (default: prompt user)
- `--local-only`: Skip chai-bot verification entirely, only run local checks

**Auto-discovery**: Infers component repo from git remote or current working directory

## See Also

- `/component-docs` - Create component documentation
- `/update-platform-docs` - Update platform documentation
- [openshift/api](https://github.com/openshift/api) - OpenShift API types
- [openshift-docs](https://github.com/openshift/openshift-docs) - Official documentation (terminology cross-check)
- [openshift/enhancements](https://github.com/openshift/enhancements) - OpenShift enhancements
