# Prow Job Analyze Test Failure Skill

This skill analyzes the given test failure by downloading artifacts using the "Prow Job Analyze Resource" skill, checking test logs, inspecting resources, logs and events from the artifacts. The skill also checks the test source code.

## Overview

The skill provides both a Claude Code skill interface for analyzing Prow CI job results including test logs.

## Components

### 1. SKILL.md
Claude Code skill definition that provides detailed implementation instructions for the AI assistant.

## Prerequisites

1. **Python 3** - For running parser and report generator scripts
2. **gcloud CLI** - For downloading artifacts from GCS
   - Install: https://cloud.google.com/sdk/docs/install
   - Authenticate: `gcloud auth login`
3. **jq** - For JSON processing (used in bash script)
4. **Access to test-platform-results GCS bucket**

## Workflow

1. **URL Parsing**
   - Validate URL contains `test-platform-results/`
   - Extract build_id (10+ digits)
   - Extract prowjob name
   - Construct GCS paths

2. **Working Directory**
   - Create `{build_id}/logs/` directory
   - Check for existing artifacts (offers to skip re-download)

3. **prowjob.json Validation**
   - Download prowjob.json
   - Search for `--target=` pattern
   - Exit if not a ci-operator job

4. **Analyze Test Failure**

6. **Report Generation**

## Using with Claude Code

When you ask Claude to analyze a Prow job, it will automatically use this skill. The skill provides detailed instructions that guide Claude through:
- Validating prerequisites
- Parsing URLs
- Downloading artifacts
- Analyzing test failure
- Generating reports

You can simply ask:
> "Analyze test failure XYZ in this Prow job: https://gcsweb-ci.../1978913325970362368/"

Claude will execute the workflow and generate a text report

## Troubleshooting

### gcloud authentication
```bash
gcloud auth login
gcloud auth list  # Verify active account
```

### Missing artifacts
- Verify job completed successfully
- Check target name is correct

### Permission denied
- Verify access to test-platform-results bucket
- Check gcloud project configuration
