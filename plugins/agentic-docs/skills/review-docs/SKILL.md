---
name: review-docs
description: Review agentic documentation by verifying local claims against source code and cross-repository claims against available authoritative resources. Use when checking generated or existing agent docs for factual accuracy, stale claims, broken references, or pre-PR readiness.
---

# Documentation Review & Verification

Reviews agentic documentation using **two-tier verification**: local codebase
checks first, then authoritative cross-repository sources for claims that cannot
be resolved locally.

## Prerequisites

Verify cross-repository facts against authoritative sources, such as upstream
GitHub sources or Chai Bot's configured CodeRAG. If running inside the Chai Bot
environment, also use its configured documentation, Slack, and Jira knowledge
for relevant historical or cross-functional context. Claims that cannot be
checked remain `unverified`; local verification still runs fully.

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

## Review mode and immutable evidence

Follow [Claim cache](#claim-cache) below for snapshots, evidence,
review planning, and cleanup. Resolve `scripts/claim_cache.py` from this skill.
Keep the cache outside the doc scope; delegated reviewers never delete it.
After each report, compact verified observations into aggregate receipts while
retaining failed and unresolved evidence.

Without a valid independent baseline, review the full scope. Otherwise, check
affected claims and their dependencies, reusing valid independent evidence.
Use a fresh context with immutable evidence and the diff, not the fixer's chat.
Check reviewer independence and inventory coverage; cache entries prove neither.

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

| Documentation Says | Local Claim | Cross-Repo Claim |
|-------------------|---------------------|--------------------------|
| "Uses admission webhooks" | Webhook registration code exists in repo | Webhooks follow platform conventions |
| "Applies resources via SSA" | SSA apply calls exist in controller code | Field manager names match platform norms |
| "Feature gate TechPreviewNoUpgrade controls X" | Code checks for this gate name | Gate exists in `openshift/api` with claimed stage (if not vendored) |

Always run the local check first. If a claim fails locally, report it without
searching for external evidence to override the repository.

## Execution Workflow

### Phase 1: Document Discovery
- [ ] Identify doc type (component or platform) and determine component repo from git remote or current working directory
- [ ] Scope discovery to the generated documentation structure — do not crawl the entire repo:
  - **Component docs**: `AGENTS.md`, `CLAUDE.md` (symlink), `REVIEW.md`, `.coderabbit.yaml`, `ai-docs/` tree (`ARCHITECTURE.md`, `DEVELOPMENT.md`, `TESTING.md`, `ENHANCEMENTS.md` if present)
  - **Platform docs** (when running inside openshift/enhancements): `dev-guide/`, `guidelines/`, `CONVENTIONS.md`
  - If `--path` is specified, scope to that path instead
- [ ] Use `find` within the scoped paths to catalog ALL markdown files
- [ ] First pass: read every scoped file. Later passes: compare the same scope
  with the baseline and read changed sections, needed context, and affected
  occurrences. Include new files and account for deletions; skip unrelated rereads.

### Phase 2: Extract & Classify Claims

Save a **claims inventory** using the format below. Extract every verifiable claim
on the full pass; re-extract changed sections on later passes, keeping stable IDs.
Record each assertion, local/cross-repo kind, occurrence ranges, source scope,
and claim dependencies. Map qualifiers, headings, table headers, summaries, and diagrams so
changes to them invalidate the affected claims.

**Extraction rules**:
- A "claim" is any assertion that can be confirmed or refuted against source code, APIs, or external references. This includes prose statements, code snippet comments, numeric values, symbol names in instructions, enum constraints, and command/target names.
- Treat every line of documentation content as potentially containing one or more claims. If a line contains no verifiable assertion, skip it — but err on the side of extraction.
- A doc file with N lines of substantive content should typically yield claims proportional to its density. If a 40-line section yields only 3 claims, re-read it — something was missed.

**Cross-file consistency**: Compare the same concepts across the inventory.
On later passes, check all occurrences and dependent claims for each changed
concept, including summaries and diagrams. Flag contradictions before queries.

Save an immutable snapshot of the inventory and document hashes. Mark coverage
complete only after checking every scoped file and changed section. A diff cannot
prove new text has no claims. Fully extract uncovered scope and report gaps as
unresolved. Never drop claims from unchanged text.

Give each claim a status and evidence: `verified`, `failed`, or `unverified`.
Skipped or unavailable checks are `unverified`; report why. Count from the current
inventory, separating new checks from reused independent evidence.

### Phase 3: Local Codebase Verification

On the full pass, check every local claim against source or valid cached excerpts.
Later, check claims selected by the plan, including missing or invalid evidence.
A fixer's cached verdict never exempts an affected claim from review.

Give every current local claim a status, including reused results. Apply the
checks below only to selected claims; reuse unchanged independent evidence.

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
- [ ] If claims reference fields or gates not present in the vendored version, flag as a potential version mismatch and check authoritative cross-repository sources in Phase 4

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

### Phase 3.5: Audit inventory coverage

First pass: compare all scoped content with the inventory for missed claims.
Later passes: audit changed sections, new/deleted files, occurrence mappings,
and affected dependencies. Reuse the valid unchanged baseline.

Add missed claims, correct mappings, and recompute the plan. If mappings are
unreliable, fully review the affected scope and report the limitation.

### Phase 4: Cross-Repository Verification

- [ ] Verify selected claims against authoritative sources, such as upstream GitHub sources or Chai Bot's configured CodeRAG
- [ ] Use configured Slack and Jira knowledge only for relevant historical or cross-functional context
- [ ] Reuse valid unchanged independent evidence; mark outstanding claims `unverified` with the reason and continue to Phase 5

### Phase 5: Report Findings

**Severity guide**:
- **Critical** — factually wrong; would cause an agent to produce incorrect code (wrong fields, wrong methods, wrong framework)
- **Warning** — outdated, imprecise, or missing reference; won't cause broken code but degrades trust
- **Cross-file inconsistency** — same concept described differently across files
- **Unverified** — couldn't confirm or deny from the available authoritative resources

Include in the report:
1. **Coverage**: Baseline/current snapshot IDs, pass number, and current, newly verified, reused, failed, and unresolved counts, split by local/cross-repo. List unresolved IDs/reasons and removed claims separately. State whether extraction covers the full scope; an empty plan cannot excuse gaps.
2. **Verification source breakdown**: Local codebase vs cross-repository or hosted resources vs unverified.
3. **Issues by severity**: Listed per the severity guide above.
4. **Issues must include corrections**: Each issue must state what the doc says (incorrect claim with file and line), what the verified-correct value is, and the verification source when available (local file path + line, authoritative document, or hosted knowledge reference). If no citable source exists, state the basis for the correction (e.g., "well-known Kubernetes convention" or "standard Go pattern"). This ensures the fixer applies a single verified-correct value across all files rather than re-deriving the answer and arriving at a different interpretation.

Save the report at the assigned `CACHE_DIR/reports/pass-NNN.md` path, creating
`reports/` if missing. Include snapshot and observation IDs. For a standalone
review, use the next unused pass number, starting at `001`. Return
the path and a summary to the main agent, or to the user for a standalone review.
Never overwrite a report or use a fixer snapshot as the independent baseline.
If only the same unresolved items remain with no new inputs, evidence, or
actionable fixes, report incomplete and stop.
New pass numbers, cache writes, or report wording alone are not progress.

After the report is complete and self-contained, compact the reviewed snapshot:

```bash
python3 "$CACHE_HELPER" --cache "$CACHE_DIR" compact --snapshot "$SNAPSHOT_ID"
```

Report its verified, retained, and removed-record counts. Compaction removes
detailed observations only for verified claims; failed and unresolved claims
remain available for the next pass.

### Phase 6: Offer Fixes

- [ ] Ask user: "Auto-fix verified issues, or manual review?"
- [ ] **Investigate full scope before editing**: For each issue, before making any edit:
  1. Grep the entire doc set for all occurrences of the incorrect claim
  2. Check whether the same file has summary, diagram, or overview sections that repeat the claim in simplified form
  3. Collect ALL locations, then fix them all in one pass — never fix a single file and move on
- [ ] If auto-fix, for each issue:
  - **Local-verified fixes**: use the codebase as source of truth to rewrite incorrect claims
  - **Cross-repository-verified fixes**: use confirmed, cited authoritative evidence for factual claims such as enhancement existence or terminology. Never auto-fix from hedged or uncited results — leave those for SME review
  - **Convention mismatches require manual review** — if local code intentionally diverges from platform convention, the docs should describe what the code does, not what convention says. Flag these for the user rather than auto-fixing
  - Update outdated conventions (branch names, versions, commands) to match verified facts
  - Fix broken internal links
  - **Do not** remove content that couldn't be verified — flag as unverified instead
  - **Stick to verified facts** — do not embellish or add interpretation beyond what was confirmed
- [ ] **Re-verify affected claims**: snapshot fixes and plan against the last independent baseline. Check affected claims and dependencies; reuse unchanged evidence. Append results. `generate-docs` still requires a fresh independent reviewer.
- [ ] **Post-fix consistency grep**: After all fixes, grep for each corrected term across all doc files. Confirm every file that mentions the concept uses the same corrected wording. Fix stragglers before proceeding.
- [ ] Re-run link validation on modified files

### Finalize cache lifetime

After reporting and any accepted fixes, follow the cleanup rules below.
A standalone run deletes its own cache only when no failed, unresolved, or pending
verification remains, unless `--keep-cache`. Delegated reviewers leave cleanup
to the main agent. Report cleanup status and any retained path and reason.

## Success Criteria

- The immutable inventory covers the baseline, changed/new sections, and removals.
- Every current claim is accounted for, separating new checks from reused evidence.
- Claims affected by edits, source/prompt changes, or dependencies are checked;
  missing, invalid, or conflicting evidence remains unresolved.
- Relevant links and cross-file consistency are checked; gaps and skips are reported.
- Cross-repo claims are verified or marked unverified. Unresolved claims prevent
  `generate-docs` from reporting verified clean.

## Arguments

```bash
/review-docs [--path <docs-path>] [--auto-fix] [--local-only]
             [--cache-dir <directory>] [--baseline <snapshot-id>] [--keep-cache]
```

- `--path`: Path to documentation file(s) to review (defaults to current directory)
- `--auto-fix`: Automatically fix issues found (default: prompt user)
- `--local-only`: Skip cross-repository verification and run only local checks
- `--cache-dir`: Shared review cache; default to a new run directory under the
  target repository's `.work/agentic-docs/`, outside the doc scope
- `--baseline`: Last independent snapshot; omit for full review. Reuse requires
  a valid, complete baseline.
- `--keep-cache`: Keep the cache after a successful run instead of deleting it.

**Auto-discovery**: Infers component repo from git remote or current working directory

## Claim cache

`scripts/claim_cache.py` saves immutable claims and evidence, checks hashes, and
selects claims for review. It requires Python 3.9+ and Git. Append results; never
overwrite them. After each review, `compact` replaces detailed verified
observations with aggregate receipts and retains failed or unresolved evidence.

### 1. Set paths

The main agent supplies these values; standalone reviews resolve them directly.
Use absolute paths. Snapshot and observation IDs are hashes.

| Variable | Value |
|----------|-------|
| `REVIEW_SKILL_DIR` | Directory containing this `SKILL.md` |
| `REPO_PATH` | Target repo from `generate-docs` or Phase 1 |
| `CACHE_DIR` | Shared cache or `--cache-dir`; otherwise a new directory under `REPO_PATH/.work/agentic-docs/` |
| `PROMPT_VERSION` | Policy hash defined under Reuse rules; shared across passes |

Before creating the default cache, ensure `/.work/` is present in the target
checkout's local Git exclude (resolve it with
`git -C "$REPO_PATH" rev-parse --git-path info/exclude`). Verify the rule with
`git check-ignore`. This local exclude is not tracked and must remain after cache
cleanup. If it cannot be installed and verified, place the cache outside the
worktree instead of creating `.work`.

