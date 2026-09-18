# Agentic Docs

AI-optimized OpenShift documentation with progressive disclosure, reference style (tables/checklists), and pointer-based navigation.

## Two-Tier Architecture

**Platform Docs** (`openshift/enhancements`)  
Development conventions (`dev-guide/`), coding standards (`CONVENTIONS.md`), enhancement guidelines (`guidelines/`).

**Component Docs** (`{component}/ai-docs/`)  
Architecture, development, testing guides, enhancement catalog. Flat structure — 3-4 files in ai-docs/, plus AGENTS.md and REVIEW.md at root.

## Skills

### `/generate-docs`
Generate, review, and fix component docs until independently verified clean,
no progress is possible, or the pass limit is reached.

```bash
/generate-docs [PATH] [--max-iterations N] [--review] [--cache-dir DIR] [--keep-cache]
```

The workflow is implemented as a portable skill without lifecycle hooks or
host-specific plugin path variables. It uses whichever native fresh-session
subagent capability the host exposes. A clean verdict still requires a fresh
isolated reviewer on every pass; a host without that capability reports
independent verification as unavailable instead of allowing the workflow to
verify its own fixes.

The first reviewer checks the full scope. Later reviewers check affected claims
and dependencies against the last independent baseline, reusing valid unchanged
evidence. They share immutable evidence, not the fixer's conversation.
Unresolved claims are reported; identical passes stop when they add no evidence.

#### Claim cache

Review state is stored outside the published documentation:

```text
.work/agentic-docs/run-.../
├── snapshots/       # document contents, claim inventory, source and policy hashes
├── observations/    # detailed per-claim evidence and review status
├── receipts/        # compact verification records
├── reports/         # self-contained pass reports
└── inputs.*/        # temporary inventory and evidence inputs
```

A snapshot records the repository revision, documentation, claims, occurrence
ranges, dependencies, source scope, and verification-policy hash. Review
observations classify each claim as `verified`, `failed`, or `unverified` and
include source excerpts. Only independent reviewer evidence is reusable;
fixer-only evidence cannot establish verification. Conflicting evidence makes a
claim unverified until an independent reviewer explicitly resolves it.

The next pass compares its snapshot with the independent baseline. Changed
claim text, source bytes, policy, document scope, or dependencies select claims
for re-verification. Unchanged claims reuse their observation or compact receipt.

After each self-contained review report is saved, compact the reviewed snapshot:

```bash
python3 claim_cache.py --cache "$CACHE_DIR" compact \
  --snapshot "$SNAPSHOT_ID"
```

Compaction writes aggregate receipts first, then deletes detailed observation
and carry files for verified claims. A receipt retains only the claim ID,
verification-context hash, evidence signature, and reviewer identity. Claim
definitions remain in the snapshot so coverage and change detection continue
to work. Failed, conflicting, and unresolved observations are retained for the
next pass. The command is idempotent.

See the [Claim cache reference](skills/review-docs/SKILL.md#claim-cache) for the
full formats, commands, and cleanup rules.

Successful runs delete their own cache after all passes finish; the report survives.
Use `--keep-cache` to retain evidence for audit or reuse. Failed, incomplete, or
interrupted runs and pre-existing caches are kept. Standalone `/review-docs`
uses the same rules.

### `/update-platform-docs`
Incrementally update platform docs with automatic gap detection.

```bash
cd /path/to/openshift/enhancements
/update-platform-docs
```

Scans ai-docs/, reports missing files, lets you fill gaps or add custom content. Auto-updates indexes/navigation and validates conventions. Use for incremental changes to existing platform documentation.

### `/component-docs`
Creates lean component docs in component repositories.

```bash
cd /path/to/component-repository
/component-docs
```

Creates AGENTS.md (executive briefing, 40-60 lines) + CLAUDE.md symlink + ai-docs/ with: ARCHITECTURE.md (internals, integration points, behavioral contracts, key design decisions), DEVELOPMENT.md, TESTING.md, ENHANCEMENTS.md (optional — enhancement/KEP/design doc catalog). Flat structure, no subdirectories. Excludes generic patterns (lives in platform docs).

### `/review-docs`
Review agentic documentation for hallucinations and verify claims against authoritative sources.

```bash
cd /path/to/component-repository
/review-docs
```

Verifies local claims from repository source and vendored dependencies, then
checks cross-repository claims against authoritative sources. When running
inside the Chai Bot environment, also use its configured documentation, Slack,
Jira, and CodeRAG knowledge where relevant.

## Development

Skills live under `skills/{generate-docs,update-platform-docs,component-docs,review-docs}/` with SKILL.md and any skill-local scripts, templates, or guides.

**License:** Apache 2.0
