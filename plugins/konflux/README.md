# Konflux Plugin

Tools for analyzing and debugging Konflux CI/CD pipelines.

## Overview

The Konflux plugin provides commands to help developers debug and analyze pipeline failures in Konflux clusters. It automates the process of analyzing pipeline logs, identifying failures, and providing actionable recommendations.

## Prerequisites

- Access to Konflux pipeline log files
- Log files should be downloaded from the Konflux UI or via kubectl/oc CLI

## Available Commands

### `/konflux:analyze-pipeline-logs`

Analyzes Konflux pipeline log files to identify root causes of failures.

**Usage:**
```
/konflux:analyze-pipeline-logs [log-file-path]
```

**What it does:**
1. Reads and parses the pipeline log file
2. Identifies failed tasks and their error messages
3. Extracts and analyzes error patterns from the logs
4. Generates a comprehensive analysis report with recommendations
5. Saves the report to `.work/konflux-analysis/[log-filename]/analysis.md`

**Examples:**
```
# Analyze a log file in current directory
/konflux:analyze-pipeline-logs ./managed-28b42.log

# Analyze a log file with full path
/konflux:analyze-pipeline-logs ~/Downloads/pipeline-logs.txt
```

**Output:**
- Structured analysis report identifying:
  - Failed tasks and error messages
  - Root causes (build errors, test failures, resource issues, etc.)
  - Relevant log excerpts
  - Actionable recommendations for fixing the issues

## Common Use Cases

1. **Quick Pipeline Debugging**: When a pipeline fails, download the logs and use this command to get a comprehensive analysis instead of manually checking each task's logs

2. **Build Failure Analysis**: Automatically extracts compilation errors and dependency issues from build task logs

3. **Test Failure Investigation**: Identifies test failures with stack traces and assertion errors

4. **Policy Violation Analysis**: Identifies Enterprise Contract policy violations and provides guidance on resolution

5. **Resource Issue Detection**: Detects out-of-memory errors, quota issues, and timeout problems

6. **Image Pull Debugging**: Identifies container image pull errors and registry authentication issues

## Getting Pipeline Logs

You can obtain pipeline logs from Konflux in several ways:

**Option 1: Download from Konflux UI**
1. Navigate to your pipeline run in the Konflux UI
2. Click on the download/export logs button
3. Save the log file locally

**Option 2: Use kubectl/oc CLI**
```bash
# Get logs from a PipelineRun
kubectl logs -n <namespace> -l tekton.dev/pipelineRun=<pipelinerun-name> --all-containers > pipeline.log

# Or using oc
oc logs -n <namespace> -l tekton.dev/pipelineRun=<pipelinerun-name> --all-containers > pipeline.log
```

## Output Location

All analysis reports are saved to:
```
.work/konflux-analysis/[log-filename]/analysis.md
```

This directory is automatically created if it doesn't exist and is included in `.gitignore`.

## Tips

- Download logs as soon as possible after a failure, as they may be purged after the retention period
- The command handles large log files efficiently by using pattern matching instead of loading the entire file
- Reports can be shared with team members or attached to bug reports

## Future Commands

Planned additions to this plugin:
- `/konflux:list-recent-failures` - List recent pipeline failures in a namespace
- `/konflux:compare-runs` - Compare two pipeline runs to identify differences
- `/konflux:watch-pipeline` - Monitor a running pipeline with live updates
- `/konflux:retry-failed-tasks` - Retry only the failed tasks in a pipeline

## Contributing

To add new commands to this plugin, create a new markdown file in `plugins/konflux/commands/` following the command definition format described in [AGENTS.md](../../AGENTS.md).
