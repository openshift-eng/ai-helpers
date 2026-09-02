---
name: component-docs
description: Create lean component documentation for OpenShift repositories
---

# Component Documentation Creator

Creates lean component agentic documentation for OpenShift component repositories.

**Philosophy**: Component docs contain ONLY component-specific knowledge. Generic platform patterns live in the openshift/enhancements repo (`dev-guide/`, `guidelines/`, `CONVENTIONS.md`). Code is the source of truth — read it, verify claims against it, but link to existing repo docs that explain the "why".

## Two-Tier Architecture

### Platform: openshift/enhancements
**Contains**: Development conventions (`dev-guide/`), coding standards (`CONVENTIONS.md`), enhancement guidelines (`guidelines/`), cross-repo architectural context

### Component: Component Repos (LEAN)
**Contains**: Component-specific architecture, behavioral contracts, development guides, test patterns

**Decision Rule**: "Would another repo need to duplicate this?"
- YES → Platform (platform)
- NO → Component (component)

## What Gets Created

```text
component-repo/
├── AGENTS.md                      # Executive briefing (40-60 lines)
├── CLAUDE.md → AGENTS.md          # Symlink (Claude Code auto-loads)
├── REVIEW.md                      # Review instructions (Claude Code Review + CodeRabbit)
├── .coderabbit.yaml               # CodeRabbit config (points at REVIEW.md)
└── ai-docs/
    ├── ARCHITECTURE.md            # Internals, integrations, behavioral contracts, design refs
    ├── DEVELOPMENT.md             # Build, common tasks, mistakes
    ├── TESTING.md                 # Test suites and patterns
    └── ENHANCEMENTS.md            # Optional — enhancement/KEP/design doc catalog
```

## What NOT to Include (lives in Platform)

❌ Generic framework patterns (controller-runtime, status conditions, common libraries)
❌ Testing practices (test pyramid, E2E framework)
❌ Security practices (STRIDE, RBAC guidelines)
❌ Reliability practices (SLO framework)
❌ Kubernetes fundamentals (Pod, Node, Service)
❌ Cross-repo ADRs (etcd, CVO orchestration, immutable nodes)

## Chai Bot Access

Before any Chai Bot-assisted operation, select exactly one access path:

1. **Hosted** — If explicit host context identifies execution inside Chai Bot's hosted workspace and provides a callable knowledge/search capability, use that capability. Do not configure or call a second Chai Bot MCP server.
2. **External** — Otherwise, use an available Chai Bot `ask_persona` MCP capability. Hosts may normalize the server name differently; select it by capability, not by an exact tool identifier.
3. **Unavailable** — If neither path is available, report which Chai Bot-assisted work could not be performed. Do not infer or fabricate results.

Resolve the access path once per run and reuse it. Explicit hosted context without a callable knowledge capability is unavailable, not permission to invent results. Do not infer hosted execution merely from a missing MCP tool, repository name, or working directory. Never modify MCP configuration from a managed hosted workspace.

## Execution Workflow

### Phase 1: Setup
- [ ] **Read existing CLAUDE.md / AGENTS.md before overwriting**: If the repo already has either file, read it first and extract important points (build instructions, critical warnings, repo conventions, key patterns, retrieval priorities, documentation maps, and useful direct links) to incorporate into the generated docs. Existing content is prior work — preserve it, don't overwrite blindly.
- [ ] **Back up prior agent docs before writing**: Save any existing `CLAUDE.md` / `AGENTS.md` content under `ai-docs/_sources/`. Use them as temporary source material for review and recovery during generation.
- [ ] **Discover existing repo docs**: Scan `docs/`, `docs/enhancements/`, `design/`, `CONTRIBUTING.md`, and any files with "design", "proposal", "enhancement" in the name. These will be linked from ENHANCEMENTS.md and ARCHITECTURE.md as appropriate. Also scan documentation files at the repository root and look elsewhere throughout the repository for relevant documentation, regardless of filename or location.
- [ ] Resolve this skill directory from the location of the loaded `SKILL.md`. Resolve all `scripts/`, `templates/`, and `guides/` paths relative to it. Do not search a plugin cache or assume the repository is the current directory.
- [ ] Preflight required resources: `scripts/create-structure.sh`, `scripts/validate.sh`, `scripts/cleanup-sources.sh`, all referenced templates, and any guide required by the selected execution path. Stop before writing if a required resource is unavailable.
- [ ] Determine repo path: `REPO_PATH="${provided_path:-$PWD}"`
- [ ] Detect component name from repo (e.g., machine-config-operator → MCO)
- [ ] Run the resolved `scripts/create-structure.sh` with `"$REPO_PATH"`.

