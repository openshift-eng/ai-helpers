"""Tests for disruption_series.py — transition detection, onset, caveats, and the lib bootstrap."""
import io
import json
import os
import random
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

import disruption_series as ds

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "..", "scripts", "disruption_common")
NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
START = NOW - timedelta(days=30)
SERIES = {"release": "5.0", "selectors": ["kube-api-new-connections"], "variants": {"Platform": "aws"},
          "master_nodes_updated": None, "percentile": "P95", "compare_release": "4.22",
          "dashboard": "(manual query)"}


@pytest.fixture(autouse=True)
def no_gcs(monkeypatch):
    """Keep main() off the network; tests that need payloads patch fetch_payloads themselves."""
    monkeypatch.setattr(ds.payload_pairs, "fetch_payloads", lambda runs, **kwargs: ({}, []))


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


def test_a_few_disrupted_runs_at_the_end_are_not_a_step():
    assert ds.find_transitions([0] * 198 + [5, 5], 8) == []
    result = analyze([0] * 198 + [5, 5])
    assert result["transitions"] == []


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


def test_a_rise_after_a_quiet_stretch_is_a_recurrence_when_the_window_starts_disrupted():
    rng = random.Random(9)
    values = ([_zero_heavy(rng, 0.8, 6) for _ in range(300)] + [_zero_heavy(rng, 0.02, 2) for _ in range(300)]
              + [_zero_heavy(rng, 0.8, 6) for _ in range(300)])
    trend = analyze(values)
    onset = trend["onset"]
    assert onset["status"] == "before_window"
    assert abs(int(trend["transitions"][-1]["first_run_after"]["prow_id"]) - 1600) <= 10
    assert onset["recurrence"]["at"] == next(t["at"] for t in trend["transitions"] if t["direction"] == "increase")
    out = io.StringIO()
    ds.print_table(SERIES, trend, out)
    assert "Recurrence: disruption dropped to near zero and rose again" in out.getvalue()


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
    assert trend["runs"] == {"scanned": 100, "used": 97, "no_data": 2, "fetch_failed": 0, "liveness_unreliable": 1}
    assert trend["degraded"] is False


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


def test_choose_bucket_picks_day_week_or_month_by_window():
    assert ds.choose_bucket(45) == "day"
    assert ds.choose_bucket(46) == "week"
    assert ds.choose_bucket(270) == "week"
    assert ds.choose_bucket(271) == "month"


def test_bucket_key_week_starts_monday_and_month_rolls_over():
    utc = timezone.utc
    sunday = datetime(2026, 11, 8, 23, 59, tzinfo=utc)
    monday = datetime(2026, 11, 9, 0, 0, tzinfo=utc)
    assert ds.bucket_key(sunday, "week") == "2026-11-02"
    assert ds.bucket_key(monday, "week") == "2026-11-09"
    assert ds.bucket_key(datetime(2026, 10, 31, 23, 59, tzinfo=utc), "month") == "2026-10"
    assert ds.bucket_key(datetime(2026, 11, 1, 0, 0, tzinfo=utc), "month") == "2026-11"
    assert ds.bucket_key(datetime(2026, 1, 1, tzinfo=utc), "week") == "2025-12-29"


def test_build_buckets_values():
    def run(ts, seconds, job, tag):
        return {"timestamp": ts, "seconds": seconds, "job": job, "release_tag": tag}

    scored = [run("2026-11-02T01:00:00Z", 0, "job-a", "tag-1"), run("2026-11-02T02:00:00Z", 4, "job-a", "tag-2"),
              run("2026-11-02T03:00:00Z", 10, "job-b", ""), run("2026-11-03T00:00:00Z", 2, "job-a", "tag-3")]
    day1, day2 = ds.build_buckets(scored, "day")
    assert (day1["bucket"], day1["n"], day1["nonzero_rate"], day1["p50"], day1["max"]) == ("2026-11-02", 3, 0.667, 4, 10)
    assert (day1["jobs"], day1["top_job"], day1["top_job_share"]) == (2, "job-a", 0.67)
    assert (day1["first_payload"], day1["last_payload"], day1["sparse"]) == ("tag-1", "tag-2", True)
    assert (day2["bucket"], day2["n"], day2["p50"], day2["first_payload"]) == ("2026-11-03", 1, 2, "tag-3")
    (week,) = ds.build_buckets(scored, "week")
    assert (week["bucket"], week["n"], week["max"]) == ("2026-11-02", 4, 10)


