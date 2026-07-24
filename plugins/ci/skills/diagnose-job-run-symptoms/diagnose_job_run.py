"""Explain which Sippy Symptoms/Labels apply to a Prow job run.

Default mode reads already-applied labels from the run's public GCS artifacts
(no auth). Deep mode (--deep --token) asks Sippy to re-scan the run server-side
with dry_run=true and reports what would match now.

GCS artifact schema (verified live 2026-07): each object under
artifacts/job_labels/*.json contains a single wrapped entry:
    {"symptom_label_v1": {"symptom": {...}, "label": {...},
                          "file_match": "<path>", "text_match": "<line>"}}
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

READ_BASE = "https://sippy.dptools.openshift.org/api/jobs"
REEVALUATE_URL = "https://sippy-auth.dptools.openshift.org/api/jobs/runs/reevaluate"
GCS_API = "https://storage.googleapis.com/storage/v1/b"


def parse_prow_url(url):
    marker = "/view/gs/"
    if marker not in url:
        raise ValueError("expected a Prow job URL containing '/view/gs/', got %r" % url)
    url = url.strip().split("#", 1)[0].split("?", 1)[0]
    rest = url.split(marker, 1)[1].strip("/")
    parts = rest.split("/")
    if len(parts) < 2 or not parts[-1].isdigit():
        raise ValueError("could not parse bucket/path/build_id from %r" % url)
    return parts[0], "/".join(parts[1:]), parts[-1]


def normalize_label_entry(entry):
    """Normalize one job_labels JSON entry to a flat match dict.

    Handles the observed wrapped schema ({"symptom_label_v1": {...}}) plus a
    flat fallback (keys like label_id/id and symptom_id) for robustness.
    """
    inner = entry.get("symptom_label_v1") if isinstance(entry, dict) else None
    if isinstance(inner, dict):
        label = inner.get("label") or {}
        symptom = inner.get("symptom") or {}
        return {
            "label_id": label.get("id"),
            "label": label,
            "symptom_id": symptom.get("id"),
            "symptom": symptom,
            "file_match": inner.get("file_match"),
            "text_match": inner.get("text_match"),
            "raw": entry,
        }
    if isinstance(entry, dict):
        return {
            "label_id": entry.get("label_id") or entry.get("id"),
            "label": entry.get("label") or {},
            "symptom_id": entry.get("symptom_id"),
            "symptom": entry.get("symptom") or {},
            "file_match": entry.get("file_match"),
            "text_match": entry.get("text_match"),
            "raw": entry,
        }
    return {"label_id": None, "label": {}, "symptom_id": None, "symptom": {},
            "file_match": None, "text_match": None, "raw": entry}


def classify_response(body):
    """Classify a deep-mode response body. Returns (parsed_json, error).

    Mirrors reevaluate_job_runs.py: an HTML body is either an SSO login page
    (expired token — the proxy redirects instead of returning 401) or a
    gateway error page; anything else must be valid JSON.
    """
    if body.lstrip().startswith("<"):
        if "log in" in body.lower():
            return None, ("got an SSO login page instead of JSON — token is "
                          "missing/expired; use the oc-auth skill to refresh it")
        return None, "gateway returned an HTML error page (likely 504 timeout); retry later"
    try:
        return json.loads(body), None
    except ValueError:
        return None, "server returned a non-JSON response body"


def get_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_applied_labels(bucket, path):
    """Return list of label entries from gs://bucket/path/artifacts/job_labels/*.json."""
    prefix = "%s/artifacts/job_labels/" % path
    list_url = "%s/%s/o?prefix=%s" % (GCS_API, bucket, urllib.parse.quote(prefix, safe=""))
    listing = get_json(list_url)
    entries = []
    for obj in listing.get("items", []):
        if not obj["name"].endswith(".json"):
            continue
        media = "%s/%s/o/%s?alt=media" % (GCS_API, bucket, urllib.parse.quote(obj["name"], safe=""))
        data = get_json(media)
        if isinstance(data, list):
            entries.extend(data)
        else:
            entries.append(data)
    return entries


def index_by_id(items):
    return {i.get("id"): i for i in items}


