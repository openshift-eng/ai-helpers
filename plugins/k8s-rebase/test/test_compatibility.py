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
                self.assertEqual(prompt, self.review(scope, "--print-prompt", ref, context).stdout)
        self.assertFalse(self.claude_called.exists())

    def test_prompt_allocation_failure_preserves_prior_payload(self):
        self.activate(step=4)
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
        self.env.update(REPO_ROOT=str(self.repo), TMPDIR=str(scratch))
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
                   "gh pr create --title test", "gh api repos/org/repo/pulls -X POST")
        allowed = ('git status; cat "$HOOK_DIR/pre-push"',
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

    def test_stop_hook_waits_past_early_result_marker(self):
        self.activate(step=1)
        state = self.repo / ".rebase-tmp"
        child = subprocess.Popen(["bash", "-c", "read -r completion"],
                                 cwd=self.repo, env=self.env,
                                 stdin=subprocess.PIPE, text=True)
        try:
            (state / "step1.pid").write_text(str(child.pid))
            self.assertFalse(self.hook("stop-hook.sh", {}))
            (state / "step1-result.txt").write_text("EXIT 2\n")
            self.assertFalse(self.hook("stop-hook.sh", {}))
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
                    "unrelated.fixture": "keep\n"}
        for name, body in retained.items():
            path = state / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(body)
        scratch = [Path(self.run_cmd("mktemp", str(state / f"{prefix}-XXXXXX"),
                                     check=True).stdout.strip())
                   for prefix in ("test-only", "step4-review", "step5-review")]
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
        for name in ("step1-rebase", "step2-compilation", "step3-autofix", "step4-verification"):
            directory = isolated / "gates" / name
            directory.mkdir(parents=True)
            (directory / "check.md").write_text("fixture gate\n")

        def run(action, *args):
            return self.run_cmd("bash", str(orch), action, str(self.repo), *args)

        return run

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
                     "HEAD: unknown\nVERDICT: PASS\n", head * 2 + "VERDICT: PASS\n"):
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