### Phase 2: Create AGENTS.md (40-60 lines)
- [ ] Create initial AGENTS.md at repo root using `templates/AGENTS-template.md`
- [ ] If existing AGENTS.md/CLAUDE.md was found in Phase 1, incorporate its critical warnings and conventions
- [ ] Treat `AGENTS.md` as the executive summary only. If the old `CLAUDE.md` contains longer repo-specific operational detail (release/bundle commands, CI/Konflux notes, metrics/debugging guidance), move that detail into `DEVELOPMENT.md` or `ARCHITECTURE.md` instead of dropping it.
- [ ] Preserve valuable navigation from prior agent docs. Keep compact, frequently used direct links in `AGENTS.md`. A detailed "need → start here" map may move to `ARCHITECTURE.md` or `ENHANCEMENTS.md`, but `AGENTS.md` must link directly to that map. Do not replace useful deep links with only a bare directory name.
- [ ] Include architecture-at-a-glance summary
- [ ] **Revisit after Phase 4**: Fill in the Critical Warnings section with 3-5 "never do X" rules discovered during architecture exploration
- [ ] Create CLAUDE.md symlink: `ln -sf AGENTS.md "$REPO_PATH/CLAUDE.md"`
- [ ] Validate line count: `wc -l AGENTS.md` (target: 40-60)

### Phase 3: ENHANCEMENTS.md (Optional)

- [ ] Search component repo for local design docs:
  - Check docs/, design/, enhancements/ directories
  - Check for files with "design", "proposal", "enhancement" in name
- [ ] Search openshift/enhancements repo for component-specific proposals:
  - Check `https://github.com/openshift/enhancements/tree/master/enhancements/{component-area}/`
- [ ] Search for related upstream KEPs (Kubernetes Enhancement Proposals)
- [ ] **Only create ai-docs/ENHANCEMENTS.md if content exists** — do not create an empty file
- [ ] Format: title, status (implemented/provisional/rejected), link only — keep concise
- [ ] Link to all found docs — these are authoritative sources, the enhancement is the source of truth
- [ ] **Note**: Enhancement proposals are feature designs (often cross-component). Key architectural decisions go inline in ARCHITECTURE.md "Design References" section, not here.

### Phase 4: Component Architecture (ARCHITECTURE.md)

- [ ] **Read one complete implementation first**: Pick one controller/component package (preferably the most recently added). Read ALL files in it — not just controller.go, but constants, utils, every reconciler file, install sequence, and tests. This is your reference implementation. Document every pattern you observe: how it applies resources, what shared utilities it calls, what predicates it uses, what constants it defines, what env vars it reads. If the repo has 2+ similar components, compare them — divergences in approach are the most valuable thing to document ("use X pattern from component A, not Y pattern from component B").
- [ ] **Detect repo type**: Check for operator signals (`controller-runtime`, `library-go`, `operator-sdk`, OLM bundle in `bundle/`, CRDs in `config/crd/`). If operator detected, follow the **Operator-Specific Discovery** checklist below in addition to the generic checklist.
- [ ] **Explore remaining codebase**: Read entrypoints, key packages, dependencies. Follow the **Implementation Pattern Discovery** checklist below.
- [ ] Create `ai-docs/ARCHITECTURE.md` with the following required sections:

**ARCHITECTURE.md Required Sections** (target: 200-400 lines):

