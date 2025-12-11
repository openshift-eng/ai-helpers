---
description: List all OpenShift QE CI jobs with optional filtering
argument-hint: keywords
---

## Name
prow-job:list-qe-jobs

## Synopsis
```
/prow-job:list-qe-jobs [keywords]
```

## Description
OpenShift QE often needs to debug ci job failures, get fault trends, the first step is to get job names and job links.

## Implementation
Pass the user's request to the skill, which will:
- Load environment variable "LIST_QE_JOBS_BEARER"
- If environment variable "LIST_QE_JOBS_BEARER" is not given, ask user to give one, otherwise stop the skill
- Access https://qe-private-deck-ci.apps.ci.l2s4.p1.openshiftapps.com/prowjobs.js?var=allBuilds&omit=annotations,labels,decoration_config,pod_spec API with above environment variable LIST_QE_JOBS_BEARER as bearer token and list all [spec/job, status/url, status/state] in the response json. 
- Accepts an optional name argument ($1)
- If $1 is provided, "$1" is a space-delimited list of words, outputs all jobs whose name contains each word in "$1"
- If no argument is provided, outputs all jobs
- Get all job names, URL and state
- Generate an interactive HTML report which can filter jobs by job name
- The command is stateless and has no side effects

The skill handles all the implementation details including extract data from URL and HTML report generation.
