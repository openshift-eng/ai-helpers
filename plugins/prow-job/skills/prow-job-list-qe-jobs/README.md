# Prow Job List Job Skill

This skill lists all Prow CI jobs by accessing https://qe-private-deck-ci.apps.ci.l2s4.p1.openshiftapps.com/prowjobs.js?var=allBuilds&omit=annotations,labels,decoration_config,pod_spec.

## Overview

The skill provides a Claude Code skill interface for listing Prow CI jobs. It helps get current test coverage and job status.

## Components

### 1. SKILL.md
Claude Code skill definition that provides detailed implementation instructions for the AI assistant.

### 2. Python Scripts

#### generate_report.py
Generates interactive HTML reports from parsed job data.
- Get job data from https://qe-private-deck-ci.apps.ci.l2s4.p1.openshiftapps.com/prowjobs.js?var=allBuilds&omit=annotations,labels,decoration_config,pod_spec
- Fill job data into html
- Creates interactive filterable table
- Adds filtering and search capabilities

**Usage:**
```bash
python3 plugins/prow-job/skills/prow-job-list-qe-jobs/generate_report.py \
  -t plugins/prow-job/skills/prow-job-list-qe-jobs/template.html \
  -d .work/prow-job-list-qe-jobs/filtered_jobs.json \
  -o .work/prow-job-list-qe-jobs/prow_jobs_report.html \
  -k "{KEYWORDS}"
```

### 3. HTML Template

#### template.html
Modern, responsive HTML template for reports featuring:
- Color-coded job state
- Filtering by job state
- Search functionality
- Mobile-responsive design

## Prerequisites

1. **Python 3**      - For running parser and report generator scripts
2. **Bearer token**  - Export bearer token, the token can be found in https://console-openshift-console.apps.ci.l2s4.p1.openshiftapps.com/topology/all-namespaces?view=graph -> click your name in right-top corner -> click `Copy login command` -> the token can be found in the new page

## Workflow

1. **Get Data**
   - Access https://qe-private-deck-ci.apps.ci.l2s4.p1.openshiftapps.com/prowjobs.js?var=allBuilds&omit=annotations,labels,decoration_config,pod_spec
   - Extract [spec/job, status/url, status/state] from the response json

2. **Report Generation**
   - Render HTML with template
   - Output to `.work/prow-job-list-qe-jobs/prow_jobs_report.html`

## Output

### HTML Report
- Header with metadata
- Filterable job entries
- Search functionality

### Directory Structure
```
.
└── prow-job-list-qe-jobs
    ├── all_jobs.json
    ├── filtered_jobs.json
    ├── prow_jobs_report.html
```

## Using with Claude Code

When you ask Claude to list Prow jobs, it will automatically use this skill. The skill provides detailed instructions that guide Claude through:
- Give keywords if needed
- Generating reports

You can simply ask:
> "List all prow jobs whose names contain release-4.21 and upgrade"
Or
> /prow-job:list-qe-jobs "release-4.21 upgrade"

Claude will execute the workflow and generate the interactive HTML report.
