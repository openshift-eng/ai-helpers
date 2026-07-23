---
name: component-docs
description: Create lean component documentation for OpenShift repositories
trigger: explicit
---

# Component Documentation Creator

Creates lean component agentic documentation for OpenShift component repositories.

**Philosophy**: Component docs contain ONLY component-specific knowledge. Generic platform patterns live in platform (openshift/enhancements/ai-docs/).

## Two-Tier Architecture

### Platform: Platform Hub (openshift/enhancements/ai-docs/)
**Contains**: Operator patterns, testing practices, security guidelines, Kubernetes/OpenShift fundamentals, cross-repo ADRs

### Component: Component Repos (LEAN)
**Contains**: Component-specific APIs/types, component architecture, component ADRs, exec-plans

**Decision Rule**: "Would another repo need to duplicate this?"
- YES → Platform (platform)
- NO → Component (component)

## What Gets Created

```text
component-repo/
├── AGENTS.md                      # Master entry point (80-100 lines)
└── ai-docs/
    ├── domain/                    # Component APIs/types
    ├── architecture/              # Component internals
    │   └── components.md
    ├── decisions/                 # Component ADRs ONLY
    │   ├── adr-0001-*.md
    │   └── adr-template.md
    ├── exec-plans/
    │   ├── active/                # Features being implemented
    │   └── README.md              # Pointer to Platform guidance
    ├── references/
    │   ├── ecosystem.md           # Links to Platform (CRITICAL)
    │   └── enhancements.md        # Enhancement proposals & design docs
    ├── [COMPONENT]_DEVELOPMENT.md
    └── [COMPONENT]_TESTING.md
```

## What NOT to Include (lives in Platform)

❌ Generic framework patterns (controller-runtime, status conditions, common libraries)
❌ Testing practices (test pyramid, E2E framework)
❌ Security practices (STRIDE, RBAC guidelines)
❌ Reliability practices (SLO framework)
❌ Kubernetes fundamentals (Pod, Node, Service)
❌ Cross-repo ADRs (etcd, CVO orchestration, immutable nodes)

## Execution Workflow

### Phase 1: Setup
- [ ] **SME context**: Ask the user: "Before I start, is there anything about this repo I should know that isn't obvious from the code?" Wait for a response before proceeding. Use their input to guide what you investigate in Phases 5, 6, and 9.
- [ ] Find skill directory: `SKILL_DIR=$(find ~/.claude/plugins/cache -path "*/component-docs" -type d | head -1)`
- [ ] Determine repo path: `REPO_PATH="${provided_path:-$PWD}"`
- [ ] Detect component name from repo (e.g., machine-config-operator → MCO)
- [ ] Run `bash "$SKILL_DIR/scripts/create-structure.sh" "$REPO_PATH"`

### Phase 2: Create AGENTS.md (80-100 lines)
- [ ] Create initial AGENTS.md at repo root using `templates/AGENTS-template.md`
- [ ] Include compressed index of component docs
- [ ] Add Platform ecosystem hub links
- [ ] **Revisit after Phase 5**: Fill in the Critical Patterns section with 2-3 "never do X" rules discovered during architecture exploration
- [ ] Validate line count: `wc -l AGENTS.md` (target: 80-100)

### Phase 3: Component Domain Concepts

- [ ] Identify component-specific APIs, types, or CRDs:
  - For operators: check CRD definitions, `oc api-resources`, or `config/crd/`
  - For libraries: identify primary exported types and interfaces
  - For CLIs: identify core commands and configuration types
- [ ] **VERIFY BEFORE DOCUMENTING**: For each type you plan to document, find its definition and verify fields/values from source:
  ```bash
  # Replace <TypeName> with the actual type (e.g., MachineSet, Build, Route)

  # If types live in openshift/api
  [ ! -d "/tmp/openshift-api" ] && git clone --depth 1 https://github.com/openshift/api.git /tmp/openshift-api
  find /tmp/openshift-api -name "types*.go" | xargs grep -A30 "type <TypeName>"

  # OR in component repo
  find . -name "types*.go" -o -name "types.go" | xargs grep -A30 "type <TypeName>"
  ```
  Read actual source, document ONLY existing fields with correct types