def test_build_buckets_orders_mixed_stream_payloads_by_build_time():
    runs = [{"timestamp": "2026-11-10T0%d:00:00Z" % i, "seconds": 1, "job": "job-a", "release_tag": tag}
            for i, tag in enumerate(["5.0.0-0.ci-2026-11-10-010000", "5.0.0-0.nightly-2026-11-01-010000"])]
    (bucket,) = ds.build_buckets(runs, "day")
    assert bucket["first_payload"] == "5.0.0-0.nightly-2026-11-01-010000"
    assert bucket["last_payload"] == "5.0.0-0.ci-2026-11-10-010000"


def _fake_rows(n):
    return [{"prow_id": str(i), "job": "job-%d" % (i % 3), "url": "https://prow/%d" % i,
             "timestamp": (NOW - timedelta(hours=1 + i)).strftime("%Y-%m-%dT%H:%M:%SZ")} for i in range(n)]


def _fake_disruption(ids, cache_path=None, progress=None, max_wait=None):
    return {pid: [{"backend_name": "kube-api-new-connections", "disruption_seconds": 9 if int(pid) < 100 else 0,
                   "release_tag": "tag-%s" % pid, "master_nodes_updated": "Y"}] for pid in ids}, []


def test_main_writes_state_and_runs_file(tmp_path, capsys):
    state = tmp_path / "inv" / "investigation.json"
    state.parent.mkdir()
    state.write_text(json.dumps({"schema_version": 1, "request": {"workflow": "W2"}}))
    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(400), False)), \
            patch.object(ds.sippy, "fetch_disruption_data_with_failures", side_effect=_fake_disruption):
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

    # A control run of another platform leaves the investigated series alone.
    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(400), False)), \
            patch.object(ds.sippy, "fetch_disruption_data_with_failures", side_effect=_fake_disruption):
        code = ds.main(["--release", "5.0", "--backend", "kube-api-new-connections", "--days", "30",
                        "--platform", "gcp", "--control", "platform-gcp", "--state-file", str(state),
                        "--cache-dir", ""])
    assert code == 0
    after = json.loads(state.read_text())
    assert after["series"] == saved["series"] and after["trend"] == saved["trend"]
    control = after["controls"]["platform-gcp"]
    assert control["series"]["variants"] == {"Platform": "gcp"}
    assert control["runs_file"].endswith("control-platform-gcp-runs.json")
    assert (tmp_path / "inv" / "control-platform-gcp-runs.json").exists()
    compared = control["at_investigated_transitions"]
    assert compared[0]["at"] == saved["trend"]["transitions"][0]["at"]
    assert compared[0]["before"]["n"] > 0 and compared[0]["after"]["n"] > 0
    # The step is about 4 days before the end of the window, so the after side is short.
    assert compared[0]["before_days"] == 7 and compared[0]["after_days"] < 7 and not compared[0]["complete"]
    out = capsys.readouterr().out
    assert "Control platform-gcp around the investigated transitions:" in out
    assert "INCOMPLETE" in out


