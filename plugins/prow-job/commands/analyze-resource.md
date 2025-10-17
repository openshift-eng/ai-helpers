---
description: Analyze Kubernetes resource lifecycle in Prow job artifacts
argument-hint: prowjob-url resource-name
---

Analyze the lifecycle of Kubernetes resource(s) in a Prow CI job by invoking the "Prow Job Analyze Resource" skill.

Pass the user's request to the skill, which will:
- Download Prow job artifacts from Google Cloud Storage
- Parse audit logs and pod logs
- Generate an interactive HTML report with timeline visualization

The skill handles all the implementation details including URL parsing, artifact downloading, log parsing, and HTML report generation.
