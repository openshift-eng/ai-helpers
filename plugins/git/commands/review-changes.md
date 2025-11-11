---
description: Automated code review analysis for git changes
argument-hint: [--staged|--pr-ready|--commits N]
---

## Name
git:review-changes

## Synopsis
```bash
/git:review-changes                    # Review current working directory changes
/git:review-changes --staged           # Review staged changes only
/git:review-changes --pr-ready         # Generate PR-ready review summary
/git:review-changes --commits N        # Review last N commits
```

## Description
AI-powered code review assistant that analyzes git changes and provides structured feedback on code quality, security, performance, and style. Helps maintain consistent code review standards across development teams.

**Key Features:**
- Security vulnerability detection
- Performance issue identification  
- Code style and best practice recommendations
- Automated review checklist generation
- PR-ready summary formatting

**Use cases:**
- Pre-commit quality checks
- Self-review before creating PRs
- Mentoring and learning from automated feedback
- Ensuring consistent review standards

## Implementation

The command analyzes git changes using multiple review perspectives:

### Step 1: Change Detection
1. Determine scope based on arguments:
   - Default: `git diff HEAD` (all uncommitted changes)
   - `--staged`: `git diff --cached` (staged changes only)
   - `--commits N`: `git diff HEAD~N..HEAD` (last N commits)
2. Extract changed files and diff content
3. Identify file types for language-specific analysis
4. Check for repository conventions (AGENTS.md, CONTRIBUTING.md, etc.)

### Step 2: Multi-Perspective Analysis
Analyze changes from these perspectives:
1. **Repository Conventions Review**
   - Check adherence to AGENTS.md guidelines (if present)
   - Validate plugin structure and naming conventions
   - Review commit message format compliance
   - Ensure ethical guidelines are followed (no real person references)

2. **Security Review**
   - Check for hardcoded secrets/credentials
   - Identify potential injection vulnerabilities
   - Review authentication/authorization changes
   - Flag unsafe file operations

3. **Performance Review** (context-aware)
   - Web/Frontend: Bundle size, render performance, API calls
   - Distributed Systems: Consensus algorithms, network partitions, eventual consistency
   - Microservices: Circuit breakers, retry patterns, service boundaries
   - Database: Query efficiency, indexing, transaction boundaries
   - General: Memory allocation, algorithm complexity

4. **Code Quality Review**
   - Assess code readability and maintainability
   - Check adherence to established patterns
   - Review error handling implementation
   - Validate naming conventions

5. **Testing Coverage**
   - Identify untested code paths
   - Suggest test cases for new functionality
   - Review existing test modifications
   - Check for regression test needs

### Step 3: Generate Structured Report
1. **Summary Section**: High-level change overview
2. **Critical Issues**: Security and performance blockers
3. **Recommendations**: Specific improvement suggestions
4. **Review Checklist**: Items for human reviewers to verify
5. **Test Plan**: Suggested testing approach

### Step 4: Format Output
- `--pr-ready` flag generates markdown formatted for PR descriptions
- Standard output uses terminal-friendly formatting with colors/icons
- Include file references with line numbers for easy navigation

## Examples

```bash
# Review all uncommitted changes
/git:review-changes

# Review only staged files before commit
git add src/auth.ts src/middleware.ts
/git:review-changes --staged

# Generate PR description with review summary
/git:review-changes --pr-ready

# Review changes in last 3 commits
/git:review-changes --commits 3
```

## Return Value

**Standard Format:**
```text
🔍 Code Review Analysis

📋 SUMMARY
- 3 files changed, 45 insertions, 12 deletions
- Languages: TypeScript (2), Markdown (1)
- Scope: Authentication system refactoring

🔴 CRITICAL ISSUES
- src/auth.ts:23 - Potential SQL injection in user query
- src/middleware.ts:45 - Hardcoded API key detected

⚠️  PERFORMANCE CONCERNS  
- src/auth.ts:67 - N+1 query pattern in user lookup
- Consider caching user permissions (lines 89-103)

✅ POSITIVE CHANGES
- Improved error handling in auth flow
- Added comprehensive input validation
- Clear separation of concerns

📝 RECOMMENDATIONS
1. Use parameterized queries for database operations
2. Extract configuration to environment variables  
3. Add rate limiting to authentication endpoints
4. Consider adding integration tests for auth flow

🧪 SUGGESTED TEST PLAN
- [ ] Unit tests for new validation functions
- [ ] Integration tests for auth middleware
- [ ] Security testing for injection vulnerabilities
- [ ] Load testing for performance changes

📁 FILES REVIEWED
- src/auth.ts (32 lines changed)
- src/middleware.ts (13 lines changed)  
- README.md (2 lines changed)
```

