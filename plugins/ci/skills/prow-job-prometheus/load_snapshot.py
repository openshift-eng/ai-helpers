#!/usr/bin/env python3
"""Download a Prow job run's Prometheus snapshot, repair its WAL and serve it locally.

The gather-extra step saves each in-cluster Prometheus replica's TSDB as
artifacts/<step>/gather-extra/artifacts/metrics/prometheus.tar.gz (replica 0)
and prometheus-k8s-1.tar.gz (replica 1); older runs saved plain .tar files.
These are copied from a running server, so the WAL usually has a corrupt page.
Prometheus's own repair then
deletes every later WAL segment and most of the run's data disappears, so this
script rewrites the WAL with walfix before starting Prometheus.

Artifacts are read anonymously from the public test-platform-results-public
bucket over HTTPS. No gcloud login is needed.

Usage:
    python3 load_snapshot.py <prow-url> [--replica 0|1] [--step STEP] [--port PORT]
                             [--dest DIR] [--no-serve]

Exit status:
    0  snapshot loaded (and served unless --no-serve)
    1  error
"""
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request

PUBLIC_BUCKET = "test-platform-results-public"
PRIVATE_BUCKET = "test-platform-results"
LIST_API = "https://storage.googleapis.com/storage/v1/b/{bucket}/o"
OBJECT_URL = "https://storage.googleapis.com/{bucket}/{name}"
# Newer runs gzip the snapshots, older ones saved plain tarballs.
SNAPSHOT_FILES = {0: ("prometheus.tar.gz", "prometheus.tar"), 1: ("prometheus-k8s-1.tar.gz", "prometheus-k8s-1.tar")}
TSDB_STATUS_FILES = {0: "prometheus-tsdb-status.json", 1: "prometheus-k8s-1-tsdb-status.json"}
PROMETHEUS_IMAGE = "quay.io/prometheus/prometheus:latest"
GOLANG_IMAGE = "docker.io/library/golang:1.23"
WALFIX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "walfix")


def parse_run_path(url):
    """Return the bucket path of a job run (e.g. logs/<job>/<build_id>) from a Prow, gcsweb or gs:// URL."""
    url = url.strip().rstrip("/")
    for bucket in (PUBLIC_BUCKET, PRIVATE_BUCKET):
        m = re.search(r"(?:/|gs://)" + re.escape(bucket) + r"/((?:pr-)?logs/.+)$", url)
        if m:
            path = m.group(1)
            # Trim anything below the run directory (e.g. a link to an artifact).
            m2 = re.match(r"(.*?/\d{10,})(?:/.*)?$", path)
            return m2.group(1) if m2 else path
    raise ValueError(f"not a recognized Prow job run URL: {url}")


def build_id(run_path):
    return run_path.rstrip("/").split("/")[-1]


def list_objects(prefix, delimiter="/"):
    """List object prefixes and names under prefix in the public bucket (anonymous)."""
    prefixes, items, token = [], [], None
    while True:
        q = {"prefix": prefix, "delimiter": delimiter, "fields": "prefixes,items(name,size),nextPageToken"}
        if token:
            q["pageToken"] = token
        u = LIST_API.format(bucket=PUBLIC_BUCKET) + "?" + urllib.parse.urlencode(q)
        with urllib.request.urlopen(u, timeout=60) as resp:
            d = json.load(resp)
        prefixes += d.get("prefixes", [])
        items += d.get("items", [])
        token = d.get("nextPageToken")
        if not token:
            return prefixes, items


def find_metrics_dirs(run_path):
    """Return {step: (metrics_prefix, file names)} for every step that has gather-extra Prometheus snapshots."""
    steps, _ = list_objects(run_path + "/artifacts/")
    found = {}
    for step_prefix in steps:
        metrics = step_prefix + "gather-extra/artifacts/metrics/"
        _, items = list_objects(metrics)
        names = {i["name"][len(metrics):] for i in items}
        if names & set(SNAPSHOT_FILES[0] + SNAPSHOT_FILES[1]):
            found[step_prefix.rstrip("/").split("/")[-1]] = (metrics, names)
    return found


