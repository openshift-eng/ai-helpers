#!/usr/bin/env python3
"""PreToolUse hook that keeps stubbed-Jira evals away from real Jira.

Blocks calls to a real Atlassian MCP server, and network-capable calls (Bash,
WebFetch, WebSearch, other MCP tools) whose input mentions a real Jira host.
Real issues are readable anonymously and would leak the post-refinement state
the eval scores. Jira links in files or stub comments are fine. Exit code 2
blocks the call and returns the reason to the agent.
"""

import json
import re
import sys

REAL_JIRA = re.compile(r"atlassian\.(net|com)|issues\.redhat\.com|jira\.redhat\.com", re.IGNORECASE)
NETWORK_TOOLS = {"Bash", "WebFetch", "WebSearch"}


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    tool = event.get("tool_name", "")
    if tool.startswith("mcp__jira-stub__"):
        return 0
    if tool.startswith("mcp__") and "atlassian" in tool.lower():
        reason = f"{tool} reaches real Jira"
    elif ((tool in NETWORK_TOOLS or tool.startswith("mcp__"))
          and REAL_JIRA.search(json.dumps(event.get("tool_input", {})))):
        reason = "the call references a real Jira host"
    else:
        return 0
    print(f"Blocked by the eval: {reason}. Jira is served only by the jira-stub "
          "MCP server (mcp__jira-stub__*) in this run.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
