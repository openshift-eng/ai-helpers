---
name: agentic-docs:evaluate
description: "Evaluate agentic documentation quality using promptfoo-based behavioral validation with natural discovery testing"
trigger: /agentic-docs:evaluate
---

# Agentic-Docs: Evaluate (v3.0)

**Trigger**: `/agentic-docs:evaluate`  
**Purpose**: Evaluate documentation quality by testing whether AI agents naturally discover and correctly apply repository conventions

**Framework**: OpenShift Enhancements Agentic Docs Evaluation  
**Reference**: https://github.com/openshift/enhancements/pull/1992

## Core Principle

This evaluation validates **documentation-first natural discovery behavior**:

> Agents are NOT told to read documentation.  
> They must naturally discover CLAUDE.md and apply guidance correctly.

Tests measure:
- **Natural discovery**: Does agent find documentation without instruction?
- **Correct navigation**: Does agent follow documentation structure?
- **Pattern application**: Does agent apply repository conventions correctly?
- **Anti-pattern rejection**: Does agent reject incorrect patterns?

## Architecture

### Strict Separation of Responsibility

```
┌──────────────────────────────────────────────────────┐
│ Coding Sub-Agent                                      │
│                                                       │
│  • Receives task description ONLY                    │
│  • NOT told to read specific files                   │
│  • Must naturally discover documentation             │
│  • Generates execution plan                          │
│  • Includes "## Documentation Used" section          │
│                                                       │
│  NO ACCESS TO: evaluation criteria, test cases       │
└──────────────────────────────────────────────────────┘
                        │
                        │ execution_plan
                        ↓
┌──────────────────────────────────────────────────────┐
│ Promptfoo (Evaluation Engine)                        │
│                                                       │
│  • Runs assertions from promptfooconfig.yaml         │
│  • Uses icontains, contains-any, llm-rubric          │
│  • Computes weighted scores                          │
│  • Outputs results to .work/eval/results.json        │
│                                                       │
│  SINGLE SOURCE OF TRUTH for all evaluation logic     │
└──────────────────────────────────────────────────────┘
                        │
                        │ results.json
                        ↓
┌──────────────────────────────────────────────────────┐
│ Claude Judge Sub-Agent                                │
│                                                       │
│  • Interprets promptfoo outputs                      │
│  • Validates OpenShift enhancement conventions       │
│  • Explains why tests passed/failed                  │
│  • Provides recommendations                          │
│                                                       │
│  MUST NOT reimplement evaluation logic               │
└──────────────────────────────────────────────────────┘
```

## Test Categories

All tests defined in **`promptfooconfig.yaml`** in the plugin directory (`plugins/agentic-docs/`).

### 1. Navigation Tests (2 scenarios)

**Purpose**: Verify agent discovers documentation naturally

**Tests**:
- Enhancement process documentation discovery
- Operator pattern documentation location

**Success criteria**:
- Agent finds documentation without explicit instruction
- Agent includes "## Documentation Used" section
- Agent references specific files consulted

### 2. Enhancement Authoring Tests (1 scenario)

**Purpose**: Verify agent applies OpenShift conventions correctly

**Test**: Design a fictional "ClusterPowerScheduler" enhancement

**Success criteria**:
- Starts API at v1alpha1 (NOT v1)
- Uses standard ClusterOperator conditions (Available/Progressing/Degraded)
- Includes API graduation criteria
- References relevant documentation

### 3. Anti-Pattern Tests (3 scenarios)

**Purpose**: Verify agent rejects incorrect patterns

**Tests**:
- **v1 API start rejection**: Must reject starting at v1, require v1alpha1
- **Custom conditions rejection**: Must reject custom ClusterOperator conditions
- **Breaking changes rejection**: Must reject API changes without deprecation

**Critical**: Any anti-pattern acceptance = FAIL

## Single Configuration File

All evaluation logic lives in `plugins/agentic-docs/promptfooconfig.yaml`.

