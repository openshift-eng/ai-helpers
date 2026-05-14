---
description: Generate repository-specific promptfoo evaluation suites for OpenShift documentation
argument-hint: "[repository-path]"
---

## Name
agentic-docs:generate-evals

## Synopsis
```
/agentic-docs:generate-evals [repository-path]
```

## Description
The `agentic-docs:generate-evals` command generates a tailored `promptfooconfig.yaml` evaluation suite for a specific OpenShift repository. Instead of using a generic evaluation configuration, it analyzes the repository's documentation structure, code patterns, and conventions to create repository-specific test cases.

The generated evaluation suite tests whether AI agents can:
- Naturally discover repository documentation
- Apply repository-specific patterns correctly
- Follow established conventions without explicit instruction
- Reject anti-patterns specific to the repository

This follows the OpenShift Enhancements Agentic Docs Evaluation framework, which emphasizes documentation-first natural discovery.

## Implementation
When this command is invoked, Claude will execute the `agentic-docs:generate-evals` skill, which:
1. Analyzes repository documentation structure (CLAUDE.md, ai-docs/, ARCHITECTURE.md)
2. Identifies code patterns (API versions, operator patterns, controller structure)
3. Extracts repository-specific conventions
4. Generates test cases that validate natural documentation discovery
5. Creates `promptfooconfig.yaml` with assertions tailored to the repository
6. Saves configuration to the repository root

## Return Value
- Generated `promptfooconfig.yaml` file in the repository root
- Test cases specific to the repository's patterns and conventions
- Assertions configured for natural discovery validation

## Examples

1. **Generate evals for current directory**:
   ```
   /agentic-docs:generate-evals
   ```
   Analyzes the current repository and generates `promptfooconfig.yaml`.

2. **Generate evals for specific repository**:
   ```
   /agentic-docs:generate-evals /path/to/openshift/repo
   ```
   Analyzes the specified repository and generates tailored evaluation configuration.

## Arguments
- `repository-path` (optional): Path to the target repository for analysis. Defaults to current directory if not specified.
