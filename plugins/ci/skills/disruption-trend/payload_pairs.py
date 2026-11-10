"""Initial and target release payloads per run, read from each run's prowjob.json.

Sippy's run and disruption APIs carry no initial payload, and the disruption
API's release_tag is often empty. The release controller writes both payloads
into the prowjob it starts: the env values RELEASE_IMAGE_INITIAL and
RELEASE_IMAGE_LATEST on the test container, and the release.openshift.io/
from-tag and /tag annotations. Jobs the release controller did not start (for
example component periodics) often have neither, so their payload is unknown.

prowjob.json is public in the test-platform-results-public bucket and is
fetched anonymously over HTTPS. Fetches are few, parallel with a small pool,
and cached, because the file never changes once the job has started.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

GCS_LOGS_URL = "https://storage.googleapis.com/test-platform-results-public/logs"
MAX_WORKERS = 4
FETCH_TIMEOUT = 20
_PAYLOAD_TIME = re.compile(r"(\d{4}-\d{2}-\d{2}-\d{6})")
_PAYLOAD_MINOR = re.compile(r"^(\d+\.\d+)\.")


class PayloadError(RuntimeError):
    """prowjob.json could not be fetched or parsed."""


def prowjob_url(job, build_id):
    return "%s/%s/%s/prowjob.json" % (GCS_LOGS_URL, job, build_id)


def payload_from_pullspec(pullspec):
    """The release tag of a pullspec (registry/ns/release:TAG), or the pullspec when it is a digest.

    ci-stream payloads are mirrored as `openshift/ci:rc_payload__<name>`; the
    prefix before the last `__` is dropped so the name matches the release.
    """
    pullspec = (pullspec or "").strip()
    if not pullspec or "@" in pullspec:
        return pullspec
    last = pullspec.rsplit("/", 1)[-1]
    if ":" not in last:
        return pullspec
    return last.split(":", 1)[1].rsplit("__", 1)[-1]


def payloads_from_prowjob(prowjob):
    """{"initial": ..., "target": ...} from a prowjob dict. Empty strings when not recorded.

    The env values win over the annotations, because they are what the test
    container actually installed and upgraded to.
    """
    env = {}
    spec = prowjob.get("spec") if isinstance(prowjob, dict) else None
    pod_spec = (spec or {}).get("pod_spec") or {}
    for container in pod_spec.get("containers") or []:
        for item in (container or {}).get("env") or []:
            if isinstance(item, dict) and item.get("name") and item.get("value"):
                env.setdefault(item["name"], item["value"])
    annotations = ((prowjob or {}).get("metadata") or {}).get("annotations") or {}
    target = payload_from_pullspec(env.get("RELEASE_IMAGE_LATEST")) or annotations.get("release.openshift.io/tag", "")
    initial = (payload_from_pullspec(env.get("RELEASE_IMAGE_INITIAL"))
               or annotations.get("release.openshift.io/from-tag", ""))
    return {"initial": initial or "", "target": target or ""}


def fetch_prowjob(job, build_id, timeout=FETCH_TIMEOUT):
    """Download and parse one prowjob.json. Raises PayloadError."""
    url = prowjob_url(job, build_id)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise PayloadError("HTTP %d for %s" % (e.code, url)) from e
    except urllib.error.URLError as e:
        raise PayloadError("failed to connect for %s: %s" % (url, e.reason)) from e
    except (OSError, ValueError) as e:
        raise PayloadError("failed to read %s: %s" % (url, e or type(e).__name__)) from e


def _load_cache(path):
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        print("Warning: ignoring unreadable payload cache %s" % path, file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def fetch_payloads(runs, cache_path=None, fetch=fetch_prowjob, max_workers=MAX_WORKERS, write=None):
    """Payload pair per run. Returns (payloads, failed).

    `runs` are dicts with prow_id and job. `payloads` maps prow_id to
    {"initial", "target"} (possibly empty strings, meaning prowjob.json has
    no payload). `failed` lists prow IDs whose prowjob.json could not be
    fetched; those are not cached, so a rerun tries them again. `write` is
    the atomic JSON writer for the cache (state.write_json_atomic).
    """
    cache = _load_cache(cache_path)
    payloads, todo, seen = {}, [], set()
    for run in runs:
        pid = str(run.get("prow_id", ""))
        if not pid or pid in seen:
            continue
        seen.add(pid)
        cached = cache.get(pid)
        if isinstance(cached, dict):
            payloads[pid] = {"initial": cached.get("initial", ""), "target": cached.get("target", "")}
        elif run.get("job"):
            todo.append((pid, run["job"]))

    def one(item):
        pid, job = item
        try:
            return pid, payloads_from_prowjob(fetch(job, pid)), None
        except PayloadError as e:
            return pid, None, str(e)

    failed, errors = [], []
    if todo:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for pid, pair, error in pool.map(one, todo):
                if pair is None:
                    failed.append(pid)
                    errors.append(error)
                else:
                    payloads[pid] = pair
    if failed:
        print("Warning: could not fetch prowjob.json for %d of %d run(s); first error: %s"
              % (len(failed), len(todo), errors[0]), file=sys.stderr)
    fresh = {pid: payloads[pid] for pid, _job in todo if pid in payloads}
    if cache_path and write and fresh:
        cache.update(fresh)
        try:
            write(cache_path, cache)
        except OSError as e:
            print("Warning: could not write payload cache %s: %s" % (cache_path, e), file=sys.stderr)
    return payloads, failed


def payload_time(payload):
    """The build time in a payload name ("2026-11-09-143447"), or "" when there is none.

    Nightly and ci payload names sort by stream before time, so payloads are
    compared on this instead of the whole name.
    """
    match = _PAYLOAD_TIME.search(payload or "")
    return match.group(1) if match else ""


def payload_minor(payload):
    """The X.Y version of a payload name ("5.1" for 5.1.0-0.nightly-...), or ""."""
    match = _PAYLOAD_MINOR.match(payload or "")
    return match.group(1) if match else ""


def is_upgrade(pair):
    return bool(pair and pair.get("initial") and pair.get("target") and pair["initial"] != pair["target"])
