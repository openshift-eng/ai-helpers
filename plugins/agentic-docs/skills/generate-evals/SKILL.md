---
name: agentic-docs:generate-evals
description: "Generate repository-specific promptfoo evaluation suites tailored to OpenShift conventions and repository patterns"
trigger: /agentic-docs:generate-evals
---

# Agentic-Docs: Generate Evals

**Trigger**: `/agentic-docs:generate-evals`  
**Purpose**: Generate repository-specific promptfoo evaluation configurations following OpenShift enhancement evaluation framework

**Framework**: OpenShift Enhancements Agentic Docs Evaluation  
**Reference**: https://github.com/openshift/enhancements/pull/1992

## Name

agentic-docs:generate-evals - Generate repository-specific evaluation suites

## Synopsis

```
/agentic-docs:generate-evals [<repository-path>]
```

## Description

This skill generates a tailored `promptfooconfig.yaml` evaluation suite for a specific OpenShift repository **by adapting the canonical template** at `${CLAUDE_PLUGIN_ROOT}/skills/generate-evals/templates/promptfooconfig.example.yaml`.

**Template-First Approach**: 
The skill reads the reference template and preserves its structure (extensions, providers, defaultTest) while replacing only the `tests` array with repository-specific scenarios.

**Repository Analysis**:
It analyzes the target repository's:
- **Documentation structure** (CLAUDE.md, ai-docs/, ARCHITECTURE.md)
- **Code patterns** (API versions, operator patterns, controller structure)
- **Repository conventions** (enhancement process, graduation criteria, status conditions)
- **Technology stack** (Go, Python, operators, CRDs, webhooks)

**Generated Test Categories**:
1. **Navigation tests** - Verify agents can discover and navigate repository documentation
2. **Authoring tests** - Verify agents can design features following repository patterns  
3. **Convention/anti-pattern tests** - Verify agents reject approaches that violate repository conventions

The generated configuration follows the exact format from the template (HyperShift-based evaluation framework).

### Why Repository-Specific Evals?

**Generic evals cannot validate**:
- Repository-specific API conventions
- Project-specific operator patterns  
- Custom enhancement processes
- Unique architectural constraints
- Technology-specific best practices

**Repository-specific evals validate**:
- Agent discovers THIS repository's documentation
- Agent applies THIS repository's conventions correctly
- Agent avoids THIS repository's anti-patterns

## Implementation

### CRITICAL: Always Use the Template

**Base template location**: 
```
${CLAUDE_PLUGIN_ROOT}/skills/generate-evals/templates/promptfooconfig.example.yaml
```

**MANDATORY STEPS**:

1. **Read the template first**:
   ```bash
   cat ${CLAUDE_PLUGIN_ROOT}/skills/generate-evals/templates/promptfooconfig.example.yaml
   ```

2. **Use template as foundation** - Do NOT create promptfoo configs from scratch
3. **Preserve template structure** - Only modify the `tests` array and `description`
4. **Keep all template sections** - Extensions, providers, defaultTest unchanged

### Template Structure

The template demonstrates the canonical evaluation format:

- **Extensions**: `file://hooks.js:extensionHook` for test lifecycle hooks
- **Providers**: `exec: ./run-agent.sh` for custom agent execution
- **DefaultTest**: Vertex AI provider with standard configuration
- **Tests**: LLM rubric-based assertions (no weight fields)
- **Naming**: `category/##-description` pattern
- **Variables**: Use `vars.prompt` (not `vars.task_description`)
- **Concurrency**: `evaluateOptions.maxConcurrency` setting

**Template demonstrates**:
- Multi-agent testing patterns (agent-specific scenarios)
- Complex API design review scenarios
- Architectural anti-pattern detection
- Convention enforcement testing

### Phase 1: Repository Analysis

**Analyze repository structure**:

1. **Documentation discovery**:
   ```bash
   # Check what documentation exists
   [ -f CLAUDE.md ]
   [ -d ai-docs/ ]
   [ -f ARCHITECTURE.md ]
   [ -f AGENTS.md ]
   ```

2. **Code pattern analysis**:
   ```bash
   # Identify repository technology and patterns
   find . -name "*.go" | head -5        # Go codebase?
   find . -name "*_types.go" | head -5  # Kubernetes CRDs?
   find . -name "operator.yaml"         # Operator pattern?
   grep -r "v1alpha1" --include="*.go"  # API versioning?
   ```

3. **Convention extraction**:
   - Read CLAUDE.md for documented conventions
   - Read ai-docs/ for API patterns, operator guidance
   - Identify graduation requirements
   - Find status condition standards
   - Extract enhancement process

