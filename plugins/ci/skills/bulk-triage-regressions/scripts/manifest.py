#!/usr/bin/env python3
"""triage-manifest schema 1.0: validate a manifest and merge prepass.json with the LLM-phase outputs.

  manifest.py validate PATH
  manifest.py merge --prepass P --dispositions D --actions A --out M
"""
import argparse
import copy
import json
import sys

SCHEMA_VERSION = "1.0"
LEVELS = ("HIGH", "ELEVATED", "LOW")
STATES = ("KNOWN-CAUSE", "CANDIDATE", "UNEXPLAINED", "UNANALYSED")
ACTION_TYPES = ("extend_triage", "create_triage", "catch_all", "none")
ACTION_STATUS = ("planned", "done", "failed", "skipped-report-mode")
JQL_AUDIT = ("pass", "fail", "unknown")
SIPPY_DIFF = ("match", "mismatch", "unknown")
PROBE_STATUS = ("ok", "unauthorized", "failed", "skipped")

TOP_PREPASS = ("schema_version", "policy", "source_run", "observation", "baseline_run", "clusters")
TOP_LLM = ("watch_list", "catch_all", "backport_candidates", "unanalysed", "audit")
CLUSTER_PREPASS = ("id", "lineage", "fingerprint", "members", "shape", "blast_radius")
CLUSTER_LLM = ("disposition", "actions", "escalation")
AUDIT_KEYS = ("jira_writes", "account_wide_creations", "sippy_catalog_diff", "jira_permissions", "receipt", "guards")
GUARD_KEYS = ("existing_only_flag", "jql_audit", "sippy_diff", "junit_backstop")
RULE_CHECKS = ("examined", "no_bug_meets_bar", "not_in_cluster", "pre_5_0")


def _t(x):
    return type(x).__name__


def _enum(path, name, value, allowed):
    if isinstance(value, (str, type(None))) and value in allowed:
        return []
    return ["%s: %s %r not in %s" % (path, name, value, list(allowed))]


def _ids(x):
    """Return a set of the hashable ids in a list; anything else is skipped."""
    if not isinstance(x, list):
        return set()
    return {i for i in x if isinstance(i, (int, str))}


def _rule_level(w, c):
    br = c.get("blast_radius")
    if "blast_radius" not in c:
        return []
    if not isinstance(br, dict):
        return ["%s: blast_radius must be an object" % w]
    return _enum(w, "blast_radius.level", br.get("level"), LEVELS)


def _rule_disposition_state(w, c):
    d = c.get("disposition")
    if "disposition" not in c:
        return []
    if not isinstance(d, dict):
        return ["%s: disposition must be an object" % w]
    return _enum(w, "disposition.state", d.get("state"), STATES)


def _evidence_items(c):
    d = c.get("disposition")
    an = d.get("analysis") if isinstance(d, dict) else None
    ev = an.get("evidence") if isinstance(an, dict) else None
    return [e for e in ev if isinstance(e, dict)] if isinstance(ev, list) else []


def _rule_evidence(w, c):
    errs = []
    for i, ev in enumerate(_evidence_items(c)):
        p = "%s evidence[%d]" % (w, i)
        if not isinstance(ev, dict):
            errs.append("%s: expected object, got %s" % (p, _t(ev)))
            continue
        if not ev.get("prowjob_run_id"):
            errs.append("%s: missing prowjob_run_id" % p)
        sup = ev.get("supports_regression_ids")
        if not isinstance(sup, list) or not sup:
            errs.append("%s: supports_regression_ids must be a non-empty list" % p)
        elif not all(isinstance(x, (int, str)) for x in sup):
            errs.append("%s: supports_regression_ids must contain only ids" % p)
    return errs


