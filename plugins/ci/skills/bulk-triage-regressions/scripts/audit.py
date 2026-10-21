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


PROTECTED_FIELDS = ("url", "type", "resolved", "resolution_reason")   # never change without a declaration
JIRA_KEY_RE = re.compile(r"([A-Z][A-Z0-9]+-\d+)")


def snapshot_triages(fetch=None):
    try:
        data = (fetch or _default_fetch)()
        triages = {}
        for t in data:
            triages[str(t["id"])] = {
                "regression_ids": [r["id"] for r in (t.get("regressions") or [])],
                "url": t.get("url"),
                "type": t.get("type"),
                "description": t.get("description"),
                "resolved": t.get("resolved"),
                "resolution_reason": t.get("resolution_reason"),
            }
        return {"time": _now(), "triages": triages}
    except Exception as e:
        return {"time": _now(), "status": "unknown", "error": "snapshot failed: %s: %s" % (type(e).__name__, e)}


def _valid_snapshot(s):
    return isinstance(s, dict) and isinstance(s.get("triages"), dict)


def _norm_field(name, value):
    """Comparable form of a protected field: `resolved` structs compare by instant + validity."""
    if name == "resolved" and isinstance(value, dict):
        valid = bool(value.get("Valid"))
        t = value.get("Time")
        if not valid:
            return ("resolved", False)
        try:
            return ("resolved", True, _parse_ts(str(t)).isoformat())
        except Exception:  # noqa: BLE001 - unparseable stays comparable as raw text
            return ("resolved", True, str(t))
    return value


def _jira_key(text):
    """Exact Jira key from a URL or a bare key ("OCPBUGS-9" never matches "OCPBUGS-99")."""
    if not text:
        return None
    m = JIRA_KEY_RE.search(str(text).rstrip("/").rsplit("/", 1)[-1])
    return m.group(1) if m else None


