---
name: update-platform-docs
description: Update existing platform documentation with automatic gap detection in openshift/enhancements
trigger: explicit
model: sonnet
---

# Platform Documentation Updater

Incrementally update existing AI-optimized platform documentation in `openshift/enhancements/ai-docs/` without regenerating everything.

**Features:**
- **Automatic gap detection** - Scans ai-docs/ and reports missing files
- **Targeted updates** - Add specific content without full regeneration
- **Smart navigation** - Auto-updates index files and AGENTS.md
- **Validation** - Ensures quality and conventions

**Use when:**
- Discovering what's missing from documentation
- Adding new content to existing documentation
- Adding new sections (e.g., workflows/exec-plans/)
- Updating AGENTS.md with new links
- Adding new domain concepts, patterns, or ADRs
- Fixing or enhancing existing files

**Don't use when:**
- ai-docs/ doesn't exist yet (use `/platform-docs` instead)
- You want to completely regenerate all docs

## Execution Workflow

### Phase 1: Discovery & Gap Detection
- [ ] Find skill directory: `SKILL_DIR=$(find ~/.claude/plugins/cache -path "*/update-platform-docs" -type d | head -1)`
- [ ] Determine repo path: `REPO_PATH="${provided_path:-$PWD}"`
- [ ] Run discovery: `bash "$SKILL_DIR/scripts/discover.sh" "$REPO_PATH"`
- [ ] Verify ai-docs/ exists (if not, suggest `/platform-docs`)
- [ ] Run gap detection: `bash "$SKILL_DIR/scripts/gap-detection.sh" "$REPO_PATH"`
- [ ] Show gap detection results to user
- [ ] Ask user: Fill detected gaps OR specify custom addition?

### Phase 2: Perform Updates
Based on user request, perform ONE OR MORE of:

#### Add New Platform Pattern
- [ ] Create new file in `platform/operator-patterns/`
- [ ] Update `platform/operator-patterns/index.md`
- [ ] Update `AGENTS.md` navigation if needed
- [ ] Use `templates/operator-pattern-template.md` for structure

#### Add New Domain Concept
- [ ] Create new file in `domain/kubernetes/` or `domain/openshift/`
- [ ] Update corresponding `domain/*/index.md`
- [ ] Update `AGENTS.md` navigation if needed
- [ ] Use `templates/domain-concept-template.md` for structure

#### Add New Practice
- [ ] Create new file in `practices/*/`
- [ ] Update corresponding `practices/*/index.md`
- [ ] Update `AGENTS.md` navigation if needed
- [ ] Use `templates/practice-template.md` for structure

#### Add New ADR
- [ ] Create new file in `decisions/adr-NNNN-*.md`
- [ ] Update `decisions/index.md`
- [ ] Update `AGENTS.md` navigation if needed
- [ ] Use `templates/adr-template.md` for structure

#### Add New Workflow Section
- [ ] Create new directory in `workflows/` (e.g., `exec-plans/`)
- [ ] Create files in new section
- [ ] Update `workflows/index.md`
- [ ] Update `AGENTS.md` navigation if needed

#### Update AGENTS.md
- [ ] Read current `AGENTS.md`
- [ ] Add new navigation links
- [ ] Verify line count stays 100-200 lines
- [ ] Maintain compressed table format

#### Update Existing Files
- [ ] Read current file
- [ ] Make targeted updates (add section, update content)
- [ ] Preserve existing structure
- [ ] Maintain file length targets

### Phase 3: Validation
- [ ] Run validation: `bash "$SKILL_DIR/scripts/validate.sh" "$REPO_PATH"`
- [ ] Verify new files follow conventions
- [ ] Verify AGENTS.md 100-200 lines
- [ ] Verify internal links work

### Phase 4: Report
- [ ] List files created
- [ ] List files updated
- [ ] Show validation status
- [ ] Suggest git commit command

## Update Scenarios

### Scenario 1: Add New Operator Pattern

**User request:** "Add RBAC patterns to operator patterns"

**Actions:**
1. Create `platform/operator-patterns/rbac.md` using pattern template
2. Add entry to `platform/operator-patterns/index.md`
3. Add link to `AGENTS.md` under "Standard Operator Patterns"
4. Validate

### Scenario 2: Add New Workflow Section

**User request:** "Add exec-plans guidance to workflows"

**Actions:**
1. Create `workflows/exec-plans/` directory
2. Create `workflows/exec-plans/README.md` from template
3. Create `workflows/exec-plans/template.md` from template
4. Update `workflows/index.md` with new section
5. Add link to `AGENTS.md` under "Workflows"
6. Validate

### Scenario 3: Update AGENTS.md

**User request:** "Add link to new ADR in AGENTS.md"

**Actions:**
1. Read current `AGENTS.md`
2. Find "Cross-Repo Architectural Decisions" section
3. Add new ADR link in table format
4. Verify line count ≤200
5. Validate

### Scenario 4: Add Multiple Related Files

**User request:** "Add security practices section with STRIDE and secrets handling"

**Actions:**
1. Create `practices/security/threat-modeling.md`
2. Create `practices/security/secrets.md`
3. Update `practices/security/index.md`
4. Add links to `AGENTS.md` under "Engineering Practices"
5. Validate

## File Naming Conventions

**MUST follow these conventions:**

1. **Index files**: Use `index.md` NOT `README.md` (exception: `exec-plans/README.md`)
2. **ADR naming**: Use `adr-NNNN-` prefix (4 digits with leading zeros)
3. **Short file names**: Match production conventions
4. **Separate distinct concepts**: Don't combine multiple topics

## Update Guidelines

### Adding Content
- Use appropriate template from `templates/`
- Follow existing file structure and style
- Maintain reference/terse style (tables, checklists)
- Keep files within length targets (100-400 lines)

