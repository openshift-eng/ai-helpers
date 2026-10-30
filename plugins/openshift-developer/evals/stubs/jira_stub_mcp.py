#!/usr/bin/env python3
"""Stub Jira MCP server for offline skill evals.

Serves a frozen issue snapshot (jira-fixture.json next to this script) over the
MCP stdio transport, with tool names and parameters mirroring the Atlassian MCP
``jira_*`` tools. Writes mutate the in-memory snapshot only; nothing reaches a
real Jira. Every call is appended to output/jira-calls.jsonl and the current
snapshot is written to output/jira-state.json so judges can score the Jira
actions a skill took.

Stdlib only. Environment overrides: JIRA_STUB_FIXTURE, JIRA_STUB_OUTPUT_DIR.
"""

import copy
import datetime
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = Path(os.environ.get("JIRA_STUB_FIXTURE", HERE / "jira-fixture.json"))
OUTPUT_DIR = Path(os.environ.get("JIRA_STUB_OUTPUT_DIR", HERE / "output"))
CALLS_LOG = OUTPUT_DIR / "jira-calls.jsonl"
STATE_FILE = OUTPUT_DIR / "jira-state.json"

AGENT_AUTHOR = "refine-eval-agent"
KEY_RE = re.compile(r"\b[A-Z][A-Z0-9_]+-\d+\b")

ISSUE_KEY = {"type": "string", "description": "Jira issue key (e.g. OCPBUGS-123)"}
JSON_OR_OBJECT = {"type": ["string", "object"], "description": "JSON object or JSON-encoded string"}

TOOLS = [
    {
        "name": "jira_get_issue",
        "description": "Get a Jira issue with its fields and comments. Use include "
                       "(comma-separated: comments, changelog, remote_links, transitions, all) "
                       "to inline enrichments.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": ISSUE_KEY,
                "fields": {"type": "string"},
                "expand": {"type": "string"},
                "include": {"type": "string"},
                "comment_limit": {"type": "integer", "default": 10},
            },
            "required": ["issue_key"],
        },
    },
    {
        "name": "jira_search",
        "description": "Search issues with JQL. The stub matches issue keys named in the "
                       "JQL and, failing that, quoted text against summaries and descriptions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "jql": {"type": "string"},
                "fields": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["jql"],
        },
    },
    {
        "name": "jira_batch_get_changelogs",
        "description": "Get changelogs for issues (comma-separated keys).",
        "inputSchema": {
            "type": "object",
            "properties": {"issue_ids_or_keys": {"type": "string"}},
            "required": ["issue_ids_or_keys"],
        },
    },
    {
        "name": "jira_get_transitions",
        "description": "List the status transitions available for an issue.",
        "inputSchema": {
            "type": "object",
            "properties": {"issue_key": ISSUE_KEY},
            "required": ["issue_key"],
        },
    },
    {
        "name": "jira_add_comment",
        "description": "Add a comment (Markdown) to an issue.",
        "inputSchema": {
            "type": "object",
            "properties": {"issue_key": ISSUE_KEY, "body": {"type": "string"}},
            "required": ["issue_key", "body"],
        },
    },
    {
        "name": "jira_transition_issue",
        "description": "Transition an issue. Set the resolution through fields, e.g. "
                       "{\"resolution\": {\"name\": \"Won't Do\"}}.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": ISSUE_KEY,
                "transition_id": {"type": ["string", "integer"]},
                "fields": JSON_OR_OBJECT,
                "comment": {"type": "string"},
            },
            "required": ["issue_key", "transition_id"],
        },
    },
    {
        "name": "jira_update_issue",
        "description": "Update issue fields. 'labels' replaces the whole label list.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": ISSUE_KEY,
                "fields": JSON_OR_OBJECT,
                "additional_fields": JSON_OR_OBJECT,
            },
            "required": ["issue_key", "fields"],
        },
    },
]

WRITE_TOOLS = {"jira_add_comment", "jira_transition_issue", "jira_update_issue"}
UPDATABLE_FIELDS = {
    "summary", "description", "labels", "priority", "assignee", "severity",
    "versions", "fixVersions", "components", "target_backport_versions",
}
# Real Jira custom field ids the skill writes, mapped to the fixture's field names.
FIELD_ALIASES = {"customfield_10878": "target_backport_versions"}


class StubError(Exception):
    pass


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def parse_object(value, name):
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as e:
        raise StubError(f"{name} must be a JSON object: {e}")
    if not isinstance(parsed, dict):
        raise StubError(f"{name} must be a JSON object")
    return parsed