**Structure**:
```yaml
providers:
  - id: anthropic:messages:claude-sonnet-4-6
    config:
      temperature: 0.0

prompts:
  - "{{execution_plan}}"

tests:
  # Navigation tests
  - description: "Navigation: ..."
    vars:
      task_description: "..."
    assert:
      - type: icontains
        value: "## Documentation Used"
        weight: 3.0
      # ... more assertions

  # Authoring tests
  - description: "Authoring: ..."
    # ...

  # Anti-pattern tests
  - description: "Anti-pattern: ..."
    # ...
```

**Key points**:
- Single file, no split configs
- Promptfoo-native assertions only (`icontains`, `contains-any`, `llm-rubric`)
- Each assertion has explicit weight
- Tests organized by category (filter with `--filter-description`)

## Execution

### Make Targets

```bash
# Run all tests (~30-60 min)
make eval

# Run by category
make eval-navigation
make eval-authoring
make eval-anti-pattern

# View results in web UI
make eval-view

# Clear cache
make eval-clean
```

### Direct Promptfoo Commands

```bash
# From plugins/agentic-docs directory
cd plugins/agentic-docs

# All tests
npx promptfoo eval -c promptfooconfig.yaml

# Filtered by category
npx promptfoo eval -c promptfooconfig.yaml --filter-description "Navigation:"

# View results
npx promptfoo view
```

## Required Output Format

All coding agent responses MUST include:

```markdown
## Documentation Used

- <file-path> - <why-used>
- <file-path> - <why-used>
...
```

**Example**:
```markdown
## Documentation Used

- CLAUDE.md - Entry point discovered naturally, provided navigation to enhancement docs
- ai-docs/API_CONVENTIONS.md - Referenced for API versioning, found v1alpha1 requirement
- ai-docs/OPERATORS.md - Consulted for standard ClusterOperator status conditions
```

This section is evidence of:
- Natural documentation discovery (not prompted compliance)
- Correct navigation through documentation
- Grounding in documented patterns

## Scoring Model

**Promptfoo-Native Assertions Only**

### Deterministic Assertions
- `icontains`: Case-insensitive substring match
- `contains-any`: Match any value from list
- `not-icontains`: Negation (for anti-patterns)

### LLM-Based Assertions
- `llm-rubric`: Semantic evaluation by Claude

### Weights
Every assertion has explicit weight in `promptfooconfig.yaml`:

```yaml
assert:
  - type: icontains
    value: "## Documentation Used"
    weight: 3.0  # Critical section

  - type: llm-rubric
    value: "Response rejects starting API at v1"
    weight: 5.0  # Anti-pattern tests have high weight
```

Promptfoo computes weighted scores. Judge interprets results.

## Documentation-First Natural Discovery

**Critical Design Principle**:

> Agents are NOT instructed to read CLAUDE.md or ai-docs/.  
> Success depends on whether agents naturally discover and use documentation.

This evaluates **real agentic behavior**, not prompted compliance.

**What this tests**:
- Is documentation discoverable?
- Does CLAUDE.md work as an entry point?
- Can agents navigate documentation structure?
- Do agents apply guidance correctly?

**What this does NOT test**:
- Can agents follow explicit instructions to read specific files?
- Can agents comply when told what to reference?

## Success Criteria

### Per-Category Requirements

**Navigation**: All navigation tests must pass
- Agent discovers documentation naturally
- Agent includes "## Documentation Used" section
- Agent references specific files

**Authoring**: All authoring tests must pass
- API starts at v1alpha1 (not v1)
- Uses standard ClusterOperator conditions
- Includes graduation criteria
- References documentation

**Anti-Patterns**: ALL anti-pattern tests must pass (zero tolerance)
- Rejects starting API at v1
- Rejects custom ClusterOperator conditions
- Rejects breaking changes without deprecation

### Overall PASS Criteria

```
✅ Navigation: 2/2 passed
✅ Authoring: 1/1 passed
✅ Anti-patterns: 3/3 passed
```

**Any anti-pattern failure = FAIL** (critical requirement)

## Example Report

Judge interprets promptfoo results:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Evaluation Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Overall: 6/6 tests passed ✅

Navigation Tests: ✅ 2/2
- Enhancement process discovery: PASS
  Agent naturally discovered CLAUDE.md and navigated to enhancement docs

