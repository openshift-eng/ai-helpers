---
description: Analyze Claude Code session logs for ai-docs usage patterns
argument-hint: "[-scan] [-project <name>] [-session <path>]"
---

## Name
metrics:ai-docs-telemetry

## Synopsis
```
/metrics:ai-docs-telemetry -scan [-project <name>]
/metrics:ai-docs-telemetry -session <path-to-session.jsonl>
```

## Description
The `metrics:ai-docs-telemetry` command analyzes Claude Code session logs to track how agentic documentation (ai-docs) is used during development. It parses session JSONL files to extract Read tool calls to ai-docs files and generates telemetry events.

This helps measure:
- Documentation effectiveness and usage patterns
- Which files are accessed most frequently
- Entry points for documentation discovery (AGENTS.md, direct search, etc.)
- Navigation paths through documentation

All output is JSON to stdout, making it easy to pipe to `jq` for analysis.

## Implementation
```python
${CLAUDE_PLUGIN_ROOT}/scripts/ai_docs_telemetry.py "$@"
```

The script:
- Parses `~/.claude/projects/` JSONL files
- Detects Read tool calls to files matching `ai-docs/`, `AGENTS.md`, or `CLAUDE.md`
- Tracks access sequence and timestamps
- Identifies entry points (AGENTS.md vs direct search)
- Privacy-first: Only file paths tracked, no code/prompts/user data

## Return Value
- **JSON**: Single event or array of events
- **Summary**: Printed to stderr with session counts

## Examples

1. **Scan all recent sessions (last 7 days)**:
   ```
   /metrics:ai-docs-telemetry -scan
   ```
   Output:
   ```json
   [
     {
       "event_type": "ai_docs_usage",
       "session_id": "a0350e3f-1853-4a56-be01-865cd0df1944",
       "documentation": {
         "entry_point": "AGENTS.md",
         "files_accessed": [...],
         "total_files": 5
       }
     }
   ]
   ```

2. **Scan only enhancements repository**:
   ```
   /metrics:ai-docs-telemetry -scan -project enhancements
   ```

3. **Scan only machine-config-operator repository**:
   ```
   /metrics:ai-docs-telemetry -scan -project machine-config-operator
   ```

4. **Analyze a specific session**:
   ```
   /metrics:ai-docs-telemetry -session ~/.claude/projects/<project>/<session-id>.jsonl
   ```

5. **Pipe to jq for analysis**:
   ```bash
   # Count files by entry point
   /metrics:ai-docs-telemetry -scan | jq -r '.[] | "\(.documentation.entry_point): \(.documentation.total_files)"'
   
   # List most accessed files
   /metrics:ai-docs-telemetry -scan | jq -r '.[] | .documentation.files_accessed[].path' | sort | uniq -c | sort -rn
   
   # Filter sessions with >5 files accessed
   /metrics:ai-docs-telemetry -scan | jq '.[] | select(.documentation.total_files > 5)'
   ```

## Arguments
- `-scan`: Scan all recent Claude Code sessions (last 7 days)
- `-project <name>`: Filter sessions by project name (e.g., "enhancements", "machine-config-operator")
- `-session <path>`: Analyze a specific session JSONL file

## Related
- Session hooks: `metrics` plugin's `SessionEnd` hook
- General metrics: `send_session_metrics.py`
