#!/usr/bin/env python3
"""Tests for prior.py: flat prior memory projected from the previous weekly manifest."""
import copy
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import prior  # noqa: E402

OBS = '2026-10-12T12:00:00Z'
LOCATOR = 'https://example.invalid/own-0/junit.xml'   # synthetic fixture locator, never fetched
RESULT_URL = 'https://example.invalid/triages/17'


def current(cid, ids, supersedes=()):
    return {'id': cid,
            'lineage': {'first_seen_run': None, 'cycles_seen': None, 'supersedes': list(supersedes)},
            'fingerprint': {'release': '4.22', 'test_family': 'install should succeed', 'lane_family': 'lane',
                            'labels': []},
            'members': {'regression_ids': list(ids), 'new_since_baseline': None, 'views': ['4.22-main'],
                        'components': []},
            'shape': {'regressions': len(ids), 'distinct_jobs': 1, 'platforms': ['azure'], 'arches': ['amd64'],
                      'days_open': 3},
            'blast_radius': {'level': 'LOW', 'score': 0.1, 'reasons': ['1 regression']}}


def source(cid, ids, state='KNOWN-CAUSE', status='skipped-report-mode', depth='deep-dive', confidence='high',
           root='signature A', evidence=None, candidates=None, actions=None, unlinked=None):
    ids = list(ids)
    if evidence is None:
        evidence = [{'claim': 'assertion seen', 'artifact': LOCATOR, 'quote': 'exact line', 'prowjob_run_id': 'own-0',
                     'supports_regression_ids': ids}]
    if candidates is None:
        candidates = [{'key': 'OCPBUGS-1', 'bar_met': True, 'verdict': 'link', 'caveat': 'fix absent from 4.22'}]
    if actions is None:
        actions = [{'type': 'extend_triage', 'triage_id': 17, 'jira': 'OCPBUGS-1', 'regression_ids': ids,
                    'status': status, 'precheck': {'triage_reread': True, 'already_present': []},
                    'result_url': RESULT_URL if status == 'done' else None, 'error': None}]
    return {'id': cid,
            'lineage': {'first_seen_run': 'r0', 'cycles_seen': 1, 'supersedes': []},
            'fingerprint': {'release': '4.22', 'test_family': 'install should succeed', 'lane_family': 'lane',
                            'labels': []},
            'members': {'regression_ids': ids, 'new_since_baseline': ids, 'views': ['4.22-main'], 'components': [],
                        'unlinked': [] if unlinked is None else unlinked},
            'shape': {'regressions': len(ids), 'distinct_jobs': 1, 'platforms': ['gcp'], 'arches': ['amd64'],
                      'days_open': 2},
            'blast_radius': {'level': 'LOW', 'score': 0.2, 'reasons': ['1 regression']},
            'oracle': {'status': 'ok', 'runs_probed': 1, 'labels': {'own-0': ['L1']},
                       'label_bugs': {'L1': ['OCPBUGS-1']}, 'error': None},
            'disposition': {'state': state,
                            'analysis': {'depth': depth, 'confidence': confidence, 'owning_component': 'Node / Kubelet',
                                         'sippy_components': ['Node'], 'triage_type': 'test', 'root_cause': root,
                                         'evidence': evidence, 'unverified_hypotheses': ['not proven: timing']},
                            'bug_search': {'candidates': candidates, 'newer_release_fix': None},
                            'proposed_action': {'type': 'extend_triage', 'triage_id': 17, 'jira': 'OCPBUGS-1',
                                                'regression_ids': ids, 'description': 'd'}},
            'actions': actions,
            'escalation': {'required': False, 'reason': 'not required', 're_notify': False,
                           're_notify_reasons': [], 'veto_deadline': '2026-10-19T00:00:00Z'}}


