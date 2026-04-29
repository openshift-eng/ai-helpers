---
name: platform-docs
description: Create AI-optimized platform documentation for openshift/enhancements
trigger: explicit
model: sonnet
---

# Platform Documentation Creator

Creates AI-optimized platform documentation in `openshift/enhancements` repository under `ai-docs/`.

## 🚨 EXECUTION WORKFLOW 🚨

**Follow this workflow. Create documentation based on principles, not arbitrary counts.**

### Phase 1: Setup ⚙️
- [ ] Find skill directory: `SKILL_DIR=$(find ~/.claude/plugins/cache -path "*/platform" -type d | head -1)`
- [ ] Determine repo path: `REPO_PATH="${provided_path:-$PWD}"`
- [ ] Run discovery: `bash "$SKILL_DIR/scripts/discover.sh" "$REPO_PATH"`
- [ ] IF `ai-docs/` doesn't exist: Run `bash "$SKILL_DIR/scripts/create-structure.sh" "$REPO_PATH"`
- [ ] IF `ai-docs/` doesn't exist: Run `bash "$SKILL_DIR/scripts/populate-templates.sh" "$REPO_PATH"`
- [ ] IF `ai-docs/` exists: Run `bash "$SKILL_DIR/scripts/fill-gaps.sh" "$REPO_PATH"`

### Phase 2: Master Entry Point 📄
- [ ] Create `AGENTS.md` in repo root (~100-200 lines, use templates/AGENTS.md as reference)
- [ ] Validate line count: `wc -l AGENTS.md` (target: 100-200 lines)

### Phase 3: Platform Patterns 🔧
- [ ] Read DESIGN_PHILOSOPHY.md to understand core principles
- [ ] For each principle, identify patterns needed to implement it
- [ ] Create pattern docs ONLY if they fill gaps (no duplication of dev-guide)
- [ ] Use `templates/operator-pattern-template.md` for structure

**Common patterns** (create based on need, not mandatory list):
- Status reporting (Available/Progressing/Degraded) → observability principle
- Controller runtime (reconcile loops) → desired-state principle  
- Upgrade safety (version skew, N→N+1) → upgrade-safety principle
- RBAC patterns → security principle

### Phase 4: Engineering Practices 📚
- [ ] Scan dev-guide/ and guidelines/ to identify what already exists
- [ ] Identify gaps where AI agents need structured guidance
- [ ] Create index.md files that LINK to existing dev-guide content
- [ ] Create NEW practice docs ONLY for gaps (use tables/checklists, not prose)
- [ ] Use `templates/practice-template.md` for structure

**Common practice areas** (assess each, create if needed):
- Testing pyramid (60/30/10 ratios, when to use each level)
- Security (STRIDE threat modeling, RBAC patterns, secret handling)
- Reliability (SLI/SLO/SLA definitions, degraded-mode patterns)
- Development (API evolution rules, compatibility guidelines)

### Phase 5: Domain Concepts 🧩
- [ ] Identify APIs fundamental to understanding OpenShift architecture
- [ ] For each API: document purpose, key fields (YAML), common patterns
- [ ] Use `templates/domain-concept-template.md` for structure
- [ ] Link to `oc explain <resource>` for exhaustive field details

**Common APIs** (create based on architectural significance):
- Kubernetes core (Pod, Service, CRD), OpenShift platform (ClusterOperator, ClusterVersion), Machine API

**Don't document**: Every field, component-specific APIs, deprecated APIs

### Phase 6: Cross-Repo ADRs 📋
- [ ] Identify architectural decisions that explain design principles
- [ ] Create ADRs ONLY for cross-repo decisions (not component-specific)
- [ ] Always create: `decisions/index.md` and `decisions/adr-template.md`
- [ ] Use `templates/adr-template.md` for structure

**Typical ADRs** (create if they explain design philosophy):
- Why etcd, why CVO orchestration, why immutable nodes

**Don't create**: Component-specific decisions, implementation details, duplicates of dev-guide

### Phase 7: Workflows & References 🔗

