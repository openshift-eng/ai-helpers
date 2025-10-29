# Prow Job Plugin

Analyze and inspect Prow CI job results for OpenShift development.

## Commands

### `/prow-job:analyze-test-failure`

Analyze a failed Prow test job and generate a detailed failure report.

### `/prow-job:analyze-resource`

Analyze Kubernetes resources from a Prow job to debug issues.

Generates interactive HTML reports with resource timelines, logs, and events.

### `/prow-job:extract-must-gather`

Extract and analyze must-gather archives from Prow job artifacts.

## Skills

This plugin includes advanced skills with Python helper scripts for log analysis and report generation. See the [skills/](skills/) directory for detailed implementation guides.

## Installation

```bash
/plugin install prow-job@ai-helpers
```

