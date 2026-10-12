#!/usr/bin/env python3
"""Runner-side audit helpers: Sippy triage catalogue snapshot/diff, Jira JQL creation audit, runner receipt.

  audit.py snapshot --out F
  audit.py diff --before A --after B --manifest M --out F
  audit.py jql --start ISO --end ISO --reporter R --out F
  audit.py receipt-write --out F --run-id R --mode-requested M --mode-effective E
                         --jira-creations F1 --sippy-diff F2 [--previous-run P]
  audit.py receipt-decide --receipt F [--ack RUN]
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
MAX_PAGES = 10
WIDEN = timedelta(hours=24)
TIMEOUT = 60


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_json(url, headers=None):
    h = {"Accept": "application/json"}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=TIMEOUT) as r:
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


def write_receipt(path, *, run_id, mode_requested, mode_effective, audit, previous_run):
    receipt = {"schema_version": SCHEMA_VERSION, "run_id": run_id, "written_at": _now(),
               "mode_requested": mode_requested, "mode_effective": mode_effective,
               "previous_run": previous_run,
               "audit": {"jira_creations": audit.get("jira_creations"),
                         "sippy_catalog_diff": audit.get("sippy_catalog_diff")}}
    _write_json(path, receipt)


def read_receipt_decision(receipt, ack_run_id=None):
    if receipt is None:
        return "report", "no receipt from the latest preceding attempt"
    if not isinstance(receipt, dict) or not isinstance(receipt.get("audit"), dict):
        return "report", "receipt unreadable: not an object with an audit section"
    if ack_run_id is not None and ack_run_id == receipt.get("run_id"):
        return "configured", "receipt %s acknowledged by manager" % ack_run_id
    jira = receipt["audit"].get("jira_creations")
    diff = receipt["audit"].get("sippy_catalog_diff")
    if not isinstance(jira, dict) or not isinstance(diff, dict):
        return "report", "receipt unreadable: audit sections missing"
    for sec in (jira, diff):
        if sec.get("status") == "unknown":
            return "report", "audit unknown — %s" % sec.get("error")
    if jira.get("truncated"):
        return "report", "Jira audit truncated at %d pages — creations may be missing" % MAX_PAGES
    if jira.get("status") == "ok" and (jira.get("count") or 0) > 0:
        keys = ", ".join(str(i.get("key")) for i in jira.get("issues") or [])
        return "report", "Jira issues created during previous run: %s (count %s)" % (keys, jira["count"])
    if diff.get("status") == "mismatch":
        return "report", "Sippy catalogue mismatch: undeclared=%s declared_not_observed=%s" % (
            json.dumps(diff.get("undeclared")), json.dumps(diff.get("declared_not_observed")))
    return "configured", ""


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
    s = sub.add_parser("receipt-write")
    for k in ("out", "run-id", "mode-requested", "mode-effective", "jira-creations", "sippy-diff"):
        s.add_argument("--" + k, required=True)
    s.add_argument("--previous-run")
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
        elif args.cmd == "receipt-write":
            write_receipt(args.out, run_id=args.run_id, mode_requested=args.mode_requested,
                          mode_effective=args.mode_effective,
                          audit={"jira_creations": _read_json(args.jira_creations),
                                 "sippy_catalog_diff": _read_json(args.sippy_diff)},
                          previous_run=args.previous_run)
        elif args.cmd == "receipt-decide":
            try:
                receipt = _read_json(args.receipt)
            except FileNotFoundError:
                receipt = None
            except (OSError, ValueError) as e:
                receipt = "unreadable: %s" % e
            if isinstance(receipt, str):
                decision, reason = "report", "receipt " + receipt
            else:
                decision, reason = read_receipt_decision(receipt, args.ack)
            print("%s\t%s" % (decision, re.sub(r"[\t\r\n]", " ", str(reason))))
    except (OSError, ValueError, KeyError, AttributeError) as e:
        print("audit.py %s: %s: %s" % (args.cmd, type(e).__name__, e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
