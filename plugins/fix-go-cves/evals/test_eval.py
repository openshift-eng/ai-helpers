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
import shlex
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
        self.enterContext(patch.dict(os.environ,
            {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}, clear=True))
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

    def test_jsonl_unicode_separators_are_data(self):
        records = [{'path': 'bin/fresh\u2028output', 'compiler': 'go\u0085version'},
                   {'type': 'result', 'result': 'completed\u2029reply'}]
        path = self.root / 'events.jsonl'
        path.write_text('\n' + '\n\n'.join(json.dumps(row, ensure_ascii=False)
                                            for row in records) + '\n')
        self.assertEqual(EVAL.events(path), records)

    def case(self, native=True):
        case = self.root / "cases/case-005"
        (case / "output").mkdir(parents=True)
        expected = {"result_commit": "a" * 40, "fix_branch": "fix-recorded",
                    "arguments": ["0.24"], "base_branch": "release-0.24", "exit_code": 0}
        state = {"head": "a" * 40, "branch": "fix-recorded", "dirty": "", "unexpected_ignored": [],
                 "invocations": [{"arguments": ["0.24"]}], "refs_unchanged": True,
                 "plugin_unchanged": True, "gh_calls": "", "trace_violations": [],
                 "execution_inputs_unchanged": True,
                 "permission_denials": [], "expected": expected}
        EVAL.write_json(case / "output/state.json", state)
        (case / "annotations.yaml").write_text(yaml.safe_dump(
            {"required_commits": ["a" * 40, "b" * 40]}))
        body = 'Recorded commit aaaaaaa, backport bbbbbbb.\n'
        source = self.root / 'fixtures/case-005'
        source.mkdir(parents=True)
        (source / 'run.log.gz').write_bytes(gzip.compress(body.encode()))
        self.freeze()
        if native:
            state, _ = self.attach_native(case, state, body, 0)
        return case, state

    def freeze(self, cases=("case-005",), live=False, annotation=None, reset=False):
        source = self.root / "fixtures"
        for case in cases:
            (source / case).mkdir(parents=True, exist_ok=True)
            state_path = self.root / "cases" / case / "output/state.json"
            baseline = self.root / "control" / case / "baseline.json"
            collected = (EVAL.read_json(state_path)["expected"] if state_path.exists() else
                         EVAL.read_json(baseline)["meta"] if baseline.exists() else {})
            data = {key: value for key, value in collected.items() if key != "runtime_dir"}
            labels = dict({"required_commits": ["a" * 40, "b" * 40]}
                          if annotation is None else annotation)
            if live:
                data["mode"] = "live"
                if state_path.exists():
                    state = EVAL.read_json(state_path)
                    state["expected"]["mode"] = "live"
                    EVAL.write_json(state_path, state)
            else:
                for key, default in (("result_commit", "a" * 40),
                                     ("fix_branch", "fix-recorded"), ("exit_code", 0)):
                    labels.setdefault(key, data.pop(key, default))
            (source / case / "input.yaml").write_text(yaml.safe_dump(data))
            (source / case / "annotations.yaml").write_text(yaml.safe_dump(labels))
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

    def capture(self, workspace):
        path = self.root / "control" / workspace.name / "baseline.json"
        baseline = EVAL.read_json(path)
        if not (self.root / "provenance").exists():
            self.freeze(cases=(workspace.name,), live=baseline["meta"].get("mode") == "live", annotation={})
        baseline.setdefault("source", str(self.root / "provenance/cases" / workspace.name))
        EVAL.write_json(path, baseline)
        return EVAL.capture(workspace)

    def test_legitimate_contract_failure_is_false_not_an_error(self):
        case, state = self.case()
        state["dirty"] = " M go.mod"
        EVAL.write_json(case / "output/state.json", state)
        with patch.object(EVAL, "EVAL_ROOT", self.root):
            verdict = EVAL.check(case)
        self.assertIs(verdict["passed"], False)
        self.assertIn("clean checkout", verdict["reason"])

    def test_collected_expectations_cannot_change_frozen_grading(self):
        case, state = self.case()
        for changes in ({"result_commit": "c" * 40}, {"arguments": ["wrong"]},
                        {"runtime_expectation": "observed"}, {"go_minor_guard": False},
                        {"canonical_commands": {"test": "true"}}, {"base_branch": "wrong"}):
            with self.subTest(changes=changes):
                EVAL.write_json(case / "output/state.json", {
                    **state, "expected": {**state["expected"], **changes}})
                verdict = EVAL.check(case)
                self.assertFalse(verdict["passed"])
                self.assertIn("frozen expectations unchanged", verdict["reason"])
        EVAL.write_json(case / "output/state.json", {
            **state, "expected": {**state["expected"], "runtime_dir": "/operational/path"}})
        self.assertTrue(EVAL.check(case)["passed"])

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
                               ("plugin_unchanged", False), ("refs_unchanged", False),
                               ("execution_inputs_unchanged", False), ("execution_inputs_unchanged", None)):
                with self.subTest(key=key):
                    state = {**clean, key: value}
                    EVAL.write_json(case / "output/state.json", state)
                    self.assertIs(EVAL.check(case)["passed"], False)

    def test_extraction_retains_all_assistant_text_and_denials(self):
        case, _ = self.case()
        EVAL.write_json(case / 'run_result.json', {'exit_code': 0, 'permission_denials': ['git push']})
        stream = EVAL.events(case / 'stdout.log')
        stream.insert(0, {'type': 'assistant', 'message': {'content': [
            {'type': 'text', 'text': 'Earlier progress requiring review'}]}})
        (case / 'stdout.log').write_text('\n'.join(json.dumps(event) for event in stream))
        EVAL.extract(self.root)
        self.assertTrue((case / 'output/reply.md').read_text().startswith('Earlier progress requiring review'))
        self.assertEqual(EVAL.read_json(case / 'output/state.json')['permission_denials'], ['git push'])
        EVAL.write_json(case / 'run_result.json', {'exit_code': 1, 'error': 'not authenticated'})
        with self.assertRaises(ValueError):
            EVAL.extract(self.root)

    def attach_native(self, case, state, body, code, prose='Selected requested inputs.', staged_engine=False, cwd=None):
        if not (case / '.git').exists():
            EVAL.git(case, 'init')
        helper = case / '.staged-plugins/fix-go-cves/scripts/deliver.py'
        if not staged_engine:
            helper.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(EVAL.EVAL_ROOT.parent / 'scripts/deliver.py', helper)
            (helper.parent / 'fix-all.sh').write_text('cat "$DELIVERY_TEST_LOG"\nexit "$DELIVERY_TEST_EXIT"\n')
        original = self.root / 'original.log'
        original.write_bytes(body if isinstance(body, bytes) else body.encode())
        temporary = self.root / 'private-tmp'
        temporary.mkdir(mode=0o700, exist_ok=True)
        environment = {**os.environ, 'TMPDIR': str(temporary), 'DELIVERY_TEST_LOG': str(original), 'DELIVERY_TEST_EXIT': str(code)}
        command = ['python3', str(helper), 'prepare', '--env', 'CVE_FIX_GO_MINOR_GUARD=true',
                   'fix', str(case), *state['expected']['arguments']]
        execution_cwd = case if cwd is None else cwd
        prepared = subprocess.run([sys.executable, *command[1:]], cwd=execution_cwd, env=environment,
                                  capture_output=True, text=True, check=True)
        value = {'command': shlex.join(command)}
        event = {'hook_event_name': 'PostToolUse', 'tool_name': 'Bash', 'cwd': str(execution_cwd),
                 'tool_input': value, 'tool_response': {'stdout': prepared.stdout}}
        completed = subprocess.run([sys.executable, str(helper), 'hook'], cwd=execution_cwd, env=environment,
                                   input=json.dumps(event), capture_output=True, text=True, check=True)
        if not staged_engine:
            state['invocations'] = [{'arguments': [str(case), *state['expected']['arguments']],
                'overrides': {key: ("true" if key == 'CVE_FIX_GO_MINOR_GUARD' else environment.get(key))
                              for key in EVAL.INVOCATION_OVERRIDES}}]
        stream = [
            {'type': 'assistant', 'message': {'content': [
                {'type': 'text', 'text': prose},
                {'type': 'tool_use', 'id': 'prepare', 'name': 'Bash', 'input': value}]}},
            {'type': 'system', 'subtype': 'hook_started', 'hook_id': 'owned-hook',
             'hook_event': 'PostToolUse', 'hook_name': 'PostToolUse:Bash'},
            {'type': 'system', 'subtype': 'hook_response', 'hook_id': 'owned-hook',
             'hook_event': 'PostToolUse', 'hook_name': 'PostToolUse:Bash', 'exit_code': 0,
             'outcome': 'success', 'stderr': '', 'stdout': completed.stdout, 'output': completed.stdout},
            {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'prepare',
                 'content': prepared.stdout, 'is_error': False}]},
             'tool_use_result': {'stdout': prepared.stdout, 'interrupted': False}},
            {'type': 'result', 'terminal_reason': 'hook_stopped', 'is_error': False, 'result': ''}]
        state['workspace'] = str(case)
        EVAL.write_json(case / 'output/state.json', state)
        for artifact in ('delivery-request.json', 'delivered.log'):
            (case / 'output' / artifact).unlink(missing_ok=True)
        EVAL.write_json(case / 'run_result.json', {'exit_code': 0, 'permission_denials': []})
        (case / 'stdout.log').write_text('\n'.join(json.dumps(event) for event in stream))
        EVAL.extract(self.root)
        return EVAL.read_json(case / 'output/state.json'), stream

    def native_case(self):
        case, state = self.case(native=False)
        state['workspace'], state['expected']['exit_code'] = str(case), 2
        EVAL.write_json(case / 'output/state.json', state)
        body = EVAL.without_recorded_exit(self.pr_log(), 2)
        (self.root / 'fixtures/case-005/run.log.gz').write_bytes(gzip.compress((body + 'exit=2\n').encode()))
        self.freeze(reset=True,
                    annotation={'exit_code': 2, 'required_commits': ['2716c2ff']})
        state, stream = self.attach_native(case, state, body, 2, 'UNSUPPORTED_INITIAL_CAUSE_FOR_REVIEW')
        return case, stream, body

    def test_native_artifact_retains_original_exit_bytes_and_all_assistant_text(self):
        case, stream, body = self.native_case()
        verdict = EVAL.check(case)
        self.assertTrue(verdict['passed'], verdict)
        reply = (case / 'output/reply.md').read_text()
        # This negative prose remains available to independent review; a transport pass is not whole acceptance.
        self.assertIn('UNSUPPORTED_INITIAL_CAUSE_FOR_REVIEW', reply)
        self.assertIn('LOG=', reply)
        self.assertIn('exit=2', reply)
        self.assertNotIn('git push', reply)
        self.assertEqual((case / 'output/delivered.log').read_bytes(), (body + '\nexit=2\n').encode())
        self.assertEqual(EVAL.read_json(case / 'output/state.json')['delivery']['exit_code'], 2)
        self.assertEqual(stream[-1]['result'], '')

    def test_native_invocation_witness_matches_selected_and_inherited_settings(self):
        with patch.dict(os.environ, {'CVE_FIX_TEST_CMD': '', 'CVE_FIX_GO_MINOR_GUARD': 'false',
                                     'CVE_FIX_K8S_VERSION_GUARD': 'false'}):
            case, state = self.case()
        self.assertTrue(EVAL.check(case)['passed'])
        self.assertEqual(state['invocations'][0]['overrides'], {
            'CVE_FIX_TEST_CMD': '', 'CVE_FIX_GO_MINOR_GUARD': 'true', 'CVE_FIX_K8S_VERSION_GUARD': 'false'})
        for mutation in ('arguments', 'overrides', 'missing-overrides'):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(state)
                invocation = changed['invocations'][0]
                if mutation == 'arguments':
                    # Semantically permitted branch alias, but not the actual native argv.
                    invocation['arguments'] = ['release-0.24']
                elif mutation == 'overrides':
                    invocation['overrides']['CVE_FIX_GO_MINOR_GUARD'] = 'false'
                else:
                    invocation.pop('overrides')
                EVAL.write_json(case / 'output/state.json', changed)
                verdict = EVAL.check(case)
                self.assertFalse(verdict['passed'])
                self.assertIn('native artifact authenticated', verdict['reason'])

    def test_native_absolute_target_is_bound_independently_of_persistent_cwd(self):
        case, state = self.case(native=False)
        sibling = self.root / 'persistent-cwd'
        sibling.mkdir()
        body = gzip.decompress((self.root / 'fixtures/case-005/run.log.gz').read_bytes()).decode()
        state, stream = self.attach_native(case, state, body, 0, cwd=sibling)
        self.assertTrue(EVAL.check(case)['passed'])
        request_path = case / 'output/delivery-request.json'
        request = EVAL.read_json(request_path)
        self.assertEqual(request['cwd'], str(sibling))
        self.assertEqual(request['runs'][0]['args'][0], str(case))
        # A matching cwd does not authorize redirecting the absolute target.
        command = shlex.split(stream[0]['message']['content'][1]['input']['command'])
        command[command.index('fix') + 1] = str(sibling)
        stream[0]['message']['content'][1]['input']['command'] = shlex.join(command)
        request['argv'] = command[2:]
        request['runs'][0]['args'][0] = str(sibling)
        state['invocations'][0]['arguments'][0] = str(sibling)
        EVAL.write_json(request_path, request)
        with self.assertRaisesRegex(ValueError, 'preparation/target'):
            EVAL.native_artifact(case, state, stream)

    def test_native_artifact_rejects_missing_forged_failed_and_repeated_preparation(self):
        case, stream, _ = self.native_case()
        for mutation in ('missing-start', 'missing-response', 'failed-hook', 'wrong-event',
                         'changed-output', 'duplicate-hook', 'repeated-prepare', 'forged-text'):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(stream)
                if mutation == 'missing-start': del changed[1]
                elif mutation == 'missing-response': del changed[2]
                elif mutation == 'failed-hook': changed[2]['exit_code'] = 2
                elif mutation == 'wrong-event': changed[2]['hook_event'] = 'PostToolUseFailure'
                elif mutation == 'changed-output': changed[2]['output'] = '{}'
                elif mutation == 'duplicate-hook': changed.insert(3, copy.deepcopy(changed[2]))
                elif mutation == 'repeated-prepare':
                    failed = copy.deepcopy(changed[0]['message']['content'][1])
                    failed['id'] = 'earlier-failed-prepare'
                    changed.insert(0, {'type': 'assistant', 'message': {'content': [failed]}})
                else:
                    forged = changed.pop(2)
                    changed[0]['message']['content'].insert(0, {'type': 'text', 'text': json.dumps(forged)})
                (case / 'stdout.log').write_text('\n'.join(json.dumps(event) for event in changed))
                EVAL.extract(self.root)
                self.assertFalse(EVAL.check(case)['passed'])
                self.assertIsNone(EVAL.read_json(case / 'output/state.json')['delivery'])

    def test_native_artifact_rejects_later_generation_and_changed_archive(self):
        case, stream, _ = self.native_case()
        stream += [{'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'BAD_LATER_REPORT'}]}},
                   {'type': 'result', 'result': 'BAD_LATER_REPORT', 'is_error': False}]
        (case / 'stdout.log').write_text('\n'.join(json.dumps(event) for event in stream))
        EVAL.extract(self.root)
        self.assertIn('BAD_LATER_REPORT', (case / 'output/reply.md').read_text())
        self.assertIn('no postruntime model generation', EVAL.check(case)['reason'])
        stream = stream[:-2]
        (case / 'stdout.log').write_text('\n'.join(json.dumps(event) for event in stream))
        EVAL.extract(self.root)
        self.assertTrue(EVAL.check(case)['passed'])
        log = case / 'output/delivered.log'
        original = log.read_bytes()
        log.write_bytes(original.replace(b'--base release-0.24', b'--base devel'))
        self.assertIn('native artifact authenticated', EVAL.check(case)['reason'])
        log.write_bytes(original)
        output, saved = case / 'output', case / 'saved-output'
        output.rename(saved)
        output.symlink_to(saved, target_is_directory=True)
        try:
            self.assertIn('native artifact authenticated', EVAL.check(case)['reason'])
        finally:
            output.unlink()
            saved.rename(output)

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

    def test_only_proven_inventory_denials_are_benign(self):
        case, state = self.case()
        good = ('git stash list', 'git stash list 2>&1',
                'git status --short && echo "---" && git stash list 2>&1')
        bad = ('git stash push', 'git stash list >go.mod', 'git stash list 2>/dev/null',
               'git stash list\ngit status', 'git stash list && git reset --hard',
               'git stash list $(touch go.mod)', 'git stash list `touch go.mod`',
               "git stash list '2>' & '1'", 'git stash list; git checkout -- go.mod',
               'git -c diff.external=tool stash list')
        for command in good + bad:
            with self.subTest(command=command):
                denial = {"tool_name": "Bash", "tool_input": {"command": command}}
                current = {**state, "permission_denials": [denial],
                           "trace_violations": self.trace(command)}
                EVAL.write_json(case / "output/state.json", current)
                self.assertEqual(EVAL.check(case)["passed"], command in good)
                self.assertEqual(EVAL.read_json(case / "output/state.json")["permission_denials"], [denial])
        for denial in ("git stash list", {"tool_name": "Agent", "tool_input": {"command": good[0]}}):
            self.assertFalse(EVAL.benign_inventory_denial(denial))

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
                  {'type': 'assistant', 'message': 'exit=2'}, {'type': 'user', 'message': 'exit=2'},
                  *EVAL.events(case / 'stdout.log')]
        (case / 'stdout.log').write_text('\n'.join(json.dumps(event) for event in stream))
        EVAL.extract(self.root)
        self.assertEqual(EVAL.read_json(case / 'output/state.json')['permission_denials'], [denial])
        verdict = EVAL.check(case)
        self.assertIs(verdict['passed'], False)
        self.assertEqual(verdict['reason'], 'no forbidden operations')

    def pr_log(self):
        return (Path(__file__).parent / "fixtures/submariner-pr-summary.txt").read_text()

    def test_replay_requires_a_frozen_runtime_log(self):
        case, _ = self.case()
        self.assertTrue(EVAL.check(case)['passed'])  # Legitimate no-Summary runtime record.
        manifest_path = self.root / 'provenance/manifest.json'
        manifest = EVAL.read_json(manifest_path)
        del manifest['files']['cases/case-005/run.log.gz']
        EVAL.write_json(manifest_path, manifest)
        # Unlisted source is an integrity error; its absence cannot authorize a reply.
        with self.assertRaisesRegex(ValueError, 'Frozen input changed'):
            EVAL.check(case)
        (self.root / 'provenance/cases/case-005/run.log.gz').unlink()
        verdict = EVAL.check(case)
        self.assertFalse(verdict['passed'])
        self.assertIn('delivered original runtime bytes', verdict['reason'])

    def test_recorded_exit_removes_only_one_matching_terminal_line(self):
        for recorded, expected in (
                ('before\nexit=2\nafter\nexit=2\n', 'before\nexit=2\nafter\n'),
                ('before\nexit=2\nexit=2\n', 'before\nexit=2\n'),
                ('before\nexit=0\n', 'before\nexit=0\n'),
                ('before exit=2\n', 'before exit=2\n'),
                ('before\nexit=2', 'before\n')):
            with self.subTest(recorded=recorded):
                self.assertEqual(EVAL.without_recorded_exit(recorded, 2), expected)

    def test_live_capture_retains_original_log_and_identity(self):
        workspace = self.root / 'cases/case-001'
        workspace.mkdir(parents=True)
        EVAL.git(workspace, 'init')
        EVAL.git(workspace, '-c', 'user.name=Eval', '-c', 'user.email=eval@example.invalid',
                 'commit', '--allow-empty', '-m', 'base')
        head = EVAL.git(workspace, 'rev-parse', 'HEAD')
        branch = EVAL.git(workspace, 'branch', '--show-current')
        runtime = self.root / 'control/case-001/runtime'
        runtime.mkdir(parents=True)
        log = self.pr_log().removesuffix('exit=2\n').encode() + b'\xff valid UTF-8: \xc3\xa9\r\n'
        (runtime / 'run.log').write_bytes(log)
        EVAL.write_json(runtime / 'evidence/run.json', {'head': head, 'exit_code': 2})
        EVAL.write_json(runtime / 'status.json', {'head': head, 'branch': branch,
            'exit_code': 2, 'evidence_hashes': EVAL.file_hashes(runtime / 'evidence'),
            'run_log_sha256': EVAL.digest(runtime / 'run.log'),
            'ignored_snapshot': {}})
        (runtime / 'invocations.jsonl').write_text('{"arguments":["devel"]}\n')
        (workspace / '.git/info/exclude').write_text('output/\n.replay/\n')
        meta = {'mode': 'live', 'repository': 'https://github.com/example/repo.git',
                'base_commit': head, 'default_commit': head, 'original_branch': branch,
                'arguments': ['devel'], 'base_branch': 'devel'}
        private = workspace / '.replay'
        private.mkdir()
        shutil.copy2(EVAL.__file__, private / 'driver.py')
        EVAL.write_json(private / 'meta.json', meta)
        EVAL.write_json(runtime.parent / 'baseline.json', {'refs': {}, 'plugin_hashes': {},
            'runtime_plugin_hashes': {}, 'runtime_dir': str(runtime),
            'execution_inputs': {name: EVAL.file_identity(private / name)
                                 for name in ('driver.py', 'meta.json')}, 'meta': meta})
        self.capture(workspace)
        output = workspace / 'output'
        self.assertEqual((output / 'run.log').read_bytes(), log)
        self.assertEqual(EVAL.read_json(output / 'runtime-identity.json')['run_log_sha256'],
                         EVAL.digest(runtime / 'run.log'))
        for changed in (False, True):
            if changed:
                (runtime / 'run.log').write_bytes(log.replace(b'\xff', b'\xfe'))
                self.assertEqual((runtime / 'run.log').read_bytes().decode('utf-8', errors='replace'),
                                 log.decode('utf-8', errors='replace'))
                completion = EVAL.read_json(runtime / 'status.json')
                completion['run_log_sha256'] = EVAL.digest(runtime / 'run.log')
                EVAL.write_json(runtime / 'status.json', completion)
                self.capture(workspace)
            state = EVAL.read_json(output / 'state.json')
            state.update(trace_violations=[], permission_denials=[])
            state, _ = self.attach_native(workspace, state, log, 2)
            verdict = EVAL.check(workspace, live=True)
            self.assertIs(verdict['passed'], not changed, verdict)
            if changed:
                self.assertIn('delivered original runtime bytes', verdict['reason'])

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
        overrides = ("CVE_FIX_TEST_CMD", "CVE_FIX_GO_MINOR_GUARD", "CVE_FIX_K8S_VERSION_GUARD")
        for index, values in enumerate(((None, None, None), ("", "false", ""),
                                        ("make unit && echo '$literal'", "true", "false"))):
            with self.subTest(overrides=values):
                meta = EVAL.read_json(private / "meta.json")
                meta["fix_branch"] = f"fix-recorded-{index}"
                EVAL.write_json(private / "meta.json", meta)
                calls = private / "invocations.jsonl"
                calls.unlink(missing_ok=True)
                environment = {key: value for key, value in os.environ.items() if key not in overrides}
                environment.update({key: value for key, value in zip(overrides, values) if value is not None})
                environment.update(HOME=str(home), UNRELATED_SECRET="must-not-be-recorded")
                result = subprocess.run(
                    [sys.executable, "-I", "-S", str(private / "driver.py"), "replay", "0.24"],
                    cwd=workspace, env=environment, capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "Recorded partial result\n")
                wrapped = result.stdout + f'exit={result.returncode}\n'
                self.assertEqual(wrapped.count('exit=2\n'), 1)
                self.assertEqual(EVAL.git(workspace, "branch", "--show-current"), meta["fix_branch"])
                records = [json.loads(line) for line in calls.read_text().splitlines()]
                self.assertEqual(len(records), 1)
                self.assertEqual(set(records[0]), {"arguments", "time", "overrides"})
                self.assertEqual(records[0]["arguments"], ["0.24"])
                self.assertEqual(records[0]["overrides"], dict(zip(overrides, values)))
                self.assertNotIn("must-not-be-recorded", calls.read_text())

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
                        "git --git-dir=/tmp/repo.git push origin HEAD", "git stash push"):
            with self.subTest(command=command):
                self.assertIn("Attempted publication or disallowed git operation", self.trace(command))
        self.assertEqual(self.trace("git -C /tmp/checkout log --oneline"), [])

    def test_trace_checks_direct_executables_instead_of_argument_words(self):
        for command in ('rg -n gh README.md', 'echo gh', 'git diff -- gh',
                        "printf '%s\\n' git push", 'rg -n /usr/bin/git README.md',
                        'git -c alias.subject=gh show HEAD'):
            with self.subTest(command=command):
                self.assertEqual(self.trace(command), [])
        for command in ('/usr/bin/git push origin HEAD', '/usr/bin/gh pr create',
                        'MODE=read /usr/bin/git -C . push origin HEAD',
                        'env MODE=read /usr/bin/git push origin HEAD',
                        'echo gh; /usr/bin/git push origin HEAD'):
            with self.subTest(command=command):
                self.assertIn('Attempted publication or disallowed git operation', self.trace(command))
        # This direct-command heuristic does not parse nested shell programs.
        self.assertEqual(self.trace('bash -c "go test ./..."'), [])

    def test_workspace_path_cannot_hide_a_source_checkout_read(self):
        project = self.root / "project"
        command = f"cat {project}/plugins/fix-go-cves/evals/cases/case-005/reply.md {self.root}/checkout/source.txt"
        self.assertIn("Command accesses protected source or eval control files", self.trace(command, project))

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
                          "printf '\\377 valid UTF-8: \\303\\251\\r\\n' >&2\nprintf tail\n"
                          'if read -r line; then exit 99; fi\nexit 2\n')
        output = io.BytesIO()
        # The byte tee must also work when the terminal's text encoding is ASCII.
        terminal = io.TextIOWrapper(output, encoding='ascii')
        with contextlib.redirect_stdout(terminal), patch.object(EVAL, "runtime_environment", return_value={}):
            status = EVAL.live_run(workspace, ["0.24"])
        self.assertEqual(status, 2)
        self.assertEqual(output.getvalue(), b"actual 0.24\ndiagnostic\n\xff valid UTF-8: \xc3\xa9\r\ntail")
        self.assertEqual((runtime / "run.log").read_bytes(), output.getvalue())
        self.assertEqual(EVAL.read_json(runtime / 'evidence/environment.json'), {'before': {}, 'after': {}})
        self.assertEqual(EVAL.read_json(runtime / "status.json"), {
            "exit_code": 2, "evidence_hashes": EVAL.file_hashes(runtime / "evidence"), "head": EVAL.git(workspace, "rev-parse", "HEAD"),
            "run_log_sha256": EVAL.digest(runtime / "run.log"),
            "branch": EVAL.git(workspace, "branch", "--show-current"),
            "ignored_snapshot": {"unit.coverprofile": EVAL.file_identity(workspace / "unit.coverprofile")}})

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
        self.capture(workspace)
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
        with patch.object(EVAL, "EVAL_ROOT", self.root):
            verdict = EVAL.check(workspace, live=True)
        self.assertIs(verdict["passed"], False)
        self.assertIn("remotes and plugin unchanged", verdict["reason"])

    def test_live_contract_uses_live_annotations_and_retains_runtime_result(self):
        case, state = self.case()
        state["expected"]["mode"] = "live"
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
        state, _ = self.attach_native(case, state, log, 2)
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
        state = EVAL.read_json(case / 'output/state.json')
        state, _ = self.attach_native(case, state, log, 2)
        self.assertTrue(EVAL.check(case, live=True)['passed'])
        for key, value in (('runtime_exit', None), ('runtime_exit', 124), ('runtime_exit', False),
                           ('invocations', []),
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
        self.assertIn('complete assistant text retained', verdict['reason'])

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
            self.capture(workspace)
            output = workspace / 'output'
            state = EVAL.read_json(output / 'state.json')
            patch_text = (output / 'change.patch').read_text()
            self.assertEqual(state['changed_files'], [] if restored else ['go.mod'])
            self.assertNotIn('Unrelated default-branch history', patch_text)
            if restored:
                self.assertEqual(patch_text, '')
            else:
                self.assertIn('+require golang.org/x/net v0.60.0', patch_text)
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
        self.capture(workspace)
        state = EVAL.read_json(workspace / "output/state.json")
        self.assertEqual(set(state["unexpected_ignored"]), {"bin/app", "bin/data", "bin/link", "bin/other"})
        self.assertEqual(set(state["ignored_snapshot"]), {"bin/app", "bin/data", "bin/link", "bin/other"})
        self.assertEqual(state["ignored_snapshot"]["bin/data"], EVAL.file_identity(workspace / "bin/data"))
        self.assertEqual(state["ignored_snapshot"]["bin/link"], {"kind": "symlink", "target": str(outside)})
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
            f'bash "{runtime}/plugin/scripts/fix-all.sh" wrong-branch',
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
            'python3 /plugin/scripts/deliver.py prepare fix /checkout devel',
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

    def test_repair_always_requires_initial_phase_at_pinned_base(self):
        case, state, result, scan, initial = self.scenario()
        root = case / "output/runtime"
        for phase in ("not_reached", "failed", None):
            EVAL.write_json(root / "run.json", {**result, "phases": {
                **result["phases"], "initial_scan": phase}})
            self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        EVAL.write_json(root / "run.json", result)
        EVAL.write_json(root / "initial-scan-status.json", {**scan, "phase": "initial"})
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))

    def test_advertised_fix_coverage_requires_usable_versions(self):
        case, state, result, scan, initial = self.scenario()
        finding = initial["matches"][0]
        controls = [([], False), ([""], False), ([None, 1], False), (["junk"], False),
                    (["v1.2.0-rc.1"], False), (["go1.26rc1"], False),
                    (["v1.2.3"], True), (["v2.3.4+incompatible"], True),
                    (["v0.0.0-20231012123456-abcdef123456"], True),
                    (["v0.21.1-0.20240508182429-e35e4ccd0d2d"], True),
                    (["v1.2.3-pre.0.20240508182429-e35e4ccd0d2d"], True),
                    (["v1.2.0-rc.1", "v1.2.0"], True)]
        for versions, expected in controls:
            with self.subTest(versions=versions):
                finding["vulnerability"]["fix"]["versions"] = versions
                EVAL.write_json(case / "output/runtime/initial-scan.json", initial)
                self.assertEqual(EVAL.runtime_scenario(case, state)[
                    "initial fixable finding actually cleared"], expected)
        finding["artifact"]["name"] = "stdlib"
        for version, expected in (("1.26.1", True), ("go1.26.1", False),
                                  ("1.26rc1", False), ("v1.26.1", True),
                                  ("v0.0.0-20231012123456-abcdef123456", False)):
            with self.subTest(stdlib=version):
                finding["vulnerability"]["fix"]["versions"] = [version]
                self.assertEqual(EVAL.usable_fix(finding), expected)

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
        state["ignored_snapshot"][binary] = {"kind": "file", "sha256": identity, "mode": 0o755}
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

    def test_native_duplicate_paths_cannot_overwrite_a_failed_witness(self):
        case, state, directory, record, catalog = self.binary_scenario()
        bad = {**record, "build_info": record["build_info"].replace(
            "vcs.modified=false", "vcs.modified=true")}
        for records in ((bad, record), (record, bad),
                        ({**bad, "path": "./" + bad["path"]}, record),
                        ({**bad, "path": bad["path"].replace("/bin/", "/bin/./")}, record)):
            with self.subTest(paths=[record["path"] for record in records]):
                (directory / "binaries.jsonl").write_text(
                    "".join(json.dumps(record) + "\n" for record in records))
                proof = EVAL.native_scan_proof(case, state, "final-gate", state["runtime_head"], retained=True)
                self.assertFalse(proof["checks"]["native binary paths unique"])
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

    def test_native_binary_requires_one_matching_linux_amd64_target(self):
        case, state, directory, record, catalog = self.binary_scenario()
        for phase in ("initial", "final-gate"):
            scan = directory if phase == "final-gate" else directory.parent / "initial.example"
            original = EVAL.read_json(scan / "binaries.jsonl")
            for key, expected, wrong in (("GOOS", "linux", "darwin"),
                                         ("GOARCH", "amd64", "arm64")):
                line = f"\tbuild\t{key}={expected}\n"
                for changed in (original["build_info"].replace(f"{key}={expected}", f"{key}={wrong}"),
                                original["build_info"].replace(line, ""), original["build_info"] + line):
                    with self.subTest(phase=phase, build_info=changed):
                        (scan / "binaries.jsonl").write_text(
                            json.dumps({**original, "build_info": changed}) + "\n")
                        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
            reordered = original["build_info"].replace(
                "\tbuild\tGOOS=linux\n\tbuild\tGOARCH=amd64\n",
                "\tbuild\tGOARCH=amd64\n\tbuild\tGOOS=linux\n")
            (scan / "binaries.jsonl").write_text(
                json.dumps({**original, "build_info": reordered}) + "\n")
            self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))

    def test_native_proof_binds_initial_and_final_scan_heads(self):
        case, state, directory, record, catalog = self.binary_scenario()
        state["expected"]["runtime_expectation"] = "observed"
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
        # Observed coverage does not gain a native gate from optional proof.
        (directory / "binaries.jsonl").write_text("")
        self.assertTrue(all(EVAL.runtime_scenario(case, state).values()))

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
                     execution_inputs_unchanged=True,
                     invocations=[{"arguments": ["devel"]}], gh_calls="", trace_violations=[], permission_denials=[])
        EVAL.write_json(case / "output/state.json", state)
        log = '--- Summary: native fixture ---\nThe native binary and canonical gates were verified.\n'
        (case / 'output/run.log').write_text(log)
        EVAL.write_json(case / "output/runtime-identity.json", {
            "evidence_hashes": EVAL.file_hashes(case / "output/runtime"),
            "run_log_sha256": EVAL.digest(case / 'output/run.log')})
        (case / "output/reply.md").write_text('```text\n' + log + '```\n')
        self.freeze(cases=(case.name,), live=True, annotation={})
        state, _ = self.attach_native(case, state, log, 0)
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
        state["ignored_snapshot"][record["path"]] = {"kind": "file", "sha256": "e" * 64, "mode": 0o755}
        self.assertFalse(all(EVAL.runtime_scenario(case, state).values()))
        state["ignored_snapshot"][record["path"]] = {"kind": "file", "sha256": record["sha256"], "mode": 0o755}
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
        original = frozen.read_bytes()
        frozen.write_text("required_commits: [ccccccc]\n")
        with self.assertRaisesRegex(ValueError, "Frozen input changed"):
            EVAL.check(case)
        frozen.write_bytes(original)
        self.assertTrue(EVAL.check(case)['passed'])
        identity = EVAL.read_json(self.root / 'provenance/manifest.json')['interpreter']
        with patch.object(EVAL, 'interpreter_identity', return_value={**identity, 'version': 'changed'}):
            with self.assertRaisesRegex(ValueError, 'Selected interpreter changed'):
                EVAL.check(case)
        self.assertTrue(EVAL.check(case)['passed'])

    def test_snapshot_freezes_explicit_runtime_settings(self):
        self.freeze(cases=("case-004",), live=True, annotation={})
        raw = {"dataset": {"path": "fixtures"}, "judges": [{"name": "live_contract"}], "runner": {"env": {
            "CVE_FIX_TEST_CMD": "$CVE_FIX_TEST_CMD", "DAPPER_ARGS": "$DAPPER_ARGS",
            "CVE_FIX_GRYPE_VERSION": "$CVE_FIX_GRYPE_VERSION"}}}
        live = yaml.safe_load((Path(__file__).parent / "eval-live.yaml").read_text())
        self.assertEqual(live["runner"]["env"].get("CVE_FIX_GRYPE_VERSION"), "$CVE_FIX_GRYPE_VERSION")
        config = SimpleNamespace(
            runner=SimpleNamespace(plugin_dirs=[EVAL.EVAL_ROOT.parent]), models=SimpleNamespace(judge=None),
            dataset=SimpleNamespace(path="fixtures"),
            resolve_path=lambda _: self.root / "fixtures", project_root=self.root)
        loader = SimpleNamespace(
            EvalConfig=SimpleNamespace(from_yaml=lambda _: config),
            load_raw=lambda _: (copy.deepcopy(raw), None), resolve_plugin_dir=lambda _, path: path)
        for version in ("v0.121.0", None):
            with self.subTest(version=version):
                selected = {"CVE_FIX_TEST_CMD": "make golangci-lint && make unit",
                            "DAPPER_ARGS": "-f /external/Dockerfile.cache",
                            "CVE_FIX_GRYPE_VERSION": version}
                directory = self.root / ("snapshot-pinned" if version else "snapshot-default")
                with patch.dict(sys.modules, {"agent_eval": SimpleNamespace(config=loader),
                                              "agent_eval.config": loader}), \
                        patch.dict(os.environ, {key: value for key, value in selected.items() if value is not None}), \
                        patch.object(EVAL, "git", side_effect=lambda _, command, *args:
                                     "a" * 40 if command == "rev-parse" else ""):
                    if version is None:
                        os.environ.pop("CVE_FIX_GRYPE_VERSION", None)
                    with self.assertRaisesRegex(ValueError, "profile"):
                        EVAL.snapshot(self.root / "eval.yaml", self.root / "wrong-track", ["case-004"])
                    input_path = self.root / "fixtures/case-004/input.yaml"
                    original = input_path.read_bytes()
                    input_path.write_text("{}\n")
                    with self.assertRaisesRegex(ValueError, "case does not match"):
                        EVAL.snapshot(self.root / "eval.yaml", self.root / "wrong-case", ["case-004"], live=True)
                    input_path.write_bytes(original)
                    EVAL.snapshot(self.root / "eval.yaml", directory, ["case-004"], live=True)
                with patch.dict(os.environ, {key: "changed after snapshot" for key in selected}):
                    _, _, frozen = EVAL.frozen_inputs(directory)
                    self.assertEqual(frozen["runner"]["env"], selected)

    def test_source_and_artifact_identity_include_mode_and_reject_plugin_links(self):
        plugin = self.root / "plugin"
        plugin.mkdir()
        script = plugin / "script.sh"
        script.write_text("#!/bin/sh\n")
        script.chmod(0o755)
        original = EVAL.plugin_hashes(plugin)
        cache = plugin / "__pycache__/generated.pyc"
        cache.parent.mkdir(exist_ok=True)
        cache.write_bytes(b"generated cache")
        self.assertEqual(EVAL.plugin_hashes(plugin), original)
        script.chmod(0o644)
        self.assertNotEqual(EVAL.plugin_hashes(plugin), original)
        (plugin / "linked.sh").symlink_to(script)
        with self.assertRaisesRegex(ValueError, "Linked plugin source"):
            EVAL.plugin_hashes(plugin)
        self.freeze()
        provenance = self.root / "provenance"
        added = provenance / "fix-go-cves/scripts/new-source.py"
        added.write_text("print('unfrozen source')\n")
        with self.assertRaisesRegex(ValueError, "Frozen input changed"):
            EVAL.frozen_inputs(self.root)
        added.unlink()
        frozen_script = provenance / "fix-go-cves/scripts/fix-all.sh"
        frozen_script.chmod(frozen_script.stat().st_mode ^ 0o100)
        with self.assertRaisesRegex(ValueError, "Frozen input changed"):
            EVAL.frozen_inputs(self.root)

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
        workspace = self.root / "cases/case-005"
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

    def prepare(self, workspace, source):
        if source.parent.parent.name != "provenance":
            dataset = self.root / "prepare-fixtures"
            shutil.copytree(source, dataset / workspace.name)
            EVAL.freeze_run({"dataset": {"path": str(dataset)}}, dataset, self.root,
                            [workspace.name], self.root)
            source = self.root / "provenance/cases" / workspace.name
        return EVAL.prepare(workspace, source)

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
                self.prepare(workspace, source)
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
            "scripts/deliver.py": "# obsolete delivery adapter\n",
            "skills/fix-go-cves/SKILL.md": "historical instructions\n",
            "skills/fix-go-cves/references/obsolete.md": "stale historical reference\n",
        }), source / "plugin.tar.gz")
        (source / "run.log.gz").write_bytes(gzip.compress(b"recorded partial outcome\n"))
        with patch.object(EVAL, "run", side_effect=local_fetch), contextlib.redirect_stdout(io.StringIO()):
            baseline = self.prepare(workspace, source)
        plugin = workspace / ".staged-plugins/fix-go-cves"
        for path in (EVAL.EVAL_ROOT.parent / "skills/fix-go-cves").rglob("*"):
            if path.is_file():
                relative = path.relative_to(EVAL.EVAL_ROOT.parent)
                self.assertEqual((plugin / relative).read_bytes(), path.read_bytes())
                self.assertEqual(baseline["plugin_hashes"][str(relative)], EVAL.file_identity(path))
        self.assertFalse((plugin / "skills/fix-go-cves/references/obsolete.md").exists())
        self.assertEqual((plugin / "scripts/deliver.py").read_bytes(),
                         (EVAL.EVAL_ROOT.parent / "scripts/deliver.py").read_bytes())
        self.assertIn("# Historical runtime witness", (plugin / "scripts/fix-all.sh").read_text())

    def prepared_replay(self):
        workspace, source, data, local_fetch = self.prepare_local_repository()
        data.pop('mode')
        data['arguments'] = ['0.24']
        (source / 'input.yaml').write_text(yaml.safe_dump(data))
        expected = {'result_commit': data['default_commit'], 'fix_branch': 'recorded-result', 'exit_code': 2}
        (source / 'annotations.yaml').write_text(yaml.safe_dump(expected))
        repository = self.root / 'repository'
        EVAL.git(repository, 'branch', 'recorded-result', data['default_commit'])
        EVAL.git(repository, 'bundle', 'create', str(source / 'result.bundle'), 'recorded-result')
        shutil.copy2(self.archive(files={'scripts/fix-all.sh': '#!/bin/sh\nexit 2\n'}),
                     source / 'plugin.tar.gz')
        body = 'recorded partial outcome\n'
        (source / 'run.log.gz').write_bytes(gzip.compress(body.encode()))
        with patch.object(EVAL, 'run', side_effect=local_fetch), contextlib.redirect_stdout(io.StringIO()):
            baseline = self.prepare(workspace, source)
        (workspace / '.hook-outputs.json').unlink()
        return workspace, baseline, body

    def test_prepared_remote_role_matches_frozen_repository_and_survives_replay(self):
        workspace, baseline, body = self.prepared_replay()
        meta = baseline['meta']
        remote = EVAL.git(workspace, 'config', '--get', 'checkout.defaultRemote')
        owner, repository = EVAL.repository_identity(meta['repository'])
        upstream = workspace / '.replay/remotes/upstream' / owner / (repository + '.git')
        self.assertEqual(EVAL.git(workspace, 'remote', 'get-url', remote), str(upstream))
        self.assertEqual(EVAL.git(workspace, 'rev-parse', f'refs/remotes/{remote}/{meta["base_branch"]}'),
                         meta['base_commit'])
        self.assertEqual(EVAL.git(workspace, 'branch', '--list', meta['base_branch']), '')
        config = (workspace / '.git/config').read_bytes()
        resolved = subprocess.run(['bash', '-c', 'source "$1"; discover_upstream_remote "$2"',
                                  'remote-fixture', str(workspace / '.staged-plugins/fix-go-cves/scripts/lib.sh'),
                                  meta['base_branch']], cwd=workspace, env=os.environ,
                                 capture_output=True, text=True, check=True)
        self.assertEqual(resolved.stdout.strip(), remote)
        self.attach_native(workspace, {'expected': meta}, body, 2, staged_engine=True)
        self.assertEqual(EVAL.git(workspace, 'rev-parse', 'HEAD'), meta['result_commit'])
        self.assertEqual(EVAL.git(workspace, 'branch', '--show-current'), meta['fix_branch'])
        self.assertEqual((workspace / '.git/config').read_bytes(), config)

    def collect_native(self, workspace):
        # Native stream/status live outside the checkout until collection.
        artifacts = {path: path.read_bytes() for path in
                     (workspace / 'stdout.log', workspace / 'run_result.json')}
        for path in artifacts:
            path.unlink()
        EVAL.capture(workspace)
        for path, content in artifacts.items():
            path.write_bytes(content)
        EVAL.extract(self.root)

    def test_capture_rejects_truncated_and_changed_invocation_witness(self):
        workspace, baseline, body = self.prepared_replay()
        calls = workspace / '.replay/invocations.jsonl'
        command = ['bash', str(workspace / '.staged-plugins/fix-go-cves/scripts/fix-all.sh'), 'wrong-branch']
        failed = subprocess.run(command, cwd=workspace, capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1)
        self.assertEqual(EVAL.events(calls)[0]['arguments'], ['wrong-branch'])
        truncate = [sys.executable, '-c',
                    'from pathlib import Path; Path(".replay/invocations.jsonl").write_text("")']
        subprocess.run(truncate, cwd=workspace, check=True)
        _, stream = self.attach_native(workspace, {'expected': baseline['meta']}, body, 2, staged_engine=True)
        earlier = []
        for identity, argv, output, error in (
                ('wrong-branch', command, failed.stdout + failed.stderr, True),
                ('truncate', truncate, '', False)):
            earlier.extend([
                {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': identity,
                    'name': 'Bash', 'input': {'command': shlex.join(argv)}}]}},
                {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': identity,
                    'content': output, 'is_error': error}]}, 'tool_use_result': {'stdout': output}}])
        (workspace / 'stdout.log').write_text('\n'.join(json.dumps(row) for row in [*earlier, *stream]))
        self.collect_native(workspace)
        self.assertEqual(len(EVAL.events(calls)), 1)
        self.assertEqual(EVAL.check(workspace), {'passed': False, 'reason': 'no forbidden operations'})
        invocation = EVAL.events(calls)[0]
        invocation['overrides']['CVE_FIX_GO_MINOR_GUARD'] = 'false'
        calls.write_text(json.dumps(invocation) + '\n')
        self.collect_native(workspace)
        state = EVAL.read_json(workspace / 'output/state.json')
        self.assertEqual(state['invocations'][0]['overrides']['CVE_FIX_GO_MINOR_GUARD'], 'false')
        self.assertIn('native artifact authenticated', EVAL.check(workspace)['reason'])

    def test_capture_rejects_changed_executed_driver_and_prepared_metadata(self):
        workspace, baseline, body = self.prepared_replay()
        private = workspace / '.replay'
        driver = private / 'driver.py'
        original = driver.read_bytes()
        driver.write_text(driver.read_text().replace('import argparse\n',
            'import argparse\nfrom pathlib import Path as DriverPath\n'
            'DriverPath(__file__).with_name("changed-driver-ran").write_text("executed")\n', 1))
        self.attach_native(workspace, {'expected': baseline['meta']}, body, 2, staged_engine=True)
        self.assertTrue((private / 'changed-driver-ran').exists())

        self.collect_native(workspace)
        state = EVAL.read_json(workspace / 'output/state.json')
        self.assertTrue(state['plugin_unchanged'])
        self.assertFalse(state['execution_inputs_unchanged'])
        self.assertEqual(state['dirty'], '')
        self.assertEqual(state['unexpected_ignored'], [])
        self.assertEqual(EVAL.check(workspace), {
            'passed': False, 'reason': 'prepared execution inputs unchanged'})

        driver.write_bytes(original)
        for name in ('driver.py', 'meta.json'):
            path = private / name
            content, mode = path.read_bytes(), path.stat().st_mode & 0o777
            for mutation in ('bytes', 'mode', 'missing', 'link'):
                with self.subTest(name=name, mutation=mutation):
                    if mutation == 'bytes':
                        path.write_bytes(content + b'\n')
                    elif mutation == 'mode':
                        path.chmod(mode ^ 0o100)
                    elif mutation == 'missing':
                        path.unlink()
                    else:
                        saved = self.root / f'original-{name}'
                        saved.write_bytes(content)
                        saved.chmod(mode)
                        path.unlink()
                        path.symlink_to(saved)
                    self.collect_native(workspace)
                    self.assertEqual(EVAL.check(workspace), {
                        'passed': False, 'reason': 'prepared execution inputs unchanged'})
                    path.unlink(missing_ok=True)
                    path.write_bytes(content)
                    path.chmod(mode)
        # The comparison binds metadata meaning as well as its baseline fingerprint.
        meta_path = private / 'meta.json'
        EVAL.write_json(meta_path, {**baseline['meta'], 'runtime_dir': '/changed-runtime'})
        changed = {**baseline, 'execution_inputs': {
            **baseline['execution_inputs'], 'meta.json': EVAL.file_identity(meta_path)}}
        EVAL.write_json(self.root / 'control/case-005/baseline.json', changed)
        self.collect_native(workspace)
        self.assertFalse(EVAL.read_json(workspace / 'output/state.json')['execution_inputs_unchanged'])
        EVAL.write_json(meta_path, baseline['meta'])
        EVAL.write_json(self.root / 'control/case-005/baseline.json', baseline)
        self.collect_native(workspace)
        self.assertTrue(EVAL.check(workspace)['passed'])

    def test_preparation_uses_frozen_plugin_after_current_source_changes(self):
        workspace, source, data, local_fetch = self.prepare_local_repository()
        # Stock workspace trees and collected/provenance runs have different roots.
        separate = self.root / "workspaces/run/cases/case-005"
        separate.parent.mkdir(parents=True)
        workspace.rename(separate)
        workspace = separate
        dataset = self.root / "frozen-fixtures"
        shutil.copytree(source, dataset / "case-005")
        current = self.root / "current-plugin"
        for name in (".claude-plugin", "skills", "scripts", "subagents"):
            shutil.copytree(EVAL.EVAL_ROOT.parent / name, current / name)
        shutil.copy2(EVAL.EVAL_ROOT.parent / "README.md", current / "README.md")
        skill = current / "skills/fix-go-cves/SKILL.md"
        frozen_skill = skill.read_bytes()
        cache = current / "scripts/__pycache__/generated.pyc"
        cache.parent.mkdir(exist_ok=True)
        cache.write_bytes(b"generated cache")
        raw = {"dataset": {"path": str(dataset)}}
        with patch.object(EVAL, "EVAL_ROOT", current / "evals"):
            EVAL.freeze_run(raw, dataset, self.root, ["case-005"], self.root)
        self.assertFalse((self.root / "provenance/fix-go-cves/scripts/__pycache__").exists())
        skill.write_text("changed after snapshot\n")
        frozen_source = self.root / "provenance/cases/case-005"
        with patch.object(EVAL, "run", side_effect=local_fetch), contextlib.redirect_stdout(io.StringIO()):
            self.prepare(workspace, frozen_source)
        self.assertEqual((workspace / ".staged-plugins/fix-go-cves/skills/fix-go-cves/SKILL.md").read_bytes(), frozen_skill)
        runtime = workspace.parent.parent / "control/case-005/runtime/plugin"
        self.assertEqual((runtime / "skills/fix-go-cves/SKILL.md").read_bytes(), frozen_skill)
        EVAL.capture(workspace)
        state = EVAL.read_json(workspace / "output/state.json")
        self.assertTrue(EVAL.expectations_match(state["expected"], data))
        self.assertIn(".replay/driver.py", (workspace / ".staged-plugins/fix-go-cves/scripts/fix-all.sh").read_text())

    def test_prepare_clean_pinned_trees_preserves_settings_and_allowed_paths(self):
        workspace, source, data, local_fetch = self.prepare_local_repository()
        settings = workspace / ".claude/settings.json"
        original_settings = settings.read_bytes()
        with patch.object(EVAL, "run", side_effect=local_fetch), \
                contextlib.redirect_stdout(io.StringIO()):
            self.prepare(workspace, source)
        self.assertEqual(settings.read_bytes(), original_settings)
        self.assertEqual(EVAL.git(workspace, "rev-parse", "HEAD"), data["default_commit"])
        self.assertEqual(EVAL.git(workspace, "branch", "--show-current"), "operator-start")
        self.assertTrue((workspace / "cmd/bin/source.go").is_file())
        EVAL.check_reserved_paths(workspace)

    def test_prepare_ignores_inherited_git_repository_selectors(self):
        workspace, source, data, local_fetch = self.prepare_local_repository()
        caller = self.root / 'caller'
        EVAL.git(self.root, 'clone', '--no-local', str(self.root / 'repository'), str(caller))
        index = self.root / 'caller-index'
        shutil.copyfile(caller / '.git/index', index)
        before, index_before = EVAL.file_hashes(caller), index.read_bytes()
        selectors = {'GIT_DIR': str(caller / '.git'), 'GIT_WORK_TREE': str(caller),
                     'GIT_COMMON_DIR': str(caller / '.git'), 'GIT_INDEX_FILE': str(index),
                     'GIT_OBJECT_DIRECTORY': str(caller / '.git/objects'),
                     'GIT_ALTERNATE_OBJECT_DIRECTORIES': str(caller / '.git/objects'),
                     'GIT_PREFIX': '', 'GIT_CONFIG': str(caller / '.git/config'),
                     'GIT_ALLOW_PROTOCOL': 'file', 'GIT_CONFIG_COUNT': '1',
                     'GIT_CONFIG_KEY_0': 'protocol.file.allow', 'GIT_CONFIG_VALUE_0': 'always'}
        with patch.dict(os.environ, selectors), patch.object(EVAL, 'run', side_effect=local_fetch), \
                contextlib.redirect_stdout(io.StringIO()):
            baseline = self.prepare(workspace, source)
            self.assertEqual(EVAL.git(workspace, 'config', '--get', 'protocol.file.allow'), 'always')
        self.assertEqual(EVAL.file_hashes(caller), before)
        self.assertEqual(index.read_bytes(), index_before)
        self.assertEqual(EVAL.git(workspace, 'rev-parse', 'HEAD'), data['default_commit'])
        self.assertEqual(baseline['meta']['base_commit'], data['base_commit'])

    def test_run_scrubs_supplied_git_selectors_and_preserves_other_settings(self):
        caller, target = self.root / 'caller', self.root / 'target'
        for repo in (caller, target):
            EVAL.git(self.root, 'init', str(repo))
        before = EVAL.file_hashes(caller)
        environment = {'PATH': os.environ['PATH'], 'GIT_DIR': str(caller / '.git'),
                       'GIT_WORK_TREE': str(caller), 'GIT_CONFIG': str(caller / '.git/config'),
                       'GIT_ALLOW_PROTOCOL': 'file', 'GIT_CONFIG_COUNT': '1',
                       'GIT_CONFIG_KEY_0': 'protocol.file.allow', 'GIT_CONFIG_VALUE_0': 'always',
                       'GIT_CONFIG_PARAMETERS': "'protocol.https.allow=never'", 'DRIVER_SETTING': 'retained'}
        supplied = dict(environment)
        EVAL.run('git', '-C', str(target), 'config', 'fixture.value', 'target', env=environment)
        self.assertEqual(EVAL.git(target, 'config', '--get', 'fixture.value'), 'target')
        self.assertEqual(EVAL.file_hashes(caller), before)
        self.assertEqual(EVAL.run('git', '-C', str(target), 'config', '--get', 'protocol.file.allow',
                                  env=environment), 'always')
        self.assertEqual(EVAL.run('git', '-C', str(target), 'config', '--get', 'protocol.https.allow',
                                  env=environment), 'never')
        observed = json.loads(EVAL.run(sys.executable, '-c',
            'import json,os; print(json.dumps([os.environ.get(k) for k in '
            '["GIT_ALLOW_PROTOCOL","DRIVER_SETTING","GIT_CONFIG"]]))', env=environment))
        self.assertEqual(observed, ['file', 'retained', None])
        self.assertEqual(environment, supplied)

class RunnerFailureTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ,
            {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}, clear=True))

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
                cases = ((code, output) for code in (0, 1, 2, 124)
                         for output in ("child output\n", "child output", "exit=0\nchild output"))
                for child_exit, child_output in cases:
                    with self.subTest(shell=shell, errexit=errexit, child_exit=child_exit,
                                      child_output=child_output), \
                            tempfile.TemporaryDirectory() as directory:
                        root = Path(directory)
                        (root / "scripts").mkdir()
                        (root / "scripts/fix-all.sh").write_text(
                            'printf "%s" "$CHILD_OUTPUT"\nexit "$CHILD_EXIT"\n')
                        result = subprocess.run(
                            [shell, *options, *(["-e"] if errexit else []), "-c", command],
                            env={**os.environ, "PLUGIN_ROOT": str(root), "TMPDIR": str(root),
                                 "CHILD_EXIT": str(child_exit), "CHILD_OUTPUT": child_output}, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                        logs = list(root.glob("fix-go-cves.*.log"))
                        self.assertEqual(len(logs), 1, result.stderr)
                        self.assertEqual(result.stdout.splitlines(), [f"LOG={logs[0]}"])
                        self.assertEqual(logs[0].read_text(),
                                         child_output + f"\nexit={child_exit}\n")
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
                harness_head = EVAL.git(harness, 'rev-parse', 'HEAD')
                caller = root / 'caller'
                EVAL.git(root, 'clone', '--no-local', str(harness), str(caller))
                (caller / 'sentinel').write_text('caller\n')
                EVAL.git(caller, 'add', 'sentinel')
                EVAL.git(caller, '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.test',
                         'commit', '-qm', 'caller')
                index = root / 'caller-index'
                shutil.copyfile(caller / '.git/index', index)
                caller_before, index_before = EVAL.file_hashes(caller), index.read_bytes()
                python = root / 'stage-python'
                python.write_text('''#!/usr/bin/env python3
import json, os, pathlib, shutil, sys
root = pathlib.Path(os.environ['RUNNER_TEST_ROOT'])
(root / 'stage-environment.json').write_text(json.dumps({key: os.environ.get(key) for key in
    ('GIT_ALLOW_PROTOCOL', 'GIT_CONFIG_COUNT', 'RUNNER_SETTING')}))
args = sys.argv[1:]
if '-c' in args:
    code = args[args.index('-c') + 1]
    if 'sys.executable' in code:
        print(pathlib.Path(__file__).resolve())
    elif 'tempfile' in code:
        print(root / 'workspaces')
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
                       'RUNNER_TEST_CODE': str(code),
                       'GIT_DIR': str(caller / '.git'), 'GIT_WORK_TREE': str(caller),
                       'GIT_COMMON_DIR': str(caller / '.git'), 'GIT_INDEX_FILE': str(index),
                       'GIT_OBJECT_DIRECTORY': str(caller / '.git/objects'),
                       'GIT_ALTERNATE_OBJECT_DIRECTORIES': str(caller / '.git/objects'),
                       'GIT_PREFIX': '', 'GIT_CONFIG': str(caller / '.git/config'),
                       'GIT_ALLOW_PROTOCOL': 'file', 'GIT_CONFIG_COUNT': '1',
                       'GIT_CONFIG_KEY_0': 'protocol.file.allow', 'GIT_CONFIG_VALUE_0': 'always',
                       'RUNNER_SETTING': 'retained'}
                result = subprocess.run(['bash', str(Path(__file__).with_name('run.sh')),
                                         '--run-id', 'run'], env=env, text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertEqual(result.returncode, code, result.stderr)
                revisions = list((root / 'runs').rglob('harness-revision.txt'))
                self.assertEqual(len(revisions), 1)
                self.assertEqual(revisions[0].read_text().strip(), harness_head)
                self.assertEqual(EVAL.file_hashes(caller), caller_before)
                self.assertEqual(index.read_bytes(), index_before)
                self.assertEqual(json.loads((root / 'stage-environment.json').read_text()),
                                 {'GIT_ALLOW_PROTOCOL': 'file', 'GIT_CONFIG_COUNT': '1', 'RUNNER_SETTING': 'retained'})
                self.assertEqual([json.loads(line) for line in
                                  (root / 'stages.jsonl').read_text().splitlines()], expected)
                self.assertEqual((root / 'collected/case-005/output/runtime.txt').read_text(),
                                 'completed engine evidence')
                self.assertIn('RESULTS:', result.stdout)

if __name__ == "__main__":
    unittest.main()