def diff_triages(before, after, declared):
    for name, snap in (("before", before), ("after", after)):
        if not _valid_snapshot(snap):
            detail = snap.get("error") if isinstance(snap, dict) and snap.get("error") else "missing or malformed"
            return {"status": "unknown", "error": "%s snapshot: %s" % (name, detail)}
    b, a = before["triages"], after["triages"]
    created, extended, removed, deleted, modified, observed = [], [], [], [], [], []
    for tid in sorted(set(a) | set(b), key=str):
        if tid not in b:
            created.append(tid)
            observed.append({"kind": "created", "triage_id": tid, "url": a[tid].get("url") or "",
                             "jira": _jira_key(a[tid].get("url")),
                             "regression_ids": sorted(a[tid].get("regression_ids") or [])})
            continue
        if tid not in a:
            deleted.append(tid)
            observed.append({"kind": "deleted", "triage_id": tid, "url": b[tid].get("url") or "",
                             "regression_ids": sorted(b[tid].get("regression_ids") or [])})
            continue
        old, new = set(b[tid].get("regression_ids") or []), set(a[tid].get("regression_ids") or [])
        if new - old:
            extended.append({"triage_id": tid, "added": sorted(new - old)})
            observed.append({"kind": "extended", "triage_id": tid, "added": sorted(new - old)})
        if old - new:
            removed.append({"triage_id": tid, "removed": sorted(old - new)})
            observed.append({"kind": "removed", "triage_id": tid, "removed": sorted(old - new)})
        changed = [f for f in PROTECTED_FIELDS + ("description",)
                   if _norm_field(f, b[tid].get(f)) != _norm_field(f, a[tid].get(f))]
        if changed:
            modified.append({"triage_id": tid, "fields": changed})
            observed.append({"kind": "modified", "triage_id": tid, "fields": changed,
                             "before": {f: b[tid].get(f) for f in changed}, "after": {f: a[tid].get(f) for f in changed}})

    done = [d for d in (declared or []) if isinstance(d, dict) and d.get("status") == "done"
            and d.get("type") in ("extend_triage", "catch_all", "create_triage")]
    # Several clusters may legitimately write to one triage: aggregate declarations per target.
    ext_by_tid = {}
    create_by_tid = {}      # explicit returned id -> {"regs": set, "keys": set of declared Jira keys}
    create_by_key = {}      # key-only declarations -> union of regs (covers exactly ONE created triage)
    for d in done:
        regs = set(d.get("regression_ids") or [])
        if d["type"] == "create_triage":
            key = _jira_key(d.get("jira"))
            if d.get("triage_id") is not None:
                slot = create_by_tid.setdefault(str(d["triage_id"]), {"regs": set(), "keys": set()})
                slot["regs"] |= regs
                if key:
                    slot["keys"].add(key)
            elif key:
                create_by_key.setdefault(key, set()).update(regs)
        elif d.get("triage_id") is not None:
            ext_by_tid.setdefault(str(d.get("triage_id")), set()).update(regs)

    # Key-only declarations bind to the first created triage carrying that key (by id); a second
    # creation for the same bug is a duplicate and stays undeclared.
    key_bound = {}
    for o in observed:
        if o["kind"] == "created" and o.get("jira") in create_by_key and o["jira"] not in key_bound \
                and o["triage_id"] not in create_by_tid:
            key_bound[o["jira"]] = o["triage_id"]

    def expected_creation(o):
        """Expected final membership of a created triage, or None when nothing declared it."""
        tid, key = o["triage_id"], o.get("jira")
        regs, declared = set(), False
        slot = create_by_tid.get(tid)
        if slot is not None:
            if slot["keys"] and key not in slot["keys"]:
                return None           # declared id and declared key disagree with what was created
            regs |= slot["regs"]
            declared = True
            if key in create_by_key:  # key-only declarations for the same bug share this creation
                regs |= create_by_key[key]
        elif key and key_bound.get(key) == tid:
            regs |= create_by_key[key]
            declared = True
        if not declared:
            return None
        return regs | ext_by_tid.get(tid, set())   # a creation followed by an extension in the same run

    def covered(o):
        tid = o["triage_id"]
        if o["kind"] == "created":
            expected = expected_creation(o)
            return expected is not None and set(o["regression_ids"]) == expected   # exact membership
        if o["kind"] == "extended":
            return tid in ext_by_tid and ext_by_tid[tid] >= set(o["added"])
        if o["kind"] == "modified":
            # A declared extension may refresh the description; protected fields never change undeclared.
            return o["fields"] == ["description"] and tid in ext_by_tid
        return False   # removed / deleted are never covered

    def observed_for(d):
        regs = set(d.get("regression_ids") or [])
        if d["type"] == "create_triage":
            tid = str(d["triage_id"]) if d.get("triage_id") is not None else None
            key = _jira_key(d.get("jira"))
            if tid is not None:
                return any(o["kind"] == "created" and o["triage_id"] == tid for o in observed)
            return key in key_bound or any(o["kind"] == "created" and o.get("jira") == key and o["triage_id"] in create_by_tid
                                           for o in observed)
        tid = str(d.get("triage_id"))
        # Declared ids must be present at the end; a declared write whose ids were already linked is a no-op.
        return tid in a and regs <= set(a[tid].get("regression_ids") or [])

    undeclared = [o for o in observed if not covered(o)]
    not_observed = [d for d in done if not observed_for(d)]
    return {"created": created, "extended": extended, "removed": removed, "deleted": deleted, "modified": modified,
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
            if not isinstance(resp, dict) or not isinstance(resp.get("issues"), list):
                raise RuntimeError("Jira search returned no issues list")
            raw.extend(resp["issues"])
            token = resp.get("nextPageToken")
            if resp.get("isLast") is True:
                done = True
                break
            if not token:
                # Not the last page by Jira's own account, yet no way to continue: never a complete zero.
                raise RuntimeError("Jira pagination incomplete: isLast=%r without nextPageToken" % resp.get("isLast"))
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
            obs = {}
            for k in PERMISSION_KEYS:
                v = (perms.get(k) or {}).get("havePermission") if isinstance(perms.get(k), dict) else None
                obs[k] = v if isinstance(v, bool) else None   # missing observation stays unknown
            res["per_project"][proj] = obs
        def _any(key):
            vals = [v[key] for v in res["per_project"].values()]
            return True if any(x is True for x in vals) else (False if vals and all(x is False for x in vals) else None)
        def _all(key):
            vals = [v[key] for v in res["per_project"].values()]
            return False if any(x is False for x in vals) else (True if vals and all(x is True for x in vals) else None)
        res["create_issues"] = _any("CREATE_ISSUES")
        res["edit_issues"] = _all("EDIT_ISSUES")
        complete = all(v is not None for p in res["per_project"].values() for v in p.values())
        res["status"] = "ok" if complete else "partial"
        if not complete:
            res["error"] = "some permissions were not reported by Jira"
    except Exception as e:  # noqa: BLE001 — a failed observation is unknown, never a default
        res["error"] = "%s: %s" % (type(e).__name__, e)
    return res


REASON_MAX = 300   # per-origin diagnostic text kept in receipts (bounded: N9)
INHERITED_PREFIX = "inherited downgrade from "


def _origins(value):
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value or "").split(",") if v.strip()]


