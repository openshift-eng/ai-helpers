#!/usr/bin/env python3
"""Post the post-GA backport-candidate note on an existing bug, only when the release check supports it.

The note says the linked regressions' releases have no release-specific clone. That is a negative claim,
so it is rendered only from a fresh, complete release check (plugins/ci/scripts/release_target.py) whose
decision is ``no-matching-clone`` for every release, and it states what was checked. Any other decision
(a matching clone exists, ambiguous, unknown or incomplete lookups) refuses the note and writes nothing.

  backport_note.py ISSUE --regression-ids 1,2 --fixed-in 4.31 --fix-ref org/repo#123 [--fix-url URL] [--post]

Without ``--post`` it is a dry run that prints the decision and the rendered text. Exit 0 posted/skipped/
dry-run, 3 refused, 1 error. Requires Jira credentials in the environment for the check and the post.
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "scripts"))
import jira_auth  # noqa: E402
import release_target  # noqa: E402

MARKER = "Component Readiness regressions on"
FOOTER = " filed by AI as part of Component Readiness triage duty. Please verify before acting on it."


def _text(node):
    if isinstance(node, dict):
        return node.get("text", "") if node.get("type") == "text" else "".join(_text(c) for c in node.get("content") or [])
    if isinstance(node, list):
        return "".join(_text(c) for c in node)
    return ""


def render(releases, fixed_in, fix_ref, fix_url, check):
    """ADF body and its plain text. ``releases`` are normalised release strings."""
    rels = ", ".join(releases)
    family = check.get("family") or []
    ref = {"type": "text", "text": fix_ref}
    if fix_url:
        ref["marks"] = [{"type": "link", "attrs": {"href": fix_url}}]
    first = [{"type": "text", "text": "%s %s are linked to this bug; the fix shipped in %s via " % (MARKER, rels, fixed_in)},
             ref, {"type": "text", "text": "."}]
    second = [{"type": "text", "text": "Release check: no issue in this bug's clone family (%d checked over Cloners links "
                                       "at %s) has Target Version %s." % (len(family), check.get("checked_at"), rels)}]
    body = {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": first},
        {"type": "paragraph", "content": second},
        {"type": "rule"},
        {"type": "panel", "attrs": {"panelType": "note"}, "content": [{"type": "paragraph", "content": [
            {"type": "text", "text": "AI-generated content:", "marks": [{"type": "strong"}]},
            {"type": "text", "text": FOOTER}]}]}]}
    return body, _text(body["content"][:2])


def _request(auth, method, path, data=None):
    req = urllib.request.Request(auth.url(path), data=None if data is None else json.dumps(data).encode("utf-8"),
                                 method=method)
    req.add_header("Authorization", auth.authorization())
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def backport_note(issue, regression_ids, fixed_in, fix_ref, fix_url=None, post=False,
                  check=None, request=None):
    """Decide, render and (optionally) post. ``check``/``request`` are injectable for tests."""
    rec = (check or release_target.check_regressions)(issue, regression_ids)
    key = release_target.issue_key(issue)
    releases = sorted(r for r in (rec.get("releases") or {}) if r != "unknown")
    errs = release_target.validate_record(rec, issue=key, require=("no-matching-clone",))
    if errs or not releases:
        return {"status": "refused", "issue": key, "reasons": errs or ["no releases"], "release_check": rec}
    body, text = render(releases, fixed_in, fix_ref, fix_url, rec)
    out = {"status": "dry-run", "issue": key, "text": text, "release_check": rec}
    if not post:
        return out
    if request is None:
        auth = jira_auth.resolve()          # once per invocation: one OAuth token for GET and POST

        def request(method, path, data=None):
            return _request(auth, method, path, data)
    path = "/rest/api/3/issue/%s/comment" % urllib.parse.quote(key)
    existing = request("GET", path + "?maxResults=100&orderBy=-created") or {}
    if existing.get("total", 0) > len(existing.get("comments") or []):
        return dict(out, status="refused", reasons=["comment list truncated; cannot deduplicate"])
    prefix = "%s %s " % (MARKER, ", ".join(releases))
    if any(prefix in _text(c.get("body")) for c in existing.get("comments") or []):
        return dict(out, status="skipped", reasons=["an equivalent note is already present"])
    created = request("POST", path, {"body": body}) or {}
    return dict(out, status="posted", comment_id=created.get("id"), created=created.get("created"))


def main(argv=None):
    p = argparse.ArgumentParser(prog="backport_note.py", description=__doc__.split("\n\n")[0])
    p.add_argument("issue")
    p.add_argument("--regression-ids", required=True)
    p.add_argument("--fixed-in", required=True, help="release the fix shipped in, e.g. 4.31")
    p.add_argument("--fix-ref", required=True, help="PR or issue that carried the fix, e.g. org/repo#123")
    p.add_argument("--fix-url")
    p.add_argument("--post", action="store_true", help="post the comment (default: dry run)")
    args = p.parse_args(argv)
    try:
        ids = [int(x) for x in args.regression_ids.split(",") if x.strip()]
        res = backport_note(args.issue, ids, args.fixed_in, args.fix_ref, args.fix_url, args.post)
    except (ValueError, OSError, jira_auth.JiraAuthError) as e:
        print(json.dumps({"status": "error", "error": "%s: %s" % (type(e).__name__, e)}))
        return 1
    print(json.dumps(res, indent=2))
    return 3 if res["status"] == "refused" else 0


if __name__ == "__main__":
    sys.exit(main())