1. **Repository Layout** — annotated directory tree with actionable annotations ("DO NOT use X for Y")
2. **Key Domain Concepts** — the core abstractions an agent must understand before touching this codebase. Not struct fields (agents read types.go), but the mental model: what are the primary resources, how do they relate, what are the key lifecycle flows. For operators: trace the primary end-to-end workflow (e.g., "user creates CR → controller renders config → daemon applies to node → node reboots"). For libraries: what are the key interfaces and their contracts. This section answers "what does this system DO" before the next sections explain "how is it BUILT"
3. **Component/Controller Details** — framework, startup sequence, per-controller tables
4. **Resource Management** — apply methods per controller (SSA, strategic merge, Create/Update), image resolution, deployment hooks
5. **Feature Gates** — definition → runtime check → startup wiring chain
6. **Error Classification** — error types, requeue behavior, status condition effects
7. **OpenShift Integration Points** — upstream project dependencies, OpenShift component integrations (CNO, CCO, OLM, proxy, TLS, etc.) with integration tables
8. **Generated Code Inventory** — generated files/dirs with "NEVER hand-edit" + make target
9. **API Behavioral Contracts** — behavioral knowledge that agents can't get from reading types.go alone: singleton constraints, naming conventions, merging order, lifecycle flows, config drift detection, plugin behaviors, gotchas, "DO NOT" rules. Point agents to types.go / api/ for actual struct field definitions
10. **Form Factor Behavior** (if applicable) — how the component behaves across deployment topologies: Standalone, SNO (replica adjustments, resource constraints), HCP/Hosted Control Planes (which cluster does it run in, cross-cluster communication), MicroShift (does it run, config alternatives). Only document form factors the code actually handles. Table format preferred
11. **Design References** — 2-3 key architectural decisions inline (5-8 lines each: title, decision, rationale, consequences). Link to existing repo design docs (from docs/) where they provide deeper detail
12. **Platform Documentation** — link to the openshift/enhancements repo for generic platform patterns. Reference stable paths: `dev-guide/` for development conventions, `guidelines/` for enhancement process, `CONVENTIONS.md` for coding standards. Do NOT link to specific files under `ai-docs/` — that structure is subject to change