def _rule_action_subset_and_unlinked(w, c):
    d = c.get("disposition")
    pa = d.get("proposed_action") if isinstance(d, dict) else None
    if pa is None:
        return []
    if not isinstance(pa, dict):
        return ["%s: proposed_action must be an object" % w]
    errs = _enum(w, "proposed_action.type", pa.get("type"), ACTION_TYPES)
    if pa.get("type") == "none":
        return errs
    union = set()
    for ev in _evidence_items(c):
        if isinstance(ev, dict):
            union |= _ids(ev.get("supports_regression_ids"))
    extra = sorted(_ids(pa.get("regression_ids")) - union, key=str)
    if extra:
        errs.append("%s: proposed_action.regression_ids not supported by evidence: %s" % (w, extra))
    mem = c.get("members")
    mem = mem if isinstance(mem, dict) else {}
    unl = mem.get("unlinked")
    unlinked = {u.get("id") for u in unl if isinstance(u, dict) and isinstance(u.get("id"), (int, str))} \
        if isinstance(unl, list) else set()
    for r in sorted(_ids(mem.get("regression_ids")) - union - unlinked, key=str):
        errs.append("%s: member %s has no evidence and is not listed in members.unlinked" % (w, r))
    return errs


def _rule_actions(w, c):
    acts = c.get("actions")
    if acts is None:
        return []
    if not isinstance(acts, list):
        return ["%s: actions must be a list" % w]
    errs = []
    for j, a in enumerate(acts):
        p = "%s actions[%d]" % (w, j)
        if not isinstance(a, dict):
            errs.append("%s: expected object, got %s" % (p, _t(a)))
            continue
        errs += _enum(p, "status", a.get("status"), ACTION_STATUS)
        errs += _enum(p, "type", a.get("type"), ACTION_TYPES)
        if a.get("type") in ("extend_triage", "create_triage", "catch_all"):
            errs += _rule_action_targets(p, c, a)
    return errs


def _rule_action_targets(p, c, a):
    """A write (intended, done or failed) may only target cluster members, and — except for the catch-all,
    whose admission is governed by rule_checks — only members some evidence item supports (review I5)."""
    ids = a.get("regression_ids")
    if not isinstance(ids, list) or not ids:
        return ["%s: regression_ids must be a non-empty list for a %s action" % (p, a.get("type"))]
    if any(not isinstance(i, (int, str)) or isinstance(i, bool) for i in ids):
        return ["%s: regression_ids must contain only integer or string ids" % p]
    members = _ids((c.get("members") or {}).get("regression_ids")) if isinstance(c.get("members"), dict) else set()
    errs = []
    outside = sorted(_ids(ids) - members, key=str)
    if outside:
        errs.append("%s: action targets non-members %s" % (p, outside))
    if a.get("type") != "catch_all":
        supported = set()
        for ev in _evidence_items(c):
            supported |= _ids(ev.get("supports_regression_ids"))
        unsupported = sorted(_ids(ids) - supported - set(outside), key=str)
        if unsupported:
            errs.append("%s: action targets members without evidence support %s" % (p, unsupported))
    return errs


def _rule_escalation(w, c):
    if "escalation" not in c:
        return []
    esc = c["escalation"]
    if not isinstance(esc, dict):
        return ["%s: escalation must be an object" % w]
    br = c.get("blast_radius")
    if isinstance(br, dict) and br.get("level") == "HIGH" and esc.get("required") is not True:
        return ["%s: escalation.required must be true for HIGH blast radius" % w]
    return []


def _rule_missing(w, c):
    return ["%s: missing %s" % (w, k) for k in CLUSTER_PREPASS + CLUSTER_LLM if k not in c]


def _rule_objects(w, c):
    errs = ["%s: %s must be an object" % (w, k) for k in ("lineage", "fingerprint", "members", "shape")
            if k in c and not isinstance(c[k], dict)]
    mem = c.get("members")
    if isinstance(mem, dict) and not isinstance(mem.get("regression_ids"), list):
        errs.append("%s: members.regression_ids must be a list" % w)
    return errs


CLUSTER_RULES = (_rule_missing, _rule_objects, _rule_level, _rule_disposition_state, _rule_evidence,
                 _rule_action_subset_and_unlinked, _rule_actions, _rule_escalation)


def _cluster(c, idx):
    if not isinstance(c, dict):
        return ["cluster %d: expected object, got %s" % (idx, _t(c))]
    w = "cluster %s" % (c["id"] if isinstance(c.get("id"), str) else "#%d" % idx)
    errs = [] if isinstance(c.get("id"), str) and c["id"] else ["%s: id must be a non-empty string, got %s" % (w, _t(c.get("id")))]
    return errs + [e for rule in CLUSTER_RULES for e in rule(w, c)]


