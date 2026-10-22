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
    base['source_run']['run_id'] = base_run
    base['observation']['time'] = '2026-10-06T05:03:40Z'
    base['observation']['views'] = [{'view': '4.22-main', 'fetch': 'complete'}]
    cur = example()
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


if __name__ == '__main__':
    unittest.main()
