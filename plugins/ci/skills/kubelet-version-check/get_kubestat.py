#!/usr/bin/env python3
"""
Determine the kubelet version and job status for each /payload job run.

Usage:
    python3 kubelet_versions.py payload-runs.txt

Environment:
    GOOGLE_APPLICATION_CREDENTIALS  Path to a GCS service-account JSON key.
                                    If set, uses authenticated requests.
                                    If unset, uses unauthenticated access
                                    (works for the public test-platform-results bucket).

Input:  A text file with one gcsweb artifact URL per line.
Output: A table of job name, build ID, status, and kubelet version.
"""

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# GCS authentication
# ---------------------------------------------------------------------------

BUCKET = "test-platform-results"
_GCS_API = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o"
_token_cache: dict = {"token": None, "expires": 0}


def _get_access_token() -> str | None:
    """Return an OAuth2 access token from the service-account key, or None."""
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        return None

    now = time.time()
    if _token_cache["token"] and _token_cache["expires"] > now + 60:
        return _token_cache["token"]

    import base64

    with open(creds_path) as f:
        sa = json.load(f)

    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
    ).rstrip(b"=")
    iat = int(now)
    exp = iat + 3600
    payload = base64.urlsafe_b64encode(json.dumps({
        "iss": sa["client_email"],
        "scope": "https://www.googleapis.com/auth/devstorage.read_only",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": iat, "exp": exp,
    }).encode()).rstrip(b"=")

    signing_input = header + b"." + payload

    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        key = serialization.load_pem_private_key(
            sa["private_key"].encode(), password=None
        )
        sig = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    except ImportError:
        import subprocess, tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pem", delete=False
        ) as kf:
            kf.write(sa["private_key"])
            kf_path = kf.name
        try:
            proc = subprocess.run(
                ["openssl", "dgst", "-sha256", "-sign", kf_path],
                input=signing_input, capture_output=True, check=True,
            )
            sig = proc.stdout
        finally:
            os.unlink(kf_path)

    signature = base64.urlsafe_b64encode(sig).rstrip(b"=")
    jwt_token = (signing_input + b"." + signature).decode()

    req = Request(
        "https://oauth2.googleapis.com/token",
        data=(
            "grant_type=urn%3Aietf%3Aparams%3Aoauth%3A"
            f"grant-type%3Ajwt-bearer&assertion={jwt_token}"
        ).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(req, timeout=30) as resp:
        token_data = json.loads(resp.read())

    _token_cache["token"] = token_data["access_token"]
    _token_cache["expires"] = now + token_data.get("expires_in", 3600)
    return _token_cache["token"]


def _gcs_request(url: str) -> Request:
    """Build a Request, adding Authorization if credentials exist."""
    req = Request(url)
    token = _get_access_token()
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    return req


# ---------------------------------------------------------------------------
# GCS helpers
# ---------------------------------------------------------------------------


def _gcs_list_step_dirs(prefix: str) -> list[str]:
    """List immediate sub-directory prefixes under *prefix* using delimiter."""
    url = (
        f"{_GCS_API}?prefix={prefix}&delimiter=/&maxResults=100"
        "&fields=prefixes,nextPageToken"
    )
    dirs: list[str] = []
    while url:
        with urlopen(_gcs_request(url), timeout=60) as resp:
            data = json.loads(resp.read())
        dirs.extend(data.get("prefixes", []))
        token = data.get("nextPageToken")
        url = (
            f"{_GCS_API}?prefix={prefix}&delimiter=/&maxResults=100"
            f"&fields=prefixes,nextPageToken&pageToken={token}"
            if token else None
        )
    return dirs


def _gcs_read(object_name: str) -> str:
    """Read a text object from the bucket."""
    url = f"https://storage.googleapis.com/{BUCKET}/{object_name}"
    with urlopen(_gcs_request(url), timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _gcs_read_json(object_name: str) -> dict | None:
    """Read and parse a JSON object from the bucket, or None on failure."""
    try:
        text = _gcs_read(object_name)
        return json.loads(text)
    except (HTTPError, URLError, json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

_URL_RE = re.compile(
    r"https://gcsweb-ci[^/]+/gcs/(?P<bucket>[^/]+)/logs/"
    r"(?P<job>[^/]+)/(?P<build>\d+)/?"
)


def parse_url(line: str) -> tuple[str, str]:
    """Return (job_name, build_id) from a gcsweb URL."""
    m = _URL_RE.match(line.strip())
    if not m:
        raise ValueError(f"Cannot parse URL: {line.strip()}")
    return m.group("job"), m.group("build")


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"v1\.3[56]\.\S+")
_E2E_RE = re.compile(r"e2e", re.IGNORECASE)


def _get_status(job: str, build: str) -> str:
    """Return the job run result from finished.json, or 'unknown'."""
    obj = f"logs/{job}/{build}/finished.json"
    data = _gcs_read_json(obj)
    if data and "result" in data:
        return data["result"]
    return "unknown"


def _get_kubelet_version(job: str, build: str) -> str:
    """Return the kubelet version from the nodes file, or an error note."""
    artifacts_prefix = f"logs/{job}/{build}/artifacts/"

    try:
        step_dirs = _gcs_list_step_dirs(artifacts_prefix)
    except Exception as exc:
        return f"error listing: {exc}"

    # Find step directories whose name contains "e2e"
    e2e_steps = [d for d in step_dirs if _E2E_RE.search(d.split("/")[-2])]
    if not e2e_steps:
        return "no e2e step"

    for step_prefix in e2e_steps:
        nodes_path = f"{step_prefix}gather-extra/artifacts/oc_cmds/nodes"
        try:
            content = _gcs_read(nodes_path)
        except (HTTPError, URLError, OSError):
            continue

        lines = [l for l in content.splitlines() if l.strip()]
        if len(lines) < 2:
            continue

        fields = lines[1].split()
        if len(fields) < 5:
            continue

        version = fields[4]
        if _VERSION_RE.match(version):
            return version
        return f"unexpected: {version}"

    return "no nodes file"


def process_run(line: str) -> tuple[str, str, str, str]:
    """Return (job, build, status, kubelet_version) for one job run."""
    job, build = parse_url(line)
    status = _get_status(job, build)
    version = _get_kubelet_version(job, build)
    return job, build, status, version


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <payload-runs.txt>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        urls = [l.strip() for l in f if l.strip()]

    creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    print(
        f"Processing {len(urls)} job runs "
        f"({'authenticated' if creds else 'unauthenticated'}) ...",
        file=sys.stderr,
    )

    results: list[tuple[str, str, str, str]] = []

    with ThreadPoolExecutor(max_workers=24) as pool:
        futures = {pool.submit(process_run, line): line for line in urls}
        done = 0
        for fut in as_completed(futures):
            done += 1
            if done % 50 == 0 or done == len(urls):
                print(f"  {done}/{len(urls)} done", file=sys.stderr)
            results.append(fut.result())

    results.sort(key=lambda r: (r[0], r[1]))

    hdr = ("JOB", "BUILD_ID", "STATUS", "KUBELET_VERSION")
    widths = [
        max(len(hdr[i]), *(len(r[i]) for r in results)) for i in range(4)
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)

    print(fmt.format(*hdr))
    print(fmt.format(*("-" * w for w in widths)))
    for row in results:
        print(fmt.format(*row))


if __name__ == "__main__":
    main()
