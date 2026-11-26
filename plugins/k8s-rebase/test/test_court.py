#!/usr/bin/env python3
"""Offline integration checks for court scope and cached review identity."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PLUGIN = Path(__file__).resolve().parents[1]
HARNESS = PLUGIN / "test/test-skill.sh"


@unittest.skipUnless(shutil.which("yq") and shutil.which("jq"), "requires yq and jq")
class CourtHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="k8s-court-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repos/acme/demo"
        self.repo.mkdir(parents=True)
        self.plugin = self.root / "plugin"
        (self.plugin / "gates/step1-rebase").mkdir(parents=True)
        (self.plugin / "test/.matrix-state/run-inputs").mkdir(parents=True)
        (self.plugin / "test/.matrix-state/court").mkdir(parents=True)
        (self.plugin / "gates/step1-rebase/court-fixture.md").write_text("fixture gate\n")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.prompts = self.root / "prompts"
        self.prompts.mkdir()
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}")
        for key in list(self.env):
            if key.startswith(("GIT_", "BASH_FUNC_")):
                del self.env[key]
        self.env.update(
            PLUGIN_DIR=str(self.plugin),
            REPOS_DIR=str(self.root / "repos"),
            CONFIG_FILE=str(self.plugin / "test/config-1.36.yaml"),
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_CONFIG_NOSYSTEM="1",
            COURT_MODEL="claude-sonnet-5-5",
            MAX_COURT_CONCURRENT="1",
            PROMPT_DIR=str(self.prompts),
        )

        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Court Fixture")
        self.git("config", "user.email", "court@example.invalid")
        (self.repo / "base.txt").write_text("base\n")
        self.commit("common base")
        self.common_base = self.sha()

        self.git("switch", "-qc", "known-good", self.common_base)
        (self.repo / "human.txt").write_text("human reference\n")
        self.commit("reference change")
        self.known_good = self.sha()

        self.git("switch", "-qc", "input", self.common_base)
        (self.repo / "input.txt").write_text("pre-existing input change\n")
        self.commit("input commit")
        self.run_base = self.sha()

        self.git("switch", "-qc", "bump1.36", self.run_base)
        (self.repo / "agent.txt").write_text("result change\n")
        self.commit("agent result")
        self.result = self.sha()
        self.git("switch", "-q", "main")

        config = self.plugin / "test/config-1.36.yaml"
        config.write_text(
            "version: 1.36.2\n"
            "max_concurrent: 1\n"
            "repos:\n"
            f"  acme/demo:\n    from_commit: {self.common_base}\n"
            "    known_good: known-good\n"
        )
        # The run's captured base takes precedence over a subsequently changed config.
        inputs = self.plugin / "test/.matrix-state/run-inputs/1.36.2_acme_demo.json"
        inputs.write_text(json.dumps({
            "version": "1.36.2", "repo": "acme/demo", "base_ref": self.run_base,
            "started_at": 1, "spec": "none", "recorded_at": "2026-09-24T00:00:00Z",
            "workflow_verdict": "PASS", "result_ref": self.result,
        }))
        self.state = self.plugin / "test/.matrix-state"

        claude = self.bin / "claude"
        claude.write_text(
            "#!/bin/bash\n"
            'if [[ "${1:-}" == "agents" ]]; then printf "%s\\n" "${AGENT_STATE:-[]}"; exit "${AGENT_EXIT:-0}"; fi\n'
            'if [[ "${1:-}" == "stop" ]]; then echo "$*" >> "$PROMPT_DIR/stops"; exit 0; fi\n'
            'if [[ "${1:-}" == "--bg" ]]; then printf "%s\\n" "$@" > "$PROMPT_DIR/launch-argv"; echo "Session backgrounded 1234abcd"; exit 0; fi\n'
            'mkdir "$PROMPT_DIR/reviewer-active" || { touch "$PROMPT_DIR/concurrent-reviewer"; exit 91; }\n'
            'trap \'rmdir "$PROMPT_DIR/reviewer-active"\' EXIT\n'
            "prompt=$(cat)\n"
            'printf "%s\\n" "$prompt" > "$PROMPT_DIR/prompt-$BASHPID.txt"\n'
            'printf "%s\\n" "$@" > "$PROMPT_DIR/argv-$BASHPID.txt"\n'
            'if [[ "$prompt" == *"You are the PROSECUTION."* ]]; then role=prosecution; '
            'elif [[ "$prompt" == *"You are the DEFENSE."* ]]; then role=defense; '
            'elif [[ "$prompt" == *"Fact-check only."* ]]; then role=judge; else role=juror; fi\n'
            'if [[ "${COURT_RETRY_ALL:-}" == "1" ]]; then '
            'count=$(cat "$PROMPT_DIR/count-$role" 2>/dev/null || echo 0); count=$((count + 1)); '
            'echo "$count" > "$PROMPT_DIR/count-$role"; '
            'limit=1; [[ "$role" == juror ]] && limit=3; [[ "$count" -le "$limit" ]] && exit 0; fi\n'
            '[[ "${COURT_INCONCLUSIVE:-}" == "1" ]] && exit 0\n'
            'padding=$(printf \'%0256d\' 0)\n'
            'if [[ "$prompt" == *"You are the PROSECUTION."* ]]; then printf "PROSECUTION %s\\n" "$padding"; '
            'elif [[ "$prompt" == *"You are the DEFENSE."* ]]; then printf "DEFENSE %s\\n" "$padding"; '
            'elif [[ "$prompt" == *"Fact-check only."* ]]; then printf "FACT CHECK %s\\n" "$padding"; '
            'elif [[ "${COURT_FAIL:-}" == "1" ]]; then printf "VERDICT: FAIL\\nVERIFIED: fixture.txt@fixture\\nEVIDENCE: fixture review %s\\n" "$padding"; '
            'else printf "VERDICT: PASS\\nEVIDENCE: fixture review %s\\n" "$padding"; fi\n'
        )
        claude.chmod(0o755)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              text=True, capture_output=True, env=self.env)

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-qm", message)

    def sha(self):
        return self.git("rev-parse", "HEAD").stdout.strip()

    def harness(self, *args):
        return subprocess.run(["bash", str(HARNESS), *args], cwd=PLUGIN, env=self.env,
                              text=True, capture_output=True, timeout=60)

    def prompt_files(self):
        return sorted(self.prompts.glob("prompt-*.txt"))

    def court_result(self):
        return self.state / "court/1.36.2_acme_demo"

    def completed_workflow(self):
        self.git("switch", "bump1.36")
        scratch = self.repo / ".rebase-tmp"
        (scratch / "gates").mkdir(parents=True)
        (scratch / "branch-name").write_text("bump1.36\n")
        (scratch / "state.json").write_text(json.dumps({
            "current_step": 5, "version": "1.36.2", "repo": str(self.repo),
        }))
        (scratch / "gates/step1-court-fixture.report").write_text(
            f"HEAD: {self.result}\nVERDICT: PASS\n")
        running = self.state / "running"
        running.mkdir(parents=True)
        (running / "1.36.2_acme_demo").write_text("none\t0\tfixture-session\t1.36.2\n")
        return scratch

    def recorded_verdict(self):
        self.harness("results")
        return (self.state / "results.tsv").read_text().splitlines()[-1].split("\t")[4:]

    def cve_workflow(self):
        scratch = self.completed_workflow()
        (scratch / "base-commit").write_text(self.run_base + "\n")
        (self.plugin / "gates/step4-verification").mkdir()
        (self.plugin / "gates/step4-verification/dep-cve-check.md").write_text("gate\n")
        (self.plugin / "scripts").mkdir()
        for name in ("check-cve-evidence.py", "resolve-rebase-base.sh"):
            shutil.copy(PLUGIN / "scripts" / name, self.plugin / "scripts" / name)
        evidence = scratch / "gates/step4-dep-cve-check.evidence"
        evidence.write_text(f"HEAD: {self.result}\nSCAN_HEAD: {self.result}\nBASE: {self.run_base}\n"
                            "COVERAGE: COMPLETE\nEXPECTED_GRAPHS: 2\nCOMPLETED_GRAPHS: 2\n"
                            "EXPECTED_QUERIES: 0\nCOMPLETED_QUERIES: 0\n"
                            "EXPECTED_ADVISORIES: 0\nCOMPLETED_ADVISORIES: 0\n")
        subprocess.run(["bash", str(PLUGIN / "scripts/write-gate-report.sh"), str(self.repo),
                        "step4-dep-cve-check", "PASS", "0", "fixture review"],
                       env=self.env, check=True, capture_output=True)
        # The harness evaluates the result branch even when it is not checked out.
        self.git("switch", "-q", "main")
        return scratch, evidence

    def test_cve_evidence_qualifies_result_branch_without_checkout(self):
        self.cve_workflow()
        self.assertEqual(self.recorded_verdict()[0], "PASS")

    def cache_diff_pass(self, base=None, source="run-input"):
        self.court_result().write_text(json.dumps({
            "verdict": "PASS", "base_ref": base or self.run_base,
            "base_source": source, "result_ref": self.result,
            "known_good_ref": self.known_good, "rubric_version": "court-review-v2",
        }))

    def test_cached_pass_requires_unchanged_live_evidence(self):
        scratch, evidence = self.cve_workflow()
        self.assertEqual(self.recorded_verdict()[0], "PASS")
        self.cache_diff_pass()
        self.assertEqual(self.harness("results").returncode, 0)
        original = evidence.read_bytes()
        for content in (None, original + b"ADVISORY: recollected facts\n"):
            with self.subTest(content=content):
                if content is None:
                    evidence.unlink()
                else:
                    evidence.write_bytes(content)
                result = self.harness("results")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("UNVERIFIED", result.stdout)
                evidence.write_bytes(original)
        report = scratch / "gates/step1-court-fixture.report"
        report.write_text(f"HEAD: {self.result}\nVERDICT: FAIL\n")
        self.assertEqual(self.harness("results").returncode, 1)
        self.assertEqual(self.prompt_files(), [])

    def test_retained_evidence_survives_worktree_cleanup_but_not_archive_changes(self):
        scratch = self.completed_workflow()
        self.git("switch", "main")
        worktree = self.repo / ".claude/worktrees/finished"
        self.git("worktree", "add", str(worktree), "bump1.36")
        shutil.move(str(scratch), worktree / ".rebase-tmp")
        self.assertEqual(self.recorded_verdict()[0], "PASS")
        self.cache_diff_pass()
        self.assertEqual(self.harness("results").returncode, 0)
        self.git("worktree", "remove", "--force", str(worktree))
        self.assertEqual(self.harness("results").returncode, 0)
        record = json.loads((self.state / "run-inputs/1.36.2_acme_demo.json").read_text())
        archive = Path(record["evidence_manifest"]).parent
        report = next(archive.glob("*/.rebase-tmp/gates/*.report"))
        report.unlink()
        self.assertEqual(self.harness("results").returncode, 1)

    def test_cached_pass_binds_completion_state_outside_gate_workspace(self):
        scratch = self.completed_workflow()
        self.git("switch", "main")
        worktree = self.repo / ".claude/worktrees/finished"
        self.git("worktree", "add", str(worktree), "bump1.36")
        result_scratch = worktree / ".rebase-tmp"
        result_scratch.mkdir()
        for name in ("state.json", "branch-name"):
            shutil.move(str(scratch / name), result_scratch / name)
        self.assertEqual(self.recorded_verdict()[0], "PASS")
        self.cache_diff_pass()
        self.assertEqual(self.harness("results").returncode, 0)
        state = result_scratch / "state.json"
        original = state.read_bytes()
        state.write_text(json.dumps({"current_step": 4, "version": "1.36.2"}))
        result = self.harness("results")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("UNVERIFIED", result.stdout)
        state.write_bytes(original)
        (result_scratch / ".session-active").touch()
        self.assertEqual(self.harness("results").returncode, 1)

    def test_new_incomplete_worktree_invalidates_cached_pass_without_gates(self):
        self.completed_workflow()
        self.assertEqual(self.recorded_verdict()[0], "PASS")
        self.cache_diff_pass()
        worktree = self.root / "other-worktree"
        self.git("worktree", "add", "--detach", str(worktree), self.result)
        status = worktree / ".rebase-tmp/status"
        status.mkdir(parents=True)
        (status / "INCOMPLETE").write_text("forced advance\n")
        result = self.harness("results")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("UNVERIFIED", result.stdout)

    def test_next_matrix_version_preserves_archived_completed_result(self):
        scratch = self.completed_workflow()
        self.git("switch", "main")
        finished = self.repo / ".claude/worktrees/k8s-rebase-1.36.2"
        self.git("worktree", "add", str(finished), "bump1.36")
        shutil.move(str(scratch), finished / ".rebase-tmp")
        self.assertEqual(self.recorded_verdict()[0], "PASS")
        self.cache_diff_pass()
        self.git("worktree", "remove", "--force", str(finished))
        self.assertEqual(self.harness("results").returncode, 0)
        next_run = self.repo / ".claude/worktrees/k8s-rebase-1.37.1"
        self.git("worktree", "add", "-b", "bump1.37", str(next_run), self.result)
        next_scratch = next_run / ".rebase-tmp"
        (next_scratch / "gates").mkdir(parents=True)
        (next_scratch / "state.json").write_text(json.dumps({
            "current_step": 4, "version": "1.37.1", "repo": str(next_run),
        }))
        (next_scratch / ".session-active").touch()
        (next_scratch / "gates/step1-court-fixture.report").write_text(
            f"HEAD: {self.result}\nVERDICT: FAIL\n")
        (next_scratch / "status").mkdir()
        (next_scratch / "status/INCOMPLETE").write_text("next version did not complete\n")
        self.assertEqual(self.harness("results").returncode, 1)
        self.next_run_inputs()
        result = self.harness("results")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OVERALL (run + diff review): PASS", result.stdout)

    def next_run_inputs(self):
        path = self.state / "run-inputs/1.37.1_acme_demo.json"
        path.write_text(json.dumps({"version": "1.37.1", "repo": "acme/demo",
                                    "base_ref": self.result, "started_at": 2}))
        return path

    def test_main_checkout_reused_for_next_version_keeps_prior_archived_proof(self):
        scratch = self.completed_workflow()
        self.assertEqual(self.recorded_verdict()[0], "PASS")
        self.cache_diff_pass()
        self.git("switch", "-c", "bump1.37")
        state = scratch / "state.json"
        state.write_text(json.dumps({"current_step": 4, "version": "1.37.1"}))
        (scratch / ".session-active").touch()
        (scratch / "gates/step1-court-fixture.report").write_text("VERDICT: FAIL\n")
        (scratch / "status").mkdir()
        (scratch / "status/INCOMPLETE").write_text("different target incomplete\n")
        self.assertEqual(self.harness("results").returncode, 1)
        next_input = self.next_run_inputs()
        self.assertEqual(self.harness("results").returncode, 0)
        next_record = json.loads(next_input.read_text())
        for field, value in (("repo", "other/repo"), ("version", "1.38.0"),
                             ("base_ref", ""), ("started_at", None),
                             ("started_at", "2"), ("started_at", 1)):
            with self.subTest(field=field, value=value):
                next_input.write_text(json.dumps(dict(next_record, **{field: value})))
                self.assertEqual(self.harness("results").returncode, 1)
        next_input.write_text(json.dumps(next_record))
        # Missing/invalid ownership cannot exempt modified live evidence.
        for version in (None, "", "unknown", "1.36.2"):
            with self.subTest(version=version):
                state.write_text(json.dumps({"current_step": 4, "version": version}))
                self.assertEqual(self.harness("results").returncode, 1)
        state.write_text(json.dumps({"current_step": 4, "version": "1.37.1"}))
        record = json.loads((self.state / "run-inputs/1.36.2_acme_demo.json").read_text())
        archive = Path(record["evidence_manifest"]).parent
        next(archive.glob("*/.rebase-tmp/gates/*.report")).write_text("changed archive\n")
        self.assertEqual(self.harness("results").returncode, 1)

    def test_new_run_cleanup_of_main_scratch_preserves_archived_main_result(self):
        scratch = self.completed_workflow()
        self.assertEqual(self.recorded_verdict()[0], "PASS")
        self.cache_diff_pass()
        # cmd_run removes the entire main scratch before launching a worktree.
        shutil.rmtree(scratch)
        next_run = self.repo / ".claude/worktrees/k8s-rebase-1.37.1"
        self.git("worktree", "add", "-b", "bump1.37", str(next_run), self.result)
        next_scratch = next_run / ".rebase-tmp"
        (next_scratch / "gates").mkdir(parents=True)
        (next_scratch / "state.json").write_text(json.dumps({
            "current_step": 1, "version": "1.37.1", "repo": str(next_run),
        }))
        self.assertEqual(self.harness("results").returncode, 1)
        self.next_run_inputs()
        result = self.harness("results")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # Partial deletion inside a surviving scratch is not cmd_run cleanup.
        scratch.mkdir()
        self.assertEqual(self.harness("results").returncode, 1)

    def test_explicit_diff_scope_must_match_completed_workflow(self):
        self.completed_workflow()
        self.assertEqual(self.recorded_verdict()[0], "PASS")
        self.cache_diff_pass(base=self.common_base, source="explicit")
        result = self.harness("results")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("diagnostic", result.stdout)
        self.cache_diff_pass(source="explicit")
        self.assertEqual(self.harness("results").returncode, 0)
        self.assertEqual(self.prompt_files(), [])

    def test_explicit_live_review_only_qualifies_its_matching_workflow_scope(self):
        self.completed_workflow()
        self.assertEqual(self.recorded_verdict()[0], "PASS")
        for base, flags, expected in ((self.common_base, (), 2),
                                       (self.common_base, ("--diff-only",), 0),
                                       (self.run_base, (), 0)):
            with self.subTest(base=base, flags=flags):
                result = self.harness("results", "acme/demo", "--court", "--from-commit", base, *flags)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                aggregate = self.harness("results")
                self.assertEqual(aggregate.returncode, 0 if base == self.run_base else 1)
        self.assertFalse((self.prompts / "concurrent-reviewer").exists())

    def test_changed_run_base_invalidates_cached_qualification(self):
        self.completed_workflow()
        self.assertEqual(self.recorded_verdict()[0], "PASS")
        inputs = self.state / "run-inputs/1.36.2_acme_demo.json"
        record = json.loads(inputs.read_text())
        record["base_ref"] = self.common_base
        inputs.write_text(json.dumps(record))
        self.cache_diff_pass(base=self.common_base)
        result = self.harness("results")
        self.assertEqual(result.returncode, 1)
        self.assertIn("UNVERIFIED", result.stdout)

    def test_cached_pass_without_retained_evidence_is_unverified(self):
        self.completed_workflow()
        self.assertEqual(self.recorded_verdict()[0], "PASS")
        self.cache_diff_pass()
        inputs = self.state / "run-inputs/1.36.2_acme_demo.json"
        record = json.loads(inputs.read_text())
        del record["evidence_manifest"]
        inputs.write_text(json.dumps(record))
        result = self.harness("results")
        self.assertEqual(result.returncode, 1)
        self.assertIn("UNVERIFIED", result.stdout)

    def test_report_details_do_not_replace_tally_metadata(self):
        scratch, _ = self.cve_workflow()
        report = scratch / "gates/step1-court-fixture.report"
        report.write_text(f"HEAD: {self.result}\nVERDICT: SKIP\nDETAILS:\n"
                          f"HEAD: {self.common_base}\nVERDICT: FAIL\n")
        cve = scratch / "gates/step4-dep-cve-check.report"
        cve.write_text(cve.read_text() + f"HEAD: {self.run_base}\n"
                       "VERDICT: INCONCLUSIVE\nEVIDENCE_SHA256: earlier-digest\n")
        originals = {p: p.read_bytes() for p in (report, cve)}
        self.assertEqual(self.recorded_verdict()[0], "PASS")
        for path, contents in originals.items():
            self.assertEqual(path.read_bytes(), contents)

    def test_duplicate_report_headers_cannot_qualify_completed_run(self):
        scratch = self.completed_workflow()
        report = scratch / "gates/step1-court-fixture.report"
        report.write_text(f"HEAD: {self.result}\n" * 2 +
                          "VERDICT: PASS\nDETAILS:\nQuoted evidence\n")
        self.assertEqual(self.recorded_verdict()[0], "FAIL")

    def test_missing_cve_evidence_cannot_qualify_completed_run(self):
        _, evidence = self.cve_workflow()
        evidence.unlink()
        self.assertEqual(self.recorded_verdict()[0], "FAIL")

    def test_incomplete_cve_evidence_cannot_qualify_completed_run(self):
        _, evidence = self.cve_workflow()
        evidence.write_text(evidence.read_text().replace("COVERAGE: COMPLETE", "COVERAGE: INCOMPLETE"))
        self.assertEqual(self.recorded_verdict()[0], "FAIL")

    def test_changed_cve_evidence_requires_a_new_review(self):
        _, evidence = self.cve_workflow()
        evidence.write_text(evidence.read_text() + "ADVISORY: newly collected facts\n")
        self.assertEqual(self.recorded_verdict()[0], "FAIL")

    def test_corrected_cve_base_cannot_reuse_old_scope_review(self):
        scratch, _ = self.cve_workflow()
        (scratch / "base-commit").write_text(self.common_base + "\n")
        self.assertEqual(self.recorded_verdict()[0], "FAIL")

    def test_live_session_is_not_stopped_when_gates_finish(self):
        scratch = self.completed_workflow()
        (scratch / ".session-active").touch()
        self.env["AGENT_STATE"] = json.dumps([{
            "cwd": str(self.repo), "state": "working", "id": "fixture-session",
        }])
        self.harness("results")
        self.assertFalse((self.prompts / "stops").exists())
        self.assertFalse((self.state / "results.tsv").exists())
        self.assertTrue((self.state / "running/1.36.2_acme_demo").exists())

    def test_dead_session_before_cleanup_cannot_pass(self):
        scratch = self.completed_workflow()
        (scratch / ".session-active").touch()
        self.assertEqual(self.recorded_verdict()[0], "FAIL")

    def test_session_list_errors_do_not_cancel_or_record_live_work(self):
        self.completed_workflow()
        for state, rc in (("[]", "1"), ('{"error":', "0"), ('{"error":"unavailable"}', "0")):
            with self.subTest(state=state, rc=rc):
                self.env.update(AGENT_STATE=state, AGENT_EXIT=rc)
                result = self.harness("results")
                self.assertFalse((self.prompts / "stops").exists(), result.stderr)
                self.assertFalse((self.state / "results.tsv").exists())
                self.assertTrue((self.state / "running/1.36.2_acme_demo").exists())

    def test_ambiguous_session_records_preserve_running_work(self):
        self.completed_workflow()
        records = (
            {"state": "thinking"}, {}, {"state": []},
            {"state": "waiting", "status": "working"},
            {"state": "working", "cwd": ""}, {"id": "", "state": "working"},
        )
        for record in records:
            with self.subTest(record=record):
                self.env["AGENT_STATE"] = json.dumps([
                    dict(cwd=str(self.repo), id="fixture-session") | record])
                self.harness("results")
                self.assertFalse((self.prompts / "stops").exists())
                self.assertFalse((self.state / "results.tsv").exists())
                self.assertTrue((self.state / "running/1.36.2_acme_demo").exists())

    def test_legacy_preliminary_pass_is_rechecked_without_head_change(self):
        scratch = self.completed_workflow()
        (scratch / ".session-active").touch()
        (self.state / "running/1.36.2_acme_demo").unlink()
        done = self.state / "done"
        done.mkdir()
        (done / "1.36.2_none_acme_demo").touch()
        (done / "1.36.2_none_acme_demo.prel").write_text(
            f"fixture-session\t{self.result}\t1.36.2\tnone\tacme_demo\n")
        (self.state / "results.tsv").write_text(
            "2026-09-24T00:00:00Z\t1.36.2\tnone\tacme/demo\tPASS\tpreliminary\n")
        self.assertEqual(self.recorded_verdict()[0], "FAIL")

    def test_live_preliminary_result_cannot_qualify_with_matching_court(self):
        scratch = self.completed_workflow()
        (scratch / ".session-active").touch()
        self.env["AGENT_STATE"] = json.dumps([{
            "cwd": str(self.repo), "state": "working", "id": "fixture-session",
        }])
        (self.state / "results.tsv").write_text(
            "2026-09-24T00:00:00Z\t1.36.2\tnone\tacme/demo\tPASS\tpreliminary\n")
        result = self.harness("results", "acme/demo", "--court")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Workflow run verdict: UNVERIFIED", result.stdout)
        self.assertEqual(self.harness("results").returncode, 1)

    def test_reports_without_completed_state_cannot_pass(self):
        scratch = self.completed_workflow()
        (scratch / "state.json").write_text('{"current_step":4,"version":"1.36.2"}')
        self.assertEqual(self.recorded_verdict()[0], "FAIL")

    def test_completed_workflow_records_pass(self):
        self.completed_workflow()
        self.assertEqual(self.recorded_verdict()[0], "PASS")

    def test_blocking_advisory_gate_failure_is_not_hidden(self):
        scratch = self.completed_workflow()
        (self.plugin / "gates/step4-verification").mkdir()
        (self.plugin / "gates/step4-verification/maintainer-review.md").write_text("gate\n")
        (scratch / "gates/step4-maintainer-review.report").write_text(
            f"HEAD: {self.result}\nVERDICT: FAIL\nDETAILS: unresolved correctness issue\n")
        verdict, detail = self.recorded_verdict()
        self.assertEqual(verdict, "FAIL")
        self.assertIn("step4-maintainer-review", detail)

    def test_missing_advisory_gate_is_not_optional(self):
        self.completed_workflow()
        (self.plugin / "gates/step4-verification").mkdir()
        (self.plugin / "gates/step4-verification/maintainer-review.md").write_text("gate\n")
        self.assertEqual(self.recorded_verdict()[0], "FAIL")

    def test_old_failure_does_not_become_skip_after_commit(self):
        scratch = self.completed_workflow()
        report = scratch / "gates/step1-court-fixture.report"
        report.write_text(f"HEAD: {self.run_base}\nVERDICT: FAIL\n")
        os.utime(report, (1, 1))
        self.assertEqual(self.recorded_verdict()[0], "FAIL")

    def test_malformed_verdict_cannot_pass(self):
        scratch = self.completed_workflow()
        (scratch / "gates/step1-court-fixture.report").write_text(
            f"HEAD: {self.result}\nVERDICT: PASS\nVERDICT: FAIL\n")
        self.assertEqual(self.recorded_verdict()[0], "FAIL")

    def test_extra_report_cannot_fill_missing_gate(self):
        scratch = self.completed_workflow()
        report = scratch / "gates/step1-court-fixture.report"
        report.rename(scratch / "gates/step1-made-up.report")
        self.assertEqual(self.recorded_verdict()[0], "FAIL")

    def test_final_step_pass_requires_result_head(self):
        scratch = self.completed_workflow()
        (self.plugin / "gates/step4-verification").mkdir()
        (self.plugin / "gates/step4-verification/correctness.md").write_text("gate\n")
        (scratch / "gates/step4-correctness.report").write_text(
            f"HEAD: {self.run_base}\nVERDICT: PASS\n")
        self.assertEqual(self.recorded_verdict()[0], "FAIL")

    def test_prior_step_pass_can_be_historical_ancestor(self):
        scratch = self.completed_workflow()
        (scratch / "gates/step1-court-fixture.report").write_text(
            f"HEAD: {self.run_base}\nVERDICT: PASS\n")
        self.assertEqual(self.recorded_verdict()[0], "PASS")

    def test_court_uses_run_base_and_recourts_changed_inputs(self):
        self.completed_workflow()
        self.assertEqual(self.recorded_verdict()[0], "PASS")
        result = self.harness("results", "acme/demo", "--court")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DIFF REVIEW VERDICT: PASS", result.stderr)
        prompt_text = "\n".join(path.read_text() for path in self.prompt_files())
        self.assertIn(f"BASE_REF: {self.run_base} (the exact commit from which this run started)", prompt_text)
        self.assertNotIn(f"BASE_REF: {self.common_base} (the exact commit from which this run started)", prompt_text)

        state = json.loads(self.court_result().read_text())
        self.assertEqual(state["base_ref"], self.run_base)
        self.assertEqual(state["result_ref"], self.result)
        self.assertEqual(state["known_good_ref"], self.known_good)
        self.assertEqual(state["verdict"], "PASS")
        self.assertFalse((self.prompts / "concurrent-reviewer").exists())

        # A matching cached review must not call the model again.
        prompt_count = len(self.prompt_files())
        cached = self.harness("court-all")
        self.assertEqual(cached.returncode, 0, cached.stderr)
        self.assertIn("No pending court reviews.", cached.stdout)
        self.assertEqual(len(self.prompt_files()), prompt_count)

        # A changed result SHA invalidates the cached court vote.
        self.git("switch", "bump1.36")
        (self.repo / "later.txt").write_text("later result change\n")
        self.commit("later result change")
        changed = self.harness("court-all")
        self.assertEqual(changed.returncode, 0, changed.stderr)
        self.assertIn("recorded PASS does not match current run/result; skipping court review", changed.stderr)
        self.assertEqual(len(self.prompt_files()), prompt_count)
        state = json.loads(self.court_result().read_text())
        self.assertEqual(state["result_ref"], self.result)

    def assert_reviewer_tool_contract(self, expected_counts):
        counts = {role: 0 for role in expected_counts}
        for prompt_file in self.prompt_files():
            prompt = prompt_file.read_text()
            argv = (self.prompts / prompt_file.name.replace("prompt-", "argv-")).read_text().splitlines()
            if "You are the PROSECUTION." in prompt:
                role = "prosecution"
            elif "You are the DEFENSE." in prompt:
                role = "defense"
            elif "Fact-check only." in prompt:
                role = "judge"
            else:
                role = "juror"
            counts[role] += 1
            self.assertEqual(argv[argv.index("--permission-mode") + 1], "dontAsk")
            self.assertEqual(argv[argv.index("--setting-sources") + 1], "")
            self.assertNotIn("bypassPermissions", argv)
            tools = argv[argv.index("--tools") + 1]
            if role == "judge":
                self.assertEqual(tools, "")
                self.assertNotIn("--allowedTools", argv)
            else:
                self.assertEqual(set(tools.split(",")), {"Bash", "Read", "Glob", "Grep"})
                allowed = argv[argv.index("--allowedTools") + 1]
                for command in ("show", "diff", "log"):
                    self.assertIn(f"Bash(git --no-pager {command} --no-ext-diff --no-textconv *)", allowed)
                self.assertNotIn("Bash(*)", allowed)
                denied = argv[argv.index("--disallowedTools") + 1]
                for restriction in ("go mod", "go build", "go vet", "go test", "make ",
                                    "rm ", "mv ", "cp ", "touch ", "tee ", "git add", "git switch", "git rebase",
                                    "git push", "git checkout", "git reset", "git commit",
                                    "--output", "--ext-diff", "--textconv", " >", " >>"):
                    self.assertIn(restriction, denied)
                self.assertIn("Do not run module operations, builds, tests", prompt)
            self.assertIn(f"BASE_REF: {self.run_base}", prompt)
            self.assertIn("RESULT_REF: bump1.36", prompt)
        self.assertEqual(counts, expected_counts)

    def test_all_court_roles_have_restricted_tools_even_with_workflow_bypass(self):
        self.completed_workflow()
        self.env["PERMISSION_MODE"] = "bypassPermissions"
        result = self.harness("results", "acme/demo", "--court")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DIFF REVIEW VERDICT: PASS", result.stderr)
        self.assert_reviewer_tool_contract({"prosecution": 1, "defense": 1, "judge": 1, "juror": 3})

    def test_all_court_retries_keep_the_same_role_tool_constraints(self):
        self.completed_workflow()
        self.env.update(PERMISSION_MODE="bypassPermissions", COURT_RETRY_ALL="1")
        result = self.harness("results", "acme/demo", "--court")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DIFF REVIEW VERDICT: PASS", result.stderr)
        for role in ("prosecution", "defense", "judge", "juror-1", "juror-2", "juror-3"):
            self.assertIn(f"Retrying {role}", result.stderr)
        self.assert_reviewer_tool_contract({"prosecution": 2, "defense": 2, "judge": 2, "juror": 6})


    def test_explicit_from_commit_overrides_saved_metadata(self):
        (self.plugin / "test/.matrix-state/run-inputs/1.36.2_acme_demo.json").unlink()
        (self.state / "results.tsv").write_text(
            "2026-09-24T00:00:00Z\t1.36.2\tnone\tacme/demo\tPASS\tfixture complete\n"
        )
        result = self.harness("results", "acme/demo", "--court", "--from-commit", self.common_base)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Workflow run verdict: UNVERIFIED", result.stdout)
        prompt_text = "\n".join(path.read_text() for path in self.prompt_files())
        self.assertIn(f"BASE_REF: {self.common_base} (the exact commit from which this run started)", prompt_text)
        state = json.loads(self.court_result().read_text())
        self.assertEqual(state["base_ref"], self.common_base)
        self.assertEqual(state["base_source"], "explicit")

        (self.state / "results.tsv").write_text(
            f"2026-09-24T00:00:00Z\t1.36.2\tnone\tacme/demo\tPASS\tfixture complete\n"
        )
        shown = self.harness("results")
        self.assertEqual(shown.returncode, 1, shown.stdout + shown.stderr)
        self.assertIn("DIFF REVIEW", shown.stdout)
        self.assertIn("UNVERIFIED", shown.stdout)
        self.assertIn("OVERALL (run + diff review): FAIL", shown.stdout)
        self.assertNotIn("stale", shown.stdout)

    def test_missing_run_base_fails_closed_without_merge_base_guess(self):
        (self.plugin / "test/.matrix-state/run-inputs/1.36.2_acme_demo.json").unlink()
        result = self.harness("results", "acme/demo", "--court")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("exact run starting commit is unavailable", result.stderr)
        self.assertFalse(self.court_result().exists())
        self.assertEqual(self.prompt_files(), [])

    def test_inconclusive_review_replaces_old_cached_pass(self):
        self.court_result().write_text(json.dumps({"verdict": "PASS"}))
        (self.state / "results.tsv").write_text(
            "2026-09-24T00:00:00Z\t1.36.2\tnone\tacme/demo\tPASS\tfixture complete\n"
        )
        env = dict(self.env, COURT_INCONCLUSIVE="1")
        result = subprocess.run(
            ["bash", str(HARNESS), "results", "acme/demo", "--court"],
            cwd=PLUGIN, env=env, text=True, capture_output=True, timeout=60,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        state = json.loads(self.court_result().read_text())
        self.assertEqual(state["verdict"], "INCONCLUSIVE")
        self.assertEqual(state["base_ref"], self.run_base)

    def test_failed_court_propagates_nonzero_status(self):
        (self.state / "results.tsv").write_text(
            "2026-09-24T00:00:00Z\t1.36.2\tnone\tacme/demo\tPASS\tfixture complete\n"
        )
        env = dict(self.env, COURT_FAIL="1")
        result = subprocess.run(
            ["bash", str(HARNESS), "results", "acme/demo", "--court"],
            cwd=PLUGIN, env=env, text=True, capture_output=True, timeout=60,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("DIFF REVIEW VERDICT: FAIL", result.stderr)
        state = json.loads(self.court_result().read_text())
        self.assertEqual(state["verdict"], "FAIL")

    def test_diff_review_pass_does_not_override_failed_workflow(self):
        (self.state / "results.tsv").write_text(
            "2026-09-24T00:00:00Z\t1.36.2\tnone\tacme/demo\tFAIL\tno gates completed\n"
        )
        inputs = self.plugin / "test/.matrix-state/run-inputs/1.36.2_acme_demo.json"
        run = json.loads(inputs.read_text())
        run.update(spec="none", recorded_at="2026-09-24T00:00:00Z",
                   workflow_verdict="FAIL", result_ref=self.result)
        inputs.write_text(json.dumps(run))
        result = self.harness("results", "acme/demo", "--court")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("DIFF REVIEW VERDICT: PASS", result.stderr)
        self.assertIn("Workflow run verdict: FAIL", result.stdout)
        state = json.loads(self.court_result().read_text())
        self.assertEqual(state["verdict"], "PASS")

    def test_diff_only_court_ignores_stale_matrix_workflow_row(self):
        (self.state / "results.tsv").write_text(
            "2026-09-24T00:00:00Z\t1.36.2\tnone\tacme/demo\tFAIL\tprior harness run failed\n"
        )
        result = self.harness("results", "acme/demo", "--court", "--from-commit",
                              self.run_base, "--diff-only")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DIFF REVIEW VERDICT: PASS", result.stderr)
        self.assertIn("Workflow run verdict: NOT INCLUDED (diff-only review", result.stdout)
        self.assertNotIn("Workflow run verdict: FAIL", result.stdout)
        state = json.loads(self.court_result().read_text())
        self.assertEqual(state["verdict"], "PASS")
        self.assertEqual(state["base_ref"], self.run_base)

    def test_unrecorded_run_gets_diagnostic_review_only(self):
        result = self.harness("results", "acme/demo", "--court", "--from-commit", self.run_base)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("DIFF REVIEW VERDICT: PASS", result.stderr)
        self.assertIn("Workflow run verdict: UNRECORDED", result.stdout)
        state = json.loads(self.court_result().read_text())
        self.assertEqual(state["verdict"], "PASS")
        self.assertEqual(state["base_source"], "explicit")

    def test_force_advance_marker_forces_workflow_run_fail(self):
        worktree = self.repo / ".claude/worktrees/rebase-run"
        worktree.parent.mkdir(parents=True)
        self.git("worktree", "add", "-q", "-b", "worktree-k8s-rebase-1.36-test",
                 str(worktree), "bump1.36")
        gates = worktree / ".rebase-tmp/gates"
        gates.mkdir(parents=True)
        (gates / "step1-court-fixture.report").write_text("VERDICT: PASS\n")
        # Claude can keep gate artifacts in a linked worktree while the
        # orchestrator's force-advance marker remains in the main checkout.
        status = self.repo / ".rebase-tmp/status"
        status.mkdir(parents=True)
        (status / "INCOMPLETE").write_text("force advanced\n")
        running = self.state / "running"
        running.mkdir(parents=True)
        (running / "1.36.2_acme_demo").write_text("none\t0\tdead-session\t1.36.2\n")

        result = self.harness("results")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        rows = (self.state / "results.tsv").read_text()
        self.assertIn("\tFAIL\t", rows)
        self.assertIn("force-advance INCOMPLETE marker", rows)

    def test_overall_results_wait_for_required_diff_review(self):
        self.completed_workflow()
        self.assertEqual(self.recorded_verdict()[0], "PASS")
        result = self.harness("results")
        self.assertEqual(result.returncode, 1)
        self.assertIn("pending", result.stdout)
        self.assertIn("OVERALL (run + diff review): FAIL", result.stdout)

    def test_exploration_without_reference_cannot_qualify(self):
        config = Path(self.env["CONFIG_FILE"])
        config.write_text(config.read_text().replace("    known_good: known-good\n", ""))
        self.completed_workflow()
        self.assertEqual(self.recorded_verdict()[0], "PASS")
        result = self.harness("results")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("no reference", result.stdout)
        self.assertIn("known_good not configured", result.stdout)
        self.assertIn("OVERALL (run + diff review): FAIL", result.stdout)
        # An old resolved-ref cache cannot supply a deliberately absent input.
        (self.state / "known_good_resolved_acme_demo_1_36_2").write_text("known-good\n")
        result = self.harness("results", "acme/demo", "--court")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("no known-good reference configured", result.stderr)
        self.assertEqual(self.prompt_files(), [])

    def test_no_runs_cannot_qualify(self):
        result = self.harness("results")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("No results yet", result.stdout)
        self.assertNotIn("OVERALL (run + diff review): PASS", result.stdout)
        self.assertEqual(self.harness("results", "--all-versions").returncode, 1)

    def test_all_versions_propagates_failed_qualification(self):
        self.completed_workflow()
        result = self.harness("results", "--all-versions")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("SUMMARY: 0 of 1 versions PASS", result.stdout)

    def test_old_pass_row_cannot_certify_new_result_commit(self):
        (self.state / "results.tsv").write_text(
            "2026-09-24T00:00:00Z\t1.36.2\tnone\tacme/demo\tPASS\tfixture complete\n"
        )
        self.git("switch", "bump1.36")
        (self.repo / "new-run.txt").write_text("new checkout result\n")
        self.commit("new result without workflow record")

        result = self.harness("results")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("UNVERIFIED", result.stdout)
        self.assertIn("OVERALL (run + diff review): FAIL", result.stdout)

    def test_test_launch_records_exact_checked_out_base(self):
        result = self.harness("test", "none", "acme/demo", "--version", "1.36.2",
                              "--from-commit", self.run_base)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        inputs = json.loads(
            (self.plugin / "test/.matrix-state/run-inputs/1.36.2_acme_demo.json").read_text()
        )
        self.assertEqual(inputs["base_ref"], self.run_base)
        self.assertEqual(inputs["repo"], "acme/demo")
        self.assertGreater(inputs["started_at"], 0)

    def test_launch_honors_config_model_default_and_repo_override(self):
        config = self.plugin / "test/config-1.36.yaml"
        original = config.read_text()
        for default, override, expected in (("default-model", None, "default-model"),
                                             ("default-model", "repo-model", "repo-model"),
                                             (None, None, None)):
            with self.subTest(default=default, override=override):
                text = original
                if default:
                    text = f"model: {default}\n" + text
                if override:
                    text = text.replace("  acme/demo:\n", f"  acme/demo:\n    model: {override}\n")
                config.write_text(text)
                result = self.harness("test", "none", "acme/demo", "--version", "1.36.2",
                                      "--from-commit", self.run_base)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                argv = (self.prompts / "launch-argv").read_text().splitlines()
                if expected:
                    self.assertEqual(argv[argv.index("--model") + 1], expected)
                else:
                    self.assertNotIn("--model", argv)


if __name__ == "__main__":
    unittest.main()
