#!/usr/bin/env python3
"""Release-aware Jira target check for Component Readiness triage writes.

A regression observed on release R must be linked to the bug that is targeted at R. When the candidate
bug is targeted elsewhere (for example a closed newer-release parent), a clone of it may carry R. This
module decides, from Jira data only, which issue of the candidate's clone family is the release-specific
target, and refuses to bless a write it cannot support.

Rules (deliberately narrow):

* The release of an issue is its explicit Target Version field (``TARGET_VERSION_FIELD``) normalised to
  ``X.Y`` (``4.20.z`` and ``4.20.0`` -> ``4.20``). Summary prefixes, copied descriptions, Affects Versions
  and Fix Versions are never used for routing: clones inherit them from the issue they were cloned from.
  They are recorded as evidence only.
* The clone family is the connected component of ``Cloners`` links ("clones" / "is cloned by", both
  directions) within the candidate's Jira project. ``Blocks``, ``Depend`` and other link types are not clone
  relations; they are recorded as ignored evidence and never followed or selected.
* Traversal keeps a visited set (cycles terminate) and a node budget; exceeding the budget is an incomplete
  search.
* Decision per release R:
    - ``self``: the candidate is targeted at R;
    - ``clone``: exactly one other family member is targeted at R (the write must go there instead);
    - ``ambiguous``: more than one family member is targeted at R;
    - ``no-matching-clone``: the search was complete, every other member has a readable Target Version and
      none is R; only then may the candidate itself be written (and only then may a "no clone targets R"
      statement be made);
    - ``unknown``: any read error, missing field, unparseable target value, untargeted other member, or
      exhausted budget.
  A write to the candidate is allowed only for ``self`` and ``no-matching-clone``.

Enforcement scope: before a write this check runs only where a caller uses the bundled scripts with it
(``triage_regression.py`` / ``add_jira_triage_link.py`` with ``--require-release-target``, and
``backport_note.py``); ``manifest.py validate`` checks the recorded evidence. It is not a security boundary:
a caller with tokens and a shell can bypass the scripts. Sippy triage writes are re-checked after the fact by
``audit.py diff`` (``release_targets``) whatever channel made them; Jira comments and description edits
made outside the scripts are not.

  release_target.py check ISSUE_KEY --regression-ids 1,2   -> prints the decision record (exit 0 allowed, 3 refused)
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jira_auth  # noqa: E402

SCHEMA_VERSION = "1"
TARGET_VERSION_FIELD = "customfield_10855"      # Jira "Target Version" (see plugins/teams/skills/list-jiras)
JIRA_FIELDS = ("summary", "status", "resolution", "issuelinks", "versions", "fixVersions", TARGET_VERSION_FIELD)
CLONE_LINK_TYPE = "Cloners"
MAX_FAMILY = 40
ALLOWED_DECISIONS = ("self", "no-matching-clone")
DECISIONS = ("self", "clone", "ambiguous", "no-matching-clone", "unknown")
SIPPY_REGRESSIONS_URL = "https://sippy.dptools.openshift.org/api/component_readiness/regressions"
TIMEOUT = 30

_VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(?:z|\d+))?")
_KEY_RE = re.compile(r"^([A-Z][A-Z0-9_]*)-(\d+)$")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_release(value):
    """``4.20``, ``4.20.z``, ``4.20.0`` -> ``4.20``; anything else -> None (unknown, never a non-match)."""
    if not isinstance(value, str):
        return None
    m = _VERSION_RE.fullmatch(value.strip())
    return "%d.%d" % (int(m.group(1)), int(m.group(2))) if m else None


def issue_key(text):
    """Exact issue key from a bare key or a browse URL; None when there is none."""
    if not isinstance(text, str) or not text.strip():
        return None
    tail = text.strip().rstrip("/").rsplit("/", 1)[-1].split("?", 1)[0].split("#", 1)[0]
    return tail if _KEY_RE.match(tail) else None


def _project(key):
    m = _KEY_RE.match(key or "")
    return m.group(1) if m else None


def _names(value):
    """Names of a version-like field value: list of {name}, a single {name}, a string, or null."""
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    out = []
    for v in items:
        if isinstance(v, dict):
            out.append(v.get("name") if isinstance(v.get("name"), str) else v.get("value"))
        else:
            out.append(v)
    return out


def issue_facts(raw):
    """Normalise a ``GET /rest/api/3/issue/{key}`` response. ``problems`` lists why it cannot be relied on."""
    problems = []
    if not isinstance(raw, dict) or not isinstance(raw.get("fields"), dict):
        return {"key": raw.get("key") if isinstance(raw, dict) else None, "problems": ["no fields in response"]}
    f = raw["fields"]
    if not isinstance(f.get("issuelinks"), list):
        problems.append("issuelinks missing from response")
    targets_raw = _names(f.get(TARGET_VERSION_FIELD))   # absent or null: untargeted
    targets = sorted({normalize_release(t) for t in targets_raw if normalize_release(t)})
    if any(normalize_release(t) is None for t in targets_raw):
        problems.append("unparseable Target Version %r" % (targets_raw,))
    links = []
    for link in f.get("issuelinks") or []:
        if not isinstance(link, dict):
            problems.append("malformed issue link")
            continue
        t = link.get("type") if isinstance(link.get("type"), dict) else {}
        if isinstance(link.get("outwardIssue"), dict):
            other, direction, relation = link["outwardIssue"], "outward", t.get("outward")
        elif isinstance(link.get("inwardIssue"), dict):
            other, direction, relation = link["inwardIssue"], "inward", t.get("inward")
        else:
            problems.append("issue link without a linked issue")
            continue
        links.append({"type": t.get("name"), "direction": direction, "relation": relation, "key": other.get("key")})
    return {"key": raw.get("key"),
            "status": (f.get("status") or {}).get("name") if isinstance(f.get("status"), dict) else None,
            "resolution": (f.get("resolution") or {}).get("name") if isinstance(f.get("resolution"), dict) else None,
            "target_versions_raw": targets_raw, "target_releases": targets,
            "affects_versions": [n for n in _names(f.get("versions")) if isinstance(n, str)],
            "fix_versions": [n for n in _names(f.get("fixVersions")) if isinstance(n, str)],
            "links": links, "problems": problems}


def clone_family(candidate, fetch, max_nodes=MAX_FAMILY):
    """Walk Cloners links from ``candidate``. Returns (members{key: facts}, ignored_links[], problems[])."""
    project = _project(candidate)
    members, ignored, problems = {}, [], []
    queue, seen = [candidate], {candidate}
    while queue:
        key = queue.pop(0)
        if len(members) >= max_nodes:
            problems.append("clone family exceeds %d issues; search incomplete" % max_nodes)
            break
        try:
            facts = issue_facts(fetch(key))
        except Exception as e:      # any read failure makes the search incomplete
            problems.append("%s: lookup failed: %s: %s" % (key, type(e).__name__, e))
            continue
        if facts.get("key") and facts["key"] != key:
            problems.append("%s: lookup returned %s" % (key, facts["key"]))
            continue
        facts["key"] = key
        members[key] = facts
        problems.extend("%s: %s" % (key, p) for p in facts.get("problems", []))
        for link in facts.get("links", []):
            other = link.get("key")
            if link.get("type") != CLONE_LINK_TYPE or not issue_key(other):
                ignored.append(dict(link, from_key=key, reason="not a clone link"))
            elif _project(other) != project:
                ignored.append(dict(link, from_key=key, reason="clone in another project"))
            elif other not in seen:
                seen.add(other)
                queue.append(other)
    return members, ignored, problems


def decide(candidate, release, members, problems):
    """Decision record for one release over a resolved family (see module docstring)."""
    rec = {"release": release, "decision": "unknown", "target": None, "complete": False, "reasons": []}
    if release is None:
        rec["reasons"].append("regression release unknown")
        return rec
    if problems or candidate not in members:
        rec["reasons"] = list(problems) or ["candidate could not be read"]
        return rec
    matches = sorted(k for k, m in members.items() if release in m["target_releases"])
    untargeted = sorted(k for k, m in members.items() if k != candidate and not m["target_versions_raw"])
    rec["complete"] = True
    if len(matches) > 1:
        rec.update(decision="ambiguous", reasons=["several family members target %s: %s" % (release, ", ".join(matches))])
    elif matches:
        rec.update(decision="self" if matches[0] == candidate else "clone", target=matches[0])
    elif untargeted:
        rec.update(complete=False, reasons=["untargeted family member(s) %s may be the %s clone" % (", ".join(untargeted), release)])
    else:
        rec.update(decision="no-matching-clone", target=candidate)
    return rec


def check_write(candidate, releases, fetch, max_nodes=MAX_FAMILY):
    """Decide whether regressions on ``releases`` may be linked to ``candidate``. Never raises."""
    key = issue_key(candidate)
    out = {"schema": SCHEMA_VERSION, "issue": key, "checked_at": now(), "allowed": False,
           "releases": {}, "family": [], "ignored_links": [], "reasons": []}
    rels = sorted({r for r in releases if r} | ({None} if None in releases else set()), key=lambda r: r or "")
    if key is None:
        out["reasons"].append("no Jira issue key in %r" % (candidate,))
        return out
    if not rels:
        out["reasons"].append("no regression releases to check")
        return out
    try:
        members, ignored, problems = clone_family(key, fetch, max_nodes)
    except Exception as e:
        members, ignored, problems = {}, [], ["%s: %s" % (type(e).__name__, e)]
    out["family"] = [{k: m.get(k) for k in ("key", "status", "resolution", "target_versions_raw", "target_releases",
                                            "affects_versions", "fix_versions")} for m in members.values()]
    out["ignored_links"] = ignored
    for r in rels:
        out["releases"][r or "unknown"] = decide(key, r, members, problems)
    bad = {r: d for r, d in out["releases"].items() if d["decision"] not in ALLOWED_DECISIONS or d["target"] != key}
    out["allowed"] = not bad
    for r, d in sorted(bad.items()):
        out["reasons"].append("release %s: %s%s%s" % (r, d["decision"], " -> " + d["target"] if d["target"] else "",
                                                     "; " + "; ".join(d["reasons"]) if d["reasons"] else ""))
    return out


def validate_record(rec, issue=None, releases=None, not_before=None, require=ALLOWED_DECISIONS):
    """Errors for a stored check record (manifest evidence). Empty list means it supports the write."""
    if not isinstance(rec, dict):
        return ["release_check missing"]
    errs = []
    if rec.get("schema") != SCHEMA_VERSION:
        errs.append("release_check.schema %r != %r" % (rec.get("schema"), SCHEMA_VERSION))
    if rec.get("allowed") is not True:
        errs.append("release_check.allowed is not true")
    if issue is not None and rec.get("issue") != issue_key(issue):
        errs.append("release_check.issue %r != %r" % (rec.get("issue"), issue_key(issue)))
    per = rec.get("releases")
    if not isinstance(per, dict) or not per:
        return errs + ["release_check.releases missing"]
    for r, d in per.items():
        if not isinstance(d, dict) or d.get("decision") not in require or d.get("target") != rec.get("issue") \
                or d.get("complete") is not True:
            errs.append("release_check.releases[%s] does not support the write: %r" % (
                r, d.get("decision") if isinstance(d, dict) else d))
    for r in releases or []:
        if normalize_release(r) not in per:
            errs.append("release_check has no decision for release %s" % r)
    checked = rec.get("checked_at")
    if not isinstance(checked, str) or not checked:
        errs.append("release_check.checked_at missing")
    elif not_before and _ts(checked) is not None and _ts(not_before) is not None and _ts(checked) < _ts(not_before):
        errs.append("release_check.checked_at %s predates this run (%s); re-resolve" % (checked, not_before))
    elif not_before and _ts(checked) is None:
        errs.append("release_check.checked_at %r unparseable" % checked)
    return errs


def _ts(text):
    try:
        s = text.strip().replace("Z", "+00:00")
        m = re.match(r"^(.*T\d\d:\d\d:\d\d)(\.\d+)?(.*)$", s)
        if m:
            s = m.group(1) + (m.group(2) or "")[:7] + m.group(3)
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (AttributeError, ValueError):
        return None


def _get_json(url, headers=None):
    req = urllib.request.Request(url, headers=dict({"Accept": "application/json"}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def jira_fetcher(auth=None):
    """fetch(key) -> raw issue JSON with exactly the fields this module needs."""
    auth = auth or jira_auth.resolve()
    fields = ",".join(JIRA_FIELDS)

    def fetch(key):
        return _get_json(auth.url("/rest/api/3/issue/%s?fields=%s" % (urllib.parse.quote(key), fields)),
                         {"Authorization": auth.authorization()})
    return fetch


def regression_releases(regression_ids, fetch_regression=None):
    """{id: "X.Y" or None} from the public Sippy regression API; failures map to None (unknown)."""
    fetch_regression = fetch_regression or (lambda rid: _get_json("%s/%s" % (SIPPY_REGRESSIONS_URL, rid)))
    out = {}
    for rid in regression_ids:
        try:
            out[rid] = normalize_release((fetch_regression(rid) or {}).get("release"))
        except Exception:
            out[rid] = None
    return out


def check_regressions(candidate, regression_ids, fetch=None, fetch_regression=None):
    """Full pre-write check: regression releases from Sippy, then the clone-family decision. Never raises."""
    rels = regression_releases(regression_ids, fetch_regression)
    if fetch is None:
        try:
            fetch = jira_fetcher()
        except Exception as e:      # no credentials: every lookup fails, so the decision is unknown
            err = "Jira unavailable: %s: %s" % (type(e).__name__, e)

            def fetch(_key, _err=err):
                raise RuntimeError(_err)
    out = check_write(candidate, set(rels.values()), fetch)
    out["regression_releases"] = {str(k): v for k, v in sorted(rels.items())}
    if not regression_ids:
        out["allowed"] = False
        out["reasons"].append("no regression ids")
    return out


def main(argv=None):
    p = argparse.ArgumentParser(prog="release_target.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="decide whether regressions may be linked to ISSUE")
    c.add_argument("issue")
    c.add_argument("--regression-ids", required=True, help="comma-separated Component Readiness regression ids")
    args = p.parse_args(argv)
    try:
        ids = [int(x) for x in args.regression_ids.split(",") if x.strip()]
    except ValueError:
        print("--regression-ids must be comma-separated integers", file=sys.stderr)
        return 2
    rec = check_regressions(args.issue, ids)
    print(json.dumps(rec, indent=2))
    return 0 if rec["allowed"] else 3


if __name__ == "__main__":
    sys.exit(main())
