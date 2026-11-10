"""Tests for disruption_series.py — transition detection, onset, caveats, and the lib bootstrap."""
import json
import os
import random
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import disruption_series as ds

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "..", "lib", "disruption_common")
NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
START = NOW - timedelta(days=30)
SERIES = {"release": "5.0", "selectors": ["kube-api-new-connections"], "variants": {"Platform": "aws"},
          "master_nodes_updated": None, "percentile": "P95", "compare_release": "4.22",
          "dashboard": "(manual query)"}


def _zero_heavy(rng, nonzero_rate, scale):
    return 0 if rng.random() >= nonzero_rate else 1 + int(rng.expovariate(1.0 / scale))


def make_runs(values, jobs=("job-a", "job-b", "job-c"), start=START):
    """One run per value, evenly spaced from `start` to NOW, round-robin across jobs."""
    step = (NOW - start) / max(len(values), 1)
    runs = []
    for i, value in enumerate(values):
        ts = start + step * i
        runs.append({"prow_id": str(1000 + i), "job": jobs[i % len(jobs)],
                     "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "seconds": value,
                     "backend": "kube-api-new-connections", "release_tag": "5.0.0-0.nightly-%03d" % i,
                     "liveness_unreliable": False, "url": "https://prow/%d" % i})
    return runs


def analyze(values, **kwargs):
    return ds.analyze(SERIES, make_runs(values, **kwargs), START, NOW, "day", False)


def test_flat_series_has_no_transition():
    rng = random.Random(1)
    trend = analyze([_zero_heavy(rng, 0.3, 4) for _ in range(600)])
    assert trend["transitions"] == []
    assert trend["shape"] == "none"
    assert trend["onset"]["status"] == "before_window"


def test_step_increase_is_found_near_the_change():
    rng = random.Random(2)
    values = [_zero_heavy(rng, 0.05, 2) for _ in range(400)] + [_zero_heavy(rng, 0.6, 8) for _ in range(200)]
    trend = analyze(values)
    assert trend["shape"] == "step"
    t = trend["transitions"][0]
    assert t["direction"] == "increase" and t["strength"] == "strong" and t["practical"]
    assert abs(int(t["first_run_after"]["prow_id"]) - 1400) <= 10
    assert t["payload_before"] and t["payload_after"]
    assert t["per_job"]["jobs_increased"] == 3
    assert trend["onset"]["status"] == "in_window"


def test_step_decrease_is_reported_as_decrease():
    rng = random.Random(3)
    values = [_zero_heavy(rng, 0.8, 6) for _ in range(300)] + [_zero_heavy(rng, 0.02, 2) for _ in range(300)]
    t = analyze(values)["transitions"][0]
    assert t["direction"] == "decrease"


def test_multiple_transitions():
    rng = random.Random(4)
    values = ([_zero_heavy(rng, 0.02, 2) for _ in range(250)] + [_zero_heavy(rng, 0.5, 6) for _ in range(250)]
              + [_zero_heavy(rng, 0.95, 25) for _ in range(250)])
    trend = analyze(values)
    assert trend["shape"] == "multiple"
    assert [t["direction"] for t in trend["transitions"] if t["practical"]] == ["increase", "increase"]


def test_gradual_drift_is_not_called_a_clean_step():
    rng = random.Random(5)
    values = [_zero_heavy(rng, 0.05 + 0.7 * i / 800, 3 + 6 * i / 800) for i in range(800)]
    trend = analyze(values)
    assert trend["trend_rho"] > 0.3
    assert trend["shape"] in ("gradual", "multiple")


def test_onset_before_window_and_sporadic_and_none():
    rng = random.Random(6)
    assert analyze([_zero_heavy(rng, 0.7, 5) for _ in range(300)])["onset"]["status"] == "before_window"
    sporadic = [0] * 300
    for i in (40, 150, 260):
        sporadic[i] = 5
    assert analyze(sporadic)["onset"]["status"] == "sporadic"
    assert analyze([0] * 100)["onset"]["status"] == "none"