Create `CACHE_DIR` first, or reuse the main agent's directory. In Bash:

```bash
set -euo pipefail
CACHE_HELPER="$REVIEW_SKILL_DIR/scripts/claim_cache.py"
WORK_DIR=$(mktemp -d "$CACHE_DIR/inputs.XXXXXX")
INVENTORY_FILE="$WORK_DIR/inventory.json"
EVIDENCE_FILE="$WORK_DIR/evidence.json"
```

### 2. Write inputs

Save this structure to `INVENTORY_FILE`, using actual claims and sources:

```json
{
  "documents": ["ai-docs/DEVELOPMENT.md"],
  "coverage_complete": true,
  "claims": [{
    "id": "test-command", "assertion": "The test target runs Go tests.", "kind": "local",
    "occurrences": [{"path": "ai-docs/DEVELOPMENT.md", "start": 8, "end": 12}],
    "depends_on": [],
    "source_scope": [{"repository": "component", "revision": "<commit>",
      "local_root": "<absolute repo path>", "path": "Makefile"}]
  }]
}
```

Use stable IDs, repo-relative paths, inclusive one-based line ranges, and kind
`local` or `cross-repo`. `depends_on` lists claim IDs. Reviewers must check coverage
and dependencies themselves; broaden the review when unsure.

