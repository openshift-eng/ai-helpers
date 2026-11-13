#!/usr/bin/env python3
"""Exercise the actual frozen-prior evaluation judges without a model session."""
import copy
import json
from pathlib import Path
import textwrap
import unittest

import yaml

EVALS = Path(__file__).resolve().parents[1]


class InvestigationOrderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = yaml.safe_load((EVALS / 'eval-bulk-triage-prior.yaml').read_text())
        cls.checks = {}
        for item in config['judges']:
            namespace = {}
            exec('def judge(outputs):\n' + textwrap.indent(item['check'], '    '), namespace)
            cls.checks[item['name']] = namespace['judge']

    def verdict(self, case):
        annotations = yaml.safe_load((EVALS / 'cases/bulk-triage-prior' / case / 'annotations.yaml').read_text())
        decisions = []
        for cid, expected in annotations['expected']['decisions'].items():
            decisions.append({'cluster_id': cid, 'next_step': expected['next_step'],
                'depth': expected['allowed_depths'][0], 'state': expected['allowed_states'][0],
                'target': expected.get('target', expected.get('allowed_targets', [None])[0]),
                'supported_member_ids': expected['supported_member_ids'], 'would_write': expected['would_write'],
                'escalation_required': expected['escalation_required'], 'check_locators': expected['required_locators']})
        return annotations, {'decisions': decisions, 'investigation_order': []}

    def judge(self, annotations, verdict, name='choices_and_priority'):
        return self.checks[name]({'annotations': annotations, 'files': {'prior-verdict.json': json.dumps(verdict)}})

    def test_case002_prefix_alone_does_not_omit_required_investigation(self):
        ann, verdict = self.verdict('case-002')
        verdict['investigation_order'] = ['c-high']
        self.assertFalse(self.judge(ann, verdict)[0])

    def test_case002_all_required_work_and_flexible_suffix_pass_all_judges(self):
        ann, verdict = self.verdict('case-002')
        for order in (['c-high', 'c-new-bug'], ['c-high', 'c-b17bd7', 'c-new-bug'],
                      ['c-high', 'c-new-bug', 'c-b17bd7']):
            verdict['investigation_order'] = order
            for name in self.checks:
                with self.subTest(order=order, judge=name):
                    self.assertTrue(self.judge(ann, verdict, name)[0], self.judge(ann, verdict, name))

    def test_analyse_first_is_required_after_prefix_too(self):
        ann, verdict = self.verdict('case-002')
        ann['expected']['decisions']['c-b17bd7']['next_step'] = 'analyse-first'
        next(d for d in verdict['decisions'] if d['cluster_id'] == 'c-b17bd7')['next_step'] = 'analyse-first'
        verdict['investigation_order'] = ['c-high', 'c-new-bug']
        self.assertFalse(self.judge(ann, verdict)[0])
        verdict['investigation_order'].append('c-b17bd7')
        self.assertTrue(self.judge(ann, verdict)[0])

    def test_priority_and_exact_order_are_preserved(self):
        ann, verdict = self.verdict('case-002')
        verdict['investigation_order'] = ['c-new-bug', 'c-high']
        self.assertFalse(self.judge(ann, verdict)[0])
        ann, verdict = self.verdict('case-001')
        verdict['investigation_order'] = copy.deepcopy(ann['expected']['investigation_order_prefix'])
        self.assertTrue(self.judge(ann, verdict)[0])
        verdict['investigation_order'].append('c-known')
        self.assertFalse(self.judge(ann, verdict)[0])

    def test_bad_order_shapes_fail_without_raising(self):
        ann, verdict = self.verdict('case-002')
        for order in (None, 'c-high', [{}], ['c-high', {}]):
            verdict['investigation_order'] = order
            self.assertFalse(self.judge(ann, verdict)[0])


if __name__ == '__main__':
    unittest.main()
