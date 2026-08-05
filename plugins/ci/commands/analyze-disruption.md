---
description: Analyze and compare disruption across one or more Prow CI job runs
argument-hint: <prowjob-or-grafana-url> [...] [--backends backend1,...] [--skip-jira]
---

## Name
ci:analyze-disruption

## Synopsis
Analyze disruption events across one or more CI job runs, comparing backends to identify root causes:
```text
/ci:analyze-disruption <prowjob-url-1> [prowjob-url-2 ...] [--backends backend1,backend2,...] [--skip-jira]
```

Also accepts a Grafana disruption dashboard URL instead of Prow URLs to discover and select runs automatically:
```text
/ci:analyze-disruption <grafana-dashboard-url> [--backends backend1,backend2,...] [--skip-jira]
```

## Description
Analyze disruption recorded in Prow CI job runs by invoking the "analyze-disruption" skill.

## Implementation
Pass the user's request to the skill, which will:
- Parse Prow URLs or resolve Grafana dashboard URLs to candidate job runs
- Download timeline/interval data, audit logs, and pod logs
- Classify disruption by backend type and correlate with cluster activity
- Generate a structured Markdown report with root cause hypothesis and team routing

The skill handles all implementation details including artifact downloading, disruption parsing, cross-run comparison, and Jira integration.