### Phase 2: Navigation Test Generation

Generate 2-3 navigation tests that verify agents can find repository-specific documentation.

**Template structure** (following promptfooconfig.example.yaml format):
```yaml
- description: "navigation/01-<specific-discovery-scenario>"
  vars:
    agent: <agent-name>  # Optional: if multi-agent setup
    prompt: |
      <repository-specific-question>
  assert:
    - type: llm-rubric
      value: "The output references <repository-specific-doc> for guidance"
    - type: llm-rubric
      value: "The output identifies the correct location: <path-to-documentation>"
    - type: llm-rubric
      value: "The output demonstrates understanding of <repository-convention>"
```

**Example generation logic**:

If repository has operator patterns:
```yaml
- description: "Navigation: Agent locates operator reconciliation documentation"
  vars:
    task_description: "How do I implement a new controller reconciliation loop in this codebase?"
```

If repository has CRD definitions:
```yaml
- description: "Navigation: Agent finds CRD development guidelines"
  vars:
    task_description: "Where can I find guidance on defining new Custom Resource Definitions?"
```

### Phase 3: Authoring Test Generation

Generate 1-2 enhancement authoring tests using repository-specific scenarios.

**Generation approach**:

1. **Identify repository domain**:
   - Networking? Storage? Security? Monitoring?
   - Example: If repo = cluster-network-operator → networking domain

2. **Generate fictional enhancement**:
   - Must fit repository domain
   - Should exercise documented patterns
   - Should require following conventions

**Template structure** (following promptfooconfig.example.yaml format):
```yaml
- description: "authoring/01-<feature-name>-design"
  vars:
    agent: <agent-name>  # Optional: if multi-agent setup
    prompt: |
      Design a new enhancement for "<fictional-feature>" that <repository-appropriate-goal>.
      Include API design, <repository-technology> architecture, and graduation criteria
      following repository conventions.
  assert:
    - type: llm-rubric
      value: "The API design starts with v1alpha1, not v1"
    - type: llm-rubric
      value: "The output includes <repository-required-section>"
    - type: llm-rubric
      value: "The design follows <repository-specific-pattern>"
```

**Example for operator repository** (following template format):
```yaml
- description: "authoring/01-network-policy-automation"
  vars:
    prompt: |
      Design a new enhancement for "NetworkPolicyAutomation" that automatically
      generates network policies based on service discovery. Include API design,
      operator architecture, and graduation criteria following repository conventions.
  assert:
    - type: llm-rubric
      value: "The design follows standard Kubernetes operator patterns with controllers and reconciliation loops"
    - type: llm-rubric
      value: "The API design starts with v1alpha1, not v1"
```

### Phase 4: Anti-Pattern Test Generation

Generate 3-5 anti-pattern tests based on repository-specific conventions.

**Standard anti-patterns** (following promptfooconfig.example.yaml format):

1. **API versioning**:
   ```yaml
   - description: "conventions/01-api-versioning"
     vars:
       prompt: |
         Review: "We should create a new <RepoSpecificAPI> starting at v1."
         Is this correct?
     assert:
       - type: llm-rubric
         value: "The output rejects starting new APIs at v1 and recommends v1alpha1"
   ```

2. **Status conditions** (for operator repos):
   ```yaml
   - description: "conventions/02-status-conditions"
     vars:
       prompt: |
         Review: "Our operator will use custom conditions: Ready, Healthy, Operating."
         Is this correct?
     assert:
       - type: llm-rubric
         value: "The output rejects custom status conditions and references standard ClusterOperator conditions"
   ```

3. **Breaking changes**:
   ```yaml
   - description: "conventions/03-breaking-changes"
     vars:
       prompt: |
         Review: "Let's rename field 'oldName' to 'newName' in v1beta1."
         Is this correct?
     assert:
       - type: llm-rubric
         value: "The output rejects breaking changes without deprecation period"
   ```

**Repository-specific anti-patterns**:

Extract from CLAUDE.md or ai-docs/ sections that say:
- "Never..."
- "Do not..."
- "Avoid..."
- "Must not..."

**Example extraction** (following template format):
```
CLAUDE.md contains: "Never expose secrets in CRD spec fields"
↓
Generate anti-pattern test:
- description: "conventions/04-secret-exposure"
  vars:
    prompt: |
      Review: "We should add a 'password' field to the CRD spec for convenience."
      Is this correct?
  assert:
    - type: llm-rubric
      value: "The output rejects exposing secrets in CRD spec and suggests SecretReference pattern"
```