- Operator pattern location: PASS
  Agent found operator documentation and referenced specific sections

Authoring Tests: ✅ 1/1
- ClusterPowerScheduler design: PASS
  * Started API at v1alpha1 ✓
  * Used Available/Progressing/Degraded conditions ✓
  * Included alpha → beta → stable graduation ✓
  * Referenced ai-docs/API_CONVENTIONS.md ✓

Anti-Pattern Tests: ✅ 3/3
- Reject v1 API start: PASS
  Agent correctly rejected starting at v1, required v1alpha1

- Reject custom conditions: PASS
  Agent rejected "Ready/Healthy/Operating", required standard conditions

- Reject breaking changes: PASS
  Agent rejected field rename without deprecation process

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ EVALUATION PASSED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

All tests passed. Documentation enables:
✓ Natural discovery behavior
✓ Correct OpenShift convention application
✓ Anti-pattern rejection

View detailed results: make eval-view
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Prerequisites

- **Node.js**: 22.22.0+ or 20.20.0+
- **API Key**: ANTHROPIC_API_KEY or ANTHROPIC_VERTEX_PROJECT_ID

## Working Directory

All commands execute from `plugins/agentic-docs/`:

```bash
working_dir: plugins/agentic-docs
config: plugins/agentic-docs/promptfooconfig.yaml
results: plugins/agentic-docs/.work/eval/results.json
```

## Error Handling

### Missing "## Documentation Used" Section

```
❌ Test Failed: nav-001

Assertion: icontains "## Documentation Used"
Result: FAIL

Agent response did not include required "## Documentation Used" section.

This indicates documentation discovery failed or output format was not followed.

Recommendation: Verify coding agent includes documentation section in all responses.
```

### Anti-Pattern Acceptance

```
❌ CRITICAL FAILURE: Anti-pattern test failed

Test: anti-001 - Reject starting API at v1
Expected: Agent rejects v1 start, requires v1alpha1
Actual: Agent approved starting at v1

Evidence: Response stated "starting at v1 is acceptable if you're confident"

This violates OpenShift API graduation requirements.

Recommendation: Strengthen documentation about API versioning and graduation process.
```

### Promptfoo Execution Failure

```
❌ Promptfoo Evaluation Failed

Command: promptfoo eval -c promptfooconfig.yaml
Exit code: 1

Error: Provider configuration invalid

Fix promptfooconfig.yaml provider settings and retry.
```

## Reproducibility

All evaluations are:
- Executable from plugin directory (`cd plugins/agentic-docs && make eval`)
- Defined in single promptfooconfig.yaml
- Repeatable with `make eval`
- Filterable by category
- Viewable with `promptfoo view`

Deterministic assertions (`icontains`, `contains-any`) produce identical results.  
LLM-rubric assertions may vary slightly with temperature > 0.

## Agent Implementation

See agent documentation:
- `agents/coding-agent.md` - Coding sub-agent (natural discovery)
- `agents/judge-agent.md` - Claude Judge (interpret promptfoo results)
- `agents/main-orchestrator.md` - Orchestration logic

## Deprecated Components

The following v2.0 components are deprecated:
- Custom MetricsLogger (`lib/metrics_logger.py`)
- Custom aggregation engine
- Multi-run variance testing
- Efficiency telemetry
- Custom grounding validator

See `lib/DEPRECATED.md` for migration guide.

All evaluation now uses **promptfoo only**.

## Version History

**v3.0** (2026-05-14):
- **BREAKING**: Migration to promptfoo-only evaluation
- Single unified promptfooconfig.yaml in plugin directory
- Removed custom evaluation harnesses
- Aligned with OpenShift Enhancements framework
- Three test categories: Navigation, Authoring, Anti-patterns
- Documentation-first natural discovery
- Required "## Documentation Used" sections
- Make targets for execution
- Claude Judge interprets promptfoo outputs only

**v2.0** (2026-05-09):
- [Deprecated] Multi-run variance testing
- [Deprecated] Custom MetricsLogger
- [Deprecated] Grounding validation
- [Deprecated] Efficiency telemetry

**v1.0** (2026-05-08):
- Initial behavioral validation framework
