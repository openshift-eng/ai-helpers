"""Create, update, or delete Sippy job run Labels (requires auth token)."""
import argparse
import json
import sys
import urllib.error
import urllib.request

WRITE_URL = "https://sippy-auth.dptools.openshift.org/api/jobs/labels"
READ_URL = "https://sippy.dptools.openshift.org/api/jobs/labels"
VALID_HIDE_CONTEXTS = ("spyglass", "metrics", "jaq-options")


def validate_label(payload):
    errs = []
    if not payload.get("label_title"):
        errs.append("label_title is required")
    if payload.get("id") and len(payload["id"]) > 80:
        errs.append("id must be at most 80 characters")
    for ctx in payload.get("hide_display_contexts") or []:
        if ctx not in VALID_HIDE_CONTEXTS:
            errs.append("invalid hide_display_contexts value %r (valid: %s)" % (ctx, ", ".join(VALID_HIDE_CONTEXTS)))
    return errs


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


def fetch_existing(label_id):
    try:
        with urllib.request.urlopen("%s/%s" % (READ_URL, label_id), timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print("Error: cannot fetch existing label %s: %s" % (label_id, e), file=sys.stderr)
        return None


def main():
    p = argparse.ArgumentParser(description="Create/update/delete Sippy labels")
    p.add_argument("action", choices=["create", "update", "delete"])
    p.add_argument("--token", required=True, help="Bearer token (use oc-auth skill)")
    p.add_argument("--id", help="Label ID (required for update/delete; optional for create)")
    p.add_argument("--title", help="Human-readable label title (required for create)")
    p.add_argument("--explanation", help="Markdown explanation of the label")
    p.add_argument("--hide-display-contexts", help="Comma-separated: spyglass,metrics,jaq-options")
    p.add_argument("--format", choices=["json", "summary"], default="json")
    args = p.parse_args()

    if args.action in ("update", "delete") and not args.id:
        print("Error: --id is required for %s" % args.action, file=sys.stderr)
        return 1

    if args.action == "delete":
        out = request("DELETE", "%s/%s" % (WRITE_URL, args.id), args.token)
    else:
        if args.action == "create":
            payload = {"label_title": args.title, "explanation": args.explanation or ""}
            if args.id:
                payload["id"] = args.id
        else:
            existing = fetch_existing(args.id)
            if existing is None:
                return 1
            payload = {"id": args.id,
                       "label_title": args.title or existing.get("label_title"),
                       "explanation": args.explanation if args.explanation is not None else existing.get("explanation", ""),
                       "hide_display_contexts": existing.get("hide_display_contexts")}
        if args.hide_display_contexts is not None:
            payload["hide_display_contexts"] = [c.strip() for c in args.hide_display_contexts.split(",") if c.strip()]
        payload = {k: v for k, v in payload.items() if v is not None}
        errs = validate_label(payload)
        if errs:
            for e in errs:
                print("Validation error: %s" % e, file=sys.stderr)
            return 1
        if args.action == "create":
            out = request("POST", WRITE_URL, args.token, payload)
        else:
            out = request("PUT", "%s/%s" % (WRITE_URL, args.id), args.token, payload)

    if args.format == "json":
        print(json.dumps(out, indent=2))
    else:
        if out["success"]:
            print("Label %s - SUCCESS" % args.action)
            print(json.dumps(out.get("result", {}), indent=2))
        else:
            print("Label %s - FAILED: %s" % (args.action, out.get("error")))
            if out.get("detail"):
                print("Detail: %s" % out["detail"])
    return 0 if out["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
