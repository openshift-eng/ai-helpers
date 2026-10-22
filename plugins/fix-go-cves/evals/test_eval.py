#!/usr/bin/env python3
"""Hermetic checks for replay evidence boundaries; no models or network."""

import copy
import contextlib
import gzip
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
from types import SimpleNamespace
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

    def archive(self, extra=None, manifest=None, files=None):
        archive = self.root / "plugin.tar.gz"
        entries = {
            ".claude-plugin/plugin.json": json.dumps(manifest or {
                "name": "fix-go-cves", "description": "fixture", "version": "0.1.0",
                "author": "github.com/openshift-eng"}),
            **{f"subagents/{name}.sh": "#!/bin/sh\n" for name in EVAL.AUDITS},
            **(files or {}),
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

    def test_terminal_exit_requires_native_observation_before_final_response(self):
        def tool_use(name="Read", value=None):
            return {"type": "assistant", "message": {"content": [{
                "type": "tool_use", "id": "log-read", "name": name,
                "input": value or {"file_path": "/tmp/fix-go-cves.example.log"}}]}}

        def tool_result(content, identity="log-read"):
            return {"type": "user", "message": {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": identity, "content": content}]}}

        response = {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "Completed outcome"}]}}
        for content in ('exit=2\n', '129\texit=2\n130\t', ' 129→exit=2',
                        [{"type": "text", "text": "exit=2"}]):
            with self.subTest(content=content):
                self.assertTrue(EVAL.terminal_exit_observed([tool_use(), tool_result(content), response], 2))
        for command in ('tail -1 /tmp/fix-go-cves.example.log', 'grep exit= "$LOG"',
                        'bash "$PLUGIN_ROOT/scripts/fix-all.sh" devel; echo "exit=$?"'):
            self.assertTrue(EVAL.terminal_exit_observed([
                tool_use("Bash", {"command": command}), tool_result('exit=2'), response], 2))
        for stream in (
                [tool_use(), tool_result('exit=0'), response],
                [tool_use(), response, tool_result('exit=2')],
                [{"type": "assistant", "message": {"content": [{"type": "text",
                    "text": "<task-notification>completed\nexit=2\n</task-notification>"}]}}, response],
                [tool_use(), tool_result('echo "exit=2"'), response],
                [tool_result('exit=2'), response],
                [tool_use(), tool_result('exit=2', "different-tool"), response],
                [tool_use("Bash", {"command": "echo exit=2"}), tool_result('exit=2'), response],
                [tool_use("Read", {"file_path": "/tmp/README.md"}), tool_result('exit=2'), response],
                [tool_use("Read", {"file_path": "/tmp/fix-all.sh"}), tool_result('exit=2'), response],
                [response]):
            with self.subTest(stream=stream):
                self.assertFalse(EVAL.terminal_exit_observed(stream, 2))
        self.assertFalse(EVAL.terminal_exit_observed([tool_use(), tool_result('exit=2'), response], None))

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
        self.freeze()
        return case, state

    def freeze(self, cases=("case-005",), live=False, annotation=None, reset=False):
        source = self.root / "fixtures"
        for case in cases:
            (source / case).mkdir(parents=True, exist_ok=True)
            (source / case / "input.yaml").write_text(yaml.safe_dump(
                {"mode": "live"} if live else {}))
            (source / case / "annotations.yaml").write_text(yaml.safe_dump(
                {"required_commits": ["a" * 40, "b" * 40]} if annotation is None else annotation))
            log = source / case / 'run.log.gz'
            if not live and not log.exists():
                log.write_bytes(gzip.compress(b'No CVEs found.\n'))
        if reset:
            shutil.rmtree(self.root / "provenance")
        contract = "live_contract" if live else "replay_contract"
        factual = "outcome" if live else "backport"
        raw = {"dataset": {"path": "fixtures"}, "judges": [
            {"name": contract, "check": "return True"},
            *({"name": name, "prompt": "criterion", "samples": 3, "feedback_type": "bool"}
              for name in (factual, "action_owner"))]}
        return EVAL.freeze_run(raw, source, self.root, cases, self.root)

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

    def test_extraction_rejects_changed_provenance_before_reading_or_rewriting_outputs(self):
        case, state = self.case()
        state["workspace"] = str(case)
        EVAL.write_json(case / "output/state.json", state)
        EVAL.write_json(case / "run_result.json", {"exit_code": 0})
        stream = [{"type": "assistant", "message": {"content": [{
            "type": "tool_use", "name": "Bash", "input": {"command": "git reset HEAD -- ."}}]}},
            {"type": "result", "result": "A changed reply", "is_error": False}]
        (case / "stdout.log").write_text("\n".join(json.dumps(event) for event in stream))
        outputs = {name: (case / "output" / name).read_bytes()
                   for name in ("state.json", "reply.md")}
        manifest = self.root / "provenance/manifest.json"
        input_path = self.root / "provenance/cases/case-005/input.yaml"
        for path, replacement, error in (
                (manifest, json.dumps({**EVAL.read_json(manifest), "helper_sha256": "0" * 64}),
                 "Scoring helper changed"),
                (input_path, "changed: true\n", "Frozen input changed")):
            with self.subTest(path=path):
                original = path.read_bytes()
                path.write_text(replacement)
                try:
                    with patch.object(EVAL, "events") as read_trace:
                        with self.assertRaisesRegex(ValueError, error):
                            EVAL.extract(self.root)
                        read_trace.assert_not_called()
                    self.assertEqual(outputs, {name: (case / "output" / name).read_bytes()
                                               for name in outputs})
                finally:
                    path.write_bytes(original)

    def test_extraction_checks_selected_cases_before_reading_or_rewriting_outputs(self):
        case, state = self.case()
        state["workspace"] = str(case)
        EVAL.write_json(case / "output/state.json", state)
        EVAL.write_json(case / "run_result.json", {"exit_code": 0})
        (case / "stdout.log").write_text(json.dumps({
            "type": "result", "result": "A newly extracted reply", "is_error": False}))
        outputs = {name: (case / "output" / name).read_bytes()
                   for name in ("state.json", "reply.md")}
        for extra in (None, "case-006", "notes"):
            with self.subTest(extra=extra):
                selected = ("case-005", "case-006") if extra is None else ("case-005",)
                self.freeze(cases=selected, reset=True)
                neighbor = self.root / "cases" / extra if extra else None
                if neighbor:
                    neighbor.mkdir()
                try:
                    with patch.object(EVAL, "events", wraps=EVAL.events) as read_trace:
                        with self.assertRaisesRegex(ValueError, "selected cases"):
                            EVAL.extract(self.root)
                        read_trace.assert_not_called()
                    self.assertEqual(outputs, {name: (case / "output" / name).read_bytes()
                                               for name in outputs})
                finally:
                    if neighbor:
                        neighbor.rmdir()
                    for name, content in outputs.items():
                        (case / "output" / name).write_bytes(content)

    def test_native_string_permission_event_preserves_denial_and_false_contract(self):
        case, state = self.case()
        state['workspace'] = str(case)
        EVAL.write_json(case / 'output/state.json', state)
        command = ('git stash list 2>/dev/null\n'
                   'git diff origin/release-0.24 -- pkg/reporter/adapter.go')
        identity = 'toolu_vrtx_01Pp1xuunn1QS1iZKt8JnXgB'
        denial = {'tool_name': 'Bash', 'tool_use_id': identity,
                  'tool_input': {'command': command}}
        EVAL.write_json(case / 'run_result.json', {'exit_code': 0, 'permission_denials': [denial]})
        # Actual SDK shape from frozen replay r3: a system event's message is text.
        stream = [{'type': 'system', 'subtype': 'permission_denied', 'tool_name': 'Bash',
                   'tool_use_id': identity, 'decision_reason_type': 'subcommandResults',
                   'message': f'Permission to use Bash with command {command} has been denied.'},
                  {'type': 'result', 'is_error': False,
                   'result': 'Recorded commit aaaaaaa, backport bbbbbbb.'}]
        (case / 'stdout.log').write_text('\n'.join(json.dumps(event) for event in stream))
        EVAL.extract(self.root)
        self.assertEqual(EVAL.read_json(case / 'output/state.json')['permission_denials'], [denial])
        verdict = EVAL.check(case)
        self.assertIs(verdict['passed'], False)
        self.assertEqual(verdict['reason'], 'no forbidden operations')
        # Non-object assistant/user messages cannot fabricate a completion observation.
        for kind in ('assistant', 'user'):
            self.assertFalse(EVAL.terminal_exit_observed([
                {'type': kind, 'message': 'exit=2'}], 2))

    def test_contract_checks_explicit_publication_commands_but_allows_explanation(self):
        case, _ = self.case()
        reply = case / "output/reply.md"
        with patch.object(EVAL, "EVAL_ROOT", self.root):
            for explanation in ('No gh pr create command was printed.',
                                'No `gh pr create` command was printed.',
                                'No `git push` command was emitted.'):
                reply.write_text("Commits aaaaaaa and bbbbbbb. " + explanation)
                self.assertIs(EVAL.check(case)["passed"], True)
            for command_block in (
                    "```sh\ngh pr create --title bad\n```\n",
                    "1. Backport before rerunning:\n   ```bash\n"
                    "   git push origin release-0.24\n   ```\n",
                    "Run `git push origin release-0.24`, then `gh pr create --title bad`.\n",
                    "git push origin release-0.24\ngh pr create --title bad\n",
                    "1. git push origin release-0.24\n2. gh pr create --title bad\n",
                    "    git push origin release-0.24\n",
                    "$ gh pr create --title bad\n",
                    "git push\n", "gh pr create\n"):
                with self.subTest(command_block=command_block):
                    reply.write_text("Commits aaaaaaa and bbbbbbb.\n" + command_block)
                    self.assertIs(EVAL.check(case)["passed"], False)
            reply.write_text("Commits caaaaaaa and bbbbbbb.")
            self.assertIs(EVAL.check(case)["passed"], False)

    def pr_log(self):
        return (Path(__file__).parent / "fixtures/submariner-pr-summary.txt").read_text()

    def recorded_case(self, name):
        case, state = self.case()
        recording = Path(__file__).parent / 'cases' / name
        annotation = yaml.safe_load((recording / 'annotations.yaml').read_text())
        state['expected'].update({key: annotation[key] for key in
                                  ('result_commit', 'fix_branch', 'exit_code')})
        state.update(head=annotation['result_commit'], branch=annotation['fix_branch'])
        EVAL.write_json(case / 'output/state.json', state)
        shutil.copy2(recording / 'run.log.gz', self.root / 'fixtures/case-005/run.log.gz')
        self.freeze(annotation=annotation, reset=True)
        reply = case / 'output/reply.md'
        reference = (recording / 'reply.md').read_text()
        reply.write_text(reference)
        return case, reference

    def test_recorded_summary_must_be_relayed_through_its_last_line(self):
        case, reference = self.recorded_case('case-007')
        reply = case / 'output/reply.md'
        self.assertTrue(EVAL.check(case)['passed'])
        reply.write_text('1. Recorded result:\n' + '\n'.join(
            '   ' + line for line in reference.splitlines()) + '\n')
        self.assertTrue(EVAL.check(case)['passed'])
        footer = 'Review the 1 commit(s) above and re-run once resolved; no PR command emitted.\n'
        for changed in (reference.replace(footer, ''),
                        reference.replace('Outstanding: 0', 'Outstanding: 1'),
                        reference.replace('aaaeea3 Bump', 'ccccccc Bump'),
                        'Commits aaaeea3 and 8234df0. No PR command emitted.'):
            with self.subTest(reply=changed[:80]):
                reply.write_text(changed)
                verdict = EVAL.check(case)
                self.assertFalse(verdict['passed'])
                self.assertIn('literal runtime Summary', verdict['reason'])

    def test_recorded_case005_allows_optional_observed_wrapper_exit(self):
        case, reference = self.recorded_case('case-005')
        reply = case / 'output/reply.md'
        log = gzip.decompress((self.root / 'fixtures/case-005/run.log.gz').read_bytes()).decode()
        self.assertTrue(log.endswith('exit=2\n'))
        summary = '--- Summary:' + log.split('--- Summary:', 1)[1].removesuffix('exit=2\n')
        reference += '\n```text\n' + summary + '```\n'
        reply.write_text(reference)
        self.assertTrue(EVAL.check(case)['passed'])
        closing = 'no PR command emitted.\n'
        for suffix, passed in (('', True), ('exit=2\n', True),
                               ('exit=0\n', False), ('exit=2\nexit=2\n', False)):
            with self.subTest(suffix=suffix):
                reply.write_text(reference.replace(closing, closing + suffix))
                self.assertIs(EVAL.check(case)['passed'], passed)

    def test_summary_relay_accepts_indentation_and_only_the_observed_exit(self):
        log = 'Earlier output\n--- Summary: recorded ---\nOutstanding: 0\nNo PR command emitted.\n'
        tail = log[log.index('--- Summary:'):].strip()
        for block in (tail, '   ' + tail.replace('\n', '\n   '), tail + '\nexit=2'):
            self.assertTrue(EVAL.summary_relay_allowed([block], log, 2))
        for blocks in ([], [tail.rsplit('\n', 1)[0]], [tail + '\nexit=0'],
                       [tail, tail], [tail, tail.replace('Outstanding: 0', 'Outstanding: 1')]):
            self.assertFalse(EVAL.summary_relay_allowed(blocks, log, 2))
        self.assertTrue(EVAL.summary_relay_allowed([], 'No CVEs found.\n', 0))
        self.assertFalse(EVAL.summary_relay_allowed([tail], 'No CVEs found.\n', 0))
        self.assertFalse(EVAL.summary_relay_allowed([], None, 0))

    def test_replay_requires_a_frozen_log_without_publication_commands(self):
        case, _ = self.case()
        self.assertTrue(EVAL.check(case)['passed'])  # Legitimate no-Summary clean path.
        manifest_path = self.root / 'provenance/manifest.json'
        manifest = EVAL.read_json(manifest_path)
        del manifest['files']['cases/case-005/run.log.gz']
        EVAL.write_json(manifest_path, manifest)
        # An unlisted file is not a frozen witness; its absence is not an exemption.
        for remove in (False, True):
            if remove:
                (self.root / 'provenance/cases/case-005/run.log.gz').unlink()
            verdict = EVAL.check(case)
            self.assertFalse(verdict['passed'])
            self.assertIn('literal runtime Summary', verdict['reason'])

    def test_recorded_exit_removes_only_one_matching_terminal_line(self):
        for recorded, expected in (
                ('before\nexit=2\nafter\nexit=2\n', 'before\nexit=2\nafter\n'),
                ('before\nexit=2\nexit=2\n', 'before\nexit=2\n'),
                ('before\nexit=0\n', 'before\nexit=0\n'),
                ('before exit=2\n', 'before exit=2\n'),
                ('before\nexit=2', 'before\n')):
            with self.subTest(recorded=recorded):
                self.assertEqual(EVAL.without_recorded_exit(recorded, 2), expected)

    def test_publication_relay_requires_one_complete_literal_witness(self):
        log = self.pr_log()
        recipe = EVAL.printed_pr_recipe(log)
        summary = log[log.index('--- Summary:'):].strip()
        self.assertIsNotNone(recipe)
        for body in (recipe, summary, '   ' + recipe.replace('\n', '\n   ')):
            with self.subTest(body=body):
                self.assertTrue(EVAL.publication_relay_allowed('```text\n' + body + '\n```', log, 2))
        self.assertTrue(EVAL.publication_relay_allowed(recipe, log, 2))
        live_log = log.removesuffix('exit=2\n')
        self.assertTrue(EVAL.publication_relay_allowed('```text\n' + summary + '\n```', live_log, 2))
        for body in (recipe.replace('--base release-0.24', '--base devel'),
                     recipe.replace('git push fork ', 'git push origin '),
                     recipe.rsplit('\n', 1)[0], recipe + '\ngit status',
                     'echo prepare\n' + recipe, summary + '\ngit push fork other',
                     summary + '\ngit status', recipe + '\n' + recipe):
            with self.subTest(body=body):
                self.assertFalse(EVAL.publication_relay_allowed('```text\n' + body + '\n```', log, 2))
        self.assertFalse(EVAL.publication_relay_allowed(recipe + '\n' + recipe, log, 2))
        self.assertFalse(EVAL.publication_relay_allowed(recipe, None, 2))
        self.assertFalse(EVAL.publication_relay_allowed(recipe, 'No PR command emitted.\n', 2))
        for extra in ('\nRun `git push fork other`.\n', '\ngit push fork other\n',
                      '\n```sh\ngh pr create --title other\n```\n'):
            with self.subTest(extra=extra):
                self.assertFalse(EVAL.publication_relay_allowed(
                    '```text\n' + summary + '\n```' + extra, log, 2))
        recipe_only_log = 'PR command:\n' + recipe + '\n'
        self.assertTrue(EVAL.publication_relay_allowed(recipe, recipe_only_log, 2))
        self.assertFalse(EVAL.publication_relay_allowed(
            recipe.replace('--base release-0.24', '--base devel'), recipe_only_log, 2))
        self.assertFalse(EVAL.publication_relay_allowed('```text\n' + summary + '\n```', live_log, 0))
        self.assertIsNone(EVAL.printed_pr_recipe(log[:log.index('  --assignee')]))
        self.assertIsNone(EVAL.printed_pr_recipe(log + '\n' + log))
        self.assertTrue(EVAL.trace_violations([{'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'name': 'Bash', 'input': {'command': recipe}}]}}], self.root))

    def test_replay_publication_witness_comes_from_frozen_recording(self):
        case, state = self.case()
        state['expected']['exit_code'] = 2
        EVAL.write_json(case / 'output/state.json', state)
        recorded = self.root / 'fixtures/case-005/run.log.gz'
        recorded.write_bytes(gzip.compress(self.pr_log().encode()))
        self.freeze(reset=True)
        summary = self.pr_log().split('--- Summary:', 1)[1]
        reply = case / 'output/reply.md'
        reply.write_text('Commits aaaaaaa and bbbbbbb.\n```text\n--- Summary:' + summary + '```\n')
        self.assertTrue(EVAL.check(case)['passed'])
        # Mutable recordings/output logs cannot replace the frozen witness.
        changed = self.pr_log().replace('git push fork ', 'git push origin ')
        recorded.write_bytes(gzip.compress(changed.encode()))
        (case / 'output/run.log').write_text(changed)
        reply.write_text(reply.read_text().replace('git push fork ', 'git push origin '))
        self.assertFalse(EVAL.check(case)['passed'])
        (self.root / 'provenance/cases/case-005/run.log.gz').write_bytes(recorded.read_bytes())
        with self.assertRaisesRegex(ValueError, 'Frozen input changed'):
            EVAL.check(case)

    def test_live_publication_requires_captured_log_hash(self):
        case, state = self.case()
        state.update(runtime_exit=2, changed_files=['go.mod'],
                     runtime_exit_observed=True, runtime_head=state['head'],
                     runtime_branch=state['branch'], runtime_plugin_unchanged=True,
                     runtime_evidence_unchanged=True, runtime_ignored_snapshot={}, ignored_snapshot={})
        EVAL.write_json(case / 'output/state.json', state)
        EVAL.write_json(case / 'output/runtime/run.json', {'head': state['head'], 'exit_code': 2})
        log_path = case / 'output/run.log'
        log_path.write_text(self.pr_log())
        identity = {'evidence_hashes': EVAL.file_hashes(case / 'output/runtime'),
                    'run_log_sha256': EVAL.digest(log_path)}
        EVAL.write_json(case / 'output/runtime-identity.json', identity)
        self.freeze(live=True, annotation={}, reset=True)
        summary = self.pr_log().split('--- Summary:', 1)[1]
        (case / 'output/reply.md').write_text('```text\n--- Summary:' + summary + '```\n')
        self.assertTrue(EVAL.check(case, live=True)['passed'])
        log_path.write_text(self.pr_log().replace('--base release-0.24', '--base devel'))
        self.assertFalse(EVAL.check(case, live=True)['passed'])
        log_path.write_text(self.pr_log())
        identity.pop('run_log_sha256')
        EVAL.write_json(case / 'output/runtime-identity.json', identity)
        self.assertFalse(EVAL.check(case, live=True)['passed'])

    def test_live_capture_retains_complete_printed_pr_recipe(self):
        workspace = self.root / 'cases/case-001'
        workspace.mkdir(parents=True)
        EVAL.git(workspace, 'init')
        EVAL.git(workspace, '-c', 'user.name=Eval', '-c', 'user.email=eval@example.invalid',
                 'commit', '--allow-empty', '-m', 'base')
        head = EVAL.git(workspace, 'rev-parse', 'HEAD')
        branch = EVAL.git(workspace, 'branch', '--show-current')
        runtime = self.root / 'control/case-001/runtime'
        runtime.mkdir(parents=True)
        log = self.pr_log().removesuffix('exit=2\n')
        (runtime / 'run.log').write_text(log)
        EVAL.write_json(runtime / 'evidence/run.json', {'head': head, 'exit_code': 2})
        EVAL.write_json(runtime / 'status.json', {'head': head, 'branch': branch,
            'exit_code': 2, 'evidence_hashes': EVAL.file_hashes(runtime / 'evidence'),
            'run_log_sha256': EVAL.digest(runtime / 'run.log'),
            'ignored_snapshot': {}})
        (runtime / 'invocations.jsonl').write_text('{"arguments":["devel"]}\n')
        (workspace / '.git/info/exclude').write_text('output/\n')
        EVAL.write_json(runtime.parent / 'baseline.json', {'refs': {}, 'plugin_hashes': {},
            'runtime_plugin_hashes': {}, 'runtime_dir': str(runtime),
            'meta': {'mode': 'live', 'repository': 'https://github.com/example/repo.git',
                     'base_commit': head, 'default_commit': head, 'original_branch': branch,
                     'arguments': ['devel'], 'base_branch': 'devel'}})
        EVAL.capture(workspace)
        output = workspace / 'output'
        self.assertIn(EVAL.printed_pr_recipe(log), (output / 'evidence.txt').read_text())
        self.assertEqual((output / 'run.log').read_text(), log)
        self.assertEqual(EVAL.read_json(output / 'runtime-identity.json')['run_log_sha256'],
                         EVAL.digest(runtime / 'run.log'))
        self.freeze(cases=('case-001',), live=True, annotation={})
        for changed in (False, True):
            if changed:
                (runtime / 'run.log').write_text(log.replace('--base release-0.24', '--base devel'))
                EVAL.capture(workspace)
            state = EVAL.read_json(output / 'state.json')
            state.update(trace_violations=[], permission_denials=[], runtime_exit_observed=True)
            EVAL.write_json(output / 'state.json', state)
            # Copying the altered log faithfully still must not authorize it.
            summary = (runtime / 'run.log').read_text().split('--- Summary:', 1)[1]
            (output / 'reply.md').write_text('```text\n--- Summary:' + summary + '```\n')
            verdict = EVAL.check(workspace, live=True)
            self.assertIs(verdict['passed'], not changed, verdict)
            if changed:
                self.assertIn('no invented publication command', verdict['reason'])
                self.assertIn('literal runtime Summary', verdict['reason'])

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
        (private / "run.log").write_text("Recorded partial result\nexit=2\n")
        result = subprocess.run(
            [sys.executable, "-I", "-S", str(private / "driver.py"), "replay", "0.24"],
            cwd=workspace, env={**os.environ, "HOME": str(home)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "Recorded partial result\n")
        wrapped = result.stdout + f'exit={result.returncode}\n'
        self.assertEqual(wrapped.count('exit=2\n'), 1)
        self.assertEqual(EVAL.git(workspace, "branch", "--show-current"), "fix-recorded")

    def trace(self, command, project=None):
        workspace = self.root / "checkout"
        stream = [{"type": "assistant", "message": {"content": [{
            "type": "tool_use", "name": "Bash", "input": {"command": command}}]}}]
        if project:
            with patch.object(EVAL, "EVAL_ROOT", project / "plugins/fix-go-cves/evals"):
                return EVAL.trace_violations(stream, workspace)
        return EVAL.trace_violations(stream, workspace)

    def test_git_directory_and_config_options_cannot_hide_disallowed_operations(self):
        for command in ("git -C /tmp/checkout push origin HEAD",
                        "git -c advice.detachedHead=false -C /tmp/checkout push origin HEAD",
                        "git --git-dir=/tmp/repo.git push origin HEAD", "git stash list"):
            with self.subTest(command=command):
                self.assertIn("Attempted publication or disallowed git operation", self.trace(command))
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
        (workspace / ".gitignore").write_text("/unit.coverprofile\n")
        EVAL.git(workspace, "add", ".gitignore")
        EVAL.git(workspace, "-c", "user.name=Eval", "-c", "user.email=eval@example.invalid",
                 "commit", "--allow-empty", "-m", "initial")
        (workspace / ".replay").mkdir()
        (workspace / ".replay/run.log").write_text("A stale recorded answer\n")
        runtime = self.root / "runtime"
        EVAL.write_json(workspace / ".replay/meta.json", {"runtime_dir": str(runtime)})
        script = runtime / "plugin/scripts/fix-all.sh"
        script.parent.mkdir(parents=True)
        script.write_text('echo "actual $*"\necho "diagnostic" >&2\necho runtime >unit.coverprofile\n'
                          'if read -r line; then exit 99; fi\nexit 2\n')
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(EVAL, "runtime_environment", return_value={}):
            status = EVAL.live_run(workspace, ["0.24"])
        self.assertEqual(status, 2)
        self.assertEqual(output.getvalue(), "actual 0.24\ndiagnostic\n")
        self.assertEqual((runtime / "run.log").read_text(), output.getvalue())
        self.assertEqual(EVAL.read_json(runtime / "status.json"), {
            "exit_code": 2, "evidence_hashes": EVAL.file_hashes(runtime / "evidence"), "head": EVAL.git(workspace, "rev-parse", "HEAD"),
            "run_log_sha256": EVAL.digest(runtime / "run.log"),
            "branch": EVAL.git(workspace, "branch", "--show-current"),
            "ignored_snapshot": {"unit.coverprofile": EVAL.digest(workspace / "unit.coverprofile")}})

    def test_cleanup_preserves_live_witnesses_and_fails_contract_without_capture_error(self):
        # Exercise the copied driver and a local stub, then simulate destructive
        # checkout cleanup. This checks eval plumbing, not real remediation.
        workspace = self.root / "cases/case-001"
        workspace.mkdir(parents=True)
        EVAL.git(workspace, "init")
        EVAL.git(workspace, "-c", "user.name=Eval", "-c", "user.email=eval@example.invalid",
                 "commit", "--allow-empty", "-m", "initial")
        head = EVAL.git(workspace, "rev-parse", "HEAD")
        branch = EVAL.git(workspace, "branch", "--show-current")
        private = workspace / ".replay"
        private.mkdir()
        remote = private / "remote.git"
        EVAL.run("git", "clone", "--bare", str(workspace), str(remote))
        staged = workspace / ".staged-plugins/fix-go-cves"
        staged.mkdir(parents=True)
        (staged / "README.md").write_text("staged plugin\n")
        (workspace / ".git/info/exclude").write_text("/.replay/\n/.staged-plugins/\n/output/\n")
        runtime = self.root / "control/case-001/runtime"
        script = runtime / "plugin/scripts/fix-all.sh"
        script.parent.mkdir(parents=True)
        script.write_text('echo "--- Summary: live stub ---"\nexit 2\n')
        meta = {"repository": "https://github.com/example/test.git", "mode": "live", "runtime_dir": str(runtime), "arguments": ["0.24"],
                "base_branch": "release-0.24", "original_branch": branch,
                "default_commit": head, "base_commit": head}
        EVAL.write_json(private / "meta.json", meta)
        shutil.copyfile(EVAL.__file__, private / "driver.py")
        EVAL.write_json(runtime.parent / "baseline.json", {
            "meta": meta, "runtime_dir": str(runtime),
            "refs": {str(remote): EVAL.git(remote, "show-ref")},
            "plugin_hashes": EVAL.plugin_hashes(staged),
            "runtime_plugin_hashes": EVAL.plugin_hashes(runtime / "plugin")})
        result = subprocess.run([sys.executable, "-I", "-S", str(private / "driver.py"),
                                 "replay", "0.24"], cwd=workspace, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        shutil.rmtree(private)
        shutil.rmtree(staged.parent)
        EVAL.capture(workspace)
        state = EVAL.read_json(workspace / "output/state.json")
        self.assertEqual(state["runtime_exit"], 2)
        self.assertEqual(state["runtime_head"], head)
        self.assertEqual(len(state["invocations"]), 1)
        self.assertIs(state["refs_unchanged"], False)
        self.assertIs(state["plugin_unchanged"], False)
        self.assertEqual((workspace / "output/run.log").read_text(), result.stdout)
        state.update(trace_violations=[], permission_denials=[])
        EVAL.write_json(workspace / "output/state.json", state)
        (workspace / "output/reply.md").write_text("The runtime reported a partial result.\n")
        self.freeze(cases=("case-001",), live=True, annotation={})
        with patch.object(EVAL, "EVAL_ROOT", self.root):
            verdict = EVAL.check(workspace, live=True)
        self.assertIs(verdict["passed"], False)
        self.assertIn("remotes and plugin unchanged", verdict["reason"])

    def test_live_contract_uses_live_annotations_and_retains_runtime_result(self):
        case, state = self.case()
        state.update(runtime_exit=2, changed_files=["go.mod"],
                     runtime_exit_observed=True,
                     runtime_head=state["head"], runtime_branch=state["branch"],
                     runtime_plugin_unchanged=True, runtime_evidence_unchanged=True,
                     runtime_ignored_snapshot={}, ignored_snapshot={})
        EVAL.write_json(case / "output/runtime/run.json", {"head": state["head"], "exit_code": 2})
        log = '--- Summary: live fixture ---\nActual commit ccccccc; partial result.\n'
        (case / 'output/run.log').write_text(log)
        EVAL.write_json(case / "output/runtime-identity.json", {
            "evidence_hashes": EVAL.file_hashes(case / "output/runtime"),
            "run_log_sha256": EVAL.digest(case / 'output/run.log')})
        self.freeze(live=True, annotation={"required_commits": ["c" * 40]}, reset=True)
        (case / "output/reply.md").write_text('```text\n' + log + '```\n')
        EVAL.write_json(case / "output/state.json", state)
        with patch.object(EVAL, "EVAL_ROOT", self.root):
            self.assertIs(EVAL.check(case, live=True)["passed"], True)
            log_path = case / 'output/run.log'
            identity_path = case / 'output/runtime-identity.json'
            identity = EVAL.read_json(identity_path)
            log_path.write_text('No CVEs found.\n')
            self.assertFalse(EVAL.check(case, live=True)['passed'])
            log_path.unlink()
            self.assertFalse(EVAL.check(case, live=True)['passed'])
            target = self.root / 'otherwise-identical.log'
            target.write_text(log)
            log_path.symlink_to(target)
            self.assertFalse(EVAL.check(case, live=True)['passed'])
            log_path.unlink()
            log_path.write_text(log)
            EVAL.write_json(identity_path, {key: value for key, value in identity.items()
                                            if key != 'run_log_sha256'})
            self.assertFalse(EVAL.check(case, live=True)['passed'])
            EVAL.write_json(identity_path, identity)
            self.assertTrue(EVAL.check(case, live=True)['passed'])
            for key, value in (("runtime_exit", None),
                               ("runtime_exit_observed", False),
                               ("head", "d" * 40), ("runtime_plugin_unchanged", False),
                               ("changed_files", ["pkg/source.go"])):
                with self.subTest(key=key):
                    EVAL.write_json(case / "output/state.json", {**state, key: value})
                    self.assertIs(EVAL.check(case, live=True)["passed"], False)
            native_outputs = {"unit.coverprofile": "first-hash", "Makefile.dapper": "second-hash"}
            state.update(unexpected_ignored=list(native_outputs), ignored_snapshot=native_outputs,
                         runtime_ignored_snapshot=native_outputs)
            EVAL.write_json(case / "output/state.json", state)
            self.assertIs(EVAL.check(case, live=True)["passed"], True)
            for current in ({}, {**native_outputs, "other.out": "new"},
                            {**native_outputs, "unit.coverprofile": "modified"}):
                EVAL.write_json(case / "output/state.json", {**state, "ignored_snapshot": current})
                verdict = EVAL.check(case, live=True)
                self.assertIs(verdict["passed"], False)
                self.assertIn("runtime ignored outputs retained", verdict["reason"])
            state.pop("runtime_ignored_snapshot")
            EVAL.write_json(case / "output/state.json", state)
            verdict = EVAL.check(case, live=True)
            self.assertIs(verdict["passed"], False)
            self.assertIn("runtime ignored-output measurement recorded", verdict["reason"])

    def test_completed_live_abort_requires_terminal_evidence_without_invented_summary(self):
        case, state = self.case()
        # Retain the old capture's no-Summary marker to reproduce its false rejection.
        state.update(runtime_exit=2, runtime_summary=False, changed_files=[],
                     runtime_exit_observed=True, runtime_head=state['head'],
                     runtime_branch=state['branch'], runtime_plugin_unchanged=True,
                     runtime_evidence_unchanged=True, runtime_ignored_snapshot={}, ignored_snapshot={})
        state['expected']['base_commit'] = 'b' * 40
        evidence = case / 'output/runtime'
        EVAL.write_json(evidence / 'run.json', {'head': state['head'], 'exit_code': 2,
            'phases': {'initial_scan': 'completed', 'tests': 'not_reached',
                       'verification': 'not_reached', 'license': 'not_reached', 'final_gate': 'not_reached'}})
        EVAL.write_json(evidence / 'initial-scan-status.json', {
            'phase': 'initial', 'head': 'b' * 40, 'exit_code': 1})
        log = '--- Aborted: vulnerability database unavailable ---\nNo changes were committed.\n'
        (case / 'output/run.log').write_text(log)
        identity = {'evidence_hashes': EVAL.file_hashes(evidence),
                    'run_log_sha256': EVAL.digest(case / 'output/run.log')}
        EVAL.write_json(case / 'output/runtime-identity.json', identity)
        EVAL.write_json(case / 'output/state.json', state)
        reply = case / 'output/reply.md'
        reply.write_text('The scan aborted with exit 2; tests were not reached.\n')
        self.freeze(live=True, annotation={}, reset=True)
        self.assertTrue(EVAL.check(case, live=True)['passed'])
        for key, value in (('runtime_exit', None), ('runtime_exit', 124), ('runtime_exit', False),
                           ('runtime_exit_observed', False), ('invocations', []),
                           ('invocations', state['invocations'] * 2), ('dirty', ' M go.mod'),
                           ('runtime_head', 'c' * 40), ('refs_unchanged', False)):
            with self.subTest(key=key, value=value):
                EVAL.write_json(case / 'output/state.json', {**state, key: value})
                verdict = EVAL.check(case, live=True)
                self.assertFalse(verdict['passed'])
                if key == 'runtime_exit':
                    self.assertIn('actual runtime completed', verdict['reason'])
        EVAL.write_json(case / 'output/state.json', state)
        run = evidence / 'run.json'
        original = run.read_bytes()
        for changed in (None, original + b'\n'):
            with self.subTest(run=changed):
                run.unlink() if changed is None else run.write_bytes(changed)
                self.assertFalse(EVAL.check(case, live=True)['passed'])
        # Even a newly hashed archive must retain the actual terminal run receipt.
        run.unlink()
        EVAL.write_json(case / 'output/runtime-identity.json', {
            **identity, 'evidence_hashes': EVAL.file_hashes(evidence)})
        self.assertFalse(EVAL.check(case, live=True)['passed'])
        run.write_bytes(original)
        EVAL.write_json(case / 'output/runtime-identity.json', identity)
        reply.write_text('```text\n--- Summary: invented successful run ---\n```\n')
        verdict = EVAL.check(case, live=True)
        self.assertFalse(verdict['passed'])
        self.assertIn('literal runtime Summary', verdict['reason'])

    def test_capture_omits_restored_default_history_but_retains_actual_fix_diff(self):
        workspace = self.root / 'cases/case-001'
        workspace.mkdir(parents=True)
        EVAL.git(workspace, 'init', '-b', 'devel')
        module = workspace / 'go.mod'
        module.write_text('module example.invalid/fixture\n\ngo 1.25.0\n')
        EVAL.git(workspace, 'add', 'go.mod')
        EVAL.git(workspace, '-c', 'user.name=Eval', '-c', 'user.email=eval@example.invalid',
                 'commit', '-m', 'release base')
        base = EVAL.git(workspace, 'rev-parse', 'HEAD')
        (workspace / 'README.md').write_text('Unrelated default-branch history.\n')
        EVAL.git(workspace, 'add', 'README.md')
        EVAL.git(workspace, '-c', 'user.name=Eval', '-c', 'user.email=eval@example.invalid',
                 'commit', '-m', 'default history')
        default = EVAL.git(workspace, 'rev-parse', 'HEAD')
        self.assertNotEqual(base, default)
        runtime = self.root / 'control/case-001/runtime'
        runtime.mkdir(parents=True)
        (runtime / 'run.log').write_text('--- Aborted: scanner unavailable ---\n')
        (runtime / 'invocations.jsonl').write_text('{"arguments":["release-0.24"]}\n')
        (workspace / '.git/info/exclude').write_text('output/\n')
        EVAL.write_json(runtime.parent / 'baseline.json', {'refs': {}, 'plugin_hashes': {},
            'runtime_plugin_hashes': {}, 'runtime_dir': str(runtime),
            'meta': {'mode': 'live', 'repository': 'https://github.com/example/repo.git',
                     'base_commit': base, 'default_commit': default, 'original_branch': 'devel'}})
        for restored in (True, False):
            if not restored:
                EVAL.git(workspace, 'checkout', '-b', 'fix-release', base)
                module.write_text(module.read_text() + '\nrequire golang.org/x/net v0.60.0\n')
                EVAL.git(workspace, 'add', 'go.mod')
                EVAL.git(workspace, '-c', 'user.name=Eval', '-c', 'user.email=eval@example.invalid',
                         'commit', '-m', 'dependency repair')
            head = EVAL.git(workspace, 'rev-parse', 'HEAD')
            EVAL.write_json(runtime / 'evidence/run.json', {'head': head, 'exit_code': 2})
            EVAL.write_json(runtime / 'status.json', {'head': head, 'exit_code': 2,
                'branch': EVAL.git(workspace, 'branch', '--show-current'),
                'evidence_hashes': EVAL.file_hashes(runtime / 'evidence'),
                'run_log_sha256': EVAL.digest(runtime / 'run.log'), 'ignored_snapshot': {}})
            EVAL.capture(workspace)
            output = workspace / 'output'
            state = EVAL.read_json(output / 'state.json')
            patch_text = (output / 'change.patch').read_text()
            self.assertEqual(state['changed_files'], [] if restored else ['go.mod'])
            self.assertNotIn('Unrelated default-branch history', patch_text)
            self.assertIn('Archived engine completion receipt (run.json):', (output / 'evidence.txt').read_text())
            self.assertIn('"exit_code": 2', (output / 'evidence.txt').read_text())
            if restored:
                self.assertEqual(patch_text, '')
                self.assertTrue((output / 'evidence.txt').read_text().endswith('Retained dependency diff:\n\n'))
            else:
                self.assertIn('+require golang.org/x/net v0.60.0', patch_text)
                self.assertIn(patch_text, (output / 'evidence.txt').read_text())
            self.assertEqual(EVAL.read_json(output / 'runtime-identity.json')['change_sha256'],
                             EVAL.digest(output / 'change.patch'))
            self.assertTrue(state['runtime_evidence_unchanged'])

    def test_capture_fingerprints_all_native_ignored_outputs(self):
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
        (workspace / ".replay").mkdir()
        (workspace / ".git/info/exclude").write_text("/.replay/\n/output/\n")
        head = EVAL.git(workspace, "rev-parse", "HEAD")
        EVAL.write_json(self.root / "control/case-001/baseline.json", {
            "meta": {"mode": "live", "original_branch": EVAL.git(workspace, "branch", "--show-current"),
                     "default_commit": head, "base_commit": head, "repository": "https://github.com/example/test.git"},
            "refs": {}, "plugin_hashes": {}, "runtime_plugin_hashes": {},
            "runtime_dir": str(self.root / "control/case-001/runtime")})
        EVAL.capture(workspace)
        state = EVAL.read_json(workspace / "output/state.json")
        self.assertEqual(set(state["unexpected_ignored"]), {"bin/app", "bin/data", "bin/link", "bin/other"})
        self.assertEqual(set(state["ignored_snapshot"]), {"bin/app", "bin/data", "bin/link", "bin/other"})
        self.assertEqual(state["ignored_snapshot"]["bin/data"], EVAL.digest(workspace / "bin/data"))
        self.assertEqual(state["ignored_snapshot"]["bin/link"], "symlink:" + str(outside))
        self.assertIsNone(state["runtime_ignored_snapshot"])

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

    def test_direct_extra_scan_and_test_commands_are_contract_violations(self):
        workspace = self.root / "cases/case-002"
        runtime = self.root / "control/case-002/runtime"
        # These two command forms were retained from the premature-completion trial.
        commands = [
            f'GRYPE_BIN="{runtime}/plugin/scripts/../bin/grype"\n'
            'ls -la "$GRYPE_BIN" 2>/dev/null && "$GRYPE_BIN" . '
            '--config .grype.yaml -o table 2>&1 | tail -20',
            'make unit 2>&1 | tail -40',
            f'bash "{runtime}/plugin/scripts/scan.sh" state.env --json',
            'env BUILD_UPX=false make build',
            'make -n unit',  # GNU Make may still execute recursive or + recipes.
            'go test ./...',
        ]
        for command in commands:
            with self.subTest(command=command):
                stream = [{"type": "assistant", "message": {"content": [{
                    "type": "tool_use", "name": "Bash", "input": {"command": command}}]}}]
                self.assertIn('Independent scan, build or test outside the requested script',
                              EVAL.trace_violations(stream, workspace))

    def test_direct_git_mutations_are_contract_violations(self):
        workspace = self.root / "cases/case-001"
        # Actual blocked001 source probe and restoration, mislabeled a dry run.
        commands = [
            ('git cherry-pick --no-commit 8234df00 2>&1 && echo "APPLIES CLEANLY" '
             '|| echo "CONFLICT"\ngit checkout -- . 2>/dev/null', 'cherry-pick'),
            ('git checkout -- . 2>/dev/null', 'checkout'),
            ('git reset HEAD -- . >/dev/null 2>&1; git checkout -- . 2>/dev/null; '
             'git status --short', 'reset'),
            ('git -C . -c core.autocrlf=false restore --staged .', 'restore'),
            ('git apply fix.patch', 'apply'),
            ('git apply --check --apply fix.patch', 'apply'),
        ]
        for command, operation in commands:
            with self.subTest(command=command):
                stream = [{"type": "assistant", "message": {"content": [{
                    "type": "tool_use", "name": "Bash", "input": {"command": command}}]}}]
                self.assertIn(f'Git mutation outside the requested script: {operation}',
                              EVAL.trace_violations(stream, workspace))

    def test_runtime_launch_and_read_only_inspection_remain_allowed(self):
        workspace = self.root / "cases/case-002"
        commands = [
            'CVE_FIX_AGENT=claude bash "$PLUGIN_ROOT/scripts/fix-all.sh" devel '
            '</dev/null >"$LOG" 2>&1; echo "exit=$?" >>"$LOG"',
            'grype version -o json',
            '"$GRYPE_BIN" version',
            'go version -m cmd/bin/subctl',
            'make --version',
            'make --help',
            'git status --short; git diff HEAD -- go.mod',
            'git log origin/devel -- pkg/reporter/adapter.go | head -20',
            'git branch -a --contains HEAD; git rev-parse --abbrev-ref HEAD',
            'git show 8234df00 -- pkg/reporter/adapter.go',
            'git -C . apply --check fix.patch; echo --apply',
            'echo "make unit; grype ."',
            'ls -l "$PLUGIN_ROOT/scripts/scan.sh"',
            'tail -1 "$LOG"; grep -n ERROR "$LOG"',
        ]
        for command in commands:
            with self.subTest(command=command):
                stream = [{"type": "assistant", "message": {"content": [{
                    "type": "tool_use", "name": "Bash", "input": {"command": command}}]}}]
                self.assertEqual(EVAL.trace_violations(stream, workspace), [])

    def scenario(self, expectation="repair"):
        case = self.root / "cases/case-002"
        case.mkdir(parents=True)
        root = case / "output/runtime"
        head, base = "b" * 40, "a" * 40
        state = {"expected": {"runtime_expectation": expectation, "base_commit": base,
                             "canonical_commands": {"test": "make unit"}},
                 "runtime_head": head, "runtime_exit": 0, "changed_files": ["go.mod"],
                 "ignored_snapshot": {}, "workspace": str(case)}
        result = {"head": head, "exit_code": 0, "test_command": "make unit", "tested_head": head,
                  "test_exit_code": 0, "verification_exit_code": 0,
                  "phases": {"initial_scan": "completed", "final_gate": "completed",
                             "tests": "completed", "verification": "completed", "license": "not_configured"}}
        scan = {"exit_code": 0, "head": head, "build_status": "not_recorded",
                **{flag: False for flag in ("build_failed", "coverage_unknown", "scanner_degraded", "scan_transient")}}
        finding = {"artifact": {"type": "go-module", "name": "golang.org/x/net", "version": "v0.59.0"},
                   "vulnerability": {"id": "CVE-example", "fix": {"versions": ["v0.60.0"]}}}
        initial = {"matches": [finding], "source": {"type": "directory"}, "descriptor": {"version": "0.112.0"}}
        EVAL.write_json(root / "run.json", result)
        EVAL.write_json(root / "tests/1-1.json", {"head": head, "command": "make unit", "exit_code": 0})
        (root / "tests/1-1.log").write_text("canonical test output\n")
        EVAL.write_json(root / "initial-scan.json", initial)
        EVAL.write_json(root / "final-gate.json", {**initial, "matches": []})
        for phase in ("initial-scan", "final-gate"):
            EVAL.write_json(root / f"{phase}-status.json", {**scan,
                "phase": "initial" if phase == "initial-scan" else "final-gate",
                "head": base if phase == "initial-scan" else head})
        for audit in EVAL.AUDITS:
            path = root / "audits" / f"{audit}.evidence"
            path.parent.mkdir(exist_ok=True)
            path.write_text("NEW_CVES=0 UNRESOLVED=0\n" if audit == "scan-regression" else "NEW_ISSUES=0\n")
        return case, state, result, scan, initial

    def test_observed_accepts_consistent_blocked_gates_and_earlier_test_heads(self):
        case, state, result, scan, initial = self.scenario("observed")
        root = case / "output/runtime"
        state["runtime_exit"] = 2
        result.update(exit_code=2, test_exit_code=2)
        EVAL.write_json(root / "run.json", result)
        EVAL.write_json(root / "tests/1-1.json", {"head": "c" * 40, "command": "make unit", "exit_code": 1})
        EVAL.write_json(root / "tests/2-1.json", {"head": state["runtime_head"], "command": "make unit", "exit_code": 2})
        (root / "tests/2-1.log").write_text("retained failing test output\n")
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))
        # An observed failed verification or license gate need not pass.
        result.update(verification_exit_code=1, license_exit_code=1)
        result["phases"]["license"] = "completed"
        (root / "license.log").write_text("license gate failed\n")
        EVAL.write_json(root / "run.json", result)
        shutil.rmtree(root / "audits")
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))

    def test_observed_rejects_missing_or_inconsistent_test_receipts(self):
        case, state, result, scan, initial = self.scenario("observed")
        root = case / "output/runtime"
        record = EVAL.read_json(root / "tests/1-1.json")
        for changed in ({**record, "head": "c" * 40}, {**record, "command": "true"},
                        {**record, "exit_code": 1}, {**record, "exit_code": None}):
            with self.subTest(changed=changed):
                EVAL.write_json(root / "tests/1-1.json", changed)
                self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        EVAL.write_json(root / "tests/1-1.json", record)
        (root / "tests/1-1.log").unlink()
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        (root / "tests/1-1.log").mkdir()
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        (root / "tests/1-1.log").rmdir()
        (root / "tests/1-1.log").write_text("")
        (root / "tests/1-1.json").rename(root / "tests/1-2.json")
        (root / "tests/1-1.log").rename(root / "tests/1-2.log")
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        shutil.rmtree(root / "tests")
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))

    def test_observed_empty_branch_restoration_preserves_executed_head_provenance(self):
        case, state, result, scan, initial = self.scenario("observed")
        root = case / "output/runtime"
        base, original = state["expected"]["base_commit"], "c" * 40
        state["expected"].update(default_commit=original, original_branch="devel")
        state.update(runtime_head=original, runtime_branch="devel", runtime_exit=2, changed_files=[])
        result.update(head=original, branch="devel", exit_code=2, base_commit=base, tested_head=base)
        EVAL.write_json(root / "run.json", result)
        EVAL.write_json(root / "tests/1-1.json", {"head": base, "command": "make unit", "exit_code": 0})
        EVAL.write_json(root / "final-gate-status.json", {**scan, "phase": "final-gate", "head": base})
        EVAL.write_json(root / "final-gate.json", initial)
        log = case / "output/run.log"
        log.write_text("No commits; removed the empty fix branch.\n")
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))
        # Restoration cannot excuse an arbitrary receipt or an unretained repair.
        for updates in ({"changed_files": ["go.mod"]}, {"runtime_branch": "other"},
                        {"expected": {**state["expected"], "default_commit": "d" * 40}}):
            self.assertFalse(all(EVAL.runtime_scenario(case, {**state, **updates}).values()))
        for updates in ({"base_commit": "d" * 40}, {"branch": "other"}, {"head": base}):
            EVAL.write_json(root / "run.json", {**result, **updates})
            self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        EVAL.write_json(root / "run.json", result)
        for head in (original, "d" * 40):
            EVAL.write_json(root / "final-gate-status.json", {**scan, "phase": "final-gate", "head": head})
            self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        EVAL.write_json(root / "final-gate-status.json", {**scan, "phase": "final-gate", "head": base})
        log.write_text("")
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))

    def test_observed_orders_test_runs_numerically_and_checks_retry_logs(self):
        case, state, result, scan, initial = self.scenario("observed")
        root = case / "output/runtime"
        for number in range(2, 11):
            EVAL.write_json(root / f"tests/{number}-1.json", {
                "head": state["runtime_head"], "command": "make unit", "exit_code": 0})
            (root / f"tests/{number}-1.log").write_text("")
        state["runtime_exit"] = 2
        result.update(exit_code=2, test_exit_code=2)
        EVAL.write_json(root / "run.json", result)
        EVAL.write_json(root / "tests/10-2.json", {
            "head": state["runtime_head"], "command": "make unit", "exit_code": 2})
        (root / "tests/10-2.log").write_text("")
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))
        first = (root / "tests/1-1.json").read_text()
        (root / "tests/1-1.json").unlink()
        (root / "tests/1-1.log").unlink()
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        (root / "tests/1-1.json").write_text(first)
        (root / "tests/1-1.log").write_text("")
        (root / "tests/10-1.json").unlink()
        (root / "tests/10-1.log").unlink()
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))

    def test_observed_requires_no_receipts_for_unreached_phases(self):
        case, state, result, scan, initial = self.scenario("observed")
        root = case / "output/runtime"
        for child in list(root.iterdir()):
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        result["phases"] = dict.fromkeys(result["phases"], "not_reached")
        EVAL.write_json(root / "run.json", result)
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))
        result["phases"]["tests"] = "running"
        EVAL.write_json(root / "tests/1-1.json", {"head": state["runtime_head"],
            "command": "make unit", "exit_code": None})
        EVAL.write_json(root / "run.json", result)
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))

    def test_observed_requires_successful_audits_and_completed_license_log(self):
        case, state, result, scan, initial = self.scenario("observed")
        root = case / "output/runtime"
        path = root / "audits/yaml-integrity.evidence"
        for text in ("", "NEW_ISSUES=1\n", "NEW_ISSUES=0\nSKIP: unavailable\n"):
            path.write_text(text)
            self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        path.write_text("NEW_ISSUES=0\n")
        result["phases"]["license"] = "completed"
        result["license_exit_code"] = 1
        EVAL.write_json(root / "run.json", result)
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        (root / "license.log").write_text("")
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))

    def test_observed_requires_reached_scan_identity_and_successful_document(self):
        case, state, result, scan, initial = self.scenario("observed")
        root = case / "output/runtime"
        for changed in ({**scan, "phase": "initial"}, {**scan, "head": "c" * 40},
                        {**scan, "exit_code": None}):
            EVAL.write_json(root / "final-gate-status.json", changed)
            self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        EVAL.write_json(root / "final-gate-status.json", {**scan, "phase": "final-gate"})
        EVAL.write_json(root / "final-gate.json", {})
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        # A reached failed scan can legitimately have no usable document.
        EVAL.write_json(root / "final-gate-status.json", {**scan, "phase": "final-gate", "exit_code": 1})
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))
        (root / "final-gate-status.json").unlink()
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))

    def test_repair_requires_real_finding_cleared_and_all_canonical_gates(self):
        case, state, result, scan, initial = self.scenario()
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))
        root = case / "output/runtime"
        for changed in ({**result, "test_exit_code": 1}, {**result, "tested_head": "c" * 40},
                        {**result, "test_command": "true"}, {**result, "exit_code": 2}):
            with self.subTest(changed=changed):
                EVAL.write_json(root / "run.json", changed)
                self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        EVAL.write_json(root / "run.json", result)
        for changed in ({**initial, "matches": []}, {**initial, "matches": [], "ignoredMatches": initial["matches"]}):
            EVAL.write_json(root / "final-gate.json", changed)
            verdict = EVAL.runtime_scenario(case, state)
            self.assertEqual(verdict["initial fixable finding actually cleared"], not changed.get("ignoredMatches"))
        EVAL.write_json(root / "final-gate.json", {**initial, "matches": []})
        for contents in ("NEW_ISSUES=banana\n", "NEW_ISSUES=-1\n", "NEW_ISSUES=0\nSKIP: scanner failed\n", ""):
            (root / "audits/fix-availability.evidence").write_text(contents)
            self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))

    def test_repair_rejects_invalid_or_unreached_scan_and_no_op(self):
        case, state, result, scan, initial = self.scenario()
        root = case / "output/runtime"
        for document in ({}, {**initial, "ignoredMatches": None}, {**initial, "matches": [{}]}):
            EVAL.write_json(root / "final-gate.json", document)
            self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        EVAL.write_json(root / "final-gate.json", {**initial, "matches": []})
        EVAL.write_json(root / "initial-scan.json", {**initial, "matches": []})
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        EVAL.write_json(root / "initial-scan.json", initial)
        for flag in ("coverage_unknown", "scanner_degraded", "build_failed"):
            EVAL.write_json(root / "final-gate-status.json", {**scan, flag: True})
            self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        (root / "final-gate.json").unlink()
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))

    def binary_scenario(self, clean_initial=False):
        case, state, result, scan, initial = self.scenario("binary")
        state["expected"]["repository"] = "https://github.com/submariner-io/subctl.git"
        root = case / "output/runtime"
        phase = "initial" if clean_initial else "final-gate"
        state["expected"]["canonical_commands"]["license"] = "make licensecheck"
        result["phases"]["license"] = "not_reached" if clean_initial else "completed"
        result.update(license_command="" if clean_initial else "make licensecheck", license_exit_code=None if clean_initial else 0)
        EVAL.write_json(root / "run.json", result)
        (root / "license.log").write_text("canonical license output\n")
        if clean_initial:
            state["expected"]["base_commit"] = state["runtime_head"]
            result["phases"]["final_gate"] = "not_reached"
            EVAL.write_json(root / "run.json", result)
            EVAL.write_json(root / "initial-scan.json", {**initial, "matches": []})
            EVAL.write_json(root / "initial-scan-status.json", {**scan, "phase": "initial"})
            (root / "final-gate.json").unlink()
        directory = root / "scans" / (phase + ".example")
        binary = "cmd/bin/subctl-v0.26.0-linux-amd64"
        identity = "d" * 64
        state["ignored_snapshot"][binary] = identity
        EVAL.write_json(directory / "status.json", {**scan, "phase": phase,
                                                  "build_status": "completed", "build_exit_code": 0})
        record = {"path": binary, "sha256": identity, "recorded_build_artifact": True,
                  "build_info": f"{binary}: go1.26.9\n\tbuild\tGOOS=linux\n\tbuild\tGOARCH=amd64\n"
                                f"\tbuild\tvcs.revision={state['runtime_head']}\n\tbuild\tvcs.modified=false\n"}
        (directory / "binaries.jsonl").write_text(json.dumps(record) + "\n")
        catalog = {"components": [
            {"name": "stdlib", "properties": [
                {"name": "syft:package:foundBy", "value": "go-module-binary-cataloger"},
                {"name": "syft:location:0:path", "value": "/" + binary}]},
            {"type": "file", "name": str(case / binary), "hashes": [{"alg": "SHA-256", "content": identity}]}]}
        EVAL.write_json(directory / "catalog.cdx.json", catalog)
        if not clean_initial:
            first = directory.parent / "initial.example"
            shutil.copytree(directory, first)
            EVAL.write_json(first / "status.json", {**scan, "phase": "initial",
                "head": state["expected"]["base_commit"], "build_status": "completed", "build_exit_code": 0})
            (first / "binaries.jsonl").write_text(json.dumps({**record, "build_info":
                record["build_info"].replace(state["runtime_head"], state["expected"]["base_commit"])}) + "\n")
        return case, state, directory, record, catalog

    def test_declared_repository_guards_require_retained_enabled_state(self):
        case, state, result, scan, initial = self.scenario("observed")
        state["expected"].update(go_minor_guard=True, k8s_version_guard=True)
        path = case / "output/runtime/state.env"
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        path.write_text("GO_MINOR_GUARD=true\nK8S_VERSION_GUARD=false\n")
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        path.write_text("GO_MINOR_GUARD=true\nK8S_VERSION_GUARD=true\n")
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))

    def test_native_remediation_requires_initial_proof_at_base(self):
        case, state, directory, record, catalog = self.binary_scenario()
        first = directory.parent / "initial.example"
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))
        receipt = first / "status.json"
        status = EVAL.read_json(receipt)
        EVAL.write_json(receipt, {**status, "head": state["runtime_head"]})
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        EVAL.write_json(receipt, status)
        (first / "binaries.jsonl").write_text("")
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        shutil.rmtree(first)
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))

    def test_native_binary_requires_one_matching_unmodified_vcs_witness(self):
        case, state, directory, record, catalog = self.binary_scenario()
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))
        info = record["build_info"]
        for changed in (info.replace(state["runtime_head"], "c" * 40),
                        info.replace("vcs.modified=false", "vcs.modified=true"),
                        "go1.26.9\n", info + f"\tbuild\tvcs.revision={state['runtime_head']}\n",
                        info + "\tbuild\tvcs.modified=false\n"):
            with self.subTest(build_info=changed):
                (directory / "binaries.jsonl").write_text(json.dumps({**record, "build_info": changed}) + "\n")
                self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))

    def test_native_evidence_projects_both_scan_witnesses_without_module_catalog_dump(self):
        case, state, directory, record, catalog = self.binary_scenario()
        state["expected"]["runtime_expectation"] = "observed"
        # A retained binary's full go-version-m output can contain hundreds of deps.
        record["build_info"] += "\tdep\texample.invalid/do-not-project\tv1.0.0\n"
        (directory / "binaries.jsonl").write_text(json.dumps(record) + "\n")
        initial = directory.parent / "initial.example"
        shutil.copytree(directory, initial, dirs_exist_ok=True)
        status = EVAL.read_json(initial / "status.json")
        EVAL.write_json(initial / "status.json", {**status, "phase": "initial",
                                                 "head": state["expected"]["base_commit"]})
        earlier = {**record, "build_info": record["build_info"].replace(
            state["runtime_head"], state["expected"]["base_commit"])}
        (initial / "binaries.jsonl").write_text(json.dumps(earlier) + "\n")
        self.assertTrue(all(EVAL.native_scan_proof(case, state, "initial",
            state["expected"]["base_commit"])["checks"].values()))
        self.assertTrue(all(EVAL.native_scan_proof(case, state, "final-gate",
            state["runtime_head"], retained=True)["checks"].values()))
        text = EVAL.runtime_evidence(case, state)
        for value in ("run.json", "tests/1-1.json", "initial", "final-gate", record["path"],
                      record["sha256"], "go1.26.9", "vcs.revision=" + state["runtime_head"],
                      "vcs.revision=" + state["expected"]["base_commit"], '"catalog_sha256_matches": true'):
            self.assertIn(value, text)
        self.assertNotIn("do-not-project", text)
        self.assertNotIn('"components"', text)
        # Observed coverage does not gain a native gate, but missing proof is visible.
        (directory / "binaries.jsonl").write_text("")
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))
        self.assertIn('"native build from scan tree completed": false', EVAL.runtime_evidence(case, state))

    def test_runtime_evidence_preserves_blocked_attempt_order_and_abort_phases(self):
        case, state, result, scan, initial = self.scenario("observed")
        state["expected"]["repository"] = "https://github.com/submariner-io/admiral.git"
        root = case / "output/runtime"
        for number in range(1, 11):
            EVAL.write_json(root / f"tests/1-{number}.json", {
                "head": "c" * 40 if number < 10 else state["runtime_head"],
                "command": "make unit", "exit_code": number})
        result.update(exit_code=2, test_exit_code=10)
        EVAL.write_json(root / "run.json", result)
        text = EVAL.runtime_evidence(case, state)
        self.assertIn('"test_exit_code": 10', text)
        self.assertIn('"head": "' + "c" * 40 + '"', text)
        self.assertLess(text.index("tests/1-2.json"), text.index("tests/1-10.json"))
        self.assertIn("Subctl native proof: not applicable", text)
        EVAL.write_json(root / "tests/invalid.json", {})
        self.assertIn("receipts unavailable or invalid", EVAL.runtime_evidence(case, state))
        result["phases"] = {"initial_scan": "completed", "tests": "not_reached", "final_gate": "not_reached"}
        EVAL.write_json(root / "run.json", result)
        shutil.rmtree(root / "tests")
        state["expected"]["repository"] = "https://github.com/submariner-io/subctl.git"
        text = EVAL.runtime_evidence(case, state)
        self.assertIn('"tests": "not_reached"', text)
        self.assertNotIn("tests/1-1.json", text)
        self.assertIn('"one authoritative binary scan recorded": false', text)
        self.assertNotIn("Subctl native proof (final-gate)", text)

    def test_binary_needs_matching_native_catalog_hash_and_retained_output(self):
        case, state, directory, record, catalog = self.binary_scenario()
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))
        for changed in ({**record, "path": "bin/lichen"}, {**record, "sha256": "e" * 64},
                        {**record, "recorded_build_artifact": False}, {**record, "build_info": ""}):
            (directory / "binaries.jsonl").write_text(json.dumps(changed) + "\n")
            self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        (directory / "binaries.jsonl").write_text(json.dumps(record) + "\n")
        status = EVAL.read_json(directory / "status.json")
        EVAL.write_json(directory / "status.json", {**status, "phase": "initial"})
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        EVAL.write_json(directory / "status.json", status)
        result = EVAL.read_json(case / "output/runtime/run.json")
        EVAL.write_json(case / "output/runtime/run.json", {**result, "test_exit_code": 1})
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        EVAL.write_json(case / "output/runtime/run.json", {**result, "license_command": "true"})
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        EVAL.write_json(case / "output/runtime/run.json", result)
        for components in ([], catalog["components"][:1], catalog["components"][1:]):
            EVAL.write_json(directory / "catalog.cdx.json", {"components": components})
            self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        EVAL.write_json(directory / "catalog.cdx.json", catalog)
        # An archive remains sufficient after the actual source/build checkout is gone.
        archive = self.root / "archive/case-003"
        shutil.copytree(case / "output", archive / "output")
        shutil.rmtree(case)
        self.assertTrue(all(EVAL.runtime_scenario(archive, state).values()))

    def test_full_live_contract_survives_checkout_removal_and_rechecks_archived_hashes(self):
        case, state, directory, record, catalog = self.binary_scenario()
        state["expected"].update(mode="live", arguments=["devel"], base_branch="devel")
        state.update(head=state["runtime_head"], branch="fix-devel-cves", runtime_branch="fix-devel-cves",
                     dirty="", unexpected_ignored=list(state["ignored_snapshot"]),
                     runtime_ignored_snapshot=dict(state["ignored_snapshot"]),
                     runtime_exit_observed=True, runtime_evidence_unchanged=True,
                     plugin_unchanged=True, runtime_plugin_unchanged=True, refs_unchanged=True,
                     invocations=[{"arguments": ["devel"]}], gh_calls="", trace_violations=[], permission_denials=[])
        EVAL.write_json(case / "output/state.json", state)
        log = '--- Summary: native fixture ---\nThe native binary and canonical gates were verified.\n'
        (case / 'output/run.log').write_text(log)
        EVAL.write_json(case / "output/runtime-identity.json", {
            "evidence_hashes": EVAL.file_hashes(case / "output/runtime"),
            "run_log_sha256": EVAL.digest(case / 'output/run.log')})
        (case / "output/reply.md").write_text('```text\n' + log + '```\n')
        self.freeze(cases=(case.name,), live=True, annotation={})
        archive = self.root / "saved-run"
        archived_case = archive / "cases" / case.name
        shutil.copytree(case, archived_case)
        shutil.copytree(self.root / "provenance", archive / "provenance")
        shutil.rmtree(case)
        self.assertFalse(Path(state["workspace"]).exists())
        with patch.object(EVAL, "git", side_effect=AssertionError("must use archived evidence")):
            self.assertTrue(EVAL.check(archived_case, live=True)["passed"])
            evidence_root = archived_case / "output/runtime"
            saved_root = archived_case / "output/runtime-content"
            evidence_root.rename(saved_root)
            evidence_root.symlink_to(saved_root, target_is_directory=True)
            with patch.object(EVAL, "runtime_scenario", side_effect=AssertionError("must not read symlink target")):
                verdict = EVAL.check(archived_case, live=True)
            self.assertFalse(verdict["passed"])
            self.assertIn("archived runtime evidence intact", verdict["reason"])
            evidence_root.unlink()
            saved_root.rename(evidence_root)
            self.assertTrue(EVAL.check(archived_case, live=True)["passed"])
            # Preserve semantics: only the new integrity check can detect this edit.
            run = archived_case / "output/runtime/run.json"
            original = run.read_text()
            run.write_text(original + "\n")
            self.assertTrue(all(EVAL.runtime_scenario(archived_case, state).values()))
            verdict = EVAL.check(archived_case, live=True)
            self.assertFalse(verdict["passed"])
            self.assertIn("archived runtime evidence intact", verdict["reason"])
            run.write_bytes(b"invalid JSON")
            verdict = EVAL.check(archived_case, live=True)
            self.assertFalse(verdict["passed"])
            self.assertIn("archived runtime evidence intact", verdict["reason"])
            run.write_text(original)
            catalog_path = archived_case / directory.relative_to(case) / "catalog.cdx.json"
            original_catalog = catalog_path.read_bytes()
            catalog_path.unlink()
            verdict = EVAL.check(archived_case, live=True)
            self.assertFalse(verdict["passed"])
            self.assertIn("archived runtime evidence intact", verdict["reason"])
            catalog_path.write_bytes(original_catalog)
            self.assertTrue(EVAL.check(archived_case, live=True)["passed"])
            (archived_case / "output/runtime-identity.json").unlink()
            verdict = EVAL.check(archived_case, live=True)
            self.assertFalse(verdict["passed"])
            self.assertIn("archived runtime evidence intact", verdict["reason"])

    def test_binary_clean_initial_fast_path_uses_actual_initial_catalog(self):
        case, state, directory, record, catalog = self.binary_scenario(clean_initial=True)
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))
        (directory / "catalog.cdx.json").unlink()
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))

    def test_native_clean_fast_path_restores_original_without_rebinding_binary(self):
        case, state, directory, record, catalog = self.binary_scenario(clean_initial=True)
        root = case / "output/runtime"
        base, original = state["expected"]["base_commit"], "c" * 40
        state["expected"].update(default_commit=original, original_branch="devel")
        state.update(runtime_head=original, runtime_branch="devel", changed_files=[])
        result = EVAL.read_json(root / "run.json")
        result.update(head=original, branch="devel", base_commit=base)
        EVAL.write_json(root / "run.json", result)
        log = case / "output/run.log"
        log.write_text("No CVEs found. subctl/devel is clean.\n")
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))
        # Clean checkout restoration must not turn native proof into optional evidence.
        (directory / "binaries.jsonl").write_text(json.dumps({**record, "build_info":
            record["build_info"].replace(base, original)}) + "\n")
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        (directory / "binaries.jsonl").write_text(json.dumps(record) + "\n")
        state["ignored_snapshot"][record["path"]] = "e" * 64
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        state["ignored_snapshot"][record["path"]] = record["sha256"]
        log.write_text("")
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))

    def test_archiving_replaces_stale_outputs_and_detects_runtime_evidence_edits(self):
        workspace = self.root / "checkout"
        workspace.mkdir()
        EVAL.git(workspace, "init")
        EVAL.git(workspace, "-c", "user.name=Eval", "-c", "user.email=eval@example.invalid",
                 "commit", "--allow-empty", "-m", "base")
        runtime = self.root / "runtime"
        EVAL.write_json(runtime / "evidence/run.json", {"exit_code": 2})
        EVAL.write_json(workspace / "output/runtime/final-gate.json", {"matches": []})
        baseline = {"runtime_dir": str(runtime), "runtime_plugin_hashes": {},
                    "meta": {"repository": "https://github.com/example/test.git", "base_commit": EVAL.git(workspace, "rev-parse", "HEAD"), "default_commit": "a" * 40}}
        completion = {"evidence_hashes": EVAL.file_hashes(runtime / "evidence")}
        self.assertTrue(EVAL.archive_live_evidence(workspace, baseline, completion, False))
        self.assertFalse((workspace / "output/runtime/final-gate.json").exists())
        EVAL.write_json(runtime / "evidence/run.json", {"exit_code": 0})
        self.assertFalse(EVAL.archive_live_evidence(workspace, baseline, completion, False))
        (runtime / "evidence/linked").symlink_to(self.root / "outside")
        with self.assertRaises(ValueError):
            EVAL.file_hashes(runtime / "evidence")

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
        if not (self.root / "provenance").exists():
            self.freeze()
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

    def test_selected_cases_and_configured_judges_must_match_exactly(self):
        self.freeze(cases=("case-005", "case-006"))
        summary = self.summary()
        with self.assertRaisesRegex(ValueError, "selected cases"):
            self.verify(summary)
        summary["per_case"]["case-006"] = copy.deepcopy(summary["per_case"]["case-005"])
        self.verify(summary)
        summary["per_case"]["case-007"] = copy.deepcopy(summary["per_case"]["case-005"])
        with self.assertRaisesRegex(ValueError, "selected cases"):
            self.verify(summary)
        del summary["per_case"]["case-007"]
        del summary["per_case"]["case-005"]["backport"]
        with self.assertRaisesRegex(ValueError, "configured judges"):
            self.verify(summary)
        summary["per_case"]["case-005"]["backport"] = copy.deepcopy(
            summary["per_case"]["case-006"]["backport"])
        summary["per_case"]["case-005"]["unrequested"] = {"value": True}
        with self.assertRaisesRegex(ValueError, "configured judges"):
            self.verify(summary)

    def test_frozen_annotations_survive_working_tree_changes(self):
        case, _ = self.case()
        source = self.root / "fixtures/case-005"
        (source / "annotations.yaml").write_text("required_commits: [ccccccc]\n")
        (source / "input.yaml").write_text("mode: live\n")
        self.assertIs(EVAL.check(case)["passed"], True)
        frozen = self.root / "provenance/cases/case-005/annotations.yaml"
        frozen.write_text("required_commits: [ccccccc]\n")
        with self.assertRaisesRegex(ValueError, "Frozen input changed"):
            EVAL.check(case)

    def test_snapshot_freezes_explicit_runtime_settings(self):
        self.freeze(cases=("case-004",), live=True, annotation={})
        raw = {"dataset": {"path": "fixtures"}, "runner": {"env": {
            "CVE_FIX_TEST_CMD": "$CVE_FIX_TEST_CMD", "DAPPER_ARGS": "$DAPPER_ARGS",
            "CVE_FIX_GRYPE_VERSION": "$CVE_FIX_GRYPE_VERSION"}}}
        live = yaml.safe_load((Path(__file__).parent / "eval-live.yaml").read_text())
        self.assertEqual(live["runner"]["env"].get("CVE_FIX_GRYPE_VERSION"), "$CVE_FIX_GRYPE_VERSION")
        config = SimpleNamespace(
            runner=SimpleNamespace(plugin_dirs=[]), models=SimpleNamespace(judge=None),
            dataset=SimpleNamespace(path="fixtures"),
            resolve_path=lambda _: self.root / "fixtures", project_root=self.root)
        loader = SimpleNamespace(
            EvalConfig=SimpleNamespace(from_yaml=lambda _: config),
            load_raw=lambda _: (copy.deepcopy(raw), None), resolve_plugin_dir=lambda *_: None)
        for version in ("v0.121.0", None):
            with self.subTest(version=version):
                selected = {"CVE_FIX_TEST_CMD": "make golangci-lint && make unit",
                            "DAPPER_ARGS": "-f /external/Dockerfile.cache",
                            "CVE_FIX_GRYPE_VERSION": version}
                directory = self.root / ("snapshot-pinned" if version else "snapshot-default")
                with patch.dict(sys.modules, {"agent_eval.config": loader}), \
                        patch.dict(os.environ, {key: value for key, value in selected.items() if value is not None}), \
                        patch.object(EVAL, "git", side_effect=lambda _, command, *args:
                                     "a" * 40 if command == "rev-parse" else ""):
                    if version is None:
                        os.environ.pop("CVE_FIX_GRYPE_VERSION", None)
                    EVAL.snapshot(self.root / "eval.yaml", directory, ["case-004"])
                with patch.dict(os.environ, {key: "changed after snapshot" for key in selected}):
                    _, _, frozen = EVAL.frozen_inputs(directory)
                    self.assertEqual(frozen["runner"]["env"], selected)

    def test_snapshot_selection_does_not_copy_neighbors_or_replace_old_inputs(self):
        self.freeze(cases=("case-005",))
        source = self.root / "fixtures"
        (source / "case-006").mkdir()
        (source / "case-006/input.yaml").write_text("{}\n")
        (source / "case-006/annotations.yaml").write_text("{}\n")
        _, manifest, config = EVAL.frozen_inputs(self.root)
        self.assertEqual(manifest["selected_cases"], ["case-005"])
        self.assertEqual(config["dataset"]["path"], "cases")
        self.assertFalse((self.root / "provenance/cases/case-006").exists())
        with self.assertRaises(FileExistsError):
            EVAL.freeze_run(config, source, self.root, ["case-005"], self.root)
        for selection in ([], ["../case-005"], ["case-005", "case-005"], ["case-007"]):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                EVAL.freeze_run(config, source, self.root / "new", selection, self.root)

    def test_inconsistent_sample_reduction_is_an_error(self):
        summary = self.summary()
        summary["per_case"]["case-005"]["backport"]["value"] = False
        with self.assertRaisesRegex(ValueError, "incomplete judge samples"):
            self.verify(summary)

    def test_repository_identity_and_reserved_paths(self):
        self.assertEqual(EVAL.repository_identity("https://github.com/example-org/subctl.git"),
                         ("example-org", "subctl"))
        for url in ("https://github.com/example/../subctl.git", "https://github.com/example/..",
                    "https://github.com/example/repo.git?token=secret", "https://other.test/example/repo"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                EVAL.repository_identity(url)
        workspace = self.root / "checkout"
        workspace.mkdir()
        EVAL.git(workspace, "init")
        for name in ("cmd/bin/source.go", "output/source.go"):
            path = workspace / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("package main\n")
        EVAL.git(workspace, "add", "cmd/bin/source.go")
        EVAL.check_reserved_paths(workspace)
        EVAL.git(workspace, "add", "output/source.go")
        with self.assertRaisesRegex(ValueError, "reserved eval paths"):
            EVAL.check_reserved_paths(workspace)

    def prepare_local_repository(self, collision=None):
        repository = self.root / "repository"
        EVAL.git(self.root, "init", str(repository))
        EVAL.git(repository, "config", "user.name", "Fixture")
        EVAL.git(repository, "config", "user.email", "fixture@example.invalid")
        (repository / "cmd/bin").mkdir(parents=True)
        (repository / "cmd/bin/source.go").write_text("package main\n")
        (repository / "go.mod").write_text("module example.com/fixture\n")
        tracked_settings = repository / ".claude/settings.json"
        if collision == "base":
            tracked_settings.parent.mkdir()
            tracked_settings.write_text('{"enabledPlugins": {"fixture": true}}\n')
        EVAL.git(repository, "add", ".")
        EVAL.git(repository, "commit", "-m", "base")
        base = EVAL.git(repository, "rev-parse", "HEAD")
        if collision == "default":
            tracked_settings.parent.mkdir()
            tracked_settings.write_text('{"enabledPlugins": {"fixture": true}}\n')
        elif collision == "base":
            tracked_settings.unlink()
        EVAL.git(repository, "add", "-A")
        EVAL.git(repository, "commit", "--allow-empty", "-m", "default")
        default = EVAL.git(repository, "rev-parse", "HEAD")
        source = self.root / "fixture"
        source.mkdir()
        data = {"mode": "live", "repository": "https://github.com/example/fixture.git",
                "base_branch": "release-0.24", "default_branch": "devel",
                "original_branch": "operator-start", "base_commit": base,
                "default_commit": default}
        (source / "input.yaml").write_text(yaml.safe_dump(data))
        (source / "annotations.yaml").write_text("{}\n")
        workspace = self.root / "cases/case-local"
        settings = workspace / ".claude/settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_bytes(b'{"permissions": {"defaultMode": "dontAsk"}}\n')
        original_run = EVAL.run

        def local_fetch(*args, **kwargs):
            # Keep real Git/bare trees and checkout behavior; replace only the
            # validated remote transport so this setup test cannot use network.
            if "fetch" in args and data["repository"] in args:
                args = tuple(str(repository) if arg == data["repository"] else arg
                             for arg in args)
            return original_run(*args, **kwargs)

        return workspace, source, data, local_fetch

    def test_prepare_rejects_reserved_default_tree_before_checkout(self):
        self.assert_prepare_rejects_reserved_tree("default")

    def test_prepare_rejects_reserved_base_tree_with_clean_default(self):
        self.assert_prepare_rejects_reserved_tree("base")

    def assert_prepare_rejects_reserved_tree(self, collision):
        workspace, source, data, local_fetch = self.prepare_local_repository(collision)
        settings = workspace / ".claude/settings.json"
        original_settings = settings.read_bytes()
        pin = data[f"{collision}_commit"]
        with patch.object(EVAL, "run", side_effect=local_fetch):
            with self.assertRaisesRegex(ValueError, rf"reserved eval paths at {pin}:.*\.claude"):
                EVAL.prepare(workspace, source)
        self.assertEqual(settings.read_bytes(), original_settings)
        self.assertFalse((workspace / ".git").exists())
        self.assertFalse((workspace / ".replay/remotes/fork").exists())
        self.assertFalse((workspace / "go.mod").exists())

    def test_replay_uses_complete_current_skill_and_historical_engine(self):
        workspace, source, data, local_fetch = self.prepare_local_repository()
        data.pop("mode")
        (source / "input.yaml").write_text(yaml.safe_dump(data))
        expected = {"result_commit": data["default_commit"], "fix_branch": "recorded-result", "exit_code": 2}
        (source / "annotations.yaml").write_text(yaml.safe_dump(expected))
        repository = self.root / "repository"
        EVAL.git(repository, "branch", "recorded-result", data["default_commit"])
        EVAL.git(repository, "bundle", "create", str(source / "result.bundle"), "recorded-result")
        shutil.copy2(self.archive(files={
            "scripts/fix-all.sh": "#!/bin/sh\n# Historical runtime witness\nexit 2\n",
            "skills/fix-go-cves/SKILL.md": "historical instructions\n",
            "skills/fix-go-cves/references/obsolete.md": "stale historical reference\n",
        }), source / "plugin.tar.gz")
        (source / "run.log.gz").write_bytes(gzip.compress(b"recorded partial outcome\n"))
        with patch.object(EVAL, "run", side_effect=local_fetch), contextlib.redirect_stdout(io.StringIO()):
            baseline = EVAL.prepare(workspace, source)
        plugin = workspace / ".staged-plugins/fix-go-cves"
        for path in (EVAL.EVAL_ROOT.parent / "skills/fix-go-cves").rglob("*"):
            if path.is_file():
                relative = path.relative_to(EVAL.EVAL_ROOT.parent)
                self.assertEqual((plugin / relative).read_bytes(), path.read_bytes())
                self.assertEqual(baseline["plugin_hashes"][str(relative)], EVAL.digest(path))
        self.assertFalse((plugin / "skills/fix-go-cves/references/obsolete.md").exists())
        self.assertIn("# Historical runtime witness", (plugin / "scripts/fix-all.sh").read_text())

    def test_prepare_clean_pinned_trees_preserves_settings_and_allowed_paths(self):
        workspace, source, data, local_fetch = self.prepare_local_repository()
        settings = workspace / ".claude/settings.json"
        original_settings = settings.read_bytes()
        with patch.object(EVAL, "run", side_effect=local_fetch), \
                contextlib.redirect_stdout(io.StringIO()):
            EVAL.prepare(workspace, source)
        self.assertEqual(settings.read_bytes(), original_settings)
        self.assertEqual(EVAL.git(workspace, "rev-parse", "HEAD"), data["default_commit"])
        self.assertEqual(EVAL.git(workspace, "branch", "--show-current"), "operator-start")
        self.assertTrue((workspace / "cmd/bin/source.go").is_file())
        EVAL.check_reserved_paths(workspace)

class RunnerFailureTests(unittest.TestCase):
    def test_documented_launch_preserves_exit_and_terminal_receipt(self):
        skill = (Path(__file__).parents[1] / "skills/fix-go-cves/SKILL.md").read_text()
        launches = [block.split("```", 1)[0] for block in skill.split("```bash\n")[1:]
                    if "/scripts/fix-all.sh" in block.split("```", 1)[0]]
        self.assertEqual(len(launches), 1, "Expected one canonical Bash launch fence")
        command = launches[0].replace(" ARGS", "")
        shells = [("bash", ["--noprofile", "--norc"])]
        if shutil.which("zsh"):
            shells.append(("zsh", ["-f"]))
        for shell, options in shells:
            for errexit in (False, True):
                for child_exit in (0, 1, 2):
                    with self.subTest(shell=shell, errexit=errexit, child_exit=child_exit), \
                            tempfile.TemporaryDirectory() as directory:
                        root = Path(directory)
                        (root / "scripts").mkdir()
                        (root / "scripts/fix-all.sh").write_text(
                            'echo "child output"\nexit "$CHILD_EXIT"\n')
                        result = subprocess.run(
                            [shell, *options, *(["-e"] if errexit else []), "-c", command],
                            env={**os.environ, "PLUGIN_ROOT": str(root), "TMPDIR": str(root),
                                 "CHILD_EXIT": str(child_exit)}, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                        logs = list(root.glob("fix-go-cves.*.log"))
                        self.assertEqual(len(logs), 1, result.stderr)
                        self.assertEqual(result.stdout.splitlines(), [f"LOG={logs[0]}"])
                        self.assertEqual(logs[0].read_text().splitlines(),
                                         ["child output", f"exit={child_exit}"])
                        self.assertEqual(result.returncode, child_exit, result.stderr)
                with self.subTest(shell=shell, errexit=errexit, parent_printf_failure=True), \
                        tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    (root / "scripts").mkdir()
                    (root / "scripts/fix-all.sh").write_text('echo "child output"\nexit 0\n')
                    result = subprocess.run(
                        [shell, *options, *(["-e"] if errexit else []), "-c",
                         "printf() { return 1; }\n" + command],
                        env={**os.environ, "PLUGIN_ROOT": str(root), "TMPDIR": str(root)},
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    logs = list(root.glob("fix-go-cves.*.log"))
                    self.assertEqual(len(logs), 1, result.stderr)
                    self.assertIn("child output", logs[0].read_text().splitlines())
                    self.assertFalse(any(line.startswith("exit=")
                                         for log in logs
                                         for line in log.read_text().splitlines()))

    def test_failed_stages_preserve_artifacts_and_nonzero_completion(self):
        # Inject CLI stage outcomes while executing the actual Bash runner.
        for failed, code, expected in (
            ('execute.py', 7, ['execute.py', 'collect.py', 'report.py', 'verify']),
            ('collect.py', 8, ['execute.py', 'collect.py', 'report.py', 'verify']),
            ('judges', 3, ['execute.py', 'collect.py', 'judges', 'report.py', 'verify', 'regression']),
        ):
            with self.subTest(stage=failed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                harness = root / 'harness'
                (harness / 'skills/eval-run/scripts').mkdir(parents=True)
                (harness / 'skills/eval-run/scripts/workspace.py').touch()
                subprocess.run(['git', 'init', '-q', str(harness)], check=True)
                subprocess.run(['git', '-C', str(harness), '-c', 'user.name=fixture',
                                '-c', 'user.email=fixture@example.test', 'commit', '-q',
                                '--allow-empty', '-m', 'fixture'], check=True)
                python = root / 'stage-python'
                python.write_text('''#!/usr/bin/env python3
import json, os, pathlib, shutil, sys
root = pathlib.Path(os.environ['RUNNER_TEST_ROOT'])
args = sys.argv[1:]
if args[0] == '-c':
    print(root / 'workspaces' if 'tempfile' in args[1] else 'fixture-eval')
    sys.exit(0)
name = pathlib.Path(args[0]).name
stage = args[1] if name in ('eval.py', 'score.py') else name
if stage == 'snapshot':
    print(root / 'frozen.yaml'); sys.exit(0)
workspace = root / 'workspaces/run'
if stage == 'workspace.py':
    (workspace / 'cases/case-005/output').mkdir(parents=True)
    print('WORKSPACE: ' + str(workspace)); sys.exit(0)
with (root / 'stages.jsonl').open('a') as stream:
    stream.write(json.dumps(stage) + '\\n')
if stage == 'execute.py':
    (workspace / 'cases/case-005/output/runtime.txt').write_text('completed engine evidence')
if stage == 'collect.py':
    shutil.copytree(workspace / 'cases', root / 'collected')
if stage == os.environ['RUNNER_TEST_FAIL']:
    sys.exit(int(os.environ['RUNNER_TEST_CODE']))
if stage == 'verify':
    sys.exit(9)  # Missing grades must remain an error, even after reporting.
''')
                python.chmod(0o755)
                env = {**os.environ, 'HARNESS': str(harness),
                       'CVE_EVAL_PYTHON': str(python), 'AGENT_EVAL_RUNS_DIR': str(root / 'runs'),
                       'RUNNER_TEST_ROOT': str(root), 'RUNNER_TEST_FAIL': failed,
                       'RUNNER_TEST_CODE': str(code)}
                result = subprocess.run(['bash', str(Path(__file__).with_name('run.sh')),
                                         '--run-id', 'run'], env=env, text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual([json.loads(line) for line in
                                  (root / 'stages.jsonl').read_text().splitlines()], expected)
                self.assertEqual((root / 'collected/case-005/output/runtime.txt').read_text(),
                                 'completed engine evidence')
                self.assertIn('RESULTS:', result.stdout)


if __name__ == "__main__":
    unittest.main()
