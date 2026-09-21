"""Re-run Sippy symptom detection on completed Prow job runs.

Requests are submitted as one asynchronous batch and polled until the batch
reaches a terminal state. Dry runs use the same flow without writing changes.
"""
import argparse
import http.client
import json
import math
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

URL = "https://sippy-auth.dptools.openshift.org/api/jobs/runs/reevaluate"
API_MAX_IDS = 10_000
REQUEST_TIMEOUT_SECONDS = 300
DEFAULT_POLL_INTERVAL_SECONDS = 5
NONTERMINAL_STATES = frozenset(("pending", "processing", "running"))
TERMINAL_STATES = frozenset(("complete", "failed", "cancelled"))
BATCH_STATES = NONTERMINAL_STATES | TERMINAL_STATES


class ClientError(Exception):
    """A controlled validation, network, or API error."""


def resolve_token(arg_token, env=None):
    """Return the Bearer token from --token or the SIPPY_TOKEN env var."""
    env = os.environ if env is None else env
    return arg_token or env.get("SIPPY_TOKEN") or None


def extract_build_id(value):
    """Normalize a numeric build ID or a Prow URL ending in one."""
    value = value.strip().split("#", 1)[0].split("?", 1)[0].rstrip("/")
    candidate = value.rsplit("/", 1)[-1]
    if candidate.isdigit():
        return candidate
    raise ValueError(
        "cannot extract a numeric build ID from %r "
        "(pass a numeric prow build ID or a Prow job URL ending in one)" % value
    )


def _origin(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        raise ValueError("URL must use HTTP(S) and include a hostname")
    default_port = 443 if parsed.scheme.lower() == "https" else 80
    return (parsed.scheme.lower(), (parsed.hostname or "").lower(), parsed.port or default_port)


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
        if exc.code == 501:
            raise ClientError("HTTP 501 (write endpoints disabled; use sippy-auth)%s" % suffix) from exc
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
    if body.lstrip().startswith("<"):
        if "log in" in body.lower():
            raise ClientError(
                "got an SSO login page instead of JSON — token is missing/expired; "
                "use the oc-auth skill to refresh it"
            )
        raise ClientError("server returned an HTML response instead of JSON")
    try:
        return json.loads(body)
    except ValueError as exc:
        raise ClientError("server returned a malformed JSON response") from exc


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
    return data


def submit(ids, token, dry_run):
    """Submit one deduplicated asynchronous request."""
    response = request_json(
        "POST",
        URL,
        token,
        202,
        {"prow_job_build_ids": ids, "dry_run": dry_run},
    )
    return _validate_submit_response(response)


def poll_batch(submission, token, poll_interval):
    """Poll the returned status link until the batch reaches a terminal state."""
    batch_id = submission["batch_id"]
    try:
        status_url = urllib.parse.urljoin(URL, submission["links"]["status"])
        status_origin = _origin(status_url)
    except ValueError as exc:
        raise ClientError("invalid links.status URL: %s" % exc) from exc
    if _origin(URL) != status_origin:
        raise ClientError("refusing to send the Bearer token to a cross-origin status URL")

    while True:
        status = _validate_batch_response(
            request_json("GET", status_url, token, 200), batch_id
        )
        if status["status"] in TERMINAL_STATES:
            return status
        time.sleep(poll_interval)


def print_batch_summary(response, dry_run=False):
    mode = "DRY RUN" if dry_run else "APPLIED"
    print("Reevaluation (%s) — batch %s: %s" %
          (mode, response["batch_id"], response["status"]))
    print("=" * 60)
    print("Requested: %(requested)s, enqueued: %(enqueued)s, deduped: %(deduped)s" % response)
    print("Completed: %(completed)s, failed: %(failed)s, running: %(running)s, pending: %(pending)s" % response)
    for item in response["items"]:
        print("Run %s: %s" % (item["item_key"], item["state"]))
        if "result" in item:
            print("  Result:")
            rendered = json.dumps(item["result"], indent=2, sort_keys=True)
            for line in rendered.splitlines():
                print("    %s" % line)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reevaluate symptoms on Prow job runs")
    parser.add_argument(
        "runs", nargs="+",
        help="Prow build IDs or Prow job URLs (maximum %d unique IDs)" % API_MAX_IDS,
    )
    parser.add_argument(
        "--token",
        help="Bearer token (or set SIPPY_TOKEN, preferred; use the oc-auth skill)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report matches without writing anything")
    parser.add_argument(
        "--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL_SECONDS,
        help="Seconds between status requests (default: %(default)s)",
    )
    parser.add_argument("--format", choices=["json", "summary"], default="json")
    args = parser.parse_args(argv)

    token = resolve_token(args.token)
    if not token:
        print(
            "Error: no token provided — pass --token or set SIPPY_TOKEN "
            "(preferred; use the oc-auth skill to obtain one)",
            file=sys.stderr,
        )
        return 1
    if not math.isfinite(args.poll_interval) or args.poll_interval <= 0:
        print("Error: --poll-interval must be finite and greater than zero", file=sys.stderr)
        return 1

    try:
        ids = sorted(set(extract_build_id(value) for value in args.runs))
    except ValueError as exc:
        print("Error: %s" % exc, file=sys.stderr)
        return 1
    if len(ids) > API_MAX_IDS:
        print("Error: maximum %d unique job run IDs per request" % API_MAX_IDS, file=sys.stderr)
        return 1

    try:
        response = submit(ids, token, args.dry_run)
        if response["requested"] != len(ids):
            raise ClientError(
                "submission response requested %d items, expected %d" %
                (response["requested"], len(ids))
            )
        response = poll_batch(response, token, args.poll_interval)
    except ClientError as exc:
        print("Error: %s" % exc, file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print_batch_summary(response, args.dry_run)

    if response["status"] in ("failed", "cancelled"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
