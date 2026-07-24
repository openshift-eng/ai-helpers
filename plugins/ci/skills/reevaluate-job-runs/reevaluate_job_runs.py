"""Re-run Sippy symptom detection on completed Prow job runs (requires auth token).

Field lesson (2026-07): the API accepts up to 50 build IDs per request, but the
server evaluates roughly 3-4 seconds per run and the fronting gateway times out
around 60-90s, returning an HTML "504 Gateway Time-out" page. Batches of ~10
are reliable. Reevaluation is delete-then-insert and idempotent, so retrying a
batch (even one that may have partially completed server-side) is safe.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

URL = "https://sippy-auth.dptools.openshift.org/api/jobs/runs/reevaluate"
API_MAX_IDS = 50
DEFAULT_BATCH_SIZE = 10
RETRIES_PER_BATCH = 3
RETRY_DELAY_SECONDS = 5


def extract_build_id(value):
    value = value.strip().split("#", 1)[0].split("?", 1)[0].rstrip("/")
    candidate = value.rsplit("/", 1)[-1]
    if candidate.isdigit():
        return candidate
    raise ValueError("cannot extract a numeric build ID from %r "
                     "(pass a numeric prow build ID or a Prow job URL ending in one)" % value)


def chunk(items, size):
    return [items[i:i + size] for i in range(0, len(items), size)]


def send_batch(ids, token, dry_run):
    """POST one batch. Returns (results, error, auth_failed).

    Retries on transient gateway errors (502/503/504, HTML error pages, non-JSON
    bodies). auth_failed=True signals the caller to stop sending further batches.
    """
    payload = {"prow_job_build_ids": ids, "dry_run": dry_run}
    last_err = None
    for attempt in range(1, RETRIES_PER_BATCH + 1):
        req = urllib.request.Request(
            URL, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer %s" % token},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                body = resp.read().decode("utf-8")
            if body.lstrip().startswith("<"):
                # HTML instead of JSON: SSO login page (bad token) or gateway error page
                if "log in" in body.lower():
                    return None, ("got an SSO login page instead of JSON — token is "
                                  "missing/expired; use the oc-auth skill to refresh it"), True
                last_err = "gateway returned an HTML error page (likely 504 timeout)"
            else:
                try:
                    return json.loads(body).get("results", []), None, False
                except ValueError:
                    last_err = "server returned a non-JSON response body"
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8")
            except Exception:
                pass
            if e.code == 501:
                return None, "HTTP 501 (write endpoints disabled; use sippy-auth)", False
            if e.code in (401, 403):
                return None, "HTTP %d (token missing/expired; use the oc-auth skill)" % e.code, True
            if e.code not in (502, 503, 504):
                return None, "HTTP %d: %s\n%s" % (e.code, e.reason, detail), False
            last_err = "HTTP %d gateway error" % e.code
        except urllib.error.URLError as e:
            last_err = "connection error: %s" % e.reason
        if attempt < RETRIES_PER_BATCH:
            print("Batch attempt %d/%d failed (%s); retrying in %ds (reevaluation is "
                  "idempotent, retries are safe)..." % (attempt, RETRIES_PER_BATCH,
                                                        last_err, RETRY_DELAY_SECONDS),
                  file=sys.stderr)
            time.sleep(RETRY_DELAY_SECONDS)
    return None, "%s after %d attempts (try a smaller --batch-size)" % (last_err, RETRIES_PER_BATCH), False


def main():
    p = argparse.ArgumentParser(description="Reevaluate symptoms on Prow job runs")
    p.add_argument("runs", nargs="+", help="Prow build IDs or Prow job URLs (any count; batched automatically)")
    p.add_argument("--token", required=True, help="Bearer token (use oc-auth skill)")
    p.add_argument("--dry-run", action="store_true", help="Report matches without writing anything")
    p.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                   help="Runs per API request (default %d; max %d, but large batches "
                        "risk 504 gateway timeouts)" % (DEFAULT_BATCH_SIZE, API_MAX_IDS))
    p.add_argument("--format", choices=["json", "summary"], default="json")
    args = p.parse_args()

    if not 1 <= args.batch_size <= API_MAX_IDS:
        print("Error: --batch-size must be between 1 and %d" % API_MAX_IDS, file=sys.stderr)
        return 1
    try:
        ids = [extract_build_id(r) for r in args.runs]
    except ValueError as e:
        print("Error: %s" % e, file=sys.stderr)
        return 1
    ids = sorted(set(ids))

    all_results = []
    failed_batches = []
    batches = chunk(ids, args.batch_size)
    for i, batch in enumerate(batches, 1):
        if len(batches) > 1:
            print("Batch %d/%d (%d runs)..." % (i, len(batches), len(batch)), file=sys.stderr)
        results, err, auth_failed = send_batch(batch, args.token, args.dry_run)
        if err:
            print("Error: batch %d failed: %s" % (i, err), file=sys.stderr)
            failed_batches.append({"batch": i, "ids": batch, "error": err})
            if auth_failed:
                auth_err = "not attempted: %s" % err
                for j, remaining in enumerate(batches[i:], i + 1):
                    failed_batches.append({"batch": j, "ids": remaining, "error": auth_err})
                print("Error: authentication failed; skipping remaining batches. "
                      "Refresh the token via the oc-auth skill and rerun.", file=sys.stderr)
                break
        else:
            all_results.extend(results)

    if args.format == "json":
        print(json.dumps({"results": all_results, "failed_batches": failed_batches}, indent=2))
    else:
        mode = "DRY RUN" if args.dry_run else "APPLIED"
        print("Reevaluation (%s) — %d runs processed, %d batches failed" %
              (mode, len(all_results), len(failed_batches)))
        print("=" * 60)
        for r in all_results:
            print("Run %s: %s" % (r.get("prow_job_build_id", "?"), r.get("status")))
            print("  Symptoms evaluated: %s, matched: %s" %
                  (r.get("symptoms_evaluated"), r.get("symptoms_matched")))
            labels = r.get("labels_applied") or []
            print("  Labels applied: %s" % (", ".join(map(str, labels)) if labels else "none"))
        for fb in failed_batches:
            print("FAILED batch %d (%d runs): %s" % (fb["batch"], len(fb["ids"]), fb["error"]))
    return 1 if failed_batches else 0


if __name__ == "__main__":
    sys.exit(main())
