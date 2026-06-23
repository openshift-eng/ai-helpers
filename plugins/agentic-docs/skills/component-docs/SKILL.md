---
name: component-docs
description: Create lean component documentation for OpenShift repositories
trigger: explicit
model: sonnet
---

# Component Documentation Creator

Creates lean component agentic documentation for OpenShift component repositories.

**Philosophy**: Component docs contain ONLY component-specific knowledge. Generic platform patterns live in platform (openshift/enhancements/ai-docs/).

## Two-Tier Architecture

### Platform: Platform Hub (openshift/enhancements/ai-docs/)
**Contains**: Operator patterns, testing practices, security guidelines, Kubernetes/OpenShift fundamentals, cross-repo ADRs

### Component: Component Repos (LEAN)
**Contains**: Component-specific CRDs, component architecture, component ADRs, exec-plans

**Decision Rule**: "Would another repo need to duplicate this?"
- YES → Platform (platform)
- NO → Component (component)

## What Gets Created

```text
component-repo/
├── AGENTS.md                      # Master entry point (80-100 lines)
└── ai-docs/
    ├── domain/                    # Component CRDs ONLY
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
```text

## What NOT to Include (lives in Platform)

❌ Generic operator patterns (controller-runtime, status conditions)  
❌ Testing practices (test pyramid, E2E framework)  
❌ Security practices (STRIDE, RBAC guidelines)  
❌ Reliability practices (SLO framework)  
❌ Kubernetes fundamentals (Pod, Node, Service)  
❌ Cross-repo ADRs (etcd, CVO orchestration, immutable nodes)

## Execution Workflow

### Phase 1: Setup
- [ ] Find skill directory: `SKILL_DIR=$(find ~/.claude/plugins/cache -path "*/component-docs" -type d | head -1)`
- [ ] Determine repo path: `REPO_PATH="${provided_path:-$PWD}"`
- [ ] Detect component name from repo (e.g., machine-config-operator → MCO)
- [ ] Run `bash "$SKILL_DIR/scripts/create-structure.sh" "$REPO_PATH"`

### Phase 2: Create AGENTS.md (80-100 lines)
- [ ] Create master entry point at repo root
- [ ] Include compressed index of component docs
- [ ] Add retrieval-first instruction
- [ ] Add Platform ecosystem hub links
- [ ] Add component quick navigation
- [ ] Validate line count: `wc -l AGENTS.md` (target: 80-100)