**PR-Ready Format (`--pr-ready`):**
```markdown
## Code Review Summary

### Changes Overview
- **Files Modified:** 3 files (2 TypeScript, 1 Markdown)
- **Lines Changed:** +45/-12
- **Scope:** Authentication system refactoring

### Security Review ⚠️
- **CRITICAL**: Potential SQL injection vulnerability in `src/auth.ts:23`
- **HIGH**: Hardcoded credentials in `src/middleware.ts:45`

### Performance Impact ✅
- **CONCERN**: N+1 query pattern detected in user lookup
- **IMPROVEMENT**: Enhanced caching strategy recommended

### Review Checklist
- [ ] Verify database queries use parameterized statements
- [ ] Confirm no hardcoded secrets remain
- [ ] Test authentication flow end-to-end
- [ ] Validate rate limiting implementation

### Test Plan
- Unit tests for validation functions
- Integration tests for middleware  
- Security penetration testing
- Performance benchmark comparison
```

## Important Limitations

**Non-Deterministic Analysis:**
This command uses AI analysis which is inherently non-deterministic. Key considerations:

- **Consistency**: Running the same command multiple times on identical code may produce different feedback
- **Prompt Sensitivity**: Changes to AGENTS.md or other repository conventions may alter analysis behavior  
- **Model Variations**: Different AI models or versions may provide varying recommendations

**Recommended Usage Pattern:**
- **Interactive Pre-Commit Checks**: Best suited for self-review before committing changes
- **Human Oversight Required**: Always apply common sense and domain expertise to suggestions
- **Supplementary Tool**: Use alongside traditional linters, security scanners, and human review
- **Learning Aid**: Treat inconsistencies as opportunities to discuss and refine standards

**Not Recommended For:**
- Automated CI/CD gates without human review
- Security-critical validation as sole verification method  
- Consistent policy enforcement across teams without additional tooling

## Security Guidelines

**The command follows these security principles:**
- Never logs or displays actual secret values
- Provides generic warnings about credential patterns
- Suggests secure alternatives for identified issues
- Focuses on defensive security practices only

## Context-Aware Analysis

**Web/Frontend Systems:**
- Bundle size optimization and lazy loading
- React/Vue component lifecycle issues
- DOM manipulation efficiency
- Browser compatibility concerns

**Distributed/Microservice Systems:**
- CAP theorem considerations (Consistency, Availability, Partition tolerance)
- Service mesh configuration and circuit breakers
- Event sourcing and saga patterns
- Distributed transaction handling
- Network partition resilience

**Database Systems:**
- ACID property maintenance
- Query optimization and indexing strategies
- Connection pooling and resource management
- Migration safety and rollback procedures

**Language-Specific Reviews:**

**TypeScript/JavaScript:**
- ESLint rule violations and TypeScript strict mode
- Async/await patterns and Promise handling
- Package vulnerability checks

**Python:**
- PEP 8 compliance and type hint coverage
- Security best practices (bandit-style checks)
- Concurrent programming patterns

**Go:**
- Go fmt compliance and race condition detection
- Goroutine lifecycle management
- Interface design and error handling patterns

**Rust:**
- Ownership and borrowing correctness
- Memory safety and performance patterns
- Cargo.toml dependency management

**General:**
- Repository convention adherence (AGENTS.md, CONTRIBUTING.md)
- Documentation completeness and accuracy
- Breaking change identification and migration paths

## Arguments

- **--staged**: Review only staged changes (git diff --cached)
- **--pr-ready**: Format output as PR-ready markdown summary
- **--commits N**: Review changes in last N commits (1-20)
- **[default]**: Review all uncommitted changes in working directory

## See Also
- **`/git:commit-suggest`** - Generate conventional commit messages
- **`/git:summary`** - Display repository status and recent commits
- **`/utils:generate-test-plan`** - Create comprehensive test plans