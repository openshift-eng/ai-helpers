---
description: Get coding challenges based on the current codebase to practice and test your skills
argument-hint: "[topic-or-difficulty]"
---

## Name
myga:challenge

## Synopsis
```
/myga:challenge [topic-or-difficulty]
```

## Description
The `myga:challenge` command generates hands-on coding challenges tailored to your codebase. Challenges are realistic programming tasks that test your understanding and help build mastery through practice.

Each challenge includes:
- **Clear objective** - What to build or fix
- **Context** - Why this matters in the codebase
- **Constraints** - Requirements and limitations
- **Starter code** - Foundation to build upon
- **Tests** - Automated verification of your solution
- **Hints** - Progressive help if you get stuck
- **Solution review** - Detailed feedback on your approach

This command is particularly useful for:
- Practicing concepts in a real codebase context
- Testing your understanding after learning sessions
- Building muscle memory for common patterns
- Interview preparation using your own code
- Deliberate practice on weak areas

## Implementation

### Phase 1: Challenge Selection

1. **Determine challenge parameters**
   - If no argument: Offer challenge menu
   - If topic specified: Generate challenge for that topic
   - If difficulty specified: Generate challenge at that level (easy/medium/hard)
   - If both specified: Use both filters

2. **Analyze codebase for challenge opportunities**
   - Identify common patterns that can be practiced
   - Find areas where new code could be added
   - Detect potential refactoring opportunities
   - Locate code that demonstrates key concepts

3. **Check user progress**
   - Load from `.work/myga/<topic>/progress.json` if exists
   - Recommend challenges based on completed lessons
   - Suggest appropriate difficulty level
   - Avoid recently completed challenges

### Phase 2: Challenge Generation

1. **Select challenge type**
   - **Feature Implementation**: Add new functionality
   - **Bug Fix**: Fix broken code
   - **Refactoring**: Improve existing code
   - **Optimization**: Make code faster/more efficient
   - **Testing**: Write tests for untested code
   - **Code Reading**: Understand and explain code
   - **Design**: Architect a solution

2. **Create challenge specification**
   ```markdown
   # Challenge: [Name]
   
   **Topic**: [Topic]
   **Difficulty**: ⭐⭐☆ (Medium)
   **Estimated Time**: 30-45 minutes
   **Skills Practiced**: [List of skills]
   
   ## Objective
   [Clear description of what to accomplish]
   
   ## Context
   [Why this matters in the codebase]
   
   ## Requirements
   1. [Specific requirement]
   2. [Specific requirement]
   3. [Specific requirement]
   
   ## Starting Point
   File: [path/to/file.go]
   [Provide starter code or point to existing code]
   
   ## Acceptance Criteria
   - [ ] [Criterion 1]
   - [ ] [Criterion 2]
   - [ ] Tests pass
   ```

3. **Prepare test cases**
   - Create automated tests for challenge
   - Save to `.work/myga/challenges/<challenge-id>/test.go`
   - Tests should validate the solution
   - Include edge cases and error conditions

### Phase 3: Challenge Presentation

1. **Display challenge**
   ```
   🎯 Challenge: Implement Request Timeout Middleware
   
   **Topic**: HTTP Middleware Patterns
   **Difficulty**: ⭐⭐☆ (Medium)
   **Estimated Time**: 30 minutes
   **Skills**: Context, Error Handling, HTTP
   
   ## Your Mission
   
   Add timeout protection to the HTTP server by implementing a
   middleware that cancels requests exceeding a duration threshold.
   
   ## Context
   
   The API server (api/server.go) currently has no timeout protection.
   Long-running requests can exhaust server resources. You'll implement
   a middleware that wraps handlers with timeout logic.
   
   ## Requirements
   
   1. Create middleware that accepts a duration parameter
   2. Use context.WithTimeout for request cancellation
   3. Return 503 Service Unavailable on timeout
   4. Log timeout events
   5. Pass through non-timeout requests unchanged
   
   ## Starting Code
   
   I've created a starter file for you:
   .work/myga/challenges/timeout-middleware/middleware.go
   
   Review it and implement the TimeoutMiddleware function.
   
   ## How to Test
   
   Run: go test .work/myga/challenges/timeout-middleware/
   
   Ready to start? Say "show me the code" or "I need a hint"
   ```

2. **Provide starter code**
   - Create challenge directory structure
   - Generate partial implementation with TODOs
   - Include test file with test cases
   - Add helpful comments and hints

### Phase 4: Interactive Assistance