def baseline(*sources, run_id='r0', observed=OBS, views=('4.22-main',), watch_list=(), unanalysed=(),
             write_mode='report'):
    return {'schema_version': '1.0', 'policy': {'name': 'post-ga', 'write_mode': write_mode},
            'source_run': {'run_id': run_id, 'url': 'https://prow.example.invalid/%s' % run_id},
            'observation': {'time': observed, 'views': [{'view': v, 'fetch': 'complete'} for v in views],
                            'symptom_probe': {'status': 'ok'}},
            'clusters': list(sources), 'watch_list': list(watch_list), 'unanalysed': list(unanalysed)}


def attach(clusters, base):
    prior.attach_priors(clusters, base)
    return clusters


class ProjectionTest(unittest.TestCase):
    def test_unchanged_projection(self):
        base = baseline(source('c-a', [1, 2]))
        before = copy.deepcopy(base)
        c = attach([current('c-a', [1, 2])], base)[0]
        self.assertEqual(c['prior']['relationship'], 'same-id')
        self.assertEqual(c['prior']['member_delta'], {'added': [], 'removed': []})
        self.assertEqual(c['prior']['run_id'], 'r0')
        self.assertEqual(c['prior']['observed_at'], OBS)
        self.assertEqual(c['prior']['source_url'], 'https://prow.example.invalid/r0')
        self.assertEqual(c['prior']['write_mode'], 'report')
        self.assertTrue(c['prior']['observation_complete'])
        s = c['prior']['sources'][0]
        self.assertEqual((s['run_id'], s['history_only'], s['unfinished']), ('r0', False, False))
        self.assertEqual(s['observed_at'], OBS)
        self.assertEqual((s['member_ids'], s['matched_member_ids']), ([1, 2], [1, 2]))
        self.assertEqual(s['state'], 'KNOWN-CAUSE')
        self.assertEqual(s['analysis']['basis'], {
            'run_id': 'r0', 'cluster_id': 'c-a', 'observed_at': OBS, 'depth': 'deep-dive'})
        self.assertEqual(s['analysis']['root_cause'], 'signature A')
        self.assertIs(s['analysis']['root_cause_truncated'], False)
        self.assertEqual(s['bug_search']['candidates'][0]['caveat'], 'fix absent from 4.22')
        self.assertIsNone(s['bug_search']['newer_release_fix'])
        self.assertEqual(s['analysis']['unverified_hypotheses'], ['not proven: timing'])
        self.assertEqual(s['analysis']['evidence_refs'],
                         [{'prowjob_run_id': 'own-0', 'supports_regression_ids': [1, 2], 'artifact': LOCATOR}])
        self.assertNotIn('quote', s['analysis']['evidence_refs'][0])
        self.assertNotIn('sippy_components', s['analysis'])
        self.assertEqual(s['oracle'], {'status': 'ok', 'runs_probed': 1, 'labels': {'own-0': ['L1']},
                                       'label_bugs': {'L1': ['OCPBUGS-1']}})
        self.assertEqual(s['escalation'], {'required': False, 'reason': 'not required', 're_notify': False,
                                           're_notify_reasons': []})
        self.assertEqual(s['proposed_action']['triage_id'], 17)
        self.assertEqual(s['unlinked'], [])
        self.assertEqual(s['watch_list'], [])
        self.assertEqual(s['unanalysed'], [])
        self.assertEqual(s['shape']['platforms'], ['gcp'])
        self.assertEqual(base, before)
        self.assertNotIn('actions', c)
        self.assertNotIn('disposition', c)

    def test_growth_and_shrink(self):
        grown = attach([current('c-a', [1, 2, 3])], baseline(source('c-a', [1, 2])))[0]
        self.assertEqual(grown['prior']['member_delta'], {'added': [3], 'removed': []})
        shrunk = attach([current('c-a', [1])], baseline(source('c-a', [1, 2])))[0]
        self.assertEqual(shrunk['prior']['member_delta'], {'added': [], 'removed': [2]})
        self.assertEqual(shrunk['prior']['sources'][0]['matched_member_ids'], [1])

    def test_single_supersedes(self):
        c = attach([current('c-new', [1, 2], supersedes=['c-old'])], baseline(source('c-old', [1, 2])))[0]
        self.assertEqual(c['prior']['relationship'], 'supersedes')
        self.assertEqual(c['prior']['sources'][0]['cluster_id'], 'c-old')

    def test_split_includes_minority(self):
        base = baseline(source('c-old', [1, 2, 3, 4, 5, 6]))
        children = attach([current('c-big', [1, 2, 3, 4], supersedes=['c-old']), current('c-small', [5, 6])], base)
        self.assertEqual([x['prior']['relationship'] for x in children], ['split', 'split'])
        self.assertEqual(children[1]['prior']['sources'][0]['matched_member_ids'], [5, 6])
        self.assertEqual(children[1]['prior']['sources'][0]['member_ids'], [1, 2, 3, 4, 5, 6])
        self.assertEqual(children[1]['lineage']['supersedes'], [])
        self.assertEqual(children[1]['prior']['member_delta']['removed'], [1, 2, 3, 4])
        self.assertEqual(children[0]['prior']['member_delta'], {'added': [], 'removed': [5, 6]})

    def test_replacement_beside_a_real_successor_is_not_a_split(self):
        base = baseline(source('c-a', [1]))
        replacement, successor = attach([current('c-a', [2]), current('c-b', [1], supersedes=['c-a'])], base)
        self.assertEqual(replacement['prior']['relationship'], 'same-id')
        self.assertEqual(replacement['prior']['sources'][0]['matched_member_ids'], [])
        self.assertEqual(successor['prior']['relationship'], 'supersedes')
        self.assertEqual(successor['prior']['sources'][0]['matched_member_ids'], [1])

    def test_malformed_lineage_and_members_do_not_crash(self):
        base = baseline(source('c-a', [1]))
        for sup in (5, 'c-a', {'c-a': 1}, None):
            with self.subTest(supersedes=sup):
                c = current('c-a', [1])
                c['lineage']['supersedes'] = sup
                self.assertEqual(attach([c], base)[0]['prior']['relationship'], 'same-id')
        c = current('c-a', [1])
        c['lineage'] = 'none'
        self.assertEqual(attach([c], base)[0]['prior']['relationship'], 'same-id')

    def test_merge_keeps_all_sources(self):
        base = baseline(source('c-a', [1, 2]), source('c-b', [3, 4]))
        c = attach([current('c-a', [1, 2, 3])], base)[0]
        self.assertEqual(c['prior']['relationship'], 'merge')
        self.assertEqual([s['cluster_id'] for s in c['prior']['sources']], ['c-a', 'c-b'])
        self.assertEqual(c['prior']['member_delta'], {'added': [], 'removed': [4]})
        reordered = baseline(source('c-b', [3, 4]), source('c-a', [1, 2]))
        other = attach([current('c-a', [1, 2, 3])], reordered)[0]
        self.assertEqual(c['prior'], other['prior'])

    def test_merge_of_split_and_overlap_below_half(self):
        base = baseline(source('c-old', [1, 2, 3, 4, 5, 6]), source('c-x', [7]))
        # one child takes a minority of c-old plus all of c-x: two immediate sources -> merge, every source kept
        c = attach([current('c-m', [5, 6, 7], supersedes=['c-x'])], base)[0]
        self.assertEqual(c['prior']['relationship'], 'merge')
        self.assertEqual([s['cluster_id'] for s in c['prior']['sources']], ['c-old', 'c-x'])
        # a lone minority overlap with no id or supersedes continuity is context only
        o = attach([current('c-o', [6, 9])], baseline(source('c-old', [1, 2, 3, 4, 5, 6])))[0]
        self.assertEqual(o['prior']['relationship'], 'overlap')
        self.assertEqual(o['prior']['member_delta'], {'added': [9], 'removed': [1, 2, 3, 4, 5]})

    def test_replacement_population(self):
        c = attach([current('c-b17bd7', [51548])], baseline(source('c-b17bd7', [51255, 51256])))[0]
        self.assertEqual(c['prior']['relationship'], 'same-id')
        self.assertEqual(c['prior']['sources'][0]['matched_member_ids'], [])
        self.assertEqual(c['prior']['member_delta'], {'added': [51548], 'removed': [51255, 51256]})

    def test_no_memory(self):
        for base in (None, baseline(source('c-a', [1]), run_id='r0') | {'schema_version': '0.9'},
                     baseline(source('c-a', [1])) | {'policy': {'name': 'pre-ga'}},
                     baseline(source('c-z', [9]))):
            with self.subTest(base=base and (base.get('schema_version'), base['policy'], len(base['clusters']))):
                c = attach([current('c-a', [1])], base)[0]
                self.assertIn('prior', c)
                self.assertIsNone(c['prior'])

    def test_unanalysed_and_watch_are_history(self):
        src = source('c-a', [1], state='UNANALYSED', depth='none', confidence='low', evidence=[])
        base = baseline(src, watch_list=[{'regression_id': 1, 'view': '4.22-main', 'cluster_id': 'c-a',
                                          'reason': 'LOW & new (<7d)'}],
                        unanalysed=[{'cluster_id': 'c-a', 'reason': 'budget', 'blast_radius': 'LOW'}])
        s = attach([current('c-a', [1])], base)[0]['prior']['sources'][0]
        self.assertEqual(s['state'], 'UNANALYSED')
        self.assertIs(s['unfinished'], True)
        self.assertIsNone(s['analysis']['basis'])
        self.assertEqual(s['analysis']['evidence_refs'], [])
        self.assertEqual(s['watch_list'], base['watch_list'])
        self.assertEqual(s['unanalysed'], base['unanalysed'])

    def test_unanalysed_entries_match_by_cluster_id_only(self):
        base = baseline(source('c-a', [1]),
                        unanalysed=[{'cluster_id': 'c-other', 'regression_id': 1, 'reason': 'budget', 'blast_radius': 'LOW'}])
        s = attach([current('c-a', [1])], base)[0]['prior']['sources'][0]
        self.assertEqual(s['unanalysed'], [])
        self.assertIs(s['unfinished'], False)
        base = baseline(source('c-a', [1]), watch_list=[{'regression_id': 1, 'view': '4.22-main', 'reason': 'LOW & new (<7d)'}])
        self.assertEqual(len(attach([current('c-a', [1])], base)[0]['prior']['sources'][0]['watch_list']), 1)

    def test_action_status_is_not_promoted(self):
        base = baseline(source('c-a', [1], status='done'), source('c-b', [2]))
        c = attach([current('c-a', [1, 2])], base)[0]
        self.assertEqual([s['actions'][0]['status'] for s in c['prior']['sources']], ['done', 'skipped-report-mode'])
        self.assertEqual(c['prior']['sources'][0]['actions'][0]['result_url'], RESULT_URL)
        self.assertIsNone(c['prior']['sources'][1]['actions'][0]['result_url'])
        self.assertEqual(c['prior']['sources'][0]['actions'][0]['triage_id'], 17)
        self.assertEqual(c['prior']['sources'][0]['actions'][0]['jira'], 'OCPBUGS-1')
        self.assertNotIn('actions', c)

    def test_bounded_nonrecursive_history(self):
        src = source('c-a', [1], root='x' * 2001)
        src['prior'] = {'sentinel': True}
        s = attach([current('c-a', [1])], baseline(src))[0]['prior']['sources'][0]
        self.assertEqual(s['analysis']['root_cause'], 'x' * 2000)
        self.assertIs(s['analysis']['root_cause_truncated'], True)
        self.assertNotIn('prior', s)
        self.assertNotIn('precheck', s['actions'][0])
        self.assertNotIn('veto_deadline', s['escalation'])

    def test_partial_and_legacy(self):
        src = source('c-a', [1])
        del src['disposition']['analysis']
        del src['disposition']['bug_search']['candidates']
        base = baseline(src, views=())
        base['observation']['views'] = [{'view': '4.22-main', 'fetch': 'partial', 'error': 'HTTP 429'}]
        c = attach([current('c-a', [1])], base)[0]
        self.assertFalse(c['prior']['observation_complete'])
        s = c['prior']['sources'][0]
        self.assertIsNone(s['analysis'])
        self.assertIs(s['unfinished'], True)
        self.assertIsNone(s['bug_search']['candidates'])

    def test_observation_complete_is_judged_per_source_view(self):
        other = source('c-b', [2])
        other['members']['views'] = ['4.20-main']
        base = baseline(source('c-a', [1]), other, views=('4.22-main',))
        base['observation']['views'].append({'view': '4.20-main', 'fetch': 'partial', 'error': 'HTTP 429'})
        a, b = attach([current('c-a', [1]), current('c-b', [2])], base)
        self.assertIs(a['prior']['observation_complete'], True)
        self.assertIs(b['prior']['observation_complete'], False)
        merged = attach([current('c-a', [1, 2])], base)[0]
        self.assertIs(merged['prior']['observation_complete'], False)
        base['observation']['views'] = []
        self.assertIs(attach([current('c-a', [1])], base)[0]['prior']['observation_complete'], False)
        # unknown source scope is never complete, even when every observed view is complete (review I3)
        for views in (None, [], 'n/a', [3], [None]):
            with self.subTest(source_views=views):
                src = source('c-a', [1])
                if views is None:
                    del src['members']['views']
                else:
                    src['members']['views'] = views
                self.assertIs(attach([current('c-a', [1])], baseline(src))[0]['prior']['observation_complete'], False)
        src = source('c-a', [1])
        del src['members']['views']
        partial = baseline(src, views=())
        partial['observation']['views'] = [{'view': '4.22-main', 'fetch': 'partial'}]
        self.assertIs(attach([current('c-a', [1])], partial)[0]['prior']['observation_complete'], False)
        # a malformed view name in the observation list is skipped, not a crash (review C2)
        base = baseline(source('c-a', [1]))
        base['observation']['views'].append({'view': [], 'fetch': 'complete'})
        self.assertIs(attach([current('c-a', [1])], base)[0]['prior']['observation_complete'], True)

    def test_triage_only_low_has_no_basis_and_legacy_values_are_opaque(self):
        src = source('c-a', [1], state='UNEXPLAINED', depth='triage-only', confidence='low',
                     candidates=[{'key': 'OCPBUGS-9', 'bar_met': 'unknown', 'verdict': 'reject', 'note': 'title only'}],
                     unlinked=[{'id': 2, 'reason': 'different assertion'}])
        s = attach([current('c-a', [1])], baseline(src))[0]['prior']['sources'][0]
        self.assertEqual((s['analysis']['depth'], s['analysis']['confidence']), ('triage-only', 'low'))
        self.assertIsNone(s['analysis']['basis'])
        self.assertIs(s['unfinished'], False)
        self.assertEqual(s['bug_search']['candidates'][0]['bar_met'], 'unknown')
        self.assertEqual(s['unlinked'], [{'id': 2, 'reason': 'different assertion'}])

    def test_malformed_optional_containers_project_to_null(self):
        src = source('c-a', [1])
        src['oracle'] = 'broken'
        src['escalation'] = []
        src['actions'] = 'none'
        src['members']['unlinked'] = 'n/a'
        base = baseline(src)
        base['watch_list'] = 'later'
        del base['unanalysed']
        s = attach([current('c-a', [1])], base)[0]['prior']['sources'][0]
        self.assertIsNone(s['oracle'])
        self.assertIsNone(s['escalation'])
        self.assertIsNone(s['actions'])
        self.assertIsNone(s['unlinked'])
        self.assertIsNone(s['watch_list'])
        self.assertIsNone(s['unanalysed'])

    def test_unknown_identity_and_time_are_null(self):
        base = baseline(source('c-a', [1]))
        base['source_run'] = ['unavailable']
        base['observation']['time'] = 'yesterday'
        c = attach([current('c-a', [1])], base)[0]
        self.assertIsNone(c['prior']['run_id'])
        self.assertIsNone(c['prior']['observed_at'])
        self.assertIsNone(c['prior']['sources'][0]['run_id'])
        self.assertIsNone(c['prior']['sources'][0]['analysis']['basis'])   # no valid identity/time -> no basis

    def test_carried_forward_source_keeps_its_recorded_basis(self):
        src = source('c-a', [1], depth='carried-forward')
        src['disposition']['analysis']['reverification'] = {
            'source_run_id': 'r-1', 'source_cluster_ids': ['c-a'], 'outcome': 'carried', 'reason': 'same signature',
            'checked_at': OBS, 'own_run_ids': ['own-0'], 'lookup_locators': ['https://example.invalid/bug/1'],
            'basis': {'run_id': 'r-2', 'cluster_id': 'c-a', 'observed_at': '2026-09-28T12:00:00Z', 'depth': 'deep-dive'}}
        s = attach([current('c-a', [1])], baseline(src))[0]['prior']['sources'][0]
        self.assertEqual(s['analysis']['basis'],
                         {'run_id': 'r-2', 'cluster_id': 'c-a', 'observed_at': '2026-09-28T12:00:00Z', 'depth': 'deep-dive'})
        src['disposition']['analysis']['reverification']['outcome'] = 'incomplete'
        s = attach([current('c-a', [1])], baseline(src))[0]['prior']['sources'][0]
        self.assertIsNone(s['analysis']['basis'])
        self.assertIs(s['unfinished'], True)