def test_control_at_transitions_records_coverage_and_exclusions():
    at = NOW - timedelta(days=10)
    runs = [{"timestamp": (at + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ"), "seconds": 0}
            for h in range(-150, 150, 6)]
    runs[0]["fetch_failed"] = True
    runs[-1]["liveness_unreliable"] = True
    transition = {"at": at.strftime("%Y-%m-%dT%H:%M:%SZ"), "direction": "increase"}
    (row,) = ds.control_at_transitions(runs, [transition], START, NOW)
    assert (row["before_days"], row["after_days"]) == (7, 7)
    assert (row["before_excluded"], row["after_excluded"]) == (1, 1)
    assert row["before"]["n"] == 24 and row["after"]["n"] == 24
    assert not row["complete"]
    (clean,) = ds.control_at_transitions([r for r in runs if not r.get("fetch_failed")
                                          and not r.get("liveness_unreliable")], [transition], START, NOW)
    assert clean["complete"]
    (short,) = ds.control_at_transitions(runs[1:-1], [transition], NOW - timedelta(days=12), NOW)
    assert short["before_days"] == 2 and not short["complete"]


@pytest.mark.parametrize("argv, message", [
    (["--control", "platform-gcp"], "--control needs --state-file"),
    (["--control", "Bad Name", "--state-file", "x.json"], "--control must be lowercase"),
])
def test_main_rejects_bad_control_options(argv, message, capsys):
    with pytest.raises(SystemExit):
        ds.main(["--release", "5.0", "--backend", "kube-api-new-connections"] + argv)
    assert message in capsys.readouterr().err


def _alert(master_nodes_updated):
    return ("alertname: DisruptionRegressionP50\nbackend: kube-api-new-connections\nrelease: 5.0\n"
            "master_nodes_updated: %s\nplatform: aws\n" % master_nodes_updated)


def test_main_stops_when_master_nodes_filter_matches_nothing(capsys):
    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(50), False)), \
            patch.object(ds.sippy, "fetch_disruption_data_with_failures", side_effect=_fake_disruption):
        code = ds.main(["--alert-text", _alert("N"), "--format", "json", "--cache-dir", ""])
    assert code == 0
    captured = capsys.readouterr()
    assert "No runs matched master_nodes_updated=N" in captured.err
    assert captured.out == ""


def test_main_json_output_describes_the_series_and_trend(capsys):
    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(400), False)), \
            patch.object(ds.sippy, "fetch_disruption_data_with_failures", side_effect=_fake_disruption):
        code = ds.main(["--alert-text", _alert("Y"), "--format", "json", "--cache-dir", ""])
    assert code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["series"]["release"] == "5.0"
    assert output["series"]["backends"] == ["kube-api-new-connections"]
    assert output["series"]["variants"] == {"Platform": "aws"}
    assert output["series"]["master_nodes_updated"] == "Y"
    assert output["trend"]["runs"] == {"scanned": 400, "used": 400, "no_data": 0, "fetch_failed": 0,
                                       "liveness_unreliable": 0}
    assert output["trend"]["runs_file"] is None
    (transition,) = output["trend"]["transitions"]
    assert transition["direction"] == "increase"
    assert transition["before"]["p50"] == 0 and transition["after"]["p50"] == 9


def test_main_reports_missing_release(capsys):
    assert ds.main(["--backend", "kube-api-new-connections"]) == 1
    assert "release is required" in capsys.readouterr().err


def _run_help(script_dir):
    return subprocess.run([sys.executable, os.path.join(script_dir, "disruption_series.py"), "--help"],
                          capture_output=True, text=True)


def test_bootstrap_finds_lib_in_whole_plugin_and_chai_layouts(tmp_path):
    plugin_skill = tmp_path / "plugin" / "skills" / "disruption-trend"
    plugin_skill.mkdir(parents=True)
    shutil.copy(os.path.join(HERE, "disruption_series.py"), plugin_skill)
    shutil.copytree(LIB, tmp_path / "plugin" / "scripts" / "disruption_common")
    assert _run_help(str(plugin_skill)).returncode == 0

    # Chai copies the plugin's scripts/ tree into each skill.
    chai_skill = tmp_path / "skills" / "disruption-trend"
    chai_skill.mkdir(parents=True)
    shutil.copy(os.path.join(HERE, "disruption_series.py"), chai_skill)
    shutil.copytree(LIB, chai_skill / "scripts" / "disruption_common")
    assert _run_help(str(chai_skill)).returncode == 0


def test_bootstrap_explains_a_missing_lib(tmp_path):
    lonely = tmp_path / "skills" / "disruption-trend"
    lonely.mkdir(parents=True)
    shutil.copy(os.path.join(HERE, "disruption_series.py"), lonely)
    result = _run_help(str(lonely))
    assert result.returncode != 0
    assert "Install the whole disruption plugin" in result.stderr


def test_main_caps_window_at_max_days(capsys):
    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(400), False)) as collect, \
            patch.object(ds.sippy, "fetch_disruption_data_with_failures", side_effect=_fake_disruption):
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


def test_onset_is_unknown_when_no_run_has_data():
    runs = make_runs([0] * 50)
    for run in runs:
        run["seconds"] = None
    trend = ds.analyze(SERIES, runs, START, NOW, "day", False)
    assert trend["onset"]["status"] == "unknown"
    out = io.StringIO()
    ds.print_table(SERIES, trend, out=out)
    assert "Onset: unknown" in out.getvalue()


