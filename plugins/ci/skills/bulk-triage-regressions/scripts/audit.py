#!/usr/bin/env python3
"""Runner-side audit helpers: Sippy triage catalogue snapshot/diff, Jira JQL creation audit, runner receipt.

  audit.py snapshot --out F
  audit.py diff --before A --after B --manifest M --out F
  audit.py jql --start ISO --end ISO --reporter R --out F
  audit.py permissions --out F [--projects P ...]
  audit.py receipt-write --out F --run-id R --mode-requested M --mode-effective E
                         --jira-creations F1 --sippy-diff F2 [--previous-run P]
  audit.py receipt-decide --receipt F [--ack RUN]   -> prints "<decision>\t<origin>\t<reason>"
"""
import argparse
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

SCHEMA_VERSION = "1.0"
SIPPY_TRIAGES_URL = "https://sippy.dptools.openshift.org/api/component_readiness/triages"
JIRA_SEARCH_URL = "https://redhat.atlassian.net/rest/api/3/search/jql"
JIRA_MYSELF_URL = "https://redhat.atlassian.net/rest/api/3/myself"
JIRA_MYPERMISSIONS_URL = "https://redhat.atlassian.net/rest/api/3/mypermissions"
DEFAULT_PERMISSION_PROJECTS = ("OCPBUGS", "TRT", "DPTP", "OCPQUAL")
PERMISSION_KEYS = ("CREATE_ISSUES", "EDIT_ISSUES", "BROWSE_PROJECTS")
MAX_PAGES = 10
WIDEN = timedelta(hours=24)
TIMEOUT = 60


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_json(url, headers=None):
    h = {"Accept": "application/json"}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=TIMEOUT) as r:
        # Jira Cloud degrades bad basic auth to an anonymous 200 and flags it in this header;
        # an anonymous search would silently under-count, so treat it as a failure.
        reason = (getattr(r, "headers", None) or {}).get("X-Seraph-LoginReason", "")
        if reason and reason.upper() not in ("OK", "AUTHENTICATED"):
            raise RuntimeError("Jira authentication failed (X-Seraph-LoginReason: %s)" % reason)
        return json.loads(r.read().decode("utf-8"))


def _default_fetch():
    return _get_json(SIPPY_TRIAGES_URL)


def snapshot_triages(fetch=None):
    try:
        data = (fetch or _default_fetch)()
        triages = {}
        for t in data:
            triages[str(t["id"])] = {
                "regression_ids": [r["id"] for r in (t.get("regressions") or [])],
                "url": t.get("url"),
                "resolved": t.get("resolved"),
            }
        return {"time": _now(), "triages": triages}
    except Exception as e:
        return {"time": _now(), "status": "unknown", "error": "snapshot failed: %s: %s" % (type(e).__name__, e)}


def _valid_snapshot(s):
    return isinstance(s, dict) and isinstance(s.get("triages"), dict)


def diff_triages(before, after, declared):
    for name, s in (("before", before), ("after", after)):
        if not _valid_snapshot(s):
            detail = s.get("error") if isinstance(s, dict) and s.get("error") else "missing or malformed"
            return {"status": "unknown", "error": "%s snapshot: %s" % (name, detail)}
    b, a = before["triages"], after["triages"]
    created, extended, removed, observed = [], [], [], []
    for tid in sorted(a, key=str):
        if tid not in b:
            created.append(tid)
            observed.append({"kind": "created", "triage_id": tid, "url": a[tid].get("url") or "",
                             "regression_ids": sorted(a[tid].get("regression_ids") or [])})
            continue
        old, new = set(b[tid].get("regression_ids") or []), set(a[tid].get("regression_ids") or [])
        if new - old:
            extended.append({"triage_id": tid, "added": sorted(new - old)})
            observed.append({"kind": "extended", "triage_id": tid, "added": sorted(new - old)})
        if old - new:
            removed.append({"triage_id": tid, "removed": sorted(old - new)})
            observed.append({"kind": "removed", "triage_id": tid, "removed": sorted(old - new)})

    done = [d for d in (declared or []) if isinstance(d, dict) and d.get("status") == "done"
            and d.get("type") in ("extend_triage", "catch_all", "create_triage")]

    def covers(d, o):
        regs = set(d.get("regression_ids") or [])
        if d["type"] == "create_triage":
            return (o["kind"] == "created" and bool(d.get("jira")) and d["jira"] in o["url"]
                    and set(o["regression_ids"]) >= regs)
        return o["kind"] == "extended" and str(d.get("triage_id")) == o["triage_id"] and regs >= set(o["added"])

    undeclared = [o for o in observed if not any(covers(d, o) for d in done)]
    not_observed = [d for d in done if not any(covers(d, o) for o in observed)]
    return {"created": created, "extended": extended, "removed": removed,
            "undeclared": undeclared, "declared_not_observed": not_observed,
            "status": "match" if not undeclared and not not_observed else "mismatch"}