### Phase 3: Component Domain Concepts
- [ ] Identify component-specific CRDs (via `oc api-resources`)
- [ ] Create domain/*.md for each CRD
- [ ] Document CRD purpose, key fields, lifecycle
- [ ] Use `templates/domain-concept-template.md` for structure
- [ ] Focus on component-specific behavior, link to Platform for generic patterns

### Phase 4: Enhancement Proposals & Design Docs
- [ ] Create references/enhancements.md to catalog all design documentation
- [ ] Search openshift/enhancements repo for component-specific proposals:
  - Check `https://github.com/openshift/enhancements/tree/master/enhancements/{component-area}/`
  - Example: MCO → `enhancements/machine-config/*.md`
  - List all enhancement proposals with links to GitHub
- [ ] Search component repo for local design docs:
  - Check docs/, design/, enhancements/ directories
  - Check for files with "design", "proposal", "enhancement" in name
  - Include links to local design docs
- [ ] Categorize by status: implemented/provisional/rejected (from enhancement metadata)
- [ ] Use `templates/enhancements-template.md` for structure
- [ ] Keep concise: Just title, status, link (no summaries - enhancement is the source of truth)

### Phase 5: Component Architecture
- [ ] Create architecture/components.md
- [ ] Document component structure (pkg/, cmd/, controllers/)
- [ ] Explain component relationships and data flow
- [ ] Keep lean (100-200 lines)

### Phase 6: Component ADRs
- [ ] Create decisions/adr-template.md (copy from templates)
- [ ] Create 2-3 component-specific ADRs
- [ ] Example: rpm-ostree choice, Ignition format, config drift detection
- [ ] NO cross-repo ADRs (those go in Platform)

### Phase 7: Exec-Plans
- [ ] Create exec-plans/active/ directory (for component-specific exec-plans)
- [ ] Create exec-plans/README.md with pointer to Platform guidance
- [ ] Link to Platform exec-plans guidance
- [ ] NO templates or detailed guidance (lives in Platform)

### Phase 8: Ecosystem References
- [ ] Create references/ecosystem.md
- [ ] Link to Platform operator patterns
- [ ] Link to Platform testing practices
- [ ] Link to Platform security practices
- [ ] Link to Platform Kubernetes/OpenShift fundamentals
- [ ] Link to Platform cross-repo ADRs

### Phase 9: Development & Testing Docs
- [ ] Create [COMPONENT]_DEVELOPMENT.md using `templates/DEVELOPMENT-template.md`
- [ ] Create [COMPONENT]_TESTING.md using `templates/TESTING-template.md`
- [ ] Link to Platform for generic practices
- [ ] Document ONLY component-specific details:
  - Build instructions (make targets, go commands)
  - Repository structure (cmd/, pkg/ organization)
  - Development workflow (local dev, on-cluster testing)
  - Test suites (unit, integration, E2E locations and commands)
  - Component-specific test patterns
  - Common development tasks (add CRD, add controller, update deps)

### Phase 10: Validation
- [ ] Run `bash "$SKILL_DIR/scripts/validate.sh" "$REPO_PATH"` (includes link validation)
- [ ] Verify AGENTS.md ≤100 lines
- [ ] Verify no generic duplication
- [ ] Verify ecosystem.md exists with Platform links
- [ ] Verify all external links (HTTP/HTTPS) are valid
- [ ] Verify all internal links (relative paths) are valid
- [ ] Fix any broken links found

**Link Validation**:
- Automatically checks all HTTP/HTTPS links (with timeout and user agent)
- Validates internal/relative links (file existence)
- Flags known Platform planned links as "KNOWN BROKEN"
- Use `VERBOSE=true bash "$SKILL_DIR/scripts/validate.sh" "$REPO_PATH"` to see all links
- Use `bash "$SKILL_DIR/scripts/validate.sh" "$REPO_PATH" false` to skip link validation

## AGENTS.md Requirements

**Length**: 80-100 lines (strict limit)

**Required Sections**:
1. Component metadata (name, repository)
2. Platform reference (link to ecosystem hub)
3. Component purpose (what is it?)
4. Core components (brief)
5. Documentation structure (compressed)
6. Knowledge graph (visual)
7. Platform ecosystem links (operator patterns, testing, security, etc.)

**Format**: Compressed, table-based, links not prose

**Example**:
```markdown
# Component Name - Agentic Documentation

**Component**: Machine Config Operator  
**Repository**: openshift/machine-config-operator  

> **Generic Platform Patterns**: See Platform documentation (openshift/enhancements/ai-docs/)

## What is MCO?

Manages OS configuration for OpenShift nodes. Controls everything between kernel and kubelet.

## Core Components

- **MCD**: DaemonSet applying configs | **MCC**: Coordinates upgrades | **MCS**: Serves Ignition

## Documentation Structure

```text
ai-docs/
├── domain/          # CRDs: MachineConfig, MachineConfigPool
├── architecture/    # Component internals
├── decisions/       # Component ADRs
└── exec-plans/      # Feature planning
```text

## Platform Links

**Patterns**: Operator | Testing | Security (see Platform docs)

## Component-Specific Domain Concepts

**Template**: `templates/domain-concept-template.md`

**Structure**:
- API Group / Kind / Scope
- Purpose (component-specific behavior)
- Key fields (most important only)
- Lifecycle
- Examples (component-specific usage)

**Length**: 100-200 lines per concept

**Example**: MachineConfig (MCO-specific)
- Ignition config structure
- Rendered config merging
- OS update mechanism
- Ownership model (system vs user)

## Component Architecture

**File**: `architecture/components.md`

**Contents**:
- Component structure (pkg/, cmd/, controllers/)
- Component relationships
- Data flow
- Key responsibilities

**Length**: 100-200 lines

## Component ADRs

**Format**: `decisions/adr-NNNN-title.md`

**Example Component ADRs**:
- Why rpm-ostree for OS updates (MCO)
- Why Ignition format for config (MCO)
- Why etcd for platform state (Platform, NOT component)

**Template**: `decisions/adr-template.md`

## Exec-Plans

**Purpose**: Track active feature implementation (bridges enhancements and PRs)

**Location**: Component repo (`ai-docs/exec-plans/active/`)

**Guidance**: See Platform documentation for exec-plans templates and workflows

**Component repo structure**:
```text
ai-docs/exec-plans/
├── active/           # Component-specific exec-plans go here
└── README.md         # Pointer to Platform guidance
```text

**What component-docs creates**:
- `active/` directory (empty, ready for exec-plans)
- `README.md` with pointer to Platform exec-plans guidance

**Note**: Exec-plans are deleted after completion; knowledge is extracted into ADRs or architecture docs

## Enhancement Proposals & Design Docs

**File**: `references/enhancements.md`

**Purpose**: Index all design documentation for this component

**Sources to search**:
1. openshift/enhancements repo: `https://github.com/openshift/enhancements/tree/master/enhancements/{component-area}/`
2. Component repo: docs/, design/, enhancements/ directories

**Format**: Simple catalog with title, status, and link (no summaries - the enhancement is the source of truth)

**Example**:
```markdown
# Enhancement Proposals & Design Docs

## openshift/enhancements
- [On-Cluster Layering](https://github.com/openshift/enhancements/blob/master/enhancements/machine-config/on-cluster-layering.md) - Implemented
- [Admin Node Disruption Policy](https://github.com/openshift/enhancements/blob/master/enhancements/machine-config/admin-defined-node-disruption-policy.md) - Implemented

## Local Design Docs
- [Config Drift Detection](../docs/design/config-drift.md)
```

**Distinction from ADRs**: Enhancement proposals are feature designs (often cross-component), ADRs are component architectural decisions

## Ecosystem References

**File**: `references/ecosystem.md`

**Links to Platform**:
- Operator patterns (controller-runtime, status conditions, webhooks, finalizers, RBAC)
- Testing practices (pyramid, E2E framework)
- Security practices (STRIDE, RBAC, secrets)
- Reliability practices (SLO, observability, degraded states)
- Kubernetes fundamentals (Pod, Node, DaemonSet)
- OpenShift fundamentals (ClusterOperator, release image)
- Cross-repo ADRs (etcd, CVO orchestration, immutable nodes)

**Purpose**: Single source of truth for Platform links

## Development & Testing Docs

**Files**: `[COMPONENT]_DEVELOPMENT.md`, `[COMPONENT]_TESTING.md`

**Templates**: Use `templates/DEVELOPMENT-template.md` and `templates/TESTING-template.md`

### DEVELOPMENT.md Contents

**Required sections** (component-specific ONLY):

1. **Quick Start**
   - Prerequisites (Go version, cluster access, tools)
   - Build commands (`make [target]`, `go build`)
   - Output locations

2. **Repository Structure**
   - cmd/ organization
   - pkg/ organization
   - manifests/ structure
   - test/ organization

3. **Development Workflow**
   - Local development (build binaries, run tests)
   - On-cluster testing (replace pod, run locally against cluster)
   - Debugging (logs, exec, delve)

4. **Code Organization**
   - Where controllers live
   - Where domain logic lives
   - Package structure

5. **Common Tasks**
   - Add new CRD
   - Add new controller
   - Update dependencies
   - Build & release process

6. **Component-Specific Notes**
   - Special build flags
   - Environment variables
   - Local development quirks

**Link to Platform for**: Generic Go standards, controller-runtime patterns, CI/CD workflows

### TESTING.md Contents

**Required sections** (component-specific ONLY):

1. **Test Organization**
   - Test pyramid visualization
   - Where tests live (unit, integration, E2E)

2. **Unit Tests**
   - Location (pkg/*/\*_test.go)
   - Running commands (`make test-unit`, `go test`)
   - Component-specific test patterns
   - Coverage commands

