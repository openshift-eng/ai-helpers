#!/usr/bin/env python3
"""Tests for the triage-manifest schema validator and merge."""
import copy
import gzip
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import clustering  # noqa: E402
import manifest as m  # noqa: E402
import prepass  # noqa: E402
import prior  # noqa: E402


def example():
    with open(os.path.join(HERE, 'fixtures', 'triage-manifest.example.json')) as f:
        return json.load(f)


def fresh_prepass():
    with gzip.open(os.path.join(HERE, 'fixtures', 'frozen-2026-10-07.json.gz'), 'rt') as f:
        inv = json.load(f)
    regs = inv['regressions'] if isinstance(inv, dict) and 'regressions' in inv else inv
    return prepass.weekly(regs, clustering.parse_ts('2026-10-07T12:00:00Z'), None,
                          view_status=[{'view': '4.22-main', 'fetch': 'complete'}])


class ManifestTest(unittest.TestCase):
    def test_example_manifest_validates(self):
        self.assertEqual(m.validate(example()), [])

    def test_schema_version_matches_prepass(self):
        self.assertEqual(m.SCHEMA_VERSION, "1.0")
        self.assertEqual(m.SCHEMA_VERSION, fresh_prepass()['schema_version'])

    def test_prepass_document_reports_only_missing_llm_keys(self):
        doc = fresh_prepass()
        errs = m.validate(doc)
        self.assertTrue(errs)
        for e in errs:
            self.assertRegex(e, r'^(missing top-level key: \w+|cluster \S+: missing (disposition|actions|escalation))$')
        self.assertIn('missing top-level key: audit', errs)
        cid = doc['clusters'][0]['id']
        self.assertIn('cluster %s: missing disposition' % cid, errs)

    def test_proposed_action_ids_must_be_subset_of_supported(self):
        d = example()
        d['clusters'][0]['disposition']['proposed_action']['regression_ids'] = [49533, 99999]
        self.assertTrue(any('99999' in e for e in m.validate(d)))

    def test_uncovered_members_must_be_unlinked(self):
        d = example()
        del d['clusters'][0]['members']['unlinked']
        errs = m.validate(d)
        self.assertTrue(any('49531' in e and 'unlinked' in e for e in errs))

    def test_none_action_may_omit_unlinked(self):
        d = example()
        c = d['clusters'][0]
        c['disposition']['proposed_action'] = {'type': 'none', 'regression_ids': [123456]}
        del c['members']['unlinked']
        self.assertEqual(m.validate(d), [])

    def test_evidence_requires_run_id_and_supported_ids(self):
        d = example()
        ev = d['clusters'][0]['disposition']['analysis']['evidence'][0]
        del ev['prowjob_run_id']
        ev['supports_regression_ids'] = []
        errs = m.validate(d)
        self.assertTrue(any('prowjob_run_id' in e for e in errs))
        self.assertTrue(any('supports_regression_ids' in e for e in errs))

    def test_catch_all_requires_all_four_rule_checks(self):
        d = example()
        del d['catch_all']['admitted'][0]['rule_checks']['pre_5_0']
        self.assertTrue(any('pre_5_0' in e for e in m.validate(d)))
        d = example()
        d['catch_all']['admitted'][0]['rule_checks']['examined'] = False
        self.assertTrue(any('examined' in e for e in m.validate(d)))

    def test_high_requires_escalation(self):
        d = example()
        d['clusters'][0]['escalation']['required'] = False
        self.assertTrue(any('escalation' in e for e in m.validate(d)))

    def test_unanalysed_high_still_requires_escalation(self):
        d = example()
        c = d['clusters'][0]
        c['disposition'] = {'state': 'UNANALYSED'}
        c['actions'] = []            # an unanalysed cluster proposes no write (a planned one would now fail validation)
        c['escalation']['required'] = False
        self.assertTrue(any('escalation' in e for e in m.validate(d)))
        c['escalation']['required'] = True
        self.assertEqual(m.validate(d), [])

    def test_unknown_states_are_allowed_values(self):
        d = example()
        d['audit']['guards']['jql_audit'] = 'unknown'
        d['audit']['guards']['sippy_diff'] = 'unknown'
        self.assertEqual(m.validate(d), [])
        d['audit']['guards']['jql_audit'] = 'maybe'
        self.assertTrue(any('jql_audit' in e for e in m.validate(d)))

    def test_enumerations_are_enforced(self):
        d = example()
        c = d['clusters'][0]
        c['blast_radius']['level'] = 'SEVERE'
        c['disposition']['state'] = 'BOGUS'
        c['actions'][0]['status'] = 'weird'
        d['observation']['symptom_probe']['status'] = 'ok|failed'
        errs = ' '.join(m.validate(d))
        for k in ('SEVERE', 'BOGUS', 'weird', 'symptom_probe'):
            self.assertIn(k, errs)

    def test_audit_keys_required(self):
        d = example()
        del d['audit']['receipt']
        del d['audit']['guards']['junit_backstop']
        errs = ' '.join(m.validate(d))
        self.assertIn('audit.receipt: missing', errs)
        self.assertIn('junit_backstop', errs)

    def test_merge_preserves_prepass_order_and_adds_dispositions(self):
        pp = fresh_prepass()
        before = copy.deepcopy(pp)
        ids = [c['id'] for c in pp['clusters']]
        disp = {i: {'state': 'UNANALYSED'} for i in ids}
        acts = {ids[0]: [{'type': 'none', 'status': 'planned'}]}
        out = m.merge(pp, disp, acts)
        self.assertEqual(pp, before)
        self.assertEqual([c['id'] for c in out['clusters']], ids)
        for c, o in zip(before['clusters'], out['clusters']):
            for k, v in c.items():
                self.assertEqual(o[k], v)
            self.assertEqual(o['disposition'], {'state': 'UNANALYSED'})
            self.assertEqual(o['escalation']['required'], c['blast_radius']['level'] == 'HIGH')
        self.assertEqual(out['clusters'][0]['actions'], acts[ids[0]])

    def test_merge_escalation_rules(self):
        pp = fresh_prepass()
        c = pp['clusters'][0]
        c['blast_radius']['level'] = 'ELEVATED'
        cid = c['id']
        out = m.merge(pp, {cid: {'state': 'UNEXPLAINED'}}, {})
        self.assertTrue(out['clusters'][0]['escalation']['required'])
        out = m.merge(pp, {cid: {'state': 'CANDIDATE'}}, {})
        self.assertFalse(out['clusters'][0]['escalation']['required'])
        esc = {'required': True, 'reason': 'llm'}
        disp = {cid: {'state': 'CANDIDATE', 'escalation': esc}}
        out = m.merge(pp, disp, {})
        self.assertEqual(out['clusters'][0]['escalation'], esc)

    def test_merge_applies_members_unlinked_from_disposition(self):
        pp = fresh_prepass()
        c = next(c for c in pp['clusters'] if len(c['members']['regression_ids']) >= 2)
        ids = c['members']['regression_ids']
        unl = [{'id': i, 'reason': 'no run evidence'} for i in ids[1:]]
        disp = {x['id']: {'state': 'UNANALYSED'} for x in pp['clusters']}
        disp[c['id']] = {
            'state': 'CANDIDATE', 'members_unlinked': unl,
            'analysis': {'evidence': [{'prowjob_run_id': '1', 'supports_regression_ids': [ids[0]]}]},
            'proposed_action': {'type': 'extend_triage', 'regression_ids': [ids[0]]}}
        out = m.merge(pp, disp, {})
        oc = next(x for x in out['clusters'] if x['id'] == c['id'])
        self.assertEqual(oc['members']['unlinked'], unl)
        self.assertNotIn('members_unlinked', oc['disposition'])
        out.update({'watch_list': [], 'catch_all': {'jira': 'OCPQUAL-88', 'triage_id': 851, 'admitted': []},
                    'backport_candidates': [], 'unanalysed': [], 'audit': example()['audit']})
        self.assertEqual(m.validate(out), [])

    def test_merge_rejects_non_list_members_unlinked(self):
        pp = fresh_prepass()
        cid = pp['clusters'][0]['id']
        with self.assertRaises(ValueError) as cm:
            m.merge(pp, {cid: {'state': 'UNANALYSED', 'members_unlinked': {'id': 1}}}, {})
        self.assertIn(cid, str(cm.exception))

    def test_merge_unknown_cluster_raises(self):
        with self.assertRaises(ValueError):
            m.merge(fresh_prepass(), {'c-nope': {'state': 'UNANALYSED'}}, {})

    def test_cli(self):
        cli = os.path.join(HERE, 'manifest.py')
        ex = os.path.join(HERE, 'fixtures', 'triage-manifest.example.json')
        self.assertEqual(subprocess.run([sys.executable, cli, 'validate', ex]).returncode, 0)
        with tempfile.TemporaryDirectory() as t:
            bad = os.path.join(t, 'bad.json')
            with open(bad, 'w') as f:
                json.dump({'schema_version': '1.0'}, f)
            r = subprocess.run([sys.executable, cli, 'validate', bad], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn('missing top-level key: audit', r.stderr)
            pp = fresh_prepass()
            paths = {}
            for name, obj in (('p', pp), ('d', {c['id']: {'state': 'UNANALYSED'} for c in pp['clusters']}),
                              ('a', {})):
                paths[name] = os.path.join(t, name + '.json')
                with open(paths[name], 'w') as f:
                    json.dump(obj, f)
            out = os.path.join(t, 'm.json')
            r = subprocess.run([sys.executable, cli, 'merge', '--prepass', paths['p'], '--dispositions',
                                paths['d'], '--actions', paths['a'], '--out', out],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)  # top-level LLM keys still missing
            self.assertTrue(os.path.exists(out))

    def test_validate_never_raises_on_malformed_documents(self):
        def mut(fn):
            d = example()
            fn(d)
            return d
        docs = [
            {}, [],
            mut(lambda d: d['clusters'].__setitem__(0, [])),
            mut(lambda d: d['clusters'][0].__setitem__('actions', [5])),
            mut(lambda d: d['catch_all'].__setitem__('admitted', ['x'])),
            mut(lambda d: d['observation'].__setitem__('symptom_probe', 'ok')),
            mut(lambda d: d['clusters'][0].__setitem__('members', [])),
            mut(lambda d: d['clusters'][0].__setitem__('blast_radius', 'HIGH')),
            mut(lambda d: d['clusters'][0]['disposition']['analysis']['evidence'][0].__setitem__(
                'supports_regression_ids', [[1]])),
        ]
        for doc in docs:
            errs = m.validate(doc)
            self.assertTrue(errs, doc)
        self.assertIn('cluster 0: expected object, got list', m.validate(docs[2]))
        self.assertTrue(any('c-7f3a9e: members must' in e or 'c-7f3a9e' in e for e in m.validate(docs[6])))

    def test_merge_gives_actions_to_clusters_without_disposition(self):
        pp = fresh_prepass()
        ids = [c['id'] for c in pp['clusters']]
        out = m.merge(pp, {}, {ids[0]: [{'type': 'none', 'status': 'planned'}]})
        self.assertEqual(out['clusters'][0]['actions'], [{'type': 'none', 'status': 'planned'}])
        if len(ids) > 1:
            self.assertEqual(out['clusters'][-1]['actions'], [])
        self.assertNotIn('disposition', out['clusters'][0])
        self.assertNotIn('escalation', out['clusters'][0])

    def test_merge_unknown_actions_cluster_raises(self):
        with self.assertRaises(ValueError):
            m.merge(fresh_prepass(), {}, {'c-nope': []})

    def test_finalize_injects_runner_audit_and_run_metadata(self):
        ex = example()
        jira = {"status": "ok", "count": 1, "raw_matched": 1, "truncated": False,
                "issues": [{"key": "OCPBUGS-999", "created": "2026-10-13T06:00:00+0000"}],
                "window": ["2026-10-13T05:00:00Z", "2026-10-13T08:00:00Z"], "error": None}
        sippy = {"status": "match", "undeclared": [], "declared_not_observed": []}
        perms = {"status": "ok", "projects": ["OCPBUGS"], "create_issues": True, "edit_issues": True}
        out = m.finalize(ex, jira_creations=jira, sippy_diff=sippy, permissions=perms,
                         mode_requested="auto", mode_effective="report",
                         decision=("report", "2105", "inherited downgrade from 2105: x"),
                         source_run={"job": "periodic-x", "run_id": "2200", "url": "https://prow/x/2200",
                                     "started": "2026-10-13T05:00:12Z"},
                         previous_run="2105", existing_only=True)
        a = out["audit"]
        self.assertEqual(a["account_wide_creations"]["count"], 1)
        self.assertEqual(a["account_wide_creations"]["attribution"][0]["key"], "OCPBUGS-999")
        self.assertEqual(a["account_wide_creations"]["attribution"][0]["attributed_to"], "unresolved")
        self.assertEqual(a["sippy_catalog_diff"]["status"], "match")
        self.assertEqual(a["jira_permissions"]["create_issues"], True)
        self.assertEqual(a["receipt"], {"previous_run": "2105", "honoured": True, "downgraded_to_report": True,
                                        "origin": "2105", "reason": "inherited downgrade from 2105: x"})
        self.assertEqual(a["guards"]["jql_audit"], "fail")      # creations observed
        self.assertEqual(a["guards"]["sippy_diff"], "match")
        self.assertEqual(a["guards"]["existing_only_flag"], True)
        self.assertEqual(out["source_run"]["job"], "periodic-x")
        self.assertEqual(out["source_run"]["run_id"], "2200")
        self.assertEqual(out["policy"]["write_mode"], "report")
        self.assertEqual(out["policy"]["existing_only"], True)
        self.assertEqual(m.validate(out), [])
        # the agent's own jira_writes list is preserved, not replaced
        self.assertEqual(out["audit"]["jira_writes"], ex["audit"]["jira_writes"])

    def test_finalize_unknown_audits_are_unknown_guards(self):
        ex = example()
        out = m.finalize(ex, jira_creations={"status": "unknown", "count": None, "error": "401"},
                         sippy_diff={"status": "unknown", "error": "snapshots missing"}, permissions={"status": "unknown"},
                         mode_requested="report", mode_effective="report", decision=("report", "", "no receipt"),
                         source_run={"job": "j", "run_id": "1", "url": "u", "started": "t"}, previous_run=None,
                         existing_only=True)
        self.assertEqual(out["audit"]["guards"]["jql_audit"], "unknown")
        self.assertEqual(out["audit"]["guards"]["sippy_diff"], "unknown")
        self.assertIsNone(out["audit"]["account_wide_creations"]["count"])
        self.assertEqual(m.validate(out), [])

    def test_finalize_truncated_jira_audit_is_fail(self):
        ex = example()
        out = m.finalize(ex, jira_creations={"status": "ok", "count": 0, "truncated": True, "issues": []},
                         sippy_diff={"status": "match"}, permissions={"status": "ok"},
                         mode_requested="auto", mode_effective="auto", decision=("configured", "", ""),
                         source_run={"job": "j", "run_id": "1", "url": "u", "started": "t"}, previous_run="0",
                         existing_only=True)
        self.assertEqual(out["audit"]["guards"]["jql_audit"], "fail")

    def test_finalize_cli(self):
        cli = os.path.join(HERE, 'manifest.py')
        with tempfile.TemporaryDirectory() as t:
            def w(name, obj):
                p = os.path.join(t, name)
                with open(p, 'w') as f:
                    json.dump(obj, f)
                return p
            man = w('m.json', example())
            jira = w('j.json', {"status": "ok", "count": 0, "issues": [], "truncated": False})
            sip = w('s.json', {"status": "match", "undeclared": [], "declared_not_observed": []})
            per = w('p.json', {"status": "ok", "create_issues": True, "edit_issues": True, "projects": ["OCPBUGS"]})
            out = os.path.join(t, 'final.json')
            r = subprocess.run([sys.executable, cli, 'finalize', '--manifest', man, '--out', out,
                                '--jira-creations', jira, '--sippy-diff', sip, '--permissions', per,
                                '--mode-requested', 'report', '--mode-effective', 'report',
                                '--decision', 'report\t\tno receipt from the latest preceding attempt',
                                '--job', 'periodic-x', '--run-id', '2200', '--url', 'https://prow/x', '--started', '2026-10-13T05:00:12Z',
                                '--existing-only', 'true'], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(out) as f:
                doc = json.load(f)
            self.assertEqual(doc["audit"]["guards"]["jql_audit"], "pass")
            self.assertEqual(doc["audit"]["receipt"]["downgraded_to_report"], True)
            self.assertEqual(doc["source_run"]["run_id"], "2200")

    def test_top_level_containers_must_have_the_right_shape(self):
        for key, bad in (('policy', None), ('policy', {}), ('source_run', None), ('source_run', {}), ('observation', {}),
                         ('observation', None), ('baseline_run', []), ('clusters', None), ('clusters', {}),
                         ('watch_list', None), ('catch_all', []), ('backport_candidates', {}), ('unanalysed', None),
                         ('audit', None), ('audit', [])):
            x = example(); x[key] = bad
            errs = m.validate(x)
            self.assertTrue(any(key in e for e in errs), (key, bad, errs))
        x = example(); x['clusters'] = []            # a quiet week is valid
        self.assertEqual([e for e in m.validate(x) if 'clusters' in e], [])

    def test_actions_are_bound_to_members_and_evidence(self):
        x = example(); c = x['clusters'][0]
        c['actions'][0].update(type='extend_triage', status='done', regression_ids=[99999])
        c['disposition']['proposed_action'] = {'type': 'none'}
        errs = m.validate(x)
        self.assertTrue(any('99999' in e and 'action' in e for e in errs), errs)
        # an action on a member that no evidence item supports is also an error
        x = example(); c = x['clusters'][0]
        member = c['members']['regression_ids'][0]
        for ev in c['disposition']['analysis']['evidence']:
            ev['supports_regression_ids'] = [i for i in ev['supports_regression_ids'] if i != member]
        c['disposition']['proposed_action'] = {'type': 'none'}
        c['members']['unlinked'] = [{'id': member, 'reason': 'no own-run evidence'}]
        c['actions'] = [{'type': 'extend_triage', 'triage_id': 1, 'jira': 'OCPBUGS-1', 'regression_ids': [member], 'status': 'done'}]
        errs = m.validate(x)
        self.assertTrue(any(str(member) in e and 'evidence' in e for e in errs), errs)

    def test_duplicate_cluster_ids_are_rejected(self):
        x = example(); x['clusters'].append(copy.deepcopy(x['clusters'][0]))
        self.assertTrue(any('duplicate' in e for e in m.validate(x)))
        pp = fresh_prepass(); pp['clusters'].append(copy.deepcopy(pp['clusters'][0]))
        with self.assertRaises(ValueError):
            m.merge(pp, {}, {})

    def test_validate_never_raises_on_wave2_shapes(self):
        shapes = []
        x = example(); x['clusters'][0]['disposition']['analysis']['evidence'] = [None, 1, 'x']; shapes.append(x)
        x = example(); x['clusters'][0]['id'] = []; shapes.append(x)
        x = example(); x['clusters'][0]['id'] = {'a': 1}; x['clusters'].append(copy.deepcopy(x['clusters'][0])); shapes.append(x)
        x = example(); x['clusters'][0]['actions'][0]['regression_ids'] = [[1], {'a': 2}]; shapes.append(x)
        x = example(); x['clusters'][0]['members']['regression_ids'] = None; shapes.append(x)
        x = example(); x['catch_all'] = {'admitted': [None, {'regression_id': [1]}]}; shapes.append(x)
        for doc in shapes:
            errs = m.validate(doc)            # must not raise
            self.assertTrue(errs)

    def _catch_all_doc(self, triage_id=851, admitted=True):
        x = example(); c = x['clusters'][0]
        member = c['members']['regression_ids'][0]
        c['disposition']['state'] = 'UNEXPLAINED'
        c['disposition']['proposed_action'] = {'type': 'none'}
        c['actions'] = [{'type': 'catch_all', 'triage_id': triage_id, 'jira': 'OCPQUAL-88',
                         'regression_ids': [member], 'status': 'skipped-report-mode'}]
        x['catch_all'] = {'jira': 'OCPQUAL-88', 'triage_id': 851, 'admitted': []}
        if admitted:
            x['catch_all']['admitted'] = [{'regression_id': member, 'signature': 's', 'status': 'skipped-report-mode',
                                           'rule_checks': {'examined': True, 'no_bug_meets_bar': True, 'not_in_cluster': True, 'pre_5_0': True}}]
        return x, member

    def test_catch_all_action_must_match_an_admission_and_the_catch_all_triage(self):
        x, member = self._catch_all_doc()
        self.assertEqual(m.validate(x), [])                                   # admitted + right triage → valid
        x, member = self._catch_all_doc(admitted=False)
        self.assertTrue(any('catch_all' in e and str(member) in e for e in m.validate(x)))
        x, member = self._catch_all_doc(triage_id=810)
        self.assertTrue(any('catch_all' in e and '810' in e for e in m.validate(x)))

    def test_missing_catch_all_configuration_does_not_skip_the_rule(self):
        x, member = self._catch_all_doc(admitted=False)
        x['clusters'][0]['actions'][0]['status'] = 'done'
        x['catch_all'] = {}
        self.assertTrue(any('catch_all' in e for e in m.validate(x)))
        x, member = self._catch_all_doc(triage_id=810)
        x['clusters'][0]['actions'][0]['status'] = 'done'
        x['catch_all'].pop('triage_id')
        self.assertTrue(any('catch_all.triage_id' in e for e in m.validate(x)))

    def test_malformed_evidence_items_are_reported_even_without_a_write(self):
        x = example(); c = x['clusters'][0]
        c['disposition'] = {'state': 'UNANALYSED', 'analysis': {'depth': 'none', 'confidence': 'low', 'root_cause': 'r',
                                                                'evidence': [None, 1, 'x'], 'unverified_hypotheses': []}}
        c['actions'] = []
        c['escalation']['required'] = True
        errs = m.validate(x)
        self.assertEqual(len([e for e in errs if 'evidence' in e and 'expected object' in e]), 3, errs)

    def test_cli_error_paths_and_merge_then_validate(self):
        cli = os.path.join(HERE, 'manifest.py')
        ex = example()
        with tempfile.TemporaryDirectory() as t:
            def w(name, obj):
                p = os.path.join(t, name)
                with open(p, 'w') as f:
                    json.dump(obj, f)
                return p
            pp = fresh_prepass()
            # one-cluster prepass built from the example so a complete document is possible
            pre = {k: ex[k] for k in m.TOP_PREPASS}
            pre['clusters'] = [{k: v for k, v in ex['clusters'][0].items() if k not in m.CLUSTER_LLM}]
            cid = pre['clusters'][0]['id']
            disp = {cid: ex['clusters'][0]['disposition']}
            disp[cid] = dict(disp[cid], escalation=ex['clusters'][0]['escalation'])
            acts = {cid: ex['clusters'][0]['actions']}
            extra = {k: ex[k] for k in m.TOP_LLM}
            out = os.path.join(t, 'm.json')
            base = [sys.executable, cli, 'merge', '--prepass', w('p.json', pre), '--dispositions', w('d.json', disp),
                    '--actions', w('a.json', acts), '--out', out]
            r = subprocess.run(base + ['--extra', w('e.json', extra)], capture_output=True, text=True)
            self.assertEqual((r.returncode, r.stderr), (0, ''))
            bad = subprocess.run([sys.executable, cli, 'merge', '--prepass', w('p2.json', pp), '--dispositions',
                                  w('d2.json', {'c-nope': {}}), '--actions', w('a2.json', {}), '--out', out],
                                 capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1)
            self.assertNotIn('Traceback', bad.stderr)
            self.assertEqual(len(bad.stderr.strip().splitlines()), 1)
            miss = subprocess.run([sys.executable, cli, 'merge', '--prepass', os.path.join(t, 'none.json'),
                                   '--dispositions', w('d3.json', {}), '--actions', w('a3.json', {}), '--out', out],
                                  capture_output=True, text=True)
            self.assertEqual(miss.returncode, 1)
            self.assertNotIn('Traceback', miss.stderr)
            v = subprocess.run([sys.executable, cli, 'validate', out])
            self.assertEqual(v.returncode, 0)


def _unanalysed_disposition():
    return {'state': 'UNANALYSED',
            'analysis': {'depth': 'none', 'confidence': 'low', 'owning_component': None, 'triage_type': None,
                         'root_cause': None, 'evidence': [], 'unverified_hypotheses': []},
            'bug_search': {'candidates': [], 'newer_release_fix': None},
            'proposed_action': {'type': 'none'}}


def with_prior(base_run='2105...', run_id='2108...'):
    """A full current manifest (the example) whose cluster carries a Task-1 prior projected from a baseline
    that is the same example one run earlier. Returns (current, baseline)."""
    base = example()
    base['clusters'] = base['clusters'][:1]
    base['source_run']['run_id'] = base_run
    base['observation']['time'] = '2026-10-06T05:03:40Z'
    base['observation']['views'] = [{'view': '4.22-main', 'fetch': 'complete'}]
    cur = example()
    cur['clusters'] = cur['clusters'][:1]
    cur['source_run']['run_id'] = run_id
    cur['baseline_run'] = {'run_id': base_run, 'manifest_url': None, 'schema_version': '1.0', 'compatible': True}
    for c in cur['clusters']:
        c.pop('prior', None)
    prior.attach_priors(cur['clusters'], base)
    return cur, base


class PriorEnvelopeTest(unittest.TestCase):
    """Task 2: optional history is accepted without retrospective validation; only new envelopes are checked."""

    def test_missing_and_null_prior_validate(self):
        self.assertEqual(m.validate(example()), [])
        doc = example()
        doc['clusters'][0]['prior'] = None
        self.assertEqual(m.validate(doc), [])

    def test_projected_prior_validates_and_legacy_values_stay_opaque(self):
        cur, base = with_prior()
        self.assertEqual(cur['clusters'][0]['prior']['relationship'], 'same-id')
        self.assertEqual(m.validate(cur), [])
        # a legacy unknown bar in the *baseline* is preserved through projection and never invalidates the
        # current manifest; the old validator has no candidate-domain rule either
        base2 = copy.deepcopy(base)
        base2['clusters'][0]['disposition']['bug_search']['candidates'][0]['bar_met'] = 'unknown'
        self.assertEqual(m.validate(base2), [])
        cur2 = example()
        cur2['clusters'] = cur2['clusters'][:1]
        cur2['source_run']['run_id'] = '2108...'
        cur2['baseline_run'] = dict(cur['baseline_run'])
        prior.attach_priors(cur2['clusters'], base2)
        self.assertEqual(cur2['clusters'][0]['prior']['sources'][0]['bug_search']['candidates'][0]['bar_met'], 'unknown')
        self.assertEqual(m.validate(cur2), [])
        cur2['clusters'][0]['prior']['sources'][0]['actions'] = [{'status': 'legacy', 'regression_ids': 'unknown'}]
        cur2['clusters'][0]['prior']['sources'][0]['state'] = 'SOMETHING-OLD'
        self.assertEqual(m.validate(cur2), [])

    def test_malformed_new_envelopes_are_reported_by_field(self):
        cur, _ = with_prior()
        for bad in ([], 'r0', True, {}, {'sources': [None]}):
            doc = copy.deepcopy(cur)
            doc['clusters'][0]['prior'] = bad
            errors = m.validate(doc)
            self.assertTrue(errors, bad)
            self.assertTrue(any('prior' in e for e in errors), errors)
        cases = [
            (lambda pr: pr['sources'][0].__setitem__('member_ids', [1.5]), 'member_ids'),
            (lambda pr: pr['sources'][0].__setitem__('matched_member_ids', [999999]), 'matched_member_ids'),
            (lambda pr: pr['sources'][0].__setitem__('history_only', 'no'), 'history_only'),
            (lambda pr: pr['sources'][0].__setitem__('unfinished', 1), 'unfinished'),
            (lambda pr: pr['sources'][0]['analysis'].__setitem__('evidence_refs', [{'prowjob_run_id': ''}]), 'evidence_refs'),
            (lambda pr: pr['sources'][0]['analysis'].__setitem__('root_cause', 'x' * 2001), 'root_cause'),
            (lambda pr: pr['sources'][0]['analysis'].__setitem__('basis', {'run_id': 'r', 'depth': 'guess'}), 'basis'),
            (lambda pr: pr.__setitem__('relationship', 'cousin'), 'relationship'),
            (lambda pr: pr.__setitem__('member_delta', {'added': [], 'removed': [49999]}), 'member_delta'),
            (lambda pr: pr.__setitem__('observation_complete', 'yes'), 'observation_complete'),
            (lambda pr: pr.__setitem__('write_mode', 'dry'), 'write_mode'),
            (lambda pr: pr.__setitem__('observed_at', 'yesterday'), 'observed_at'),
            (lambda pr: pr['sources'].append(copy.deepcopy(pr['sources'][0])), 'duplicate'),
            (lambda pr: pr['sources'][0].__setitem__('history_only', True), 'immediate'),
            (lambda pr: pr['sources'][0].__setitem__('cluster_id', ''), 'cluster_id'),
            (lambda pr: pr['sources'][0].__setitem__('bug_search', 'none'), 'bug_search'),
        ]
        for mutate, field in cases:
            doc = copy.deepcopy(cur)
            mutate(doc['clusters'][0]['prior'])
            errors = m.validate(doc)
            self.assertTrue(any(field in e for e in errors), (field, errors))

    def test_prior_context_binds_immediate_sources_to_the_baseline_run(self):
        cur, _ = with_prior()
        doc = copy.deepcopy(cur)
        doc['baseline_run']['run_id'] = 'r-other'
        self.assertTrue(any('baseline_run' in e for e in m.validate(doc)))
        doc = copy.deepcopy(cur)
        doc['clusters'][0]['prior']['sources'][0]['run_id'] = 'r-older'
        self.assertTrue(any('run_id' in e for e in m.validate(doc)))
        doc = copy.deepcopy(cur)
        doc['baseline_run']['compatible'] = False
        self.assertTrue(any('compatible' in e for e in m.validate(doc)))
        # a retained history-only snapshot may legitimately be older than the latest attempt
        doc = copy.deepcopy(cur)
        retained = copy.deepcopy(doc['clusters'][0]['prior']['sources'][0])
        retained.update(run_id='r-older', observed_at='2026-09-29T05:03:40Z', history_only=True, unfinished=False)
        doc['clusters'][0]['prior']['sources'].append(retained)
        self.assertEqual(m.validate(doc), [])

    def test_unreached_attempt_history_validates_without_coverage(self):
        """R1 immediate (UNANALYSED) + R0 history-only; the current cluster has no action and no coverage."""
        cur, base = with_prior(base_run='r0', run_id='r1')
        r1 = copy.deepcopy(cur)
        r1['clusters'][0]['disposition'] = _unanalysed_disposition()
        r1['clusters'][0]['actions'] = []
        r1['clusters'][0]['escalation'] = {'required': True, 'reason': 'blast_radius HIGH'}
        r1['unanalysed'] = [{'cluster_id': r1['clusters'][0]['id'], 'reason': 'budget', 'blast_radius': 'HIGH'}]
        self.assertEqual(m.validate(r1), [])
        r2 = example()
        r2['clusters'] = r2['clusters'][:1]
        r2['source_run']['run_id'] = 'r2'
        r2['baseline_run'] = {'run_id': 'r1', 'manifest_url': None, 'schema_version': '1.0', 'compatible': True}
        r2['clusters'][0]['disposition'] = _unanalysed_disposition()
        r2['clusters'][0]['actions'] = []
        r2['clusters'][0]['members'].pop('unlinked', None)
        prior.attach_priors(r2['clusters'], r1)
        self.assertEqual([(s['run_id'], s['history_only']) for s in r2['clusters'][0]['prior']['sources']],
                         [('r1', False), ('r0', True)])
        self.assertEqual(m.validate(r2), [])


class PriorMergeTest(unittest.TestCase):
    def _one_cluster_prepass(self):
        cur, _ = with_prior()
        pre = {k: cur[k] for k in m.TOP_PREPASS}
        pre['clusters'] = [{k: v for k, v in cur['clusters'][0].items() if k not in m.CLUSTER_LLM}]
        return pre, cur

    def test_merge_preserves_prior_and_never_replays_actions(self):
        pre, cur = self._one_cluster_prepass()
        cid = pre['clusters'][0]['id']
        before = copy.deepcopy(pre)
        disp = {cid: dict(cur['clusters'][0]['disposition'], escalation=cur['clusters'][0]['escalation'])}
        merged = m.merge(pre, disp, {})
        self.assertEqual(merged['clusters'][0]['prior'], pre['clusters'][0]['prior'])
        self.assertEqual(merged['clusters'][0]['actions'], [])
        self.assertEqual(merged['clusters'][0]['prior']['sources'][0]['actions'][0]['status'], 'planned')
        self.assertEqual(pre, before)
        final = m.finalize(merged, jira_creations={'status': 'ok', 'count': 0, 'window': []},
                           sippy_diff={'status': 'match'}, permissions={'status': 'ok'},
                           mode_requested='report', mode_effective='report', decision=('auto', '', ''),
                           source_run={'job': 'j', 'run_id': '2108...', 'url': 'u', 'started': 's'},
                           previous_run='2105...', existing_only=True)
        self.assertEqual(final['clusters'][0]['prior'], pre['clusters'][0]['prior'])

    def test_disposition_may_not_replace_prior(self):
        pre, cur = self._one_cluster_prepass()
        cid = pre['clusters'][0]['id']
        with self.assertRaises(ValueError) as ctx:
            m.merge(pre, {cid: {'state': 'UNANALYSED', 'prior': None}}, {})
        self.assertIn('prior', str(ctx.exception))

    def test_cli_extra_may_not_replace_clusters(self):
        cli = os.path.join(HERE, 'manifest.py')
        pre, cur = self._one_cluster_prepass()
        cid = pre['clusters'][0]['id']
        with tempfile.TemporaryDirectory() as t:
            def w(name, obj):
                path = os.path.join(t, name)
                with open(path, 'w') as f:
                    json.dump(obj, f)
                return path
            disp = {cid: dict(cur['clusters'][0]['disposition'], escalation=cur['clusters'][0]['escalation'])}
            out = os.path.join(t, 'm.json')
            base = [sys.executable, cli, 'merge', '--prepass', w('p.json', pre), '--dispositions', w('d.json', disp),
                    '--actions', w('a.json', {cid: cur['clusters'][0]['actions']}), '--out', out]
            extra = {k: cur[k] for k in m.TOP_LLM}
            ok = subprocess.run(base + ['--extra', w('e.json', extra)], capture_output=True, text=True)
            self.assertEqual((ok.returncode, ok.stderr), (0, ''))
            with open(out) as f:
                self.assertEqual(json.load(f)['clusters'][0]['prior'], pre['clusters'][0]['prior'])
            bad = subprocess.run(base + ['--extra', w('e2.json', dict(extra, clusters=[]))],
                                 capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1)
            self.assertIn('clusters', bad.stderr)
            unrelated = subprocess.run(base + ['--extra', w('e3.json', dict(extra, note='kept'))],
                                       capture_output=True, text=True)
            self.assertEqual(unrelated.returncode, 0)


OWN1 = 'https://example.invalid/own-1/junit.xml'


def carried_doc():
    """One LOW cluster (member 49533) whose analysis is carried from a same-id finished source of run r0."""
    base = example()
    base['clusters'] = base['clusters'][:1]
    base['source_run']['run_id'] = 'r0'
    base['observation']['time'] = '2026-10-12T05:03:40Z'
    base['observation']['views'] = [{'view': '4.22-main', 'fetch': 'complete'}]
    bc = base['clusters'][0]
    bc['members']['regression_ids'] = [49533]
    bc['members']['unlinked'] = []
    bc['blast_radius']['level'] = 'LOW'
    bc['disposition']['analysis']['depth'] = 'deep-dive'
    bc['disposition']['analysis']['evidence'][0]['prowjob_run_id'] = 'own-0'
    bc['actions'][0]['status'] = 'skipped-report-mode'
    bc['escalation'] = {'required': False, 'reason': 'not required'}

    doc = example()
    doc['clusters'] = doc['clusters'][:1]
    doc['source_run']['run_id'] = 'r1'
    doc['baseline_run'] = {'run_id': 'r0', 'manifest_url': None, 'schema_version': '1.0', 'compatible': True}
    doc['observation']['views'] = [{'view': '4.22-main', 'fetch': 'complete'}]
    doc['policy']['write_mode'] = 'report'
    c = doc['clusters'][0]
    c['members']['regression_ids'] = [49533]
    c['members']['new_since_baseline'] = []
    c['members']['unlinked'] = []
    c['shape'].update(regressions=1, growth_since_baseline=0)
    c['blast_radius']['level'] = 'LOW'
    c['escalation'] = {'required': False, 'reason': 'not required'}
    an = c['disposition']['analysis']
    an['depth'] = 'carried-forward'
    an['confidence'] = 'high'
    an['evidence'] = [{'claim': 'same own-test signature', 'artifact': OWN1, 'quote': 'exact line',
                       'prowjob_run_id': 'own-1', 'supports_regression_ids': [49533]}]
    c['actions'] = [{'type': 'extend_triage', 'triage_id': 810, 'jira': 'OCPBUGS-129375', 'regression_ids': [49533],
                     'status': 'skipped-report-mode', 'result_url': None, 'error': None}]
    c['disposition']['proposed_action']['regression_ids'] = [49533]
    prior.attach_priors(doc['clusters'], base)
    source = c['prior']['sources'][0]
    assert source['analysis']['basis'] == {'run_id': 'r0', 'cluster_id': c['id'],
                                           'observed_at': '2026-10-12T05:03:40Z', 'depth': 'deep-dive'}, source
    an['reverification'] = {
        'source_run_id': 'r0', 'source_cluster_ids': [c['id']], 'basis': dict(source['analysis']['basis']),
        'outcome': 'carried', 'reason': 'same own-test signature on own-1; OCPBUGS-129375 still Verified, triage 810 unresolved',
        'checked_at': '2026-10-13T06:10:00Z', 'own_run_ids': ['own-1'],
        'lookup_locators': ['https://example.invalid/jira/OCPBUGS-129375', 'https://example.invalid/triages/810']}
    return doc


def _errors_mention(errs, *needles):
    return any(any(n in e for n in needles) for e in errs)


class CarriedAnalysisTest(unittest.TestCase):
    """Task 3: a carry is validated on current evidence and the prior's typed facts."""

    def test_carried_fixture_validates(self):
        self.assertEqual(m.validate(carried_doc()), [])

    def test_carry_needs_current_own_run_evidence(self):
        doc = carried_doc()
        doc['clusters'][0]['disposition']['analysis']['evidence'] = []
        errs = m.validate(doc)
        self.assertTrue(_errors_mention(errs, 'evidence', 'own_run_ids'), errs)

    def test_legacy_unknown_bar_cannot_establish_known_cause_carry(self):
        doc = carried_doc()
        doc['clusters'][0]['prior']['sources'][0]['bug_search']['candidates'][0]['bar_met'] = 'unknown'
        self.assertTrue(_errors_mention(m.validate(doc), 'bar_met', 'candidates'))
        doc['clusters'][0]['disposition']['analysis']['depth'] = 'deep-dive'
        doc['clusters'][0]['disposition']['analysis']['reverification']['outcome'] = 'reinvestigated'
        self.assertEqual(m.validate(doc), [])

    def test_report_to_auto_needs_current_support_for_the_new_member(self):
        doc = carried_doc()
        doc['policy']['write_mode'] = 'auto'
        c = doc['clusters'][0]
        c['members']['regression_ids'].append(49534)
        c['prior']['member_delta']['added'] = [49534]
        c['actions'][0].update(status='done', regression_ids=[49533, 49534])
        self.assertTrue(any('49534' in e for e in m.validate(doc)))

    def test_unchanged_high_is_never_carried(self):
        doc = carried_doc()
        c = doc['clusters'][0]
        c['blast_radius']['level'] = 'HIGH'
        c['prior']['sources'][0]['blast_radius']['level'] = 'HIGH'
        c['escalation']['required'] = True
        self.assertTrue(_errors_mention(m.validate(doc), 'HIGH'))
        c['disposition']['analysis']['depth'] = 'deep-dive'
        c['disposition']['analysis']['reverification']['outcome'] = 'reinvestigated'
        self.assertEqual(m.validate(doc), [])
        self.assertIs(c['escalation']['required'], True)

    def _ineligible_cases(self):
        def two_sources(c):
            c['prior']['relationship'] = 'merge'
            extra = copy.deepcopy(c['prior']['sources'][0])
            extra['cluster_id'] = 'c-other'
            extra['member_ids'] = [49540]
            extra['matched_member_ids'] = []
            c['prior']['sources'].append(extra)
            c['prior']['member_delta'] = {'added': [], 'removed': [49540]}
            c['disposition']['analysis']['reverification']['source_cluster_ids'] = [c['id'], 'c-other']

        def zero_overlap(c):
            s = c['prior']['sources'][0]
            s['member_ids'] = [49599]
            s['matched_member_ids'] = []
            c['prior']['member_delta'] = {'added': [49533], 'removed': [49599]}

        def unfinished_with_history(c):
            s = c['prior']['sources'][0]
            s['unfinished'] = True
            s['state'] = 'UNANALYSED'
            kept = copy.deepcopy(c['prior']['sources'][0])
            kept.update(history_only=True, unfinished=False, run_id='r-1', observed_at='2026-10-05T05:03:40Z',
                        state='KNOWN-CAUSE')
            c['prior']['sources'].append(kept)

        def no_timestamp(c):
            c['prior']['observed_at'] = None
            c['prior']['sources'][0]['observed_at'] = None

        def added_without_check(c):
            c['members']['regression_ids'] = [49533, 49534]
            c['members']['unlinked'] = [{'id': 49534, 'reason': 'not yet checked'}]
            c['prior']['member_delta']['added'] = [49534]

        def promoted(c):
            c['blast_radius']['level'] = 'ELEVATED'
            c['prior']['sources'][0]['blast_radius']['level'] = 'LOW'

        def wrong_basis(c):
            c['disposition']['analysis']['reverification']['basis']['run_id'] = 'r-not-the-source'

        def wrong_source_ref(c):
            c['disposition']['analysis']['reverification']['source_cluster_ids'] = ['c-elsewhere']

        def split_child(c):
            c['prior']['relationship'] = 'split'

        def overlap_only(c):
            c['prior']['relationship'] = 'overlap'

        def basis_missing(c):
            c['prior']['sources'][0]['analysis']['basis'] = None
            c['disposition']['analysis']['reverification']['basis'] = None

        def low_confidence(c):
            c['prior']['sources'][0]['analysis']['confidence'] = 'medium'

        def truncated(c):
            c['prior']['sources'][0]['analysis']['root_cause_truncated'] = True

        def incomplete_observation(c):
            c['prior']['observation_complete'] = False

        def missing_own_run(c):
            c['disposition']['analysis']['reverification']['own_run_ids'] = ['own-9']

        def changed_state(c):
            c['disposition']['state'] = 'CANDIDATE'

        def no_locators(c):
            c['disposition']['analysis']['reverification']['lookup_locators'] = []

        def checked_before_observation(c):
            c['disposition']['analysis']['reverification']['checked_at'] = '2026-10-12T00:00:00Z'

        def current_confidence_low(c):
            c['disposition']['analysis']['confidence'] = 'medium'

        return [('two_sources', two_sources, ('source', 'merge')), ('zero_overlap', zero_overlap, ('matched',)),
                ('unfinished_with_history', unfinished_with_history, ('unfinished',)),
                ('no_timestamp', no_timestamp, ('observed_at',)), ('added_without_check', added_without_check, ('49534', 'added')),
                ('promoted', promoted, ('level',)), ('wrong_basis', wrong_basis, ('basis',)),
                ('wrong_source_ref', wrong_source_ref, ('source_cluster_ids',)), ('split_child', split_child, ('relationship',)),
                ('overlap_only', overlap_only, ('relationship',)), ('basis_missing', basis_missing, ('basis',)),
                ('low_confidence', low_confidence, ('confidence',)), ('truncated', truncated, ('truncated',)),
                ('incomplete_observation', incomplete_observation, ('observation_complete',)),
                ('missing_own_run', missing_own_run, ('own_run_ids',)), ('changed_state', changed_state, ('state',)),
                ('no_locators', no_locators, ('lookup_locators',)),
                ('checked_before_observation', checked_before_observation, ('checked_at',)),
                ('current_confidence_low', current_confidence_low, ('confidence',))]

    def test_ineligible_carries_are_rejected_by_field(self):
        for name, mutate, needles in self._ineligible_cases():
            with self.subTest(case=name):
                doc = carried_doc()
                mutate(doc['clusters'][0])
                errs = m.validate(doc)
                self.assertTrue(errs, name)
                self.assertTrue(_errors_mention(errs, *needles), (name, errs))

    def test_fresh_analysis_still_validates_where_a_carry_would_not(self):
        for name, mutate, _ in self._ineligible_cases():
            if name in ('added_without_check', 'wrong_source_ref', 'missing_own_run', 'checked_before_observation',
                        'wrong_basis'):
                continue   # these break the record itself, not only carry eligibility
            with self.subTest(case=name):
                doc = carried_doc()
                mutate(doc['clusters'][0])
                an = doc['clusters'][0]['disposition']['analysis']
                an['depth'] = 'deep-dive'
                an['confidence'] = 'high'
                an['reverification']['outcome'] = 'reinvestigated'
                if name == 'basis_missing':
                    an['reverification']['basis'] = None
                errs = [e for e in m.validate(doc)]
                self.assertEqual(errs, [], (name, errs))

    def test_malformed_records_report_without_raising(self):
        for bad in ('x', [], {'outcome': 'carried'}, {'outcome': 7, 'own_run_ids': 'own-1', 'lookup_locators': None,
                                                       'source_cluster_ids': 'c', 'basis': [], 'checked_at': 5}):
            with self.subTest(bad=bad):
                doc = carried_doc()
                doc['clusters'][0]['disposition']['analysis']['reverification'] = bad
                errs = m.validate(doc)
                self.assertTrue(errs)
                self.assertTrue(_errors_mention(errs, 'reverification'), errs)
        doc = carried_doc()
        del doc['clusters'][0]['disposition']['analysis']['reverification']
        self.assertTrue(_errors_mention(m.validate(doc), 'reverification'))   # carried-forward needs the record
        doc = carried_doc()
        doc['clusters'][0]['disposition']['analysis']['depth'] = 'deep-dive'   # outcome carried needs the depth
        self.assertTrue(_errors_mention(m.validate(doc), 'carried-forward', 'outcome'))

    def test_added_member_requires_verification_after_net_shrink_and_demotion(self):
        doc = carried_doc()
        c = doc['clusters'][0]
        source = c['prior']['sources'][0]
        source['blast_radius']['level'] = 'ELEVATED'
        source['member_ids'] = [49533, 49535, 49536]
        source['matched_member_ids'] = [49533]
        c['blast_radius']['level'] = 'LOW'
        c['members']['regression_ids'] = [49533, 49534]
        c['members']['new_since_baseline'] = [49534]
        c['members']['unlinked'] = [{'id': 49534, 'reason': 'not proposed for a link in this fixture'}]
        c['shape'].update(regressions=2, growth_since_baseline=1)
        c['prior']['member_delta'] = {'added': [49534], 'removed': [49535, 49536]}
        analysis = c['disposition']['analysis']
        self.assertEqual(analysis['reverification']['own_run_ids'], ['own-1'])
        errs = m.validate(doc)
        self.assertTrue(_errors_mention(errs, '49534', 'added'), errs)
        added_evidence = copy.deepcopy(analysis['evidence'][0])
        added_evidence.update(prowjob_run_id='own-added', supports_regression_ids=[49534],
                              artifact='https://example.invalid/own-added/junit.xml')
        analysis['evidence'].append(added_evidence)
        analysis['reverification']['own_run_ids'].append('own-added')
        self.assertEqual(m.validate(doc), [])

    def test_watched_replacement_with_prior_needs_no_reverification(self):
        doc = carried_doc()
        c = doc['clusters'][0]
        s = c['prior']['sources'][0]
        s['member_ids'] = [51255, 51256]
        s['matched_member_ids'] = []
        c['members']['regression_ids'] = [51548]
        c['members']['new_since_baseline'] = [51548]
        c['members']['unlinked'] = []
        c['prior']['member_delta'] = {'added': [51548], 'removed': [51255, 51256]}
        c['shape'].update(regressions=1, days_open=1, growth_since_baseline=1)
        c['disposition'] = {'state': 'UNEXPLAINED',
                            'analysis': {'depth': 'none', 'confidence': 'low', 'owning_component': None,
                                         'triage_type': None, 'root_cause': None, 'evidence': [],
                                         'unverified_hypotheses': []},
                            'bug_search': {'candidates': [], 'newer_release_fix': None},
                            'proposed_action': {'type': 'none'}}
        c['actions'] = []
        doc['watch_list'] = [{'regression_id': 51548, 'view': '4.22-main', 'cluster_id': c['id'],
                              'reason': 'LOW & new (<7d)', 'revisit': 'next cycle'}]
        self.assertEqual(m.validate(doc), [])
        self.assertIsNotNone(c['prior'])
        self.assertEqual(c['actions'], [])

    def test_current_evidence_stays_within_current_members(self):
        doc = carried_doc()
        doc['clusters'][0]['disposition']['analysis']['evidence'][0]['supports_regression_ids'] = [49533, 49599]
        self.assertTrue(_errors_mention(m.validate(doc), '49599'))


class MultiGenerationTest(unittest.TestCase):
    """attach -> merge/finalize -> attach across runs (plan Task 3)."""
    EXTRA = {'watch_list': [], 'catch_all': {'jira': 'OCPQUAL-88', 'triage_id': 851, 'admitted': []},
             'backport_candidates': [], 'unanalysed': [], 'audit': {}}

    def finish(self, pp, dispositions, actions, run_id, unanalysed=()):
        merged = m.merge(pp, dispositions, actions)
        merged.update(copy.deepcopy(self.EXTRA))
        merged['unanalysed'] = list(unanalysed)
        return m.finalize(merged, jira_creations={'status': 'ok', 'count': 0, 'window': []},
                          sippy_diff={'status': 'match'}, permissions={'status': 'ok'},
                          mode_requested='report', mode_effective='report', decision=('auto', '', ''),
                          source_run={'job': 'j', 'run_id': run_id, 'url': 'u', 'started': 's'},
                          previous_run=None, existing_only=True)

    def prepass_doc(self, run_id, observed, baseline):
        doc = carried_doc()
        pp = {k: copy.deepcopy(doc[k]) for k in m.TOP_PREPASS}
        pp['source_run'] = {'run_id': run_id}
        pp['observation']['time'] = observed
        pp['clusters'] = [{k: v for k, v in doc['clusters'][0].items() if k not in m.CLUSTER_LLM and k != 'prior'}]
        pp['baseline_run'] = {'run_id': (baseline or {}).get('source_run', {}).get('run_id'), 'manifest_url': None,
                              'schema_version': '1.0' if baseline else None, 'compatible': bool(baseline) or None}
        prior.attach_priors(pp['clusters'], baseline)
        return pp

    def test_completed_carry_round_trip(self):
        doc = carried_doc()
        cid = doc['clusters'][0]['id']
        disp1 = {cid: dict(copy.deepcopy(doc['clusters'][0]['disposition']), escalation=doc['clusters'][0]['escalation'])}
        # R0 is the baseline carried_doc() was built from: rebuild it as a finalized manifest
        base = example()
        base['clusters'] = base['clusters'][:1]
        base['source_run']['run_id'] = 'r0'
        base['observation']['time'] = '2026-10-12T05:03:40Z'
        base['observation']['views'] = [{'view': '4.22-main', 'fetch': 'complete'}]
        bc = base['clusters'][0]
        bc['members']['regression_ids'] = [49533]
        bc['members']['unlinked'] = []
        bc['blast_radius']['level'] = 'LOW'
        bc['disposition']['analysis']['depth'] = 'deep-dive'
        bc['disposition']['analysis']['evidence'][0]['prowjob_run_id'] = 'own-0'
        bc['actions'][0]['status'] = 'skipped-report-mode'
        bc['escalation'] = {'required': False, 'reason': 'not required'}
        pp1 = self.prepass_doc('r1', '2026-10-13T05:03:40Z', base)
        snap = copy.deepcopy(pp1)
        final1 = self.finish(pp1, disp1, {cid: doc['clusters'][0]['actions']}, 'r1')
        self.assertEqual(pp1, snap)
        self.assertEqual(final1['clusters'][0]['prior'], pp1['clusters'][0]['prior'])
        self.assertEqual(m.validate(final1), [])
        pp2 = self.prepass_doc('r2', '2026-10-20T05:03:40Z', final1)
        c2 = pp2['clusters'][0]
        self.assertEqual(c2['prior']['run_id'], 'r1')
        self.assertEqual(c2['prior']['sources'][0]['analysis']['basis']['run_id'], 'r0')
        self.assertEqual([e['prowjob_run_id'] for e in c2['prior']['sources'][0]['analysis']['evidence_refs']], ['own-1'])
        self.assertEqual(c2['prior']['sources'][0]['analysis']['depth'], 'carried-forward')
        # R2 unreached: nothing replays
        final2 = self.finish(pp2, {cid: dict(_unanalysed_disposition(), escalation={'required': False, 'reason': 'n'})}, {},
                             'r2', unanalysed=[{'cluster_id': cid, 'reason': 'budget', 'blast_radius': 'LOW'}])
        self.assertEqual(final2['clusters'][0]['actions'], [])
        self.assertEqual(m.validate(final2), [])
        # a separate R2 carry continues the same basis
        carried2 = copy.deepcopy(doc['clusters'][0]['disposition'])
        carried2['analysis']['evidence'][0].update(prowjob_run_id='own-2')
        carried2['analysis']['reverification'].update(source_run_id='r1', own_run_ids=['own-2'],
                                                       checked_at='2026-10-20T06:10:00Z')
        final2b = self.finish(pp2, {cid: dict(carried2, escalation={'required': False, 'reason': 'n'})},
                              {cid: doc['clusters'][0]['actions']}, 'r2')
        self.assertEqual(m.validate(final2b), [])
        self.assertEqual(final2b['clusters'][0]['disposition']['analysis']['reverification']['basis']['run_id'], 'r0')

    def test_unreached_attempt_round_trip(self):
        doc = carried_doc()
        cid = doc['clusters'][0]['id']
        base = example()
        base['clusters'] = base['clusters'][:1]
        base['source_run']['run_id'] = 'r0'
        base['observation']['time'] = '2026-10-12T05:03:40Z'
        base['observation']['views'] = [{'view': '4.22-main', 'fetch': 'complete'}]
        bc = base['clusters'][0]
        bc['members']['regression_ids'] = [49533]
        bc['members']['unlinked'] = []
        bc['blast_radius']['level'] = 'LOW'
        bc['disposition']['analysis']['depth'] = 'deep-dive'
        bc['actions'][0]['status'] = 'skipped-report-mode'
        bc['escalation'] = {'required': False, 'reason': 'not required'}
        pp1 = self.prepass_doc('r1', '2026-10-13T05:03:40Z', base)
        pending_final1 = self.finish(pp1, {cid: dict(_unanalysed_disposition(), escalation={'required': False, 'reason': 'n'})},
                                     {}, 'r1', unanalysed=[{'cluster_id': cid, 'reason': 'budget', 'blast_radius': 'LOW'}])
        self.assertEqual(m.validate(pending_final1), [])
        pending_pp2 = self.prepass_doc('r2', '2026-10-20T05:03:40Z', pending_final1)
        pending_c2 = pending_pp2['clusters'][0]
        self.assertEqual([(s['run_id'], s['history_only']) for s in pending_c2['prior']['sources']],
                         [('r1', False), ('r0', True)])
        pending_final2 = self.finish(pending_pp2,
                                     {cid: dict(_unanalysed_disposition(), escalation={'required': False, 'reason': 'n'})},
                                     {}, 'r2', unanalysed=[{'cluster_id': cid, 'reason': 'budget', 'blast_radius': 'LOW'}])
        self.assertEqual(pending_final2['clusters'][0]['disposition']['analysis']['evidence'], [])
        self.assertEqual(pending_final2['clusters'][0]['actions'], [])
        self.assertEqual(m.validate(pending_final2), [])
        # marking R2 carried from the retained R0 snapshot must fail: the immediate source is unfinished
        carried = copy.deepcopy(doc['clusters'][0]['disposition'])
        carried['analysis']['reverification'].update(source_run_id='r1', checked_at='2026-10-20T06:10:00Z')
        bad = self.finish(pending_pp2, {cid: dict(carried, escalation={'required': False, 'reason': 'n'})},
                          {cid: doc['clusters'][0]['actions']}, 'r2')
        self.assertTrue(_errors_mention(m.validate(bad), 'unfinished', 'basis'))


class ExamplePriorTest(unittest.TestCase):
    def test_example_has_a_carried_low_cluster(self):
        ex = example()
        c = [c for c in ex['clusters'] if c['id'] == 'c-prior-example'][0]
        self.assertEqual(c['members']['regression_ids'], [90001])
        self.assertEqual((c['disposition']['state'], c['disposition']['analysis']['depth']), ('UNEXPLAINED', 'carried-forward'))
        self.assertEqual(c['actions'], [])
        self.assertEqual(c['disposition']['analysis']['reverification']['outcome'], 'carried')
        self.assertEqual(c['prior']['sources'][0]['analysis']['basis']['run_id'], '2105...')
        self.assertEqual(m.validate(ex), [])


if __name__ == '__main__':
    unittest.main()
