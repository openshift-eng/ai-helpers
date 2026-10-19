#!/usr/bin/env python3
"""Hermetic checks for replay evidence boundaries; no models or network."""

import copy
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import yaml


SPEC = importlib.util.spec_from_file_location(
    "cve_eval", Path(__file__).parent / "scripts/eval.py")
EVAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVAL)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, extra=None, manifest=None):
        archive = self.root / "plugin.tar.gz"
        entries = {
            ".claude-plugin/plugin.json": json.dumps(manifest or {
                "name": "fix-go-cves", "description": "fixture", "version": "0.1.0",
                "author": "github.com/openshift-eng"}),
            **{f"subagents/{name}.sh": "#!/bin/sh\n" for name in EVAL.AUDITS},
        }
        with tarfile.open(archive, "w:gz") as tar:
            for name, content in entries.items():
                data = content.encode()
                entry = tarfile.TarInfo(name)
                entry.size = len(data)
                tar.addfile(entry, io.BytesIO(data))
            if extra:
                entry, content = extra
                entry.size = len(content)
                tar.addfile(entry, io.BytesIO(content))
        return archive

    def test_recorded_audits_can_be_unpacked(self):
        destination = self.root / "plugin"
        EVAL.unpack_plugin(self.archive(), destination)
        for audit in EVAL.AUDITS:
            self.assertTrue((destination / "subagents" / f"{audit}.sh").is_file())

    def test_archive_cannot_escape_or_replace_members(self):
        for name in ("../escaped", "/escaped", "scripts/../../escaped",
                     ".mcp.json", ".claude-plugin/plugin.json"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    EVAL.unpack_plugin(self.archive((tarfile.TarInfo(name), b"bad")),
                                       self.root / "plugin")
        self.assertFalse((self.root / "escaped").exists())

    def test_archive_cannot_install_links_or_special_files(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE):
            with self.subTest(kind=kind):
                member = tarfile.TarInfo("scripts/linked")
                member.type = kind
                member.linkname = "../../outside"
                with self.assertRaises(ValueError):
                    EVAL.unpack_plugin(self.archive((member, b"")), self.root / "plugin")

    def test_manifest_cannot_enable_runtime_hooks(self):
        manifest = {"name": "fix-go-cves", "description": "fixture", "version": "0.1.0",
                    "author": "github.com/openshift-eng", "hooks": {"Stop": []}}
        with self.assertRaises(ValueError):
            EVAL.unpack_plugin(self.archive(manifest=manifest), self.root / "plugin")

    def test_final_reply_excludes_progress_and_uses_completed_result(self):
        stream = [{"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Progress with an incorrect diagnosis"}]}},
            {"type": "result", "result": "Completed diagnosis", "is_error": False}]
        self.assertEqual(EVAL.final_reply(stream), "Completed diagnosis")

    def test_progress_or_errored_results_are_not_completed_answers(self):
        for stream in ([], [{"type": "assistant", "result": "progress"}],
                       [{"type": "result", "result": "   "}],
                       [{"type": "result", "result": "incomplete", "is_error": True}],
                       [{"type": "result", "result": "old answer"},
                        {"type": "result", "result": "failed retry", "is_error": True}]):
            with self.subTest(stream=stream):
                with self.assertRaises(ValueError):
                    EVAL.final_reply(stream)

    def case(self):
        case = self.root / "cases/case-005"
        (case / "output").mkdir(parents=True)
        expected = {"result_commit": "a" * 40, "fix_branch": "fix-recorded",
                    "arguments": ["0.24"], "base_branch": "release-0.24"}
        state = {"head": "a" * 40, "branch": "fix-recorded", "dirty": "", "unexpected_ignored": [],
                 "invocations": [{"arguments": ["0.24"]}], "refs_unchanged": True,
                 "plugin_unchanged": True, "gh_calls": "", "trace_violations": [],
                 "permission_denials": [], "expected": expected}
        EVAL.write_json(case / "output/state.json", state)
        (case / "output/reply.md").write_text("Recorded commit aaaaaaa, backport bbbbbbb.\n")
        (case / "annotations.yaml").write_text(yaml.safe_dump(
            {"required_commits": ["a" * 40, "b" * 40]}))
        return case, state

    def test_legitimate_contract_failure_is_false_not_an_error(self):
        case, state = self.case()
        state["dirty"] = " M go.mod"
        EVAL.write_json(case / "output/state.json", state)
        with patch.object(EVAL, "EVAL_ROOT", self.root):
            verdict = EVAL.check(case)
        self.assertIs(verdict["passed"], False)
        self.assertIn("clean checkout", verdict["reason"])

    def test_missing_or_malformed_state_is_an_error(self):
        case, _ = self.case()
        path = case / "output/state.json"
        for content in (None, "not json", "{}"):
            with self.subTest(content=content):
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_text(content)
                with self.assertRaises((OSError, ValueError, KeyError)):
                    EVAL.check(case)

    def test_complete_contract_passes_and_forbidden_activity_fails(self):
        case, clean = self.case()
        with patch.object(EVAL, "EVAL_ROOT", self.root):
            self.assertIs(EVAL.check(case)["passed"], True)
            for key, value in (("invocations", []), ("gh_calls", "pr create"),
                               ("permission_denials", ["git push"]),
                               ("unexpected_ignored", ["bin/unexpected"]),
                               ("plugin_unchanged", False), ("refs_unchanged", False)):
                with self.subTest(key=key):
                    state = {**clean, key: value}
                    EVAL.write_json(case / "output/state.json", state)
                    self.assertIs(EVAL.check(case)["passed"], False)

    def test_extraction_uses_final_reply_and_retains_denials(self):
        case, state = self.case()
        state["workspace"] = str(case)
        EVAL.write_json(case / "output/state.json", state)
        EVAL.write_json(case / "run_result.json", {
            "exit_code": 0, "permission_denials": ["git push"]})
        stream = [{"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Progress only"}]}},
            {"type": "result", "result": "The final answer", "is_error": False}]
        (case / "stdout.log").write_text("\n".join(json.dumps(event) for event in stream))
        EVAL.extract(self.root)
        self.assertEqual((case / "output/reply.md").read_text(), "The final answer\n")
        self.assertEqual(EVAL.read_json(case / "output/state.json")["permission_denials"],
                         ["git push"])
        EVAL.write_json(case / "run_result.json", {"exit_code": 1, "error": "not authenticated"})
        with self.assertRaises(ValueError):
            EVAL.extract(self.root)

    def test_contract_checks_command_blocks_but_allows_explanation(self):
        case, _ = self.case()
        reply = case / "output/reply.md"
        with patch.object(EVAL, "EVAL_ROOT", self.root):
            reply.write_text("Commits aaaaaaa and bbbbbbb. No gh pr create command was printed.")
            self.assertIs(EVAL.check(case)["passed"], True)
            reply.write_text("Commits aaaaaaa and bbbbbbb.\n```sh\ngh pr create --title bad\n```\n")
            self.assertIs(EVAL.check(case)["passed"], False)
            reply.write_text("Commits caaaaaaa and bbbbbbb.")
            self.assertIs(EVAL.check(case)["passed"], False)

    def test_replay_runs_with_fresh_home_and_without_site_packages(self):
        workspace = self.root / "checkout"
        private = workspace / ".replay"
        private.mkdir(parents=True)
        home = self.root / "empty-home"
        home.mkdir()
        EVAL.git(workspace, "init")
        EVAL.git(workspace, "config", "user.name", "Eval")
        EVAL.git(workspace, "config", "user.email", "eval@example.invalid")
        (workspace / "source.txt").write_text("initial\n")
        EVAL.git(workspace, "add", "source.txt")
        EVAL.git(workspace, "commit", "-m", "initial")
        initial = EVAL.git(workspace, "rev-parse", "HEAD")
        (workspace / ".git/info/exclude").write_text("/.replay/\n")
        shutil.copyfile(EVAL.__file__, private / "driver.py")
        EVAL.write_json(private / "meta.json", {
            "arguments": ["0.24"], "base_branch": "release-0.24", "fix_branch": "fix-recorded",
            "default_commit": initial, "result_commit": initial, "exit_code": 2})
        (private / "run.log").write_text("Recorded partial result\n")
        result = subprocess.run(
            [sys.executable, "-I", "-S", str(private / "driver.py"), "replay", "0.24"],
            cwd=workspace, env={**os.environ, "HOME": str(home)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "Recorded partial result\n")
        self.assertEqual(EVAL.git(workspace, "branch", "--show-current"), "fix-recorded")

    def trace(self, command, project=None):
        workspace = self.root / "checkout"
        stream = [{"type": "assistant", "message": {"content": [{
            "type": "tool_use", "name": "Bash", "input": {"command": command}}]}}]
        if project:
            with patch.object(EVAL, "EVAL_ROOT", project / "plugins/fix-go-cves/evals"):
                return EVAL.trace_violations(stream, workspace)
        return EVAL.trace_violations(stream, workspace)

    def test_git_directory_and_config_options_cannot_hide_publication(self):
        for command in ("git -C /tmp/checkout push origin HEAD",
                        "git -c advice.detachedHead=false -C /tmp/checkout push origin HEAD",
                        "git --git-dir=/tmp/repo.git push origin HEAD"):
            with self.subTest(command=command):
                self.assertIn("Attempted publication or destructive git operation", self.trace(command))
        self.assertEqual(self.trace("git -C /tmp/checkout log --oneline"), [])

    def test_workspace_path_cannot_hide_a_source_checkout_read(self):
        project = self.root / "project"
        command = f"cat {project}/plugins/fix-go-cves/evals/cases/case-005/reply.md {self.root}/checkout/source.txt"
        self.assertIn("Command accesses the source checkout", self.trace(command, project))

    def test_explicit_checkout_argument_is_scored_in_case_context(self):
        workspace = self.root / "checkout"
        meta = {"arguments": ["0.24"], "base_branch": "release-0.24"}
        for arguments in ([str(workspace), "0.24"], [".", "release-0.24"]):
            with self.subTest(arguments=arguments):
                self.assertTrue(EVAL.requested_arguments(arguments, meta, workspace))
        self.assertFalse(EVAL.requested_arguments([str(self.root / "other"), "0.24"], meta, workspace))

    def test_live_dry_run_is_rejected_before_preparing_or_executing(self):
        argv = ["eval.py", "dry-run", "--workspace", str(self.root)]
        with patch.object(sys, "argv", argv), patch.object(
                EVAL, "case_data", return_value=({"mode": "live"}, {})), patch.object(
                EVAL, "prepare") as prepare, patch.object(EVAL, "live_run") as execute:
            with self.assertRaisesRegex(ValueError, "dry-run"):
                EVAL.main()
            prepare.assert_not_called()
            execute.assert_not_called()

    def test_live_wrapper_runs_the_script_and_records_its_actual_status(self):
        # This stub tests wrapper plumbing only, not real remediation.
        workspace = self.root / "checkout"
        workspace.mkdir()
        EVAL.git(workspace, "init")
        EVAL.git(workspace, "-c", "user.name=Eval", "-c", "user.email=eval@example.invalid",
                 "commit", "--allow-empty", "-m", "initial")
        (workspace / ".replay").mkdir()
        (workspace / ".replay/run.log").write_text("A stale recorded answer\n")
        runtime = self.root / "runtime"
        EVAL.write_json(workspace / ".replay/meta.json", {"runtime_dir": str(runtime)})
        script = runtime / "plugin/scripts/fix-all.sh"
        script.parent.mkdir(parents=True)
        script.write_text('echo "actual $*"\necho "diagnostic" >&2\n'
                          'if read -r line; then exit 99; fi\nexit 2\n')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = EVAL.live_run(workspace, ["0.24"])
        self.assertEqual(status, 2)
        self.assertEqual(output.getvalue(), "actual 0.24\ndiagnostic\n")
        self.assertEqual((workspace / ".replay/run.log").read_text(), output.getvalue())
        self.assertEqual(EVAL.read_json(workspace / ".replay/status.json"), {
            "exit_code": 2, "head": EVAL.git(workspace, "rev-parse", "HEAD"),
            "branch": EVAL.git(workspace, "branch", "--show-current")})

    def test_live_contract_uses_live_annotations_and_retains_runtime_result(self):
        case, state = self.case()
        state.update(runtime_exit=2, runtime_summary=True, changed_files=["go.mod"],
                     runtime_head=state["head"], runtime_branch=state["branch"],
                     runtime_plugin_unchanged=True)
        annotation = self.root / "live/cases/case-005/annotations.yaml"
        annotation.parent.mkdir(parents=True)
        annotation.write_text(yaml.safe_dump({"required_commits": ["c" * 40]}))
        (case / "output/reply.md").write_text("Actual commit ccccccc; partial result.\n")
        EVAL.write_json(case / "output/state.json", state)
        with patch.object(EVAL, "EVAL_ROOT", self.root):
            self.assertIs(EVAL.check(case, live=True)["passed"], True)
            for key, value in (("runtime_exit", None), ("runtime_summary", False),
                               ("head", "d" * 40), ("runtime_plugin_unchanged", False),
                               ("changed_files", ["pkg/source.go"])):
                with self.subTest(key=key):
                    EVAL.write_json(case / "output/state.json", {**state, key: value})
                    self.assertIs(EVAL.check(case, live=True)["passed"], False)

    def test_build_artifact_allowance_is_exact_and_manifest_backed(self):
        workspace = self.root / "cases/case-001"
        workspace.mkdir(parents=True)
        EVAL.git(workspace, "init")
        (workspace / ".gitignore").write_text("/bin/\n")
        EVAL.git(workspace, "add", ".gitignore")
        EVAL.git(workspace, "-c", "user.name=Eval", "-c", "user.email=eval@example.invalid",
                 "commit", "-m", "initial")
        (workspace / "bin").mkdir()
        for name in ("app", "other", "data"):
            path = workspace / "bin" / name
            path.write_text("output\n")
            path.chmod(0o644 if name == "data" else 0o755)
        outside = self.root / "outside"
        outside.write_text("outside\n")
        outside.chmod(0o755)
        (workspace / "bin/link").symlink_to(outside)
        manifest = workspace / ".git/fix-go-cves-artifacts"
        manifest.write_text("\n".join(map(str, (workspace / "bin/app", workspace / "bin/data",
                                                  outside, workspace / "bin/link"))) + "\nbin/other\n")
        self.assertEqual(EVAL.generated_artifacts(workspace), {"bin/app"})
        (workspace / ".replay").mkdir()
        (workspace / ".git/info/exclude").write_text("/.replay/\n/output/\n")
        head = EVAL.git(workspace, "rev-parse", "HEAD")
        EVAL.write_json(self.root / "control/case-001/baseline.json", {
            "meta": {"mode": "live", "original_branch": EVAL.git(workspace, "branch", "--show-current"),
                     "default_commit": head}, "refs": {}, "plugin_hashes": {}, "runtime_plugin_hashes": {},
            "runtime_dir": str(self.root / "control/case-001/runtime")})
        EVAL.capture(workspace)
        state = EVAL.read_json(workspace / "output/state.json")
        self.assertEqual(state["generated_artifacts"], ["bin/app"])
        self.assertEqual(set(state["unexpected_ignored"]), {"bin/data", "bin/link", "bin/other"})

    def test_runtime_read_allowance_excludes_baseline_and_neighbors(self):
        workspace = self.root / "cases/case-005"
        runtime = self.root / "control/case-005/runtime"
        for path, allowed in ((runtime / "tmp/run.log", True),
                              (runtime / "plugin/scripts/fix-all.sh", True),
                              (self.root / "control/case-005/baseline.json", False),
                              (self.root / "control/case-006/runtime/tmp/run.log", False)):
            with self.subTest(path=path):
                stream = [{"type": "assistant", "message": {"content": [{
                    "type": "tool_use", "name": "Read", "input": {"file_path": str(path)}}]}}]
                violations = EVAL.trace_violations(stream, workspace)
                self.assertEqual(not violations, allowed)
                stream[0]["message"]["content"][0] = {
                    "type": "tool_use", "name": "Bash", "input": {"command": f"cat {path}"}}
                self.assertEqual(not EVAL.trace_violations(stream, workspace), allowed)

    def summary(self):
        # Shape emitted by the stock harness's _aggregate_samples: successful
        # samples live under stability, not a top-level `samples` array.
        sampled = {"value": True, "judge_type": "llm", "stability": {
            "samples": 3, "error_count": 0, "values": [True, True, False],
            "pass_count": 2, "stable": False}}
        return {"per_case": {"case-005": {
            "replay_contract": {"value": True, "judge_type": "check"},
            "backport": copy.deepcopy(sampled), "action_owner": copy.deepcopy(sampled)}}}

    def verify(self, summary):
        (self.root / "summary.yaml").write_text(yaml.safe_dump(summary))
        return EVAL.verify(self.root)

    def test_complete_disagreeing_samples_are_valid_evidence(self):
        self.verify(self.summary())

    def test_completed_factual_failure_is_not_a_harness_error(self):
        summary = self.summary()
        summary["per_case"]["case-005"]["backport"].update(value=False, stability={
            "samples": 3, "error_count": 0, "values": [False, False, True],
            "pass_count": 1, "stable": False})
        self.verify(summary)

    def test_missing_verdict_or_incomplete_samples_are_errors(self):
        for label, mutation in (
            ("one surviving sample", {"samples": 3, "error_count": 2, "values": [True]}),
            ("too few requested", {"samples": 1, "error_count": 0, "values": [True]}),
            ("missing sample value", {"samples": 3, "error_count": 0, "values": [True, True]}),
            ("nonboolean sample", {"samples": 3, "error_count": 0, "values": [True, 1, False]}),
        ):
            with self.subTest(label=label):
                summary = self.summary()
                summary["per_case"]["case-005"]["backport"]["stability"] = mutation
                with self.assertRaises((ValueError, KeyError)):
                    self.verify(summary)
        for result in ({"value": None, "error": "judge unavailable"}, {}, {"value": "true"}):
            with self.subTest(result=result):
                summary = self.summary()
                summary["per_case"]["case-005"]["backport"] = result
                with self.assertRaises((ValueError, KeyError)):
                    self.verify(summary)
        with self.assertRaises(ValueError):
            self.verify({"per_case": {}})


if __name__ == "__main__":
    unittest.main()
