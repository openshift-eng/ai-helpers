"""Tests for compare_cohorts.py — the candidate x cohort matrix."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import compare_cohorts as cc  # noqa: E402


def _parsed(disruptions=0, episodes=0, etcd=0, ovs_ms=0, kas_rollouts=0, kas_inside=0, during_etcd=0,
            liveness="clean", target="5.0.0-0.nightly-2026-11-01-000000"):
    run_context = {}
    if etcd:
        run_context["EtcdLog"] = {"count": etcd, "per_node": {"master-0": etcd}}
    if ovs_ms:
        run_context["OVSVswitchdLog"] = {"count": 3, "max_poll_interval_ms": ovs_ms, "nodes_affected": 1}
    concurrent = {"EtcdLog": {"count": during_etcd, "events": []}} if during_etcd else {}
    rollouts = [{"operator": "kube-apiserver", "episode_indices": [0] if i < kas_inside else []}
                for i in range(kas_rollouts)]
    return {"summary": {"disruption_count": disruptions, "episode_count": episodes, "wave_count": 1 if episodes else 0,
                        "phase_breakdown": {"upgrade": disruptions} if disruptions else {},
                        "network_liveness_status": liveness, "episode_summary": "%d episodes" % episodes},
            "run_context": run_context, "concurrent_events": concurrent, "revision_rollouts": rollouts,
            "payloads": {"initial": "5.0.0-0.nightly-2026-10-30-000000", "target": target}}


def _cohorts():
    before = {"1": _parsed(etcd=5, kas_rollouts=1), "2": _parsed(etcd=4, kas_rollouts=1),
              "3": _parsed(disruptions=1, episodes=1, etcd=6, kas_rollouts=1, kas_inside=1)}
    after = {"4": _parsed(disruptions=6, episodes=2, etcd=5, kas_rollouts=2, kas_inside=2, ovs_ms=1500, during_etcd=2),
             "5": _parsed(disruptions=5, episodes=2, etcd=6, kas_rollouts=2, kas_inside=2, ovs_ms=1300),
             "6": _parsed(disruptions=4, episodes=2, etcd=4, kas_rollouts=2, kas_inside=1, liveness="degraded")}
    return {"before": before, "after": after}


def _row(rows, signal):
    return next(r for r in rows if r["signal"] == signal)


def test_matrix_labels_new_more_and_pre_existing_signals():
    rows, _ = cc.build_matrix(_cohorts())
    assert _row(rows, "EtcdLog (events)")["suggested"] == "pre-existing, similar"
    assert _row(rows, "EtcdLog (events)")["kind"] == "run-wide"
    assert _row(rows, "OVSVswitchdLog (max poll ms)")["suggested"] == "new"
    assert _row(rows, "kube-apiserver revision rollouts")["suggested"] == "more in after"
    assert _row(rows, "kube-apiserver rollouts with disruption inside")["after"]["runs"] == 3
    assert _row(rows, "disruptions")["suggested"] == "more in after"
    during = _row(rows, "EtcdLog during disruption (events)")
    assert during["suggested"] == "sporadic in after" and during["after"]["build_ids"] == ["4"]
    # Disruption rows sort first, run-wide stress last.
    assert rows[0]["kind"] == "disruption" and rows[-1]["kind"] == "run-wide"


def test_suggest_covers_less_and_before_only():
    assert cc.suggest({"runs": 3, "of": 3, "median": 10}, {"runs": 1, "of": 3, "median": 0}) == "less in after"
    assert cc.suggest({"runs": 2, "of": 3, "median": 4}, {"runs": 0, "of": 3, "median": 0}) == "before only"


def test_main_reads_cohorts_from_state_and_records_the_comparison(tmp_path, capsys):
    runs_dir = tmp_path / "runs"
    for side in _cohorts().values():
        for bid, parsed in side.items():
            (runs_dir / bid).mkdir(parents=True)
            (runs_dir / bid / "parsed.json").write_text(json.dumps(parsed))
    (runs_dir / "8").mkdir()
    (runs_dir / "8" / "parsed.json").write_text("")
    state_file = tmp_path / "investigation.json"
    state_file.write_text(json.dumps({"cohorts": {
        "before": [{"prow_id": "1"}, {"prow_id": "2"}, {"prow_id": "3"}],
        "after": [{"prow_id": "4"}, {"prow_id": "5"}, {"prow_id": "6"}, {"prow_id": "7"}, {"prow_id": "8"}]}}))
    assert cc.main(["--state-file", str(state_file), "--runs-dir", str(runs_dir)]) == 0
    out = capsys.readouterr().out
    assert "before: 3 run(s), after: 3 run(s)" in out
    assert "Run 7 (after) has no" in out
    assert "Run 8 (after) was skipped: cannot read parser output" in out
    assert "degraded or unreliable in 6" in out
    saved = json.loads(state_file.read_text())
    assert saved["cohorts"]["before"][0]["prow_id"] == "1"
    assert _row(saved["comparison"]["matrix"], "OVSVswitchdLog (max poll ms)")["suggested"] == "new"


def test_main_with_parser_files_and_bad_input(tmp_path, capsys):
    a = tmp_path / "111" / "parsed.json"
    b = tmp_path / "222.json"
    a.parent.mkdir()
    a.write_text(json.dumps(_parsed(etcd=1)))
    b.write_text(json.dumps(_parsed(disruptions=3, episodes=1, etcd=1)))
    assert cc.main(["--before", str(a), "--after", str(b), "--format", "json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["runs"] == {"before": ["111"], "after": ["222"]}

    assert cc.main(["--before", str(a)]) == 1
    assert "pass both --before and --after" in capsys.readouterr().err
    bad = tmp_path / "bad.json"
    bad.write_text("[]")
    assert cc.main(["--before", str(bad), "--after", str(b)]) == 1
    assert "is not parse_disruption.py --format json output" in capsys.readouterr().err
    assert cc.main(["--state-file", str(tmp_path / "none.json"), "--runs-dir", str(tmp_path)]) == 1
    assert "run disruption-find-runs first" in capsys.readouterr().err


def test_main_keeps_files_without_build_ids_apart_and_rejects_repeats(tmp_path, capsys):
    paths = []
    for name in ("good-a", "good-b"):
        path = tmp_path / name / "parsed.json"
        path.parent.mkdir()
        path.write_text(json.dumps(_parsed(etcd=1)))
        paths.append(str(path))
    after = tmp_path / "333.json"
    after.write_text(json.dumps(_parsed(disruptions=3, episodes=1, etcd=1)))
    assert cc.main(["--before", ",".join(paths), "--after", str(after), "--format", "json"]) == 0
    assert len(json.loads(capsys.readouterr().out)["runs"]["before"]) == 2

    assert cc.main(["--before", paths[0], "--after", "%s,%s" % (after, after)]) == 1
    assert "are the same run (333)" in capsys.readouterr().err


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