def _rule_probe(doc):
    obs = doc.get("observation")
    if not isinstance(obs, dict) or "symptom_probe" not in obs:
        return []
    probe = obs["symptom_probe"]
    if not isinstance(probe, dict):
        return ["observation.symptom_probe: expected object, got %s" % _t(probe)]
    return _enum("observation.symptom_probe", "status", probe.get("status"), PROBE_STATUS)


def _rule_catch_all(doc):
    ca = doc.get("catch_all")
    if ca is None:
        return []
    if not isinstance(ca, dict):
        return ["catch_all: expected object, got %s" % _t(ca)]
    adm = ca.get("admitted")
    if adm is None:
        return []
    if not isinstance(adm, list):
        return ["catch_all.admitted: expected list, got %s" % _t(adm)]
    errs = []
    for i, a in enumerate(adm):
        p = "catch_all.admitted[%d]" % i
        if not isinstance(a, dict):
            errs.append("%s: expected object, got %s" % (p, _t(a)))
            continue
        rc = a.get("rule_checks")
        rc = rc if isinstance(rc, dict) else {}
        errs += ["%s: rule_checks.%s must be true" % (p, k) for k in RULE_CHECKS if rc.get(k) is not True]
    return errs + _rule_catch_all_actions(doc, ca, adm)


def _rule_catch_all_actions(doc, ca, adm):
    """A catch_all action is only legitimate for members admitted under the four rule checks, and only
    against the configured catch-all triage (review N5)."""
    admitted = {a.get("regression_id") for a in adm if isinstance(a, dict) and isinstance(a.get("regression_id"), (int, str))
                and isinstance(a.get("rule_checks"), dict) and all(a["rule_checks"].get(k) is True for k in RULE_CHECKS)}
    target = ca.get("triage_id")
    errs = []
    clusters = doc.get("clusters") if isinstance(doc.get("clusters"), list) else []
    for c in clusters:
        if not isinstance(c, dict) or not isinstance(c.get("actions"), list):
            continue
        for j, a in enumerate(c["actions"]):
            if not isinstance(a, dict) or a.get("type") != "catch_all":
                continue
            p = "cluster %s actions[%d]" % (c.get("id"), j)
            if target is not None and str(a.get("triage_id")) != str(target):
                errs.append("%s: catch_all action targets triage %s, not the catch-all triage %s" % (p, a.get("triage_id"), target))
            not_admitted = sorted(_ids(a.get("regression_ids")) - admitted, key=str)
            if not_admitted:
                errs.append("%s: catch_all action for members without a valid catch_all.admitted entry %s" % (p, not_admitted))
    return errs


def _rule_audit(doc):
    audit = doc.get("audit")
    if audit is None:
        return []
    if not isinstance(audit, dict):
        return ["audit: expected object, got %s" % _t(audit)]
    errs = ["audit.%s: missing" % k for k in AUDIT_KEYS if k not in audit]
    g = audit.get("guards")
    if isinstance(g, dict):
        errs += ["audit.guards.%s: missing" % k for k in GUARD_KEYS if k not in g]
        if "jql_audit" in g:
            errs += _enum("audit.guards", "jql_audit", g["jql_audit"], JQL_AUDIT)
        if "sippy_diff" in g:
            errs += _enum("audit.guards", "sippy_diff", g["sippy_diff"], SIPPY_DIFF)
    elif "guards" in audit:
        errs.append("audit.guards: expected object, got %s" % _t(g))
    return errs


