"""Tests for cohorts.py — proposing cohorts around a transition and checking user cohorts."""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cohorts  # noqa: E402
from disruption_common import payloads, sippy  # noqa: E402

SPLIT = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
JOB_A = "periodic-ci-openshift-release-main-nightly-5.0-e2e-aws-ovn-upgrade"
JOB_B = "periodic-ci-openshift-release-main-ci-5.0-e2e-aws-upgrade-ovn-single-node"
JOB_C = "periodic-ci-openshift-release-main-nightly-5.0-e2e-aws-ovn-upgrade-fips"


def _run(pid, job, hours, seconds, **extra):
    run = {"prow_id": str(pid), "job": job, "timestamp": sippy.rfc3339(SPLIT + timedelta(hours=hours)),
           "seconds": seconds, "url": "https://prow/%s/%s" % (job, pid), "fetch_failed": False,
           "liveness_unreliable": False}
    run.update(extra)
    return run


def _series():
    runs = []
    pid = 100
    for hours in range(-120, 0, 6):
        for job, secs in ((JOB_A, 1), (JOB_B, 0)):
            pid += 1
            runs.append(_run(pid, job, hours, secs))
    for hours in range(3, 120, 6):
        for job, secs in ((JOB_A, 9), (JOB_B, 6)):
            pid += 1
            runs.append(_run(pid, job, hours, secs))
    return runs


def test_around_picks_shared_jobs_nearest_the_split_and_balances_jobs():
    result = cohorts.build_around(_series(), SPLIT, per_side=4)
    assert len(result["before"]) == len(result["after"]) == 4
    for side in ("before", "after"):
        assert {r["job"] for r in result[side]} == {JOB_A, JOB_B}
    assert max(sippy.parse_timestamp(r["timestamp"]) for r in result["before"]) < SPLIT
    assert min(sippy.parse_timestamp(r["timestamp"]) for r in result["after"]) >= SPLIT
    # Nearest the split: the latest before runs and the earliest after runs.
    assert sippy.parse_timestamp(result["before"][-1]["timestamp"]) == SPLIT - timedelta(hours=6)
    assert sippy.parse_timestamp(result["after"][0]["timestamp"]) == SPLIT + timedelta(hours=3)
    assert result["cohort_stats"]["after"]["p50"] > result["cohort_stats"]["before"]["p50"]
    assert result["population"]["before"]["n"] == 2 * len(range(-120, 0, 6))


def test_around_takes_one_run_per_launch_batch():
    runs = _series()
    # Three more JOB_A runs launched in the same minute just before the split.
    runs += [_run(900 + i, JOB_A, -0.5, 2) for i in range(3)]
    result = cohorts.build_around(runs, SPLIT, per_side=4)
    batch = [r for r in result["before"] if r["prow_id"].startswith("90")]
    assert len(batch) == 1


def test_around_leaves_out_liveness_and_failed_runs_and_says_so():
    runs = _series()
    runs.append(_run(990, JOB_A, -1, 40, liveness_unreliable=True))
    runs.append(_run(991, JOB_A, 1, None, fetch_failed=True))
    result = cohorts.build_around(runs, SPLIT, per_side=4)
    ids = {r["prow_id"] for r in result["before"] + result["after"]}
    assert not ids & {"990", "991"}
    assert any("ci-cluster-network-liveness" in n for n in result["notes"])
    assert result["data_loss"] == {"before": 0, "after": 1}
    assert any(n.startswith("the Sippy disruption API failed for 0 before and 1 after") for n in result["notes"])
    assert not any(n.startswith("DEGRADED") for n in result["notes"])


def test_around_marks_degraded_only_for_api_failures():
    runs = _series() + [_run(980 + i, JOB_A, 1 + i, None) for i in range(5)]
    result = cohorts.build_around(runs, SPLIT, per_side=4)
    assert result["data_loss"] == {"before": 0, "after": 0}
    assert any(n.startswith("0 before and 5 after run(s) in the window have no disruption data")
               for n in result["notes"])
    assert not any(n.startswith("DEGRADED") for n in result["notes"])

    runs = _series() + [_run(980 + i, JOB_A, 1 + i, None, fetch_failed=True) for i in range(5)]
    result = cohorts.build_around(runs, SPLIT, per_side=4)
    assert any(n.startswith("DEGRADED: the Sippy disruption API failed for 0 before and 5 after")
               for n in result["notes"])


