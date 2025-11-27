---
description: Explain code or concepts using first principles with WHAT/WHY/HOW structure
argument-hint: <file|package|concept>
---

## Name

learning:explain

## Synopsis

```
/learning:explain <file|package|concept>
```

## Description

The `learning:explain` command provides deep, first-principles explanations of code files, packages, or technical concepts.
It structures explanations using the WHAT/WHY/HOW framework to build understanding from the ground up.

This command is designed for engineers who learn best through:
- Understanding fundamental principles before implementation details
- Seeing the big picture before diving into specifics
- Understanding the problem context before the solution
- Building mental models from first principles

## Implementation

### Phase 1: Input Analysis

1. **Identify Input Type**
   - Check if argument is a file path (exists in filesystem)
   - Check if argument is a package name (contains multiple files in directory)
   - Otherwise, treat as a concept or technology name

2. **Gather Context**
   - For files: Read the file content using Read tool
   - For packages: Use Glob to find all relevant files, then Read key files
   - For concepts: Use existing knowledge or WebSearch if needed for current information

### Phase 2: First Principles Analysis

1. **Identify Fundamental Concepts**
   - Break down the topic into its most basic building blocks
   - Identify the core primitives and abstractions
   - Understand the foundational principles at play

2. **Trace Problem Space**
   - What fundamental problem is being addressed?
   - What constraints exist in the problem domain?
   - What trade-offs are being made?

### Phase 3: Structured Explanation

Present the explanation in three distinct phases:

**WHAT: High-Level Overview**
- Provide a clear, concise summary of what this is
- Describe its role in the larger system
- Define key terminology
- Give a mental model or analogy if helpful

**WHY: Problem and Purpose**
- Explain the fundamental problem being solved
- Describe what would happen without this solution
- Explain the design decisions and trade-offs
- Connect to broader principles or patterns

**HOW: Implementation Details**
- Walk through the important mechanisms
- Explain key algorithms or data structures
- Show how the pieces fit together
- Highlight interesting or non-obvious details
- Include code examples where relevant

### Phase 4: Verification and Depth

1. **Check Understanding**
   - Ensure explanation builds logically from first principles
   - Verify no circular reasoning or unexplained assumptions
   - Confirm technical accuracy

2. **Add Context**
   - Connect to related concepts or technologies
   - Mention common pitfalls or gotchas
   - Suggest areas for further exploration

## Return Value

- **Format**: Structured markdown explanation with WHAT/WHY/HOW sections
- **Content**: Deep, first-principles understanding of the target
- **Style**: Educational, building from fundamentals to specifics

## Examples

1. **Explain a file**:
   ```
   /learning:explain pkg/reconciler/controller.go
   ```
   Analyzes the controller file and explains its purpose, the problem it solves (reconciliation loop pattern), and how it implements the controller pattern.

2. **Explain a package**:
   ```
   /learning:explain pkg/cache
   ```
   Examines all files in the cache package and explains the caching system from first principles.

3. **Explain a concept**:
   ```
   /learning:explain eventual consistency
   ```
   Provides a first-principles explanation of eventual consistency, starting with the fundamental constraints of distributed systems.

4. **Explain a data structure**:
   ```
   /learning:explain pkg/datastructures/btree.go
   ```
   Explains B-trees from first principles, covering what they are (balanced tree structure), why they exist (disk I/O optimization), and how they work (node splitting, balancing).

## Arguments

- **$1 (required)**: File path, package path, or concept name to explain
  - File path: Relative or absolute path to a source file
  - Package path: Directory containing related source files
  - Concept: Technical concept or technology name