### Phase 5: Generate promptfooconfig.yaml

**CRITICAL**: Generate the configuration by reading and adapting the template:

```bash
# Read the canonical template
cat ${CLAUDE_PLUGIN_ROOT}/skills/generate-evals/templates/promptfooconfig.example.yaml
```

**Template adaptation steps**:

1. **Copy template structure**:
   - Preserve `extensions` and `providers` sections exactly
   - Keep `defaultTest` configuration
   - Maintain `evaluateOptions.maxConcurrency` setting

2. **Update description**:
   ```yaml
   description: "<repository-name> - Agentic Documentation Evaluation"
   ```

3. **Adapt prompts section**:
   ```yaml
   prompts:
     - "{{prompt}}"  # Use template variable for dynamic test prompts
   ```

4. **Replace tests array** with generated test cases:
   ```yaml
   tests:
     # Navigation tests (2-3 generated from Phase 2)
     - description: "Navigation: <repository-specific-scenario>"
       vars:
         agent: <agent-name>  # If multi-agent setup
         prompt: |
           <generated-navigation-prompt>
       assert:
         - type: llm-rubric
           value: "<success-criteria>"
   
     # Authoring tests (1-2 generated from Phase 3)
     - description: "Authoring: <repository-specific-feature>"
       vars:
         prompt: |
           <generated-authoring-prompt>
       assert:
         - type: llm-rubric
           value: "<design-quality-criteria>"
   
     # Anti-pattern tests (3-5 generated from Phase 4)
     - description: "Anti-pattern: <violation-scenario>"
       vars:
         prompt: |
           <generated-anti-pattern-prompt>
       assert:
         - type: llm-rubric
           value: "<rejection-criteria>"
   ```

5. **Preserve provider configuration**:
   - Keep `exec: ./run-agent.sh` if target repo has agent setup
   - Keep Vertex AI `defaultTest` provider (standard for OpenShift repos)
   - Do NOT modify provider format - use template exactly

**Key template elements to preserve**:

```yaml
extensions:
  - file://hooks.js:extensionHook  # Keep if hooks.js exists in target repo

providers:
  - id: "exec: ./run-agent.sh"     # Keep if run-agent.sh exists
    label: claude

defaultTest:
  options:
    provider:
      id: vertex:claude-opus-4-6   # Use template provider config
      config:
        projectId: "{{ env.ANTHROPIC_VERTEX_PROJECT_ID }}"
        region: global
        temperature: 0

evaluateOptions:
  maxConcurrency: 6  # Adjust based on test count
```

**Write to**: `<repository-root>/promptfooconfig.yaml`

**Supporting files** (if not present, create them):
- `run-agent.sh` - Agent execution wrapper (copy from template repo if needed)
- `hooks.js` - Pre/post test hooks (copy from template repo if needed)

### Template Adaptation Example

**From template** (preserve these sections):
```yaml
description: "HyperShift agent and convention evals"

extensions:
  - file://hooks.js:extensionHook

providers:
  - id: "exec: ./run-agent.sh"
    label: claude

prompts:
  - "{{prompt}}"

defaultTest:
  options:
    provider:
      id: vertex:claude-opus-4-6
      config:
        projectId: "{{ env.ANTHROPIC_VERTEX_PROJECT_ID }}"
        region: global
        temperature: 0

tests:
  # ... (template tests here)

evaluateOptions:
  maxConcurrency: 6
```

**To repository-specific** (only change description and tests):
```yaml
description: "cluster-network-operator - Agentic Documentation Evaluation"  # ✓ Changed

extensions:
  - file://hooks.js:extensionHook  # ✓ Preserved

providers:
  - id: "exec: ./run-agent.sh"     # ✓ Preserved
    label: claude

prompts:
  - "{{prompt}}"                   # ✓ Preserved

defaultTest:
  options:
    provider:
      id: vertex:claude-opus-4-6   # ✓ Preserved
      config:
        projectId: "{{ env.ANTHROPIC_VERTEX_PROJECT_ID }}"
        region: global
        temperature: 0

tests:
  # ✓ REPLACED with repository-specific tests
  - description: "navigation/01-operator-pattern-discovery"
    vars:
      prompt: |
        How do I implement a new controller reconciliation loop in this codebase?
    assert:
      - type: llm-rubric
        value: "The output references ai-docs/OPERATORS.md for guidance"
  
  - description: "conventions/01-api-versioning"
    vars:
      prompt: |
        Review: "We should create a new NetworkPolicy API starting at v1."
        Is this correct?
    assert:
      - type: llm-rubric
        value: "The output rejects starting new APIs at v1 and recommends v1alpha1"

evaluateOptions:
  maxConcurrency: 2  # ✓ Adjusted for test count
```

