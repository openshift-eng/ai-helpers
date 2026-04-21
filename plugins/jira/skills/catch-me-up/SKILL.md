---
name: Catch Me Up
description: Gather and classify recent Jira activity to surface what needs attention
---

# Catch Me Up

Gathers recent Jira activity (changelogs and comments) for issues where the user is assignee or watcher, then classifies events into three tiers: needs attention, unsure, or noise.

## Scripts

- `scripts/gather.py` — Fetches events from Jira REST API. Requires `aiohttp`. Outputs JSON to `.work/catch-me-up/runs/{date}-{days}d/events.json`. Caches by date and lookback window.
- `scripts/split_batches.py` — Splits gathered events into batch files for parallel classification.

## Usage

Invoked by the `/jira:catch-me-up` command. Not intended for standalone use.
