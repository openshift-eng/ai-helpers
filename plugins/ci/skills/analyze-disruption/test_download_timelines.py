"""Tests for download_timelines.py — input parsing, target extraction, output formatting."""
import json
import os
import subprocess
import tempfile
from unittest.mock import patch, MagicMock

from download_timelines import (
    download_file,
    exit_code,
    extract_target,
    gcloud_env,
    list_timeline_files,
    main,
    parse_runs,
    process_run,
    sanitize_process_output,
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
        "gs://test-platform-results-public/logs/job/123/artifacts/target/openshift-e2e-test/artifacts/junit/e2e-timelines_spyglass_20260804-000654.json\n"
        "gs://test-platform-results-public/logs/job/123/artifacts/target/openshift-e2e-test/artifacts/junit/e2e-timelines_spyglass_20260804-012513.json\n"
    )
    mock_result.stderr = ""
    with patch("download_timelines.subprocess.run", return_value=mock_result) as run:
        files, error = list_timeline_files("job", "123")
    assert error is None
    assert len(files) == 2
    assert files[0].endswith("000654.json")
    assert files[1].endswith("012513.json")
    assert run.call_args.kwargs["env"]["CLOUDSDK_AUTH_DISABLE_CREDENTIALS"] == "true"


def test_list_timeline_files_failure_keeps_stderr():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = (
        "ERROR: There was a problem refreshing your current auth tokens: "
        "Reauthentication failed. cannot prompt during non-interactive execution.\n"
    )
    with patch("download_timelines.subprocess.run", return_value=mock_result):
        files, error = list_timeline_files("job", "123")
    assert files == []
    assert error is not None
    assert "Reauthentication failed" in error
    assert "cannot prompt during non-interactive execution" in error