def test_around_notes_jobs_on_one_side_and_falls_back_without_shared_jobs():
    runs = _series() + [_run(995, JOB_C, 10, 30)]
    result = cohorts.build_around(runs, SPLIT, per_side=2)
    assert any("only after the split" in n and JOB_C in n for n in result["notes"])
    assert JOB_C not in {r["job"] for r in result["after"]}

    disjoint = [_run(1, JOB_A, -5, 1), _run(2, JOB_B, 5, 9)]
    result = cohorts.build_around(disjoint, SPLIT, per_side=1)
    assert any("No job ran on both sides" in n for n in result["notes"])


def test_around_without_runs_on_a_side_fails_with_the_window():
    before_only = [r for r in _series() if sippy.parse_timestamp(r["timestamp"]) < SPLIT]
    with pytest.raises(cohorts.CohortError, match="after side within 7 day"):
        cohorts.build_around(before_only, SPLIT)


def test_pick_transition_defaults_to_the_strongest_practical_increase():
    transitions = [{"at": "a", "direction": "increase", "practical": True, "z": 4.5},
                   {"at": "b", "direction": "decrease", "practical": True, "z": -9},
                   {"at": "c", "direction": "increase", "practical": True, "z": 6.1},
                   {"at": "d", "direction": "increase", "practical": False, "z": 12}]
    assert cohorts.pick_transition(transitions) == (2, transitions[2])
    assert cohorts.pick_transition(transitions, 1) == (1, transitions[1])
    with pytest.raises(cohorts.CohortError, match="out of range"):
        cohorts.pick_transition(transitions, 7)
    with pytest.raises(cohorts.CohortError, match="no practical increase"):
        cohorts.pick_transition([transitions[1]])
    with pytest.raises(cohorts.CohortError, match="--at"):
        cohorts.pick_transition([])


