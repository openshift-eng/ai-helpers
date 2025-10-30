# Learning Plugin

Educational commands for understanding code and concepts through first principles and hands-on building.

## Overview

The Learning plugin provides two complementary approaches to mastering technical concepts:

1. **First Principles Explanation** - Understand existing code and concepts through structured WHAT/WHY/HOW analysis
2. **Build From Scratch** - Learn by building toy implementations that demonstrate how complex systems emerge from simple fundamentals

These commands are designed for engineers who learn best by understanding the "why" behind the "what" and by building working examples.

## Commands

### `/learning:explain`

Explains code files, packages, or technical concepts using a first principles approach with WHAT/WHY/HOW structure.

**Usage:**
```
/learning:explain <file|package|concept>
```

**Examples:**
- `/learning:explain pkg/reconciler/controller.go` - Explain a specific file
- `/learning:explain pkg/cache` - Explain an entire package
- `/learning:explain eventual consistency` - Explain a technical concept

**Structure:**
- **WHAT**: High-level overview and mental models
- **WHY**: Problem being solved and design decisions
- **HOW**: Implementation details and mechanisms

### `/learning:build-from-scratch`

Creates a comprehensive "Build Your Own X" walkthrough that demonstrates how complex systems emerge from simple fundamentals.
Progressive learning through building working code examples.

**Usage:**
```
/learning:build-from-scratch <topic or technology>
```

**Examples:**
- `/learning:build-from-scratch container runtime` - Build a minimal container runtime
- `/learning:build-from-scratch DNS resolver` - Build a DNS resolver from TCP sockets up
- `/learning:build-from-scratch garbage collector` - Implement basic GC algorithms

**Features:**
- Starts with simplest possible working example
- Adds one new concept per step
- Every step has runnable code
- Connects to real-world production systems
- Includes test/demo code for verification

## When to Use This Plugin

### Use `/learning:explain` when you:
- Encounter unfamiliar code and need to understand it deeply
- Want to understand design decisions and trade-offs
- Need to explain complex systems to others
- Want to build mental models of technical concepts
- Are reviewing code and need architectural context

### Use `/learning:build-from-scratch` when you:
- Want to understand how a system works under the hood
- Learn best by building working examples
- Need to teach concepts to others
- Want to demystify complex technologies
- Preparing for technical interviews or presentations
- Want to contribute to systems but need foundational understanding

## Learning Philosophy

This plugin embodies two key learning principles:

1. **First Principles Thinking**: Break complex topics down to fundamental truths and build up understanding from there
2. **Learning by Building**: Understand systems by implementing simplified versions yourself

Together, these approaches help engineers develop deep, transferable understanding rather than surface-level knowledge.

## Installation

### From Marketplace

```bash
# Add the ai-helpers marketplace
/plugin marketplace add openshift-eng/ai-helpers

# Install the learning plugin
/plugin install learning@ai-helpers
```

### Manual Installation

```bash
# Clone the repository
git clone git@github.com:openshift-eng/ai-helpers.git

# Link to Claude Code plugins directory
ln -s $(pwd)/ai-helpers/plugins/learning ~/.claude/plugins/learning
```

## Output Locations

- `/learning:explain` - Returns formatted markdown explanation inline
- `/learning:build-from-scratch` - Creates files in `.work/learning-build-from-scratch/{topic}/`
  - `walkthrough.md` - Complete tutorial document
  - `step-{n}/` - Working code for each step

## Contributing

This plugin is part of the [ai-helpers](https://github.com/openshift-eng/ai-helpers) repository.

To contribute:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run `make lint` to validate
5. Submit a pull request

## License

See the main repository for license information.