3. **Integration Tests**
   - Location (test/integration/ or with build tags)
   - Running commands
   - Component-specific integration scenarios

4. **E2E Tests**
   - Location (test/e2e/)
   - Running commands
   - Component-specific E2E scenarios
   - Test organization

5. **Test Coverage**
   - Current coverage
   - Coverage targets
   - Known gaps

6. **Debugging Tests**
   - Unit test failures
   - E2E test failures
   - Must-gather commands

7. **Component-Specific Test Notes**
   - Special test setup
   - Known flaky tests
   - Test environment requirements

**Link to Platform for**: Test pyramid philosophy (60/30/10), E2E framework patterns, mock vs real strategies

### Example from MCO

**DEVELOPMENT.md** includes:
- Build commands: `make machine-config-daemon`, `make machine-config-controller`
- Repository structure: cmd/, pkg/, templates/, manifests/
- Development workflow: Local build, on-cluster testing
- Common tasks: Add CRD, update deps

**TESTING.md** includes:
- Unit test patterns: Controller tests, Ignition tests
- Integration tests: Node update scenarios
- E2E tests: OS update tests, config drift tests
- Test commands: `make test-unit`, `make test-e2e`

**Both files** are ~100-200 lines, lean, component-specific only

## Validation Criteria

✅ **AGENTS.md**:
- At repo root (not in ai-docs/)
- 80-100 lines
- Compressed index format
- Retrieval-first instruction
- Platform ecosystem links section