def test_main_keeps_a_corrupt_state_file_and_still_prints(tmp_path, capsys):
    state = tmp_path / "investigation.json"
    state.write_text("{not json")
    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(50), False)), \
            patch.object(ds.sippy, "fetch_disruption_data_with_failures", side_effect=_fake_disruption):
        code = ds.main(["--release", "5.0", "--backend", "kube-api-new-connections",
                        "--state-file", str(state), "--cache-dir", ""])
    assert code == 1
    assert state.read_text() == "{not json"
    captured = capsys.readouterr()
    assert "it was not overwritten" in captured.err
    assert "| Bucket |" in captured.out
    assert json.loads((tmp_path / "trend-runs.json").read_text())
    assert not [p for p in os.listdir(tmp_path) if p.endswith(".tmp")]


def test_build_runs_orders_mixed_precision_timestamps_by_time():
    rows = [{"prow_id": "whole", "job": "j", "timestamp": "2026-11-01T00:00:05Z"},
            {"prow_id": "fraction", "job": "j", "timestamp": "2026-11-01T00:00:04.500Z"},
            {"prow_id": "later-fraction", "job": "j", "timestamp": "2026-11-01T00:00:05.250Z"}]
    runs = ds.build_runs(rows, {}, ["kube-api-new-connections"])
    assert [r["prow_id"] for r in runs] == ["fraction", "whole", "later-fraction"]


def _lose(runs, indexes):
    for i in indexes:
        runs[i]["seconds"] = None
        runs[i]["fetch_failed"] = True
    return runs


def test_lost_runs_get_their_own_caveat_and_are_not_counted_as_no_data():
    runs = _lose(make_runs([0, 1] * 300), range(10, 14))
    trend = ds.analyze(SERIES, runs, START, NOW, "day", False)
    text = " ".join(trend["caveats"])
    assert "4 run(s) from %s" % runs[10]["timestamp"][:16] in text
    assert "to %s" % runs[13]["timestamp"][:16] in text
    assert "Sippy disruption API failed" in text and "Rerun later" in text
    assert "have no disruption data (often" not in text
    assert trend["runs"]["fetch_failed"] == 4 and trend["runs"]["no_data"] == 0
    loss = trend["data_loss"]
    assert loss["runs"] == 4 and loss["first"] == runs[10]["timestamp"] and loss["last"] == runs[13]["timestamp"]
    assert sum(loss["buckets"].values()) == 4
    assert trend["degraded"] is False
    assert "The result is degraded" not in text


def test_more_than_a_few_percent_lost_marks_the_trend_degraded():
    runs = _lose(make_runs([0, 1] * 300), range(0, 60))
    trend = ds.analyze(SERIES, runs, START, NOW, "day", False)
    assert trend["degraded"] is True and trend["data_loss"]["fraction"] == 0.1
    assert any("The result is degraded" in c for c in trend["caveats"])
    out = io.StringIO()
    ds.print_table(SERIES, trend, out=out)
    assert "DEGRADED: 60 run(s) (10.0%) lost to Sippy disruption API failures" in out.getvalue()


def test_loss_concentrated_after_a_step_degrades_that_transition():
    values = [0] * 600 + [10] * 200
    runs = _lose(make_runs(values), range(780, 795))
    trend = ds.analyze(SERIES, runs, START, NOW, "day", False)
    (t,) = trend["transitions"]
    assert t["lost_runs"] == {"before": 0, "after": 15}
    assert t["degraded"] is True
    assert trend["degraded"] is True
    assert trend["data_loss"]["fraction"] < ds.DEGRADED_LOST_FRACTION
    out = io.StringIO()
    ds.print_table(SERIES, trend, out=out)
    assert "DEGRADED: 0 run(s) before and 15 after this step" in out.getvalue()


def test_build_runs_marks_api_failures():
    rows = [{"prow_id": "1", "job": "j", "timestamp": "2026-11-01T00:00:00Z"},
            {"prow_id": "2", "job": "j", "timestamp": "2026-11-02T00:00:00Z"}]
    runs = ds.build_runs(rows, {}, ["kube-api-new-connections"], failed=["2"])
    assert [(r["prow_id"], r["seconds"], r["fetch_failed"]) for r in runs] == [("1", None, False), ("2", None, True)]


