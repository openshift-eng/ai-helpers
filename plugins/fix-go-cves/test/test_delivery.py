#!/usr/bin/env python3
"""Behavioral controls for owned native delivery; no provider or scanner calls."""
import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

PLUGIN = Path(__file__).resolve().parents[1]
WORK = PLUGIN.parents[1] / ".work" / "fix-go-cves-delivery-tests"
ENGINE = r'''#!/usr/bin/env bash
set -eu
if read -r unexpected; then exit 91; fi
python3 - "$0" "$@" <<'INNER'
import json, os, sys
with open(os.environ['DELIVERY_TEST_CAPTURE'], 'a') as f:
    f.write(json.dumps({'script':sys.argv[1], 'args':sys.argv[2:],
        'test':os.environ.get('CVE_FIX_TEST_CMD'),
        'go':os.environ.get('CVE_FIX_GO_MINOR_GUARD'),
        'k8s':os.environ.get('CVE_FIX_K8S_VERSION_GUARD'),
        'docker':os.environ.get('DOCKER_HOST'), 'dapper':os.environ.get('DAPPER_ARGS'),
        'dapper_env':os.environ.get('DAPPER_ENV'),
        'common':os.environ.get('DELIVERY_TEST_COMMON')})+'\n')
INNER
printf 'original stdout\n'
printf 'original stderr\n' >&2
case "${1##*/}" in
  cancel)
    trap 'echo rollback >> "$DELIVERY_TEST_ROLLBACK"; sleep .2; exit 143' TERM
    echo "$$" > "$DELIVERY_TEST_READY"
    sleep 120 &
    wait "$!"
    ;;
  ignore-term)
    trap '' TERM
    echo "$$" > "$DELIVERY_TEST_READY"
    exec sleep 120
    ;;
  lingering)
    bash -c 'trap "" TERM; echo "$$" > "$DELIVERY_TEST_READY"; sleep .3; echo escaped >> "$DELIVERY_TEST_ROLLBACK"' &
    for attempt in {1..100}; do [[ ! -f "$DELIVERY_TEST_READY" ]] || break; sleep .01; done
    ;;
  killed) kill -KILL "$$" ;;
  unterminated) printf 'tail' ;;
  0|2|124|137) exit "${1##*/}" ;;
esac
'''


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="case-", dir=WORK)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.cwd = self.root / "workspace"
        self.cwd.mkdir()
        self.tmp = self.root / "tmp"
        self.tmp.mkdir()
        scripts = self.root / "scripts"
        scripts.mkdir()
        self.helper = scripts / "deliver.py"
        shutil.copyfile(PLUGIN / "scripts/deliver.py", self.helper)
        for engine in ("fix-all.sh", "report.sh"):
            (scripts / engine).write_text(ENGINE)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.env.update({"TMPDIR": str(self.tmp),
                    "DELIVERY_TEST_CAPTURE": str(self.root / "calls.jsonl"),
                    "DELIVERY_TEST_COMMON": "inherited", "DELIVERY_TEST_READY": str(self.root / "ready"),
                    "DELIVERY_TEST_ROLLBACK": str(self.root / "rollback")})
        for name in ("CVE_FIX_TEST_CMD", "CVE_FIX_GO_MINOR_GUARD", "CVE_FIX_K8S_VERSION_GUARD"):
            self.env.pop(name, None)

    def prepare(self, *arguments, cwd=None):
        argv = ["prepare", *arguments]
        cwd = self.cwd if cwd is None else cwd
        result = subprocess.run([sys.executable, str(self.helper), *argv], cwd=cwd,
                                env=self.env, capture_output=True, text=True, check=True)
        event = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": str(cwd),
                 "tool_use_id": "fixture-tool", "tool_input": {
                     "command": shlex.join(["python3", str(self.helper), *argv])},
                 "tool_response": {"stdout": result.stdout}}
        request = Path(json.loads(result.stdout)["fix_go_cves_request"])
        return event, request

    def repo(self, name="0"):
        path = self.root / "repos" / name
        if not path.exists():
            path.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(path)], env=self.env, check=True, capture_output=True)
        return str(path)

    def invoke(self, event):
        process = subprocess.run([sys.executable, str(self.helper), "hook"], cwd=self.cwd,
                                 env=self.env, input=json.dumps(event), capture_output=True,
                                 text=True, timeout=20, check=True)
        self.assertEqual(process.stderr, "")
        return json.loads(process.stdout)

    def calls(self):
        path = self.root / "calls.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def logs(self, result):
        return [Path(line[4:]) for line in result["stopReason"].splitlines() if line.startswith("LOG=")]

    def unconfirmed(self, result):
        self.assertIs(result["continue"], False)
        self.assertIn("completion unconfirmed:", result["stopReason"])

    def test_actual_exit_codes_and_original_output(self):
        for code in ("0", "2", "124", "137", "killed"):
            with self.subTest(code=code):
                event, request = self.prepare("fix", self.repo(code))
                result = self.invoke(event)
                actual = "137" if code == "killed" else code
                self.assertIn(f"exit={actual}", result["stopReason"])
                self.assertEqual(self.logs(result)[0].read_bytes(),
                                 f"original stdout\noriginal stderr\n\nexit={actual}\n".encode())
                self.assertFalse(request.exists())
                self.assertTrue(request.with_name("running.json").exists())
                self.assertEqual("unconfirmed" in result["stopReason"], actual not in ("0", "2"))
        self.assertEqual(len(self.calls()), 5)

    def test_unterminated_original_output_cannot_swallow_terminal_marker(self):
        result = self.invoke(self.prepare("fix", self.repo("unterminated"))[0])
        self.assertTrue(self.logs(result)[0].read_bytes().endswith(b"tail\nexit=0\n"))

    def test_distinct_batch_settings_and_common_environment(self):
        event, _ = self.prepare("--env", "CVE_FIX_TEST_CMD=echo '$x'; make unit", "--env",
                                "CVE_FIX_GO_MINOR_GUARD=true", "fix", self.repo("2"), "release-1.0", "--next",
                                "--env", "CVE_FIX_TEST_CMD=", "--env", "CVE_FIX_K8S_VERSION_GUARD=false",
                                "report", self.repo("0"))
        result = self.invoke(event)
        calls = self.calls()
        self.assertEqual([c["args"] for c in calls], [[self.repo("2"), "release-1.0"], [self.repo("0")]])
        self.assertEqual([Path(c["script"]).name for c in calls], ["fix-all.sh", "report.sh"])
        self.assertEqual([c["test"] for c in calls], ["echo '$x'; make unit", ""])
        self.assertEqual([c["go"] for c in calls], ["true", None])
        self.assertEqual([c["k8s"] for c in calls], [None, "false"])
        self.assertEqual([c["common"] for c in calls], ["inherited", "inherited"])
        self.assertEqual(len(self.logs(result)), 2)
        self.assertNotIn("unconfirmed", result["stopReason"])

    def test_known_cve_settings_follow_prepare_environment_and_run_overrides(self):
        self.env.update(CVE_FIX_TEST_CMD="session test", CVE_FIX_GO_MINOR_GUARD="true",
                        DOCKER_HOST="unix:///session-fixture.sock", DAPPER_ARGS="",
                        DELIVERY_TEST_CREDENTIAL="fixture-private-value")
        self.env.pop("DAPPER_ENV", None)
        event, request = self.prepare("--env", "CVE_FIX_TEST_CMD=selected test", "fix", self.repo("2"),
                                      "--next", "report", self.repo("0"))
        self.assertNotIn("fixture-private-value", request.read_text())
        self.env.update(CVE_FIX_TEST_CMD="hook test", CVE_FIX_GO_MINOR_GUARD="false",
                        CVE_FIX_K8S_VERSION_GUARD="false", DELIVERY_TEST_COMMON="hook inherited",
                        DOCKER_HOST="unix:///hook-fixture.sock", DAPPER_ARGS="hook args", DAPPER_ENV="hook env")
        result = self.invoke(event)
        self.assertNotIn("unconfirmed", result["stopReason"])
        calls = self.calls()
        self.assertEqual([c["test"] for c in calls], ["selected test", "session test"])
        self.assertEqual([c["go"] for c in calls], ["true", "true"])
        self.assertEqual([c["k8s"] for c in calls], [None, None])
        self.assertEqual([c["docker"] for c in calls], ["unix:///session-fixture.sock"] * 2)
        self.assertEqual([c["dapper"] for c in calls], [""] * 2)
        self.assertEqual([c["dapper_env"] for c in calls], [None, None])
        self.assertEqual([c["common"] for c in calls], ["hook inherited", "hook inherited"])

    def test_abnormal_first_run_leaves_later_operation_unreached(self):
        event, _ = self.prepare("fix", self.repo("124"), "--next", "report", self.repo("0"))
        result = self.invoke(event)
        self.unconfirmed(result)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(len(self.logs(result)), 1)

    def test_unrelated_bash_wrong_event_and_stale_cat_do_not_consume(self):
        for change in ("cat", "event", "tool"):
            with self.subTest(change=change):
                event, request = self.prepare("fix", self.repo("0"))
                if change == "cat":
                    event["tool_input"]["command"] = f"cat {request}"
                elif change == "event":
                    event["hook_event_name"] = "PostToolUseFailure"
                else:
                    event["tool_name"] = "Read"
                self.assertEqual(self.invoke(event), {})
                self.assertTrue(request.exists())
        self.assertEqual(self.calls(), [])

    def test_background_and_interrupted_prepare_reject_before_claim(self):
        for flag in ("run_in_background", "interrupted"):
            with self.subTest(flag=flag):
                event, request = self.prepare("fix", self.repo("0"))
                event["tool_input" if flag == "run_in_background" else "tool_response"][flag] = True
                result = self.invoke(event)
                self.unconfirmed(result)
                self.assertTrue(request.exists())
                self.assertFalse(request.with_name("running.json").exists())
                self.assertEqual(self.logs(result), [])
                event["tool_input"]["command"] = "printf unrelated"
                self.assertEqual(self.invoke(event), {})
                self.assertTrue(request.exists())
        self.assertEqual(self.calls(), [])

    def test_duplicate_and_concurrent_hook_dispatch_run_once(self):
        event, _ = self.prepare("fix", self.repo("0"))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self.invoke, [event, event]))
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(sum("unconfirmed" not in r["stopReason"] for r in results), 1)
        self.unconfirmed(self.invoke(event))
        self.assertEqual(len(self.calls()), 1)

    def test_changed_data_command_and_cwd_reject_before_engine(self):
        for change in ("runs", "argv", "cwd", "inherited-env", "inherited-type", "inherited-nul", "operator", "extra"):
            with self.subTest(change=change):
                event, request = self.prepare("fix", self.repo("0"))
                data = json.loads(request.read_text())
                if change == "runs": data["runs"][0]["args"] = ["2"]
                elif change == "argv": data["argv"].append("different")
                elif change == "cwd": data["cwd"] = "/"
                elif change == "inherited-env": data["env"]["DELIVERY_TEST_CREDENTIAL"] = "not transported"
                elif change == "inherited-type": data["env"]["CVE_FIX_TEST_CMD"] = None
                elif change == "inherited-nul": data["env"]["CVE_FIX_TEST_CMD"] = "bad\0value"
                else: event["tool_input"]["command"] += "; echo unrelated" if change == "operator" else " extra"
                request.write_text(json.dumps(data))
                self.unconfirmed(self.invoke(event))
                self.assertTrue(request.exists())
        self.assertEqual(self.calls(), [])

    def test_ownership_type_mode_and_canonical_path(self):
        for change in ("symlink", "hardlink", "directory", "fifo", "mode", "parent-mode", "parent-link", "missing"):
            with self.subTest(change=change):
                event, request = self.prepare("fix", self.repo("0"))
                if change == "symlink":
                    other = request.with_name("other.json")
                    request.rename(other)
                    request.symlink_to(other)
                elif change == "hardlink": os.link(request, request.with_name("other.json"))
                elif change in ("directory", "fifo"):
                    request.unlink()
                    request.mkdir(mode=0o700) if change == "directory" else os.mkfifo(request, 0o600)
                elif change == "mode": request.chmod(0o644)
                elif change == "parent-mode": request.parent.chmod(0o755)
                elif change == "parent-link":
                    alias = self.root / "alias"
                    alias.symlink_to(request.parent, target_is_directory=True)
                    event["tool_response"]["stdout"] = json.dumps({"fix_go_cves_request": str(alias / request.name)})
                else: request.unlink()
                self.unconfirmed(self.invoke(event))
        self.assertEqual(self.calls(), [])

    def test_malformed_response_and_existing_log_fail_closed(self):
        event, request = self.prepare("fix", self.repo("0"))
        event["tool_response"]["stdout"] = "bad json"
        self.unconfirmed(self.invoke(event))
        self.assertTrue(request.exists())
        event, request = self.prepare("fix", self.repo("0"))
        (request.parent / "runtime-1.log").write_text("foreign existing bytes")
        result = self.invoke(event)
        self.unconfirmed(result)
        self.assertEqual(self.logs(result), [])
        self.assertEqual(self.calls(), [])
        self.assertEqual((request.parent / "runtime-1.log").read_text(), "foreign existing bytes")

    def test_existing_claim_is_preserved_without_engine_execution(self):
        event, request = self.prepare("fix", self.repo("0"))
        claimed = request.with_name("running.json")
        claimed.write_text("existing retained claim")
        self.unconfirmed(self.invoke(event))
        self.assertEqual(claimed.read_text(), "existing retained claim")
        self.assertTrue(request.exists())
        self.assertEqual(self.calls(), [])

    def test_invalid_prepare_does_not_create_or_run_requests(self):
        repo = self.repo("0")
        cases = [[], ["fix"], ["report"], ["fix", "named-repo"], ["fix", "main", repo],
                 ["report", repo, "main"], ["fix", repo, "main", "extra"], ["fix", repo, "--bad"],
                 ["report", str(self.cwd)],
                 ["--env", "OPENAI_API_KEY=not-transported", "fix"], ["--env", "bad", "fix"],
                 ["--env", "CVE_FIX_TEST_CMD=a", "--env", "CVE_FIX_TEST_CMD=b", "fix"],
                 ["fix", "--next"], ["unknown"]]
        for args in cases:
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, str(self.helper), "prepare", *args],
                                        cwd=self.cwd, env=self.env, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("fix_go_cves_request", result.stdout)
        self.assertEqual(list(self.tmp.glob("fix-go-cves-*")), [])
        self.assertEqual(self.calls(), [])

    def test_signal_cancellation_preserves_partial_log_and_rollback(self):
        event, request = self.prepare("fix", self.repo("cancel"), "--next", "fix", self.repo("0"))
        with subprocess.Popen([sys.executable, str(self.helper), "hook"], cwd=self.cwd, env=self.env,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True) as process:
            process.stdin.write(json.dumps(event))
            process.stdin.close()
            process.stdin = None
            deadline = time.monotonic() + 5
            while not (self.root / "ready").exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue((self.root / "ready").exists())
            process.send_signal(signal.SIGTERM)
            output, error = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, error)
        result = json.loads(output)
        self.unconfirmed(result)
        self.assertEqual((self.root / "rollback").read_text(), "rollback\n")
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(len(self.logs(result)), 1)
        self.assertIn("original stdout", self.logs(result)[0].read_text())
        self.assertNotIn("exit=", self.logs(result)[0].read_text())
        self.assertFalse(request.exists())
        self.unconfirmed(self.invoke(event))
        self.assertEqual(len(self.calls()), 1)

    def test_term_ignoring_child_gets_grace_then_is_killed_and_reaped(self):
        event, request = self.prepare("fix", self.repo("ignore-term"), "--next", "fix", self.repo("0"))
        with subprocess.Popen([sys.executable, str(self.helper), "hook"], cwd=self.cwd, env=self.env,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True) as process:
            process.stdin.write(json.dumps(event))
            process.stdin.close()
            process.stdin = None
            deadline = time.monotonic() + 5
            while not (self.root / "ready").exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue((self.root / "ready").exists())
            child_pid = int((self.root / "ready").read_text())
            started = time.monotonic()
            process.send_signal(signal.SIGTERM)
            output, error = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, error)
        self.assertGreaterEqual(time.monotonic() - started, 9)
        result = json.loads(output)
        self.unconfirmed(result)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(len(self.logs(result)), 1)
        self.assertIn("original stdout", self.logs(result)[0].read_text())
        self.assertNotIn("exit=", self.logs(result)[0].read_text())
        self.assertFalse(request.exists())
        with self.assertRaises(ProcessLookupError):
            os.kill(child_pid, 0)

    def test_launch_failure_preserves_owned_empty_log_without_exit(self):
        tools = self.root / "git-only"
        tools.mkdir()
        (tools / "git").symlink_to(shutil.which("git"))
        self.env["PATH"] = str(tools)
        event, _ = self.prepare("fix", self.repo("0"))
        result = self.invoke(event)
        self.unconfirmed(result)
        self.assertEqual(len(self.logs(result)), 1)
        self.assertEqual(self.logs(result)[0].read_bytes(), b"")
        self.assertEqual(self.calls(), [])

    def test_completed_request_does_not_signal_unrelated_process_group(self):
        with subprocess.Popen(["sleep", "120"], env=self.env, start_new_session=True) as unrelated:
            try:
                result = self.invoke(self.prepare("fix", self.repo("0"))[0])
                self.assertNotIn("unconfirmed", result["stopReason"])
                self.assertIsNone(unrelated.poll())
            finally:
                unrelated.terminate()
                unrelated.wait(timeout=5)

    def test_normal_leader_exit_cleans_owned_lingering_group(self):
        event, _ = self.prepare("fix", self.repo("lingering"))
        result = self.invoke(event)
        self.assertNotIn("unconfirmed", result["stopReason"])
        before = self.logs(result)[0].read_bytes()
        time.sleep(.4)
        self.assertFalse((self.root / "rollback").exists())
        self.assertEqual(self.logs(result)[0].read_bytes(), before)

    def test_symlink_installation_resolves_actual_helper(self):
        event, _ = self.prepare("fix", self.repo("0"))
        alias = self.root / "installed"
        alias.symlink_to(self.helper.parent, target_is_directory=True)
        argv = shlex.split(event["tool_input"]["command"])
        argv[1] = str(alias / "deliver.py")
        event["tool_input"]["command"] = shlex.join(argv)
        result = self.invoke(event)
        self.assertNotIn("unconfirmed", result["stopReason"])
        self.assertEqual(len(self.calls()), 1)

    def test_temporary_directory_inside_selected_worktree_rejected_before_writes(self):
        target = Path(self.repo("0"))
        module = target / "module"
        module.mkdir()
        temporary = target / "temporary"
        temporary.mkdir()
        for mode in ("fix", "report"):
            for selected in (target, module):
                with self.subTest(mode=mode, selected=selected):
                    result = subprocess.run([sys.executable, str(self.helper), "prepare", mode, str(selected)],
                                            cwd=self.cwd, env={**self.env, "TMPDIR": str(temporary)},
                                            capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("outside repository worktrees", result.stderr)
                    self.assertEqual(list(temporary.iterdir()), [])
        self.assertEqual(self.calls(), [])

    def test_later_batch_target_checked_before_any_delivery_writes(self):
        first, second = self.repo("0"), Path(self.repo("2"))
        temporary = second / "temporary"
        temporary.mkdir()
        result = subprocess.run([sys.executable, str(self.helper), "prepare", "fix", first,
                                 "--next", "report", str(second)], cwd=self.cwd,
                                env={**self.env, "TMPDIR": str(temporary)}, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside repository worktrees", result.stderr)
        self.assertEqual(list(temporary.iterdir()), [])
        self.assertEqual(self.calls(), [])

    def test_temporary_directory_inside_newline_named_worktree_rejected(self):
        target = Path(self.repo("trailing-newline\n"))
        temporary = target / "temporary"
        temporary.mkdir()
        result = subprocess.run([sys.executable, str(self.helper), "prepare", "report", str(target)],
                                cwd=self.cwd, env={**self.env, "TMPDIR": str(temporary)},
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside repository worktrees", result.stderr)
        self.assertEqual(list(temporary.iterdir()), [])

    def test_broad_or_unrelated_cwd_does_not_become_a_target(self):
        for cwd in (Path("/"), self.root):
            with self.subTest(cwd=cwd):
                result = self.invoke(self.prepare("report", self.repo("0"), cwd=cwd)[0])
                self.assertNotIn("unconfirmed", result["stopReason"])
        self.env["TMPDIR"] = str(self.cwd)
        result = self.invoke(self.prepare("report", self.repo("0"))[0])
        self.assertNotIn("unconfirmed", result["stopReason"])
        self.assertEqual(len(self.calls()), 3)

    def test_terminal_capture_failure_retains_partial_and_stops_batch(self):
        event, _ = self.prepare("fix", self.repo("0"), "--next", "fix", self.repo("0"))
        spec = importlib.util.spec_from_file_location("delivery_subject", self.helper)
        subject = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(subject)
        original_open = Path.open

        class FullLog:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *args): self.stream.close()
            def fileno(self): return self.stream.fileno()
            def write(self, _text): raise OSError("injected terminal capture failure")
            def flush(self): self.stream.flush()

        def open_with_full_log(path, *args, **kwargs):
            stream = original_open(path, *args, **kwargs)
            return FullLog(stream) if path.name.startswith("runtime-") else stream

        with patch.dict(os.environ, self.env, clear=True), patch.object(Path, "open", open_with_full_log):
            result = subject.hook(event)
        self.unconfirmed(result)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(len(self.logs(result)), 1)
        self.assertTrue(self.logs(result)[0].read_text().startswith("original stdout\n"))
        self.assertNotIn("exit=", self.logs(result)[0].read_text())


if __name__ == "__main__":
    unittest.main()