1. **Progressive hints system**
   ```
   User: "I need a hint"
   
   💡 Hint 1/5: Think about how you can wrap the existing handler
   with a new function. The middleware pattern uses function composition.
   
   Need another hint? Just ask!
   ```
   
   - Hint 1: High-level approach
   - Hint 2: Specific direction
   - Hint 3: Code structure suggestion
   - Hint 4: Almost complete example
   - Hint 5: Full solution with explanation

2. **Answer questions**
   - Clarify requirements
   - Explain relevant concepts
   - Help debug issues
   - Provide documentation links

3. **Code review**
   ```
   User: "Here's my solution: [code]"
   
   📝 Code Review
   
   ✅ Excellent: You correctly used context.WithTimeout
   ✅ Good: Error handling follows project conventions
   ⚠️  Improvement: Consider extracting the timeout duration to a constant
   ❌ Issue: The response code should be 503, not 500
   
   Let me explain the 503 vs 500 distinction...
   
   Would you like to revise or move on?
   ```

4. **Run tests and provide feedback**
   - Execute test suite if user provides solution
   - Show test results with clear pass/fail
   - Explain why tests failed if applicable
   - Celebrate successes

### Phase 5: Solution Review and Learning

1. **Show exemplary solution**
   ```
   🌟 Exemplary Solution
   
   Here's a well-crafted implementation:
   
   [Show clean, idiomatic solution]
   
   Key Points:
   - Uses context properly
   - Handles errors gracefully
   - Follows project patterns
   - Well documented
   
   How does this compare to your approach?
   ```

2. **Discuss tradeoffs**
   - Compare different approaches
   - Explain design decisions
   - Discuss performance implications
   - Highlight edge cases

3. **Suggest related challenges**
   ```
   🎯 Related Challenges You Might Like:
   
   1. "Rate Limiting Middleware" (Medium)
      - Builds on timeout concepts
      - Adds token bucket algorithm
   
   2. "Circuit Breaker Pattern" (Hard)
      - Advanced failure handling
      - Stateful middleware
   
   3. "Middleware Composition" (Medium)
      - Combine multiple middleware
      - Order and precedence
   
   Try one? Or /myga:path to see your roadmap
   ```

4. **Update progress**
   - Mark challenge as completed
   - Update skill ratings
   - Save to `.work/myga/challenges/progress.json`

## Challenge Difficulty Levels

### ⭐ Easy (15-20 minutes)
- Single concept focus
- Clear, specific task
- Minimal code changes
- Examples: Add validation, format output, simple refactor

### ⭐⭐ Medium (30-45 minutes)
- Multiple concepts combined
- Requires design thinking
- Moderate complexity
- Examples: Implement feature, optimize algorithm, write middleware

### ⭐⭐⭐ Hard (60-90 minutes)
- Complex problem solving
- Architectural decisions
- Multiple components
- Examples: Design subsystem, refactor architecture, solve distributed problem

## Return Value

- **Challenge Specification**: Detailed description of the task
- **Starter Code**: Files in `.work/myga/challenges/<challenge-id>/`
- **Tests**: Automated test suite
- **Solution Review**: Detailed feedback on submitted solutions
- **Progress Update**: Updated skill tracking

## Examples

### Example 1: Get a random challenge

```bash
/myga:challenge
```

**Output:**
```
🎲 Let me find a good challenge for you...

Based on your progress, I recommend:

🎯 Challenge: Add Retry Logic to API Client

**Topic**: Error Handling & Resilience
**Difficulty**: ⭐⭐☆ (Medium)
**Estimated Time**: 40 minutes
**Skills**: Error handling, Exponential backoff, HTTP

Your mission: The API client (pkg/client/client.go) fails
immediately on network errors. Add retry logic with exponential
backoff for transient failures.

Want to try this? Or say "show me other options"
```

### Example 2: Request specific topic

```bash
/myga:challenge kubernetes
```

**Output:**
```
🎯 Kubernetes Challenge: Implement Leader Election

**Difficulty**: ⭐⭐⭐ (Hard)
**Estimated Time**: 60-75 minutes
**Skills**: Kubernetes client-go, Concurrency, Distributed Systems

## Objective

Implement leader election for the controller to ensure only
one instance is active in a multi-replica deployment.

## Context

The etcd controller (controllers/etcd_controller.go) doesn't
currently support multiple replicas. Without leader election,
multiple controllers would conflict when modifying resources.

## Requirements

1. Use client-go's leader election package
2. Acquire lease before starting reconciliation
3. Release lease on shutdown
4. Implement leader lost handling
5. Add metrics for leadership status

## Starting Point

I've created starter code at:
.work/myga/challenges/leader-election/

Files:
- election.go (implement LeaderElector)
- election_test.go (tests to pass)
- main.go (integration example)

Ready to begin? Let me know if you need hints!
```