- [ ] Create domain/*.md for each key type with links to source definitions (100-200 lines per concept)
- [ ] Use `templates/domain-concept-template.md` for structure
- [ ] Focus on component-specific behavior, link to Platform for generic patterns

### Phase 4: Enhancement Proposals & Design Docs
- [ ] Create references/enhancements.md to catalog all design documentation
- [ ] Search openshift/enhancements repo for component-specific proposals:
  - Check `https://github.com/openshift/enhancements/tree/master/enhancements/{component-area}/`
- [ ] Search component repo for local design docs:
  - Check docs/, design/, enhancements/ directories
  - Check for files with "design", "proposal", "enhancement" in name
- [ ] Categorize by status: implemented/provisional/rejected
- [ ] Keep concise: title, status, link only (enhancement is the source of truth)
- [ ] **Note**: Enhancement proposals are feature designs (often cross-component). ADRs are component architectural decisions. Don't conflate them.

### Phase 5: Component Architecture

- [ ] **Read one complete implementation first**: Pick one controller/component package (preferably the most recently added). Read ALL files in it — not just controller.go, but constants, utils, every reconciler file, install sequence, and tests. This is your reference implementation. Document every pattern you observe: how it applies resources, what shared utilities it calls, what predicates it uses, what constants it defines, what env vars it reads. If the repo has 2+ similar components, compare them — divergences in approach are the most valuable thing to document ("use X pattern from component A, not Y pattern from component B").
- [ ] **Detect repo type**: Check for operator signals (`controller-runtime`, `library-go`, `operator-sdk`, OLM bundle in `bundle/`, CRDs in `config/crd/`). If operator detected, follow the **Operator-Specific Discovery** checklist below in addition to the generic checklist.
- [ ] **Explore remaining codebase**: Read entrypoints, key packages, dependencies. Follow the **Implementation Pattern Discovery** checklist below. The architecture doc should contain enough detail that an agent reading it produces correct code on the first try.
- [ ] Create architecture/components.md with **repo layout as single source of truth** (add actionable annotations like "DO NOT use X for Y")
- [ ] Document discovered patterns using the discovery checklist results
- [ ] Explain component relationships and data flow
- [ ] Keep lean but dense (100-200 lines, high information per line)

### Phase 5.5: Tribal Knowledge Enrichment (Optional)

Requires chai-bot MCP server. If unavailable, skip — Phase 5 content stands on its own.

Two prompts, run sequentially via `mcp__chai-bot__ask_persona`. Substitute `{component}` with the repo name.

**Prompt 1 — Operational knowledge** (run immediately after Phase 5):

```
"I'm generating agentic documentation for {component}
(github.com/openshift/{component}).

I already have complete architecture, code structure, controller
design, Makefile targets, and API types from reading the source
code. DO NOT describe any of these — your answers about repo
internals will be wrong.

Instead, tell me ONLY things that cannot be learned from the
source code:

1. OPERATIONAL ISSUES: Production failures, support escalations,
   upgrade gotchas, or common misconfigurations discussed in
   Slack or filed in Jira. Include Jira keys if you know them.

2. CROSS-COMPONENT FRICTION: Misunderstood boundaries or
   surprising interactions between {component} and other
   OpenShift components (OLM, service-ca, console, CCO,
   monitoring, etc.).

Format each item as:
- Title (short)
- Source (Slack channel, Jira key, or 'team knowledge')
- Description (2-3 sentences max)

If you don't have tribal knowledge for a category, say so —
don't fill it with code observations."
```

**Prompt 2 — Design rationale** (requires Phase 5 findings):

Review Phase 5 results. Identify 3-5 patterns that are surprising, inconsistent, or divergent across components — where the code shows *what* but not *why*. Then:

```
"I'm documenting design decisions for {component}
(github.com/openshift/{component}). I already know WHAT the
code does — I need to know WHY from Slack, Jira, or team
discussions.

For each question below, only answer if you have actual context
from Slack threads, Jira issues, PR discussions, or team
conversations. If you're guessing from code structure, say
'no tribal knowledge found' — that's more useful than inference.

1. [Specific divergence found in Phase 5]
2. [Another divergence]
3. [...]

For each answer, include the source (Slack channel/thread date,
Jira key, PR number) so I can trace it."
```

**Filtering**: DISCARD any claims about repo internals (namespaces, file paths, Makefile targets, function names, controller structure) — chai-bot fabricates these. KEEP only Slack/Jira/docs knowledge that cannot be learned from code.

**Placement** (no separate file — findings go where developers already look):
- Operational issues → `[COMPONENT]_DEVELOPMENT.md` "Known Operational Issues" section (Phase 9)
- Cross-component friction → `architecture/components.md` under "OpenShift Integrations" (Phase 5)
- Design rationale → ADR "Context" sections (Phase 6)

### Phase 6: Component ADRs
- [ ] Create decisions/adr-template.md (copy from templates)
- [ ] Create 2-3 component-specific ADRs
- [ ] **Enrich with Phase 5.5**: If chai-bot provided design rationale, add to the ADR's "Context" section with source (e.g., "Per CM-486 (Jira)..."). If "no tribal knowledge found", note under "SME Review Recommended".
- [ ] NO cross-repo ADRs (those go in Platform)

### Phase 7: Exec-Plans
- [ ] Create exec-plans/active/ directory
- [ ] Create exec-plans/README.md with pointer to Platform guidance

### Phase 8: Ecosystem References
- [ ] Create references/ecosystem.md using `templates/ecosystem-template.md`
- [ ] Link to Platform: operator patterns, testing, security, Kubernetes/OpenShift fundamentals, cross-repo ADRs

### Phase 9: Development & Testing Docs

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
- [ ] Create [COMPONENT]_DEVELOPMENT.md from template:
  - **Remove** "Repository Structure" section (already in components.md)
  - **Replace** generic template placeholders with actual repo patterns discovered in Phase 5
  - Fill "Common Tasks" with repo-specific tasks, not generic placeholders
  - Fill "Common Mistakes" from anti-patterns discovered in Phase 5
  - If common tasks vary in complexity, document tiers with specific file modification lists
- [ ] Create [COMPONENT]_TESTING.md from template:
  - **Replace** generic code examples with actual test patterns from this repo
  - Fill "Component-Specific" sections with real test scenarios
- [ ] Link to Platform for generic practices
- [ ] Document ONLY verified component-specific details (target: 100-200 lines each)

### Phase 10: Validation & Verification

- [ ] Run `bash "$SKILL_DIR/scripts/validate.sh" "$REPO_PATH"` (includes link validation)
- [ ] Verify AGENTS.md ≤100 lines, no generic duplication, ecosystem.md exists
- [ ] **Verify specificity**: Repo structure only in components.md (not duplicated in DEVELOPMENT.md), pattern claims backed by code evidence
- [ ] **Anti-hallucination checks**: Spot-check type fields if applicable, verify branch names in examples match repo, confirm pattern claims reference actual code
- [ ] **Operator-specific checks** (if operator repo): Verify apply method claims per-controller (`grep -r "client.Apply\|r.Update\|resourceapply" pkg/controller/<name>/`). Verify feature gate claims trace to actual runtime code. Verify image env var names match Makefile/CSV.
- [ ] Verify all domain/*.md files link to actual type definitions
- [ ] Cross-check with openshift-docs if time permits
- [ ] **Flag discovery gaps**: At the end of components.md and DEVELOPMENT.md, add a brief "SME Review Recommended" note listing areas where automated discovery may be incomplete — typically: implementation recipes for adding new components, anti-patterns from institutional knowledge, and rationale behind pattern choices. This sets expectations that the docs are a verified foundation, not a complete implementation guide

**Link Validation**:
- Link validation always runs — broken links (wrong relative paths, 404 URLs) are a common source of documentation errors
- Automatically checks all HTTP/HTTPS links (with timeout and user agent)
- Validates internal/relative links (file existence)
- Flags known Platform planned links as "KNOWN BROKEN"
- Use `VERBOSE=true bash "$SKILL_DIR/scripts/validate.sh" "$REPO_PATH"` to see all links including successful ones

### Phase 11: Verification (Recommended)

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

**Note**: `/review-docs` verifies claims locally against the repo's source code (including vendored dependencies) first, then uses chai-bot MCP for cross-repo verification (enhancements, platform terminology, convention compliance). Local verification works without any setup. Chai-bot is needed for cross-functional checks and requires VPN + MCP configuration — see [review-docs skill](../review-docs/SKILL.md).

## Implementation Pattern Discovery

Use this checklist during Phase 5 when exploring the codebase. These patterns produce the most valuable documentation — the kind that prevents an agent from writing subtly incorrect code.

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

### Operator-Specific Discovery

When the repo is a Kubernetes/OpenShift operator (detected via controller-runtime, library-go, OLM bundle, CRDs), also investigate these patterns. Skipping them produces docs that look correct but cause agents to write subtly wrong code.

| Pattern | How to Discover | What to Document |
|---------|----------------|------------------|
| **Controller framework split** | Check imports in EACH controller package for `library-go` vs `controller-runtime`. Don't assume uniformity. | Per-controller table: framework, apply method (`client.Apply` vs `resourceapply` vs Create+Update), code ref. |
| **Reconciliation apply method** | For EACH controller: `grep -r "client.Apply\|r.Update\|r.Create\|resourceapply" pkg/controller/<name>/` | Actual method per controller. This is the #1 source of hallucinations — the cert-manager-operator review found docs claiming "all controllers use SSA" when only one of three did. |
| **Feature gate runtime behavior** | Read `features.go` end-to-end. Trace from definition → runtime check → startup wiring. | Full chain. For TechPreview: cluster-side gating (FeatureSet discovery, fail-closed). Don't just list gate names. |
| **Image resolution & OLM bundle** | `grep -r RELATED_IMAGE Makefile bundle/`. Check Makefile for `*_VERSION` vars. Check `bundle/manifests/` for CSV. | Env var naming convention, version variables, how OLM injects images. CSV update checklist (env vars, RBAC, relatedImages). |
| **Error classification** | Check common/ for error wrapper types (`IrrecoverableError`, `RetryRequiredError`). | Which types exist, effect on requeue behavior. |
| **Generated code & bindata pipeline** | `find . -name "zz_generated*" -o -name "bindata.go" -o -path "*/clientset/*"`. Check Makefile for generation targets. | Generated files/dirs with "NEVER hand-edit" + make target. For bindata: version var → hack script → output dir → Go loading. |
| **FIPS compliance** | Check for OpenShift fork references in `go.mod` (`replace` directives), FIPS build tags, or crypto constraints in Dockerfiles. | Whether FIPS is build-time (fork/toolchain) or runtime. Only document if present — not all operators have FIPS requirements. |
| **OLM lifecycle** | Check `bundle/manifests/` CSV for `spec.replaces`, `skips`, `skipRange`, `installModes`, `spec.relatedImages`, channel annotations. | Which upgrade strategy is used, relatedImages list, install mode constraints. Document if the operator has OLM-specific lifecycle quirks (e.g., cross-namespace cleanup limitations, annotation conflicts on reinstall). |
| **Status conditions & OpenShift integrations** | Check for library-go `OperatorStatus` vs custom conditions. Grep for proxy, trusted-CA, TLS profile, CCO references. | Which condition system, which integrations exist — only document what's present. |

### Information Density

- Exact symbol names over generic descriptions
- Comparison tables for contrasting patterns
- "Never" / "DO NOT" warnings for common confusion points
- One table with symbols beats three paragraphs of prose
- Every line should tell the reader something they can't infer from file names alone
- Every pattern claim must include a file:line reference (e.g., `pkg/controller/foo/deployments.go:40`). If you can't point to source, you're inferring — flag it as unverified instead of stating it as fact

## AGENTS.md Requirements

**Length**: 80-100 lines (strict limit)

**Required Sections**:
1. Component metadata (name, repository)
2. Platform reference (link to ecosystem hub)
3. Component purpose (1-2 sentences)
4. Core components (brief)
5. Critical patterns (2-3 "never do X" rules — the most important architectural warnings)
6. Documentation structure (compressed)
7. Platform ecosystem links

**Format**: Compressed, table-based, links not prose. Use `templates/AGENTS-template.md`.

## Validation Criteria

✅ **AGENTS.md**: At repo root, 80-100 lines, compressed index, retrieval-first instruction, Platform links, critical pattern warnings

✅ **No duplication**: No generic framework explanations, no testing pyramid, no security frameworks

✅ **References**: ecosystem.md with Platform links, enhancements.md with design docs catalog

✅ **Component-specific only**: Domain concepts are component-specific, ADRs are component-specific, architecture is component internals

✅ **Link validation**: All external links return 200 OK, all internal links resolve

✅ **Implementation patterns**: Architecture doc has discovery checklist results, shared utilities listed with exact symbols, anti-patterns documented

✅ **Operator accuracy** (if operator repo): Apply method documented per-controller (not assumed uniform), feature gate runtime behavior traced, generated code inventory listed, image resolution mechanism documented

## Anti-Patterns

### ❌ DON'T duplicate Platform content

**Wrong**: 187-line TESTING.md where 60% is generic test pyramid explanation
**Right**: 90-line COMPONENT_TESTING.md that's 100% component-specific, links to Platform

### ❌ DON'T explain generic framework patterns

**Wrong**: Explaining framework internals in component docs
**Right**: Link to Platform, document component-specific usage only

### ❌ DON'T create cross-repo ADRs

**Wrong**: ADR about shared infrastructure in component repo
**Right**: That ADR belongs in Platform

### ❌ DON'T document without verification

**Wrong**: Type fields from memory, outdated conventions, pattern claims without code evidence
**Right**: Verify in source code, check actual branch names, confirm patterns exist, link to sources

### ❌ DON'T write generic placeholders

**Wrong**: "Add new controller: 1. Create controller.go 2. Implement Reconcile() 3. Register"
**Right**: Repo-specific steps with exact file paths, shared utilities to use, registration wiring, and naming conventions

## Prerequisites

1. ✅ Platform documentation exists at openshift/enhancements/ai-docs/
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
  ✅ AGENTS.md (root): XX lines (target: 80-100)
  ✅ Domain concepts: N files
  ✅ Architecture: components.md
  ✅ Component ADRs: N files
  ✅ References: ecosystem.md, enhancements.md
  ✅ Development: COMPONENT_DEVELOPMENT.md
  ✅ Testing: COMPONENT_TESTING.md

Next Steps:
  1. Run `/review-docs` to verify claims locally + cross-repo via chai-bot (recommended)
  2. Review generated documentation for accuracy
  3. Create PR with documentation changes
```

## See Also

- `/review-docs` - Verify documentation claims locally and cross-repo via chai-bot (recommended after creation)
- `/update-platform-docs` - Update Platform documentation
- Platform Documentation (openshift/enhancements/ai-docs/)