def test_job_mix_shift_is_flagged():
    values = [0] * 300 + [10] * 300
    runs = make_runs(values)
    for run in runs[300:]:
        run["job"] = "job-new"
    trend = ds.analyze(SERIES, runs, START, NOW, "day", False)
    t = trend["transitions"][0]
    assert t["job_mix_shift"] == 1.0
    assert t["per_job"]["jobs_compared"] == 0
    assert any("job mix changed" in c for c in trend["caveats"])


def test_caveats_for_missing_data_liveness_and_late_start():
    runs = make_runs([0, 1] * 50, start=NOW - timedelta(days=10))
    runs[-1]["seconds"] = None
    runs[-1]["timestamp"] = (NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    runs[0]["seconds"] = None
    runs[1]["liveness_unreliable"] = True
    trend = ds.analyze(SERIES, runs, START, NOW, "day", True)
    text = " ".join(trend["caveats"])
    assert "stopped before the window start" in text
    assert "No runs before" in text and "90 days" in text
    assert "BigQuery lag" in text
    assert "1 older run(s) have no disruption data" in text
    assert "ci-cluster-network-liveness" in text
    assert trend["runs"] == {"scanned": 100, "used": 97, "no_data": 2, "liveness_unreliable": 1}


def test_build_runs_uses_exact_backends_and_flags_liveness():
    rows = [{"prow_id": "1", "job": "j", "timestamp": "2026-11-01T00:00:00Z", "url": "u1"},
            {"prow_id": "2", "job": "j", "timestamp": "2026-10-31T00:00:00Z", "url": "u2"},
            {"prow_id": "3", "job": "j", "timestamp": "2026-11-02T00:00:00Z", "url": "u3"}]
    data = {
        "1": [{"backend_name": "kube-api-http2-localhost-new-connections", "disruption_seconds": 50},
              {"backend_name": "kube-api-new-connections", "disruption_seconds": 3, "release_tag": "tag-1"}],
        "2": [{"backend_name": "kube-api-new-connections", "disruption_seconds": 0},
              {"backend_name": "ci-cluster-network-liveness-new-connections", "disruption_seconds": 4}],
    }
    runs = ds.build_runs(rows, data, ["kube-api-new-connections"])
    assert [r["prow_id"] for r in runs] == ["2", "1", "3"]
    assert runs[1]["seconds"] == 3 and runs[1]["release_tag"] == "tag-1"
    assert runs[0]["liveness_unreliable"] is True
    assert runs[2]["seconds"] is None


def test_buckets_and_choose_bucket():
    assert ds.choose_bucket(30) == "day"
    assert ds.choose_bucket(90) == "week"
    assert ds.choose_bucket(730) == "month"
    trend = analyze([0, 2, 4] * 40)
    assert len(trend["buckets"]) in (30, 31)
    assert all({"bucket", "n", "p95", "sparse", "top_job"} <= set(b) for b in trend["buckets"])


def _fake_rows(n):
    return [{"prow_id": str(i), "job": "job-%d" % (i % 3), "url": "https://prow/%d" % i,
             "timestamp": (NOW - timedelta(hours=1 + i)).strftime("%Y-%m-%dT%H:%M:%SZ")} for i in range(n)]


def _fake_disruption(ids, cache_path=None, progress=None):
    return {pid: [{"backend_name": "kube-api-new-connections", "disruption_seconds": 9 if int(pid) < 100 else 0,
                   "release_tag": "tag-%s" % pid, "master_nodes_updated": "Y"}] for pid in ids}


def test_main_writes_state_and_runs_file(tmp_path, capsys):
    state = tmp_path / "inv" / "investigation.json"
    state.parent.mkdir()
    state.write_text(json.dumps({"schema_version": 1, "request": {"workflow": "W2"}}))
    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(400), False)), \
            patch.object(ds.sippy, "fetch_disruption_data", side_effect=_fake_disruption):
        code = ds.main(["--release", "5.0", "--backend", "kube-api-new-connections", "--days", "30",
                        "--state-file", str(state), "--cache-dir", ""])
    assert code == 0
    saved = json.loads(state.read_text())
    assert saved["request"] == {"workflow": "W2"}
    assert saved["series"]["backends"] == ["kube-api-new-connections"]
    assert saved["trend"]["transitions"][0]["direction"] == "increase"
    runs = json.loads((tmp_path / "inv" / "trend-runs.json").read_text())
    assert len(runs) == 400
    out = capsys.readouterr().out
    assert "Transition increase" in out and "| Bucket |" in out