✅ **No duplication**:
- No testing pyramid explanations
- No controller-runtime patterns
- No status condition semantics
- No STRIDE threat model
- No SLO framework

✅ **References**:
- references/ecosystem.md exists with Platform links
- references/enhancements.md exists with design docs catalog
- Enhancement proposals from openshift/enhancements discovered
- Local design docs discovered and linked

✅ **Component-specific only**:
- Domain concepts are component CRDs
- ADRs are component-specific
- Architecture is component internals

✅ **Link validation**:
- All external links (HTTP/HTTPS) return 200 OK
- All internal links (relative paths) resolve to existing files/directories
- No broken links except known Platform planned links
- Links to upstream documentation are valid and current

## Anti-Patterns

### ❌ DON'T duplicate Platform content

**Wrong**:
```markdown
# TESTING.md (187 lines, 60% generic)

## Testing Pyramid
[100 lines explaining pyramid]

## Component Tests
[37 lines component-specific]
```text

**Right**:
```markdown
# COMPONENT_TESTING.md (90 lines, 100% component-specific)

> Testing practices: See Platform docs

## Component Test Suites
[90 lines component-specific]
```text

### ❌ DON'T explain generic patterns

**Wrong**: Explaining controller-runtime in component docs  
**Right**: Link to Platform, document component-specific usage

### ❌ DON'T create cross-repo ADRs

**Wrong**: ADR about etcd in component repo  
**Right**: ADR about etcd in Platform

## Metrics

**Expected structure**:
- AGENTS.md: 80-100 lines (vs 150+ for single-tier)
- Total docs: ~2,500 lines (vs ~6,000 single-tier)
- Generic duplication: 0 lines (vs ~2,400 single-tier)

**Benefits**:
- 58% smaller than single-tier
- Zero duplication across ecosystem
- Pattern updates: 1 Platform PR (not 60+ component PRs)

## Prerequisites

**Before running**:
1. ✅ Platform exists at openshift/enhancements/ai-docs/
2. ✅ Repository is OpenShift component
3. ✅ You understand two-tier architecture
4. ✅ Platform documentation exists at openshift/enhancements/ai-docs/

## Arguments

```bash
/component-docs [--path <repository-path>]
```text

**Arguments**:
- `--path <repository-path>`: Path to component repository (default: current directory)
- No args: Create documentation in current directory

## Success Output

```text
✅ Component Documentation Created

Component: machine-config-operator
Repository: /path/to/repo

Structure:
  ✅ AGENTS.md (root): 87 lines (target: 80-100)
  ✅ Domain concepts: 4 files (component CRDs only)
  ✅ Architecture: 1 file (components.md)
  ✅ Component ADRs: 3 files
  ✅ Exec-plans: README.md, active/
  ✅ References: ecosystem.md, enhancements.md
  ✅ Development: COMPONENT_DEVELOPMENT.md
  ✅ Testing: COMPONENT_TESTING.md

Validation:
  ✅ AGENTS.md at root (80-100 lines)
  ✅ No generic duplication
  ✅ Platform links present
  ✅ Component-specific content only

References:
  - Ecosystem hub: openshift/enhancements/ai-docs
  - Enhancement proposals: Catalogued from openshift/enhancements + local docs
  - Platform links: Operator patterns, testing, security, Kubernetes/OpenShift fundamentals

Next Steps:
  1. Populate domain/*.md with component CRDs
  2. Document architecture in components.md
  3. Create component-specific ADRs
  4. Use exec-plans/ for active features
```text

## Example: Machine Config Operator

**Created files**:
- AGENTS.md (87 lines)
- ai-docs/domain/machineconfig.md
- ai-docs/domain/machineconfigpool.md
- ai-docs/domain/kubeletconfig.md
- ai-docs/domain/containerruntimeconfig.md
- ai-docs/architecture/components.md
- ai-docs/decisions/adr-0001-rpm-ostree-updates.md
- ai-docs/decisions/adr-0002-ignition-format.md
- ai-docs/decisions/adr-0003-config-drift-detection.md
- ai-docs/references/ecosystem.md
- ai-docs/exec-plans/README.md
- ai-docs/MCO_DEVELOPMENT.md
- ai-docs/MCO_TESTING.md

**Total**: ~2,500 lines (component-specific only)

## See Also

- `/update-platform-docs` - Update Platform documentation
- Platform Documentation (openshift/enhancements/ai-docs/)
- [MCO Example](https://github.com/openshift/machine-config-operator/tree/master/ai-docs)