**Workflows** (AI-optimized versions):
- [ ] Create `workflows/enhancement-process.md` - Reformat `guidelines/enhancement_template.md` into tables/steps/YAML
- [ ] Create `workflows/implementing-features.md` - Structured workflow (spec → plan → build → test → review → ship)
- [ ] Create `workflows/index.md` - Navigation + links to guidelines/ for authoritative source

**References** (pointer-based):
- [ ] Create `references/repo-index.md` with GitHub org search links (not exhaustive lists)
- [ ] Create `references/glossary.md` with core stable terms only (~15-20 terms)
- [ ] Create `references/api-reference.md` with `oc api-resources` pointer
- [ ] Create `references/index.md` for navigation

**Key principle**: 
- Workflows are AI-optimized (tables, checklists, structured) versions of guidelines content
- References use pointers (GitHub links, `oc` commands) not exhaustive lists

### Phase 7.5: Exec-Plans (Feature Tracking) 📋

**Purpose**: Provide templates and guidance for tracking feature implementation

- [ ] Create `workflows/exec-plans/README.md` using `templates/workflows/exec-plans-README.md`
- [ ] Create `workflows/exec-plans/template.md` using `templates/workflows/exec-plan-template.md`
- [ ] Explain when to use exec-plans (multi-week features, multi-PR coordination)
- [ ] Explain relationship to enhancements (enhancement = design, exec-plan = implementation tracking)
- [ ] Explain completion workflow (extract to ADRs/architecture, then delete)

**Key principle**:
- Guidance lives in Tier 1 (generic, used by all repos)
- Actual exec-plans live in Tier 2 component repos (`ai-docs/exec-plans/active/`)
- Exec-plans are ephemeral - extract knowledge to permanent docs, then delete

### Phase 8: Validation ✅
- [ ] Run validation: `bash "$SKILL_DIR/scripts/validate.sh" "$REPO_PATH"`
- [ ] IF validation fails: Fix issues and re-run
- [ ] Verify all required files exist
- [ ] Verify AGENTS.md is 100-200 lines

### Phase 9: Report 📊
- [ ] Report created files count
- [ ] Report validation status
- [ ] Suggest git commit command

**🚨 DO NOT SKIP ANY CHECKBOX. Complete phases in order.**

---

## What This Skill Creates

**Principle**: Generate documentation that helps AI agents understand and apply OpenShift design philosophy.

**Structure:**
```text
AGENTS.md                       # Master entry point (navigation)
ai-docs/
├── DESIGN_PHILOSOPHY.md        # Core principles (copy from templates)
├── KNOWLEDGE_GRAPH.md          # Visual navigation (copy from templates)
├── platform/                   # Operator patterns (create based on design principles)
├── practices/                  # Cross-cutting concerns (create to fill gaps)
├── domain/                     # Core API concepts (create for architectural context)
├── decisions/                  # Cross-repo ADRs (create for key decisions)
├── workflows/                  # Links to existing dev-guide/guidelines
│   ├── exec-plans/             # Exec-plan templates and guidance (Tier 1)
│   │   ├── README.md           # What/when/how to use exec-plans
│   │   └── template.md         # Feature tracking template
│   ├── enhancement-process.md
│   └── implementing-features.md
└── references/                 # Pointer-based navigation (GitHub links, `oc` commands)
```

**What gets automated:**
- `scripts/create-structure.sh`: Creates base directory tree
- `scripts/populate-templates.sh`: Copies DESIGN_PHILOSOPHY.md and KNOWLEDGE_GRAPH.md

**What you (AI agent) decide:**
- Which platform patterns to document (based on design principles)
- Which domain concepts to document (based on architectural significance)
- Which practices to document (based on gaps in dev-guide)
- Which ADRs to create (based on cross-repo architectural decisions)

**Do NOT create:**
- Files just to meet a count quota
- Duplicates of dev-guide/guidelines content
- Exhaustive lists that get stale (use pointers instead)
- Component-specific content (belongs in tier-2)