class RetentionTest(unittest.TestCase):
    """R0 useful finding -> R1 unreached -> R2 keeps R0 as flat history-only context (plan Decision 7)."""

    UNANALYSED = {'state': 'UNANALYSED',
                  'analysis': {'depth': 'none', 'confidence': 'low', 'owning_component': None, 'triage_type': None,
                               'root_cause': None, 'evidence': [], 'unverified_hypotheses': []},
                  'bug_search': {'candidates': [], 'newer_release_fix': None},
                  'proposed_action': {'type': 'none'}}

    def r0_source(self):
        return source('c-a', [1], state='CANDIDATE', actions=[],
                      candidates=[{'key': 'OCPBUGS-1', 'bar_met': False, 'verdict': 'candidate',
                                   'caveat': 'fix absent from 4.22'}])

    def unreached(self, base_prev, run_id, observed):
        """A manifest of `run_id` whose only cluster was unreached: prior attached from base_prev, UNANALYSED."""
        c = current('c-a', [1])
        prior.attach_priors([c], base_prev)
        c['disposition'] = copy.deepcopy(self.UNANALYSED)
        c['actions'] = []
        c['escalation'] = {'required': False, 'reason': 'not required'}
        return baseline(c, run_id=run_id, observed=observed,
                        unanalysed=[{'cluster_id': 'c-a', 'reason': 'budget', 'blast_radius': 'LOW'}])

    def test_three_attempts_keep_the_last_useful_analysis(self):
        r0 = baseline(self.r0_source(), run_id='r0', observed='2026-10-12T12:00:00Z')
        r1 = self.unreached(r0, 'r1', '2026-10-13T12:00:00Z')
        c2 = attach([current('c-a', [1])], r1)[0]
        self.assertEqual(c2['prior']['run_id'], 'r1')
        latest, retained = c2['prior']['sources']
        self.assertEqual((latest['run_id'], latest['state'], latest['history_only'], latest['unfinished']),
                         ('r1', 'UNANALYSED', False, True))
        self.assertEqual((retained['run_id'], retained['observed_at'], retained['state'], retained['history_only']),
                         ('r0', '2026-10-12T12:00:00Z', 'CANDIDATE', True))
        self.assertEqual(retained['matched_member_ids'], [1])
        self.assertEqual(retained['bug_search']['candidates'][0]['key'], 'OCPBUGS-1')
        self.assertEqual(retained['bug_search']['candidates'][0]['caveat'], 'fix absent from 4.22')
        self.assertEqual(retained['analysis']['evidence_refs'][0]['prowjob_run_id'], 'own-0')
        self.assertEqual(retained['analysis']['basis']['run_id'], 'r0')
        self.assertEqual(c2['prior']['relationship'], 'same-id')
        self.assertEqual(c2['prior']['member_delta'], {'added': [], 'removed': []})
        self.assertTrue(all('prior' not in s for s in c2['prior']['sources']))
        # another unreached attempt: the chain does not grow with intermediate unfinished snapshots
        r2 = self.unreached(r1, 'r2', '2026-10-14T12:00:00Z')
        c3 = attach([current('c-a', [1])], r2)[0]
        self.assertEqual([(s['run_id'], s['history_only']) for s in c3['prior']['sources']],
                         [('r2', False), ('r0', True)])

    def test_incomplete_reverification_is_unfinished_and_retains_context(self):
        r0 = baseline(self.r0_source(), run_id='r0')
        c = current('c-a', [1])
        prior.attach_priors([c], r0)
        c['disposition'] = copy.deepcopy(self.UNANALYSED)
        c['disposition']['analysis']['reverification'] = {'outcome': 'incomplete', 'reason': 'artifact 404'}
        c['actions'] = []
        c['escalation'] = {'required': False, 'reason': 'not required'}
        r1 = baseline(c, run_id='r1', observed='2026-10-13T12:00:00Z')
        c2 = attach([current('c-a', [1])], r1)[0]
        self.assertIs(c2['prior']['sources'][0]['unfinished'], True)
        self.assertEqual([(s['run_id'], s['history_only']) for s in c2['prior']['sources']],
                         [('r1', False), ('r0', True)])

    def test_unfinished_merge_keeps_both_old_snapshots(self):
        r0 = baseline(source('c-a', [1], state='CANDIDATE', actions=[]), source('c-b', [2], actions=[]), run_id='r0')
        c = current('c-a', [1, 2])
        prior.attach_priors([c], r0)
        self.assertEqual(c['prior']['relationship'], 'merge')
        c['disposition'] = copy.deepcopy(self.UNANALYSED)
        c['actions'] = []
        c['escalation'] = {'required': False, 'reason': 'not required'}
        r1 = baseline(c, run_id='r1', observed='2026-10-13T12:00:00Z')
        c2 = attach([current('c-a', [1, 2])], r1)[0]
        self.assertEqual([(s['run_id'], s['cluster_id'], s['history_only']) for s in c2['prior']['sources']],
                         [('r1', 'c-a', False), ('r0', 'c-a', True), ('r0', 'c-b', True)])
        self.assertEqual([s['state'] for s in c2['prior']['sources'][1:]], ['CANDIDATE', 'KNOWN-CAUSE'])

    def test_completed_latest_analysis_supersedes_retained_context(self):
        r0 = baseline(self.r0_source(), run_id='r0')
        c = current('c-a', [1])
        prior.attach_priors([c], r0)
        finished = source('c-a', [1])
        finished['prior'] = c['prior']
        r1 = baseline(finished, run_id='r1', observed='2026-10-13T12:00:00Z')
        c2 = attach([current('c-a', [1])], r1)[0]
        self.assertEqual([(s['run_id'], s['history_only']) for s in c2['prior']['sources']], [('r1', False)])

    def test_malformed_embedded_prior_yields_no_retained_snapshots(self):
        finished = {'run_id': 'r0', 'observed_at': OBS, 'cluster_id': 'c-a', 'history_only': False, 'unfinished': False,
                    'member_ids': [1], 'analysis': {'depth': 'deep-dive', 'confidence': 'high', 'root_cause': 'ok',
                                                    'root_cause_truncated': False, 'evidence_refs': [], 'basis': None}}
        for bad in ('x', {'sources': 'none'}, {'sources': [None, 3, {'history_only': 'yes'}]},
                    {'sources': [dict(finished, run_id=[]), dict(finished, observed_at={'t': 1}), dict(finished, cluster_id=7),
                                 dict(finished, analysis='prose'), dict(finished, analysis={'root_cause': 5}),
                                 dict(finished, member_ids='1', analysis={'depth': 'none'})]}):
            with self.subTest(bad=str(bad)[:60]):
                c = current('c-a', [1])
                c['disposition'] = copy.deepcopy(self.UNANALYSED)
                c['actions'] = []
                c['escalation'] = {'required': False, 'reason': 'not required'}
                c['prior'] = bad
                r1 = baseline(c, run_id='r1')
                c2 = attach([current('c-a', [1])], r1)[0]
                self.assertEqual([s['history_only'] for s in c2['prior']['sources']], [False])

    def test_retained_snapshot_is_renormalised_to_the_projection_contract(self):
        r0 = baseline(self.r0_source(), run_id='r0')
        c = current('c-a', [1])
        prior.attach_priors([c], r0)
        snap = c['prior']['sources'][0]
        snap['analysis']['root_cause'] = 'y' * 2001          # oversize prose smuggled into history
        snap['analysis']['extra'] = 'not part of the contract'
        snap['analysis']['evidence_refs'].append({'prowjob_run_id': '', 'supports_regression_ids': []})
        snap['analysis']['basis'] = {'run_id': 'r0', 'depth': 'guess'}
        snap['oracle'] = 'broken'
        snap['actions'] = 'none'
        snap['state'] = 7
        snap['stray'] = True
        c['disposition'] = copy.deepcopy(self.UNANALYSED)
        c['actions'] = []
        c['escalation'] = {'required': False, 'reason': 'not required'}
        r1 = baseline(c, run_id='r1', observed='2026-10-13T12:00:00Z')
        kept = attach([current('c-a', [1])], r1)[0]['prior']['sources'][1]
        self.assertIs(kept['history_only'], True)
        self.assertEqual(kept['analysis']['root_cause'], 'y' * 2000)
        self.assertIs(kept['analysis']['root_cause_truncated'], True)
        self.assertNotIn('extra', kept['analysis'])
        self.assertEqual(len(kept['analysis']['evidence_refs']), 1)
        self.assertIsNone(kept['analysis']['basis'])
        self.assertIsNone(kept['oracle'])
        self.assertIsNone(kept['actions'])
        self.assertIsNone(kept['state'])
        self.assertNotIn('stray', kept)
        self.assertEqual(sorted(kept), sorted(prior.SOURCE_KEYS))


class GraphInternalsTest(unittest.TestCase):
    def test_project_source_and_retained_sources_are_the_module_boundary(self):
        base = baseline(source('c-a', [1, 2]))
        projected = prior._project_source(base['clusters'][0], base, [1])
        self.assertEqual((projected['cluster_id'], projected['matched_member_ids'], projected['history_only']),
                         ('c-a', [1], False))
        self.assertEqual(prior._retained_sources(projected, [1, 2]), [])

    def test_ids_sort_integers_before_strings(self):
        base = baseline(source('c-a', [3, 'b', 1, 'a']))
        c = attach([current('c-a', [1, 'a', 'c', 2])], base)[0]
        self.assertEqual(c['prior']['sources'][0]['member_ids'], [1, 3, 'a', 'b'])
        self.assertEqual(c['prior']['member_delta'], {'added': [2, 'c'], 'removed': [3, 'b']})


if __name__ == '__main__':
    unittest.main()
