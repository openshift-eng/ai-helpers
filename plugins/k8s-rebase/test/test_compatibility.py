#!/usr/bin/env python3
"""Offline interface/gate checks. No real reviewer, build, or rebase."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


PLUGIN = Path(__file__).resolve().parents[1]


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="k8s-compatibility-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo with spaces"
        self.repo.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}")
        # Ignore user signing/hooks, Git directories, and shell startup/functions.
        for key in list(self.env):
            if key.startswith(("GIT_", "BASH_FUNC_")):
                del self.env[key]
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                        BASH_ENV="", ENV="")
        self.run_cmd("git", "init", "-q", "-b", "main", check=True)
        self.run_cmd("git", "config", "user.name", "Compatibility Test", check=True)
        self.run_cmd("git", "config", "user.email", "test@example.invalid", check=True)
        (self.repo / "main.go").write_text("package main\n")
        self.commit("base")
        self.base = self.git_sha()
        self.run_cmd("git", "checkout", "-qb", "rebase", check=True)
        (self.repo / "main.go").write_text("package main\n// fix $HOME $(false)\n")
        self.commit("fix")
        self.claude_called = self.root / "claude-called"
        self.env["REVIEW_CAPTURE"] = str(self.claude_called)
        self.stub("claude", 'cat > "$REVIEW_CAPTURE"\nprintf "%s\\n" "${TEST_VERDICT-APPROVE: fixture}"\n'
                  'exit "${TEST_REVIEW_RC:-0}"\n')

    def run_cmd(self, *args, check=False, **kwargs):
        return subprocess.run(args, cwd=self.repo, env=self.env, text=True,
                              capture_output=True, check=check, **kwargs)

    def commit(self, message):
        self.run_cmd("git", "add", ".", check=True)
        self.run_cmd("git", "commit", "-qm", message, check=True)

    def git_sha(self):
        return self.run_cmd("git", "rev-parse", "HEAD", check=True).stdout.strip()

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/bash\n" + body)
        path.chmod(0o755)

    def review(self, scope="fix", *args):
        name = "k8s-rebase-review.sh" if scope == "fix" else "k8s-rebase-pr-review.sh"
        return self.run_cmd("bash", str(PLUGIN / "scripts" / name), *args)

    def portable_mktemp(self):
        # Darwin's mkstemp-based CLI requires trailing Xs, unlike GNU mktemp.
        real_mktemp = shutil.which("mktemp")
        self.stub("mktemp", '[[ "${@: -1}" == *XXXXXX ]] || exit 97\n'
                  f'exec "{real_mktemp}" "$@"\n')

    def test_cve_report_rejects_incomplete_or_stale_collection(self):
        gates = self.repo / ".rebase-tmp/gates"
        gates.mkdir(parents=True)
        evidence = gates / "step4-dep-cve-check.evidence"
        report = gates / "step4-dep-cve-check.report"
        helper = PLUGIN / "scripts/write-gate-report.sh"
        complete = (f"HEAD: {self.git_sha()}\nSCAN_HEAD: {self.git_sha()}\n"
                    f"BASE: {self.base}\n"
                    "COVERAGE: COMPLETE\nEXPECTED_QUERIES: 45\nCOMPLETED_QUERIES: 45\n"
                    "EXPECTED_GRAPHS: 2\nCOMPLETED_GRAPHS: 2\n"
                    "EXPECTED_ADVISORIES: 2\nCOMPLETED_ADVISORIES: 2\n")
        for text in (None, complete.replace('COVERAGE: COMPLETE', 'COVERAGE: INCOMPLETE'),
                     complete.replace('COMPLETED_GRAPHS: 2', 'COMPLETED_GRAPHS: 1'),
                     complete.replace('EXPECTED_GRAPHS: 2\nCOMPLETED_GRAPHS: 2\n', ''),
                     complete.replace('COMPLETED_QUERIES: 45', 'COMPLETED_QUERIES: 7'),
                     complete.replace('COMPLETED_ADVISORIES: 2', 'COMPLETED_ADVISORIES: 1'),
                     complete.replace(self.git_sha(), self.base, 1),
                     complete.replace(f'SCAN_HEAD: {self.git_sha()}', f'SCAN_HEAD: {self.base}'),
                     complete.replace(f'BASE: {self.base}', f'BASE: {self.git_sha()}'),
                     complete + 'COVERAGE: COMPLETE\n'):
            with self.subTest(evidence=text):
                evidence.unlink(missing_ok=True)
                if text is not None:
                    evidence.write_text(text)
                for verdict in ('PASS', 'SKIP'):
                    report.write_text('preserve prior report\n')
                    result = self.run_cmd('bash', str(helper), str(self.repo),
                                          'step4-dep-cve-check', verdict, '0', 'fixture')
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('ERROR:', result.stderr)
                    self.assertEqual(report.read_text(), 'preserve prior report\n')
        for verdict in ('FAIL', 'INCONCLUSIVE'):
            result = self.run_cmd('bash', str(helper), str(self.repo),
                                  'step4-dep-cve-check', verdict, '1', 'missing coverage')
            self.assertEqual(result.returncode, 0, result.stderr)
        evidence.write_text(complete)
        result = self.run_cmd('bash', str(helper), str(self.repo),
                              'step4-dep-cve-check', 'PASS', '0', 'reviewed all findings')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('VERDICT: PASS', report.read_text())

    def test_prompt_scopes_and_no_claude(self):
        fix = self.review("fix", "--print-prompt", "HEAD", "undefined: oldAPI")
        pr = self.review("pr", "--print-prompt", self.base, "1.36.0")
        for result in (fix, pr):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("$HOME $(false)", result.stdout)
        self.assertIn("undefined: oldAPI", fix.stdout)
        self.assertIn("ALL fields", fix.stdout)
        self.assertIn("COMMIT COMPLETENESS", pr.stdout)
        self.assertIn("1.36.0", pr.stdout)
        self.assertIn("fix", pr.stdout)
        self.assertIn(f"REVIEW COMMIT: {self.git_sha()}", fix.stdout)
        self.assertIn(f"REVIEW SCOPE: {self.base}..{self.git_sha()}", pr.stdout)
        self.assertNotIn("COMMIT COMPLETENESS", fix.stdout)
        self.assertFalse(self.claude_called.exists())

    def test_pr_review_includes_draft_literally_and_requires_readable_evidence(self):
        draft = self.repo / ".rebase-tmp/pr body.md"
        draft.parent.mkdir()
        draft.write_text("Verified command: $(touch must-not-execute) `false` $HOME\n")
        prepared = self.review("pr", "--print-prompt", "--verification", str(draft),
                               self.base, "1.37.1")
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        self.assertIn(draft.read_text(), prepared.stdout)
        self.assertIn("VERIFICATION ACCURACY", prepared.stdout)
        self.assertIn(str(self.repo / ".rebase-tmp"), prepared.stdout)
        self.assertIn(str(PLUGIN / "gates"), prepared.stdout)
        self.assertFalse((self.repo / "must-not-execute").exists())
        self.assertFalse(self.claude_called.exists())
        nested = self.review("pr", "--verification", str(draft), self.base, "1.37.1")
        self.assertEqual(nested.returncode, 0, nested.stderr)
        self.assertEqual(prepared.stdout, self.claude_called.read_text())
        for missing in (False, True):
            with self.subTest(missing=missing):
                if missing:
                    draft.unlink()
                else:
                    draft.write_text("")
                self.claude_called.unlink(missing_ok=True)
                for flags in ((), ("--print-prompt",)):
                    result = self.review("pr", *flags, "--verification", str(draft),
                                         self.base, "1.37.1")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("ERROR:", result.stderr)
                    self.assertFalse(self.claude_called.exists())

    def test_pr_review_receives_local_evidence_map_outside_the_body(self):
        draft = self.repo / ".rebase-tmp/pr-body.md"
        draft.parent.mkdir()
        draft.write_text("Unit tests passed at abc123.\n")
        prepared = self.review("pr", "--print-prompt", "--verification", str(draft),
                               self.base, "1.37.1")
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        self.assertNotIn("LOCAL EVIDENCE MAP", prepared.stdout)
        evidence = draft.parent / "pr-evidence.md"
        evidence.write_text("Unit tests: .rebase-tmp/validation-x/output.log exit 0 $(false)\n")
        prepared = self.review("pr", "--print-prompt", "--verification", str(draft),
                               self.base, "1.37.1")
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        body, _, local = prepared.stdout.partition("LOCAL EVIDENCE MAP")
        self.assertIn(draft.read_text(), body)
        self.assertIn(evidence.read_text(), local)
        self.assertNotIn(evidence.read_text(), body)

    def test_nested_pr_review_can_read_criteria_and_retains_failed_attempts(self):
        draft = self.repo / ".rebase-tmp/pr-body.md"
        draft.parent.mkdir()
        draft.write_text("Verification awaiting review.\n")
        argv = self.root / "review-argv"
        self.env["REVIEW_ARGV"] = str(argv)
        self.stub("claude", 'printf "%s\\n" "$@" > "$REVIEW_ARGV"\n'
                  'cat > "$REVIEW_CAPTURE"\n'
                  'echo "fixture transport failure" >&2\n'
                  'echo "partial review; no verdict"\nexit 17\n')
        for _ in range(2):
            result = self.review("pr", "--verification", str(draft), self.base, "1.37.1")
            self.assertEqual(result.returncode, 17)
            self.assertEqual(result.stdout, "partial review; no verdict\n")
        args = argv.read_text().splitlines()
        # Rubrics link to sibling docs (for example the pattern reference),
        # so allowing only gates/ leaves required review inputs inaccessible.
        self.assertEqual(args[args.index("--add-dir") + 1], str(PLUGIN))
        for flag in ("--tools", "--allowedTools"):
            self.assertEqual(set(args[args.index(flag) + 1].split(",")),
                             {"Read", "Glob", "Grep"})
        self.assertIn("--strict-mcp-config", args)
        attempts = list(draft.parent.glob("pr-review-*"))
        self.assertEqual(len(attempts), 2)
        for attempt in attempts:
            self.assertEqual((attempt / "exit-code").read_text(), "17\n")
            self.assertEqual((attempt / "stderr.log").read_text(),
                             "fixture transport failure\n")
            self.assertEqual((attempt / "result.txt").read_text(), result.stdout)
            self.assertEqual((attempt / "prompt.txt").read_text(),
                             self.claude_called.read_text())

    def test_verification_review_stops_when_gate_rubrics_are_missing(self):
        # A relocated helper must not silently review verdicts without criteria.
        helper = self.root / "incomplete plugin/scripts/k8s-rebase-pr-review.sh"
        helper.parent.mkdir(parents=True)
        shutil.copy2(PLUGIN / "scripts/k8s-rebase-pr-review.sh", helper)
        draft = self.repo / "draft.md"
        draft.write_text("Gate results await verification.\n")
        for flags in ((), ("--print-prompt",)):
            with self.subTest(flags=flags):
                result = self.run_cmd("bash", str(helper), *flags, "--verification",
                                      str(draft), self.base, "1.37.1")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Cannot locate gate rubrics", result.stderr)
                self.assertNotIn("VERIFICATION ACCURACY", result.stdout)
                self.assertFalse(self.claude_called.exists())

    def test_cve_scan_example_preserves_full_output_and_producer_failure(self):
        instructions = (PLUGIN / "gates/step4-verification/dep-cve-check.md").read_text()
        example = next(block.split("```", 1)[0] for block in instructions.split("```bash\n")[1:]
                       if "SCAN_LOG=" in block.split("```", 1)[0])
        (self.repo / ".rebase-tmp").mkdir()
        self.env.update(REPO_ROOT=str(self.repo), GOMEMLIMIT="2GiB", GOMAXPROCS="1")
        self.stub("govulncheck", '[[ "$GOMEMLIMIT" == 2GiB && "$GOMAXPROCS" == 1 ]] || exit 99\n'
                  '[[ "$#" == 3 && "$1" == -show && "$2" == verbose && "$3" == ./... ]] || exit 98\n'
                  'for ((i=0; i<5000; i++)); do printf "finding %s\\n" "$i"; done\n'
                  'echo "last diagnostic" >&2\nexit 7\n')
        result = self.run_cmd("bash", "-ec", example)
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertLess(len(result.stdout), 1024)
        logs = list((self.repo / ".rebase-tmp").glob("govulncheck-*.log"))
        self.assertEqual(len(logs), 1)
        output = logs[0].read_text()
        self.assertEqual(output.count("finding "), 5000)
        self.assertTrue(output.endswith("last diagnostic\n\nEXIT_STATUS: 7\n"))
        self.assertIn(str(logs[0]), result.stdout)

    def test_invalid_references_and_missing_arguments(self):
        for scope in ("fix", "pr"):
            context = "context" if scope == "fix" else "1.36.0"
            for args in (("--print-prompt",), ("--print-prompt", "missing", context),
                         ("--print-prompt", "--help", context),
                         ("--print-prompt", "HEAD:main.go", context)):
                with self.subTest(scope=scope, args=args):
                    result = self.review(scope, *args)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("APPROVE:", result.stdout)
        self.assertFalse(self.claude_called.exists())

    def test_evidence_command_failures(self):
        real_git = shutil.which("git")
        for scope, command in (("fix", "show"), ("pr", "diff"), ("pr", "log")):
            with self.subTest(scope=scope, command=command):
                self.stub("git", f'for arg in "$@"; do [[ "$arg" == {command} ]] && exit 17; done\nexec "{real_git}" "$@"\n')
                ref = "HEAD" if scope == "fix" else self.base
                context = "context" if scope == "fix" else "1.36.0"
                result = self.review(scope, "--print-prompt", ref, context)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("APPROVE:", result.stdout)
        self.assertFalse(self.claude_called.exists())

    def test_render_failure(self):
        self.stub("envsubst", "exit 19\n")
        result = self.review("fix", "--print-prompt", "HEAD", "context")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("APPROVE:", result.stdout)
        self.assertFalse(self.claude_called.exists())

    def test_failed_ancestry_check(self):
        real_git = shutil.which("git")
        self.stub("git", f'for arg in "$@"; do [[ "$arg" == --is-ancestor ]] && exit 17; done\nexec "{real_git}" "$@"\n')
        for scope, ref, context in (("fix", "HEAD", "context"), ("pr", self.base, "1.36.0")):
            result = self.review(scope, "--print-prompt", ref, context)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("APPROVE:", result.stdout)
        self.assertFalse(self.claude_called.exists())

    def test_failed_truncation_does_not_prepare_prompt(self):
        self.stub("head", "exit 19\n")
        for scope, ref, context in (("fix", "HEAD", "context"), ("pr", self.base, "1.36.0")):
            result = self.review(scope, "--print-prompt", ref, context)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("APPROVE:", result.stdout)
            self.assertFalse(self.claude_called.exists())

    def test_review_examples_expose_success_and_failure_status(self):
        self.portable_mktemp()
        self.env.update(PLUGIN_ROOT=str(PLUGIN), REPO_ROOT=str(self.repo), VERSION="1.36.0")
        self.activate(step=4)
        (self.repo / ".rebase-tmp/pr-body.md").write_text("Verification remains unverified.\n")
        real_git = shutil.which("git")
        for step in ("step4-verification", "step5-pr"):
            with self.subTest(step=step):
                (self.bin / "git").unlink(missing_ok=True)
                instructions = (PLUGIN / f"skills/k8s-rebase/steps/{step}.md").read_text()
                example = next(block.split("```", 1)[0] for block in instructions.split("```bash\n")[1:]
                               if "--print-prompt" in block.split("```", 1)[0])
                result = self.run_cmd("bash", "-ec", example)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Preparation exit status: 0\n", result.stdout)
                prompt_path = Path(result.stdout.split("Review prompt file: ", 1)[1].strip())
                self.assertEqual(prompt_path.parent, self.repo / ".rebase-tmp")
                self.assertTrue(prompt_path.is_file())
                self.stub("git", f'for arg in "$@"; do [[ "$arg" == show || "$arg" == diff ]] && exit 17; done\nexec "{real_git}" "$@"\n')
                result = self.run_cmd("bash", "-ec", example)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout.strip(), "Preparation exit status: 1")
                self.assertIn("ERROR:", result.stderr)
                self.assertFalse(self.claude_called.exists())

    def test_review_examples_deliver_large_prompts_without_stdout_truncation(self):
        self.portable_mktemp()
        (self.repo / "main.go").write_text("package main\n" + "// " + "x" * 90 + "\n" +
                                          "".join(f"// {i}: " + "x" * 90 + "\n" for i in range(900)) +
                                          "// DELIVERY_END_SENTINEL\n")
        self.commit("large evidence fixture")
        self.activate(step=4)
        draft = self.repo / ".rebase-tmp/pr-body.md"
        draft.write_text("Verification remains unverified.\n")
        self.env.update(PLUGIN_ROOT=str(PLUGIN), REPO_ROOT=str(self.repo), VERSION="1.36.0")
        for step, scope, ref, context in (("step4-verification", "fix", "HEAD", "k8s rebase"),
                                          ("step5-pr", "pr", self.base, "1.36.0")):
            with self.subTest(step=step):
                instructions = (PLUGIN / f"skills/k8s-rebase/steps/{step}.md").read_text()
                example = next(block.split("```", 1)[0] for block in instructions.split("```bash\n")[1:]
                               if "--print-prompt" in block.split("```", 1)[0])
                result = self.run_cmd("bash", "-ec", example)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertLess(len(result.stdout), 2048)
                prompt_path = Path(result.stdout.split("Review prompt file: ", 1)[1].strip())
                prompt = prompt_path.read_text()
                self.assertGreater(len(prompt), 32000)
                self.assertIn("DELIVERY_END_SENTINEL", prompt)
                flags = ("--verification", str(draft)) if scope == "pr" else ()
                self.assertEqual(prompt, self.review(scope, "--print-prompt", *flags, ref, context).stdout)
        self.assertFalse(self.claude_called.exists())

    def test_prompt_allocation_failure_preserves_prior_payload(self):
        self.activate(step=4)
        (self.repo / ".rebase-tmp/pr-body.md").write_text("Verification remains unverified.\n")
        self.env.update(PLUGIN_ROOT=str(PLUGIN), REPO_ROOT=str(self.repo), VERSION="1.36.0")
        for step in ("step4-verification", "step5-pr"):
            with self.subTest(step=step):
                self.portable_mktemp()
                instructions = (PLUGIN / f"skills/k8s-rebase/steps/{step}.md").read_text()
                example = next(block.split("```", 1)[0] for block in instructions.split("```bash\n")[1:]
                               if "--print-prompt" in block.split("```", 1)[0])
                result = self.run_cmd("bash", "-ec", example, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                path = Path(result.stdout.split("Review prompt file: ", 1)[1].strip())
                before = path.read_bytes()
                self.stub("mktemp", "echo 'fixture allocation failure' >&2; exit 19\n")
                result = self.run_cmd("bash", "-ec", example, timeout=5)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn("fixture allocation failure", result.stderr)
                self.assertEqual(path.read_bytes(), before)
                self.assertFalse(self.claude_called.exists())

    def test_eval_known_good_fetch_preserves_requested_commit(self):
        # Exercise only artifact collection, never the runner's reset or model call.
        runner = (PLUGIN / "evals/scripts/run-rebase.sh").read_text()
        fetch = runner.split('if [[ -n "$KNOWN_GOOD_REF" ]]; then', 1)[1].split(
            "# Scope to Bash-only", 1)[0]
        fetch = 'COURT_EXCLUDES=()\nif [[ -n "$KNOWN_GOOD_REF" ]]; then' + fetch
        pinned = self.git_sha()
        self.run_cmd("git", "tag", "known-good", pinned, check=True)
        (self.repo / "later.txt").write_text("not part of the configured comparison\n")
        self.commit("later branch tip")
        tip = self.git_sha()
        self.run_cmd("git", "branch", "bump1.36", tip, check=True)
        remote = self.root / "local remote.git"
        self.run_cmd("git", "clone", "--bare", str(self.repo), str(remote), check=True)
        self.run_cmd("git", "remote", "add", "origin", str(remote), check=True)
        output = self.root / "output"
        output.mkdir()
        self.env.update(REPO_URL=str(remote), FROM_COMMIT=self.base,
                        VERSION="1.36.2", OUTPUT_DIR=str(output))
        real_git = shutil.which("git")
        self.stub("git", 'if [[ "$1" == fetch && "${FAIL_DIRECT:-0}" == 1 && '
                  '"${3:-}" == "$KNOWN_GOOD_REF" ]]; then exit 1; fi\n'
                  f'exec "{real_git}" "$@"\n')
        cases = ((pinned, False, False, pinned), ("known-good", False, False, pinned),
                 ("bump1.36", False, False, tip), (pinned, True, False, pinned),
                 (pinned, False, True, pinned), ("missing-ref", True, False, None),
                 ("", False, False, None))
        for ref, fallback, fork, expected in cases:
            with self.subTest(ref=ref, fallback=fallback, fork=fork):
                self.env.update(KNOWN_GOOD_REF=ref, FAIL_DIRECT=str(int(fallback)),
                                KNOWN_GOOD_URL=remote.as_uri() if fork else "")
                patch = output / "known-good.patch"
                patch.write_text("stale artifact\n")
                result = self.run_cmd("bash", "-euo", "pipefail", "-c", fetch)
                self.assertEqual(result.returncode, 0, result.stderr)
                expected_patch = self.run_cmd("git", "diff", f"{self.base}..{expected}",
                                               check=True).stdout if expected else ""
                self.assertEqual(patch.read_text(), expected_patch)
        self.assertFalse(self.claude_called.exists())

    def test_eval_capture_retains_nested_attempts_and_native_review_files(self):
        scratch = self.repo / ".rebase-tmp"
        inputs = {
            "validation-first/command.txt": "HEAD: original\nEXIT_STATUS: 7\n",
            "validation-first/output.log": "failed build\n",
            "validation-second/command.txt": "HEAD: result\nEXIT_STATUS: 0\n",
            "validation-second/output.log": "passed build\n",
            "pr-review-first/prompt.txt": "prompt\n",
            "pr-review-first/result.txt": "REJECT: incomplete\n",
            "pr-review-first/exit-code": "0\n",
            "pr-review-first/stderr.log": "diagnostic\n",
            "step4-review-native": "fix review prompt\n",
            "step5-review-native": "final review prompt\n",
            "step5-review-native.review.json": "{\"verdict\":\"APPROVE\"}\n",
            "gate-retries/old/step4-check.crash": "timed out\n",
        }
        for name, contents in inputs.items():
            path = scratch / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        output = self.root / "output"
        output.mkdir()
        source = (PLUGIN / "evals/scripts/run-rebase.sh").read_text()
        capture = source.split("capture_diagnostics() {", 1)[1].split('\nREPO_DIR="', 1)[0]
        self.env.update(REPO_DIR=str(self.repo), OUTPUT_DIR=str(output),
                        FROM_COMMIT=self.base, RUN_STARTED_AT="0")
        result = self.run_cmd("bash", "-ec", "capture_diagnostics() {" + capture + "\ncapture_diagnostics\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        retained = output / "script-logs/01-repo with spaces"
        for name, contents in inputs.items():
            self.assertEqual((retained / name).read_text(), contents)

    def test_eval_runner_collects_current_linked_worktree_artifacts(self):
        runner = PLUGIN / "evals/scripts/run-rebase.sh"
        source = self.root / "eval-source"
        source.mkdir()
        env = dict(self.env, PATH=f"{self.bin}:{os.environ['PATH']}")

        def git(repo, *args):
            return subprocess.run(["git", "-C", str(repo), *args], env=env,
                                  text=True, capture_output=True, check=True)

        git(source, "init", "-q", "-b", "main")
        git(source, "config", "user.name", "Eval Fixture")
        git(source, "config", "user.email", "eval@example.invalid")
        (source / "base.txt").write_text("baseline\n")
        git(source, "add", ".")
        git(source, "commit", "-qm", "baseline")
        baseline = git(source, "rev-parse", "HEAD").stdout.strip()
        remote = self.root / "eval-origin.git"
        subprocess.run(["git", "clone", "-q", "--bare", str(source), str(remote)],
                       env=env, check=True)

        repo = self.root / "eval-repo"
        subprocess.run(["git", "clone", "-q", str(remote), str(repo)], env=env, check=True)
        git(repo, "config", "user.name", "Eval Fixture")
        git(repo, "config", "user.email", "eval@example.invalid")
        stale_wt = self.root / "stale-worktree"
        git(repo, "worktree", "add", "-q", "-b", "bump1.36-stale", str(stale_wt), "HEAD")
        stale_marker = stale_wt / ".rebase-tmp/status/INCOMPLETE"
        stale_marker.parent.mkdir(parents=True)
        stale_marker.write_text("stale marker\n")
        stale_branch_file = stale_wt / ".rebase-tmp/branch-name"
        stale_branch_file.write_text("bump1.36-stale\n")
        stale_report = stale_wt / ".rebase-tmp/gates/step1-example.report"
        stale_report.parent.mkdir(parents=True)
        stale_report.write_text("VERDICT: FAIL\n")
        os.utime(stale_branch_file, (1, 1))

        helpers = self.root / "eval-helpers"
        orchestrator = helpers / "plugins/k8s-rebase/scripts/k8s-rebase-orchestrator.sh"
        orchestrator.parent.mkdir(parents=True)
        orchestrator.write_text(
            '#!/bin/bash\nprintf "%s\\n" "$2" > "$STATUS_ROOT_CAPTURE"\necho "DONE: true"\n'
        )
        orchestrator.chmod(0o755)
        live_plugin_script = helpers / "plugins/k8s-rebase/scripts/k8s-rebase.sh"
        live_plugin_script.write_text("original eval plugin source\n")
        current_wt = self.root / "current-worktree"
        result_sha_file = self.root / "result-sha"
        self.stub(
            "claude",
            'plugin_dir=""\n'
            'while [[ $# -gt 0 ]]; do\n'
            '  if [[ "$1" == "--plugin-dir" ]]; then plugin_dir="$2"; shift 2; else shift; fi\n'
            'done\n'
            'printf "%s\\n" "$plugin_dir" > "$PLUGIN_DIR_CAPTURE"\n'
            'echo "eval recovery edit" > "$plugin_dir/scripts/k8s-rebase.sh"\n'
            'repo=$(pwd)\n'
            'if [[ "${FAKE_CLAUDE_ERROR:-false}" == true ]]; then\n'
            '  mkdir -p "$repo/.rebase-tmp"\n'
            '  echo "go mod tidy failed" > "$repo/.rebase-tmp/step1.log"\n'
            '  mkdir -p "$repo/.rebase-tmp/gates"\n'
            '  echo "partial collector facts" > "$repo/.rebase-tmp/gates/step4-example.evidence"\n'
            '  echo "collector crash" > "$repo/.rebase-tmp/gates/step4-example.crash"\n'
            '  echo "interrupted target edit" >> "$repo/base.txt"\n'
            '  printf \'%s\\n\' \'{"type":"result","is_error":true,"terminal_reason":"aborted_streaming","usage":{"input_tokens":1,"output_tokens":2},"total_cost_usd":0.1,"num_turns":1}\'\n'
            '  exit 0\n'
            'fi\n'
            'git -C "$repo" worktree add -q -b bump1.36-current "$CURRENT_WT" HEAD\n'
            'mkdir -p "$CURRENT_WT/.rebase-tmp/status" "$CURRENT_WT/.rebase-tmp/gates"\n'
            'mkdir -p "$repo/.rebase-tmp/status"\n'
            'echo bump1.36-current > "$CURRENT_WT/.rebase-tmp/branch-name"\n'
            'echo "VERDICT: PASS" > "$CURRENT_WT/.rebase-tmp/gates/step1-example.report"\n'
            'echo "full raw gate evidence" > "$CURRENT_WT/.rebase-tmp/gates/step1-example.evidence"\n'
            'echo "collector error" > "$CURRENT_WT/.rebase-tmp/gates/step4-example.crash"\n'
            'echo "incomplete in main" > "$repo/.rebase-tmp/status/INCOMPLETE"\n'
            'echo "from current worktree" > "$CURRENT_WT/from-worktree.txt"\n'
            'git -C "$CURRENT_WT" add from-worktree.txt\n'
            'git -C "$CURRENT_WT" commit -qm "worktree result"\n'
            'echo "post-commit dirty change" >> "$CURRENT_WT/base.txt"\n'
            'echo "step1 run log" > "$CURRENT_WT/.rebase-tmp/step1.log"\n'
            'git -C "$CURRENT_WT" rev-parse HEAD > "$RESULT_SHA_FILE"\n'
            'printf \'{"type":"result","usage":{"input_tokens":1,"output_tokens":1},"total_cost_usd":0.01,"num_turns":1}\\n\'\n'
        )

        run_dir = self.root / "eval-run"
        run_dir.mkdir()
        env.update(
            AI_HELPERS_DIR=str(helpers), EVAL_REPO_DIR=str(repo), CURRENT_WT=str(current_wt),
            RESULT_SHA_FILE=str(result_sha_file), STATUS_ROOT_CAPTURE=str(self.root / "status-root"),
            PLUGIN_DIR_CAPTURE=str(self.root / "plugin-dir-capture"),
        )
        result = subprocess.run(
            ["bash", str(runner), str(remote), baseline, "1.36.2", "fixture-model"],
            cwd=run_dir, env=env, text=True, capture_output=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = run_dir / "output"
        self.assertEqual((output / "gate-reports/step1-example.evidence").read_text(),
                         "full raw gate evidence\n")
        self.assertEqual((output / "gate-reports/step4-example.crash").read_text(),
                         "collector error\n")
        inputs = json.loads((output / "run-input.json").read_text())
        self.assertEqual(inputs["from_commit"], baseline)
        self.assertEqual(inputs["result_ref"], result_sha_file.read_text().strip())
        self.assertIn("from-worktree.txt", (output / "files-changed.txt").read_text())
        self.assertIn("base.txt", (output / "files-changed-working-tree.txt").read_text())
        self.assertIn("post-commit dirty change", (output / "working-tree.patch").read_text())
        script_logs = list((output / "script-logs").glob("*/step1.log"))
        self.assertEqual(len(script_logs), 1)
        self.assertEqual(script_logs[0].read_text(), "step1 run log\n")
        self.assertEqual((output / "gate-reports/step1-example.report").read_text(), "VERDICT: PASS\n")
        force_log = (output / "force-advance.log").read_text()
        self.assertIn("incomplete in main", force_log)
        self.assertNotIn("stale marker", force_log)
        self.assertEqual(Path((self.root / "status-root").read_text().strip()), current_wt)
        plugin_dir = Path((self.root / "plugin-dir-capture").read_text().strip())
        self.assertNotEqual(plugin_dir, live_plugin_script.parent.parent)
        self.assertEqual(live_plugin_script.read_text(), "original eval plugin source\n")

        error_repo = self.root / "eval-repo-error"
        subprocess.run(["git", "clone", "-q", str(remote), str(error_repo)], env=env, check=True)
        git(error_repo, "config", "user.name", "Eval Fixture")
        git(error_repo, "config", "user.email", "eval@example.invalid")
        error_run_dir = self.root / "eval-run-error"
        error_run_dir.mkdir()
        error_env = dict(
            env, EVAL_REPO_DIR=str(error_repo), FAKE_CLAUDE_ERROR="true",
        )
        error_result = subprocess.run(
            ["bash", str(runner), str(remote), baseline, "1.36.2", "fixture-model"],
            cwd=error_run_dir, env=error_env, text=True, capture_output=True, timeout=60,
        )
        self.assertNotEqual(error_result.returncode, 0)
        error_output = error_run_dir / "output"
        status = json.loads((error_output / "run-status.json").read_text())
        self.assertEqual(status["status"], "infra_error")
        self.assertIn("interruption", status["reason"])
        self.assertTrue((error_output / "session-output.json").exists())
        self.assertIn("go mod tidy failed",
                      (error_output / "script-logs/01-eval-repo-error/step1.log").read_text())
        self.assertIn("interrupted target edit",
                      (error_output / "working-tree.patch").read_text())
        self.assertEqual((error_output / "script-logs/01-eval-repo-error/gates/step4-example.evidence").read_text(),
                         "partial collector facts\n")
        self.assertEqual((error_output / "script-logs/01-eval-repo-error/gates/step4-example.crash").read_text(),
                         "collector crash\n")
        self.assertIn("01-eval-repo-error/base.txt",
                      (error_output / "files-changed-working-tree.txt").read_text())

    def lint_baseline_fixture(self):
        (self.repo / "main.go").write_text("package main\n// unrelated saved work\n")
        self.run_cmd("git", "stash", "push", "-qm", "unrelated work", check=True)
        self.activate(step=4)
        (self.repo / ".rebase-tmp/lint-results.txt").write_text("active lint failure\n")
        hook = self.repo / ".git/hooks/pre-push"
        hook.write_text("#!/bin/sh\nexit 1 # active push guard\n")
        hook.chmod(0o755)
        scratch = self.root / "baseline comparisons"
        scratch.mkdir()
        self.env.update(REPO_ROOT=str(self.repo), PLUGIN_ROOT=str(PLUGIN), TMPDIR=str(scratch))
        instructions = (PLUGIN / "skills/k8s-rebase/steps/step4-verification.md").read_text()
        example = next(block.split("```", 1)[0] for block in instructions.split("```bash\n")[1:]
                       if "LINT_BASE=" in block.split("```", 1)[0])
        return example, scratch

    def repo_snapshot(self):
        # Includes index, refs/reflogs (and stash), hooks, active reports and files.
        return {p.relative_to(self.repo): (p.read_bytes(), p.stat().st_mode)
                for p in self.repo.rglob("*") if p.is_file()}

    def test_lint_baseline_example_isolates_checkout_and_stash(self):
        example, scratch = self.lint_baseline_fixture()
        for dirty in (False, True):
            if dirty:
                (self.repo / "main.go").write_text("package main\n// staged work\n")
                self.run_cmd("git", "add", "main.go", check=True)
                (self.repo / "main.go").write_text("package main\n// unstaged work\n")
                (self.repo / "untracked.txt").write_text("unrelated new file\n")
            for branch in ("main", "master"):
                if branch == "master":
                    self.run_cmd("git", "branch", "-m", "main", "master", check=True)
                with self.subTest(dirty=dirty, branch=branch):
                    before = self.repo_snapshot()
                    result = self.run_cmd("bash", "-euo", "pipefail", "-c", example)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(self.repo_snapshot(), before)
                    values = dict(line.split(": ", 1) for line in result.stdout.splitlines())
                    self.assertEqual(values["LINT_BASE"], self.base)
                    clone = Path(values["LINT_BASE_REPO"])
                    self.assertTrue(clone.is_relative_to(scratch))
                    self.assertFalse(clone.is_relative_to(self.repo))
                    self.assertEqual(self.run_cmd("git", "-C", str(clone), "rev-parse", "HEAD",
                                                  check=True).stdout.strip(), self.base)
                    self.assertNotEqual(self.run_cmd("git", "-C", str(clone), "symbolic-ref",
                                                     "-q", "HEAD").returncode, 0)
                    self.assertEqual((clone / "main.go").read_text(), "package main\n")
                    self.assertEqual(self.run_cmd("git", "-C", str(clone), "stash", "list",
                                                  check=True).stdout, "")
                    self.assertTrue((clone / ".git").is_dir())
                    self.assertFalse((clone / ".git/objects/info/alternates").exists())
                    self.assertFalse((clone / ".git/hooks/pre-push").exists())
                    self.assertFalse((clone / ".rebase-tmp").exists())
                    (clone / "main.go").write_text("comparison-only change\n")
                    (clone / ".git/hooks/pre-push").write_text("clone-only hook\n")
                    self.assertEqual(self.repo_snapshot(), before)
                if branch == "master":
                    self.run_cmd("git", "branch", "-m", "master", "main", check=True)

    def test_lint_baseline_example_missing_base_stops(self):
        example, scratch = self.lint_baseline_fixture()
        self.run_cmd("git", "branch", "-D", "main", check=True)
        before = self.repo_snapshot()
        result = self.run_cmd("bash", "-c", example)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot resolve lint baseline", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(list(scratch.iterdir()), [])
        self.assertEqual(self.repo_snapshot(), before)

    def test_lint_baseline_example_setup_failures_stop(self):
        example, _ = self.lint_baseline_fixture()
        real_git = shutil.which("git")
        before = self.repo_snapshot()
        for command in ("clone", "checkout"):
            for flags in (("-c",), ("-euo", "pipefail", "-c")):
                with self.subTest(command=command, flags=flags):
                    self.stub("git", f'for arg in "$@"; do [[ "$arg" == {command} ]] && exit 17; done\nexec "{real_git}" "$@"\n')
                    result = self.run_cmd("bash", *flags, example)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(self.repo_snapshot(), before)

    def test_pre_pr_evidence_uses_snapshot_if_head_moves(self):
        reviewed = self.git_sha()
        real_git = shutil.which("git")
        self.stub("git", f'''if [[ "$1" == diff ]]; then
  "{real_git}" commit --allow-empty -qm "later commit" || exit 1
fi
exec "{real_git}" "$@"
''')
        result = self.review("pr", "--print-prompt", self.base, "1.36.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(reviewed, self.git_sha())
        self.assertIn(f"REVIEW SCOPE: {self.base}..{reviewed}", result.stdout)
        self.assertNotIn("later commit", result.stdout)
        self.assertFalse(self.claude_called.exists())

    def test_missing_or_non_regular_template(self):
        for kind in ("missing", "directory"):
            copied = self.root / f"script copy {kind}"
            copied.mkdir()
            script = shutil.copy(PLUGIN / "scripts/k8s-rebase-review.sh", copied)
            shutil.copy(PLUGIN / "scripts/resolve-rebase-base.sh", copied)
            if kind == "directory":
                (copied / "k8s-rebase-review-prompt.md").mkdir()
            for print_prompt in (True, False):
                with self.subTest(kind=kind, print_prompt=print_prompt):
                    args = ("--print-prompt",) if print_prompt else ()
                    result = self.run_cmd("bash", script, *args, "HEAD", "context")
                    if print_prompt:
                        self.assertEqual(result.returncode, 1, result.stderr)
                        self.assertEqual(result.stdout, "")
                        self.assertIn("ERROR:", result.stderr)
                    else:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn("APPROVE: template not found, skipping", result.stdout)
                    self.assertFalse(self.claude_called.exists())

    def test_template_disappears_during_collection(self):
        copied = self.root / "script copy"
        copied.mkdir()
        script = shutil.copy(PLUGIN / "scripts/k8s-rebase-review.sh", copied)
        shutil.copy(PLUGIN / "scripts/resolve-rebase-base.sh", copied)
        template = copied / "k8s-rebase-review-prompt.md"
        self.env["REVIEW_TEMPLATE"] = str(template)
        real_git = shutil.which("git")
        self.stub("git", f'''for arg in "$@"; do
  if [[ "$arg" == show ]]; then
    mv -- "$REVIEW_TEMPLATE" "$REVIEW_TEMPLATE.removed" || exit 1
  fi
done
exec "{real_git}" "$@"
''')
        for print_prompt in (True, False):
            with self.subTest(print_prompt=print_prompt):
                shutil.copy(PLUGIN / "scripts/k8s-rebase-review-prompt.md", template)
                args = ("--print-prompt",) if print_prompt else ()
                result = self.run_cmd("bash", script, *args, "HEAD", "context")
                self.assertFalse(template.exists())
                self.assertTrue(Path(f"{template}.removed").is_file())
                if print_prompt:
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("ERROR:", result.stderr)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("APPROVE: template not found, skipping", result.stdout)
                self.assertFalse(self.claude_called.exists())

    def test_empty_filtered_diff_is_valid(self):
        self.run_cmd("git", "checkout", "-qb", "empty-filter", self.base, check=True)
        (self.repo / "docs.md").write_text("documentation only\n")
        self.commit("docs only")
        fix = self.review("fix", "--print-prompt", "HEAD", "context")
        pr = self.review("pr", "--print-prompt", "HEAD", "1.36.0")
        self.assertEqual(fix.returncode, 0, fix.stderr)
        self.assertEqual(pr.returncode, 0, pr.stderr)
        self.assertFalse(self.claude_called.exists())

    def test_fix_review_excludes_root_and_nested_vendor(self):
        for path, text in {
            "vendor/root.go": "// root vendor noise\n" * 2400,
            "nested module/vendor/nested.go": "// nested vendor noise\n" * 2400,
            "nested module/owned.go": "package owned\n// owned nested review marker\n",
            "go.mod": "module fixture\nrequire k8s.io/api v0.37.1\n",
            "nested module/go.mod": "module nested\nrequire k8s.io/apimachinery v0.37.1\n",
        }.items():
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        self.commit("dependency and owned source review fixture")
        prepared = self.review("fix", "--print-prompt", "HEAD", "review scope regression")
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        self.assertNotIn("diff --git a/vendor/", prepared.stdout)
        self.assertNotIn("diff --git a/nested module/vendor/", prepared.stdout)
        self.assertNotIn("diff was truncated", prepared.stdout)
        self.assertIn("owned nested review marker", prepared.stdout)
        self.assertIn("+require k8s.io/api v0.37.1", prepared.stdout)
        self.assertIn("+require k8s.io/apimachinery v0.37.1", prepared.stdout)
        nested = self.review("fix", "HEAD", "review scope regression")
        self.assertEqual(nested.returncode, 0, nested.stderr)
        self.assertIn("APPROVE:", nested.stdout)
        self.assertEqual(self.claude_called.read_text(), prepared.stdout.split("\n\n", 1)[1])

    def test_truncation_disclosed(self):
        (self.repo / "large.go").write_text("// large\n" * 2400)
        (self.repo / "large.md").write_text("documentation\n" * 20000)
        self.commit("large diff")
        for scope, ref in (("fix", "HEAD"), ("pr", self.base)):
            context = "context" if scope == "fix" else "1.36.0"
            result = self.review(scope, "--print-prompt", ref, context)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("truncated", result.stdout)

    def test_claude_default_verdicts(self):
        for verdict, model_rc, expected in (("APPROVE: fixture", 0, 0), ("REJECT: fixture", 0, 1),
                                            ("malformed", 0, 0), ("", 17, 0),
                                            ("REJECT: fixture", 17, 1)):
            with self.subTest(verdict=verdict, model_rc=model_rc):
                self.claude_called.unlink(missing_ok=True)
                self.env["TEST_VERDICT"] = verdict
                self.env["TEST_REVIEW_RC"] = str(model_rc)
                result = self.review("fix", "HEAD", "context")
                self.assertEqual(result.returncode, expected, result.stderr)
                expected_verdict = verdict if verdict.startswith(("APPROVE:", "REJECT:")) else "APPROVE: no verdict"
                self.assertIn(expected_verdict, result.stdout)
                self.assertTrue(self.claude_called.exists())
        self.env["TEST_REVIEW_RC"] = "0"
        result = self.review("pr", self.base, "1.36.0")
        self.assertEqual(result.returncode, 0)
        self.assertIn("COMMIT COMPLETENESS", self.claude_called.read_text())

    def test_claude_render_failure_keeps_legacy_behavior(self):
        self.stub("envsubst", "exit 19\n")
        result = self.review("fix", "HEAD", "context")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("APPROVE: fixture", result.stdout)
        self.assertEqual(self.claude_called.read_text(), "\n")

    def test_claude_timeout_keeps_legacy_fallback(self):
        self.stub("timeout", "exit 124\n")
        result = self.review("fix", "HEAD", "context")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("APPROVE: no verdict", result.stdout)
        self.assertFalse(self.claude_called.exists())

    def test_missing_claude_keeps_legacy_fallback_and_allows_preparation(self):
        # Restrict this subprocess's PATH, never remove or invoke an installed CLI.
        isolated_bin = self.root / "no reviewer bin"
        isolated_bin.mkdir()
        for tool in ("bash", "dirname", "git", "envsubst", "head", "wc", "grep"):
            path = shutil.which(tool)
            self.assertIsNotNone(path, tool)
            (isolated_bin / tool).symlink_to(path)
        self.env["PATH"] = str(isolated_bin)
        prepared = self.review("fix", "--print-prompt", "HEAD", "context")
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        self.assertIn("REVIEW COMMIT:", prepared.stdout)
        result = self.review("fix", "HEAD", "context")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("APPROVE: claude CLI not available", result.stdout)
        self.assertFalse(self.claude_called.exists())

    def activate(self, step=3):
        state = self.repo / ".rebase-tmp"
        state.mkdir(exist_ok=True)
        (state / ".session-active").touch()
        (state / "state.json").write_text(json.dumps({"current_step": step, "version": "1.36.0"}))

    def hook(self, name, tool_input, tool_name="Bash", **extra):
        payload = {"cwd": str(self.repo), "tool_name": tool_name,
                   "tool_input": tool_input, **extra}
        result = self.run_cmd("bash", str(PLUGIN / "hooks" / name), input=json.dumps(payload))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def test_vendor_payloads(self):
        self.activate()
        for header in ("Add File", "Update File", "Delete File", "Move to"):
            for path in ("vendor/a.go", "module/vendor/a.go", "\tvendor/a.go", "ven\tdor/a.go",
                         str(self.repo / "vendor/a.go")):
                with self.subTest(header=header, path=path):
                    patch = f"*** Begin Patch\n*** Update File: safe.go\n*** {header}: {path}\n*** End Patch\n"
                    result = self.hook("block-vendor-edit.sh", {"command": patch}, "apply_patch")
                    self.assertEqual(result.get("decision"), "block")
        self.assertEqual(self.hook("block-vendor-edit.sh", {"file_path": "vendor/a.go"}, "Edit").get("decision"), "block")
        self.assertFalse(self.hook("block-vendor-edit.sh", {"command": "*** Update File: main.go\n+// vendor/a.go"}, "apply_patch"))
        self.assertFalse(self.hook("block-vendor-edit.sh", {"command": "*** Add File:   vendor/a.go\n+package fixture"}, "apply_patch"))
        (self.repo / ".rebase-tmp/.session-active").unlink()
        self.assertFalse(self.hook("block-vendor-edit.sh", {"command": "*** Delete File: vendor/a.go"}, "apply_patch"))

    def test_existing_shell_hooks_and_guards(self):
        self.activate()
        cases = (("block-push.sh", "git push origin HEAD"),
                 ("block-push.sh", "gh pr create --title test"),
                 ("block-module-ops.sh", "go mod tidy"),
                 ("block-prior-step-rm.sh", "rm .rebase-tmp/gates/step2-build-vet.report"))
        for name, command in cases:
            self.assertEqual(self.hook(name, {"command": command}).get("decision"), "block")
        # Codex hook cwd stays at the session root during module-local work.
        self.assertEqual(self.hook("block-module-ops.sh", {"command": "cd module && go mod tidy"}).get("decision"), "block")
        (self.repo / ".rebase-tmp/.session-active").unlink()
        for name, command in cases:
            self.assertFalse(self.hook(name, {"command": command}))

    def test_module_hook_allows_verified_report_literals(self):
        self.activate()
        helper = PLUGIN / "scripts/write-gate-report.sh"
        commands = (
            f'bash "{helper}" "{self.repo}" step4-maintainer-review PASS 0 '
            '"Scope correct" "INFO: produced by go mod tidy; go get was not run"',
            f'PLUGIN_ROOT="{PLUGIN}"; [ "$(git rev-parse HEAD)" = fixture ] && '
            'bash "$PLUGIN_ROOT/scripts/write-gate-report.sh" "$PWD" '
            'step4-maintainer-review PASS 0 "Scope correct" \\\n'
            '"Body describes go get/tidy; produced by go mod tidy" && ls .rebase-tmp/gates/',
            f'P="{PLUGIN}" && bash "${{P}}/scripts/write-gate-report.sh" "$PWD" '
            "step4-maintainer-review PASS 0 'go generate was not run' 'go run was not run'",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertFalse(self.hook("block-module-ops.sh", {"command": command}))

    def test_module_hook_report_exemption_keeps_operations_blocked(self):
        self.activate()
        helper = PLUGIN / "scripts/write-gate-report.sh"
        report = f'bash "{helper}" "$PWD" step4-maintainer-review PASS 0 '
        commands = (
            report + '"produced by go mod tidy"; go mod tidy',
            'go get example.invalid/module; ' + report + '"produced by go mod tidy"',
            report + '"$(go mod tidy)"',
            report + '"`go get example.invalid/module`"',
            report + '"Scope correct" "$(go generate ./...)"',
            'bash -c "go mod tidy"',
            'go "mod" tidy',
            'bash /other/plugin/scripts/write-gate-report.sh "$PWD" '
            'step4-maintainer-review PASS 0 "produced by go mod tidy"',
            'bash "$UNKNOWN/scripts/write-gate-report.sh" "$PWD" '
            'step4-maintainer-review PASS 0 "produced by go mod tidy"',
            report + '"unterminated go mod tidy',
            'echo $#; go mod tidy',
            'echo ${value#prefix}; go mod tidy',
            'echo foo#bar; go mod tidy',
            f'P="{PLUGIN}"; bash \'$P/scripts/write-gate-report.sh\' "$PWD" '
            'step4-maintainer-review PASS 0 "go mod tidy"',
            f'P="{PLUGIN}"; P="$UNKNOWN"; '
            'bash "$P/scripts/write-gate-report.sh" "$PWD" '
            'step4-maintainer-review PASS 0 "go mod tidy"',
            f'P="{PLUGIN}"; unset P; '
            'bash "$P/scripts/write-gate-report.sh" "$PWD" '
            'step4-maintainer-review PASS 0 "go mod tidy"',
            f'P="{PLUGIN}" | bash "$P/scripts/write-gate-report.sh" "$PWD" '
            'step4-maintainer-review PASS 0 "go mod tidy"',
            f'P="{PLUGIN}" & bash "$P/scripts/write-gate-report.sh" "$PWD" '
            'step4-maintainer-review PASS 0 "go mod tidy"',
            f'(P="{PLUGIN}"); bash "$P/scripts/write-gate-report.sh" "$PWD" '
            'step4-maintainer-review PASS 0 "go mod tidy"',
            f'false && P="{PLUGIN}"; '
            'bash "$P/scripts/write-gate-report.sh" "$PWD" '
            'step4-maintainer-review PASS 0 "go mod tidy"',
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(self.hook("block-module-ops.sh", {"command": command}).get("decision"), "block")

    def test_depfix_sync_runs_only_module_synchronization(self):
        calls = self.root / "go-calls"
        self.env["GO_CALLS"] = str(calls)
        self.stub("go", 'printf "%s\\n" "$*" >> "$GO_CALLS"\n')
        depfix = str(PLUGIN / "scripts/k8s-rebase-depfix.sh")
        (self.repo / "vendor").mkdir()
        for args, expected in ((["--sync"], "mod tidy\nmod vendor\n"),
                               (["example.com/dep@v1.2.3"], "get example.com/dep@v1.2.3\nmod tidy\nmod vendor\n")):
            with self.subTest(args=args):
                calls.unlink(missing_ok=True)
                self.assertEqual(self.run_cmd("bash", depfix, *args).returncode, 0)
                self.assertEqual(calls.read_text(), expected)
        calls.unlink()
        for args in ([], ["--sync", "extra"], ["--unknown"]):
            with self.subTest(args=args):
                self.assertEqual(self.run_cmd("bash", depfix, *args).returncode, 1)
        self.assertFalse(calls.exists())
        # The hook exempts whole-command script invocations, including module-local ones.
        self.activate()
        for command in (f"bash {depfix} --sync", f'cd module && bash "{depfix}" --sync'):
            self.assertFalse(self.hook("block-module-ops.sh", {"command": command}))

    def test_stop_hook(self):
        self.assertFalse(self.hook("stop-hook.sh", {}))
        self.activate()
        self.assertEqual(self.hook("stop-hook.sh", {}).get("decision"), "block")
        self.assertFalse(self.hook("stop-hook.sh", {}, stop_hook_active=True))
        self.activate(step=5)
        self.assertFalse(self.hook("stop-hook.sh", {}))

    def test_push_guard_distinguishes_hook_filenames_from_publishing(self):
        self.activate(step=5)
        blocked = ("git push origin HEAD", "git -c key=val push --dry-run",
                   'git -C "repo path" "push" origin HEAD', "git 'push'",
                   "git-push origin HEAD", "git send-pack origin HEAD",
                   "git status; git push", "git status && git push",
                   "git status\ngit push", 'bash -c "git push origin HEAD"',
                   "gh pr create --title test", "gh api repos/org/repo/pulls -X POST",
                   "gh api -XPOST repos/org/repo/pulls", "gh api --method=PATCH repos/org/repo/pulls/4",
                   "gh api repos/org/repo/pulls -f title=example", "gh api repos/org/repo/pulls -F draft=true",
                   "gh api repos/org/repo/pulls --raw-field=title=example", "gh api repos/org/repo/pulls --input body.json",
                   "gh api repos/org/repo/pulls --method '$METHOD'", "gh api repos/org/repo/pulls -X",
                   "gh api \\\n repos/org/repo/pulls \\\n -X POST",
                   "gh api repos/org/repo/pulls/4\ngh api repos/org/repo/pulls -f title=fixture",
                   "gh api repos/org/repo/pulls/4; gh api repos/org/repo/pulls -X POST")
        allowed = ('git status; cat "$HOOK_DIR/pre-push"',
                   'gh api "repos/org/repo/pulls/4" --jq \'{head: .head.sha, base: .base.sha}\'',
                   "gh api repos/org/repo/pulls --paginate", "gh api -X GET repos/org/repo/pulls/4/files",
                   "gh api --method=GET repos/org/repo/pulls -f state=open",
                   "gh api repos/org/repo/pulls/4 --method HEAD",
                   "gh api \\\n repos/org/repo/pulls/4 \\\n --jq '.head.sha'",
                   'git rev-parse --git-common-dir; mv pre-push.bak.k8s-rebase pre-push')
        for command in blocked:
            with self.subTest(command=command):
                self.assertEqual(self.hook("block-push.sh", {"command": command}).get("decision"), "block")
        cleanup = self.cleanup_example()
        # Inspect both renderings without executing either command.
        flattened = cleanup.replace("\\\n", " ").replace("\n", "; ")
        for command in (*allowed, cleanup, flattened):
            with self.subTest(command=command):
                self.assertFalse(self.hook("block-push.sh", {"command": command}))
                self.assertEqual(self.hook("block-push.sh", {"command": command + "\ngit push"}).get("decision"), "block")
        (self.repo / ".rebase-tmp/.session-active").unlink()
        for command in blocked:
            self.assertFalse(self.hook("block-push.sh", {"command": command}))

    def test_stop_hook_blocks_exit_while_step1_runs_and_names_the_pid(self):
        self.activate(step=1)
        state = self.repo / ".rebase-tmp"
        child = subprocess.Popen(["bash", "-c", "read -r completion"],
                                 cwd=self.repo, env=self.env,
                                 stdin=subprocess.PIPE, text=True)
        try:
            (state / "step1.pid").write_text(str(child.pid))
            for _ in range(2):
                blocked = self.hook("stop-hook.sh", {})
                self.assertEqual(blocked.get("decision"), "block")
                self.assertIn(f"tail --pid={child.pid}", blocked["reason"])
                self.assertIn("Do not end your turn", blocked["reason"])
                # The early result marker must not end the wait.
                (state / "step1-result.txt").write_text("EXIT 2\n")
            # The hook yields once it has already blocked this stop.
            self.assertFalse(self.hook("stop-hook.sh", {}, stop_hook_active=True))
            # A retained PID must not exempt later steps (including PID reuse).
            self.activate(step=2)
            self.assertEqual(self.hook("stop-hook.sh", {}).get("decision"), "block")
            self.activate(step=1)
        finally:
            child.communicate("done\n", timeout=5)
        self.assertEqual(self.hook("stop-hook.sh", {}).get("decision"), "block")
        for pid in ("0", "-1", "not-a-pid"):
            (state / "step1.pid").write_text(pid)
            self.assertEqual(self.hook("stop-hook.sh", {}).get("decision"), "block")

    def test_stop_hook_does_not_exempt_exited_unreaped_child(self):
        self.activate(step=1)
        state = self.repo / ".rebase-tmp"
        child = subprocess.Popen(["bash", "-c", "exit 2"], cwd=self.repo, env=self.env)
        try:
            # Do not poll()/wait() yet: retain the exited child as a zombie.
            for _ in range(100):
                status = self.run_cmd("ps", "-p", str(child.pid), "-o", "stat=").stdout.strip()
                if status.startswith("Z"):
                    break
                time.sleep(0.01)
            else:
                self.fail("fixture child did not enter zombie state")
            (state / "step1.pid").write_text(str(child.pid))
            (state / "step1-result.txt").write_text("EXIT 2\n")
            self.assertEqual(self.hook("stop-hook.sh", {}).get("decision"), "block")
        finally:
            child.wait(timeout=5)

    def test_parallel_test_only_preserves_summary_and_separate_logs(self):
        self.portable_mktemp()
        (self.repo / "go.mod").write_text("module example.invalid/fixture\n\ngo 1.23.0\n")
        self.commit("fixture module")
        self.env.pop("K8S_REBASE_IN_CONTAINER", None)
        self.stub("go", 'case "$1" in\n'
                  '  env) echo go1.99.0 ;;\n'
                  '  test) echo "$*"; [[ "$*" != *./bad* ]] ;;\n'
                  '  build|vet) exit 0 ;;\n'
                  '  *) echo "Unexpected Go invocation" >&2; exit 97 ;;\n'
                  'esac\n')
        self.activate(step=4)
        summary = self.repo / ".rebase-tmp/summary.txt"
        summary.write_text("## LINT ERRORS\nretained finding\n")
        original = summary.read_bytes()
        script = str(PLUGIN / "scripts/k8s-rebase-validate.sh")
        processes = [subprocess.Popen(["bash", "-c", f'umask {mask}; exec bash "$@"',
                                      "validator", script, "--test-only", pkg],
                                     cwd=self.repo, env=self.env, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for pkg, mask in (("./good", "022"), ("./bad", "077"))]
        try:
            for process, expected in zip(processes, (0, 1)):
                stdout, stderr = process.communicate(timeout=10)
                self.assertEqual(process.returncode, expected, stdout + stderr)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.communicate()
        self.assertEqual(summary.read_bytes(), original)
        logs = list(summary.parent.glob("test-only-*"))
        self.assertEqual(len(logs), 2)
        self.assertEqual(sum("./good" in p.read_text() for p in logs), 1)
        self.assertEqual(sum("./bad" in p.read_text() for p in logs), 1)
        for log in logs:
            expected_mode = 0o644 if "./good" in log.read_text() else 0o600
            self.assertEqual(log.stat().st_mode & 0o777, expected_mode)
        # Full validation still replaces its own summary rather than retaining stale errors.
        result = self.run_cmd("bash", script, "--quick", timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(summary.read_text(), "")
        self.assertEqual(self.run_cmd("git", "diff", "HEAD", check=True).stdout, "")

    def test_normal_validation_keeps_log_names_for_test_only_prefixed_modules(self):
        module = self.repo / "test-only-module"
        module.mkdir()
        (module / "go.mod").write_text("module example.invalid/fixture\n\ngo 1.23.0\n")
        self.commit("fixture module")
        self.env.pop("K8S_REBASE_IN_CONTAINER", None)
        self.stub("go", 'case "$1" in\n'
                  '  env) echo go1.99.0 ;;\n'
                  '  build) echo "main.go:1:1: undefined: removedAPI"; exit 1 ;;\n'
                  '  vet) exit 0 ;;\n'
                  '  *) exit 97 ;;\n'
                  'esac\n')
        result = self.run_cmd("bash", str(PLUGIN / "scripts/k8s-rebase-validate.sh"),
                              "--quick", timeout=10)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        state = self.repo / ".rebase-tmp"
        self.assertTrue((state / "test-only-module-build.log").is_file())
        self.assertIn("undefined: removedAPI", (state / "summary.txt").read_text())

    def test_test_log_setup_failure_stops_before_test(self):
        self.activate(step=4)
        self.env.pop("K8S_REBASE_IN_CONTAINER", None)
        (self.repo / "go.mod").write_text("module example.invalid/fixture\n\ngo 1.23.0\n")
        summary = self.repo / ".rebase-tmp/summary.txt"
        summary.write_text("retained validation\n")
        self.env["GO_TEST_CAPTURE"] = str(self.root / "go-test-called")
        self.stub("go", 'case "$1" in env) echo go1.99.0 ;; '
                  'test) touch "$GO_TEST_CAPTURE"; exit 97 ;; *) exit 97 ;; esac\n')
        for tool in ("mktemp", "chmod"):
            with self.subTest(tool=tool):
                self.stub(tool, "echo 'fixture log setup failure' >&2; exit 19\n")
                result = self.run_cmd("bash", str(PLUGIN / "scripts/k8s-rebase-validate.sh"),
                                      "--test-only", "./...", timeout=5)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("fixture log setup failure", result.stderr)
                self.assertFalse((self.root / "go-test-called").exists())
                self.assertEqual(summary.read_text(), "retained validation\n")
                (self.bin / tool).unlink()

    def version_evidence(self, modules, target="v0.36.2"):
        self.activate(step=2)
        self.env.update(GOPROXY="off", GOSUMDB="off", GOFLAGS="", GOWORK="off",
                        GOTOOLCHAIN="local")
        state = self.repo / ".rebase-tmp"
        target_file = state / "target-k8s-api-version.txt"
        if target is None:
            target_file.unlink(missing_ok=True)
        else:
            target_file.write_text(target + "\n")
        for name, requires in modules.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            # A future Go version must not trigger a toolchain download for parsing.
            path.write_text("module example.invalid/fixture\ngo 1.99.0\n" + requires)
        before = {p: p.read_bytes() for p in self.repo.rglob("go.mod")}
        result = self.run_cmd("bash", str(PLUGIN / "gates/step2-compilation/version-consistency.sh"),
                              str(self.repo), timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual({p: p.read_bytes() for p in self.repo.rglob("go.mod")}, before)
        self.assertFalse(list(self.repo.rglob("go.sum")))
        self.assertFalse((state / "gates/step2-version-consistency.report").exists())
        return (state / "gates/step2-version-consistency.evidence").read_text()

    def test_version_evidence_exempts_independent_modules_not_kubernetes(self):
        modules = {"go.mod": "require (\n k8s.io/api v0.36.2\n"
                   " k8s.io/klog v1.0.0\n k8s.io/klog/v2 v2.140.0\n"
                   " k8s.io/utils v0.0.0-20260101000000-000000000000\n"
                   " k8s.io/kube-openapi v0.0.0-20260101000000-000000000000\n"
                   " k8s.io/gengo v0.0.0-20260101000000-000000000000\n"
                   " k8s.io/gengo/v2 v2.0.0\n sigs.k8s.io/yaml v1.6.0\n)\n",
                   "nested module/go.mod": "require k8s.io/kubernetes v1.36.2\n"}
        self.assertIn("SUMMARY: 0 version inconsistencies", self.version_evidence(modules))
        modules["nested module/go.mod"] = "require k8s.io/kubernetes v1.35.2\n"
        evidence = self.version_evidence(modules)
        self.assertIn("SUMMARY: 1 version inconsistencies", evidence)
        self.assertIn("k8s.io/kubernetes at v1.35.2, expected v1.36.2", evidence)

    def test_version_evidence_checks_requires_not_excludes_or_replacements(self):
        modules = {"go.mod": "require k8s.io/api v0.35.2\nexclude (\n"
                   " k8s.io/apimachinery v0.34.0\n)\nreplace (\n"
                   " k8s.io/client-go => k8s.io/client-go v0.33.0\n)\n",
                   "nested module/go.mod": "require (\n k8s.io/apimachinery v0.36.1\n"
                   " k8s.io/klog-extra v0.35.2\n k8s.io/api v0.36.2-alpha.1\n)\n",
                   "vendor/ignored/go.mod": "require k8s.io/api v0.34.0\n"}
        # Avoid network/cache verification: only this existing vendor check is stubbed.
        real_go = shutil.which("go")
        self.stub("go", '[[ "$*" == "mod verify" ]] && { echo "all modules verified"; exit 0; }\n'
                  f'exec "{real_go}" "$@"\n')
        evidence = self.version_evidence(modules)
        self.assertIn("SUMMARY: 4 version inconsistencies", evidence)
        self.assertIn("k8s.io/api at v0.35.2, expected v0.36.2", evidence)
        self.assertIn("k8s.io/apimachinery at v0.36.1, expected v0.36.2", evidence)
        self.assertIn("k8s.io/klog-extra at v0.35.2, expected v0.36.2", evidence)
        self.assertIn("k8s.io/api at v0.36.2-alpha.1, expected v0.36.2", evidence)
        self.assertNotIn("v0.34.0", evidence)
        self.assertNotIn("v0.33.0", evidence)

    def test_version_evidence_never_claims_zero_after_incomplete_comparison(self):
        for target in (None, "", "v1.36.2", "garbage"):
            with self.subTest(target=target):
                evidence = self.version_evidence({"go.mod": "require k8s.io/api v0.36.2\n"}, target)
                self.assertIn("NO_TARGET:", evidence)
                self.assertNotIn("SUMMARY: 0 ", evidence)
        (self.repo / "go.mod").unlink()
        self.assertIn("CHECK_ERROR: no go.mod", self.version_evidence({}))
        evidence = self.version_evidence({"go.mod": "require (\n"})
        self.assertIn("CHECK_ERROR: cannot read requirements", evidence)
        self.assertNotIn("SUMMARY: 0 ", evidence)
        for tool in ("go", "jq"):
            with self.subTest(tool=tool):
                self.stub(tool, "exit 19\n")
                evidence = self.version_evidence({"go.mod": "require k8s.io/api v0.36.2\n"})
                self.assertIn("CHECK_ERROR: cannot read requirements", evidence)
                self.assertNotIn("SUMMARY: 0 ", evidence)
                (self.bin / tool).unlink()

    def cleanup_example(self):
        instructions = (PLUGIN / "skills/k8s-rebase/steps/step5-pr.md").read_text()
        return next(block.split("```", 1)[0] for block in instructions.split("```bash\n")[1:]
                    if "HOOK_DIR=" in block.split("```", 1)[0])

    def test_cleanup_removes_scratch_and_preserves_reports_and_original_hook(self):
        self.activate(step=5)
        state = self.repo / ".rebase-tmp"
        retained = {"state.json": (state / "state.json").read_text(),
                    "gates/step4-review.report": "VERDICT: FAIL\n",
                    "status/INCOMPLETE": "unresolved fixture\n",
                    "base-commit": self.git_sha() + "\n",
                    "test-only-fixture": "actual test output\n",
                    "root-build.log": "actual build output\n",
                    "step4-review-2.log": "APPROVE: reviewed final commit\n",
                    "step4-review-fixture": "selected-commit review prompt\n",
                    "step5-review-fixture": "full-rebase review prompt\n",
                    "summary.txt": "actual validation summary\n",
                    "unrelated.fixture": "keep\n"}
        for name, body in retained.items():
            path = state / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(body)
        scratch = [state / "step4.pid", state / "worker.pid", state / "crd-pre-codegen"]
        for path in scratch[:2]:
            path.write_text("12345\n")
        scratch[2].mkdir()
        (scratch[2] / "generated.yaml").write_text("scratch snapshot\n")
        hook = self.repo / ".git/hooks/pre-push"
        hook.write_text("#!/bin/sh\nexit 1 # k8s-rebase guard\n")
        backup = hook.with_name("pre-push.bak.k8s-rebase")
        backup.write_text("#!/bin/sh\nexit 0 # original hook\n")
        backup.chmod(0o755)
        original = (backup.read_bytes(), backup.stat().st_mode)
        result = self.run_cmd("bash", "-c", self.cleanup_example())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(path.exists() for path in scratch))
        self.assertFalse((state / ".session-active").exists())
        for name, body in retained.items():
            self.assertEqual((state / name).read_text(), body)
        self.assertEqual((hook.read_bytes(), hook.stat().st_mode), original)
        self.assertFalse(backup.exists())

    def test_cleanup_failures_preserve_session_and_recovery_artifacts(self):
        self.activate(step=5)
        state = self.repo / ".rebase-tmp"
        (state / "step1.log").write_text("retained diagnostic\n")
        hook = self.repo / ".git/hooks/pre-push"
        backup = hook.with_name("pre-push.bak.k8s-rebase")
        for tool in ("git", "cat", "mv", "rm"):
            with self.subTest(tool=tool):
                hook.write_text("#!/bin/sh\nexit 1 # k8s-rebase guard\n")
                backup.write_text("#!/bin/sh\nexit 0 # original hook\n")
                backup.chmod(0o751)
                self.stub(tool, "exit 19\n")
                result = self.run_cmd("bash", "-c", self.cleanup_example())
                (self.bin / tool).unlink()
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue((state / ".session-active").exists())
                self.assertEqual((state / "step1.log").read_text(), "retained diagnostic\n")
                if tool != "rm":
                    self.assertIn("k8s-rebase guard", hook.read_text())
                    self.assertTrue(backup.exists())
                else:
                    self.assertIn("original hook", hook.read_text())
                    self.assertEqual(hook.stat().st_mode & 0o777, 0o751)

    @unittest.skipUnless(shutil.which("zsh"), "zsh is not installed")
    def test_cleanup_from_zsh_handles_unmatched_globs_and_preserves_evidence(self):
        self.activate(step=5)
        state = self.repo / ".rebase-tmp"
        (state / "gates").mkdir()
        report = state / "gates/step4-check.report"
        report.write_text(f"HEAD: {self.git_sha()}\nVERDICT: PASS\n")
        for name in ("root-build.log", "go-get.log", "summary.txt"):
            (state / name).write_text("verification evidence\n")
        # There are deliberately no step*.pid or test-only-* matches.
        result = self.run_cmd("zsh", "-f", "-c", self.cleanup_example())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("no matches found", result.stderr)
        self.assertFalse((state / ".session-active").exists())
        for name in ("root-build.log", "go-get.log", "summary.txt"):
            self.assertEqual((state / name).read_text(), "verification evidence\n")
        self.assertTrue(report.exists())
        self.assertTrue((state / "state.json").exists())

    def test_cleanup_without_backup_preserves_unrelated_hook(self):
        hook = self.repo / ".git/hooks/pre-push"
        for contents in ("#!/bin/sh\nexit 1 # k8s-rebase guard\n",
                         "#!/bin/sh\nexit 0 # unrelated user hook\n"):
            with self.subTest(contents=contents):
                self.activate(step=5)
                hook.write_text(contents)
                hook.chmod(0o751)
                result = self.run_cmd("bash", "-c", self.cleanup_example())
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse((self.repo / ".rebase-tmp/.session-active").exists())
                if "k8s-rebase" in contents:
                    self.assertFalse(hook.exists())
                else:
                    self.assertEqual(hook.read_text(), contents)
                    self.assertEqual(hook.stat().st_mode & 0o777, 0o751)

    def isolated_orchestrator(self):
        # Isolate actual orchestrator from expensive real companions.
        isolated = self.root / "plugin"
        (isolated / "scripts").mkdir(parents=True)
        orch = isolated / "scripts/k8s-rebase-orchestrator.sh"
        shutil.copy(PLUGIN / "scripts/k8s-rebase-orchestrator.sh", orch)
        shutil.copy(PLUGIN / "scripts/check-cve-evidence.py", isolated / "scripts")
        shutil.copy(PLUGIN / "scripts/resolve-rebase-base.sh", isolated / "scripts")
        for name in ("step1-rebase", "step2-compilation", "step3-autofix", "step4-verification"):
            directory = isolated / "gates" / name
            directory.mkdir(parents=True)
            (directory / "check.md").write_text("fixture gate\n")

        def run(action, *args):
            return self.run_cmd("bash", str(orch), action, str(self.repo), *args)

        return run

    def test_build_vet_evidence_retains_silent_failure_and_killed_command_output(self):
        self.isolated_orchestrator()
        helpers = self.root / "plugin/scripts"
        shutil.copy(PLUGIN / "scripts/gate-script-lib.sh", helpers)
        companion = self.root / "plugin/gates/step2-compilation/build-vet.sh"
        shutil.copy(PLUGIN / "gates/step2-compilation/build-vet.sh", companion)
        scratch = self.repo / ".rebase-tmp"
        scratch.mkdir()
        (scratch / "base-commit").write_text(self.base + "\n")
        (self.repo / "go.mod").write_text("module example.invalid/fixture\n")
        for phase, code in (("build", 17), ("build", 124), ("vet", 137)):
            with self.subTest(phase=phase, code=code):
                self.env.update(FAIL_PHASE=phase, FAIL_EXIT=str(code))
                self.stub("go", 'if [[ "$1" == "$FAIL_PHASE" ]]; then\n'
                          '  [[ "$FAIL_EXIT" -lt 124 ]] || echo "partial output before kill"\n'
                          '  exit "$FAIL_EXIT"\nfi\n')
                result = self.run_cmd("bash", str(companion), str(self.repo))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                evidence = (scratch / "gates/step2-build-vet.evidence").read_text()
                self.assertIn(f"RESULT .: {phase}={code}", evidence)
                if code >= 124:
                    self.assertIn("SUMMARY: INCOMPLETE", evidence)
                    self.assertIn("partial output before kill", evidence)
                    self.assertIn("NOT_RUN:", evidence)
                else:
                    self.assertIn("1 failed commands", evidence)
                self.assertFalse((scratch / "gates/step2-build-vet.report").exists())

    def test_retry_gate_retains_failed_attempt_and_restarts_only_current_collector(self):
        run = self.isolated_orchestrator()
        self.activate(step=4)
        gates = self.repo / ".rebase-tmp/gates"
        gates.mkdir()
        originals = {"report": "VERDICT: INCONCLUSIVE\n", "crash": "CRASH: timed out\n",
                     "evidence": "partial evidence\n"}
        for suffix, contents in originals.items():
            (gates / f"step4-check.{suffix}").write_text(contents)
        prior = gates / "step3-check.report"
        prior.write_text("prior-step review\n")
        companion = self.root / "plugin/gates/step4-verification/check.sh"
        companion.write_text('#!/bin/bash\necho collected >> "$1/.rebase-tmp/collector-calls"\n'
                             'echo replacement > "$1/.rebase-tmp/gates/step4-check.evidence"\n')
        companion.chmod(0o755)
        self.assertIn("previously crashed", run("gates").stdout)
        self.assertFalse((self.repo / ".rebase-tmp/collector-calls").exists())
        self.assertEqual(run("retry-gate", "../step3-autofix/check").returncode, 2)
        retry = run("retry-gate", "check")
        self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
        archive = next((self.repo / ".rebase-tmp/gate-retries").iterdir())
        for suffix, contents in originals.items():
            self.assertEqual((archive / f"step4-check.{suffix}").read_text(), contents)
        self.assertFalse((gates / "step4-check.report").exists())
        self.assertFalse((gates / "step4-check.crash").exists())
        self.assertFalse((gates / "step4-check.evidence").exists())
        self.assertEqual(prior.read_text(), "prior-step review\n")
        run("gates")
        self.assertEqual((self.repo / ".rebase-tmp/collector-calls").read_text(), "collected\n")
        self.assertEqual((gates / "step4-check.evidence").read_text(), "replacement\n")
        self.assertEqual((archive / "step4-check.evidence").read_text(), originals["evidence"])

    def test_failed_cve_retry_cannot_reuse_old_complete_scan(self):
        run = self.isolated_orchestrator()
        self.activate(step=4)
        gate_dir = self.root / "plugin/gates/step4-verification"
        (gate_dir / "check.md").rename(gate_dir / "dep-cve-check.md")
        gates = self.repo / ".rebase-tmp/gates"
        gates.mkdir()
        evidence = gates / "step4-dep-cve-check.evidence"
        complete = (f"HEAD: {self.git_sha()}\nSCAN_HEAD: {self.git_sha()}\nBASE: {self.base}\n"
                    "COVERAGE: COMPLETE\nEXPECTED_GRAPHS: 2\nCOMPLETED_GRAPHS: 2\n"
                    "EXPECTED_QUERIES: 0\nCOMPLETED_QUERIES: 0\n"
                    "EXPECTED_ADVISORIES: 0\nCOMPLETED_ADVISORIES: 0\n")
        evidence.write_text(complete)
        writer = PLUGIN / "scripts/write-gate-report.sh"
        self.run_cmd("bash", str(writer), str(self.repo), "step4-dep-cve-check",
                     "INCONCLUSIVE", "1", "recollect current advisory facts", check=True)
        retry = run("retry-gate", "dep-cve-check")
        self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
        archive = next((self.repo / ".rebase-tmp/gate-retries").iterdir())
        self.assertEqual((archive / evidence.name).read_text(), complete)
        self.assertFalse(evidence.exists())
        companion = gate_dir / "dep-cve-check.sh"
        companion.write_text("#!/bin/bash\nexit 124\n")
        companion.chmod(0o755)
        failed = run("gates")
        self.assertEqual(failed.returncode, 1)
        self.assertIn("companion crashed", failed.stdout)
        for verdict in ("PASS", "SKIP"):
            result = self.run_cmd("bash", str(writer), str(self.repo), "step4-dep-cve-check",
                                  verdict, "0", "cannot accept previous scan")
            self.assertNotEqual(result.returncode, 0)
        self.assertFalse((gates / "step4-dep-cve-check.report").exists())
        self.assertEqual(run("retry-gate", "dep-cve-check").returncode, 0)
        fresh = complete + "ADVISORY: freshly collected facts\n"
        (self.repo / "fresh-evidence").write_text(fresh)
        companion.write_text('#!/bin/bash\ncp "$1/fresh-evidence" '
                             '"$1/.rebase-tmp/gates/step4-dep-cve-check.evidence"\n')
        self.assertEqual(run("gates").returncode, 1)
        self.assertEqual(evidence.read_text(), fresh)
        self.run_cmd("bash", str(writer), str(self.repo), "step4-dep-cve-check",
                     "PASS", "0", "reviewed replacement scan", check=True)
        self.assertEqual(run("gates").returncode, 0)
        self.assertEqual((archive / evidence.name).read_text(), complete)

    def test_cve_cache_requires_review_of_exact_current_evidence(self):
        run = self.isolated_orchestrator()
        self.activate(step=4)
        gate_dir = self.root / "plugin/gates/step4-verification"
        (gate_dir / "check.md").rename(gate_dir / "dep-cve-check.md")
        gates = self.repo / ".rebase-tmp/gates"
        gates.mkdir()
        evidence = gates / "step4-dep-cve-check.evidence"
        report = gates / "step4-dep-cve-check.report"
        complete = (f"HEAD: {self.git_sha()}\nSCAN_HEAD: {self.git_sha()}\nCOVERAGE: COMPLETE\n"
                    f"BASE: {self.base}\n"
                    "EXPECTED_GRAPHS: 2\nCOMPLETED_GRAPHS: 2\n"
                    "EXPECTED_QUERIES: 2\nCOMPLETED_QUERIES: 2\n"
                    "EXPECTED_ADVISORIES: 0\nCOMPLETED_ADVISORIES: 0\n")
        evidence.write_text(complete.replace("EXPECTED_GRAPHS: 2\nCOMPLETED_GRAPHS: 2\n", ""))
        # Legacy writer accepted this same-HEAD report without graph evidence.
        report.write_text(f"HEAD: {self.git_sha()}\nVERDICT: PASS\n")
        for collected in (False, True):
            if collected:
                evidence.write_text(complete)
            result = run("gates")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("PENDING: dep-cve-check", result.stdout)
            self.assertIn("STALE final-step", run("reports").stdout)
        writer = PLUGIN / "scripts/write-gate-report.sh"
        self.run_cmd("bash", str(writer), str(self.repo), "step4-dep-cve-check",
                     "PASS", "0", "reviewed current facts",
                     "Quoted metadata from an earlier report:",
                     f"HEAD: {self.base}", "VERDICT: FAIL",
                     "EVIDENCE_SHA256: earlier-digest", check=True)
        self.assertEqual(run("gates").returncode, 0)
        self.assertIn("FRESHNESS: current HEAD", run("reports").stdout)
        # Valid coverage and HEAD still match, but a new advisory body needs review.
        evidence.write_text(complete + "ADVISORY: new facts\n")
        self.assertEqual(run("gates").returncode, 1)
        self.assertEqual(run("advance").returncode, 1)
        self.assertIn("STALE final-step", run("reports").stdout)
        evidence.write_text(complete)
        # A corrected starting commit changes scope without changing HEAD.
        (self.repo / ".rebase-tmp/base-commit").write_text(self.git_sha() + "\n")
        self.assertEqual(run("gates").returncode, 1)
        result = self.run_cmd("bash", str(writer), str(self.repo), "step4-dep-cve-check",
                              "PASS", "0", "wrong base scope")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BASE", result.stderr)

    def test_large_gate_evidence_survives_bounded_output(self):
        self.isolated_orchestrator()
        self.activate(step=4)
        plugin = self.root / "plugin"
        shutil.copy(PLUGIN / "scripts/gate-script-lib.sh", plugin / "scripts")
        payload = "advisory detail " + "x" * 100 + "\n"
        payload *= 10000
        (self.repo / "payload.txt").write_text(payload)
        companion = plugin / "gates/step4-verification/check.sh"
        companion.write_text(
            '#!/bin/bash\n'
            'source "$(dirname "$0")/../../scripts/gate-script-lib.sh"\n'
            'init_gate "$@"\n'
            'finish_evidence "large fixture" "$(cat "$REPO/payload.txt")"\n')
        companion.chmod(0o755)
        result = self.run_cmd(
            "bash", "-o", "pipefail", "-c",
            'bash "$1" gates "$2" 4 2>&1 | head -80', "fixture",
            str(plugin / "scripts/k8s-rebase-orchestrator.sh"), str(self.repo))
        evidence = self.repo / ".rebase-tmp/gates/step4-check.evidence"
        self.assertTrue(evidence.exists(), result.stdout + result.stderr)
        self.assertEqual(evidence.read_text(),
                         f"HEAD: {self.git_sha()}\nSUMMARY: large fixture\n" + payload)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("PENDING: check", result.stdout)
        self.assertLess(len(result.stdout), 2000)
        self.assertFalse(evidence.with_suffix(".crash").exists())
        self.assertFalse(evidence.with_suffix(".evidence.tmp").exists())

    def test_report_details_do_not_replace_header_metadata(self):
        run = self.isolated_orchestrator()
        writer = PLUGIN / "scripts/write-gate-report.sh"
        state = self.repo / ".rebase-tmp"
        cases = (
            # The cloud-controller trial repeated this line in its details.
            ("PASS", f"HEAD: {self.git_sha()} (verified)"),
            ("PASS", f"HEAD: {self.base}\nVERDICT: FAIL"),
            ("SKIP", "HEAD: unknown\nVERDICT: INCONCLUSIVE"),
            ("FAIL", f"HEAD: {self.git_sha()}\nVERDICT: PASS"),
            ("INCONCLUSIVE", "VERDICT: SKIP"),
        )
        for verdict, details in cases:
            with self.subTest(verdict=verdict, details=details):
                self.activate(step=2)
                (state / ".advance-attempts-step2").unlink(missing_ok=True)
                self.run_cmd("bash", str(writer), str(self.repo), "step2-check",
                             verdict, "0" if verdict in ("PASS", "SKIP") else "1",
                             "reviewed current source", "Quoted evidence:", details,
                             check=True)
                report = state / "gates/step2-check.report"
                original = report.read_bytes()

                result = run("gates")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(f"EXISTING: check {verdict}", result.stdout)
                inventory = run("reports")
                self.assertEqual(inventory.returncode, 0, inventory.stderr)
                self.assertIn(f"| `step2-check.report` | {verdict} | current | "
                              f"`{self.git_sha()[:12]}` |", inventory.stdout)

                result = run("advance")
                passed = verdict in ("PASS", "SKIP")
                self.assertEqual(result.returncode, 0 if passed else 1,
                                 result.stdout + result.stderr)
                current_step = json.loads((state / "state.json").read_text())["current_step"]
                self.assertEqual(current_step, 3 if passed else 2)
                self.assertFalse((state / "status/INCOMPLETE").exists())
                self.assertEqual(report.read_bytes(), original)

    def test_fresh_pass_and_skip_advance_without_retries(self):
        run = self.isolated_orchestrator()
        self.activate(step=2)
        state = self.repo / ".rebase-tmp"
        writer = PLUGIN / "scripts/write-gate-report.sh"
        for step, verdict in ((2, "PASS"), (3, "SKIP")):
            with self.subTest(verdict=verdict):
                self.run_cmd("bash", str(writer), str(self.repo), f"step{step}-check",
                             verdict, "0", "fixture", check=True)
                report = state / f"gates/step{step}-check.report"
                original = report.read_bytes()
                result = run("gates")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"EXISTING: check {verdict}", result.stdout)
                result = run("advance")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads((state / "state.json").read_text())["current_step"], step + 1)
                self.assertFalse((state / f".advance-attempts-step{step}").exists())
                self.assertFalse((state / "status/INCOMPLETE").exists())
                self.assertEqual(report.read_bytes(), original)

    def test_fail_and_inconclusive_block_without_losing_reports(self):
        run = self.isolated_orchestrator()
        self.activate(step=2)
        state = self.repo / ".rebase-tmp"
        original_state = (state / "state.json").read_bytes()
        writer = PLUGIN / "scripts/write-gate-report.sh"
        for attempt, verdict in enumerate(("FAIL", "INCONCLUSIVE"), 1):
            with self.subTest(verdict=verdict):
                self.run_cmd("bash", str(writer), str(self.repo), "step2-check",
                             verdict, "1", "fixture", check=True)
                report = state / "gates/step2-check.report"
                original = report.read_bytes()
                result = run("gates")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"EXISTING: check {verdict}", result.stdout)
                result = run("advance")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("FAILING: step2-compilation/check", result.stdout)
                self.assertEqual((state / ".advance-attempts-step2").read_text().strip(), str(attempt))
                self.assertEqual((state / "state.json").read_bytes(), original_state)
                self.assertEqual(report.read_bytes(), original)

    def test_stale_pass_and_skip_still_block(self):
        run = self.isolated_orchestrator()
        self.activate(step=2)
        state = self.repo / ".rebase-tmp"
        original_state = (state / "state.json").read_bytes()
        writer = PLUGIN / "scripts/write-gate-report.sh"
        for verdict in ("PASS", "SKIP"):
            with self.subTest(verdict=verdict):
                self.run_cmd("bash", str(writer), str(self.repo), "step2-check",
                             verdict, "0", "fixture", check=True)
                report = state / "gates/step2-check.report"
                original = report.read_bytes()
                self.run_cmd("git", "commit", "--allow-empty", "-qm", "new HEAD", check=True)
                result = run("gates")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("PENDING: check", result.stdout)
                result = run("advance")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("STALE: step2-compilation/check", result.stdout)
                self.assertEqual((state / "state.json").read_bytes(), original_state)
                self.assertEqual(report.read_bytes(), original)

    def test_missing_and_malformed_reports_block(self):
        run = self.isolated_orchestrator()
        self.activate(step=2)
        state = self.repo / ".rebase-tmp"
        original_state = (state / "state.json").read_bytes()
        report = state / "gates/step2-check.report"
        for contents in (None, f"HEAD: {self.git_sha()}\nVERDICT: unknown\n"):
            with self.subTest(contents=contents):
                if contents is not None:
                    report.parent.mkdir(parents=True, exist_ok=True)
                    report.write_text(contents)
                self.assertEqual(run("gates").returncode, 1)
                result = run("advance")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("MISSING: step2-compilation/check", result.stdout)
                self.assertEqual((state / "state.json").read_bytes(), original_state)
                if contents is None:
                    self.assertFalse(report.exists())
                else:
                    self.assertEqual(report.read_text(), contents)

    def test_verdict_prefixes_and_duplicate_verdicts_are_not_accepted(self):
        run = self.isolated_orchestrator()
        self.activate(step=2)
        state = self.repo / ".rebase-tmp"
        report = state / "gates/step2-check.report"
        report.parent.mkdir()
        for verdict in ("SKIP_PENDING", "SKIP: not evaluated", "PASSING",
                        "PASS\nVERDICT: FAIL", "SKIP\nVERDICT: SKIP"):
            with self.subTest(verdict=verdict):
                # Each case gets its first blocked attempt, not a forced handoff.
                (state / ".advance-attempts-step2").unlink(missing_ok=True)
                report.write_text(f"HEAD: {self.git_sha()}\nVERDICT: {verdict}\n")
                before = report.read_bytes()
                self.assertEqual(run("gates").returncode, 1)
                result = run("advance")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(json.loads((state / "state.json").read_text())["current_step"], 2)
                self.assertEqual(report.read_bytes(), before)
                self.assertFalse((state / "status/INCOMPLETE").exists())

    def test_gate_cache_freshness_and_force_advance(self):
        run = self.isolated_orchestrator()
        result = run("init", "1.36.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("STEP_FILE: steps/step1-rebase.md", result.stdout)
        self.assertEqual(run("gates").returncode, 1)
        writer = PLUGIN / "scripts/write-gate-report.sh"
        self.run_cmd("bash", str(writer), str(self.repo), "step1-check", "FAIL", "1", "fixture", check=True)
        result = run("gates")
        self.assertEqual(result.returncode, 0)
        self.assertIn("FAIL", result.stdout)
        self.run_cmd("git", "commit", "--allow-empty", "-qm", "new HEAD", check=True)
        self.assertEqual(run("gates").returncode, 1)
        for rc in (1, 1, 2):
            result = run("advance")
            self.assertEqual(result.returncode, rc, result.stderr)
        self.assertIn("FORCE_ADVANCE", result.stdout)
        self.assertIn("CURRENT: 2", run("status").stdout)
        state = self.repo / ".rebase-tmp"
        self.assertTrue((state / "gates/step1-check.report").exists())
        self.assertFalse((state / ".advance-attempts-step2").exists())
        self.assertTrue((state / "status/INCOMPLETE").exists())

    def test_final_inventory_includes_missing_reports_without_mutation(self):
        self.isolated_orchestrator()
        self.activate(step=5)
        self.env.update(PLUGIN_ROOT=str(self.root / "plugin"), REPO_ROOT=str(self.repo))
        writer = PLUGIN / "scripts/write-gate-report.sh"
        for step, verdict in ((1, "PASS"), (3, "INCONCLUSIVE"), (4, "SKIP")):
            self.run_cmd("bash", str(writer), str(self.repo), f"step{step}-check",
                         verdict, "0", "fixture", check=True)
        # Make the stored SHA historical: inventory must not refresh it.
        self.run_cmd("git", "commit", "--allow-empty", "-qm", "later HEAD", check=True)
        state = self.repo / ".rebase-tmp"
        before = {p: p.read_bytes() for p in state.rglob("*") if p.is_file()}
        instructions = (PLUGIN / "skills/k8s-rebase/steps/step5-pr.md").read_text()
        inventory = next(block.split("```", 1)[0] for block in instructions.split("```bash\n")[1:]
                         if ' reports "$REPO_ROOT"' in block.split("```", 1)[0])
        result = self.run_cmd("bash", "-c", inventory)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("EXPECTED GATES: 4\n", result.stdout)
        sections = result.stdout.strip().split("REPORT: ")[1:]
        self.assertEqual(len(sections), 4)
        self.assertIn("REPORT VERDICTS: PASS=1 SKIP=1 FAIL=0 INCONCLUSIVE=1 UNVERIFIED=1\n", result.stdout)
        self.assertIn("FINAL-STEP STALE: 1\n", result.stdout)
        self.assertIn("PASS AT INVENTORY HEAD: 0\nHISTORICAL PRIOR-STEP PASS: 1\nSTALE FINAL-STEP PASS: 0\n", result.stdout)
        for step, verdict in ((1, "PASS"), (2, None), (3, "INCONCLUSIVE"), (4, "SKIP")):
            section = next(s for s in sections if s.startswith(str(state / f"gates/step{step}-check.report") + "\n"))
            if verdict is None:
                self.assertIn("UNVERIFIED:", section)
                self.assertNotIn("VERDICT:", section)
            else:
                self.assertIn(f"VERDICT: {verdict}\n", section)
                self.assertIn(f"ASSESSMENT: {verdict}\n", section)
                self.assertIn("FRESHNESS: " + ("STALE final-step" if step == 4 else "historical"), section)
        self.assertEqual({p: p.read_bytes() for p in state.rglob("*") if p.is_file()}, before)

    def test_report_inventory_rejects_malformed_verdicts_and_heads(self):
        run = self.isolated_orchestrator()
        self.activate(step=5)
        state = self.repo / ".rebase-tmp"
        (state / "gates").mkdir()
        report = state / "gates/step2-check.report"
        head = f"HEAD: {self.git_sha()}\n"
        for body in (head + "VERDICT: PASSING\n", head + "VERDICT: PASS\nVERDICT: FAIL\n",
                     head + "VERDICT: SKIP\nVERDICT: SKIP\n", "VERDICT: PASS\n",
                     "HEAD: unknown\nVERDICT: PASS\n", head * 2 + "VERDICT: PASS\n",
                     head * 2 + "VERDICT: PASS\nDETAILS:\nquoted evidence\n",
                     head + "VERDICT: FAIL\nVERDICT: PASS\nDETAILS:\nquoted evidence\n"):
            with self.subTest(body=body):
                report.write_text(body)
                result = run("reports")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("UNVERIFIED: malformed HEAD or verdict\n", result.stdout)
                self.assertIn("REPORT VERDICTS: PASS=0 SKIP=0 FAIL=0 INCONCLUSIVE=0 UNVERIFIED=4\n", result.stdout)
                self.assertEqual(report.read_text(), body)
        for verdict in ("PASS", "SKIP", "FAIL", "INCONCLUSIVE"):
            report.write_text(head + f"VERDICT: {verdict}\n")
            result = run("reports")
            self.assertIn(f"ASSESSMENT: {verdict}\n", result.stdout)
            self.assertIn("FRESHNESS: current HEAD\n", result.stdout)
            self.assertIn(f"{verdict}=1", result.stdout)

    def test_report_inventory_errors_cannot_certify_completion(self):
        run = self.isolated_orchestrator()
        self.activate(step=5)
        state = self.repo / ".rebase-tmp"
        (state / "gates").mkdir()
        (state / "gates/step1-check.report").write_text(f"HEAD: {self.git_sha()}\nVERDICT: PASS\n")
        before = {p: p.read_bytes() for p in state.rglob("*") if p.is_file()}
        for tool in ("git", "cat"):
            with self.subTest(tool=tool):
                self.stub(tool, "exit 19\n")
                result = run("reports")
                (self.bin / tool).unlink()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("REPORT VERDICTS:", result.stdout)
        (self.root / "plugin/gates/step2-compilation/check.md").unlink()
        result = run("reports")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("REPORT VERDICTS:", result.stdout)
        self.assertEqual({p: p.read_bytes() for p in state.rglob("*") if p.is_file()}, before)

    def test_report_inventory_computes_pass_freshness_without_relabeling(self):
        run = self.isolated_orchestrator()
        self.activate(step=5)
        state = self.repo / ".rebase-tmp"
        (state / "gates").mkdir()
        for step, sha, verdict in ((1, self.base, "PASS"), (2, self.git_sha(), "PASS"),
                                   (3, self.git_sha(), "SKIP"), (4, self.base, "PASS")):
            (state / f"gates/step{step}-check.report").write_text(f"HEAD: {sha}\nVERDICT: {verdict}\n")
        before = {p: p.read_bytes() for p in state.rglob("*") if p.is_file()}
        result = run("reports")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("REPORT VERDICTS: PASS=3 SKIP=1 FAIL=0 INCONCLUSIVE=0 UNVERIFIED=0\n", result.stdout)
        self.assertIn("FINAL-STEP STALE: 1\n", result.stdout)
        self.assertIn("PASS AT INVENTORY HEAD: 1\nHISTORICAL PRIOR-STEP PASS: 1\nSTALE FINAL-STEP PASS: 1\n", result.stdout)
        self.assertEqual({p: p.read_bytes() for p in state.rglob("*") if p.is_file()}, before)

    def test_report_table_uses_exact_names_verdicts_and_freshness_without_mutation(self):
        run = self.isolated_orchestrator()
        self.activate(step=5)
        state = self.repo / ".rebase-tmp"
        (state / "gates").mkdir()
        gates = self.root / "plugin/gates"
        for check in gates.glob("*/check.md"):
            check.unlink()
        head = self.git_sha()
        cases = (
            ("step1-rebase", "rebase-completeness", "PASS", self.base, "historical"),
            ("step2-compilation", "test-compilation", "PASS", head, "current"),
            ("step3-autofix", "feature-gates", "SKIP", head, "current"),
            ("step4-verification", "correctness", "FAIL", head, "current"),
            ("step4-verification", "go-version-check", "PASS", self.base, "stale"),
            ("step4-verification", "maintainer-review", "INCONCLUSIVE", head, "current"),
        )
        rows = []
        for step, gate, verdict, sha, freshness in cases:
            (gates / step / f"{gate}.md").write_text("fixture gate\n")
            name = f"{step.split('-', 1)[0]}-{gate}.report"
            (state / "gates" / name).write_text(f"HEAD: {sha}\nVERDICT: {verdict}\n")
            rows.append(f"| `{name}` | {verdict} | {freshness} | `{sha[:12]}` |")
        before = {p: p.read_bytes() for p in state.rglob("*") if p.is_file()}
        result = run("reports")
        self.assertEqual(result.returncode, 0, result.stderr)
        table = result.stdout.split("\nGATE TABLE:\n", 1)[1]
        self.assertEqual(table, "| Gate report | Recorded verdict | Freshness | Reviewed HEAD |\n"
                         "| --- | --- | --- | --- |\n" + "\n".join(rows) + "\n")
        self.assertIn("REPORT VERDICTS: PASS=3 SKIP=1 FAIL=1 INCONCLUSIVE=1 UNVERIFIED=0\n", result.stdout)
        self.assertNotIn("unit-tests", table)
        self.assertNotIn("integration", table)
        self.assertEqual({p: p.read_bytes() for p in state.rglob("*") if p.is_file()}, before)

    def test_report_table_marks_missing_and_malformed_reports_unverified(self):
        run = self.isolated_orchestrator()
        self.activate(step=5)
        state = self.repo / ".rebase-tmp"
        (state / "gates").mkdir()
        (state / "gates/step2-check.report").write_text(f"HEAD: {self.git_sha()}\nVERDICT: PASSING\n")
        (state / "gates/step3-check.report").write_text("HEAD: unknown\nVERDICT: PASS\n")
        (state / "gates/step4-check.report").write_text(
            f"HEAD: {self.git_sha()}\nVERDICT: PASS\nVERDICT: SKIP\n")
        before = {p: p.read_bytes() for p in state.rglob("*") if p.is_file()}
        result = run("reports")
        self.assertEqual(result.returncode, 0, result.stderr)
        table = result.stdout.split("\nGATE TABLE:\n", 1)[1]
        self.assertEqual(table.splitlines()[2:], [
            f"| `step{step}-check.report` | UNVERIFIED | unverified | `-` |"
            for step in range(1, 5)])
        self.assertIn("REPORT VERDICTS: PASS=0 SKIP=0 FAIL=0 INCONCLUSIVE=0 UNVERIFIED=4\n", result.stdout)
        self.assertEqual({p: p.read_bytes() for p in state.rglob("*") if p.is_file()}, before)

    def test_report_table_is_not_emitted_if_head_changes_during_inventory(self):
        run = self.isolated_orchestrator()
        self.activate(step=5)
        state = self.repo / ".rebase-tmp"
        (state / "gates").mkdir()
        (state / "gates/step1-check.report").write_text(f"HEAD: {self.git_sha()}\nVERDICT: PASS\n")
        before = {p: p.read_bytes() for p in state.rglob("*") if p.is_file()}
        real_git = shutil.which("git")
        self.stub("git", 'if [[ "${*: -2}" == "rev-parse HEAD" ]]; then\n'
                  f'  printf "%s\\n" "{self.base}"; exit 0\nfi\nexec "{real_git}" "$@"\n')
        result = run("reports")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HEAD changed during report inventory", result.stderr)
        self.assertNotIn("REPORT VERDICTS:", result.stdout)
        self.assertNotIn("GATE TABLE:", result.stdout)
        self.assertNotIn("| Gate report |", result.stdout)
        self.assertEqual({p: p.read_bytes() for p in state.rglob("*") if p.is_file()}, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
