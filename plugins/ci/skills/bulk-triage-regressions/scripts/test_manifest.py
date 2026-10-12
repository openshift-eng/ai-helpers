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
        self.assertIn('audit.receipt', errs)
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


if __name__ == '__main__':
    unittest.main()