def _parse_ts(text):
    t = text.strip().replace("Z", "+00:00")
    t = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", t)
    t = re.sub(r"\.(\d+)", lambda m: "." + m.group(1)[:6].ljust(6, "0"), t)
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _jira_ts(iso):
    return _parse_ts(iso).strftime("%Y-%m-%d %H:%M")


def build_jql(start, end, reporter):
    reporter = reporter.replace("\\", "\\\\").replace('"', '\\"')
    return 'reporter = "%s" AND created >= "%s" AND created <= "%s" ORDER BY created ASC' % (
        reporter, _jira_ts(start), _jira_ts(end))


def build_auth_header(user, token):
    return "Basic " + base64.b64encode(("%s:%s" % (user, token)).encode("utf-8")).decode("ascii")


def _default_search(jql, page_token=None):
    user, token = os.environ.get("JIRA_USERNAME"), os.environ.get("JIRA_API_TOKEN")
    if not user or not token:
        raise RuntimeError("JIRA_USERNAME/JIRA_API_TOKEN not set")
    if page_token is None:
        # First page: prove the credentials authenticate (401 here, not an anonymous 200 later).
        _get_json(JIRA_MYSELF_URL, {"Authorization": build_auth_header(user, token)})
    params = {"jql": jql, "fields": "key,created,summary,reporter", "maxResults": 100}
    if page_token:
        params["nextPageToken"] = page_token
    return _get_json("%s?%s" % (JIRA_SEARCH_URL, urllib.parse.urlencode(params)),
                     {"Authorization": build_auth_header(user, token)})


def jql_creations(start, end, reporter, search=None):
    res = {"status": "unknown", "count": None, "raw_matched": None, "truncated": False, "issues": [],
           "window": [start, end], "reporter": reporter, "error": None}
    try:
        lo, hi = _parse_ts(start), _parse_ts(end)
        jql = build_jql((lo - WIDEN).isoformat(), (hi + WIDEN).isoformat(), reporter)
        search = search or _default_search
        raw, token, done = [], None, False
        for _ in range(MAX_PAGES):
            resp = search(jql, token)
            raw.extend(resp["issues"])
            token = resp.get("nextPageToken")
            if resp.get("isLast") or not token:
                done = True
                break
        kept = [i for i in raw if lo <= _parse_ts(i["fields"]["created"]) <= hi]
        res.update(status="ok", count=len(kept), raw_matched=len(raw), truncated=not done,
                   issues=[{"key": i["key"], "created": i["fields"].get("created"),
                            "summary": i["fields"].get("summary")} for i in kept])
    except Exception as e:
        res.update(status="unknown", count=None, raw_matched=None, issues=[],
                   error="%s: %s" % (type(e).__name__, e))
    return res


def _default_permissions_fetch(project):
    user, token = os.environ.get("JIRA_USERNAME"), os.environ.get("JIRA_API_TOKEN")
    if not user or not token:
        raise RuntimeError("JIRA_USERNAME/JIRA_API_TOKEN not set")
    q = urllib.parse.urlencode({"projectKey": project, "permissions": ",".join(PERMISSION_KEYS)})
    return _get_json("%s?%s" % (JIRA_MYPERMISSIONS_URL, q), {"Authorization": build_auth_header(user, token)})