class Jira:
    def __init__(self, fixture):
        self.data = fixture
        self.issues = fixture["issues"]
        self.resolutions = fixture.get("resolutions", [])
        self.next_comment_id = 9000000

    def issue(self, key):
        issue = self.issues.get(str(key).strip().upper())
        if issue is None:
            raise StubError(f"Issue {key} does not exist or you do not have permission to see it.")
        return issue

    def transitions(self, issue):
        return issue.get("transitions", self.data.get("transitions", []))

    def render(self, issue, include="", expand="", comment_limit=10):
        wanted = {p.strip() for p in f"{include},{expand}".split(",") if p.strip()}
        out = {k: copy.deepcopy(v) for k, v in issue.items()
               if k not in ("comments", "changelog", "remote_links", "transitions")}
        out["status"] = {"name": issue["status"]}
        out["resolution"] = {"name": issue["resolution"]} if issue.get("resolution") else None
        comments = issue.get("comments", [])
        limit = len(comments) if comment_limit in (None, 0) else int(comment_limit)
        out["comments"] = copy.deepcopy(comments[-limit:]) if limit else []
        if wanted & {"all", "changelog"}:
            out["changelog"] = copy.deepcopy(issue.get("changelog", []))
        if wanted & {"all", "remote_links"}:
            out["remote_links"] = copy.deepcopy(issue.get("remote_links", []))
        if wanted & {"all", "transitions"}:
            out["transitions"] = copy.deepcopy(self.transitions(issue))
        return out

    # Tool handlers return (result, wrote_state).

    def jira_get_issue(self, issue_key, include="", expand="", comment_limit=10, **_):
        return self.render(self.issue(issue_key), include or "", expand or "", comment_limit), False

    def jira_search(self, jql, limit=10, **_):
        keys = [k for k in KEY_RE.findall(jql) if k in self.issues]
        if not keys:
            terms = [t.lower() for t in re.findall(r'"([^"]+)"', jql)]
            keys = [k for k, i in self.issues.items()
                    if terms and any(t in f"{i.get('summary', '')} {i.get('description', '')}".lower()
                                     for t in terms)]
        found = [self.render(self.issues[k], comment_limit=0) for k in keys[: int(limit or 10)]]
        return {"total": len(found), "issues": found}, False

    def jira_batch_get_changelogs(self, issue_ids_or_keys, **_):
        keys = [k.strip() for k in issue_ids_or_keys.split(",") if k.strip()]
        return [{"issue_key": k, "changelogs": copy.deepcopy(self.issue(k).get("changelog", []))}
                for k in keys], False

    def jira_get_transitions(self, issue_key, **_):
        return copy.deepcopy(self.transitions(self.issue(issue_key))), False

    def jira_add_comment(self, issue_key, body, **_):
        issue = self.issue(issue_key)
        if not str(body).strip():
            raise StubError("Comment body must not be empty")
        self.next_comment_id += 1
        comment = {"id": str(self.next_comment_id), "author": AGENT_AUTHOR,
                   "created": now(), "body": body}
        issue.setdefault("comments", []).append(comment)
        issue["updated"] = comment["created"]
        return comment, True

    def jira_transition_issue(self, issue_key, transition_id, fields=None, comment=None, **_):
        issue = self.issue(issue_key)
        match = [t for t in self.transitions(issue) if str(t["id"]) == str(transition_id)]
        if not match:
            raise StubError(f"Transition {transition_id} is not valid for {issue_key}")
        target = match[0]
        fields = parse_object(fields, "fields")
        resolution = fields.get("resolution")
        if isinstance(resolution, dict):
            resolution = resolution.get("name")
        if resolution is not None and resolution not in self.resolutions:
            raise StubError(f"Resolution {resolution!r} is not one of {self.resolutions}")
        if target.get("category") == "Done" and not resolution:
            resolution = "Done"
        from_status = issue["status"]
        issue["status"] = target["name"]
        issue["resolution"] = resolution if target.get("category") == "Done" else None
        issue["updated"] = now()
        issue.setdefault("changelog", []).append({
            "created": issue["updated"], "author": AGENT_AUTHOR,
            "items": [{"field": "status", "from": from_status, "to": issue["status"]},
                      {"field": "resolution", "from": None, "to": issue["resolution"]}],
        })
        if comment:
            self.jira_add_comment(issue_key, comment)
        return {"message": f"Issue {issue_key} transitioned successfully",
                "status": issue["status"], "resolution": issue["resolution"]}, True

    def jira_update_issue(self, issue_key, fields, additional_fields=None, **_):
        issue = self.issue(issue_key)
        changes = {**parse_object(fields, "fields"), **parse_object(additional_fields, "additional_fields")}
        changes = {FIELD_ALIASES.get(name, name): value for name, value in changes.items()}
        unknown = sorted(set(changes) - UPDATABLE_FIELDS)
        if unknown:
            raise StubError(f"Unsupported fields for the stub: {unknown}")
        items = []
        for name, value in changes.items():
            if name == "labels":
                if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                    raise StubError("labels must be a list of strings")
            items.append({"field": name, "from": copy.deepcopy(issue.get(name)), "to": value})
            issue[name] = value
        issue["updated"] = now()
        issue.setdefault("changelog", []).append(
            {"created": issue["updated"], "author": AGENT_AUTHOR, "items": items})
        return {"message": "Issue updated successfully",
                "issue": self.render(issue, comment_limit=0)}, True


def record(entry):
    with CALLS_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def save_state(jira):
    STATE_FILE.write_text(json.dumps(jira.data, indent=2) + "\n")


def call_tool(jira, name, args):
    entry = {"ts": now(), "tool": name, "args": args, "write": name in WRITE_TOOLS}
    try:
        handler = getattr(jira, name) if name in {t["name"] for t in TOOLS} else None
        if handler is None:
            raise StubError(f"Unknown tool {name}")
        result, wrote = handler(**args)
        entry["ok"] = True
        if wrote:
            save_state(jira)
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    except (StubError, TypeError, KeyError) as e:
        entry["ok"] = False
        entry["error"] = str(e)
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
    finally:
        record(entry)


def handle(jira, msg):
    method = msg.get("method")
    if method == "initialize":
        return {
            "protocolVersion": msg.get("params", {}).get("protocolVersion", "2025-06-18"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "jira-stub", "version": "1.0.0"},
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        params = msg.get("params", {})
        return call_tool(jira, params.get("name"), params.get("arguments") or {})
    raise LookupError(method)


def main():
    jira = Jira(json.loads(FIXTURE.read_text()))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_state(jira)
    for line in sys.stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        if "id" not in msg:
            continue  # notifications need no response
        try:
            reply = {"jsonrpc": "2.0", "id": msg["id"], "result": handle(jira, msg)}
        except LookupError as e:
            reply = {"jsonrpc": "2.0", "id": msg["id"],
                     "error": {"code": -32601, "message": f"Method not found: {e}"}}
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
