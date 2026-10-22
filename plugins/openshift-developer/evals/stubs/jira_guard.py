#!/usr/bin/env python3
"""PreToolUse hook that keeps stubbed-Jira evals away from real Jira.

Blocks calls to a real Atlassian MCP server, and network-capable calls (Bash,
WebFetch, WebSearch, other MCP tools) whose input mentions a real Jira host.
Real issues are readable anonymously and would leak the post-refinement state
the eval scores. Jira links in files or stub comments are fine. A case can also
block material published after its snapshot, such as a fix pull request, from
its jira-fixture.json: "blocked_research" lists regexes, and
"blocked_research_sha256" lists SHA-256 digests of lowercase tokens (a PR
number, a fork owner, a branch) so the workspace does not reveal them. Network
calls that match are blocked too. Exit code 2 blocks the call and returns the
reason to the agent.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

REAL_JIRA = re.compile(r"atlassian\.(net|com)|issues\.redhat\.com|jira\.redhat\.com", re.IGNORECASE)
NETWORK_TOOLS = {"Bash", "WebFetch", "WebSearch"}
FIXTURE = Path(__file__).resolve().parent / "jira-fixture.json"
TOKEN = re.compile(r"[\w.\-/]+")


def blocked_research():
    try:
        fixture = json.loads(FIXTURE.read_text())
    except (OSError, ValueError):
        return [], set()
    patterns = [re.compile(p, re.IGNORECASE) for p in fixture.get("blocked_research", [])]
    return patterns, set(fixture.get("blocked_research_sha256", []))


def hashed_tokens(text):
    """Digests of each token, its /-separated parts, and adjacent part pairs."""
    for token in TOKEN.findall(text.lower()):
        parts = token.split("/")
        for candidate in {token, *parts, *("/".join(parts[i:i + 2]) for i in range(len(parts) - 1))}:
            yield hashlib.sha256(candidate.encode()).hexdigest()


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    tool = event.get("tool_name", "")
    # Codex reports MCP tools with the server name's hyphens as underscores.
    if tool.replace("-", "_").startswith("mcp__jira_stub__"):
        return 0
    network = tool in NETWORK_TOOLS or tool.startswith("mcp__")
    tool_input = json.dumps(event.get("tool_input", {}))
    if tool.startswith("mcp__") and "atlassian" in tool.lower():
        reason = f"{tool} reaches real Jira"
    elif network and REAL_JIRA.search(tool_input):
        reason = "the call references a real Jira host"
    else:
        patterns, digests = blocked_research() if network else ([], set())
        leak = next((p.pattern for p in patterns if p.search(tool_input)), None)
        if leak is None and digests and not digests.isdisjoint(hashed_tokens(tool_input)):
            leak = "a blocked reference"
        if leak is None:
            return 0
        print(f"Blocked by the eval: the call matches {leak!r}, which this case reserves "
              "for material published after its snapshot.", file=sys.stderr)
        return 2
    print(f"Blocked by the eval: {reason}. Jira is served only by the jira-stub "
          "MCP server (mcp__jira-stub__*) in this run.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
