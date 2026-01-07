---
description: Analyze Konflux pipeline logs for failures and issues
argument-hint: "[log-file-path]"
---

## Name
konflux:analyze-pipeline-logs

## Synopsis
```
/konflux:analyze-pipeline-logs [log-file-path]
```

## Description
The `konflux:analyze-pipeline-logs` command analyzes logs from a Konflux PipelineRun to identify failures, errors, and potential issues. It provides a structured analysis of what went wrong in the pipeline execution, including:

- Failed tasks and their error messages
- Build failures and compilation errors
- Test failures with relevant stack traces
- Resource/quota issues
- Timeout problems
- Container image pull errors
- Authentication/permission errors
- Policy/compliance violations

The command analyzes locally downloaded log files from Konflux pipelines.

## Implementation

### Step 1: Validate File
- Check if the log file exists and is readable
- If the file doesn't exist, provide a clear error message with the expected path

### Step 2: Use Grep to Search for Failure Patterns
**IMPORTANT**: Do NOT try to read the entire log file with the Read tool, as large log files may exceed token limits. Instead, use the Grep tool to search for specific failure patterns.

Use Grep with multiple searches to find:
- **Critical failures**: Pattern `fatal:|ERRO\[|Error|error occurred|failed|FAILED|make: \*\*\*` with context lines (-C 3 or more)
- **Violations and warnings**: Pattern `Violation|violation|Warning|warning` with context
- **Test failures**: Pattern `FAIL:|FAILED|TEST_OUTPUT|test.*failed` with context
- **Build errors**: Pattern `compilation error|build failed|undefined reference|cannot find` with context
- **Git issues**: Pattern `dubious ownership|Permission denied|fatal:.*git` with context
- **Resource issues**: Pattern `OOMKilled|out of memory|quota exceeded|throttl` with context
- **Image issues**: Pattern `ErrImagePull|ImagePullBackOff|authentication.*fail` with context

**Grep parameters to use**:
- Use `output_mode: "content"` to see the actual log lines
- Use `-i: true` for case-insensitive search when appropriate
- Use `-C: 5` to get 5 lines of context around matches (adjust as needed)
- Use `head_limit` if there are too many matches (e.g., `head_limit: 100`)

### Step 3: Identify Task Sections (if needed)
If the log file is a Tekton pipeline log, use Grep or bash to find task section headers:
- Search for patterns like `^[a-z-]*$` to find task names
- Use these to understand the pipeline structure
- Only use Read with offset/limit if you need to examine specific task sections

### Step 4: Extract Pipeline Context
Use targeted searches to find metadata:
- Pipeline name, namespace, application (search for `pipelinerun|namespace|application`)
- Build/commit information (search for `commit|revision|repository`)
- Overall status (search for `Success:|Result:|Status:`)

### Step 5: Analyze Search Results
Based on the Grep results, identify issues:

- **Build failures**: Compilation errors, missing dependencies, make failures
- **Test failures**: Test framework output, failed assertions, exit codes
- **Image issues**: Pull errors, registry authentication problems
- **Git issues**: Dubious ownership, permission errors
- **Resource issues**: OOM, CPU throttling, quota problems
- **Policy/Conforma violations**: Enterprise Contract policy failures
- **FBC (File-Based Catalog) issues**: Operator catalog validation
- **Release failures**: Release pipeline, admission issues
- **Pipeline/Task failures**: General pipeline issues

**Note**: Only use the Read tool with offset/limit parameters if you need to examine specific sections of the log file after identifying interesting areas with Grep.

### Step 6: Generate Analysis Report
Create a structured report containing:

```markdown
# Konflux Pipeline Log Analysis

## Summary
- **Source**: [log file path]
- **Analysis Date**: [current date]
- **Pipeline**: [pipeline name if identifiable]
- **Overall Status**: [Failed/Succeeded/Running]
- **Issues Found**: [count]

## Identified Issues

### Issue 1: [issue type - e.g., Build Failure, Test Failure, Policy Violation]
- **Severity**: [Critical/High/Medium/Low]
- **Root Cause**: [analysis of what went wrong]

#### Relevant Logs
```
[filtered logs showing the actual error]
```

#### Recommendations
- [actionable steps to fix the issue]

## Next Steps
[Overall recommendations for fixing the pipeline]
```

### Step 7: Save Report
- Save to `.work/konflux-analysis/[log-filename]/analysis.md`
- Display the report to the user
- Provide the path to the saved report

## Return Value
- **Format**: Structured markdown report with pipeline analysis
- **Location**: `.work/konflux-analysis/[log-filename]/analysis.md`
- **Content**: Summary, identified issues/failed tasks, relevant logs, and recommendations

## Examples

1. **Analyze a downloaded log file**:
   ```
   /konflux:analyze-pipeline-logs /path/to/pipeline-logs.txt
   ```
   Analyzes the local log file and generates a comprehensive failure analysis report.

2. **Analyze logs in current directory**:
   ```
   /konflux:analyze-pipeline-logs ./build-failure.log
   ```
   Analyzes a log file in the current working directory.

3. **Analyze a log file with absolute path**:
   ```
   /konflux:analyze-pipeline-logs ~/Downloads/managed-28b42.log
   ```
   Analyzes a pipeline log from the Downloads directory.

## Arguments

- $1: **log-file-path** (required) - Path to the local log file to analyze. Can be absolute or relative path.

## Prerequisites

- Read access to the log file
- Log file should be from a Konflux pipeline (Tekton-based logs)

## Error Handling

- If log file is not found, provide a clear error message with the attempted path
- If log file is not readable, check permissions and provide guidance
- If log file is empty or contains no recognizable patterns, inform the user
- Handle large log files gracefully by using Grep instead of reading the entire file