### Example 3: Request specific difficulty

```bash
/myga:challenge hard
```

**Output:**
```
🎯 Hard Challenge: Implement Distributed Cache

**Topic**: Distributed Systems
**Difficulty**: ⭐⭐⭐ (Hard)
**Estimated Time**: 90 minutes

## Objective

Design and implement a distributed in-memory cache with
consistent hashing and replication.

## Requirements

1. Consistent hashing for key distribution
2. Replication factor of 3
3. Read-your-writes consistency
4. Handle node failures gracefully
5. Implement cache eviction (LRU)

This challenge tests:
- Distributed systems thinking
- Concurrency control
- Network protocols
- Data structures

Are you ready for this challenge?
```

### Example 4: Interactive session

```bash
/myga:challenge "error wrapping"
```

**Output:**
```
🎯 Challenge: Fix Error Wrapping in Storage Layer

**Difficulty**: ⭐☆☆ (Easy)
**Estimated Time**: 15 minutes
**Skills**: Error handling, Error wrapping, fmt.Errorf

## Your Mission

The storage layer has inconsistent error handling. Fix the
error wrapping to preserve error context properly.

## File to Fix

pkg/storage/storage.go (lines 45-80)

I've copied it to:
.work/myga/challenges/error-wrapping/storage.go

## Problems to Fix

1. Line 52: Error is formatted but not wrapped
2. Line 67: Context is lost when returning error
3. Line 73: Missing error context entirely

## Tests

Run: go test .work/myga/challenges/error-wrapping/

Currently: 0/3 tests passing
Fix the code to make all tests pass!

---

> [User works on it and submits]

User: "Here's my fix: [shows code]"

📝 Code Review:

✅ Line 52: Perfect! You used %w to wrap the error
✅ Line 67: Great! Added context while preserving the chain
❌ Line 73: You added context, but forgot to wrap the original error

Try fixing line 73 with %w instead of %v

> [User fixes]

User: "Updated!"

🎉 Excellent! All tests passing!

💡 Key Takeaway: Always use %w when you want to preserve
error chains for later inspection with errors.Is() or errors.As().

Your solution follows the project's error handling conventions perfectly.

📊 Challenge Complete!
- Attempts: 2
- Time: 12 minutes
- Hints used: 0

🎯 Next Challenge Suggestion:
"Custom Error Types" - Build on error handling skills
Try it? (/myga:challenge "custom error types")
```

## Arguments

- **[topic-or-difficulty]** *(optional)*
  - Topic: Generate challenge for specific topic (e.g., `"kubernetes"`, `"testing"`)
  - Difficulty: `easy`, `medium`, `hard`
  - Both: `"kubernetes hard"` or `"testing easy"`
  - If omitted: Recommend challenge based on progress

## Prerequisites

- Works in any codebase
- For best results: Have relevant files for the challenge topic
- Tests require language-specific tooling (go test, npm test, etc.)

## Best Practices

1. **Actually code it**: Don't just read - implement the solution
2. **Try before hints**: Struggle a bit before asking for help
3. **Run the tests**: Use automated tests to verify your solution
4. **Review the exemplary solution**: Even if you solved it, compare approaches
5. **Do multiple challenges**: Repetition builds mastery
6. **Time yourself**: Treat it like real problem-solving practice
7. **Document your learning**: Add comments explaining your reasoning

## Challenge Types

| Type | Description | Example |
|------|-------------|---------|
| **Feature** | Implement new functionality | "Add pagination to API" |
| **Bug Fix** | Fix intentionally broken code | "Fix race condition" |
| **Refactor** | Improve code quality | "Extract interface" |
| **Optimization** | Improve performance | "Optimize database query" |
| **Testing** | Write comprehensive tests | "Test edge cases" |
| **Reading** | Understand and explain code | "Explain reconciliation loop" |
| **Design** | Architect a solution | "Design caching layer" |

## See Also

- `/myga:start` - Interactive learning sessions
- `/myga:assess` - Test your knowledge comprehensively
- `/myga:path` - View your learning roadmap
- `/git:feature-summary` - Analyze code changes