**Anti-Staleness Strategy:**
- References use GitHub org links and `oc` commands (not exhaustive lists)
- Domain files show key fields only (not every field)
- Workflows link to directories (not specific files)
- Glossary contains only stable core terms (not release-specific features)

---

## File Naming Conventions (MANDATORY)

**YOU MUST follow these conventions:**

1. **Index files**: Use `index.md` NOT `README.md` (exception: `workflows/exec-plans/README.md`)
   - ✅ `decisions/index.md`, `platform/operator-patterns/index.md`
   - ❌ `decisions/README.md`
   - ✅ `workflows/exec-plans/README.md` (exception: exec-plans uses README for GitHub convention)

2. **ADR naming**: Use `adr-NNNN-` prefix (4 digits with leading zeros)
   - ✅ `decisions/adr-0001-topic-name.md`
   - ❌ `decisions/001-topic-name.md`

3. **Short file names**: Match production conventions
   - ✅ `practices/testing/pyramid.md`
   - ❌ `practices/testing/testing-pyramid.md`

4. **Separate distinct concepts**:
   - ✅ Create separate files for related but distinct APIs
   - ❌ Don't combine multiple APIs in one file

5. **index.md files**: Brief navigation with 1-sentence descriptions per file
   - Example: `## Operator Patterns\n- [status-conditions.md](status-conditions.md) - Available/Progressing/Degraded reporting\n- [controller-runtime.md](controller-runtime.md) - Reconciliation loop patterns`

---

## File Length Targets (Reference Style)

**Target: 100-400 lines per file**

- AGENTS.md: **100-200 lines** (aim for concise navigation)
- Operator patterns: **100-400 lines**
- Practices: **150-400 lines**
- Domain concepts: **100-350 lines**

**Style**: Reference/terse (like man pages), NOT tutorial/verbose. Minimal emojis.

---

## Using Templates

**Templates are in `$SKILL_DIR/templates/`:**

### Available Templates

**Core philosophy** (base content):
- `templates/DESIGN_PHILOSOPHY.md` - Core OpenShift principles (copy/adapt this)
- `templates/KNOWLEDGE_GRAPH.md` - Visual navigation map (copy/adapt this)

**Entry point** (create in repo root):
- `templates/AGENTS.md` - Master navigation file template

**Patterns** (templates for structure):
- `templates/operator-pattern-template.md` - Pattern for operator patterns
- `templates/practice-template.md` - Pattern for practices (index files linking to dev-guide)
- `templates/domain-concept-template.md` - Pattern for domain concepts  
- `templates/adr-template.md` - Pattern for ADRs

**How to use templates:**
1. Read template file to understand structure
2. Create new file following same pattern
3. Adapt content to the specific topic
4. Keep similar length and depth

**Example workflow:**
```bash
# Read template
cat "$SKILL_DIR/templates/operator-patterns/status-conditions.md"

# Create file following same structure
# Keep: Overview, Key Concepts, Implementation, Best Practices, Examples, References
# Adapt: Topic-specific content
```

---

## Guidance: What Documentation to Create

**Principle-Driven Approach**: Create docs that help AI agents apply OpenShift design philosophies, not arbitrary file counts.

### Entry Points (Always Required)
- `AGENTS.md` - Navigation hub in repo root
- `DESIGN_PHILOSOPHY.md` - Core principles
- `KNOWLEDGE_GRAPH.md` - Visual navigation

### Platform Patterns (Create Based on Design Philosophy)

**Ask**: Which patterns help implement the design principles from DESIGN_PHILOSOPHY.md?

**Common examples** (create if they fill a gap):
- `status-conditions.md` - Implements "Observability by Default" principle
- `controller-runtime.md` - Implements "Desired State" principle
- `upgrade-strategies.md` - Implements "Upgrade Safety" principle
- `webhooks.md` - Implements "API-First Design" principle

**Don't create**: Patterns already well-documented in dev-guide or controller-runtime docs.

### Domain Concepts (Create Based on Need)

**Ask**: Which APIs are fundamental to understanding the architecture?