def permissions(projects=None, fetch=None):
    """Observe (not gate) the account's permissions per project (spec §6.3: transparency only).
    create_issues is True when ANY listed project grants it — the token is write-capable by design."""
    projects = list(projects or DEFAULT_PERMISSION_PROJECTS)
    res = {"status": "unknown", "time": _now(), "projects": projects, "per_project": {},
           "create_issues": None, "edit_issues": None, "error": None}
    try:
        fetch = fetch or _default_permissions_fetch
        for proj in projects:
            perms = (fetch(proj) or {}).get("permissions") or {}
            res["per_project"][proj] = {k: bool((perms.get(k) or {}).get("havePermission")) for k in PERMISSION_KEYS}
        res["create_issues"] = any(v["CREATE_ISSUES"] for v in res["per_project"].values())
        res["edit_issues"] = all(v["EDIT_ISSUES"] for v in res["per_project"].values())
        res["status"] = "ok"
    except Exception as e:  # noqa: BLE001 — a failed observation is unknown, never a default
        res["error"] = "%s: %s" % (type(e).__name__, e)
    return res


def write_receipt(path, *, run_id, mode_requested, mode_effective, audit, previous_run, downgrade=None):
    """Receipt consumed by the next run. `downgrade` carries a pending, unacknowledged downgrade
    ({"pending": True, "origin": <violating run id>, "reason": ...}) so that one violation keeps
    forcing report mode until a manager acknowledges the ORIGIN run, not merely until the next clean run."""
    receipt = {"schema_version": SCHEMA_VERSION, "run_id": run_id, "written_at": _now(),
               "mode_requested": mode_requested, "mode_effective": mode_effective,
               "previous_run": previous_run,
               "downgrade": downgrade if (isinstance(downgrade, dict) and downgrade.get("pending")) else None,
               "audit": {"jira_creations": audit.get("jira_creations"),
                         "sippy_catalog_diff": audit.get("sippy_catalog_diff")}}
    _write_json(path, receipt)


def read_receipt_decision(receipt, ack_run_id=None):
    """Return (decision, origin, reason). decision is "report" or "configured"; origin is the run id
    whose violation forces report mode ("" when none), which is what a manager must acknowledge."""
    if receipt is None:
        return "report", "", "no receipt from the latest preceding attempt"
    if not isinstance(receipt, dict) or not isinstance(receipt.get("audit"), dict):
        return "report", "", "receipt unreadable: not an object with an audit section"
    run_id = str(receipt.get("run_id", ""))
    jira = receipt["audit"].get("jira_creations")
    diff = receipt["audit"].get("sippy_catalog_diff")
    if not isinstance(jira, dict) or not isinstance(diff, dict):
        return "report", "", "receipt unreadable: audit sections missing"
    violation = None  # (origin, reason) — this receipt's own audit first, then an inherited downgrade
    for sec in (jira, diff):
        if sec.get("status") == "unknown":
            violation = (run_id, "audit unknown — %s" % sec.get("error")); break
    if violation is None and jira.get("truncated"):
        violation = (run_id, "Jira audit truncated at %d pages — creations may be missing" % MAX_PAGES)
    if violation is None and jira.get("status") == "ok" and (jira.get("count") or 0) > 0:
        keys = ", ".join(str(i.get("key")) for i in jira.get("issues") or [])
        violation = (run_id, "Jira issues created during previous run: %s (count %s)" % (keys, jira["count"]))
    if violation is None and diff.get("status") == "mismatch":
        violation = (run_id, "Sippy catalogue mismatch: undeclared=%s declared_not_observed=%s" % (
            json.dumps(diff.get("undeclared")), json.dumps(diff.get("declared_not_observed"))))
    inherited = receipt.get("downgrade")
    if violation is None and isinstance(inherited, dict) and inherited.get("pending"):
        origin = str(inherited.get("origin") or run_id)
        violation = (origin, "inherited downgrade from %s: %s" % (origin, inherited.get("reason")))
    if violation is None:
        return "configured", "", ""
    origin, reason = violation
    if ack_run_id is not None and ack_run_id == origin:
        return "configured", "", "downgrade from run %s acknowledged by manager" % origin
    return "report", origin, reason


