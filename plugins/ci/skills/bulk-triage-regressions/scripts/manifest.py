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


def _enum(errs, where, name, value, allowed):
    if value not in allowed:
        errs.append("%s: %s %r not in %s" % (where, name, value, list(allowed)))


def _evidence(errs, where, items):
    """Validate evidence items; return the union of supports_regression_ids."""
    union = set()
    for i, ev in enumerate(items or []):
        w = "%s evidence[%d]" % (where, i)
        if not isinstance(ev, dict):
            errs.append("%s: not an object" % w)
            continue
        if not ev.get("prowjob_run_id"):
            errs.append("%s: missing prowjob_run_id" % w)
        sup = ev.get("supports_regression_ids")
        if not isinstance(sup, list) or not sup:
            errs.append("%s: supports_regression_ids must be a non-empty list" % w)
        else:
            union.update(sup)
    return union


def _cluster(errs, c, idx):
    cid = c.get("id") if isinstance(c.get("id"), str) else "#%d" % idx
    where = "cluster %s" % cid
    for k in CLUSTER_PREPASS:
        if k not in c:
            errs.append("%s: missing %s" % (where, k))
    for k in CLUSTER_LLM:
        if k not in c:
            errs.append("%s: missing %s" % (where, k))
    level = (c.get("blast_radius") or {}).get("level")
    if "blast_radius" in c:
        _enum(errs, where, "blast_radius.level", level, LEVELS)
    disp = c.get("disposition")
    if isinstance(disp, dict):
        _enum(errs, where, "disposition.state", disp.get("state"), STATES)
        union = _evidence(errs, where, (disp.get("analysis") or {}).get("evidence"))
        pa = disp.get("proposed_action")
        if pa is not None:
            _enum(errs, where, "proposed_action.type", pa.get("type"), ACTION_TYPES)
            if pa.get("type") != "none":
                extra = sorted(set(pa.get("regression_ids") or []) - union)
                if extra:
                    errs.append("%s: proposed_action.regression_ids not supported by evidence: %s" % (where, extra))
                members = (c.get("members") or {}).get("regression_ids") or []
                unlinked = {u.get("id") for u in (c.get("members") or {}).get("unlinked") or []
                            if isinstance(u, dict)}
                for r in members:
                    if r not in union and r not in unlinked:
                        errs.append("%s: member %s has no evidence and is not listed in members.unlinked" % (where, r))
    elif "disposition" in c:
        errs.append("%s: disposition must be an object" % where)
    for j, a in enumerate(c.get("actions") or []):
        _enum(errs, where, "actions[%d].status" % j, a.get("status"), ACTION_STATUS)
        _enum(errs, where, "actions[%d].type" % j, a.get("type"), ACTION_TYPES)
    esc = c.get("escalation")
    if isinstance(esc, dict):
        if level == "HIGH" and esc.get("required") is not True:
            errs.append("%s: escalation.required must be true for HIGH blast radius" % where)
    elif "escalation" in c:
        errs.append("%s: escalation must be an object" % where)


def validate(doc):
    """Return a list of error strings; empty means valid."""
    errs = []
    if not isinstance(doc, dict):
        return ["manifest must be a JSON object"]
    for k in TOP_PREPASS + TOP_LLM:
        if k not in doc:
            errs.append("missing top-level key: %s" % k)
    if "schema_version" in doc and doc["schema_version"] != SCHEMA_VERSION:
        errs.append("schema_version %r != %r" % (doc["schema_version"], SCHEMA_VERSION))
    probe = (doc.get("observation") or {}).get("symptom_probe")
    if probe is not None:
        _enum(errs, "observation", "symptom_probe.status", probe.get("status"), PROBE_STATUS)
    for i, c in enumerate(doc.get("clusters") or []):
        _cluster(errs, c, i)
    ca = doc.get("catch_all")
    if isinstance(ca, dict):
        for i, adm in enumerate(ca.get("admitted") or []):
            rc = adm.get("rule_checks") or {}
            for k in RULE_CHECKS:
                if rc.get(k) is not True:
                    errs.append("catch_all.admitted[%d]: rule_checks.%s must be true" % (i, k))
    audit = doc.get("audit")
    if isinstance(audit, dict):
        for k in AUDIT_KEYS:
            if k not in audit:
                errs.append("audit.%s missing" % k)
        g = audit.get("guards")
        if isinstance(g, dict):
            for k in GUARD_KEYS:
                if k not in g:
                    errs.append("audit.guards.%s missing" % k)
            if "jql_audit" in g:
                _enum(errs, "audit.guards", "jql_audit", g["jql_audit"], JQL_AUDIT)
            if "sippy_diff" in g:
                _enum(errs, "audit.guards", "sippy_diff", g["sippy_diff"], SIPPY_DIFF)
    elif "audit" in doc:
        errs.append("audit must be an object")
    return errs


def merge(prepass, dispositions, actions):
    """Combine prepass.json with LLM-phase dispositions (id -> dict) and actions (id -> list)."""
    known = {c["id"] for c in prepass["clusters"]}
    unknown = sorted(set(dispositions) - known)
    if unknown:
        raise ValueError("dispositions for clusters not in prepass: %s" % unknown)
    out = copy.deepcopy(prepass)
    for c in out["clusters"]:
        cid = c["id"]
        if cid not in dispositions:
            continue
        disp = copy.deepcopy(dispositions[cid])
        esc = disp.pop("escalation", None)
        c["disposition"] = disp
        c["actions"] = copy.deepcopy(actions.get(cid, []))
        if esc is None:
            level = c["blast_radius"]["level"]
            unexplained = disp.get("state") == "UNEXPLAINED" and level == "ELEVATED"
            esc = {"required": level == "HIGH" or unexplained,
                   "reason": ("blast_radius HIGH" if level == "HIGH" else
                              "UNEXPLAINED at ELEVATED blast radius" if unexplained else "not required")}
        c["escalation"] = esc
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
    args = ap.parse_args(argv)
    if args.cmd == "validate":
        doc = _load(args.path)
    else:
        doc = merge(_load(args.prepass), _load(args.dispositions), _load(args.actions))
        with open(args.out, "w") as f:
            json.dump(doc, f, indent=2)
            f.write("\n")
    errs = validate(doc)
    for e in errs:
        print(e, file=sys.stderr)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