**Common examples** (create if needed for AI context):
- `pod.md`, `service.md`, `crds.md` - Kubernetes fundamentals
- `clusteroperator.md`, `clusterversion.md` - OpenShift platform coordination
- `machine.md`, `machineconfig.md` - Immutable infrastructure

**Don't create**: Every API (use `oc explain` instead). Only document what's architecturally significant.

### Practices (Create to Fill Gaps)

**Ask**: What cross-cutting guidance is missing from dev-guide/guidelines?

**Common examples** (create if gaps exist):
- Testing pyramid, SLI/SLO patterns, threat modeling (STRIDE)
- Link to dev-guide for: enhancement process, git conventions, CI setup

**Don't create**: Duplicates of existing dev-guide content.

### ADRs (Create for Cross-Repo Decisions)

**Ask**: What architectural decisions explain the design philosophy?

**Common examples**: Why etcd, why CVO orchestration, why immutable nodes

**Don't create**: Component-specific decisions or implementation details.

### Workflows (Create AI-Optimized Versions)

**Ask**: What workflows from guidelines/ need AI-parseable versions?

**Common examples**:
- **enhancement-process.md** - Reformat `guidelines/enhancement_template.md` (prose → tables/YAML/checklists)
- **implementing-features.md** - Structured workflow (spec → plan → build → test → review → ship)

**Key**: Same information as guidelines/, but reformatted for AI agents (tables, numbered steps, YAML examples)

**Don't create**: Verbatim copies of guidelines content.

---

## Validation Criteria

**Validation focuses on principles, not counts:**

### Phase 1: Entry Points (Required)
- ✅ AGENTS.md exists at repo root (100-200 lines, navigation-focused)
- ✅ DESIGN_PHILOSOPHY.md exists (defines core principles)
- ✅ KNOWLEDGE_GRAPH.md exists (visual navigation)

### Phase 2: Design Philosophy Coverage (Assess Gaps)
For each principle in DESIGN_PHILOSOPHY.md, check:
- ✅ Is there documentation to help AI agents apply this principle?
- ✅ Are there examples showing the pattern in action?
- ✅ Are cross-cutting concerns (testing, security, reliability) covered?

### Phase 3: Avoid Duplication
- ✅ No content duplicating dev-guide/ or guidelines/ (link instead)
- ✅ No component-specific content (belongs in tier-2)
- ✅ References are pointer-based (GitHub org links, `oc` commands)

### Phase 4: Structural Quality
- ✅ All internal links valid
- ✅ Index files navigate to relevant content
- ✅ Files are reference-style (tables/checklists), not tutorial prose

**If validation fails:**
- Phase 1 failure: Add missing files to meet minimums
- Phase 2 failure: Fix broken links, adjust line counts, remove component-specific content

---

## What NOT to Include (Forbidden Content)

**These belong elsewhere:**

❌ **Component-specific domain concepts**
- Example: Component-specific internal types or controllers
- Note: Platform APIs used across components are OK

❌ **Component architecture**
- Example: Internal component relationships specific to one repository

❌ **Component-specific decisions**
- Example: Technology choices unique to one component

❌ **Component-specific work tracking content**
- Example: component-local sprint plans, team-specific roadmaps
- Note: Tier-1 exec-plan guidance/templates are allowed; only component-local instances belong in tier-2 repos

❌ **Verbatim copies of existing docs**
- Don't copy/paste from guidelines/ or dev-guide/
- Don't duplicate prose-heavy content without reformatting

**✅ What IS allowed:**

✅ **AI-optimized versions of guidelines content** - **REFORMAT, don't duplicate**
- Example: Enhancement process → Reformat `guidelines/enhancement_template.md` (prose) into tables/structured format
- Example: API conventions → Extract key rules into decision tables
- Example: PR workflow → Transform narrative into numbered steps + checklists
- **Key**: Same information, AI-parseable format (tables, YAML, checklists)

✅ **Generic platform patterns** - **CREATE NEW**
- All operators use these (status conditions, controller runtime, etc.)