def test_main_json_and_master_nodes_filter(capsys):
    alert = "alertname: DisruptionRegressionP50\nbackend: kube-api-new-connections\nrelease: 5.0\n" \
            "master_nodes_updated: N\nplatform: aws\n"
    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(50), False)), \
            patch.object(ds.sippy, "fetch_disruption_data", side_effect=_fake_disruption):
        code = ds.main(["--alert-text", alert, "--format", "json", "--cache-dir", ""])
    assert code == 0
    assert "No runs matched master_nodes_updated=N" in capsys.readouterr().err


def test_main_reports_missing_release(capsys):
    assert ds.main(["--backend", "kube-api-new-connections"]) == 1
    assert "release is required" in capsys.readouterr().err


def _run_help(script_dir):
    return subprocess.run([sys.executable, os.path.join(script_dir, "disruption_series.py"), "--help"],
                          capture_output=True, text=True)


def test_bootstrap_finds_lib_in_whole_plugin_and_flat_layouts(tmp_path):
    plugin_skill = tmp_path / "plugin" / "skills" / "disruption-trend"
    plugin_skill.mkdir(parents=True)
    shutil.copy(os.path.join(HERE, "disruption_series.py"), plugin_skill)
    shutil.copytree(LIB, tmp_path / "plugin" / "lib" / "disruption_common")
    assert _run_help(str(plugin_skill)).returncode == 0

    flat_skill = tmp_path / "skills" / "disruption-trend"
    flat_skill.mkdir(parents=True)
    shutil.copy(os.path.join(HERE, "disruption_series.py"), flat_skill)
    shutil.copytree(LIB, tmp_path / "skills" / "disruption_common")
    assert _run_help(str(flat_skill)).returncode == 0


def test_bootstrap_explains_a_missing_lib(tmp_path):
    lonely = tmp_path / "skills" / "disruption-trend"
    lonely.mkdir(parents=True)
    shutil.copy(os.path.join(HERE, "disruption_series.py"), lonely)
    result = _run_help(str(lonely))
    assert result.returncode != 0
    assert "supporting_dirs: [lib/disruption_common]" in result.stderr


def test_main_caps_window_at_max_days(capsys):
    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(400), False)) as collect, \
            patch.object(ds.sippy, "fetch_disruption_data", side_effect=_fake_disruption):
        code = ds.main(["--release", "5.0", "--backend", "kube-api-new-connections", "--days", "730",
                        "--format", "json", "--cache-dir", ""])
    assert code == 0
    window_start = collect.call_args[0][2]
    assert abs((datetime.now(timezone.utc) - window_start) - timedelta(days=ds.MAX_DAYS)) < timedelta(minutes=5)
    captured = capsys.readouterr()
    assert "using the maximum of 90 days" in captured.err
    assert "maximum is 90 days" in json.loads(captured.out)["trend"]["caveats"][0]


def test_main_rejects_nonpositive_days(capsys):
    assert ds.main(["--release", "5.0", "--backend", "kube-api-new-connections", "--days", "0"]) == 1
    assert "--days must be positive" in capsys.readouterr().err
