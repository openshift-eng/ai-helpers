#!/usr/bin/env python3
"""Mock Jira CLI for the check-memory-drift eval.

Stands in for "the environment's Jira mechanism" the skill files through. Every
create/update/comment appends one JSON line to ``jira-calls.jsonl`` in the
current working directory, so the eval judges score the writes the skill
*actually made* — not a self-reported plan.

The mocked OCPBUGS store (open bugs) is NOT served here; it is given to the skill
as ``preexisting_bugs`` in input.yaml for the reconcile step. This stub only
records writes.

Usage:
  # create / update take the rendered bug (render-bug.py output) on stdin:
  python3 render-bug.py ... | python3 jira-mock.py create
  python3 render-bug.py ... | python3 jira-mock.py update
  # comment takes a key and text:
  python3 jira-mock.py comment --key <memory-drift-key> --text "refreshed data"

Each logged line: {"action", "key", "deployment", "namespace", "summary",
"labels", "description"} (comment: {"action","key","text"}).
"""
import argparse
import json
import sys
from pathlib import Path

LOG = Path("jira-calls.jsonl")


def _append(record):
    with LOG.open("a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def _parts(key):
    """A memory-drift-key is '<release>/<namespace>/<deployment>'."""
    bits = str(key or "").split("/")
    namespace = bits[1] if len(bits) >= 3 else None
    deployment = bits[-1] if bits and bits[-1] else None
    return namespace, deployment


def main(argv=None):
    ap = argparse.ArgumentParser(prog="jira-mock.py")
    sub = ap.add_subparsers(dest="action", required=True)
    for name in ("create", "update"):
        p = sub.add_parser(name, help=f"{name} a bug from the rendered JSON on stdin")
        p.add_argument("--key", help="override the memory-drift-key (else read from stdin bug)")
    pc = sub.add_parser("comment", help="comment on an existing bug")
    pc.add_argument("--key", required=True)
    pc.add_argument("--text", default="")
    args = ap.parse_args(argv)

    if args.action == "comment":
        ns, dep = _parts(args.key)
        _append({"action": "comment", "key": args.key, "namespace": ns,
                 "deployment": dep, "text": args.text})
        print(f"OCPBUGS-MOCK commented on {args.key}")
        return 0

    raw = sys.stdin.read().strip()
    if not raw:
        print("jira-mock: create/update needs the rendered bug JSON on stdin",
              file=sys.stderr)
        return 2
    try:
        bug = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"jira-mock: invalid bug JSON on stdin: {exc}", file=sys.stderr)
        return 2

    key = args.key or bug.get("key")
    ns, dep = _parts(key)
    _append({
        "action": args.action,
        "key": key,
        "namespace": ns,
        "deployment": dep,
        "summary": bug.get("summary"),
        "labels": bug.get("labels", []),
        "description": bug.get("description", ""),
    })
    print(f"OCPBUGS-MOCK {args.action}d {key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