def _step_with_jobs():
    """600 quiet runs over jobs a-c, then 120 runs where job-a and job-b step up and job-c stays flat.

    job-d runs only twice before and once after; job-new appears only after the step.
    """
    before_jobs = ["job-a", "job-b", "job-c"] * 200
    before_jobs[5], before_jobs[300] = "job-d", "job-d"
    after_jobs = ["job-a", "job-b", "job-c"] * 39 + ["job-d", "job-new", "job-a"]
    values = [2] * 600 + [60 if job in ("job-a", "job-b", "job-new") else 2 for job in after_jobs]
    runs = make_runs(values)
    for run, job in zip(runs, before_jobs + after_jobs):
        run["job"] = job
    return runs


def test_per_job_table_lists_every_job_with_a_run_after_the_step():
    trend = ds.analyze(SERIES, _step_with_jobs(), START, NOW, "day", False)
    t = trend["transitions"][0]
    rows = {row["job"]: row for row in t["per_job"]["jobs"]}
    assert set(rows) == {"job-a", "job-b", "job-c", "job-d", "job-new"}
    assert [row["job"] for row in t["per_job"]["jobs"]][:1] == ["job-a"]
    a = rows["job-a"]
    assert (a["n_after"], a["before_p50"], a["before_p95"], a["after_p50"], a["after_max"]) == (40, 2, 2, 60, 60)
    assert a["after_vs_before"] == "above_p95" and a["small_n"] is False
    assert rows["job-c"]["after_vs_before"] == "at_or_below_p50"
    assert rows["job-d"]["small_n"] is True and rows["job-d"]["n_before"] == 2 and rows["job-d"]["n_after"] == 1
    assert rows["job-new"]["n_before"] == 0 and rows["job-new"]["before_p50"] is None
    assert rows["job-new"]["after_vs_before"] is None
    out = io.StringIO()
    ds.print_table(SERIES, trend, out=out)
    text = out.getvalue()
    assert "| Job | n before | n after | Before P50 | Before P95 | After P50 | After max | Note |" in text
    assert "| job-d | 2 | 1 | 2 | 2 | 2 | 2 | small n |" in text
    assert "| job-new | 0 | 1 | — | — | 60 | 60 | small n, new after the step |" in text
    assert "| job-a | 199 | 40 | 2 | 2 | 60 | 60 | after P50 above before P95 |" in text


def test_handoff_pairs_use_same_job_nearest_runs_as_prow_urls():
    trend = ds.analyze(SERIES, _step_with_jobs(), START, NOW, "day", False)
    t = trend["transitions"][0]
    handoff = t["handoff"]
    assert len(handoff["pairs"]) == ds.PAIRS_PER_TRANSITION
    jobs = [pair["job"] for pair in handoff["pairs"]]
    assert jobs == ["job-a", "job-b", "job-c"]
    for pair in handoff["pairs"]:
        assert pair["before"]["job"] == pair["after"]["job"] == pair["job"]
        assert pair["before"]["timestamp"] < t["at"] <= pair["after"]["timestamp"]
    first = handoff["pairs"][0]
    assert first["after"]["representative"] and first["after"]["seconds"] == 60
    assert handoff["pairs"][2]["after"]["representative"] is False
    assert first["before"]["prow_id"] == "1597"
    assert handoff["prow_urls"][:2] == [first["before"]["url"], first["after"]["url"]]
    assert handoff["download_runs"].split(",")[0] == "job-a:1597"
    out = io.StringIO()
    ds.print_table(SERIES, trend, out=out)
    assert 'download_timelines.py --runs "job-a:1597,' in out.getvalue()


def _run(pid, job, minutes, seconds):
    ts = datetime(2026, 11, 9, 12, tzinfo=timezone.utc) + timedelta(minutes=minutes)
    return {"prow_id": pid, "job": job, "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "seconds": seconds,
            "release_tag": "", "url": "https://prow/%s" % pid}


