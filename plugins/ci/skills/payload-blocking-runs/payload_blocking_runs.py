#!/usr/bin/env python3
"""List gcsweb artifact URLs for /payload test runs triggered on a pull request.

This queries the CI analytics BigQuery table for payload jobs run against a
specific PR, then (by default) filters them down to the runs that correspond
to the *blocking* jobs of one or more release streams. The blocking-job set is
read live from the OpenShift release controller.

Output is a sorted list of gcsweb artifact base URLs (one per line), suitable
as input to other tools -- for example, the ``kubelet-version-check`` skill.

Auth:
    BigQuery uses Application Default Credentials (ADC). Run:
        gcloud auth application-default login

Requires:
    google-cloud-bigquery, requests
"""

import argparse
import re
import sys
from datetime import datetime, timezone

try:
    import requests
except ImportError:  # pragma: no cover - dependency guard
    print(
        "ERROR: the 'requests' package is required (pip install requests).",
        file=sys.stderr,
    )
    sys.exit(2)

try:
    from google.cloud import bigquery
except ImportError:  # pragma: no cover - dependency guard
    print(
        "ERROR: the 'google-cloud-bigquery' package is required "
        "(pip install google-cloud-bigquery).",
        file=sys.stderr,
    )
    sys.exit(2)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BQ_TABLE = "openshift-gce-devel.ci_analysis_us.jobs"
RC_API_BASE = "https://amd64.ocp.releases.ci.openshift.org/api/v1"
GCSWEB_BASE = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs"
GCS_BUCKET = "test-platform-results"

# Matches the "<stream>-<version>-" prefix that precedes the test-specific
# suffix inside a periodic payload job name, e.g. "nightly-4.20-" or "ci-4.20-".
# Everything after the *last* such match is the "test suffix".
_STREAM_PREFIX_RE = re.compile(r"(?:nightly|ci)-\d+\.\d+-")

# Extracts the prowjob name from a Prow "view" URL: the path segment that
# follows "/logs/".
_PROW_LOGS_RE = re.compile(r"/logs/([^/]+)")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "List gcsweb artifact URLs for /payload runs on a PR, optionally "
            "filtered to the current release blocking jobs."
        ),
    )
    parser.add_argument(
        "--org", default="openshift",
        help="GitHub org that owns the PR (default: openshift).",
    )
    parser.add_argument(
        "--repo", required=True,
        help="GitHub repo that owns the PR (required).",
    )
    parser.add_argument(
        "--pr", required=True, type=int,
        help="Pull request number (required).",
    )
    parser.add_argument(
        "--start", required=True, metavar="YYYY-MM-DD",
        help="Only include runs started on or after this UTC date (required).",
    )
    parser.add_argument(
        "--end", metavar="YYYY-MM-DD", default=None,
        help="Only include runs started on or before this UTC date "
             "(inclusive of the whole day). Defaults to now.",
    )
    parser.add_argument(
        "--streams", nargs="+", default=[], metavar="STREAM",
        help="Release stream name(s) whose blocking jobs define the filter, "
             "e.g. 5.0.0-0.nightly 5.0.0-0.ci. Required unless --all-jobs.",
    )
    parser.add_argument(
        "--all-jobs", action="store_true",
        help="Do not filter by blocking jobs; return every payload run.",
    )
    parser.add_argument(
        "--show-jobs", action="store_true",
        help="Print the unique matched job names to stderr at the end.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print filter diagnostics to stderr.",
    )
    parser.add_argument(
        "-o", "--output", default=None, metavar="FILE",
        help="Write the URL list to FILE (default: stdout).",
    )
    args = parser.parse_args(argv)
    if not args.all_jobs and not args.streams:
        parser.error("--streams is required unless --all-jobs is given.")
    return args


def parse_date(value, end_of_day=False):
    """Parse a YYYY-MM-DD string into an aware UTC datetime."""
    try:
        dt = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise SystemExit(
            f"ERROR: invalid date {value!r}; expected format YYYY-MM-DD."
        )
    dt = dt.replace(tzinfo=timezone.utc)
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt


# ---------------------------------------------------------------------------
# Release controller: derive blocking-job "test suffixes"
# ---------------------------------------------------------------------------

def prowjob_name_from_url(url):
    """Return the prowjob name embedded in a Prow view URL, or ''."""
    if not url:
        return ""
    match = _PROW_LOGS_RE.search(url)
    return match.group(1) if match else ""


def test_suffix(job_name):
    """Return the test-specific suffix of a periodic payload job name.

    The suffix is everything after the last "<stream>-<version>-" prefix
    (for example "nightly-4.20-"). If no such prefix is present, the whole
    job name is returned so it can still be used as a substring match.
    """
    matches = list(_STREAM_PREFIX_RE.finditer(job_name))
    if matches:
        return job_name[matches[-1].end():]
    return job_name


def fetch_blocking_suffixes(streams, verbose=False):
    """Fetch the blocking-job suffix patterns for the given release streams."""
    suffixes = set()
    for stream in streams:
        url = f"{RC_API_BASE}/releasestream/{stream}/latest"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            print(
                f"WARNING: could not fetch blocking jobs for stream "
                f"{stream!r}: {exc}",
                file=sys.stderr,
            )
            continue

        blocking = (data.get("results") or {}).get("blockingJobs") or {}
        if verbose:
            print(
                f"[verbose] stream {stream}: {len(blocking)} blocking job(s) "
                f"(latest tag {data.get('name', '?')})",
                file=sys.stderr,
            )
        for rc_key, info in blocking.items():
            # Aggregated jobs don't follow the periodic naming scheme, so use
            # the full release-controller key as the match pattern.
            if rc_key.startswith("aggregated-"):
                suffixes.add(rc_key)
                continue
            job_name = prowjob_name_from_url((info or {}).get("url", ""))
            if not job_name:
                job_name = rc_key
            suffix = test_suffix(job_name)
            if suffix:
                suffixes.add(suffix)
    return suffixes