def test_list_timeline_files_no_matches_is_not_a_command_failure():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "ERROR: (gcloud.storage.ls) One or more URLs matched no objects.\n"
    with patch("download_timelines.subprocess.run", return_value=mock_result):
        files, error = list_timeline_files("job", "123")
    assert files == []
    assert error is None


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
    mock_result.stdout = ""
    mock_result.stderr = (
        "Reauthentication failed. cannot prompt during non-interactive execution. "
        "token ya29.super-secret-token"
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("download_timelines.subprocess.run", return_value=mock_result):
            r = process_run("my-job", "999", tmpdir)

    assert r["error"].startswith("failed to download prowjob.json:")
    assert "Reauthentication failed" in r["error"]
    assert "ya29." not in r["error"]
    assert "[redacted]" in r["error"]
    assert r["timeline_files"] == []


def test_process_run_listing_failure_is_not_an_empty_list():
    prowjob_data = {"spec": {"pod_spec": {"containers": [{"args": ["--target=e2e"]}]}}}

    def mock_subprocess_run(cmd, **kwargs):
        result = MagicMock()
        result.stdout = ""
        result.stderr = ""
        if "cp" in cmd:
            dest = cmd[4]
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w") as f:
                json.dump(prowjob_data, f)
            result.returncode = 0
        else:
            result.returncode = 1
            result.stderr = "ERROR: HTTPSConnectionPool: network is unreachable"
        return result

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("download_timelines.subprocess.run", side_effect=mock_subprocess_run):
            r = process_run("my-job", "999", tmpdir)
        assert os.path.isfile(os.path.join(tmpdir, "999", "logs", "prowjob.json"))

    assert r["target"] == "e2e"
    assert r["timeline_files"] == []
    assert r["error"].startswith("failed to list timeline files:")
    assert "network is unreachable" in r["error"]


def test_process_run_keeps_successful_timeline_when_another_fails():
    prowjob_data = {"spec": {"pod_spec": {"containers": [{"args": ["--target=e2e"]}]}}}

    def mock_subprocess_run(cmd, **kwargs):
        result = MagicMock()
        result.stdout = ""
        result.stderr = ""
        result.returncode = 0
        if "cp" in cmd and "prowjob.json" in cmd[3]:
            dest = cmd[4]
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w") as f:
                json.dump(prowjob_data, f)
        elif "ls" in cmd:
            result.stdout = (
                "gs://bucket/e2e-timelines_spyglass_ok.json\n"
                "gs://bucket/e2e-timelines_spyglass_bad.json\n"
            )
        elif "cp" in cmd and cmd[3].endswith("bad.json"):
            result.returncode = 1
            result.stderr = "ERROR: timed out reading the object"
        else:
            dest = cmd[4]
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w") as f:
                f.write("{}")
        return result

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("download_timelines.subprocess.run", side_effect=mock_subprocess_run):
            r = process_run("my-job", "999", tmpdir)

    assert len(r["timeline_files"]) == 1
    assert r["timeline_files"][0].endswith("e2e-timelines_spyglass_ok.json")
    assert "1 of 2 timeline file downloads failed" in r["error"]
    assert "timed out reading the object" in r["error"]


def test_download_file_timeout_and_launch_errors():
    with patch("download_timelines.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd=["gcloud"], timeout=120)):
        ok, error = download_file("gs://bucket/prowjob.json", "/tmp/prowjob.json")
    assert ok is False
    assert error == "timed out after 120s"

    with patch("download_timelines.subprocess.run",
               side_effect=OSError(2, "No such file or directory")):
        ok, error = download_file("gs://bucket/prowjob.json", "/tmp/prowjob.json")
    assert ok is False
    assert error == "failed to start gcloud: No such file or directory"


def test_gcloud_env_does_not_change_process_environment():
    before = os.environ.get("CLOUDSDK_AUTH_DISABLE_CREDENTIALS")
    env = gcloud_env()
    assert env["CLOUDSDK_AUTH_DISABLE_CREDENTIALS"] == "true"
    assert os.environ.get("CLOUDSDK_AUTH_DISABLE_CREDENTIALS") == before
    assert env is not os.environ


def test_sanitize_process_output_redacts_tokens():
    text = sanitize_process_output(
        "Reauthentication failed.\naccess_token=ya29.secret-value bearer ya29.other\n"
    )
    assert "Reauthentication failed." in text
    assert "ya29." not in text
    assert "secret-value" not in text


def test_exit_code_total_partial_and_success():
    assert exit_code([{"error": None, "timeline_files": ["a.json"]}]) == 0
    assert exit_code([
        {"error": None, "timeline_files": ["a.json"]},
        {"error": "failed to download prowjob.json: timed out after 120s", "timeline_files": []},
    ]) == 2
    assert exit_code([
        {"error": "1 of 2 timeline file downloads failed: bad.json: exited 1",
         "timeline_files": ["ok.json"]},
    ]) == 2
    assert exit_code([
        {"error": "failed to download prowjob.json: exited 1", "timeline_files": []},
        {"error": "no timeline files found", "timeline_files": []},
    ]) == 1


def test_main_exit_status(tmp_path=None):
    runs = {
        "1": {"build_id": "1", "job": "job-a", "target": "e2e", "timeline_files": [],
              "error": "failed to download prowjob.json: timed out after 120s"},
        "2": {"build_id": "2", "job": "job-b", "target": "e2e", "timeline_files": ["/tmp/a.json"],
              "error": None},
    }

    def fake_process(job, build_id, output_dir):
        return runs[build_id]

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("download_timelines.check_gcloud"), \
                patch("download_timelines.process_run", side_effect=fake_process):
            try:
                main(["--runs", "job-a:1", "--output-dir", tmpdir, "--format", "json"])
                assert False, "total failure should exit 1"
            except SystemExit as exc:
                assert exc.code == 1
            try:
                main(["--runs", "job-a:1,job-b:2", "--output-dir", tmpdir, "--format", "text"])
                assert False, "partial success should exit 2"
            except SystemExit as exc:
                assert exc.code == 2
            runs["1"] = {"build_id": "1", "job": "job-a", "target": "e2e",
                         "timeline_files": ["/tmp/b.json"], "error": None}
            main(["--runs", "job-a:1", "--output-dir", tmpdir, "--format", "text"])
