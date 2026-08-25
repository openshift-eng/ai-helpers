#!/usr/bin/env python3
"""Return whether a PR comment body is only Prow/GitHub slash commands.

Usage:
    printf '%s' "$BODY" | is_slash_command_only.py

Exit:
    0  slash-command-only — skip (not review work)
    1  has review text — keep
    2  usage / empty stdin with no body (treat as skip: not work)
"""

from __future__ import annotations

import re
import sys

HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
COMMAND_LINE_RE = re.compile(r"^/[A-Za-z][A-Za-z0-9_-]*(?:\s.*)?$")


def is_slash_command_only(body: str) -> bool:
    """True when every remaining line is a slash command."""
    stripped = HTML_COMMENT_RE.sub("", body)
    lines = [line.strip() for line in stripped.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return True
    return all(COMMAND_LINE_RE.match(line) for line in lines)


def main() -> int:
    body = sys.stdin.read()
    if is_slash_command_only(body):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