def main():
    p = argparse.ArgumentParser(description="Diagnose which Sippy symptoms/labels apply to a job run")
    p.add_argument("prow_url", help="Prow job run URL (https://prow.ci.openshift.org/view/gs/...)")
    p.add_argument("--deep", action="store_true",
                   help="Server-side dry-run rescan via the reevaluate API (requires --token)")
    p.add_argument("--token", help="Bearer token, required with --deep (use oc-auth skill)")
    p.add_argument("--format", choices=["json", "summary"], default="summary")
    args = p.parse_args()

    if args.deep and not args.token:
        print("Error: --deep requires --token (use the oc-auth skill)", file=sys.stderr)
        return 1

    try:
        bucket, path, build_id = parse_prow_url(args.prow_url)
    except ValueError as e:
        print("Error: %s" % e, file=sys.stderr)
        return 1

    try:
        labels_catalog = index_by_id(get_json("%s/labels" % READ_BASE))
        symptoms_catalog = index_by_id(get_json("%s/symptoms" % READ_BASE))
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print("Error: cannot reach Sippy API: %s" % e, file=sys.stderr)
        return 1

    report = {"build_id": build_id, "mode": "deep" if args.deep else "applied", "matches": []}

    if args.deep:
        req = urllib.request.Request(
            REEVALUATE_URL,
            data=json.dumps({"prow_job_build_ids": [build_id], "dry_run": True}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer %s" % args.token},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            hint = " (token expired? use oc-auth)" if e.code in (401, 403) else ""
            print("Error: HTTP %d: %s%s" % (e.code, e.reason, hint), file=sys.stderr)
            return 1
        except urllib.error.URLError as e:
            print("Error: failed to connect to Sippy API: %s" % e.reason, file=sys.stderr)
            return 1
        result, err = classify_response(body)
        if err:
            print("Error: %s" % err, file=sys.stderr)
            return 1
        report["reevaluate_results"] = result.get("results", [])
        for r in result.get("results", []):
            for lid in r.get("labels_applied") or []:
                report["matches"].append({"label_id": lid,
                                          "label": labels_catalog.get(lid, {})})
    else:
        try:
            entries = fetch_applied_labels(bucket, path)
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            print("Error: cannot read GCS artifacts for this run: %s" % e, file=sys.stderr)
            return 1
        for entry in entries:
            m = normalize_label_entry(entry)
            # Enrich with the live catalogs (embedded copies may lack
            # explanation text that was added after the run was labeled).
            if m["label_id"] and labels_catalog.get(m["label_id"]):
                m["label"] = labels_catalog[m["label_id"]]
            if m["symptom_id"] and symptoms_catalog.get(m["symptom_id"]):
                m["symptom"] = symptoms_catalog[m["symptom_id"]]
            report["matches"].append(m)

    if args.format == "json":
        print(json.dumps(report, indent=2))
        return 0

    print("Symptom diagnosis for run %s (%s mode)" % (build_id, report["mode"]))
    print("=" * 60)
    if not report["matches"]:
        print("No symptom labels found for this run.")
        if not args.deep:
            print("The run may never have been scanned (default mode cannot distinguish")
            print("that from 'scanned, nothing matched') — try --deep --token \"$TOKEN\"")
            print("for a server-side rescan with the current symptom set.")
        print("If you have identified the failure cause, consider creating a new")
        print("symptom with the manage-symptoms skill so future runs are auto-labeled.")
        return 0
    for m in report["matches"]:
        label = m.get("label") or {}
        print("Label: %s — %s" % (m.get("label_id"), label.get("label_title", "(unknown label)")))
        if label.get("explanation"):
            print("  Meaning: %s" % label["explanation"])
        sym = m.get("symptom") or {}
        if sym:
            print("  Matched symptom: %s (%s)" % (sym.get("id"), sym.get("summary")))
            print("    Rule: %s matcher on %s" % (sym.get("matcher_type"), sym.get("file_pattern")))
            if sym.get("match_string"):
                print("    Pattern: %s" % sym.get("match_string"))
        if m.get("file_match"):
            print("    Matched file: %s" % m["file_match"])
        if m.get("text_match"):
            print("    Matched text: %s" % m["text_match"].strip())
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