def test_handoff_pairs_take_one_run_per_launch_batch_and_prefer_representative_runs():
    before = [_run("b-old", "up", -300, 40), _run("b1", "up", -30, 40), _run("b2", "up", -28, 40),
              _run("b-high", "up", -5, 90)]
    after = [_run("a-low", "up", 1, 10), _run("a1", "up", 2, 90), _run("a2", "up", 3, 95),
             _run("a3", "up", 4, 100), _run("a-late", "up", 200, 90)]
    handoff = ds.suggest_pairs(before, after, "increase", limit=3)
    picked = [(pair["before"]["prow_id"], pair["after"]["prow_id"]) for pair in handoff["pairs"]]
    # a-low and a1-a3 are one launch, as are b1 and b2. a-low is not above the job's before P95,
    # and b-high is above it, so neither is representative.
    assert picked == [("b2", "a1"), ("b-old", "a-late")]
    assert all(pair["before"]["representative"] and pair["after"]["representative"] for pair in handoff["pairs"])


def test_handoff_pairs_for_a_decrease_prefer_runs_that_show_the_drop():
    before = [_run("b-low", "j", -5, 0), _run("b-high", "j", -60, 50), _run("b-mid", "j", -200, 40)]
    after = [_run("a-high", "j", 1, 50), _run("a-low", "j", 30, 0)]
    handoff = ds.suggest_pairs(before, after, "decrease")
    pair = handoff["pairs"][0]
    assert (pair["before"]["prow_id"], pair["after"]["prow_id"]) == ("b-high", "a-low")
    assert pair["before"]["representative"] and pair["after"]["representative"]


def test_handoff_pairs_skip_a_launch_batch_that_straddles_the_step():
    before = [_run("b-batch", "up", -2, 40), _run("b-old", "up", -120, 40)]
    after = [_run("a-batch", "up", 1, 90)]
    handoff = ds.suggest_pairs(before, after, "increase")
    assert [(p["before"]["prow_id"], p["after"]["prow_id"]) for p in handoff["pairs"]] == [("b-old", "a-batch")]


def _pair(initial, target):
    return {"initial": "5.%s" % initial if initial else "", "target": "5.%s" % target if target else ""}


def test_payload_summary_detects_overlapping_targets_and_initial_payload_dependence():
    nightly = "1.0-0.nightly-2026-11-%s"
    before = [_run("b%d" % i, "up", -100 + i, 40) for i in range(4)]
    after = [_run("a%d" % i, "up", i + 1, 100) for i in range(4)] + [_run("a-fresh", "up", 10, 40),
                                                                      _run("a-plain", "plain", 11, 5)]
    payloads = {
        "b0": _pair(nightly % "08-120000", nightly % "09-143447"),
        "b1": _pair("0.0-0.nightly-2026-11-01-000000", nightly % "09-143447"),
        "b2": _pair(nightly % "08-120000", nightly % "08-180000"),
        "a0": _pair(nightly % "08-173648", nightly % "09-143447"),
        "a1": _pair(nightly % "08-173648", nightly % "09-143447"),
        "a2": _pair("0.0-0.nightly-2026-11-01-000000", nightly % "09-200000"),
        "a-fresh": _pair(nightly % "09-143447", nightly % "09-200000"),
        "a-plain": _pair(nightly % "09-200000", nightly % "09-200000"),
    }
    summary = ds.payload_summary(before, after, payloads, failed=["a3"])
    assert summary["fetch_failed"] == 1 and summary["no_payload"] == 0
    assert summary["newest_target_before"] == "5." + nightly % "09-143447"
    assert summary["oldest_target_after"] == "5." + nightly % "09-143447"
    assert summary["target_separates"] is False and summary["after_on_old_target"] == 2
    assert summary["after_on_shared_target"] == 2
    groups = summary["after_upgrades_by_initial"]
    assert groups["pre_step"] == {"n": 3, "p50": 100, "max": 100}
    assert groups["post_step"] == {"n": 1, "p50": 40, "max": 40}
    assert groups["not_upgrade"]["n"] == 1
    pairs = {(p["from"], p["to"]): p for p in summary["version_pairs"]}
    assert pairs[("5.0", "5.1")]["before"]["n"] == 1 and pairs[("5.0", "5.1")]["after"]["n"] == 1
    assert pairs[("5.1", "5.1")]["after"]["n"] == 3