def validate(doc):
    """Return a list of error strings; empty means valid. Never raises."""
    if not isinstance(doc, dict):
        return ["manifest: expected object, got %s" % _t(doc)]
    errs = ["missing top-level key: %s" % k for k in TOP_PREPASS + TOP_LLM if k not in doc]
    if "schema_version" in doc and doc["schema_version"] != SCHEMA_VERSION:
        errs.append("schema_version: %r != %r" % (doc["schema_version"], SCHEMA_VERSION))
    errs += _rule_top_level_shapes(doc)
    errs += _rule_probe(doc)
    cl = doc.get("clusters", [])
    if not isinstance(cl, list):
        cl = []
    seen = {}
    for i, c in enumerate(cl):
        errs += _cluster(c, i)
        cid = c.get("id") if isinstance(c, dict) else None
        if isinstance(cid, (str, int)):
            if cid in seen:
                errs.append("cluster %s: duplicate cluster id (also at index %d)" % (cid, seen[cid]))
            seen.setdefault(cid, i)
    return errs + _rule_catch_all(doc) + _rule_audit(doc)


TOP_SHAPES = {"policy": dict, "source_run": dict, "observation": dict, "baseline_run": dict, "clusters": list,
              "watch_list": list, "catch_all": dict, "backport_candidates": list, "unanalysed": list, "audit": dict}
TOP_REQUIRED_FIELDS = {"policy": ("name",), "source_run": ("run_id",), "observation": ("time", "views", "symptom_probe")}


def _rule_top_level_shapes(doc):
    """Required containers must have their documented shape; a null or empty object is not a manifest (review I5)."""
    errs = []
    for key, typ in TOP_SHAPES.items():
        if key not in doc:
            continue
        v = doc[key]
        if not isinstance(v, typ):
            errs.append("%s: expected %s, got %s" % (key, typ.__name__, _t(v)))
            continue
        for f in TOP_REQUIRED_FIELDS.get(key, ()):
            if f not in v:
                errs.append("%s.%s: missing" % (key, f))
    return errs


def merge(prepass, dispositions, actions):
    """Combine prepass.json with LLM-phase dispositions (id -> dict) and actions (id -> list)."""
    ids = [c["id"] for c in prepass["clusters"]]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError("prepass has duplicate cluster ids: %s" % dupes)
    known = set(ids)
    for name, d in (("dispositions", dispositions), ("actions", actions)):
        unknown = sorted(set(d) - known)
        if unknown:
            raise ValueError("%s for clusters not in prepass: %s" % (name, unknown))
    out = copy.deepcopy(prepass)
    for c in out["clusters"]:
        cid = c["id"]
        c["actions"] = copy.deepcopy(actions.get(cid, []))
        if cid not in dispositions:
            continue
        disp = copy.deepcopy(dispositions[cid])
        esc = disp.pop("escalation", None)
        unl = disp.pop("members_unlinked", None)
        if unl is not None:
            if not isinstance(unl, list):
                raise ValueError("members_unlinked for cluster %s must be a list, got %s" % (cid, _t(unl)))
            c["members"]["unlinked"] = unl
        c["disposition"] = disp
        if esc is None:
            level = c["blast_radius"]["level"]
            unexplained = disp.get("state") == "UNEXPLAINED" and level == "ELEVATED"
            esc = {"required": level == "HIGH" or unexplained,
                   "reason": ("blast_radius HIGH" if level == "HIGH" else
                              "UNEXPLAINED at ELEVATED blast radius" if unexplained else "not required")}
        c["escalation"] = esc
    return out


def _jql_guard(jira):
    if not isinstance(jira, dict) or jira.get("status") != "ok" or jira.get("count") is None:
        return "unknown"
    if jira.get("truncated") or jira.get("count", 0) > 0:
        return "fail"
    return "pass"


def _sippy_guard(diff):
    st = diff.get("status") if isinstance(diff, dict) else None
    return st if st in SIPPY_DIFF else "unknown"