Save one claim's evidence to `EVIDENCE_FILE`:

```json
{"reviewer": "pass-1", "role": "reviewer",
 "evidence": [{"source": "Makefile:8 at <commit>", "excerpt": "test:\n\tgo test ./..."}]}
```

Use role `fixer` or `reviewer`; the role alone does not prove independence.
Include exact excerpts, qualifications, and reasons for failures or uncertainty.
Exclude chat, fixer reasoning, credentials, and unrelated sources.

These input files may change; saved cache records stay immutable.

### 3. Review and record results

Save a snapshot and plan the first full review:

```bash
SNAPSHOT_ID=$(python3 "$CACHE_HELPER" --cache "$CACHE_DIR" snapshot \
  --repo "$REPO_PATH" --inventory "$INVENTORY_FILE" --prompt-version "$PROMPT_VERSION" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["snapshot"])')
python3 "$CACHE_HELPER" --cache "$CACHE_DIR" plan --current "$SNAPSHOT_ID"
```

For each selected claim, set `CLAIM_ID`, update `EVIDENCE_FILE`, and check sources.
Set `STATUS` to `verified` (supported), `failed` (contradicted), or `unverified`
(unknown, skipped, or timed out). Save the result ID for the report:

```bash
OBSERVATION_ID=$(python3 "$CACHE_HELPER" --cache "$CACHE_DIR" put \
  --snapshot "$SNAPSHOT_ID" --claim "$CLAIM_ID" --status "$STATUS" --evidence "$EVIDENCE_FILE" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["observation"])')
python3 "$CACHE_HELPER" --cache "$CACHE_DIR" get --snapshot "$SNAPSHOT_ID" --claim "$CLAIM_ID"
```

