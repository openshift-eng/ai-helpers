#!/usr/bin/env python3
"""Tests for the pr-risk-assessment eval's evidence guard and judge."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pr_evidence_guard as guard

REPO = "openshift/hypershift"
BASE = "57a98bf0f6cc7267865b372f05a5bd151d632fd6"
HEAD = "0123456789abcdef0123456789abcdef01234567"
EVIDENCE = {"repo": REPO, "base_sha": BASE}
CLONE = (
    "mkdir -p .work && git init -q .work/repo && cd .work/repo\n"
    f"git remote add origin https://github.com/{REPO}.git\n"
    "git sparse-checkout set --no-cone '/*' '!/vendor/' '!**/testdata/'\n"
    f"git fetch -q --depth 1 --filter=blob:none origin {BASE}\n"
    "git checkout -q FETCH_HEAD"
)


def bash(command):
    return guard.denial("Bash", {"command": command}, EVIDENCE)


class PullRequestReads(unittest.TestCase):
    def test_denied(self):
        for command in [
            "gh pr view 10224 --repo openshift/hypershift --json labels",
            "gh --repo openshift/hypershift pr view 10224 --json labels,comments",
            "gh -R openshift/hypershift pr view 10224",
            "gh --repo=openshift/hypershift pr view 10224",
            "echo 10224 | xargs -n 1 gh -R openshift/hypershift pr view",
            "GH_REPO=openshift/hypershift gh issue view 1",
            "gh search prs --repo openshift/hypershift capabilities",
            "gh browse 10224 -R openshift/hypershift",
            "gh api repos/openshift/hypershift/pulls/10224",
            "gh api /repos/openshift/hypershift/issues/10224/comments",
            "gh api repos/openshift/hypershift/commits/abc123/pulls",
            "gh api graphql -f query='{ repository { pullRequest { labels } } }'",
            "curl -s https://api.github.com/search/issues?q=10224",
            "curl -sL 'https://github.com/search?q=repo%3Aopenshift%2Fhypershift+10224&type=pullrequests'",
            "curl -sL https://github.com/openshift/hypershift/pull/10224",
        ]:
            with self.subTest(command=command):
                self.assertIsNotNone(bash(command))

    def test_web_fetch_denied(self):
        reason = guard.denial("WebFetch", {"url": "https://github.com/search?q=10224"}, EVIDENCE)
        self.assertIsNotNone(reason)

    def test_eval_answers_denied_for_every_tool(self):
        path = "/repo/plugins/openshift-developer/evals/cases/pr-risk-assessment/case-004/annotations.yaml"
        self.assertIsNotNone(guard.denial("Read", {"file_path": path}, EVIDENCE))
        self.assertIsNotNone(guard.denial("Grep", {"pattern": "tier", "path": path}, EVIDENCE))
        self.assertIsNotNone(bash(f"cat {path}"))


class BaseOnly(unittest.TestCase):
    def test_denied(self):
        for command in [
            f"git fetch -q origin refs/pull/10224/head",
            "cd .work/repo && git fetch -q origin main && git log --oneline origin/main",
            "git fetch origin",
            f"git fetch --all",
            f"git fetch --tags origin {BASE}",
            f"git fetch origin {BASE} main",
            f"git fetch https://github.com/{REPO}.git refs/pull/10224/head",
            f"git clone --depth 1 https://github.com/{REPO}.git",
            "git pull",
            "git remote update",
            f"git -C .work/repo show {HEAD}:api/hypershift/v1beta1/hostedcluster_types.go",
            f"H={HEAD}; git -C .work/repo fetch --depth 1 origin $H",
            "git fetch origin $(jq -r .head_sha input.json)",
            f"gh api repos/{REPO}/contents/AGENTS.md",
            f"gh api 'repos/{REPO}/contents/AGENTS.md?ref=main'",
            f"gh api 'repos/{REPO}/contents/AGENTS.md?ref={HEAD}'",
            f"gh api -X GET repos/{REPO}/contents/AGENTS.md -f ref=main",
            "gh api 'repos/{owner}/{repo}/contents/AGENTS.md'",
            f"gh api 'repos/{REPO}/commits?sha=main'",
            f"gh api repos/{REPO}/compare/{BASE}...main",
            f"gh api repos/{REPO}/git/refs/heads/main",
            f"curl -sL https://raw.githubusercontent.com/{REPO}/main/AGENTS.md",
            f"curl -sL https://raw.githubusercontent.com/{REPO}/refs/heads/main/AGENTS.md",
            f"curl -sL https://github.com/{REPO}/blob/main/AGENTS.md",
            f"curl -sL https://github.com/{REPO}/commits/main",
        ]:
            with self.subTest(command=command):
                self.assertIsNotNone(bash(command))

    def test_allowed(self):
        for command in [
            CLONE,
            f"B={BASE}; mkdir -p .work && cd .work/repo && git fetch -q --depth=1 --filter=blob:none origin \"$B\"",
            f"git -C .work/repo show {BASE}:AGENTS.md",
            "cd .work/repo && cat AGENTS.md && git show FETCH_HEAD:control-plane-operator/AGENTS.md",
            f"gh api \"repos/{REPO}/contents/AGENTS.md?ref={BASE}\" -H 'Accept: application/vnd.github.raw'",
            f"B={BASE}; gh api \"repos/{REPO}/contents/support/globalconfig/dns.go?ref=$B\" --jq .content | base64 -d | head -60",
            f"gh api -X GET repos/{REPO}/contents/AGENTS.md -f ref={BASE}",
            f"gh api repos/{REPO}/git/trees/{BASE}",
            f"curl -sL https://raw.githubusercontent.com/{REPO}/{BASE}/AGENTS.md",
            f"B=https://raw.githubusercontent.com/{REPO}/{BASE}; for f in AGENTS.md api/AGENTS.md; "
            "do curl -sfL \"$B/$f\" -o \"$(basename $f)\"; done",
            f"curl -sL https://github.com/{REPO}/blob/{BASE}/AGENTS.md",
            "gh api 'repos/openshift/api/contents/config/v1/types.go?ref=master'",
            "ls .work/repos/openshift/hypershift/pkg",
            "grep -rn 'sha256:" + "a" * 64 + "' .work/repo/hack",
            f"git ls-remote https://github.com/{REPO}.git",
            "python3 -I -c \"import json;d=json.load(open('input.json'));print(d['title'])\"",
        ]:
            with self.subTest(command=command):
                self.assertIsNone(bash(command))

    def test_result_written_by_heredoc_is_not_a_read(self):
        result = json.dumps({"pr_url": f"https://github.com/{REPO}/pull/10224", "head": HEAD})
        for header in ("cat > output/risk-result.json <<'EOF'", "cat <<EOF > output/risk-result.json",
                       "tee output/risk-result.json <<'EOF' >/dev/null"):
            with self.subTest(header=header):
                self.assertIsNone(bash(f"{header}\n{result}\nEOF\necho done"))

    def test_heredoc_that_runs_is_still_read(self):
        script = f"import subprocess\nsubprocess.run(['curl', 'https://github.com/{REPO}/pull/10224'])"
        self.assertIsNotNone(bash(f"python3 - <<'EOF'\n{script}\nEOF"))
        self.assertIsNotNone(bash(f"cat <<'EOF' | sh\ngh pr view 10224\nEOF"))

    def test_local_tools_are_not_base_checked(self):
        self.assertIsNone(guard.denial("Read", {"file_path": f"/ws/.work/{HEAD}.txt"}, EVIDENCE))


class Hook(unittest.TestCase):
    def setUp(self):
        self.workspace = Path(tempfile.mkdtemp())
        shutil.copy2(Path(guard.__file__), self.workspace / "pr_evidence_guard.py")

    def tearDown(self):
        shutil.rmtree(self.workspace)

    def run_hook(self, tool, tool_input):
        payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input})
        return subprocess.run([sys.executable, str(self.workspace / "pr_evidence_guard.py")],
                              input=payload, text=True, capture_output=True)

    def test_denies_with_exit_2_and_guidance(self):
        (self.workspace / "input.json").write_text(json.dumps({"repo": REPO, "base_sha": BASE}))
        result = self.run_hook("Bash", {"command": "gh -R openshift/hypershift pr view 10224"})
        self.assertEqual(result.returncode, 2)
        self.assertIn(guard.BLOCKED, result.stderr)
        self.assertIn(BASE, result.stderr)

    def test_allows_with_exit_0(self):
        (self.workspace / "input.json").write_text(json.dumps({"repo": REPO, "base_sha": BASE}))
        result = self.run_hook("Bash", {"command": CLONE})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fails_closed_without_input_json(self):
        result = self.run_hook("Bash", {"command": "ls"})
        self.assertEqual(result.returncode, 2)
        self.assertIn("the evidence guard failed", result.stderr)


class Judge(unittest.TestCase):
    def setUp(self):
        self.cases = Path(tempfile.mkdtemp())
        (self.cases / "case-001").mkdir()
        (self.cases / "case-001" / "input.json").write_text(json.dumps({"repo": REPO, "base_sha": BASE}))
        self.patch = patch.object(guard, "CASES", self.cases)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.cases)

    def judge(self, *calls):
        events = []
        for i, (tool, tool_input, content) in enumerate(calls):
            events.append({"type": "assistant", "tools": [{"id": f"t{i}", "name": tool, "input": tool_input}]})
            events.append({"type": "tool_result", "tool_use_id": f"t{i}", "content": content})
        ok, rationale = guard.judge_pull_request_not_read(
            {"case_dir": "/runs/r1/cases/case-001", "events": events})
        return ok, rationale

    def test_clean_run_passes(self):
        ok, _ = self.judge(("Bash", {"command": CLONE}, ""),
                           ("Read", {"file_path": "/ws/.work/repo/AGENTS.md"}, "# AGENTS.md"))
        self.assertTrue(ok)

    def test_blocked_call_passes(self):
        ok, _ = self.judge(("Bash", {"command": "gh -R openshift/hypershift pr view 1"},
                            f"PreToolUse:Bash hook error: {guard.BLOCKED}: gh pr"))
        self.assertTrue(ok)

    def test_call_the_hook_missed_fails(self):
        ok, rationale = self.judge(("Bash", {"command": f"git fetch origin {HEAD}"}, ""))
        self.assertFalse(ok)
        self.assertIn("not blocked", rationale)

    def test_label_in_output_fails_however_it_was_read(self):
        ok, rationale = self.judge(("Bash", {"command": "python3 fetch.py"},
                                    '["approved","chai-risk-assessment/critical"]'))
        self.assertFalse(ok)
        self.assertIn("chai-risk-assessment/", rationale)

    def test_answers_in_output_fail(self):
        ok, _ = self.judge(("Grep", {"pattern": "tier", "path": "scripts/.."}, "expected_tier: critical"))
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