def snapshot_file(names, replica):
    """Pick the snapshot file name for a replica from the names in the metrics directory."""
    for candidate in SNAPSHOT_FILES[replica]:
        if candidate in names:
            return candidate
    raise ValueError(f"no snapshot for replica {replica}; metrics directory has: {sorted(n for n in names if 'tar' in n)}")


def choose_step(found, step):
    if step:
        if step not in found:
            raise ValueError(f"step {step!r} has no Prometheus snapshot; available: {sorted(found)}")
        return step
    if not found:
        raise ValueError("no gather-extra Prometheus snapshot found in this run")
    if len(found) > 1:
        raise ValueError(f"several steps have snapshots, pass --step: {sorted(found)}")
    return next(iter(found))


def download(name, dest):
    url = OBJECT_URL.format(bucket=PUBLIC_BUCKET, name=urllib.parse.quote(name))
    with urllib.request.urlopen(url, timeout=60) as resp:
        size = int(resp.headers.get("Content-Length", 0))
        if os.path.exists(dest) and size and os.path.getsize(dest) == size:
            print(f"already downloaded: {dest}")
            return
        print(f"downloading {url} ({size / 1e6:.0f} MB)")
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            shutil.copyfileobj(resp, f, 1 << 20)
    os.replace(tmp, dest)


def safe_extract(tar_path, dest):
    """Extract a tarball, refusing absolute paths, '..' and anything but files and directories."""
    os.makedirs(dest, exist_ok=True)
    root = os.path.realpath(dest)
    with tarfile.open(tar_path) as tf:
        members = []
        for m in tf.getmembers():
            target = os.path.realpath(os.path.join(root, m.name))
            if os.path.isabs(m.name) or not (target == root or target.startswith(root + os.sep)):
                raise ValueError(f"unsafe path in archive: {m.name}")
            if not (m.isfile() or m.isdir()):
                raise ValueError(f"unexpected member type in archive: {m.name}")
            m.mode = 0o755 if m.isdir() else 0o644
            members.append(m)
        tf.extractall(root, members=members)


def run_walfix(raw_wal, out_wal):
    """Rewrite raw_wal into out_wal, with local Go if available, otherwise a golang container."""
    if shutil.which("go"):
        cmd = ["go", "run", ".", raw_wal, out_wal]
        subprocess.run(cmd, cwd=WALFIX_DIR, check=True)
        return
    if not shutil.which("podman"):
        raise RuntimeError("walfix needs either go or podman")
    common = os.path.commonpath([raw_wal, out_wal])
    cmd = ["podman", "run", "--rm", "-v", f"{WALFIX_DIR}:/src:ro,Z", "-v", f"{common}:/data:Z",
           "-w", "/src", "-e", "GOFLAGS=-buildvcs=false", GOLANG_IMAGE, "go", "run", ".",
           "/data/" + os.path.relpath(raw_wal, common), "/data/" + os.path.relpath(out_wal, common)]
    subprocess.run(cmd, check=True)


def prepare_data(raw, data):
    """Build a servable TSDB dir from the raw extraction: copy blocks and head chunks, repair the WAL."""
    if os.path.exists(data):
        shutil.rmtree(data)
    os.makedirs(data)
    for entry in os.listdir(raw):
        if entry in ("wal", "lock", "queries.active"):
            continue
        src, dst = os.path.join(raw, entry), os.path.join(data, entry)
        (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)
    if os.path.isdir(os.path.join(raw, "wal")):
        run_walfix(os.path.join(raw, "wal"), os.path.join(data, "wal"))


def free_port(start=9090):
    for port in range(start, start + 100):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("no free port found")


def serve(data, name, port):
    subprocess.run(["podman", "rm", "-f", name], capture_output=True)
    # An empty config, so Prometheus doesn't scrape itself and mix today's samples into the run's data.
    subprocess.run(["podman", "run", "-d", "--name", name, "-p", f"{port}:9090", "--user", "root",
                    "-v", f"{data}:/prometheus:Z", PROMETHEUS_IMAGE,
                    "--storage.tsdb.path=/prometheus", "--storage.tsdb.retention.time=100y",
                    "--config.file=/dev/null"], check=True, capture_output=True)
    base = f"http://localhost:{port}"
    deadline = time.time() + 900
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base + "/-/ready", timeout=5) as resp:
                if resp.status == 200:
                    return base
        except OSError:
            pass
        time.sleep(5)
    raise RuntimeError(f"Prometheus did not become ready; check `podman logs {name}`")


