# prow-agent

Hooks and utilities for Claude Code sessions running inside Prow CI jobs.

## Session Metrics (Stop Hook)

Automatically extracts cost, token, duration, and tool-usage metrics from a
Claude session and writes an autodl JSON file for BigQuery ingestion.

### How it works

A Stop hook fires at the end of every `claude -p` invocation. It reads the
streaming output log, extracts aggregate metrics (including subagents), and
writes a `claude-session-metrics-autodl.json` file.

The hook requires two environment variables:
- `ARTIFACT_DIR` — where to write the autodl output
- `CLAUDE_OUTPUT_LOG` — path to the streaming output log (`--output-format stream-json`)

If either is unset, the hook is a silent no-op — so it does nothing during
interactive use.

For CI jobs that use `--continue`, the hook fires after each invocation and
overwrites the output file. The final run produces the authoritative result since
the `result` message accumulates totals across the full session.

### Setup

```bash
export CLAUDE_OUTPUT_LOG="${ARTIFACT_DIR}/claude-output.log"
claude -p "..." --output-format stream-json 2>&1 | tee "${CLAUDE_OUTPUT_LOG}"
```

In Prow jobs, `ARTIFACT_DIR` is already set. The autodl file will appear at
`${ARTIFACT_DIR}/claude-session-metrics-autodl.json`.

### Standalone usage

The extraction script can also be run directly:

```bash
python3 hooks/scripts/extract_metrics.py <claude-output.log> [output.json]
```