def _strip_inherited(text):
    text = str(text or "")
    while text.startswith(INHERITED_PREFIX):
        text = text.split(": ", 1)[1] if ": " in text else text[len(INHERITED_PREFIX):]
    return text[:REASON_MAX]


def write_receipt(path, *, run_id, mode_requested, mode_effective, audit, previous_run, downgrade=None):
    """Receipt consumed by the next run. `downgrade` carries the pending, unacknowledged downgrade(s):
    {"pending": True, "origins": [...], "reasons": {origin: text}, "reason": <joined text>} — every violating
    run id that still has to be acknowledged, so report mode persists until each ORIGIN is acknowledged,
    not until the next clean run. Per-origin reasons are taken, in order, from `downgrade["reasons"]`,
    from `downgrade["previous_receipt"]` (the receipt this run inherited from), from this run's own audit,
    and finally from the joined `reason` text — each bounded to REASON_MAX characters."""
    jira, diff = audit.get("jira_creations"), audit.get("sippy_catalog_diff")
    dg = None
    if isinstance(downgrade, dict) and downgrade.get("pending"):
        origins = _origins(downgrade.get("origins") or downgrade.get("origin"))
        if origins:
            given = downgrade.get("reasons") if isinstance(downgrade.get("reasons"), dict) else {}
            prev = downgrade.get("previous_receipt")
            prev_reasons = ((prev.get("downgrade") or {}).get("reasons") or {}) if isinstance(prev, dict) else {}
            own = {o: r for o, r in (_own_violations(str(run_id), jira, diff) if isinstance(jira, dict) and isinstance(diff, dict)
                                      else [(str(run_id), "audit unreadable")])}
            reasons = {}
            for o in origins:
                text = given.get(o) or prev_reasons.get(o) or own.get(o) or downgrade.get("reason") or ""
                reasons[o] = _strip_inherited(text)
            dg = {"pending": True, "origin": ",".join(origins), "origins": origins, "reasons": reasons,
                  "reason": "; ".join("%s: %s" % (o, reasons[o]) for o in origins)[:REASON_MAX * max(1, len(origins))]}
    receipt = {"schema_version": SCHEMA_VERSION, "run_id": run_id, "written_at": _now(),
               "mode_requested": mode_requested, "mode_effective": mode_effective,
               "previous_run": previous_run, "downgrade": dg,
               "audit": {"jira_creations": jira, "sippy_catalog_diff": diff}}
    _write_json(path, receipt)


