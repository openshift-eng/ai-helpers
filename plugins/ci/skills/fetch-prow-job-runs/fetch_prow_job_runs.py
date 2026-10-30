"""List Prow job runs from the Sippy API using its filter syntax.

The /api/jobs/runs endpoint takes a JSON "filter" query parameter — NOT
ad-hoc query params like ?job_name= or ?period= (those do not exist).
Unknown columnField values yield HTTP 400 "column does not exist"; that
message is surfaced verbatim.
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

BASE_URL = "https://sippy.dptools.openshift.org/api/jobs/runs"


def since_cutoff(hours, now=None):
    """Return the lookback cutoff datetime for `hours` before `now`.

    `now` defaults to the current UTC time; pass a timezone-aware datetime to
    override it (e.g. in tests).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    return now - timedelta(hours=hours)


def build_filter(job_contains, variants, result, since, extra_items):
    """Build the Sippy filter dict. All items are ANDed together.

    `since`, when set, is a datetime. The Sippy `timestamp` column is a
    timestamptz, so it is formatted to an RFC 3339 UTC string here.
    """
    items = []
    for substr in job_contains:
        items.append({"columnField": "name", "operatorValue": "contains", "value": substr})
    for variant in variants:
        items.append({"columnField": "variants", "operatorValue": "has entry", "value": variant})
    if result is not None:
        items.append({"columnField": "overall_result", "operatorValue": "equals", "value": result})
    if since is not None:
        items.append({"columnField": "timestamp", "operatorValue": ">", "value": since.isoformat().replace("+00:00", "Z")})
    items.extend(extra_items)
    return {"items": items, "linkOperator": "and"}


def extract_ids(rows):
    return [row["prow_id"] for row in rows]


def fetch_runs(release, filter_dict, limit):
    params = {
        "release": release,
        "filter": json.dumps(filter_dict),
        "limit": str(limit),
        "sortField": "timestamp",
        "sort": "desc",
    }
    url = "%s?%s" % (BASE_URL, urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except (OSError, ValueError):
            detail = "<unable to read response body>"
        raise RuntimeError("HTTP %d from Sippy API: %s" % (e.code, detail.strip())) from e
    except urllib.error.URLError as e:
        raise RuntimeError("failed to connect to Sippy API: %s" % e.reason) from e
    try:
        data = json.loads(body)
    except ValueError as e:
        raise RuntimeError("server returned a non-JSON response body") from e
    return data.get("rows") or []


def print_summary(rows):
    for row in rows:
        print("%s  %s  %s  %s" % (
            row.get("overall_result", "?"),
            row.get("job", "?"),
            row.get("prow_id", "?"),
            row.get("timestamp", "?")))
    print("Total: %d" % len(rows))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="List Prow job runs from Sippy using proper filter syntax")
    parser.add_argument("--release", required=True, help="OpenShift release, e.g. 5.0")
    parser.add_argument("--job-contains", action="append", default=[],
                        help="substring the job name must contain (repeatable, ANDed)")
    parser.add_argument("--variant", action="append", default=[],
                        help="variant entry like Platform:metal (repeatable, ANDed)")
    parser.add_argument("--result", help="overall_result code: S=success, F=failure, n=infra failure")
    parser.add_argument("--since-hours", type=float,
                        help="only runs newer than N hours ago")
    parser.add_argument("--filter-json",
                        help="raw JSON array of extra filter items, merged with generated ones")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--ids-only", action="store_true",
                        help="print only prow_id values, one per line")
    parser.add_argument("--format", choices=["json", "summary"], default="json")
    args = parser.parse_args(argv)

    extra_items = []
    if args.filter_json:
        try:
            extra_items = json.loads(args.filter_json)
        except ValueError as e:
            print("Error: --filter-json is not valid JSON: %s" % e, file=sys.stderr)
            return 1
        if not isinstance(extra_items, list):
            print("Error: --filter-json must be a JSON array of filter items", file=sys.stderr)
            return 1

    since = since_cutoff(args.since_hours) if args.since_hours is not None else None
    filter_dict = build_filter(args.job_contains, args.variant, args.result,
                               since, extra_items)
    try:
        rows = fetch_runs(args.release, filter_dict, args.limit)
    except RuntimeError as e:
        print("Error: %s" % e, file=sys.stderr)
        return 1

    if args.ids_only:
        for prow_id in extract_ids(rows):
            print(prow_id)
    elif args.format == "summary":
        print_summary(rows)
    else:
        print(json.dumps(rows, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