def test_payload_summary_reports_clean_target_separation():
    before = [_run("b", "j", -10, 0)]
    after = [_run("a", "j", 10, 50)]
    payloads = {"b": _pair("", "1.0-0.nightly-2026-11-09-100000"), "a": _pair("", "1.0-0.ci-2026-11-09-120000")}
    summary = ds.payload_summary(before, after, payloads, failed=[])
    assert summary["target_separates"] is True and summary["after_on_old_target"] == 0
    assert summary["after_on_shared_target"] == 0


def test_apply_payloads_annotates_runs_pairs_and_caveats():
    runs = _step_with_jobs()
    trend = ds.analyze(SERIES, runs, START, NOW, "day", False)
    sample = ds.payload_sample(trend, runs)
    ids = [r["prow_id"] for r in sample]
    assert len(ids) == len(set(ids)) and len(ids) <= 2 * ds.PAYLOAD_SAMPLE_PER_SIDE + 2 * ds.PAIRS_PER_TRANSITION
    assert "1599" in ids and "1600" in ids and "1000" not in ids
    payloads = {pid: {"initial": "", "target": ""} for pid in ids[1:]}
    ds.apply_payloads(trend, runs, payloads, failed=ids[:1])
    t = trend["transitions"][0]
    assert t["payloads"]["fetch_failed"] == 1
    assert "target_payload" in t["handoff"]["pairs"][0]["after"]
    assert any("prowjob.json could not be fetched for 1 of 40" in c for c in trend["caveats"])
    assert any("cannot be placed by payload" in c for c in trend["caveats"])
    by_id = {run["prow_id"]: run for run in runs}
    assert by_id[ids[1]]["target_payload"] == "" and "target_payload" not in by_id["1000"]


def test_main_reports_lost_runs_fetches_payloads_and_writes_pairs_to_state(tmp_path, capsys):
    state = tmp_path / "investigation.json"
    lost_ids = {str(i) for i in range(300, 340)}

    def disruption(ids, cache_path=None, progress=None, max_wait=None):
        data, _ = _fake_disruption([pid for pid in ids if pid not in lost_ids])
        return data, sorted(lost_ids)

    calls = {}

    def fake_payloads(runs, cache_path=None, write=None):
        calls["runs"], calls["cache_path"] = runs, cache_path
        return {r["prow_id"]: {"initial": "5.0.0-0.nightly-2026-11-01-000000",
                               "target": "5.1.0-0.nightly-2026-11-09-143447"} for r in runs}, []

    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(400), False)), \
            patch.object(ds.sippy, "fetch_disruption_data_with_failures", side_effect=disruption) as fetch, \
            patch.object(ds.payload_pairs, "fetch_payloads", side_effect=fake_payloads):
        code = ds.main(["--release", "5.0", "--backend", "kube-api-new-connections", "--state-file", str(state),
                        "--cache-dir", str(tmp_path / "cache"), "--rate-limit-wait", "60"])
    assert code == 0
    assert fetch.call_args[1]["max_wait"] == 60
    assert calls["cache_path"] == str(tmp_path / "cache" / "prowjob-payloads.json")
    trend = json.loads(state.read_text())["trend"]
    assert trend["runs"]["fetch_failed"] == 40 and trend["degraded"] is True
    t = trend["transitions"][0]
    assert t["handoff"]["pairs"] and t["handoff"]["download_runs"]
    assert t["payloads"]["oldest_target_after"] == "5.1.0-0.nightly-2026-11-09-143447"
    runs = json.loads((tmp_path / "trend-runs.json").read_text())
    assert sum(1 for r in runs if r["fetch_failed"]) == 40
    assert any(r.get("target_payload") for r in runs)
    captured = capsys.readouterr()
    assert "reported as lost" in captured.err
    assert "DEGRADED:" in captured.out and "Suggested before/after pairs" in captured.out
    assert "Upgrades 5.0 → 5.1" in captured.out


def test_main_keeps_lost_runs_when_filtering_on_master_nodes_updated(capsys):
    def disruption(ids, cache_path=None, progress=None, max_wait=None):
        data, _ = _fake_disruption([pid for pid in ids if pid != "7"])
        return data, ["7"]

    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(50), False)), \
            patch.object(ds.sippy, "fetch_disruption_data_with_failures", side_effect=disruption):
        code = ds.main(["--alert-text", _alert("Y"), "--format", "json", "--cache-dir", "", "--no-payloads"])
    assert code == 0
    trend = json.loads(capsys.readouterr().out)["trend"]
    assert trend["runs"]["scanned"] == 50 and trend["runs"]["fetch_failed"] == 1
    assert any("upper bound" in caveat for caveat in trend["caveats"])