def _own_violations(run_id, jira, diff):
    """Reasons this receipt's own audit is not a VALID, CLEAN audit. Fail closed: anything short of
    jira ok/count exactly 0/not truncated and sippy match is a violation attributed to this run."""
    out = []
    st = jira.get("status")
    if st != "ok":
        out.append("Jira audit %s — %s" % (st if st else "missing", jira.get("error") or "no clean result"))
    else:
        count = jira.get("count")
        if jira.get("truncated"):
            out.append("Jira audit truncated at %d pages — creations may be missing" % MAX_PAGES)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            out.append("Jira audit has no valid count (%r)" % (count,))
        elif count > 0:
            keys = ", ".join(str(i.get("key")) for i in (jira.get("issues") or []) if isinstance(i, dict))
            out.append("Jira issues created during previous run: %s (count %s)" % (keys, count))
    dst = diff.get("status")
    if dst == "mismatch":
        out.append("Sippy catalogue mismatch: undeclared=%s declared_not_observed=%s" % (
            json.dumps(diff.get("undeclared")), json.dumps(diff.get("declared_not_observed"))))
    elif dst != "match":
        out.append("Sippy catalogue audit %s — %s" % (dst if dst else "missing", diff.get("error") or "no clean result"))
    return [(run_id, r[:REASON_MAX]) for r in out]


def _inherited(receipt):
    """(origin, reason) pairs carried by a receipt's downgrade block, oldest first."""
    dg = receipt.get("downgrade") if isinstance(receipt, dict) else None
    if not isinstance(dg, dict) or not dg.get("pending"):
        return []
    reasons = dg.get("reasons") if isinstance(dg.get("reasons"), dict) else {}
    out = []
    for o in _origins(dg.get("origins") or dg.get("origin")):
        text = _strip_inherited(reasons.get(o) or dg.get("reason") or "")
        out.append((o, INHERITED_PREFIX + "%s: %s" % (o, text)))
    return out


def read_receipt_decision(receipt, ack_run_id=None):
    """Return (decision, origin, reason). decision is "report" or "configured"; origin lists every run id
    whose violation still forces report mode (comma-separated, "" when none) — what a manager must
    acknowledge (POSTGA_ACK_RECEIPT accepts the same comma-separated form). Inherited origins are
    recovered BEFORE this receipt's own audit is judged, so an unreadable carrier never erases them."""
    if receipt is None:
        return "report", "", "no receipt from the latest preceding attempt"
    if not isinstance(receipt, dict):
        return "report", "", "receipt unreadable: not an object"
    run_id = str(receipt.get("run_id", ""))
    outstanding = list(_inherited(receipt))   # oldest first
    audit = receipt.get("audit")
    jira = audit.get("jira_creations") if isinstance(audit, dict) else None
    diff = audit.get("sippy_catalog_diff") if isinstance(audit, dict) else None
    unreadable = not isinstance(jira, dict) or not isinstance(diff, dict)
    if unreadable:
        outstanding.append((run_id, "receipt unreadable: audit sections missing"))
    else:
        outstanding.extend(_own_violations(run_id, jira, diff))
    acked = set(_origins(ack_run_id)) if ack_run_id is not None else set()
    remaining, seen = [], set()
    for origin, reason in outstanding:
        # An unreadable receipt cannot be acknowledged away: nobody knows what that run did.
        if (origin in acked and not (unreadable and origin == run_id)) or origin in seen:
            continue
        seen.add(origin)
        remaining.append((origin, reason))
    if not remaining:
        if outstanding:
            return "configured", "", "downgrade from run %s acknowledged by manager" % ",".join(sorted({o for o, _ in outstanding}))
        return "configured", "", ""
    return "report", ",".join(o for o, _ in remaining), "; ".join(r for _, r in remaining)


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
    s.add_argument("--downgrade-origin", help="run id(s), comma-separated, whose violations force report mode (propagated)")
    s.add_argument("--downgrade-reason", default="")
    s.add_argument("--previous-receipt", help="the receipt this run inherited from (per-origin reasons are copied)")
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
                          downgrade=({"pending": True, "origins": _origins(args.downgrade_origin),
                                      "reason": args.downgrade_reason,
                                      "previous_receipt": (_read_json(args.previous_receipt)
                                                           if args.previous_receipt and os.path.exists(args.previous_receipt) else None)}
                                     if args.downgrade_origin else None))
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