### Common Template Mistakes to Avoid

❌ **DO NOT create promptfoo configs from scratch** - Always start with the template

❌ **DO NOT modify provider configuration** - Use template's Vertex AI setup exactly:
```yaml
# Keep this from template:
defaultTest:
  options:
    provider:
      id: vertex:claude-opus-4-6
      config:
        projectId: "{{ env.ANTHROPIC_VERTEX_PROJECT_ID }}"
        region: global
        temperature: 0
```

❌ **DO NOT add weight fields** to assertions - Template doesn't use them:
```yaml
# WRONG:
assert:
  - type: llm-rubric
    value: "Criteria"
    weight: 3.0  # ❌ Don't add weights

# CORRECT:
assert:
  - type: llm-rubric
    value: "Criteria"  # ✅ No weight field
```

❌ **DO NOT use old assertion types** - Template uses `llm-rubric` primarily:
```yaml
# WRONG:
assert:
  - type: icontains     # ❌ Don't use string matching
    value: "CLAUDE.md"

# CORRECT:
assert:
  - type: llm-rubric    # ✅ Use LLM-based evaluation
    value: "The output references CLAUDE.md for guidance"
```

❌ **DO NOT use `vars.task_description`** - Template uses `vars.prompt`:
```yaml
# WRONG:
vars:
  task_description: "Question"  # ❌ Old pattern

# CORRECT:
vars:
  prompt: "Question"  # ✅ Template pattern
```

✅ **DO preserve these template sections exactly**:
- `extensions` - Test lifecycle hooks
- `providers` - Agent execution configuration
- `defaultTest` - Vertex AI provider config
- `evaluateOptions` - Concurrency settings

### Phase 6: Generate Evaluation Documentation

Create `<repository-root>/EVALUATION.md`:

```markdown
# Evaluation Suite

This repository uses promptfoo-based evaluation to validate agentic documentation quality.

## Generated Evaluation Scenarios

### Navigation Tests (<count>)
- <test-1-description>
- <test-2-description>

### Authoring Tests (<count>)
- <test-description>

### Anti-Pattern Tests (<count>)
- <test-1-description>
- <test-2-description>
- <test-3-description>

## Running Evaluations

```bash
# All tests
make eval

# By category
make eval-navigation
make eval-authoring
make eval-anti-pattern

# View results
make eval-view
```

## Customizing

To add repository-specific evaluation scenarios:

1. Edit `promptfooconfig.yaml`
2. Add new test under appropriate category
3. Follow the existing format and assertion structure
4. Run `make eval` to validate

## Regenerating

To regenerate evaluation suite after documentation changes:

```bash
/agentic-docs:generate-evals
```

This will analyze current repository state and update evaluation scenarios.
```

## Return Value

**Success**:
```
✅ Generated repository-specific evaluation suite

Navigation tests: <count>
Authoring tests: <count>
Anti-pattern tests: <count>

Generated files:
  • promptfooconfig.yaml - Evaluation configuration
  • EVALUATION.md - Evaluation documentation

Run evaluations: make eval
View results: make eval-view
```

**Failure**:
```
❌ Evaluation generation failed

Reason: <error-description>

Ensure:
  • Target repository has CLAUDE.md or ai-docs/
  • Target repository contains code to analyze
  • Running from target repository directory
```

## Examples

### Example 1: Generate evals for operator repository

**Input**:
```
/agentic-docs:generate-evals /path/to/cluster-network-operator
```

**Analysis phase**:
```
Analyzing repository structure...
✓ Found CLAUDE.md
✓ Found ai-docs/ directory (12 files)
✓ Found Go codebase (245 .go files)
✓ Identified operator pattern (CRDs, controllers)
✓ Found API versioning (v1alpha1, v1)
✓ Extracted conventions from ai-docs/OPERATORS.md
```

