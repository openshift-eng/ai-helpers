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
import http.client
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

READ_BASE = "https://sippy.dptools.openshift.org/api/jobs"
JIRA_URL_PREFIX = "https://redhat.atlassian.net/browse/"
REEVALUATE_URL = "https://sippy-auth.dptools.openshift.org/api/jobs/runs/reevaluate"
GCS_API = "https://storage.googleapis.com/storage/v1/b"
REQUEST_TIMEOUT_SECONDS = 300
POLL_INTERVAL_SECONDS = 5
NONTERMINAL_STATES = frozenset(("pending", "processing", "running"))
TERMINAL_STATES = frozenset(("complete", "failed", "cancelled"))
BATCH_STATES = NONTERMINAL_STATES | TERMINAL_STATES


class ClientError(Exception):
    """A controlled authenticated API error."""


def resolve_token(arg_token, env=None):
    """Return the Bearer token from --token or the SIPPY_TOKEN env var.

    --token takes precedence over the environment variable. Prefer the env
    var: command-line arguments are visible in process listings.
    """
    env = os.environ if env is None else env
    return arg_token or env.get("SIPPY_TOKEN") or None


def _origin(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        raise ValueError("URL must use HTTP(S) and include a hostname")
    default_port = 443 if parsed.scheme.lower() == "https" else 80
    return (parsed.scheme.lower(), parsed.hostname.lower(), parsed.port or default_port)


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects that would leave the authenticated API origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            same_origin = _origin(req.full_url) == _origin(newurl)
        except ValueError as exc:
            raise ClientError("invalid API URL or redirect: %s" % exc) from exc
        if not same_origin:
            raise ClientError("refusing to follow a cross-origin API redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


HTTP_OPENER = urllib.request.build_opener(SafeRedirectHandler())


def _read_body(response):
    try:
        return response.read().decode("utf-8")
    except (TimeoutError, socket.timeout) as exc:
        raise ClientError("request timed out while reading the response") from exc
    except (OSError, http.client.HTTPException, UnicodeError) as exc:
        raise ClientError("could not read the API response: %s" % exc) from exc


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


def _api_message(body):
    if not body:
        return ""
    try:
        decoded = json.loads(body)
    except (TypeError, ValueError):
        return body.strip()[:500]
    if isinstance(decoded, dict) and decoded.get("message"):
        return str(decoded["message"])
    return body.strip()[:500]


def request_json(method, url, token, expected_status, payload=None):
    """Make one authenticated request and return its decoded JSON body."""
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Accept": "application/json",
            "Authorization": "Bearer %s" % token,
            **({"Content-Type": "application/json"} if data is not None else {}),
        },
        method=method,
    )
    try:
        with HTTP_OPENER.open(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            status = response.getcode()
            body = _read_body(response)
    except urllib.error.HTTPError as exc:
        try:
            body = _read_body(exc)
        except ClientError:
            body = ""
        detail = _api_message(body)
        suffix = ": %s" % detail if detail else ""
        if exc.code in (401, 403):
            raise ClientError(
                "HTTP %d (token missing/expired; use the oc-auth skill)%s" %
                (exc.code, suffix)
            ) from exc
        raise ClientError("HTTP %d%s" % (exc.code, suffix)) from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise ClientError("request timed out connecting to the API") from exc
        raise ClientError("connection error: %s" % exc.reason) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise ClientError("request timed out connecting to the API") from exc
    except ValueError as exc:
        raise ClientError("invalid API URL or redirect: %s" % exc) from exc
    except (OSError, http.client.HTTPException) as exc:
        raise ClientError("connection error: %s" % exc) from exc

    if status != expected_status:
        raise ClientError("expected HTTP %d, got HTTP %d" % (expected_status, status))
    decoded, error = classify_response(body)
    if error:
        raise ClientError(error)
    return decoded


def _validate_submit_response(data):
    if not isinstance(data, dict):
        raise ClientError("submission response is not a JSON object")
    if not isinstance(data.get("batch_id"), str) or not data["batch_id"]:
        raise ClientError("submission response is missing batch_id")
    if not isinstance(data.get("requested"), int):
        raise ClientError("submission response is missing requested")
    links = data.get("links")
    if not isinstance(links, dict) or not isinstance(links.get("status"), str):
        raise ClientError("submission response is missing links.status")
    return data


def _validate_batch_response(data, batch_id):
    if not isinstance(data, dict):
        raise ClientError("batch status response is not a JSON object")
    if data.get("batch_id") != batch_id:
        raise ClientError("batch status response has an unexpected batch_id")
    if not isinstance(data.get("status"), str):
        raise ClientError("batch status response is missing status")
    if data["status"] not in BATCH_STATES:
        raise ClientError("batch status response has unknown status %r" % data["status"])
    for field in ("requested", "enqueued", "deduped", "completed", "failed", "running", "pending"):
        if not isinstance(data.get(field), int):
            raise ClientError("batch status response is missing integer %s" % field)
    items = data.get("items")
    if not isinstance(items, list):
        raise ClientError("batch status response is missing items")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ClientError("batch status item %d is not a JSON object" % index)
        if not isinstance(item.get("item_key"), str) or not isinstance(item.get("state"), str):
            raise ClientError("batch status item %d is missing item_key or state" % index)
        if "result" in item and not isinstance(item["result"], dict):
            raise ClientError("batch status item %d has a non-object result" % index)
    return data


def deep_reevaluate(build_id, token):
    """Submit and poll one asynchronous dry-run reevaluation."""
    submission = _validate_submit_response(request_json(
        "POST",
        REEVALUATE_URL,
        token,
        202,
        {"prow_job_build_ids": [build_id], "dry_run": True},
    ))
    if submission["requested"] != 1:
        raise ClientError(
            "submission response requested %d items, expected 1" % submission["requested"]
        )

    try:
        status_url = urllib.parse.urljoin(REEVALUATE_URL, submission["links"]["status"])
        status_origin = _origin(status_url)
    except ValueError as exc:
        raise ClientError("invalid links.status URL: %s" % exc) from exc
    if _origin(REEVALUATE_URL) != status_origin:
        raise ClientError("refusing to send the Bearer token to a cross-origin status URL")

    while True:
        status = _validate_batch_response(
            request_json("GET", status_url, token, 200), submission["batch_id"]
        )
        if status["status"] in TERMINAL_STATES:
            return status
        time.sleep(POLL_INTERVAL_SECONDS)


def _results_for_build(status, build_id):
    matching = [item for item in status["items"] if item["item_key"] == build_id]
    if len(matching) != 1:
        raise ClientError(
            "batch status response has %d items for requested build %s" %
            (len(matching), build_id)
        )
    result = matching[0].get("result")
    return [] if result is None else [result]


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


def jira_issue_url(key):
    """Return the browse URL for a Jira issue key."""
    return JIRA_URL_PREFIX + urllib.parse.quote(key, safe="")


def format_jira_issues(keys):
    """Format Jira issue keys with browse URLs for summary output."""
    return ", ".join("%s (%s)" % (key, jira_issue_url(key)) for key in keys)


def main(argv=None):
    p = argparse.ArgumentParser(description="Diagnose which Sippy symptoms/labels apply to a job run")
    p.add_argument("prow_url", help="Prow job run URL (https://prow.ci.openshift.org/view/gs/...)")
    p.add_argument("--deep", action="store_true",
                   help="Server-side dry-run rescan via the reevaluate API (requires --token)")
    p.add_argument("--token", help="Bearer token, required with --deep "
                   "(or set SIPPY_TOKEN env var, preferred; use oc-auth skill)")
    p.add_argument("--format", choices=["json", "summary"], default="summary")
    args = p.parse_args(argv)

    token = resolve_token(args.token)
    if args.deep and not token:
        print("Error: --deep requires a token — pass --token or set the SIPPY_TOKEN "
              "environment variable (preferred; use the oc-auth skill to obtain "
              "one)", file=sys.stderr)
        return 1

    try:
        bucket, path, build_id = parse_prow_url(args.prow_url)
    except ValueError as e:
        print("Error: %s" % e, file=sys.stderr)
        return 1

    try:
        labels_catalog = index_by_id(get_json("%s/labels" % READ_BASE))
        symptoms_catalog = index_by_id(get_json("%s/symptoms" % READ_BASE))
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as e:
        print("Error: cannot reach Sippy API: %s" % e, file=sys.stderr)
        return 1

    report = {"build_id": build_id, "mode": "deep" if args.deep else "applied", "matches": []}

    if args.deep:
        try:
            status = deep_reevaluate(build_id, token)
            if status["status"] != "complete":
                raise ClientError(
                    "deep reevaluation batch ended in %s" % status["status"]
                )
            results = _results_for_build(status, build_id)
        except ClientError as exc:
            print("Error: %s" % exc, file=sys.stderr)
            return 1
        report["reevaluate_results"] = results
        for r in results:
            for lid in r.get("labels_applied") or []:
                report["matches"].append({"label_id": lid,
                                          "label": labels_catalog.get(lid, {})})
    else:
        try:
            entries = fetch_applied_labels(bucket, path)
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as e:
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
        if label.get("bugs"):
            print("  Bugs: %s" % format_jira_issues(label["bugs"]))
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
