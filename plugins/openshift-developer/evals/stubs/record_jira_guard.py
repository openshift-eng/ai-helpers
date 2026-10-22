#!/usr/bin/env python3
"""Run the eval's Jira guard and record guard decisions."""

import json
import subprocess
import sys
from pathlib import Path

payload = sys.stdin.read()
event = json.loads(payload)
result = subprocess.run(
    [sys.executable, str(Path.cwd() / "jira_guard.py")],
    input=payload,
    text=True,
    capture_output=True,
)
output = Path.cwd() / "output"
output.mkdir(exist_ok=True)
with (output / "jira-guard-events.jsonl").open("a") as log:
    log.write(
        json.dumps(
            {
                "tool": event.get("tool_name"),
                "blocked": result.returncode == 2,
                "exit_code": result.returncode,
                "reason": result.stderr.strip(),
            }
        )
        + "\n"
    )
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