# ---------------------------------------------------------------------------
# BigQuery
# ---------------------------------------------------------------------------

def query_payload_runs(args, start_dt, end_dt):
    """Query the CI analytics table for payload runs on the given PR."""
    try:
        client = bigquery.Client()
    except Exception as exc:  # noqa: BLE001 - surface any ADC/setup error
        raise SystemExit(
            "ERROR: could not initialize the BigQuery client. Ensure "
            "Application Default Credentials are configured "
            "('gcloud auth application-default login'). "
            f"Underlying error: {exc}"
        )

    query = f"""
        SELECT
          prowjob_name,
          prowjob_build_id,
          prowjob_url,
          prowjob_start
        FROM `{BQ_TABLE}`
        WHERE prowjob_name LIKE '%payload%'
          AND prowjob_org = @org
          AND prowjob_repo = @repo
          AND prowjob_pull_number = @pr
          AND prowjob_start >= @start
    """
    params = [
        bigquery.ScalarQueryParameter("org", "STRING", args.org),
        bigquery.ScalarQueryParameter("repo", "STRING", args.repo),
        bigquery.ScalarQueryParameter("pr", "STRING", str(args.pr)),
        bigquery.ScalarQueryParameter("start", "TIMESTAMP", start_dt),
    ]
    if end_dt is not None:
        query += "          AND prowjob_start <= @end\n"
        params.append(
            bigquery.ScalarQueryParameter("end", "TIMESTAMP", end_dt)
        )
    query += "        ORDER BY prowjob_start\n"

    job_config = bigquery.QueryJobConfig(query_parameters=params)
    try:
        rows = client.query(query, job_config=job_config).result()
    except Exception as exc:  # noqa: BLE001 - surface any query error
        raise SystemExit(f"ERROR: BigQuery query failed: {exc}")

    return [
        {
            "prowjob_name": row["prowjob_name"],
            "prowjob_build_id": str(row["prowjob_build_id"]),
            "prowjob_url": row["prowjob_url"],
            "prowjob_start": row["prowjob_start"],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Filtering / output
# ---------------------------------------------------------------------------

def filter_by_suffixes(rows, suffixes):
    """Split rows into (matched, unmatched) by blocking-job suffix."""
    matched, unmatched = [], []
    for row in rows:
        name = row.get("prowjob_name") or ""
        if any(suffix in name for suffix in suffixes):
            matched.append(row)
        else:
            unmatched.append(row)
    return matched, unmatched


def gcsweb_url(row):
    """Build the gcsweb artifact base URL for a payload run row."""
    return (
        f"{GCSWEB_BASE}/{GCS_BUCKET}/logs/"
        f"{row['prowjob_name']}/{row['prowjob_build_id']}/"
    )


def main(argv=None):
    args = parse_args(argv)

    start_dt = parse_date(args.start)
    end_dt = parse_date(args.end, end_of_day=True) if args.end else None

    rows = query_payload_runs(args, start_dt, end_dt)
    if args.verbose:
        print(
            f"[verbose] BigQuery returned {len(rows)} payload run(s) for "
            f"{args.org}/{args.repo}#{args.pr}",
            file=sys.stderr,
        )

    if args.all_jobs:
        selected = rows
        if args.verbose:
            print(
                "[verbose] --all-jobs set: skipping blocking-job filter.",
                file=sys.stderr,
            )
    else:
        suffixes = fetch_blocking_suffixes(args.streams, verbose=args.verbose)
        if args.verbose:
            print(
                f"[verbose] extracted {len(suffixes)} blocking suffix(es):",
                file=sys.stderr,
            )
            for suffix in sorted(suffixes):
                print(f"[verbose]   {suffix}", file=sys.stderr)
        if not suffixes:
            print(
                "WARNING: no blocking suffixes were extracted, so nothing "
                "will match. Re-run with --all-jobs to skip filtering, or "
                "check the --streams values.",
                file=sys.stderr,
            )
        selected, unmatched = filter_by_suffixes(rows, suffixes)
        if args.verbose:
            print(
                f"[verbose] {len(selected)} row(s) matched a blocking suffix; "
                f"{len(unmatched)} did not:",
                file=sys.stderr,
            )
            for row in unmatched:
                print(
                    f"[verbose]   (no match) {row['prowjob_name']}",
                    file=sys.stderr,
                )

    urls = sorted({gcsweb_url(row) for row in selected})

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write("\n".join(urls))
            if urls:
                handle.write("\n")
        print(f"Wrote {len(urls)} URL(s) to {args.output}", file=sys.stderr)
    else:
        for url in urls:
            print(url)

    if args.show_jobs:
        names = sorted({row["prowjob_name"] for row in selected})
        print(f"\n# {len(names)} unique job name(s):", file=sys.stderr)
        for name in names:
            print(f"#   {name}", file=sys.stderr)


if __name__ == "__main__":
    main()
