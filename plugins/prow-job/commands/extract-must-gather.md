---
description: Extract and decompress must-gather archives from Prow job artifacts
argument-hint: prowjob-url
---

Extract the must-gather archive from a Prow CI job by invoking the "Prow Job Extract Must-Gather" skill.

Pass the user's request to the skill, which will:
- Download the must-gather.tar from Google Cloud Storage
- Extract and recursively decompress all nested archives
- Generate an interactive HTML file browser with filters

The skill handles all the implementation details including URL parsing, artifact downloading, archive extraction, and HTML report generation.