### 4. Compact completed verification

After the report contains the evidence needed by the main agent or user, compact
the reviewed snapshot:

```bash
python3 "$CACHE_HELPER" --cache "$CACHE_DIR" compact --snapshot "$SNAPSHOT_ID"
```

The command preserves small context/signature/reviewer receipts so unchanged
verified claims remain reusable. It deletes detailed observation and carry
records for those claims. It is idempotent and does not remove failed or
unresolved observations.

### 5. Review fixes

The main agent passes the completed independent review's `SNAPSHOT_ID` as the
next reviewer's `BASELINE_ID`. After fixes, update the inventory and snapshot:

```bash
CURRENT_ID=$(python3 "$CACHE_HELPER" --cache "$CACHE_DIR" snapshot \
  --repo "$REPO_PATH" --inventory "$INVENTORY_FILE" --prompt-version "$PROMPT_VERSION" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["snapshot"])')
python3 "$CACHE_HELPER" --cache "$CACHE_DIR" plan --previous "$BASELINE_ID" --current "$CURRENT_ID"
SNAPSHOT_ID="$CURRENT_ID"
```

Repeat `put`/`get` for selected claims. Never use a fixer snapshot as the baseline.
Omit `--previous` for full review. Edits, context changes, and dependencies need
checks; unrelated line shifts do not. Extract new claims from changed sections.

### Reuse rules

Keys include repo identity/commit, document/claim hashes, source scope, and policy
hash. Snapshots capture uncommitted edits too. Pin sources to immutable commits
or snapshots; branches, mutable URLs, or unpinned evidence cannot support reuse.

Keep `local_root` to refresh source hashes. Update the revision when HEAD changes;
stale pins fail. Unchanged local bytes and scope allow reuse across commits.
Changed remote revisions need review.

Compute `PROMPT_VERSION` once per run as a SHA-256 hash of this skill,
`generate-docs`, and task instructions including overrides. Exclude claim text
and line numbers. Policy changes invalidate reuse.

If only document hashes or commits change, a carry receipt links the new snapshot
to valid independent evidence. Count it as reuse. Fixer verdicts never exempt
affected claims; reuse cannot turn failed or unverified results into verified ones.

Missing, corrupt, or conflicting records need review or an unresolved status.
Only a fresh reviewer can resolve conflicts with `supersedes`, listing the exact
observation or carry IDs from `get` for the same context. Records are immutable
while present; post-review compaction is the only supported removal and applies
only to verified observations after writing their aggregate receipts. Newer
results do not win automatically; author differences alone are not conflicts.

### Cleanup

Record the cache's canonical path and owner. A run owns only directories it
creates; preserve pre-existing directories, including `--cache-dir`.

After success, the owner deletes only its run directory unless `--keep-cache`.
Wait for reviewers and prepare a self-contained final summary with coverage,
findings, and sources; pass reports disappear with the cache. Keep failed,
incomplete, or interrupted runs. Delegated reviewers and helper calls never clean up.
Never delete parent directories, sibling runs, or sources. Verify removal and
report any retained path and reason or error.

Compaction runs after every completed review, including incomplete runs, so
retained caches contain detailed records only for failed or unresolved claims.

## See Also

- `/component-docs` - Create component documentation
- `/update-platform-docs` - Update platform documentation
- [openshift/api](https://github.com/openshift/api) - OpenShift API types
- [openshift-docs](https://github.com/openshift/openshift-docs) - Official documentation (terminology cross-check)
- [openshift/enhancements](https://github.com/openshift/enhancements) - OpenShift enhancements
