"""Create, update, or delete Sippy Symptoms (requires auth token)."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

WRITE_URL = "https://sippy-auth.dptools.openshift.org/api/jobs/symptoms"
READ_SYMPTOMS_URL = "https://sippy.dptools.openshift.org/api/jobs/symptoms"
READ_LABELS_URL = "https://sippy.dptools.openshift.org/api/jobs/labels"
VALID_MATCHERS = ("string", "regex", "none", "cel")


def resolve_token(arg_token, env=None):
    """Return the Bearer token from --token or the SIPPY_TOKEN env var.

    --token takes precedence over the environment variable. Prefer the env
    var: command-line arguments are visible in process listings.
    """
    env = os.environ if env is None else env
    return arg_token or env.get("SIPPY_TOKEN") or None


def validate_symptom(payload):
    errs = []
    summary = payload.get("summary")
    if not summary:
        errs.append("summary is required")
    elif len(summary) > 200:
        errs.append("summary must be at most 200 characters")
    mt = payload.get("matcher_type")
    if mt not in VALID_MATCHERS:
        errs.append("matcher_type must be one of: %s" % ", ".join(VALID_MATCHERS))
        return errs
    if mt != "cel" and not payload.get("file_pattern"):
        errs.append("file_pattern is required for matcher_type %r" % mt)
    if mt in ("string", "regex", "cel") and not payload.get("match_string"):
        errs.append("match_string is required for matcher_type %r" % mt)
    return errs


def build_update_payload(existing, summary=None, matcher_type=None,
                         file_pattern=None, match_string=None, label_ids=None):
    """Merge changed fields into the existing symptom for a full-replacement PUT.

    Pass None to preserve the existing value; an explicit empty string for
    file_pattern/match_string clears it. label_ids is a list when overriding.
    """
    return {"id": existing.get("id"),
            "summary": summary or existing.get("summary"),
            "matcher_type": matcher_type or existing.get("matcher_type"),
            "file_pattern": file_pattern if file_pattern is not None else existing.get("file_pattern"),
            "match_string": match_string if match_string is not None else existing.get("match_string"),
            "label_ids": label_ids if label_ids is not None else existing.get("label_ids", [])}


def parse_label_ids(value):
    """Parse the --label-ids flag. None = flag not passed (preserve on update);
    empty string = explicit clear (returns []); otherwise comma-separated list."""
    if value is None:
        return None
    return [x.strip() for x in value.split(",") if x.strip()]


def symptom_url(base, symptom_id):
    return "%s/%s" % (base, urllib.parse.quote(symptom_id, safe=""))


def get_json(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print("Error fetching %s: %s" % (url, e), file=sys.stderr)
        return None


def check_labels_exist(label_ids):
    labels = get_json(READ_LABELS_URL)
    if not isinstance(labels, list) or not all(isinstance(label, dict) for label in labels):
        return ["could not verify label IDs (labels API unreachable or returned unexpected data)"]
    known = {label.get("id") for label in labels}
    return ["label ID %r does not exist (create it first with the manage-labels skill)" % lid
            for lid in label_ids if lid not in known]


def request(method, url, token, payload=None):
    headers = {"Content-Type": "application/json", "Authorization": "Bearer %s" % token}
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return {"success": True, "result": json.loads(body) if body.strip() else {}}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            pass
        hint = ""
        if e.code == 501:
            hint = " (write endpoints are disabled on this instance; make sure you are using sippy-auth)"
        elif e.code in (401, 403):
            hint = " (token missing/expired; use the oc-auth skill to obtain a fresh token)"
        return {"success": False, "error": "HTTP %d: %s%s" % (e.code, e.reason, hint), "detail": detail}
    except urllib.error.URLError as e:
        return {"success": False, "error": "Failed to connect: %s" % e.reason}


def main():
    p = argparse.ArgumentParser(description="Create/update/delete Sippy symptoms")
    p.add_argument("action", choices=["create", "update", "delete"])
    p.add_argument("--token", help="Bearer token (or set SIPPY_TOKEN env var, preferred; use oc-auth skill)")
    p.add_argument("--id", help="Symptom ID (required for update/delete; server-generated on create)")
    p.add_argument("--summary", help="Short unique description (required for create, max 200 chars)")
    p.add_argument("--matcher-type", choices=list(VALID_MATCHERS),
                   help="How match_string is interpreted: string=substring, regex, "
                        "none=file exists, cel=CEL expression over label names")
    p.add_argument("--file-pattern", help="Artifact glob, e.g. '**/build-log.txt'")
    p.add_argument("--match-string", help="Substring, regex, or CEL expression")
    p.add_argument("--label-ids", help="Comma-separated label IDs to apply on match")
    p.add_argument("--skip-label-check", action="store_true",
                   help="Skip verifying label IDs against the labels API")
    p.add_argument("--format", choices=["json", "summary"], default="json")
    args = p.parse_args()

    token = resolve_token(args.token)
    if not token:
        print("Error: no token provided — pass --token or set the SIPPY_TOKEN "
              "environment variable (preferred; use the oc-auth skill to obtain "
              "one)", file=sys.stderr)
        return 1

    if args.action in ("update", "delete") and not args.id:
        print("Error: --id is required for %s" % args.action, file=sys.stderr)
        return 1

    if args.action == "delete":
        out = request("DELETE", symptom_url(WRITE_URL, args.id), token)
    else:
        label_ids = parse_label_ids(args.label_ids)
        if args.action == "create":
            payload = {"summary": args.summary, "matcher_type": args.matcher_type,
                       "file_pattern": args.file_pattern, "match_string": args.match_string,
                       "label_ids": label_ids or []}
        else:
            existing = get_json(symptom_url(READ_SYMPTOMS_URL, args.id))
            if existing is None:
                print("Error: cannot fetch existing symptom %s (see error above; "
                      "check the ID with the list-symptoms skill)" % args.id, file=sys.stderr)
                return 1
            existing["id"] = args.id
            payload = build_update_payload(existing, summary=args.summary,
                                           matcher_type=args.matcher_type,
                                           file_pattern=args.file_pattern,
                                           match_string=args.match_string,
                                           label_ids=label_ids)
        payload = {k: v for k, v in payload.items() if v is not None}
        errs = validate_symptom(payload)
        if not args.skip_label_check and payload.get("label_ids"):
            errs += check_labels_exist(payload["label_ids"])
        if errs:
            for e in errs:
                print("Validation error: %s" % e, file=sys.stderr)
            return 1
        if args.action == "create":
            out = request("POST", WRITE_URL, token, payload)
        else:
            out = request("PUT", symptom_url(WRITE_URL, args.id), token, payload)

    if args.format == "json":
        print(json.dumps(out, indent=2))
    else:
        if out["success"]:
            print("Symptom %s - SUCCESS" % args.action)
            print(json.dumps(out.get("result", {}), indent=2))
        else:
            print("Symptom %s - FAILED: %s" % (args.action, out.get("error")))
            if out.get("detail"):
                print("Detail: %s" % out["detail"])
    return 0 if out["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