def test_around_reads_the_trend_state_and_records_cohorts(tmp_path, capsys):
    runs_file = tmp_path / "trend-runs.json"
    runs_file.write_text(json.dumps(_series()))
    state_file = tmp_path / "investigation.json"
    state_file.write_text(json.dumps({"trend": {"runs_file": str(runs_file), "transitions": [
        {"at": sippy.rfc3339(SPLIT), "direction": "increase", "practical": True, "z": 7}]}}))
    code = cohorts.main(["around", "--state-file", str(state_file), "--per-side", "3", "--no-payloads"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Cohorts around 2026-11-04T12:00:00Z" in out
    assert "For disruption-analyze-run: --runs" in out
    saved = json.loads(state_file.read_text())
    assert saved["trend"]["runs_file"] == str(runs_file)
    assert saved["cohorts"]["transition"] == 0
    assert len(saved["cohorts"]["handoff"]["prow_urls"]["after"]) == 3
    assert saved["cohorts"]["handoff"]["download_runs"].count(":") == 6


def test_around_finds_a_relative_runs_file_beside_the_state_file(tmp_path, capsys, monkeypatch):
    (tmp_path / "trend-runs.json").write_text(json.dumps(_series()))
    state_file = tmp_path / "investigation.json"
    state_file.write_text(json.dumps({"trend": {"runs_file": ".work/elsewhere/trend-runs.json", "transitions": [
        {"at": sippy.rfc3339(SPLIT), "direction": "increase", "practical": True, "z": 7}]}}))
    other = tmp_path / "cwd"
    other.mkdir()
    monkeypatch.chdir(other)
    assert cohorts.main(["around", "--state-file", str(state_file), "--per-side", "2", "--no-payloads"]) == 0
    capsys.readouterr()


def test_around_without_a_runs_file_explains_what_to_run(tmp_path, capsys):
    assert cohorts.main(["around", "--state-file", str(tmp_path / "none.json")]) == 1
    assert "run disruption-trend with --state-file first" in capsys.readouterr().err


def test_parse_prow_url_accepts_prow_and_gcsweb_and_rejects_pr_logs():
    view = "https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/%s/2084701838124257280" % JOB_A
    assert cohorts.parse_prow_url(view) == (JOB_A, "2084701838124257280")
    gcsweb = ("https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results-public/logs/"
              "%s/2084701838124257280/" % JOB_A)
    assert cohorts.parse_prow_url(gcsweb) == (JOB_A, "2084701838124257280")
    pr = ("https://prow.ci.openshift.org/view/gs/test-platform-results-public/pr-logs/pull/"
          "openshift_origin/30123/pull-ci-openshift-origin-main-e2e-aws/2084701838124257281")
    with pytest.raises(cohorts.CohortError, match="presubmit"):
        cohorts.parse_prow_url(pr)
    with pytest.raises(cohorts.CohortError, match="not a Prow job URL"):
        cohorts.parse_prow_url("https://grafana-loki.ci.openshift.org/d/abc")


def _prowjob(start, initial, target):
    return {"status": {"startTime": start},
            "metadata": {"annotations": {"release.openshift.io/from-tag": initial, "release.openshift.io/tag": target}}}


def test_validate_keeps_user_cohorts_and_reports_comparability():
    view = "https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/%s/%s"
    before = [view % (JOB_A, "1000001"), view % (JOB_A, "1000002")]
    after = [view % (JOB_B, "1000003"), view % (JOB_A, "1000004")]
    jobs = {"1000001": _prowjob("2026-11-01T00:00:00Z", "5.0.0-0.nightly-2026-10-30-000000",
                                "5.0.0-0.nightly-2026-11-01-000000"),
            "1000002": _prowjob("2026-11-06T00:00:00Z", "5.0.0-0.nightly-2026-10-30-000000",
                                "5.0.0-0.nightly-2026-11-02-000000"),
            "1000003": _prowjob("2026-11-05T00:00:00Z", "5.0.0-0.nightly-2026-11-03-000000",
                                "5.0.0-0.nightly-2026-11-02-000000")}

    def fetch(job, build_id):
        if build_id not in jobs:
            raise payloads.PayloadError("HTTP 404 for %s" % build_id)
        return jobs[build_id]

    def fetch_disruption(ids, cache_path=None):
        data = {"1000001": [{"backend_name": "kube-api-new-connections", "disruption_seconds": 4}],
                "1000002": [{"backend_name": "kube-api-new-connections", "disruption_seconds": 6},
                            {"backend_name": "ci-cluster-network-liveness-new-connections", "disruption_seconds": 3}],
                "1000003": [{"backend_name": "kube-api-new-connections", "disruption_seconds": 2}]}
        return {k: v for k, v in data.items() if k in ids}, ["1000004"]

    result = cohorts.build_validated(before, after, ["kube-api-new-connections"], fetch=fetch,
                                     fetch_disruption=fetch_disruption)
    assert result["source"] == "user"
    assert [r["prow_id"] for r in result["before"]] == ["1000001", "1000002"]
    assert [r["prow_id"] for r in result["after"]] == ["1000003", "1000004"]
    assert result["before"][1]["seconds"] == 6
    notes = " | ".join(result["notes"])
    assert "prowjob.json could not be read for 1 run(s) (1000004)" in notes
    assert "unknown, not zero" in notes
    assert "ci-cluster-network-liveness was disrupted in 1000002" in notes
    assert "Jobs only in the after cohort: %s" % JOB_B in notes
    assert "not separated in time" in notes
    assert "no newer than the newest before payload" in notes
    assert "may not show a regression" in notes


def test_validate_rejects_duplicates_and_empty_sides():
    url = "https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/%s/1000001" % JOB_A
    with pytest.raises(cohorts.CohortError, match="listed twice"):
        cohorts.build_validated([url], [url], ["kube-api-new-connections"], fetch=None, fetch_disruption=None)
    with pytest.raises(cohorts.CohortError, match="before cohort is empty"):
        cohorts.build_validated([], [url], ["kube-api-new-connections"])


def test_validate_needs_backends(tmp_path, capsys):
    url = "https://prow.ci.openshift.org/view/gs/test-platform-results-public/logs/%s/1000001" % JOB_A
    assert cohorts.main(["validate", "--before", url, "--after", url]) == 1
    assert "pass --backends" in capsys.readouterr().err


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
