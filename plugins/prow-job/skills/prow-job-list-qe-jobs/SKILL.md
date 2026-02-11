---
name: Prow Job list jobs
description: List all jobs for further debugging or analysis
allowed-tools: Read, Grep, Glob
---

## Version History
- v1.0.0 (2025-11-18): Initial release


# Prow Job list jobs

This skill lists all Prow CI jobs by accessing https://qe-private-deck-ci.apps.ci.l2s4.p1.openshiftapps.com/prowjobs.js?var=allBuilds&omit=annotations,labels,decoration_config,pod_spec.

## When to Use This Skill

Use this skill when the user wants to:
- Analyze a batch of CI jobs
- Check which area have been covered
- Share CI jobs

## Prerequisites

Before starting, verify these prerequisites:

1. **Python 3** - For running parser and report generator scripts
2. **Bearer token**  - Export bearer token, the token can be found in https://console-openshift-console.apps.ci.l2s4.p1.openshiftapps.com/topology/all-namespaces?view=graph -> click your name in right-top corner -> click `Copy login command` -> the token can be found in the new page
   - Example: `sha256~_xxxxxxxxxxxxxxxxxxxx`

## Input Format

The user will provide:
1. **Key words** - space-delimited list in format `word1 word2 word3`
   - Example: `release-4.21 upgrade`

## Implementation Steps

### Step 1: Create directory structure

**Usage:**
   ```bash
   mkdir -p .work/prow-job-list-qe-jobs/
   ```

### Step 2: get all jobs data by accessing URL

**Usage:**
```bash
curl -f -H "Authorization: Bearer {LIST_QE_JOBS_BEARER}" \
  -o .work/prow-job-list-qe-jobs/all_jobs.json \
  https://qe-private-deck-ci.apps.ci.l2s4.p1.openshiftapps.com/prowjobs.js?var=allBuilds&omit=annotations,labels,decoration_config,pod_spec

# Verify the download succeeded
if [ ! -s .work/prow-job-list-qe-jobs/all_jobs.json ]; then
  echo "Error: Failed to fetch jobs data. Check your bearer token and network connectivity."
  exit 1
fi
```

### Step 3: filter out the jobs which name contains all keywords

**IMPORTANT: Use the provided shell script `filter_jobs.sh` from the skill directory.**

**Usage:**
```bash
sh plugins/prow-job/skills/prow-job-list-qe-jobs/filter_jobs.sh \
   .work/prow-job-list-qe-jobs/all_jobs.json \
   .work/prow-job-list-qe-jobs/filtered_jobs.json \
   "{KEYWORDS}"
```

### Step 4: Generate HTML Report

**IMPORTANT: Use the provided Python script `generate_report.py` from the skill directory.**

**Usage:**
```bash
python3 plugins/prow-job/skills/prow-job-list-qe-jobs/generate_report.py \
  -t plugins/prow-job/skills/prow-job-list-qe-jobs/template.html \
  -d .work/prow-job-list-qe-jobs/filtered_jobs.json \
  -o .work/prow-job-list-qe-jobs/prow_jobs_report.html \
  -k "{KEYWORDS}"
```

### Step 5: Present Results to User

1. **Open report in browser**
   - Detect platform and automatically open the HTML report in the default browser
   - Linux: `xdg-open .work/prow-job-list-qe-jobs/prow_jobs_report.html`
   - macOS: `open .work/prow-job-list-qe-jobs/prow_jobs_report.html`
   - Windows: `start .work/prow-job-list-qe-jobs/prow_jobs_report.html`
   - On Linux (most common for this environment), use `xdg-open`
