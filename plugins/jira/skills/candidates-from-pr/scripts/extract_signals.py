#!/usr/bin/env python3
"""Extract triage signals from a PR's title, body, commits, files, and diff.

Reads PR JSON (fetch_pr.py output) on stdin and emits a JSON object with
typed signal arrays. All extraction is local regex/string work — no API
calls and no model judgement.

Usage:
    fetch_pr.py ... | extract_signals.py

Output:
    {
      "symbols":        [{"value": "ensureSubnet"}, ...],
      "error_strings":  [{"value": "failed to add subnet"}, ...],
      "log_messages":   [{"value": "..."}, ...],
      "labels":         [{"value": "kind/bug"}, ...],
      "title_keywords": [{"value": "subnet"}, ...],
      "path_tags":      [{"value": "subnet"}, ...]
    }
"""

from __future__ import annotations

import json
import re
import sys

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "of", "for", "to", "in", "on",
    "with", "from", "by", "is", "are", "was", "were", "be", "been", "fix",
    "fixes", "bug", "bugs", "add", "adds", "added", "remove", "removes",
    "removed", "update", "updates", "updated", "use", "uses", "using",
    "this", "that", "these", "those", "into", "make", "makes", "made",
    "merge", "branch", "master", "main", "feat", "feature", "chore", "docs",
    "doc", "test", "tests", "ci", "build", "release", "version", "support",
    "no-jira", "downstream", "upstream",
}

GO_FUNC_RE = re.compile(r"^\+.*\bfunc\s+(?:\(\s*\w+\s+\*?\w+\s*\)\s+)?(\w+)\s*\(", re.M)
GO_TYPE_RE = re.compile(r"^\+.*\btype\s+(\w+)\s+(?:struct|interface)\b", re.M)
ERR_NEW_RE = re.compile(r'errors\.New\(\s*"([^"]{4,200})"\s*\)')
FMT_ERRORF_RE = re.compile(r'fmt\.Errorf\(\s*"([^"]{4,200})"')
LOG_RE = re.compile(
    r'(?:klog|log|logger|logrus)\.[A-Za-z]+\(\s*"([^"]{12,200})"'
)
PANIC_RE = re.compile(r'panic\(\s*"([^"]{4,200})"\s*\)')

# Identifier extraction from added lines (lines starting with '+').
CAMEL_RE = re.compile(r"\b([A-Z][a-zA-Z0-9]{3,})\b")
SNAKE_RE = re.compile(r"\b([a-z][a-zA-Z0-9_]{4,})\b")

# Identifiers we never want to treat as signals (too generic to be useful).
SYMBOL_BLOCKLIST = {
    "string", "error", "context", "Context", "true", "false", "nil",
    "return", "interface", "struct", "package", "import", "func",
    "default", "switch", "select", "channel", "range", "map", "make",
    "panic", "recover", "println", "Sprintf", "Errorf",
}


def added_lines(diff: str) -> str:
    """Return only the '+ ...' added lines from a unified diff."""
    out: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            out.append(line[1:])
    return "\n".join(out)


def uniq(items: list[str], cap: int | None = None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
        if cap and len(out) >= cap:
            break
    return out


def extract_symbols(diff_added: str) -> list[str]:
    syms: list[str] = []
    syms += GO_FUNC_RE.findall(diff_added)
    syms += GO_TYPE_RE.findall(diff_added)

    # Camel/snake identifiers from added lines (capped to keep payload sane).
    camel = CAMEL_RE.findall(diff_added)
    snake = SNAKE_RE.findall(diff_added)
    syms += [s for s in camel if s not in SYMBOL_BLOCKLIST]
    syms += [s for s in snake if s not in SYMBOL_BLOCKLIST]

    return uniq(syms, cap=200)


def extract_error_strings(diff_added: str) -> list[str]:
    found: list[str] = []
    for rx in (ERR_NEW_RE, FMT_ERRORF_RE, PANIC_RE):
        found += rx.findall(diff_added)
    return uniq(found, cap=100)


def extract_log_messages(diff_added: str) -> list[str]:
    return uniq(LOG_RE.findall(diff_added), cap=100)


def title_keywords(title: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9]{3,}", title or "")
    out: list[str] = []
    for t in tokens:
        lo = t.lower()
        if lo in STOP_WORDS:
            continue
        out.append(lo)
    return uniq(out)


def path_tags(files: list[dict]) -> list[str]:
    leaves: list[str] = []
    for f in files:
        path = f.get("path") or ""
        for part in path.split("/"):
            if not part or "." in part:
                continue
            if len(part) < 4:
                continue
            leaves.append(part.lower())
    return uniq(leaves, cap=50)


def main() -> None:
    pr = json.load(sys.stdin)
    diff = pr.get("diff", "") or ""
    added = added_lines(diff)

    # When the diff is unavailable (large PRs, gh 406s, private), fall back
    # to commit messages so symbol/error extraction still has something to
    # chew on. Treat each commit headline+body as if it were an added line.
    if not added:
        commit_text = "\n".join(
            f"+{c.get('headline','')}\n+{c.get('body','')}"
            for c in pr.get("commits") or []
        )
        added = added_lines(commit_text)

    out = {
        "symbols":        [{"value": v} for v in extract_symbols(added)],
        "error_strings":  [{"value": v} for v in extract_error_strings(added)],
        "log_messages":   [{"value": v} for v in extract_log_messages(added)],
        "labels":         [{"value": v} for v in pr.get("labels") or []],
        "title_keywords": [{"value": v} for v in title_keywords(pr.get("title", ""))],
        "path_tags":      [{"value": v} for v in path_tags(pr.get("files") or [])],
        "commit_keywords": [
            {"value": v}
            for v in uniq(
                [
                    kw
                    for c in pr.get("commits") or []
                    for kw in title_keywords(c.get("headline", ""))
                ],
                cap=100,
            )
        ],
        "diff_unavailable": pr.get("diff_unavailable_reason") is not None
        or (not (pr.get("diff") or "") and bool(pr.get("commits"))),
    }
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