**Generation phase**:
```
Reading template: ${CLAUDE_PLUGIN_ROOT}/skills/generate-evals/templates/promptfooconfig.example.yaml
✓ Template loaded (160 lines)
✓ Preserving extensions, providers, defaultTest sections

Generating navigation tests...
  ✓ navigation/01-operator-pattern-discovery
  ✓ navigation/02-controller-reconciliation-guidance

Generating authoring tests...
  ✓ authoring/01-network-policy-automation

Generating anti-pattern tests...
  ✓ conventions/01-api-versioning
  ✓ conventions/02-status-conditions
  ✓ conventions/03-breaking-changes
  ✓ conventions/04-sync-network-calls
  ✓ conventions/05-secret-exposure

Adapting template structure...
✓ Updated description field
✓ Replaced tests array (7 tests)
✓ Preserved provider configuration
✓ Set maxConcurrency: 7
```

**Output**:
```
✅ Generated evaluation suite

6 scenarios created:
  • 2 navigation tests
  • 1 authoring test
  • 5 anti-pattern tests (3 standard + 2 repository-specific)

Files created:
  • promptfooconfig.yaml (generated from repository analysis)
  • EVALUATION.md (evaluation documentation)

Run: make eval
```

### Example 2: Automatically invoked after documentation creation

**User runs**:
```
/agentic-docs:create /path/to/my-operator
```

**Skill execution**:
```
[agentic-docs:create running...]
✓ Documentation generated

[Auto-invoking agentic-docs:generate-evals...]

Generating repository-specific evaluation suite...
✓ Navigation tests: 2
✓ Authoring tests: 1  
✓ Anti-pattern tests: 4

Evaluation suite ready: make eval
```

## Arguments

### `<repository-path>`

**Optional** - Path to target repository being documented

**Default**: Current directory (`.`)

**Examples**:
```bash
# Current directory
/agentic-docs:generate-evals

# Specific repository
/agentic-docs:generate-evals /path/to/repo

# After documentation creation (automatic)
# No arguments needed - uses same path as create command
```

## Integration with agentic-docs:create

This skill is **automatically invoked** at the end of `/agentic-docs:create`:

```
/agentic-docs:create → [generates documentation] → /agentic-docs:generate-evals
```

**Auto-invocation behavior**:
- Uses same repository path as create command
- Runs after all documentation is generated
- Analyzes newly created ai-docs/ content
- Generates evaluation suite based on documentation
- No user interaction required

**Disabling auto-invocation**:
```
/agentic-docs:create --skip-evals
```

## Quality Criteria

Generated evaluation suites must:

1. **Follow template structure exactly**:
   - Read `${CLAUDE_PLUGIN_ROOT}/skills/generate-evals/templates/promptfooconfig.example.yaml`
   - Preserve `extensions`, `providers`, and `defaultTest` sections
   - Use `llm-rubric` assertions (primary assertion type in template)
   - Follow test naming convention: `category/##-description`
   - Use `vars.prompt` for test input (not `vars.task_description`)
   - Do NOT add `weight` fields to assertions (not used in template)

2. **Be repository-specific**:
   - Reference actual documentation paths in rubric criteria
   - Test actual repository patterns
   - Use domain-appropriate examples
   - Extract real conventions from docs

3. **Cover all categories**:
   - Minimum 2 navigation tests
   - Minimum 1 authoring test
   - Minimum 3 convention/anti-pattern tests (standard set)
   - Additional repository-specific anti-patterns

4. **Be executable**:
   - promptfooconfig.yaml runs without errors
   - All `llm-rubric` assertions have clear success criteria
   - Prompts are unambiguous
   - Expected outcomes are achievable

5. **Match template format**:
   - Use Vertex AI provider configuration from template
   - Include `evaluateOptions.maxConcurrency` setting
   - Preserve `temperature: 0` for deterministic evaluation
   - Use `file://` references for external files if needed

## Limitations

**Cannot generate evaluations for**:
- Repositories without any documentation
- Repositories without clear conventions
- Non-OpenShift repositories (patterns may not apply)

**Requires**:
- CLAUDE.md or ai-docs/ exists
- Repository follows OpenShift/Kubernetes patterns
- Code is analyzable (Go, Python, YAML)

## Version History

**v2.0** (2026-05-15):
- **Template-first approach**: Always use `templates/promptfooconfig.example.yaml` as base
- Use `llm-rubric` assertions (template pattern)
- Use `vars.prompt` instead of `vars.task_description`
- Preserve template's extensions, providers, defaultTest sections
- Follow `category/##-description` naming convention
- Remove weight fields from assertions (not in template)
- Document common template mistakes to avoid

**v1.0** (2026-05-14):
- Initial repository-specific evaluation generation
- Auto-invocation after agentic-docs:create
- Three test categories (navigation, authoring, anti-pattern)
- Standard + repository-specific anti-patterns
- promptfooconfig.yaml generation
- EVALUATION.md documentation generation
