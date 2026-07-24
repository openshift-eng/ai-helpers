"""List, search, and fetch Sippy Symptoms and Labels (read-only, no auth)."""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://sippy.dptools.openshift.org/api/jobs"


def item_url(resource, item_id):
    """Build the URL for a single symptom/label, URL-encoding the ID."""
    return "%s/%s/%s" % (BASE_URL, resource, urllib.parse.quote(item_id, safe=""))


def fetch(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("Error: not found: %s (use list mode to see valid IDs)" % url, file=sys.stderr)
        else:
            print("Error: HTTP %d from %s: %s" % (e.code, url, e.reason), file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print("Error: failed to connect to Sippy API: %s" % e.reason, file=sys.stderr)
        sys.exit(1)


def filter_symptoms(symptoms, search=None, label=None, matcher_type=None):
    out = []
    for s in symptoms:
        if search:
            hay = " ".join([s.get("id", ""), s.get("summary", ""), s.get("match_string", "") or ""]).lower()
            if search.lower() not in hay:
                continue
        if label and label not in (s.get("label_ids") or []):
            continue
        if matcher_type and s.get("matcher_type") != matcher_type:
            continue
        out.append(s)
    return out


def summarize_symptom(s):
    lines = ["Symptom: %s" % s.get("id")]
    lines.append("  Summary:      %s" % s.get("summary"))
    lines.append("  Matcher:      %s" % s.get("matcher_type"))
    if s.get("file_pattern"):
        lines.append("  File pattern: %s" % s.get("file_pattern"))
    if s.get("match_string"):
        lines.append("  Match string: %s" % s.get("match_string"))
    lines.append("  Labels:       %s" % ", ".join(s.get("label_ids") or []))
    lines.append("  Updated by:   %s at %s" % (s.get("updated_by"), s.get("updated_at")))
    return "\n".join(lines)


def filter_labels(labels, search=None):
    if not search:
        return labels
    out = []
    for label in labels:
        hay = " ".join([label.get("id", ""), label.get("label_title", ""),
                        label.get("explanation", "") or ""]).lower()
        if search.lower() in hay:
            out.append(label)
    return out


def summarize_label(label):
    lines = ["Label: %s" % label.get("id")]
    lines.append("  Title:       %s" % label.get("label_title"))
    if label.get("explanation"):
        lines.append("  Explanation: %s" % label.get("explanation"))
    if label.get("hide_display_contexts"):
        lines.append("  Hidden in:   %s" % ", ".join(label["hide_display_contexts"]))
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="List/search Sippy symptoms and labels")
    p.add_argument("--id", help="Fetch a single symptom (or label with --labels) by ID")
    p.add_argument("--search", help="Case-insensitive text search over id/summary/match_string")
    p.add_argument("--label", help="Only symptoms that apply this label ID")
    p.add_argument("--matcher-type", choices=["string", "regex", "none", "cel"])
    p.add_argument("--labels", action="store_true", help="List labels instead of symptoms")
    p.add_argument("--format", choices=["json", "summary"], default="json")
    args = p.parse_args()

    if args.labels and (args.label or args.matcher_type):
        print("Error: --label and --matcher-type only apply to symptoms and cannot "
              "be combined with --labels", file=sys.stderr)
        return 1

    resource = "labels" if args.labels else "symptoms"
    if args.id:
        items = [fetch(item_url(resource, args.id))]
    else:
        items = fetch("%s/%s" % (BASE_URL, resource))
        if args.labels:
            items = filter_labels(items, args.search)
        else:
            items = filter_symptoms(items, args.search, args.label, args.matcher_type)

    if args.format == "json":
        print(json.dumps(items, indent=2))
    else:
        fmt = summarize_label if args.labels else summarize_symptom
        print(("\n\n".join(fmt(i) for i in items)) if items else "No results.")
        print("\nTotal: %d" % len(items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
