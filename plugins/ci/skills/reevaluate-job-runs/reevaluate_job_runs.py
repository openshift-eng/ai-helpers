"""Submit and monitor an asynchronous Sippy symptom re-evaluation batch."""

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


URL = "https://sippy-auth.dptools.openshift.org/api/jobs/runs/reevaluate"
API_MAX_IDS = 10000
POLL_INTERVAL_SECONDS = 2.5
REQUEST_TIMEOUT_SECONDS = 30
MAX_CONSECUTIVE_POLL_ERRORS = 5
TERMINAL_STATUSES = frozenset(("complete", "failed", "cancelled"))
KNOWN_STATUSES = frozenset(("pending", "processing", "running")) | TERMINAL_STATUSES
STATUS_COUNTERS = (
    "requested",
    "enqueued",
    "deduped",
    "completed",
    "failed",
    "running",
    "pending",
)


class APIError(Exception):
    """A useful, sanitized API error suitable for display to the user."""

    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


class MalformedResponseError(APIError):
    """The API returned JSON that does not match its documented contract."""


def _url_origin(url):
    parsed = urllib.parse.urlsplit(url)
    default_port = 443 if parsed.scheme.lower() == "https" else 80
    return parsed.scheme.lower(), (parsed.hostname or "").lower(), parsed.port or default_port


class SameOriginAuthRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep Authorization on same-origin redirects and strip it otherwise."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and _url_origin(req.full_url) != _url_origin(
            redirected.full_url
        ):
            redirected.remove_header("Authorization")
        return redirected


_OPENER = urllib.request.build_opener(SameOriginAuthRedirectHandler())


def _open_url(req, timeout):
    return _OPENER.open(req, timeout=timeout)


def resolve_token(arg_token, env=None):
    """Return the Bearer token from --token or the SIPPY_TOKEN env var."""
    env = os.environ if env is None else env
    return arg_token or env.get("SIPPY_TOKEN") or None


def extract_build_id(value):
    value = value.strip().split("#", 1)[0].split("?", 1)[0].rstrip("/")
    candidate = value.rsplit("/", 1)[-1]
    if candidate.isdigit():
        return candidate
    raise ValueError(
        "cannot extract a numeric build ID from %r "
        "(pass a numeric Prow build ID or a Prow job URL ending in one)" % value
    )


def _response_status(response):
    status = getattr(response, "status", None)
    return status if status is not None else response.getcode()


def _read_error_body(error):
    try:
        return error.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _message_from_body(body):
    try:
        parsed = json.loads(body)
    except (TypeError, ValueError):
        return ""
    if isinstance(parsed, dict) and isinstance(parsed.get("message"), str):
        return parsed["message"]
    return ""


def _request_json(url, token, method, expected_status, payload=None):
    data = None
    headers = {"Authorization": "Bearer %s" % token, "Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with _open_url(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            status = _response_status(response)
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        body = _read_error_body(error)
        detail = _message_from_body(body)
        if error.code in (401, 403):
            raise APIError(
                "HTTP %d (token missing/expired; use the oc-auth skill)" % error.code
            )
        if error.code == 501:
            raise APIError("HTTP 501 (write endpoints disabled; use sippy-auth)")
        message = "HTTP %d: %s" % (error.code, detail or error.reason)
        raise APIError(message, retryable=error.code in (429, 502, 503, 504))
    except urllib.error.URLError as error:
        raise APIError("connection error: %s" % error.reason, retryable=True)
    except (socket.timeout, TimeoutError) as error:
        detail = str(error) or "request timed out"
        raise APIError("request timeout: %s" % detail, retryable=True)

    if status != expected_status:
        raise APIError("expected HTTP %d, got HTTP %d" % (expected_status, status))
    if body.lstrip().startswith("<"):
        if "log in" in body.lower() or "login" in body.lower():
            raise APIError(
                "got an SSO login page instead of JSON — token is missing/expired; "
                "use the oc-auth skill to refresh it"
            )
        raise MalformedResponseError("server returned an HTML response instead of JSON")
    try:
        parsed = json.loads(body)
    except ValueError:
        raise MalformedResponseError("server returned a non-JSON response body")
    if not isinstance(parsed, dict):
        raise MalformedResponseError("server returned JSON that is not an object")
    return parsed


def _documented_status_url(batch_id):
    return URL + "/" + urllib.parse.quote(batch_id, safe="")


def _status_url(submission, batch_id):
    """Use the HATEOAS URL only when it is the expected authenticated endpoint."""
    fallback = _documented_status_url(batch_id)
    links = submission.get("links")
    candidate = links.get("status") if isinstance(links, dict) else None
    if candidate is None:
        return fallback
    if not isinstance(candidate, str) or not candidate:
        raise MalformedResponseError("submission response has an invalid links.status")

    expected = urllib.parse.urlsplit(fallback)
    actual = urllib.parse.urlsplit(candidate)
    if (
        actual.scheme != expected.scheme
        or actual.netloc != expected.netloc
        or actual.path != expected.path
        or actual.query
        or actual.fragment
    ):
        raise MalformedResponseError(
            "submission response links.status does not match the documented endpoint"
        )
    return candidate


def submit_batch(ids, token, dry_run):
    """Submit all deduplicated IDs in one POST and return batch metadata."""
    payload = {"prow_job_build_ids": ids, "dry_run": dry_run}
    submission = _request_json(URL, token, "POST", 202, payload)

    batch_id = submission.get("batch_id")
    if not isinstance(batch_id, str) or not batch_id:
        raise MalformedResponseError("submission response is missing a string batch_id")
    requested = submission.get("requested")
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 0:
        raise MalformedResponseError("submission response has an invalid requested count")
    if requested != len(ids):
        raise MalformedResponseError(
            "submission response requested count %d does not match %d submitted IDs"
            % (requested, len(ids))
        )

    return submission, _status_url(submission, batch_id)


def _validate_status_response(response, batch_id):
    if response.get("batch_id") != batch_id:
        raise MalformedResponseError(
            "status response batch_id does not match the submitted batch"
        )
    status = response.get("status")
    if status not in KNOWN_STATUSES:
        raise MalformedResponseError("status response has unknown status %r" % status)
    for field in STATUS_COUNTERS:
        value = response.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise MalformedResponseError("status response has an invalid %s count" % field)
    items = response.get("items")
    if not isinstance(items, list):
        raise MalformedResponseError("status response has an invalid items list")
    for item in items:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("item_key"), str)
            or not isinstance(item.get("state"), str)
        ):
            raise MalformedResponseError("status response contains an invalid item")
    return response