✅ **Navigation/cross-references** - **LINK**
- Point to authoritative sources in dev-guide/ and guidelines/

✅ **Cross-repo architectural decisions** - **CREATE NEW**
- Affects multiple components (why etcd, why CVO orchestration)

✅ **Platform APIs** - **CREATE NEW**
- Used across multiple components (ClusterOperator, MachineConfig)

---

## AGENTS.md Requirements

**This file is the master entry point. Guidelines:**

### Length
- **100-200 lines** (aim for concise, table-based navigation)
- Use navigation tables, not tutorial explanations

### Mandatory Sections

1. **AI Navigation Section** at TOP (immediately after metadata)
   - DON'T read all docs warning
   - Explicit examples: 
     - "Building operator? → DESIGN_PHILOSOPHY.md → controller-runtime.md → status-conditions.md"
     - "Writing enhancement? → enhancement-process.md → api-evolution.md → pyramid.md"
   - Reference to KNOWLEDGE_GRAPH.md
   - Concrete navigation steps (4-5 docs per task)

2. **Quick Navigation by Role** (table format)
3. **Core Platform Concepts** (table format)
4. **Standard Operator Patterns** (table format)
5. **Engineering Practices** (table format)
6. **Workflows** (link to workflows/ - enhancement process, feature implementation)
7. **Component Repository Index** (link to references/repo-index.md)
8. **Cross-Repo Architectural Decisions** (link to decisions/)
9. **Relationship to Other Documentation** (dev-guide, enhancements, guidelines)
10. **How to Use This Documentation** (for AI agents and humans)

### Style
- ✅ Navigation-focused with tables
- ✅ Links to detailed docs
- ❌ Tutorial-style explanations
- ❌ Verbose descriptions

### Validation
```bash
LINE_COUNT=$(wc -l < AGENTS.md)
if [ $LINE_COUNT -gt 200 ] || [ $LINE_COUNT -lt 100 ]; then
    echo "⚠️  WARNING: File is $LINE_COUNT lines (target: 100-200)"
fi
```

---

## Script Execution Reference

### 1. Discovery Script
```bash
bash "$SKILL_DIR/scripts/discover.sh" "$REPO_PATH"
```
**Purpose:** Check if ai-docs/ exists, learn naming conventions, identify gaps

