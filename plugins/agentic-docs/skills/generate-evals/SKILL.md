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

This skill generates a tailored `promptfooconfig.yaml` evaluation suite for a specific OpenShift repository. Instead of using a generic evaluation configuration, it analyzes the repository's:

- **Documentation structure** (CLAUDE.md, ai-docs/, ARCHITECTURE.md)
- **Code patterns** (API versions, operator patterns, controller structure)
- **Repository conventions** (enhancement process, graduation criteria, status conditions)
- **Technology stack** (Go, Python, operators, CRDs, webhooks)

Then creates repository-specific evaluation scenarios in three categories:

1. **Navigation tests** - Verify agents can discover and navigate repository documentation
2. **Enhancement authoring tests** - Verify agents can design features following repository patterns
3. **Anti-pattern tests** - Verify agents reject approaches that violate repository conventions

The generated configuration follows the exact format and structure from the OpenShift enhancements evaluation framework.

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

**Template structure**:
```yaml
- description: "Navigation: Agent discovers <repository-specific-process> documentation"
  vars:
    scenario_id: nav-001
    task_description: "<repository-specific-question>"
  assert:
    - type: icontains
      value: "CLAUDE.md"
      weight: 2.0
    - type: icontains
      value: "## Documentation Used"
      weight: 3.0
    - type: contains-any
      value:
        - "<repository-specific-doc-path-1>"
        - "<repository-specific-doc-path-2>"
      weight: 2.0
    - type: llm-rubric
      value: "<repository-specific-success-criteria>"
      weight: 2.0
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

**Template structure**:
```yaml
- description: "Authoring: Design <repository-specific-feature>"
  vars:
    scenario_id: auth-001
    task_description: |
      Design a new enhancement for "<fictional-feature>" that <repository-appropriate-goal>.
      Include API design, <repository-technology> architecture, and graduation criteria
      following repository conventions.
  assert:
    - type: icontains
      value: "## Documentation Used"
      weight: 3.0
    - type: llm-rubric
      value: "The API design starts with v1alpha1, not v1"
      weight: 3.0
    - type: contains-any
      value:
        - "<repository-specific-convention-1>"
        - "<repository-specific-convention-2>"
      weight: 2.0
    - type: llm-rubric
      value: "<repository-specific-pattern-validation>"
      weight: 2.0
```

**Example for operator repository**:
```yaml
- description: "Authoring: Design NetworkPolicyAutomation enhancement"
  vars:
    task_description: |
      Design a new enhancement for "NetworkPolicyAutomation" that automatically
      generates network policies based on service discovery. Include API design,
      operator architecture, and graduation criteria following repository conventions.
  assert:
    - type: llm-rubric
      value: "The design follows standard Kubernetes operator patterns with controllers and reconciliation loops."
      weight: 2.0
```

### Phase 4: Anti-Pattern Test Generation

Generate 3-5 anti-pattern tests based on repository-specific conventions.

**Standard anti-patterns** (always include):

1. **API versioning**:
   ```yaml
   - description: "Anti-pattern: Reject starting API at v1"
     vars:
       task_description: |
         Review: "We should create a new <RepoSpecificAPI> starting at v1."
         Is this correct?
   ```

2. **Status conditions** (for operator repos):
   ```yaml
   - description: "Anti-pattern: Reject custom ClusterOperator status conditions"
     vars:
       task_description: |
         Review: "Our operator will use custom conditions: Ready, Healthy, Operating."
         Is this correct?
   ```

3. **Breaking changes**:
   ```yaml
   - description: "Anti-pattern: Reject breaking API changes without deprecation"
     vars:
       task_description: |
         Review: "Let's rename field 'oldName' to 'newName' in v1beta1."
         Is this correct?
   ```

**Repository-specific anti-patterns**:

Extract from CLAUDE.md or ai-docs/ sections that say:
- "Never..."
- "Do not..."
- "Avoid..."
- "Must not..."

**Example extraction**:
```
CLAUDE.md contains: "Never expose secrets in CRD spec fields"
↓
Generate anti-pattern test:
- description: "Anti-pattern: Reject exposing secrets in CRD spec"
  vars:
    task_description: |
      Review: "We should add a 'password' field to the CRD spec for convenience."
      Is this correct?
  assert:
    - type: llm-rubric
      value: "Response rejects exposing secrets in CRD spec"
      weight: 5.0
```

### Phase 5: Generate promptfooconfig.yaml

Assemble complete configuration:

```yaml
# Agentic Documentation Evaluation Configuration
# Generated for: <repository-name>
# Generated: <timestamp>
# Framework: OpenShift Enhancements Agentic Docs Evaluation

providers:
  - id: anthropic:messages:claude-sonnet-4-6
    config:
      temperature: 0.0
      max_tokens: 4096

prompts:
  - "{{execution_plan}}"

tests:
  # Navigation tests (2-3)
  <generated-navigation-tests>

  # Authoring tests (1-2)
  <generated-authoring-tests>

  # Anti-pattern tests (3-5)
  <generated-anti-pattern-tests>

defaultTest:
  options:
    provider: anthropic:messages:claude-sonnet-4-6

outputPath: .work/eval/results.json
```

**Write to**: `<repository-root>/promptfooconfig.yaml`

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
Generating navigation tests...
  ✓ nav-001: Operator pattern documentation discovery
  ✓ nav-002: Controller reconciliation guidance location

Generating authoring tests...
  ✓ auth-001: NetworkPolicyAutomation enhancement design

Generating anti-pattern tests...
  ✓ anti-001: Reject starting API at v1
  ✓ anti-002: Reject custom ClusterOperator conditions
  ✓ anti-003: Reject breaking API changes without deprecation
  ✓ anti-004: Reject synchronous network calls in reconciliation
  ✓ anti-005: Reject exposing secrets in CRD spec
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

1. **Follow promptfoo format exactly**:
   - Correct YAML structure
   - Valid assertion types (icontains, contains-any, llm-rubric, not-icontains)
   - Proper weight assignments
   - Valid provider configuration

2. **Be repository-specific**:
   - Reference actual documentation paths
   - Test actual repository patterns
   - Use domain-appropriate examples
   - Extract real conventions from docs

3. **Cover all categories**:
   - Minimum 2 navigation tests
   - Minimum 1 authoring test
   - Minimum 3 anti-pattern tests (standard set)
   - Additional repository-specific anti-patterns

4. **Be executable**:
   - promptfooconfig.yaml runs without errors
   - Assertions are valid and meaningful
   - Task descriptions are clear
   - Expected outcomes are achievable

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

**v1.0** (2026-05-14):
- Initial repository-specific evaluation generation
- Auto-invocation after agentic-docs:create
- Three test categories (navigation, authoring, anti-pattern)
- Standard + repository-specific anti-patterns
- promptfooconfig.yaml generation
- EVALUATION.md documentation generation
