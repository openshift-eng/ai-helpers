---
description: Build a concept from first principles with progressive, working code examples
argument-hint: <topic or technology>
---

## Name

learning:build-from-scratch

## Synopsis

```
/learning:build-from-scratch <topic or technology>
```

## Description

The `learning:build-from-scratch` command creates a comprehensive "Build Your Own X" walkthrough that demonstrates how complex systems emerge from simple building blocks through progressive, incremental steps.

This educational approach:
- Starts with the absolute minimum working example
- Builds incrementally, adding exactly one new concept per step
- Provides runnable code at every step
- Shows how complexity emerges from simple fundamentals
- Connects toy implementations to real-world production systems

Perfect for engineers who learn by building and want to understand systems from the ground up.

## Implementation

### Phase 1: Topic Analysis and Planning

1. **Understand the Topic**
   - Parse the requested topic/technology
   - Identify the core concepts that need to be built
   - Research if needed (use WebSearch for current information)

2. **Plan the Progression**
   - Identify the simplest possible working example (MVP)
   - List the key features to add incrementally
   - Ensure each step builds logically on previous steps
   - Plan 5-7 progressive steps from simple to complete

3. **Determine Working Directory**
   - Create workspace: `.work/learning-build-from-scratch/{topic-name}/`
   - This directory will contain all code examples

### Phase 2: Create Incremental Steps

For each step in the progression:

1. **Write Step Documentation**
   - Clear title indicating what's being added
   - Brief explanation of the concept
   - Connection to previous steps
   - Real-world relevance

2. **Create Working Code**
   - Write complete, runnable code
   - Include clear comments explaining the "why"
   - Keep code simple and focused on the new concept
   - Save code to `.work/learning-build-from-scratch/{topic}/step-{n}/`

3. **Provide Test/Demo Code**
   - Include example usage showing the code works
   - Add verification steps
   - Show expected output

4. **Show the Progression**
   - Highlight what changed from previous step
   - Explain why this addition matters
   - Preview what's coming next

### Phase 3: Structure the Walkthrough

Create a comprehensive markdown document with:

**Introduction Section**
- Brief overview of what will be built
- Why building from scratch aids understanding
- Prerequisites (language, tools needed)

**Step-by-Step Sections** (5-7 steps)

Each step includes:
- **Title**: "Step N: [What's being added]"
- **Concept**: Explain the fundamental principle
- **Implementation**: Complete code with comments
- **How It Works**: Explain the mechanism
- **Try It**: Commands to run and test the code
- **Output**: Expected results
- **Reflection**: Connect to real-world systems

**Final Section**
- Complete working example combining all concepts
- Comparison to production implementations
- What's been simplified vs. real systems
- Suggestions for further exploration
- Links to relevant projects/documentation

### Phase 4: Create and Verify Code

1. **Write All Code Files**
   - Use Write tool to create each step's code
   - Ensure proper directory structure
   - Follow language best practices

2. **Test Compilation/Execution**
   - Use Bash tool to verify code compiles/runs
   - Fix any syntax errors
   - Verify examples produce expected output

3. **Create Master Document**
   - Assemble complete walkthrough
   - Ensure smooth narrative flow
   - Include all code snippets inline
   - Add file paths for reference

## Return Value

- **Format**: Comprehensive markdown walkthrough document
- **Location**: `.work/learning-build-from-scratch/{topic}/walkthrough.md`
- **Code Examples**: Working code in `.work/learning-build-from-scratch/{topic}/step-*/`
- **Style**: Progressive, educational, building from simple to complex

## Examples

1. **Build a container runtime**:
   ```
   /learning:build-from-scratch container runtime
   ```
   Creates a walkthrough building a minimal container runtime, starting with process isolation, then adding namespaces, cgroups, and finally a basic image system.

2. **Build a DNS resolver**:
   ```
   /learning:build-from-scratch DNS resolver
   ```
   Builds a DNS resolver from scratch, starting with UDP sockets, then adding query parsing, recursive resolution, and caching.

3. **Build a distributed key-value store**:
   ```
   /learning:build-from-scratch distributed key-value store
   ```
   Creates a distributed KV store, starting with simple in-memory storage, adding network communication, then replication, and finally consensus.

4. **Build a garbage collector**:
   ```
   /learning:build-from-scratch garbage collector
   ```
   Implements a GC from first principles, starting with mark-and-sweep on a simple heap, then adding generational collection and incremental marking.

5. **Build a HTTP server**:
   ```
   /learning:build-from-scratch HTTP server
   ```
   Constructs an HTTP server from TCP sockets, parsing HTTP requests, handling routes, and adding concurrent connection handling.

## Arguments

- **$1 (required)**: Topic or technology to build from scratch
  - Can be a system (e.g., "container runtime", "web server")
  - Can be a technology (e.g., "DNS", "TLS")
  - Can be a concept (e.g., "garbage collector", "scheduler")
  - Can be a data structure (e.g., "B-tree", "skip list")

## Notes

- All code examples must be complete and runnable
- Each step should take 5-10 minutes to understand and try
- Focus on clarity over performance
- Emphasize the "aha!" moments where simple concepts combine powerfully
- Connect toy implementations to real production systems
- Include plenty of comments explaining the "why" not just the "what"
