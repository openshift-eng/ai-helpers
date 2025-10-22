# AI Agents Guide

This document provides guidance on using AI agents effectively with the AI Helpers repository and Claude Code in general.

## Table of Contents

- [What are AI Agents?](#what-are-ai-agents)
- [When to Use Agents](#when-to-use-agents)
- [Agent Types in Claude Code](#agent-types-in-claude-code)
- [Best Practices](#best-practices)
- [Agent Examples](#agent-examples)
- [Troubleshooting](#troubleshooting)

## What are AI Agents?

AI agents are autonomous task executors that can perform complex, multi-step operations without constant supervision. In Claude Code, agents are specialized workers that can:

- Search and analyze codebases
- Research complex topics
- Execute multi-step workflows
- Make autonomous decisions based on context

Unlike direct tool usage, agents operate independently and report back with results, making them ideal for time-consuming or exploratory tasks.

## When to Use Agents

### Use Agents When:

1. **Searching for unknown code locations**
   - You need to find a function but don't know which file it's in
   - You're exploring an unfamiliar codebase
   - You need to trace dependencies across multiple files

2. **Multi-step research tasks**
   - Analyzing how a feature is implemented across the codebase
   - Investigating bug patterns or test failures
   - Understanding complex architectural decisions

3. **Exploratory analysis**
   - You're not sure what you're looking for
   - The task requires multiple rounds of searching and reading
   - You need context from various sources before making decisions

4. **Parallel work**
   - You have multiple independent tasks that can run simultaneously
   - You want to continue working while background research happens

### Don't Use Agents When:

1. **You know the exact file path** - Use `Read` tool directly
2. **You know the exact search term** - Use `Grep` or `Glob` directly
3. **Simple, single-step tasks** - Direct tool calls are faster
4. **Real-time interaction needed** - Agents work autonomously

## Agent Types in Claude Code

### General-Purpose Agent

**Access to:** All tools (Read, Write, Edit, Glob, Grep, Bash, WebFetch, etc.)

**Best for:**
- Complex codebase research
- Multi-step implementation planning
- Cross-file analysis
- Feature investigation

**Example:**
```
Use the general-purpose agent to find all places where authentication tokens are validated,
analyze the current implementation, and recommend improvements.
```

### Specialized Agents

Claude Code may include specialized agents for specific tasks. Check the current documentation for available agent types:

```bash
/help agents
```

## Best Practices

### 1. Clear Task Definition

**Good:** "Search the codebase for all Jira API calls, identify which endpoints are used, and document the authentication flow."

**Bad:** "Look at the Jira stuff."

### 2. Specify Expected Output

**Good:** "Return a list of file paths and line numbers where database migrations are defined, along with a summary of what each migration does."

**Bad:** "Find migrations."

### 3. Run Agents in Parallel

When you have multiple independent research tasks, launch agents in parallel:

```
Launch three agents in parallel:
1. Research how error handling is implemented in the API layer
2. Find all test files related to authentication
3. Analyze how configuration is loaded and validated
```

### 4. Provide Context

Give agents enough context to make good decisions:

**Good:** "This is a Node.js Express API. Search for rate limiting middleware and analyze how it's configured for different endpoints."

**Bad:** "Find rate limiting code."

### 5. Trust Agent Results

Agents are designed to be thorough. If an agent reports it couldn't find something, it's likely not there (or not easily discoverable).

## Agent Examples

### Example 1: Codebase Research

**Task:** Understanding how the Jira plugin handles authentication

```
Use a general-purpose agent to research how the Jira plugin authenticates with Jira.
Find:
1. Where credentials are configured
2. How tokens are stored and used
3. Any authentication error handling
4. Whether there are different auth methods for different Jira instances

Return file paths with line numbers and a summary of the authentication flow.
```

### Example 2: Bug Investigation

**Task:** Finding the root cause of a test failure

```
Launch an agent to investigate why the test "should handle rate limiting" is failing.

The agent should:
1. Find the test file and read the test implementation
2. Locate the code being tested
3. Check for recent changes to either the test or the implementation
4. Look for similar tests that are passing
5. Report findings and suggest potential causes
```

### Example 3: Implementation Planning

**Task:** Planning a new feature

```
Use an agent to research how to add a new command to the Jira plugin.

The agent should:
1. Analyze existing command implementations (e.g., /jira:solve, /jira:status-rollup)
2. Document the common patterns and structure
3. Identify shared utilities or helpers
4. Create a checklist of steps needed to add a new command
5. Note any configuration or registration requirements
```

### Example 4: Parallel Research

**Task:** Comprehensive analysis of multiple areas

```
Launch three agents in parallel:

Agent 1: Research error handling patterns
- Find all custom error classes
- Document how errors are logged
- Identify where errors are caught and handled

Agent 2: Research testing infrastructure
- Find test utilities and helpers
- Document test setup and teardown patterns
- Identify mocking strategies

Agent 3: Research configuration management
- Find all configuration files
- Document environment variable usage
- Identify validation and default value handling

Wait for all agents to complete and synthesize their findings.
```

## Troubleshooting

### Agent Takes Too Long

- **Check scope:** Did you give the agent too broad a task?
- **Be more specific:** Narrow down the search criteria
- **Use direct tools:** If you know where to look, use Read/Grep directly

### Agent Doesn't Find What You Expected

- **Verify it exists:** The code you're looking for might not exist
- **Check search terms:** Try alternative terminology
- **Expand scope:** You might be looking in the wrong area

### Agent Returns Too Much Information

- **Refine the task:** Be more specific about what you need
- **Request filtering:** Ask the agent to prioritize or filter results
- **Break it down:** Split into smaller, focused tasks

### Multiple Agents Conflict

- **Ensure independence:** Agents should work on separate tasks
- **Sequential execution:** If tasks depend on each other, run them sequentially
- **Coordinate results:** Synthesize findings after all agents complete

## Contributing Agent Patterns

If you discover effective agent usage patterns while working with this repository, please contribute them:

1. Document the task type
2. Provide the agent prompt you used
3. Explain why it worked well
4. Note any lessons learned

Submit contributions via pull request to help the community learn from your experience.

## Additional Resources

- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code)
- [AI Helpers Repository](https://github.com/openshift-eng/ai-helpers)
- [Plugin Development Guide](README.md#plugin-development)

## License

Apache-2.0 - See [LICENSE](LICENSE) for details.