def _write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


def _read_json(path):
    with open(path) as f:
        return json.load(f)


def _declared(manifest):
    clusters = manifest.get("clusters") if isinstance(manifest, dict) else None
    out = []
    for c in clusters if isinstance(clusters, list) else []:
        acts = c.get("actions") if isinstance(c, dict) else None
        if isinstance(acts, list):
            out.extend(a for a in acts if isinstance(a, dict))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(prog="audit.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot"); s.add_argument("--out", required=True)
    s = sub.add_parser("diff")
    for k in ("before", "after", "manifest", "out"):
        s.add_argument("--" + k, required=True)
    s = sub.add_parser("jql")
    for k in ("start", "end", "reporter", "out"):
        s.add_argument("--" + k, required=True)
    s = sub.add_parser("permissions")
    s.add_argument("--out", required=True)
    s.add_argument("--projects", nargs="*", default=list(DEFAULT_PERMISSION_PROJECTS))
    s = sub.add_parser("receipt-write")
    for k in ("out", "run-id", "mode-requested", "mode-effective", "jira-creations", "sippy-diff"):
        s.add_argument("--" + k, required=True)
    s.add_argument("--previous-run")
    s.add_argument("--downgrade-origin", help="run id whose violation forces report mode (propagated)")
    s.add_argument("--downgrade-reason", default="")
    s = sub.add_parser("receipt-decide")
    s.add_argument("--receipt", required=True); s.add_argument("--ack")
    args = p.parse_args(argv)

    try:
        if args.cmd == "snapshot":
            _write_json(args.out, snapshot_triages())
        elif args.cmd == "jql":
            try:
                res = jql_creations(args.start, args.end, args.reporter)
            except Exception as e:
                res = {"status": "unknown", "count": None, "issues": [], "window": [args.start, args.end],
                       "reporter": args.reporter, "error": "%s: %s" % (type(e).__name__, e)}
            if res.get("truncated"):
                print("audit.py jql: warning: Jira search truncated at %d pages" % MAX_PAGES, file=sys.stderr)
            _write_json(args.out, res)
        elif args.cmd == "diff":
            res = diff_triages(_read_json(args.before), _read_json(args.after),
                               _declared(_read_json(args.manifest)))
            _write_json(args.out, res)
            print(res["status"])
        elif args.cmd == "permissions":
            _write_json(args.out, permissions(args.projects))
        elif args.cmd == "receipt-write":
            write_receipt(args.out, run_id=args.run_id, mode_requested=args.mode_requested,
                          mode_effective=args.mode_effective,
                          audit={"jira_creations": _read_json(args.jira_creations),
                                 "sippy_catalog_diff": _read_json(args.sippy_diff)},
                          previous_run=args.previous_run,
                          downgrade=({"pending": True, "origin": args.downgrade_origin,
                                      "reason": args.downgrade_reason} if args.downgrade_origin else None))
        elif args.cmd == "receipt-decide":
            try:
                receipt = _read_json(args.receipt)
            except FileNotFoundError:
                receipt = None
            except (OSError, ValueError) as e:
                receipt = "unreadable: %s" % e
            if isinstance(receipt, str):
                decision, origin, reason = "report", "", "receipt " + receipt
            else:
                decision, origin, reason = read_receipt_decision(receipt, args.ack)
            clean = lambda v: re.sub(r"[\t\r\n]", " ", str(v))
            print("%s\t%s\t%s" % (decision, clean(origin), clean(reason)))
    except (OSError, ValueError, KeyError, AttributeError) as e:
        print("audit.py %s: %s: %s" % (args.cmd, type(e).__name__, e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