def get_json(url):
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)["data"]


def data_range(base, hs):
    """Return (min, max) in ms covering the on-disk blocks, which long runs ship with, and the head."""
    spans = [(b["minTime"], b["maxTime"]) for b in get_json(base + "/api/v1/status/tsdb/blocks")["blocks"]]
    if hs["numSeries"]:
        spans.append((hs["minTime"], hs["maxTime"]))
    if not spans:
        raise RuntimeError("Prometheus loaded no data")
    return min(s for s, _ in spans), max(e for _, e in spans)


def live_series(metrics_prefix, replica):
    """Series count the live Prometheus reported at gather time, if that artifact exists."""
    name = metrics_prefix + TSDB_STATUS_FILES[replica]
    try:
        with urllib.request.urlopen(OBJECT_URL.format(bucket=PUBLIC_BUCKET, name=name), timeout=60) as resp:
            d = json.load(resp)
        return d.get("data", d)["headStats"]["numSeries"]
    except (OSError, KeyError, ValueError):
        return None


def fmt_ms(ms):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ms / 1000))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", help="Prow, gcsweb or gs:// URL of the job run")
    ap.add_argument("--replica", type=int, choices=[0, 1], default=0, help="Prometheus replica (default 0)")
    ap.add_argument("--step", help="step directory, needed when several steps have snapshots")
    ap.add_argument("--port", type=int, help="local port (default: first free from 9090)")
    ap.add_argument("--dest", default=os.path.expanduser("~/.cache/prow-prometheus"),
                    help="cache directory; on macOS it must be under /Users for podman (default ~/.cache/prow-prometheus)")
    ap.add_argument("--no-serve", action="store_true", help="download and repair only")
    args = ap.parse_args()
    # Keep our progress lines in order with walfix's output.
    sys.stdout.reconfigure(line_buffering=True)

    try:
        run_path = parse_run_path(args.url)
        if PRIVATE_BUCKET + "/" in args.url and PUBLIC_BUCKET not in args.url:
            print(f"note: reading from the public {PUBLIC_BUCKET} bucket")
        found = find_metrics_dirs(run_path)
        step = choose_step(found, args.step)
        metrics, names = found[step]
        snapshot = snapshot_file(names, args.replica)
        bid = build_id(run_path)
        work = os.path.join(os.path.abspath(args.dest), bid, f"{step}-replica{args.replica}")
        os.makedirs(work, exist_ok=True)
        tar_path = os.path.join(work, snapshot)
        download(metrics + snapshot, tar_path)
        raw, data = os.path.join(work, "raw"), os.path.join(work, "data")
        if not os.path.isdir(raw):
            print(f"extracting to {raw}")
            # Extract to a temp dir so an interrupted extraction is never reused as complete.
            partial = raw + ".partial"
            shutil.rmtree(partial, ignore_errors=True)
            safe_extract(tar_path, partial)
            os.replace(partial, raw)
        print("repairing WAL")
        prepare_data(raw, data)
        print(f"data ready: {data}")
        if args.no_serve:
            return 0
        name = f"prow-prom-{bid}-{args.replica}"
        base = serve(data, name, args.port or free_port())
        hs = get_json(base + "/api/v1/status/tsdb")["headStats"]
        lo, hi = data_range(base, hs)
        live = live_series(metrics, args.replica)
        print(f"\nPrometheus: {base}  (container {name}; stop with `podman rm -f {name}`)")
        print(f"data range: {fmt_ms(lo)} to {fmt_ms(hi)}")
        recovered = f"series loaded: {hs['numSeries']}"
        if live:
            recovered += f" of {live} in the live server ({100 * hs['numSeries'] / live:.0f}%)"
        print(recovered)
        if live and hs["numSeries"] < 0.8 * live:
            print("warning: much of the snapshot is missing; try the other replica (--replica)")
        return 0
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
