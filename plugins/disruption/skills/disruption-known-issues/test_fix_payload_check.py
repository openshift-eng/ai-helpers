"""Tests for fix_payload_check.py and known_issue_queries.py."""
import datetime
import json
import os
import sys

import pytest

from fix_payload_check import (
    check_fix,
    main,
    normalize_run,
    payload_time,
    percentile,
    scan_signature,
)
from known_issue_queries import main as queries_main

FIX = "5.1.0-0.nightly-2026-11-06-043907"
BACKEND = "openshift-api-http2-service-network-reused-connections"


def _trend_run(prow_id, tag, seconds, liveness=False):
    return {"prow_id": prow_id, "seconds": seconds, "release_tag": tag, "liveness_unreliable": liveness}


def _finder_run(prow_id, tag, seconds):
    return {"prow_id": prow_id, "disruption_seconds": seconds,
            "disruption_backends": [{"backend_name": BACKEND, "disruption_seconds": seconds,
                                     "release_tag": tag}]}


def test_payload_time_reads_the_tag_suffix():
    assert payload_time(FIX) == datetime.datetime(2026, 11, 6, 4, 39, 7)
    assert payload_time("5.1.0-0.ci-2026-10-28-120000") == datetime.datetime(2026, 10, 28, 12, 0, 0)
    assert payload_time("") is None
    assert payload_time("4.21.3") is None


def test_normalize_run_reads_both_input_formats():
    assert normalize_run(_trend_run("1", FIX, 0, liveness=True)) == ("1", 0, FIX, True)
    assert normalize_run(_finder_run(2, FIX, 7)) == ("2", 7, FIX, False)
    assert normalize_run({"prow_id": "3", "disruption_seconds": 4, "disruption_backends": []}) == ("3", 4, "", False)


def test_percentile_is_nearest_rank():
    assert percentile([], 95) == 0
    assert percentile([5], 95) == 5
    assert percentile(list(range(1, 21)), 95) == 19


def test_check_fix_splits_runs_at_the_fix_payload():
    runs = [
        _trend_run("a", "5.1.0-0.nightly-2026-11-04-010000", 15),
        _trend_run("b", "5.1.0-0.nightly-2026-11-04-020000", 0),
        _trend_run("c", "5.1.0-0.nightly-2026-11-06-010000", 15),  # same day, before the fix
        _trend_run("d", FIX, 0),
        _trend_run("e", "5.1.0-0.nightly-2026-11-08-000000", 2),
        _trend_run("f", "", 3),
        _trend_run("g", "5.1.0-0.nightly-2026-11-08-000000", None),
        _trend_run("h", "5.1.0-0.nightly-2026-11-08-000000", 30, liveness=True),
    ]

    result = check_fix(runs, FIX, signature_ids={"a", "c"})

    assert result["before_fix"] == {"runs": 3, "disrupted": 2, "p95_seconds": 15, "max_seconds": 15,
                                    "signature": 2}
    assert result["after_fix"] == {"runs": 2, "disrupted": 1, "p95_seconds": 2, "max_seconds": 2,
                                   "signature": 0}
    assert [(d["day"], d["fixed"], d["runs"], d["signature"]) for d in result["by_payload_day"]] == [
        ("2026-11-04", "no", 2, 1), ("2026-11-06", "split", 2, 1), ("2026-11-08", "yes", 1, 0)]
    assert result["excluded"] == {"no_disruption_data": 1, "no_payload_tag": 1, "liveness_unreliable": 1}
    assert any("Fixed=split" in c for c in result["caveats"])
    assert any("1 runs had no payload tag" in c for c in result["caveats"])


def test_check_fix_warns_when_one_side_is_empty_and_input_is_the_finder():
    result = check_fix([_finder_run(1, "5.1.0-0.nightly-2026-11-08-000000", 5)], FIX)

    caveats = " ".join(result["caveats"])
    assert "No runs tested a payload older than the fix" in caveats
    assert "lists only runs with disruption" in caveats
    assert "signature" not in result["before_fix"]


def test_check_fix_rejects_a_fix_payload_without_a_timestamp():
    with pytest.raises(ValueError, match="cannot read a timestamp"):
        check_fix([], "5.1.0")


def _write_timeline(root, build_id, intervals):
    logs = os.path.join(root, build_id, "logs")
    os.makedirs(logs)
    items = [{"source": "Disruption", "level": level, "from": "2026-11-04T14:00:00Z",
              "to": "2026-11-04T14:00:15Z", "locator": {"keys": {"backend-disruption-name": backend}},
              "message": {"humanMessage": message}}
             for backend, level, message in intervals]
    with open(os.path.join(logs, "e2e-timelines_spyglass_20261104-140000.json"), "w") as handle:
        json.dump({"items": items}, handle)


def test_scan_signature_matches_full_messages_on_the_selected_backends(tmp_path):
    long_prefix = "x" * 400  # past the parser's 300-character message cut
    _write_timeline(str(tmp_path), "1", [(BACKEND, "Error", long_prefix + " Client.Timeout exceeded roundtrip=15s")])
    _write_timeline(str(tmp_path), "2", [(BACKEND, "Error", "connection reset by peer roundtrip=14.1s")])
    _write_timeline(str(tmp_path), "3", [("kube-api-new-connections", "Error", "Client.Timeout exceeded")])
    _write_timeline(str(tmp_path), "4", [(BACKEND, "Info", "Client.Timeout exceeded")])
    os.makedirs(os.path.join(str(tmp_path), "5", "logs"))  # no timeline downloaded

    matched, scanned = scan_signature(str(tmp_path), "Client.Timeout exceeded", [BACKEND])

    assert matched == {"1"}
    assert scanned == {"1", "2", "3", "4"}


