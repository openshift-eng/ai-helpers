---
argument-hint: <file|commit>
description: Review code for quality issues, bad patterns, and code smells.
---

## Name
openshift:sniff-test

## Synopsis
```
/openshift:sniff-test <file|commit>
```

## Description

Review code for quality issues, bad patterns, and code smells.

This command accepts a file path or commit hash as an argument to analyze for code quality issues.
Usage: `/openshift:sniff-test path/to/file.go` or `/openshift:sniff-test commit-hash`

## Implementation

The command will analyze the code for:
- Bad patterns or anti-patterns
- Unnecessary or dead code
- Unreferenced functions or variables
- Code duplication
- Functions that should be simplified or refactored
- API fields missing documentation
- Hardcoded values that should be constants
- Unhelpful or misleading comments
- Missing error handling
- Performance issues
- Security vulnerabilities
- Inconsistent naming conventions
- Missing unit tests for public functions

Steps:
1. Determine if the argument is a file path or commit hash
2. If it's a commit hash, get the list of changed files in that commit
3. For each file to analyze:
   - Read the file content
   - Perform static analysis looking for code smells
   - Check for Go-specific issues like inefficient patterns
   - Look for missing documentation on exported types/functions
   - Identify hardcoded values that could be constants
   - Check for unused imports, variables, or functions
   - Look for duplicated code blocks
   - Analyze function complexity and suggest simplifications
4. Generate a comprehensive report with:
   - Summary of issues found
   - Specific line numbers and explanations
   - Suggested improvements
   - Severity levels (critical, major, minor)
   - Best practice recommendations

For Go files, pay special attention to:
- Proper error handling patterns
- Efficient slice/map operations
- Context usage in functions
- Interface design
- Goroutine and channel usage
- Memory allocation patterns
- API design and documentation

The analysis should be constructive and educational, explaining why certain patterns are problematic and how to improve them.