### 2. Structure Creation Script
```bash
bash "$SKILL_DIR/scripts/create-structure.sh" "$REPO_PATH"
```
**Purpose:** Create empty directory tree (only if ai-docs/ doesn't exist)

### 3. Populate Templates Script
```bash
bash "$SKILL_DIR/scripts/populate-templates.sh" "$REPO_PATH"
```
**Purpose:** Copy DESIGN_PHILOSOPHY.md and KNOWLEDGE_GRAPH.md (only if ai-docs/ doesn't exist)

### 4. Fill Gaps Script
```bash
bash "$SKILL_DIR/scripts/fill-gaps.sh" "$REPO_PATH"
```
**Purpose:** Identify missing recommended files (only if ai-docs/ already exists)

### 5. Validation Script
```bash
bash "$SKILL_DIR/scripts/validate.sh" "$REPO_PATH"
```
**Purpose:** Comprehensive validation (content minimums + structural checks)

---

## Execution Flow

```text
User invokes: /platform-docs

↓

Phase 1: Setup
  → Find skill directory
  → Run discovery script
  → Create structure (if new) OR identify gaps (if exists)
  → Copy base templates (DESIGN_PHILOSOPHY, KNOWLEDGE_GRAPH)

↓

Phase 2: Create AGENTS.md
  → Use template reference
  → Validate 150-170 lines
  
↓

Phase 3-7: Create Documentation
  → Platform patterns (use templates/)
  → Practices (use templates/)
  → Domain concepts (use templates/)
  → ADRs, workflows, references

↓

Phase 8: Validation
  → Run validation script
  → Fix issues if validation fails

↓

Phase 9: Report
  → Summary of created files
  → Validation status
  → Git commit command
```

---

## Common Mistakes to Avoid

### ❌ Mistake 1: Skipping Script Execution
**Wrong:** Manually creating directories with `mkdir -p ai-docs/...`
**Right:** Run `create-structure.sh` script

### ❌ Mistake 2: AGENTS.md Too Long
**Wrong:** 250+ lines with verbose explanations
**Right:** 100-200 lines with navigation tables

### ❌ Mistake 3: Duplicating Existing Docs
**Wrong:** Verbatim-copying `guidelines/enhancement_template.md` into `workflows/enhancement-process.md`
**Right:** Create `workflows/enhancement-process.md` as an AI-optimized reformatted guide (prose → tables/checklists/YAML), and link the authoritative source from `workflows/index.md`

### ❌ Mistake 4: Including Component-Specific Content
**Wrong:** Creating files for component-specific internals
**Right:** Keep platform-level only (public APIs, cross-component patterns)

### ❌ Mistake 5: Skipping Validation
**Wrong:** Not running `validate.sh` at the end
**Right:** Always run validation and fix issues

### ❌ Mistake 6: Not Using Templates
**Wrong:** Creating files from scratch without looking at templates
**Right:** Read template, understand structure, adapt to topic

### ❌ Mistake 7: Wrong File Naming
**Wrong:** `decisions/README.md`, `adr-1-topic.md`, `testing-pyramid.md`
**Right:** `decisions/index.md`, `adr-0001-topic.md`, `pyramid.md`

---

## Arguments

```bash
/platform-docs [--path <repository-path>]
```

**Arguments:**
- `--path <repository-path>`: Path to target repository (default: current directory)
- No args: Create documentation in current directory

---

## When to Use This Skill

**Use when:**
- Creating AI-optimized documentation structure
- Setting up the ecosystem documentation hub
- The `ai-docs/` directory doesn't exist OR needs to be completed

**Do NOT use when:**
- The `ai-docs/` directory is already complete and up-to-date

---

## Success Criteria

**Documentation is complete when:**

✅ Entry points exist (AGENTS.md, DESIGN_PHILOSOPHY.md, KNOWLEDGE_GRAPH.md)
✅ AGENTS.md is 100-200 lines (navigation-focused)
✅ Each design principle has supporting documentation (patterns, examples)
✅ No duplication of dev-guide/guidelines content (links instead)
✅ No component-specific content (belongs in tier-2)
✅ References are pointer-based (GitHub org links, `oc` commands, not exhaustive lists)
✅ All files are reference-style (tables/checklists, not tutorial prose)
✅ Internal links are valid
✅ Validation script passes (structural checks)

**Not success criteria:**
❌ File count targets (create what's needed, not to fill quotas)
❌ Covering every API (only architecturally significant ones)
❌ Duplicating existing documentation (link instead)

---

## Final Report Template

```text
✅ AI-Optimized Documentation Created

Location: ai-docs/

Entry Points:
  ✅ AGENTS.md: XXX lines (target: 100-200)
  ✅ DESIGN_PHILOSOPHY.md
  ✅ KNOWLEDGE_GRAPH.md

Documentation Created:
  Platform patterns: [X] files
  Domain concepts: [X] files  
  Practices: [X] files
  ADRs: [X] files
  References: [X] files

Validation:
  ✅ Phase 1: Entry points exist
  ✅ Phase 2: Design philosophy coverage adequate
  ✅ Phase 3: No duplication detected
  ✅ Phase 4: Structural quality checks passed

Next Steps:
  1. Review documentation for accuracy
  2. Create git commit:
     
     git add ai-docs/
     git commit -m "Add AI-optimized ecosystem documentation
     
     Creates ecosystem hub for all OpenShift components.
     
     Structure:
     - Platform patterns (operator patterns, OpenShift specifics)
     - Engineering practices (testing, security, reliability)
     - Domain concepts (K8s and OpenShift fundamentals)
     - Cross-repo ADRs
     - Repository index for discovery
     
     Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

**Remember: Complete ALL checklist items. Do NOT skip phases. Use scripts and templates.**