def poll_batch(
    status_url,
    batch_id,
    token,
    poll_interval=POLL_INTERVAL_SECONDS,
    sleeper=None,
):
    """Poll until the batch reaches complete, failed, or cancelled."""
    sleeper = time.sleep if sleeper is None else sleeper
    consecutive_errors = 0
    while True:
        try:
            response = _request_json(status_url, token, "GET", 200)
            response = _validate_status_response(response, batch_id)
            consecutive_errors = 0
        except APIError as error:
            if not error.retryable:
                raise
            consecutive_errors += 1
            if consecutive_errors >= MAX_CONSECUTIVE_POLL_ERRORS:
                raise APIError(
                    "lost connection to batch status after %d attempts: %s"
                    % (MAX_CONSECUTIVE_POLL_ERRORS, error)
                )
            print(
                "Status poll failed (%s); retrying in %ss..." % (error, poll_interval),
                file=sys.stderr,
            )
            sleeper(poll_interval)
            continue

        print(
            "Batch %s: %s (%d completed, %d failed, %d running, %d pending)"
            % (
                batch_id,
                response["status"],
                response["completed"],
                response["failed"],
                response["running"],
                response["pending"],
            ),
            file=sys.stderr,
        )
        if response["status"] in TERMINAL_STATUSES:
            return response
        sleeper(poll_interval)


def _print_summary(response, dry_run):
    mode = "DRY RUN" if dry_run else "APPLIED"
    print(
        "Reevaluation (%s) — batch %s: %s"
        % (mode, response["batch_id"], response["status"])
    )
    print("=" * 60)
    print(
        "Requested: %d, completed: %d, failed: %d, running: %d, pending: %d"
        % (
            response["requested"],
            response["completed"],
            response["failed"],
            response["running"],
            response["pending"],
        )
    )
    print(
        "Enqueued: %d, deduplicated by server: %d"
        % (response["enqueued"], response["deduped"])
    )
    for item in response["items"]:
        print("Run %s: %s" % (item["item_key"], item["state"]))


def _print_failure_json(submission, ids, stage, message):
    failure = {"batch": 1, "ids": ids, "stage": stage, "error": message}
    if submission is not None:
        failure["batch_id"] = submission["batch_id"]
    print(
        json.dumps(
            {
                "submission": submission,
                "status": None,
                "failed_batches": [failure],
            },
            indent=2,
        )
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Reevaluate symptoms on Prow job runs"
    )
    parser.add_argument(
        "runs",
        nargs="+",
        help="Prow build IDs or Prow job URLs (up to %d; submitted as one batch)" % API_MAX_IDS,
    )
    parser.add_argument(
        "--token",
        help="Bearer token (or set SIPPY_TOKEN env var, preferred; use oc-auth skill)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report matches without writing anything",
    )
    parser.add_argument("--format", choices=("json", "summary"), default="json")
    args = parser.parse_args(argv)

    token = resolve_token(args.token)
    if not token:
        print(
            "Error: no token provided — pass --token or set the SIPPY_TOKEN "
            "environment variable (preferred; use the oc-auth skill to obtain one)",
            file=sys.stderr,
        )
        return 1

    try:
        ids = sorted(set(extract_build_id(run) for run in args.runs))
    except ValueError as error:
        print("Error: %s" % error, file=sys.stderr)
        return 1
    if len(ids) > API_MAX_IDS:
        print(
            "Error: at most %d unique job runs may be submitted (got %d)"
            % (API_MAX_IDS, len(ids)),
            file=sys.stderr,
        )
        return 1

    submission = None
    stage = "submission"
    try:
        submission, status_url = submit_batch(ids, token, args.dry_run)
        print(
            "Submitted batch %s for %d run(s); polling %s"
            % (submission["batch_id"], submission["requested"], status_url),
            file=sys.stderr,
        )
        stage = "polling"
        final_status = poll_batch(status_url, submission["batch_id"], token)
    except (APIError, KeyboardInterrupt) as error:
        message = (
            "interrupted while waiting for batch"
            if isinstance(error, KeyboardInterrupt)
            else str(error)
        )
        print("Error: %s" % message, file=sys.stderr)
        if args.format == "json":
            _print_failure_json(submission, ids, stage, message)
        return 1

    if args.format == "json":
        print(json.dumps({"submission": submission, "status": final_status}, indent=2))
    else:
        _print_summary(final_status, args.dry_run)

    return 1 if final_status["status"] != "complete" or final_status["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