def finalize(doc, *, jira_creations, sippy_diff, permissions, mode_requested, mode_effective, decision,
             source_run, previous_run, existing_only):
    """Inject the runner-owned facts into the agent's manifest: the post-run audit (account-wide Jira
    creations, Sippy catalogue diff, permissions observation), the receipt decision, the effective
    policy/write mode and the authoritative source_run. The agent's own `audit.jira_writes` is kept.
    `decision` is the (decision, origin, reason) tuple from audit.read_receipt_decision."""
    out = copy.deepcopy(doc)
    dec, origin, reason = (list(decision) + ["", ""])[:3]
    jira = jira_creations if isinstance(jira_creations, dict) else {"status": "unknown", "count": None}
    diff = sippy_diff if isinstance(sippy_diff, dict) else {"status": "unknown"}
    perms = permissions if isinstance(permissions, dict) else {"status": "unknown"}
    prev_audit = out.get("audit") if isinstance(out.get("audit"), dict) else {}
    issues = jira.get("issues") if isinstance(jira.get("issues"), list) else []
    out["audit"] = {
        "jira_writes": prev_audit.get("jira_writes") if isinstance(prev_audit.get("jira_writes"), list) else [],
        "account_wide_creations": {
            "window": jira.get("window"), "count": jira.get("count"), "status": jira.get("status", "unknown"),
            "truncated": bool(jira.get("truncated")),
            "attribution": [{"key": i.get("key"), "created": i.get("created"), "attributed_to": "unresolved"}
                            for i in issues if isinstance(i, dict)],
            "note": "service account shared with the 5.0 duty job; attribution is best-effort",
        },
        "sippy_catalog_diff": diff,
        "jira_permissions": {k: perms.get(k) for k in ("status", "projects", "create_issues", "edit_issues", "per_project", "error")},
        "receipt": {"previous_run": previous_run, "honoured": True,
                    "downgraded_to_report": dec == "report", "origin": origin or None, "reason": reason or None},
        "guards": {"existing_only_flag": bool(existing_only), "jql_audit": _jql_guard(jira),
                   "sippy_diff": _sippy_guard(diff), "junit_backstop": "runner"},
    }
    out["source_run"] = dict(source_run or {})
    pol = out.get("policy") if isinstance(out.get("policy"), dict) else {}
    pol.update({"name": pol.get("name") or "post-ga", "write_mode": mode_effective,
                "write_mode_requested": mode_requested, "existing_only": bool(existing_only)})
    out["policy"] = pol
    return out


def _load(path):
    with open(path) as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("path")
    mg = sub.add_parser("merge")
    mg.add_argument("--prepass", required=True)
    mg.add_argument("--dispositions", required=True)
    mg.add_argument("--actions", required=True)
    mg.add_argument("--out", required=True)
    mg.add_argument("--extra", help="JSON file whose object is shallow-merged at the top level of the merged "
                                    "document (e.g. watch_list, catch_all, backport_candidates, unanalysed, audit)")
    fz = sub.add_parser("finalize", help="inject the runner's audit, receipt decision and run metadata")
    fz.add_argument("--manifest", required=True); fz.add_argument("--out", required=True)
    for k in ("jira-creations", "sippy-diff", "permissions"):
        fz.add_argument("--" + k, required=True)
    fz.add_argument("--mode-requested", required=True); fz.add_argument("--mode-effective", required=True)
    fz.add_argument("--decision", required=True, help="receipt-decide output: '<decision>\\t<origin>\\t<reason>'")
    for k in ("job", "run-id", "url", "started"):
        fz.add_argument("--" + k, required=True)
    fz.add_argument("--previous-run")
    fz.add_argument("--existing-only", default="true")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "validate":
            doc = _load(args.path)
        elif args.cmd == "finalize":
            parts = args.decision.split("\t")
            doc = finalize(_load(args.manifest), jira_creations=_load(args.jira_creations),
                           sippy_diff=_load(args.sippy_diff), permissions=_load(args.permissions),
                           mode_requested=args.mode_requested, mode_effective=args.mode_effective,
                           decision=(parts + ["", ""])[:3],
                           source_run={"job": args.job, "run_id": args.run_id, "url": args.url, "started": args.started},
                           previous_run=args.previous_run, existing_only=args.existing_only.lower() == "true")
            with open(args.out, "w") as f:
                json.dump(doc, f, indent=2)
                f.write("\n")
        else:
            doc = merge(_load(args.prepass), _load(args.dispositions), _load(args.actions))
            if args.extra:
                extra = _load(args.extra)
                if not isinstance(extra, dict):
                    raise ValueError("--extra must contain a JSON object")
                doc.update(extra)
            with open(args.out, "w") as f:
                json.dump(doc, f, indent=2)
                f.write("\n")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    errs = validate(doc)
    for e in errs:
        print(e, file=sys.stderr)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
