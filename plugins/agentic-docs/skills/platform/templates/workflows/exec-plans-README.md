# Execution Plans (Exec-Plans)

Track active feature implementations across component repositories.

## What are Exec-Plans?

Exec-plans are **ephemeral** feature tracking documents that bridge enhancements (high-level design) and implementation (PRs and code). They help:

- Track multi-PR features
- Coordinate work across weeks/months
- Capture implementation decisions during development

**Important**: Exec-plans are temporary. When complete, extract permanent knowledge into proper docs (ADRs, architecture docs) and delete the exec-plan.

## When to Create an Exec-Plan

**DO create** an exec-plan when:
- ✅ Implementing a new feature from an enhancement
- ✅ Major refactoring or architectural change
- ✅ Cross-component feature (your component's portion)
- ✅ Multi-week engineering effort (3+ weeks)
- ✅ Feature requires coordination across multiple PRs

**DON'T create** an exec-plan for:
- ❌ Bug fixes (unless major architectural fix)
- ❌ Minor refactoring
- ❌ Documentation-only changes
- ❌ Single-PR features
- ❌ Routine maintenance

## Usage

### Starting a New Feature

```bash
# In your component repo: component-repo/ai-docs/exec-plans/

# Copy template from Tier 1
curl -O https://raw.githubusercontent.com/openshift/enhancements/master/ai-docs/workflows/exec-plans/template.md

# Move to active
mv template.md active/feature-name.md

# Fill in the template
# - Summary: What you're building
# - Goals/Non-Goals: Scope boundaries
# - Implementation Plan: Phases with tasks and PRs
# - Testing Strategy: How you'll test it
# - Dependencies: What you need from other teams
# - Risks: What could go wrong
```

### During Implementation

Update the exec-plan as you work:
- Check off completed tasks: `- [x] Task completed`
- Link PRs: `- [x] PR #123 - Add controller logic`
- Document decisions in Notes section
- Update timelines if they slip

### When Implementation Completes

**Extract permanent knowledge**, then delete the exec-plan:

```bash
# 1. Review the exec-plan for permanent knowledge
cat active/feature-name.md

# 2. Extract to permanent docs:

# If architectural decision was made:
cp ai-docs/decisions/adr-template.md ai-docs/decisions/adr-NNNN-decision-name.md
# Document the decision in the ADR

# If architecture changed:
# Update ai-docs/architecture/components.md with new structure

# If new CRD was added:
# Already documented in ai-docs/domain/crd-name.md

# 3. Delete the exec-plan (it's in git history if needed)
git rm active/feature-name.md
git commit -m "Complete feature-name implementation

Architectural decisions documented in adr-NNNN-*.md
Architecture changes in architecture/components.md
"
```

**Why delete?**
- Exec-plans are ephemeral tracking, not permanent docs
- Git history preserves it if needed: `git log --all -- ai-docs/exec-plans/active/feature-name.md`
- Permanent knowledge belongs in ADRs and architecture docs

## Relationship to Other Docs

**Enhancement (Tier 1)**:
- Where: `openshift/enhancements`
- What: High-level design, API, user stories
- When: Before implementation starts
- Scope: Platform-wide, cross-repo

**Exec-Plan (Tier 2)**:
- Where: Component repository (`ai-docs/exec-plans/active/`)
- What: Implementation tracking, PR coordination, decisions
- When: During implementation
- Scope: Component-specific

**PRs**:
- Where: GitHub pull requests
- What: Actual code changes
- When: Implementation

**Flow**: Enhancement → Exec-Plan → PRs → Code

## Completion Decision Matrix

When feature is complete, ask:

| Question | Yes | Action |
|----------|-----|--------|
| Did we make an architectural decision? | ✅ | Create ADR in `ai-docs/decisions/adr-NNNN-*.md` |
| Did component architecture change? | ✅ | Update `ai-docs/architecture/components.md` |
| Did we add a new CRD? | ✅ | Already in `ai-docs/domain/*.md` |
| Did we add new components/controllers? | ✅ | Update `ai-docs/architecture/components.md` |
| Just implementation (no architecture)? | ✅ | Delete exec-plan (it's in git history) |

**Then**: Delete the exec-plan. It's ephemeral tracking, not permanent documentation.

## Example Workflow

### Example: Custom Kernels Feature

1. **New Enhancement Approved**
   - Enhancement: "Add support for custom kernels"
   - Create: `ai-docs/exec-plans/active/custom-kernels.md`

2. **During Development** (Week 1-4)
   - Update exec-plan with PRs
   - Document decisions in Notes: "decided to use kernel args instead of kernel modules"
   - Track dependencies: "waiting for CVO changes"

3. **Feature Complete**
   
   **Extract permanent knowledge**:
   ```bash
   # Architectural decision made during development
   vim ai-docs/decisions/adr-0004-kernel-args-vs-modules.md
   # Document: Why kernel args? Performance, compatibility, rollback
   
   # Architecture changed (new controller added)
   vim ai-docs/architecture/components.md
   # Add: KernelController - manages kernel arguments via MachineConfig
   
   # New CRD added
   vim ai-docs/domain/kernelconfig.md
   # Already documented during development
   
   # Delete ephemeral exec-plan
   git rm ai-docs/exec-plans/active/custom-kernels.md
   git commit -m "Complete custom kernels feature
   
   Architectural decision in adr-0004-kernel-args-vs-modules.md
   Architecture updated in components.md
   KernelConfig CRD documented in domain/kernelconfig.md
   "
   ```

4. **Result**
   - ✅ Permanent knowledge in proper docs (ADR, architecture, domain)
   - ✅ Exec-plan deleted (ephemeral tracking done)
   - ✅ Git history preserves exec-plan if needed for historical context

## Tips

**Keep it lean**: Exec-plans are not requirements docs. Link to the enhancement for design details.

**Update regularly**: Keep the exec-plan current as you implement. It's most valuable when actively maintained.

**Document decisions in Notes**: Capture implementation decisions during development. When complete, move architectural decisions to ADRs.

**Extract, then delete**: When done, extract permanent knowledge into proper docs, then delete the exec-plan. Git history preserves it if needed.

## See Also

- [Enhancement Process](../enhancement-process.md)
- [Exec-Plan Template](./template.md)
- [Component Documentation Guide](https://github.com/openshift/ai-helpers/tree/master/plugins/agentic-docs)