- [ ] Document discovered patterns using the discovery checklist results
- [ ] Link to existing repo docs (from `docs/`, design docs) where they provide deeper detail — ARCHITECTURE.md is a map, not a replacement for existing documentation
- [ ] Keep lean but dense (every line should tell the reader something they can't infer from file names alone)
- [ ] Every pattern claim must include a file:line reference. If you can't point to source, flag as unverified

### Phase 4.5: Tribal Knowledge Enrichment (REQUIRED when chai-bot available)

- [ ] Use the Chai Bot access path selected above
- [ ] If hosted or external access is available: read and follow `guides/CHAI-BOT.md` — run both prompts, do not skip
- [ ] If Chai Bot is unavailable: report that tribal knowledge enrichment could not be performed, then skip this phase

### Phase 5: Development & Testing Docs

- [ ] **VERIFY FIRST**:
  ```bash
  # Go version
  grep "^go " "$REPO_PATH/go.mod"

  # Branch name (no clone needed) — uses first remote found
  _remote=$(git remote | head -1)
  git ls-remote --symref "$(git remote get-url "$_remote")" HEAD | grep 'ref:' | awk '{print $2}' | cut -d/ -f3

  # Makefile targets
  grep "^[a-zA-Z-]*:" Makefile | cut -d: -f1

  # Directory structure
  ls -d cmd pkg test manifests 2>/dev/null
  ```
- [ ] Create `ai-docs/DEVELOPMENT.md` using `templates/DEVELOPMENT-template.md`:
  - Do not repeat repo layout — it is in ARCHITECTURE.md
  - **Replace** generic template placeholders with actual repo patterns discovered in Phase 4
  - Fill "Common Tasks" with repo-specific tasks, not generic placeholders
  - Fill "Common Mistakes" from anti-patterns discovered in Phase 4
  - Preserve still-relevant operational detail from the prior `CLAUDE.md` (for example: bundle/catalog/release commands, CI/Konflux notes, metrics/debugging commands, non-default environment variables)
  - If common tasks vary in complexity, document tiers with specific file modification lists
- [ ] Create `ai-docs/TESTING.md` using `templates/TESTING-template.md`:
  - **Replace** generic code examples with actual test patterns from this repo
  - Fill "Component-Specific" sections with real test scenarios
- [ ] Link to Platform for generic practices
- [ ] Document ONLY verified component-specific details (target: 100-200 lines each)

### Phase 6: Generate REVIEW.md + .coderabbit.yaml (REQUIRED)

- [ ] Read and follow `guides/REVIEW-GENERATION.md` — all 8 steps are required
- [ ] Do not skip — REVIEW.md and .coderabbit.yaml are mandatory outputs

### Phase 7: Validation & Verification

- [ ] Run the resolved `scripts/validate.sh` with `"$REPO_PATH"` (includes link validation and removal of broken external-link lines)
- [ ] Verify `ai-docs/_sources/` contains backups of any prior `CLAUDE.md` / `AGENTS.md` that existed
- [ ] Verify AGENTS.md 40-60 lines, no generic duplication
- [ ] Verify CLAUDE.md → AGENTS.md symlink exists
- [ ] Verify ARCHITECTURE.md 200-400 lines, contains required sections (repo layout, API Behavioral Contracts, Design References, Platform Documentation)
- [ ] **Verify specificity**: Pattern claims backed by code evidence, not generic placeholders
- [ ] **Anti-hallucination checks**: Spot-check type fields if applicable, verify branch names in examples match repo, confirm pattern claims reference actual code
- [ ] **Operator-specific checks** (if operator repo): Verify apply method claims per-controller (`grep -r "client.Apply\|r.Update\|resourceapply" pkg/controller/<name>/`). Verify feature gate claims trace to actual runtime code. Verify image env var names match Makefile/CSV.
- [ ] **REVIEW.md checks**: exists at repo root, ≤100 lines (`wc -l REVIEW.md`), skip paths reference real directories (`test -d`), platform citations present (grep for "dev-guide" or "CONVENTIONS"), no content overlap with AGENTS.md
- [ ] **.coderabbit.yaml checks**: valid YAML (`python3 -c "import yaml; yaml.safe_load(open('.coderabbit.yaml'))"`), `filePatterns` contains "REVIEW.md" but NOT "CLAUDE.md", `path_filters` match "Do not report" globs, `path_instructions` match "Path-specific rules"
- [ ] Cross-check with openshift-docs if time permits
- [ ] **Chai-bot enrichment gate**: If hosted or external Chai Bot access is available, verify Phase 4.5 was executed (operational issues and design rationale queries were run and results incorporated into ARCHITECTURE.md and DEVELOPMENT.md). If skipped with Chai Bot available, go back and run it before proceeding.
- [ ] **Flag discovery gaps**: At the end of ARCHITECTURE.md and DEVELOPMENT.md, add a brief "SME Review Recommended" note listing areas where automated discovery may be incomplete
- [ ] **No silent drops**: Compare the prior `CLAUDE.md` / `AGENTS.md` against the generated docs and ensure repo-specific commands, CI notes, metrics/debug tips, hard warnings, retrieval instructions, documentation maps, and useful direct links were preserved. For every relocated item, verify the new location and leave a discoverable route from `AGENTS.md`. Record any intentional drop and its rationale in the completion report.
- [ ] **Cleanup**: After validation passes, run the resolved `scripts/cleanup-sources.sh` with `"$REPO_PATH"`. Do not leave temporary source backups in the final repo tree.

**Link Validation**:
- Link validation always runs — broken links (wrong relative paths, 404 URLs) are a common source of documentation errors
- Automatically checks all HTTP/HTTPS links (with timeout and user agent)
- Validates internal/relative links (file existence)
- Use `VERBOSE=true` with the resolved validator to see successful links. Use `CHECK_EXTERNAL_LINKS=false` when the host intentionally has no network access; report external links as unverified in that mode.

### Phase 8: Verification (Recommended)

- [ ] **Ask user**: "Run `/review-docs` to verify claims?"
  - If **YES**: Run `/review-docs --path "$REPO_PATH"`
  - If **NO**: Warn user:
    ```
    Skipping verification. Documentation may contain:
    - Incorrect API field claims
    - Wrong branch/version references
    - Unverified pattern claims (SSA vs strategic merge, etc.)

    Recommend running `/review-docs` before creating PRs to catch hallucinations.
    ```

**Note**: `/review-docs` verifies claims locally against the repo's source code (including vendored dependencies) first, then uses Chai Bot for cross-repo verification (enhancements, platform terminology, convention compliance). Chai Bot access may be provided directly by its hosted workspace or through an external MCP connection. External access requires VPN + MCP configuration — see [review-docs skill](../review-docs/SKILL.md).

## Implementation Pattern Discovery

Use this checklist during Phase 4 when exploring the codebase. These patterns produce the most valuable documentation — the kind that prevents an agent from writing subtly incorrect code.

### What to Look For

| Pattern | How to Discover | What to Document |
|---------|----------------|------------------|
| **Multiple paradigms** | Do different packages use different frameworks or approaches for similar tasks? | Comparison table with "use X for Y, never Z for Y" guidance |
| **Shared utilities** | Is there a `common/`, `shared/`, `utils/`, or `internal/` package used across components? | Exact exported symbols with one-line usage contract |
| **Wiring/registration** | How do new components get registered and started? How does work get dispatched to them? | Startup sequence, event/trigger flow, where to hook in new components |
| **Resource management** | How does code create/update external resources? (SSA, strategic merge, REST calls, etc.) | Actual method with code reference — verify in code, don't assume |
| **Naming conventions** | Grep for patterns in env vars, labels, file names, package names | Exact format with examples |
| **Feature toggles** | Are there feature gates, flags, or config-driven enablement? | Definition → runtime check → wiring chain |
| **Anti-patterns** | Search for "DO NOT", "NEVER", "MUST", "HACK" in code comments. Study 2-3 existing implementations to identify shared patterns and things they avoid | Numbered "DO NOT" list with brief explanation |
| **CI enforcement** | `grep -E "^(lint\|fmt\|vet\|check\|verify):" Makefile` | CI-enforced checks → "Do not report" in REVIEW.md |
| **High-risk areas** | `git log --since="1 year" --name-only --pretty=format: \| sort \| uniq -c \| sort -rn \| head -20` | High-churn files → severity tuning in REVIEW.md |
| **Vendored API boundaries** | `ls vendor/github.com/openshift/api 2>/dev/null` | Vendored API types → "Always check" in REVIEW.md |

### Operator-Specific Discovery

When the repo is a Kubernetes/OpenShift operator (detected via controller-runtime, library-go, OLM bundle, CRDs), also investigate these patterns. Skipping them produces docs that look correct but cause agents to write subtly wrong code.

| Pattern | How to Discover | What to Document |
|---------|----------------|------------------|
| **Controller framework split** | Check imports in EACH controller package for `library-go` vs `controller-runtime`. Don't assume uniformity. | Per-controller table: framework, apply method (`client.Apply` vs `resourceapply` vs Create+Update), code ref. |
| **Reconciliation apply method** | For EACH controller: `grep -r "client.Apply\|r.Update\|r.Create\|resourceapply" pkg/controller/<name>/` | Actual method per controller. This is the #1 source of hallucinations. |
| **Feature gate runtime behavior** | Read `features.go` end-to-end. Trace from definition → runtime check → startup wiring. | Full chain. For TechPreview: cluster-side gating (FeatureSet discovery, fail-closed). Don't just list gate names. |
| **Image resolution & OLM bundle** | `grep -r RELATED_IMAGE Makefile bundle/`. Check Makefile for `*_VERSION` vars. Check `bundle/manifests/` for CSV. | Env var naming convention, version variables, how OLM injects images. CSV update checklist (env vars, RBAC, relatedImages). |
| **Error classification** | Check common/ for error wrapper types (`IrrecoverableError`, `RetryRequiredError`). | Which types exist, effect on requeue behavior. |
| **Generated code & bindata pipeline** | `find . -name "zz_generated*" -o -name "bindata.go" -o -path "*/clientset/*"`. Check Makefile for generation targets. | Generated files/dirs with "NEVER hand-edit" + make target. For bindata: version var → hack script → output dir → Go loading. |
| **FIPS compliance** | Check for OpenShift fork references in `go.mod` (`replace` directives), FIPS build tags, or crypto constraints in Dockerfiles. | Whether FIPS is build-time (fork/toolchain) or runtime. Only document if present. |
| **OLM lifecycle** | Check `bundle/manifests/` CSV for `spec.replaces`, `skips`, `skipRange`, `installModes`, `spec.relatedImages`, channel annotations. | Which upgrade strategy is used, relatedImages list, install mode constraints. |
| **Status conditions & OpenShift integrations** | Check for library-go `OperatorStatus` vs custom conditions. Grep for proxy, trusted-CA, TLS profile, CCO references. | Which condition system, which integrations exist — only document what's present. |
| **Form factor behavior** | Grep for topology detection: `ControlPlaneTopology`, `InfrastructureTopology`, `SingleReplica`, `HighlyAvailable`, `External`, `single-node-cluster` label, `hypershift`, `HostedControlPlane`, `HostedCluster`. Check for replica count adjustments, anti-affinity skips, or HCP-specific namespaces/RBAC. | Form factor table: how the component behaves on Standalone, SNO (single replica? resource constraints?), HCP (which cluster does it run in? cross-cluster communication?), MicroShift (does it run at all? config file alternative?). Only document form factors the code actually handles — don't invent behavior. |

### Information Density

- Exact symbol names over generic descriptions
- Comparison tables for contrasting patterns
- "Never" / "DO NOT" warnings for common confusion points
- One table with symbols beats three paragraphs of prose
- Every line should tell the reader something they can't infer from file names alone
- Every pattern claim must include a file:line reference (e.g., `pkg/controller/foo/deployments.go:40`). If you can't point to source, you're inferring — flag it as unverified instead of stating it as fact

## AGENTS.md Requirements

**Length**: 40-60 lines (strict limit)

**Required Sections**:
1. Component metadata (name, repository)
2. Purpose (1-2 sentences)
3. Critical warnings (3-5 "never do X" rules — the most important architectural warnings)
4. Architecture at a glance (brief orientation)
5. Documentation structure (flat tree)
6. Key files quick reference
7. External references

**Format**: Compressed, table-based, links not prose. Use `templates/AGENTS-template.md`.

**Symlink**: `CLAUDE.md → AGENTS.md` must exist at repo root.

## Validation Criteria

✅ **AGENTS.md**: At repo root, 40-60 lines, critical warnings, no generic duplication

✅ **CLAUDE.md**: Symlink to AGENTS.md

✅ **Temporary sources cleaned up**: Any working backups created under `ai-docs/_sources/` were removed before finishing

✅ **No duplication**: No generic framework explanations, no testing pyramid, no security frameworks

✅ **ARCHITECTURE.md**: 200-400 lines, contains repo layout, API Behavioral Contracts, Design References, OpenShift Integration Points, Platform Documentation sections

✅ **Link validation**: All external links return 200 OK, all internal links resolve

✅ **Implementation patterns**: ARCHITECTURE.md has discovery checklist results, shared utilities listed with exact symbols, anti-patterns documented

✅ **Operator accuracy** (if operator repo): Apply method documented per-controller (not assumed uniform), feature gate runtime behavior traced, generated code inventory listed, image resolution mechanism documented

✅ **REVIEW.md**: At repo root, 60-80 lines (cap 100), skip paths valid, platform citations present, no AGENTS.md overlap, .coderabbit.yaml in sync

## Anti-Patterns

### ❌ DON'T duplicate Platform content

**Wrong**: 187-line TESTING.md where 60% is generic test pyramid explanation
**Right**: 90-line TESTING.md that's 100% component-specific, links to Platform

### ❌ DON'T explain generic framework patterns

**Wrong**: Explaining framework internals in component docs
**Right**: Link to Platform, document component-specific usage only

### ❌ DON'T document without verification

**Wrong**: Type fields from memory, outdated conventions, pattern claims without code evidence
**Right**: Verify in source code, check actual branch names, confirm patterns exist, link to sources


### ❌ DON'T write generic placeholders

**Wrong**: "Add new controller: 1. Create controller.go 2. Implement Reconcile() 3. Register"
**Right**: Repo-specific steps with exact file paths, shared utilities to use, registration wiring, and naming conventions

### ❌ DON'T scatter related content across many files

**Wrong**: Scattering content across many small files — agents must read 8+ files
**Right**: ARCHITECTURE.md as single authoritative source for internals, integrations, contracts, and key decisions

### ❌ DON'T ignore existing repo documentation

**Wrong**: Generating docs that don't link to existing design docs in docs/
**Right**: Discover and link to all existing repo docs — they are authoritative sources

## Prerequisites

1. ✅ openshift/enhancements repo accessible (dev-guide/, guidelines/, CONVENTIONS.md)
2. ✅ Repository is an OpenShift component

## Arguments

```bash
/component-docs [--path <repository-path>]
```

- `--path <repository-path>`: Path to component repository (default: current directory)

## Success Output

```text
✅ Component Documentation Created

Component: [component-name]
Repository: [path]

Structure:
  ✅ AGENTS.md (root): XX lines (target: 40-60)
  ✅ CLAUDE.md → AGENTS.md symlink
  ✅ REVIEW.md: XX lines (target: 60-80)
  ✅ .coderabbit.yaml: valid, synced with REVIEW.md
  ✅ ARCHITECTURE.md: XXX lines (target: 200-400)
  ✅ DEVELOPMENT.md
  ✅ TESTING.md
  ✅ ENHANCEMENTS.md (optional — only if content found)

Next Steps:
  1. Run `/review-docs` to verify claims locally + cross-repo via chai-bot (recommended)
  2. Review generated documentation for accuracy
  3. Create PR with documentation changes
```

## See Also

- `/review-docs` - Verify documentation claims locally and cross-repo via chai-bot (recommended after creation)
- `/update-platform-docs` - Update Platform documentation
- Platform Documentation (openshift/enhancements — dev-guide/, guidelines/, CONVENTIONS.md)
