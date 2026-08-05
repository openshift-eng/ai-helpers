"""Tests for download_timelines.py — input parsing, target extraction, output formatting."""
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

from download_timelines import (
    extract_target,
    list_timeline_files,
    parse_runs,
    process_run,
)


def test_parse_runs_single():
    runs = parse_runs("periodic-ci-openshift-release-main-ci-5.0-e2e-gcp-ovn-upgrade:2084701838124257280")
    assert runs == [("periodic-ci-openshift-release-main-ci-5.0-e2e-gcp-ovn-upgrade", "2084701838124257280")]


def test_parse_runs_multiple():
    runs = parse_runs(
        "job-a:111,job-b:222, job-c:333"
    )
    assert runs == [("job-a", "111"), ("job-b", "222"), ("job-c", "333")]


def test_parse_runs_trailing_comma():
    runs = parse_runs("job-a:111,")
    assert runs == [("job-a", "111")]


def test_extract_target_valid():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({
            "spec": {
                "pod_spec": {
                    "containers": [{
                        "args": [
                            "--image-import-pull-secret=/etc/pull-secret/.dockerconfigjson",
                            "--target=e2e-gcp-ovn-upgrade",
                            "--variant=ci-5.0",
                        ]
                    }]
                }
            }
        }, f)
        f.flush()
        assert extract_target(f.name) == "e2e-gcp-ovn-upgrade"
    os.unlink(f.name)


def test_extract_target_no_target():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"spec": {"pod_spec": {"containers": [{"args": ["--foo=bar"]}]}}}, f)
        f.flush()
        assert extract_target(f.name) is None
    os.unlink(f.name)


def test_extract_target_missing_file():
    assert extract_target("/nonexistent/path.json") is None


def test_extract_target_invalid_json():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("not json")
        f.flush()
        assert extract_target(f.name) is None
    os.unlink(f.name)


def test_list_timeline_files_success():
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = (
        "gs://test-platform-results/logs/job/123/artifacts/target/openshift-e2e-test/artifacts/junit/e2e-timelines_spyglass_20260804-000654.json\n"
        "gs://test-platform-results/logs/job/123/artifacts/target/openshift-e2e-test/artifacts/junit/e2e-timelines_spyglass_20260804-012513.json\n"
    )
    with patch("download_timelines.subprocess.run", return_value=mock_result):
        files = list_timeline_files("job", "123")
    assert len(files) == 2
    assert files[0].endswith("000654.json")
    assert files[1].endswith("012513.json")


def test_list_timeline_files_failure():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    with patch("download_timelines.subprocess.run", return_value=mock_result):
        files = list_timeline_files("job", "123")
    assert files == []


def test_process_run_full_success():
    prowjob_data = {
        "spec": {
            "pod_spec": {
                "containers": [{
                    "args": ["--target=e2e-gcp-ovn-upgrade"]
                }]
            }
        }
    }

    def mock_subprocess_run(cmd, **kwargs):
        result = MagicMock()
        if "cp" in cmd:
            if "prowjob.json" in cmd[3]:
                dest = cmd[4]
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "w") as f:
                    json.dump(prowjob_data, f)
            else:
                dest = cmd[4]
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "w") as f:
                    f.write("{}")
            result.returncode = 0
        elif "ls" in cmd:
            result.returncode = 0
            result.stdout = "gs://bucket/path/e2e-timelines_spyglass_20260804-000654.json\n"
        return result

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("download_timelines.subprocess.run", side_effect=mock_subprocess_run):
            r = process_run("my-job", "999", tmpdir)

    assert r["build_id"] == "999"
    assert r["job"] == "my-job"
    assert r["target"] == "e2e-gcp-ovn-upgrade"
    assert r["error"] is None
    assert len(r["timeline_files"]) == 1
    assert r["timeline_files"][0].endswith("e2e-timelines_spyglass_20260804-000654.json")


def test_process_run_prowjob_download_fails():
    mock_result = MagicMock()
    mock_result.returncode = 1

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("download_timelines.subprocess.run", return_value=mock_result):
            r = process_run("my-job", "999", tmpdir)

    assert r["error"] == "failed to download prowjob.json"
    assert r["timeline_files"] == []