### Updating AGENTS.md
- Always read current content first
- Add new links in appropriate sections
- Use table format for consistency
- Keep compressed (navigation, not prose)
- Verify line count ≤200 after update

### Updating Index Files
- Add one-line description per new file
- Maintain alphabetical or logical order
- Use consistent format: `- [filename.md](filename.md) - Brief description`

### Preserving Structure
- Don't reorganize existing content unless explicitly requested
- Match existing conventions and patterns
- Maintain consistency with existing files

## Validation

After updates, verify:

✅ New files use correct naming conventions
✅ Index files updated with new entries
✅ AGENTS.md updated if needed (and 100-200 lines)
✅ Internal links work
✅ Files follow reference style (tables, checklists)
✅ No duplication of dev-guide/guidelines content

## Gap Detection Mode

**Automatic workflow:**

1. **Scan** existing ai-docs/ structure
2. **Compare** against expected files checklist
3. **Report** what's missing (by category)
4. **Ask** user which gaps to fill

**Gap categories scanned:**
- Platform Patterns (controller-runtime, status-conditions, webhooks, etc.)
- Domain Concepts - Kubernetes (pod, service, crds)
- Domain Concepts - OpenShift (clusteroperator, clusterversion)
- Practices (testing, security, reliability, development)
- Workflows (enhancement-process, implementing-features, exec-plans)
- Decisions (adr-template, index)
- References (repo-index, glossary, api-reference)
- Core Files (DESIGN_PHILOSOPHY, KNOWLEDGE_GRAPH)
- Navigation (AGENTS.md)

**User chooses:**
- Fill all detected gaps
- Fill specific gaps (select from list)
- Skip gaps, specify custom addition

## Examples

### Example 1: Gap Detection Workflow

```bash
/update-platform-docs

# Automatic gap detection runs:
🔍 Scanning ai-docs/ for gaps...

## Platform Patterns
Missing:
  - platform/operator-patterns/webhooks.md
  - platform/operator-patterns/finalizers.md

## Workflows
Missing:
  - workflows/exec-plans/README.md
  - workflows/exec-plans/template.md

📊 Summary: 4 missing files detected

# User selects:
"Fill all gaps" OR "Fill exec-plans only" OR "Custom: add observability practices"

# Actions: Creates missing files, updates indexes, validates
```

### Example 2: Add Exec-Plans Workflow

```bash
/update-platform-docs

# User: "Add exec-plans guidance to workflows"

# Actions:
mkdir -p ai-docs/workflows/exec-plans
# Create README.md from template
# Create template.md from template
# Update workflows/index.md
# Update AGENTS.md
# Update create-structure.sh
# Validate
```

### Example 2: Add New Platform Pattern

```bash
/update-platform-docs

# User: "Add webhooks pattern to operator patterns"

# Actions:
# Create platform/operator-patterns/webhooks.md from template
# Update platform/operator-patterns/index.md
# Update AGENTS.md (add link to webhooks)
# Validate
```

### Example 3: Update Existing File

```bash
/update-platform-docs

# User: "Add conversion webhooks section to webhooks.md"

# Actions:
# Read platform/operator-patterns/webhooks.md
# Add new section with conversion webhook guidance
# Validate (check line count, style)
```

## Arguments

```bash
/update-platform-docs [--path <repository-path>]
```

**Arguments:**
- `--path <repository-path>`: Path to enhancements repository (default: current directory)
- No args: Update documentation in current directory

## Prerequisites

**Before running:**
1. ✅ ai-docs/ already exists (if not, use `/platform-docs`)
2. ✅ You're in openshift/enhancements repository
3. ✅ You know what you want to add/update

**If ai-docs/ doesn't exist:**
```bash
# First create base documentation
/platform-docs

# Then use /update-platform-docs for incremental changes
```

## Success Output

```text
✅ Platform Documentation Updated

Repository: /path/to/enhancements

Changes:
  ✅ Created: ai-docs/workflows/exec-plans/README.md
  ✅ Created: ai-docs/workflows/exec-plans/template.md
  ✅ Updated: ai-docs/workflows/index.md
  ✅ Updated: AGENTS.md (added exec-plans link)

Validation:
  ✅ File naming conventions correct
  ✅ Index files updated
  ✅ AGENTS.md: 192 lines (target: ≤200)
  ✅ Internal links valid
  ✅ Reference style maintained

Next Steps:
  1. Review changes
  2. Run: git add ai-docs/ AGENTS.md
  3. Run: git commit -m "Add exec-plans workflow guidance"
```

## Common Mistakes to Avoid

### ❌ Mistake 1: Using When ai-docs/ Doesn't Exist
**Wrong:** Running `/update-platform-docs` on fresh repo
**Right:** Run `/platform-docs` first, then use `/update-platform-docs`

### ❌ Mistake 2: Making AGENTS.md Too Long
**Wrong:** Adding verbose descriptions to AGENTS.md
**Right:** Keep compressed, table-based navigation only

### ❌ Mistake 3: Not Updating Index Files
**Wrong:** Creating new file without updating parent index.md
**Right:** Always update corresponding index.md

### ❌ Mistake 4: Inconsistent Naming
**Wrong:** Creating `README.md` (except in exec-plans/) or `adr-1-topic.md`
**Right:** Use `index.md` (or `exec-plans/README.md` as exception) and `adr-0001-topic.md`

### ❌ Mistake 5: Duplicating Content
**Wrong:** Copying content from dev-guide/guidelines
**Right:** Link to authoritative source or reformat for AI agents

## See Also

- `/platform-docs` - Create platform documentation from scratch
- [Platform SKILL.md](../SKILL.md) - Full platform docs creation guide
- [Validation Script](../scripts/validate.sh) - Structure validation
