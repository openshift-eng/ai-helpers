---
name: prow-job-prometheus
description: Use when you need in-cluster Prometheus metrics from a Prow CI job run — apiserver in-flight requests, etcd disk latency, node CPU/memory/disk, per-pod usage, restarts — by downloading the run's Prometheus snapshot, repairing it, and querying it locally with PromQL
---

# Prow Job Prometheus

Most OpenShift e2e prow jobs that use and reach the `gather-extra` step save the in-cluster Prometheus
TSDB. Loading it locally lets you run PromQL against the cluster as it was during the run.
This is the way to answer "what was the apiserver/etcd/node doing at the moment tests failed".

Use this skill when:
- Autodl or Sippy data points at a time window (high CPU, disruption, a burst of failures) and
  you need the underlying metrics.
- Debugging apiserver slowness, etcd latency, node resource exhaustion, or restarts in one run.
- Comparing the same metrics between a bad run and a good run.

These TSDB's can be quite large, so avoid bulk downloading when possible, this is for targeted
investigations.

## Prerequisites

- **podman**, to run Prometheus (and to build `walfix` if `go` isn't installed).
  On macOS the podman VM only mounts paths under `/Users`. The default cache
  `~/.cache/prow-prometheus` is fine, but `/tmp` fails with `statfs ... no such file or directory`.
- **Python 3.9+**.
- Roughly 2 GB of disk per replica (download plus extracted data).
- Artifacts come from the public `test-platform-results-public` bucket over anonymous HTTPS.
  Do not run `gcloud auth login` or change the user's gcloud account to reach them. The bucket
  named `test-platform-results` (no `-public`) is private.

## Where the snapshots are

```
<run>/artifacts/<step>/gather-extra/artifacts/metrics/
  prometheus.tar.gz            # replica prometheus-k8s-0 TSDB (prometheus.tar in older runs)
  prometheus-k8s-1.tar.gz      # replica prometheus-k8s-1 TSDB (prometheus-k8s-1.tar in older runs)
  prometheus-tsdb-status.json  # live head stats at gather time (series count, time range)
  prometheus-targets.json      # scrape targets and their health at gather time
  job_metrics.json             # a few precomputed queries
```

Both replicas scrape the same targets, so either works. The snapshot covers the whole run
(install through gather), roughly 2–3 hours.

## Step 1: Load the snapshot

```bash
SKILL_DIR="${CLAUDE_PLUGIN_ROOT}/skills/prow-job-prometheus"
python3 "$SKILL_DIR/load_snapshot.py" "<prow-job-url>"
```

The script:
1. Finds the step with a `gather-extra` snapshot (pass `--step` if several steps have one).
2. Downloads the replica 0 snapshot (`--replica 1` for the other replica) into `~/.cache/prow-prometheus/<build_id>/`.
3. Extracts it safely and **repairs the WAL** with `walfix` (see below).
4. Starts `quay.io/prometheus/prometheus` in podman on the first free port from 9090, waits until ready.
5. Prints the URL, the data time range, and how many series loaded compared with the live server.

If fewer than about 80% of the live series loaded, try the other replica. Even at ~98%, the
series lost to corruption can be an entire target, e.g. one etcd member. If a target you need
shows no data (check `count by (instance) (count_over_time(<metric>[4h]))`), load the other
replica on another port (`--replica 1 --port 9091`) and query it with `promql.py --url`.

**Why the WAL repair matters.** The snapshot is copied from a running Prometheus, so the WAL
almost always has a corrupt page. Prometheus's built-in repair handles that by **deleting
every WAL segment after the corruption** and only logging a warning. A naively loaded snapshot
can silently lose 90%+ of its series, e.g. two of three apiservers or etcd members appear to
have no data. `walfix` keeps every record whose checksum verifies and skips only the corrupt
fragments, typically recovering ~98% of series. Never load a raw snapshot without it.
If you see `Deleting all segments newer than corrupted segment` in `podman logs`, the WAL was
not repaired.

## Step 2: Find the time window

Metrics timestamps are UTC. Anchor the window on something concrete from the run:
- Test failure times from junit (`start_time`/`end_time`) or the run's intervals files.
- The autodl `node_cpu_usage_timeline` for the run, whose first sample is about the start of e2e.
- A scrape gap: `up == 0` or a missing sample means the target stopped responding.

## Step 3: Query

```bash
python3 "$SKILL_DIR/promql.py" '<promql>' --url http://localhost:9090 \
  --start 2026-10-13T14:30:00Z --end 2026-10-13T14:56:00Z --step 60 --label instance
python3 "$SKILL_DIR/promql.py" '<promql>' --time 2026-10-13T14:43:00Z   # instant query
```

It prints a time-by-series table (columns ordered by peak value, `--max-series` to widen).
The Prometheus UI at the printed URL also works for ad hoc exploration.

### PromQL cookbook

**Apiserver load and responsiveness**

| Question | Query |
|---|---|
| In-flight requests per apiserver | `sum by (instance) (apiserver_current_inflight_requests{job="apiserver"})` |
| Read vs mutating in flight | `sum by (request_kind) (apiserver_current_inflight_requests{job="apiserver"})` |
| APF executing by priority level | `sum by (priority_level) (apiserver_flowcontrol_current_executing_requests)` |
| APF queued requests | `sum by (priority_level) (apiserver_flowcontrol_current_inqueue_requests) > 0` |
| 429 rejections | `sum by (priority_level, reason) (rate(apiserver_flowcontrol_rejected_requests_total[2m])) > 0` |
| Request latency p99 by verb | `histogram_quantile(0.99, sum by (verb, le) (rate(apiserver_request_duration_seconds_bucket{verb!~"WATCH\|CONNECT"}[2m])))` |
| Apiserver unresponsive | `up{job="apiserver"}` and `scrape_duration_seconds{job="apiserver"}` (rising scrape time, then a gap) |
| Apiserver restarts | `process_start_time_seconds{job="apiserver"}` (a step change is a restart) |

**etcd** (healthy: WAL fsync p99 < 10 ms, backend commit p99 < 25 ms)

| Question | Query |
|---|---|
| WAL fsync p99 (ms) | `1000*histogram_quantile(0.99, sum by (instance, le) (rate(etcd_disk_wal_fsync_duration_seconds_bucket[1m])))` |
| Backend commit p99 (ms) | `1000*histogram_quantile(0.99, sum by (instance, le) (rate(etcd_disk_backend_commit_duration_seconds_bucket[1m])))` |
| Leader and leader changes | `etcd_server_is_leader`, `etcd_server_leader_changes_seen_total` |
| DB size | `etcd_mvcc_db_total_size_in_bytes` |

**Nodes** (node-exporter `instance` labels are node names, e.g. `ip-10-0-60-161...`)

| Question | Query |
|---|---|
| CPU cores by mode | `sum by (mode) (rate(node_cpu_seconds_total{instance=~"<node>.*",mode!="idle"}[1m]))` |
| CPU busy % | `100*(1-avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[1m])))` |
| Available memory | `node_memory_MemAvailable_bytes` |
| Page-cache thrashing | `rate(node_vmstat_pgmajfault[1m])` with `rate(node_disk_read_bytes_total[1m])` |
| Disk write latency (ms) | `1000*rate(node_disk_write_time_seconds_total[1m]) / rate(node_disk_writes_completed_total[1m])` |
| OOM kills | `node_vmstat_oom_kill` |

**Pods and containers** (`node` label on cAdvisor metrics)

| Question | Query |
|---|---|
| Top CPU containers on a node | `topk(8, sum by (namespace, container) (rate(container_cpu_usage_seconds_total{node="<node>",container!="",container!="POD"}[2m])))` |
| Top memory containers on a node | `topk(10, sum by (namespace, container) (container_memory_working_set_bytes{node="<node>",container!="",container!="POD"}))` |
| Pod cgroup total on a node | `container_memory_usage_bytes{node="<node>",id="/kubepods.slice"}` |
| Disk reads by pod on a node | `topk(8, sum by (namespace, pod) (rate(container_fs_reads_bytes_total{node="<node>",pod!=""}[1m])))` |
| Restarts in the window | `increase(kube_pod_container_status_restarts_total[30m]) > 0` |
| Why a container last died | `kube_pod_container_status_last_terminated_reason == 1` |

## Interpreting results

- **Rising in-flight with no APF queueing or 429s** means requests were admitted and then stuck,
  so look below the apiserver (etcd, or the node the apiserver/etcd runs on).
- **One etcd member with high fsync/commit latency** stalls requests that land on it, and the
  apiserver on the same master often hangs and gets restarted by its liveness probe
  (last terminated reason `Completed`). The other apiservers then see an in-flight spike.
- **High major page faults and disk reads spread across many pods, with no single reader**
  means memory pressure: page cache is being evicted and processes re-read their own pages.
  Check the node's pod cgroup total (`id="/kubepods.slice"`) against node memory. Masters that
  host more singleton operators carry more memory than their peers.
- **Node CPU near 100% while containers account for much less** usually means the rest is
  iowait or kernel reclaim. Check `node_cpu_seconds_total` by mode.
- **A scrape gap is itself evidence**: the target was too slow to answer within the scrape timeout.
  On a stalled node the kubelet's cAdvisor endpoint often goes quiet too, so per-pod `rate()`
  queries for that node can return nothing during the worst minutes. Use node-exporter metrics there.
- Compare against the other control-plane nodes in the same window, and ideally the same point
  in a good run, before concluding something is abnormal.

## Bundled files

- `load_snapshot.py`: find, download, extract, repair and serve a run's snapshot.
- `promql.py`: range/instant PromQL queries printed as tables.
- `walfix/main.go` (with `walfix/go.mod` and tests in `walfix/main_test.go`): the WAL repair tool,
  standard library only. `load_snapshot.py` runs it with `go run` when Go is installed,
  otherwise in a `golang` container. To run it by hand: `go run . <raw-wal-dir> <output-wal-dir>`.

## Cleanup

```bash
BUILD_ID=<build_id> REPLICA=<replica>   # substitute the real values
podman rm -f "prow-prom-${BUILD_ID}-${REPLICA}"
rm -rf -- "$HOME/.cache/prow-prometheus/${BUILD_ID}"
```

## Related skills

- `ci:prow-job-analysis` — overall failure debugging and the artifact layout (`references/artifacts.md`).
- `ci:analyze-disruption` — disruption intervals, audit logs and CPU metrics across runs.
- `bigquery-ci-data:autodl` — per-run summaries (CPU timeline, audit latency) to pick runs and windows.