def test_main_reports_runs_without_timelines(tmp_path, capsys):
    _write_timeline(str(tmp_path), "1", [(BACKEND, "Error", "Client.Timeout exceeded")])
    runs_file = tmp_path / "runs.json"
    runs_file.write_text(json.dumps([
        _trend_run("1", "5.1.0-0.nightly-2026-11-01-000000", 15),
        _trend_run("2", "5.1.0-0.nightly-2026-11-01-000000", 4),
        _trend_run("3", "5.1.0-0.nightly-2026-11-08-000000", 0),
    ]))

    code = main(["--runs", str(runs_file), "--fix-payload", FIX, "--format", "json",
                 "--timelines-dir", str(tmp_path), "--backends", BACKEND, "--signature", "Client.Timeout"])

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["before_fix"]["signature"] == 1
    assert result["before_fix"]["timelines"] == 1
    assert any("Only 1 of 2 disrupted runs had timelines" in c for c in result["caveats"])


def test_main_table_shows_share_and_signature_columns(tmp_path, capsys):
    runs_file = tmp_path / "runs.json"
    runs_file.write_text(json.dumps([_trend_run("1", "5.1.0-0.nightly-2026-11-01-000000", 15),
                                     _trend_run("2", "5.1.0-0.nightly-2026-11-01-000000", 0)]))

    assert main(["--runs", str(runs_file), "--fix-payload", FIX, "--signature-runs", "1"]) == 0

    out = capsys.readouterr().out
    assert "2026-11-01   no         2    1 (50%)    15    15         1" in out
    assert "Before fix: 2 runs, 1 (50%) disrupted, P95 15s, 1 with the signature" in out


@pytest.mark.parametrize("argv, message", [
    (["--signature", "x"], "--signature needs --timelines-dir and --backends"),
    (["--signature", "x", "--signature-runs", "1"], "not both"),
])
def test_main_rejects_incomplete_signature_options(tmp_path, capsys, argv, message):
    with pytest.raises(SystemExit):
        main(["--runs", str(tmp_path / "runs.json"), "--fix-payload", FIX] + argv)
    assert message in capsys.readouterr().err


def test_main_reports_unreadable_input_and_bad_regex(tmp_path, capsys):
    assert main(["--runs", str(tmp_path / "missing.json"), "--fix-payload", FIX]) == 1
    assert "cannot read" in capsys.readouterr().err

    runs_file = tmp_path / "runs.json"
    runs_file.write_text("[]")
    assert main(["--runs", str(runs_file), "--fix-payload", FIX, "--timelines-dir", str(tmp_path),
                 "--backends", BACKEND, "--signature", "("]) == 1
    assert "bad --signature regex" in capsys.readouterr().err


def test_queries_cli_prints_family_and_root_cause_queries(capsys):
    assert queries_main(["--backends", BACKEND, "--component", "openshift-apiserver",
                         "--keyword", "watch cache", "--signal", "etcd"]) == 0

    result = json.loads(capsys.readouterr().out)
    assert result["families"] == ["openshift-api"]
    assert [q["name"] for q in result["queries"]] == [
        "root-cause", "component", "backend-family", "backend-family-history", "signal-etcd"]


def test_queries_cli_rejects_unknown_signal(capsys):
    with pytest.raises(SystemExit):
        queries_main(["--backends", BACKEND, "--signal", "disk"])
    assert "unknown signal disk" in capsys.readouterr().err


def test_queries_cli_records_classified_cards_separately(tmp_path, capsys):
    state_file = tmp_path / "investigation.json"
    state_file.write_text(json.dumps({"trend": {"shape": "step"}}))
    assert queries_main(["--record", str(state_file), "--demonstrated", "OCPBUGS-1",
                         "--related", "OCPBUGS-2,OCPBUGS-3"]) == 0
    saved = json.loads(state_file.read_text())
    assert saved["jira"] == {"demonstrated": ["OCPBUGS-1"], "related": ["OCPBUGS-2", "OCPBUGS-3"]}
    assert saved["trend"] == {"shape": "step"}
    capsys.readouterr()
    assert queries_main(["--record", str(state_file), "--demonstrated", "OCPBUGS-1", "--related", "OCPBUGS-1"]) == 1
    assert "cannot be both" in capsys.readouterr().err


def test_queries_cli_needs_backends_without_record(capsys):
    with pytest.raises(SystemExit):
        queries_main([])
    assert "--backends is empty" in capsys.readouterr().err



def test_clean_run_timelines_do_not_hide_missing_disrupted_ones():
    runs = [_trend_run("1", "5.1.0-0.nightly-2026-11-01-000000", 15),
            _trend_run("2", "5.1.0-0.nightly-2026-11-01-000000", 0)]
    result = check_fix(runs, FIX, signature_ids=set(), scanned_ids={"2"})
    assert any("Only 0 of 1 disrupted runs had timelines" in c for c in result["caveats"])


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