def test_main_warns_about_runs_whose_selected_rows_lack_master_nodes_updated(capsys):
    def disruption(ids, cache_path=None, progress=None, max_wait=None):
        data, failed = _fake_disruption(ids)
        del data["3"][0]["master_nodes_updated"]
        data["3"].append({"backend_name": "other-backend", "disruption_seconds": 0, "master_nodes_updated": "Y"})
        return data, failed

    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(50), False)), \
            patch.object(ds.sippy, "fetch_disruption_data_with_failures", side_effect=disruption):
        code = ds.main(["--alert-text", _alert("Y"), "--format", "json", "--cache-dir", "", "--no-payloads"])
    captured = capsys.readouterr()
    assert code == 0
    assert "1 run(s) have no master_nodes_updated value on the selected backends and were left out: 3" in captured.err
    trend = json.loads(captured.out)["trend"]
    assert trend["runs"]["scanned"] == 49
    assert any("could not be classified and were left out" in caveat for caveat in trend["caveats"])


def test_main_reports_the_loss_when_every_run_is_lost_under_master_nodes_updated(capsys):
    def disruption(ids, cache_path=None, progress=None, max_wait=None):
        return {}, list(ids)

    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(50), False)), \
            patch.object(ds.sippy, "fetch_disruption_data_with_failures", side_effect=disruption):
        code = ds.main(["--alert-text", _alert("Y"), "--format", "json", "--cache-dir", "", "--no-payloads"])
    captured = capsys.readouterr()
    assert code == 0
    assert "No runs matched" not in captured.err
    trend = json.loads(captured.out)["trend"]
    assert trend["runs"]["fetch_failed"] == 50 and trend["degraded"]


def test_main_flags_a_misspelled_backend_instead_of_reporting_no_disruption(capsys):
    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(400), False)), \
            patch.object(ds.sippy, "fetch_disruption_data_with_failures", side_effect=_fake_disruption):
        code = ds.main(["--release", "5.0", "--backend", "kube-api-new-conections", "--format", "json",
                        "--cache-dir", "", "--no-payloads"])
    captured = capsys.readouterr()
    assert code == 0
    assert "did you mean 'kube-api-new-connections'" in captured.err
    trend = json.loads(captured.out)["trend"]
    assert trend["runs"]["used"] == 0 and trend["runs"]["no_data"] == 400
    assert trend["onset"]["status"] == "unknown"
    assert "did you mean 'kube-api-new-connections'" in trend["caveats"][0]


def test_main_fails_when_master_nodes_updated_is_missing_from_the_response(capsys):
    def disruption(ids, cache_path=None, progress=None, max_wait=None):
        data, failed = _fake_disruption(ids)
        for entries in data.values():
            for entry in entries:
                del entry["master_nodes_updated"]
        return data, failed

    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(50), False)), \
            patch.object(ds.sippy, "fetch_disruption_data_with_failures", side_effect=disruption):
        code = ds.main(["--alert-text", _alert("Y"), "--format", "json", "--cache-dir", "", "--no-payloads"])
    captured = capsys.readouterr()
    assert code == 1
    assert "did not include that field" in captured.err
    assert captured.out == ""


def test_main_still_prints_when_the_runs_file_cannot_be_written(tmp_path, capsys):
    state = tmp_path / "investigation.json"
    state.write_text(json.dumps({"schema_version": 1}))
    blocked = tmp_path / "not-a-dir"
    blocked.write_text("")
    with patch.object(ds.sippy, "collect_runs", return_value=(_fake_rows(400), False)), \
            patch.object(ds.sippy, "fetch_disruption_data_with_failures", side_effect=_fake_disruption):
        code = ds.main(["--release", "5.0", "--backend", "kube-api-new-connections", "--days", "30",
                        "--runs-out", str(blocked / "runs.json"), "--state-file", str(state),
                        "--cache-dir", "", "--format", "json", "--no-payloads"])
    captured = capsys.readouterr()
    assert code == 1
    assert "cannot write runs file" in captured.err
    assert json.loads(captured.out)["trend"]["runs_file"] is None
    assert json.loads(state.read_text()) == {"schema_version": 1}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
