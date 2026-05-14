---
description: Evaluate agentic documentation quality using promptfoo-based behavioral validation
argument-hint: "[repository-path]"
---

## Name
agentic-docs:evaluate

## Synopsis
```
/agentic-docs:evaluate [repository-path]
```

## Description
The `agentic-docs:evaluate` command evaluates documentation quality by testing whether AI agents naturally discover and correctly apply repository conventions without being explicitly told to read documentation.

This command validates **documentation-first natural discovery behavior** using the OpenShift Enhancements Agentic Docs Evaluation framework. It measures:
- **Natural discovery**: Does the agent find documentation without instruction?
- **Correct navigation**: Does the agent follow documentation structure?
- **Pattern application**: Does the agent apply repository conventions correctly?
- **Anti-pattern rejection**: Does the agent reject incorrect patterns?

The evaluation uses promptfoo to run assertions from `promptfooconfig.yaml` and generates detailed HTML reports with pass/fail grades.

## Implementation
When this command is invoked, Claude will execute the `agentic-docs:evaluate` skill, which:
1. Loads evaluation configuration from `promptfooconfig.yaml`
2. Runs coding sub-agents with task descriptions (no explicit file instructions)
3. Evaluates whether agents naturally discovered and applied documentation
4. Generates graded results with pass/fail assertions
5. Creates HTML reports for review

The skill maintains strict separation between coding agents (who must discover docs naturally) and evaluation agents (who grade the results).

## Return Value
- Evaluation results with pass/fail grades for each test case
- HTML report showing which documentation was discovered and applied
- Metrics on natural discovery patterns

## Examples

1. **Evaluate current directory**:
   ```
   /agentic-docs:evaluate
   ```
   Evaluates documentation in the current working directory.

2. **Evaluate specific repository**:
   ```
   /agentic-docs:evaluate /path/to/openshift/repo
   ```
   Evaluates documentation in the specified repository.

## Arguments
- `repository-path` (optional): Path to the repository to evaluate. Defaults to current directory if not specified.
