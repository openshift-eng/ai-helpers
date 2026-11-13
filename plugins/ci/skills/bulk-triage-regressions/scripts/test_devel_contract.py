#!/usr/bin/env python3
"""Contract tests for development triage memory: pair-scoped ancestry (prior.py) and the devel manifest rules
(manifest.py). Synthetic fixtures only; nothing is fetched."""
import copy
import hashlib
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import coverage  # noqa: E402
import manifest as m  # noqa: E402
import prior  # noqa: E402

T0 = '2026-11-12T07:00:00Z'
T1 = '2026-11-13T07:00:00Z'
CHECKED = '2026-11-13T07:30:00Z'
SCOPE = {'views': ['5.1-main'], 'components': ['*']}
SIG = {'stage': 'bootstrap', 'discriminator': 'etcdserver: request timed out'}
DRAFT = 'Full bug draft.\n' * 800     # deliberately far beyond the root-cause bound


def cov(**by):
    """cov(r1=['a', 'b']) -> coverage for regression 1."""
    return [{'regression_id': int(k[1:]), 'run_ids': list(v)} for k, v in sorted(by.items())]


def inv(rid, runs, required=True):
    return {'id': rid, 'required': required, 'triages': [],
            'job_runs': [{'prowjob_run_id': r, 'prowjob_name': 'job', 'start_time': T0} for r in runs]}


def cluster(cid, coverage_, state='UNEXPLAINED', signature=SIG, candidates=None, level='LOW', confidence='high',
            depth='deep-dive', proposal=None):
    ids = [e['regression_id'] for e in coverage_]
    evidence = [{'claim': 'assertion seen', 'artifact': 'https://example.invalid/%s' % e['run_ids'][0],
                 'quote': 'exact line', 'prowjob_run_id': e['run_ids'][0], 'supports_regression_ids': [e['regression_id']]}
                for e in coverage_ if e['run_ids']]
    if candidates is None:
        candidates = ([{'key': 'OCPBUGS-1', 'bar_met': True, 'verdict': 'link'}] if state == 'KNOWN-CAUSE' else [])
    disp = {'state': state,
            'analysis': {'depth': depth, 'confidence': confidence, 'owning_component': 'Etcd',
                         'triage_type': 'product', 'root_cause': 'mechanism', 'evidence': evidence,
                         'unverified_hypotheses': []},
            'bug_search': {'candidates': candidates, 'newer_release_fix': None},
            'proposed_action': {'type': 'none'}}
    if proposal is not None:
        disp['new_bug_proposal'] = proposal
    return {'id': cid, 'lineage': {'first_seen_run': 'r0', 'cycles_seen': 1, 'supersedes': []},
            'fingerprint': {'release': '5.1', 'test_family': 'install', 'lane_family': 'lane'},
            'members': {'regression_ids': ids, 'new_since_baseline': None, 'views': ['5.1-main'], 'components': [],
                        'coverage': copy.deepcopy(coverage_), 'unlinked': []},
            'signature': copy.deepcopy(signature),
            'shape': {'regressions': len(ids)}, 'blast_radius': {'level': level, 'score': 0.1, 'reasons': []},
            'disposition': disp, 'actions': [], 'escalation': {'required': level == 'HIGH', 'reason': 'n/a'}}


def unanalysed(cid, coverage_):
    c = cluster(cid, coverage_, state='UNANALYSED', signature={'stage': '', 'discriminator': ''}, confidence='low',
                depth='none')
    c['disposition']['analysis']['evidence'] = []
    return c


def proposal(draft=DRAFT):
    return {'status': 'not-filed', 'summary': 'etcd times out on bootstrap', 'component': 'Etcd',
            'triage_type': 'product', 'release_blocker': False, 'regression_ids': [1], 'draft': draft}


def doc(clusters, inventory, run_id='r0', time=T0, mode='reuse', baseline_run=None):
    return {'schema_version': '1.0',
            'policy': {'name': 'devel', 'memory_version': 1, 'memory_mode': mode, 'scope': copy.deepcopy(SCOPE)},
            'source_run': {'run_id': run_id, 'url': 'https://example.invalid/run/%s' % run_id},
            'observation': {'time': time, 'views': [{'view': '5.1-main', 'fetch': 'complete'}],
                            'symptom_probe': {'status': 'skipped', 'runs_probed': 0}},
            'baseline_run': baseline_run or {'run_id': None, 'manifest_url': None, 'schema_version': None,
                                             'compatible': None},
            'inventory': inventory, 'clusters': clusters, 'unanalysed': []}


def today(clusters, inventory, baseline, mode='reuse'):
    """A day-two document: priors attached from `baseline`."""
    d = doc(clusters, inventory, run_id='r1', time=T1, mode=mode,
            baseline_run={'run_id': 'r0', 'manifest_url': None, 'schema_version': '1.0', 'compatible': True})
    prior.attach_priors(d['clusters'], baseline, 'devel')
    return d


def carry(c, own):
    """Turn a current cluster with an attached prior into a carried-forward analysis checked on `own` runs."""
    src = c['prior']['sources'][0]
    an = c['disposition']['analysis']
    an['depth'] = 'carried-forward'
    an['reverification'] = {'source_run_id': 'r0', 'source_cluster_ids': [src['cluster_id']],
                            'basis': copy.deepcopy(src['analysis']['basis']), 'outcome': 'carried',
                            'reason': 'same signature', 'checked_at': CHECKED, 'own_run_ids': list(own),
                            'lookup_locators': ['https://example.invalid/search']}
    return c


def mentions(errs, *needles):
    return any(all(n in e for n in needles) for e in errs)


def baseline_one():
    return doc([cluster('g-a', cov(r1=['a1', 'a2']))], [inv(1, ['a1', 'a2'])])


class CoverageHelpersTest(unittest.TestCase):
    def test_pairs_zero_and_canonical_form(self):
        c = [{'regression_id': 2, 'run_ids': ['b', 'a']}, {'regression_id': 1, 'run_ids': []}]
        self.assertEqual(coverage.pairs(c), {(2, 'a'), (2, 'b')})
        self.assertEqual(coverage.zero_ids(c), {1})
        self.assertEqual(coverage.regression_ids(c), {1, 2})
        self.assertEqual(coverage.normalized(c), [{'regression_id': 1, 'run_ids': []},
                                                  {'regression_id': 2, 'run_ids': ['a', 'b']}])
        self.assertEqual(coverage.from_pairs({(2, 'b'), (2, 'a'), (1, 'x')}),
                         [{'regression_id': 1, 'run_ids': ['x']}, {'regression_id': 2, 'run_ids': ['a', 'b']}])

    def test_malformed_coverage_is_reported_not_raised(self):
        for bad in (None, 'x', [1], [{'regression_id': '1', 'run_ids': []}], [{'regression_id': True, 'run_ids': []}],
                    [{'regression_id': 1, 'run_ids': [1]}], [{'regression_id': 1, 'run_ids': ['a', 'a']}],
                    [{'regression_id': 1, 'run_ids': []}, {'regression_id': 1, 'run_ids': ['a']}]):
            self.assertTrue(coverage.problems(bad), bad)
            self.assertIsNone(coverage.normalized(bad), bad)
            coverage.pairs(bad), coverage.zero_ids(bad)


class CompatibilityTest(unittest.TestCase):
    def test_development_analysis_must_be_an_object_even_when_unanalysed(self):
        for bad in (None, [], 'unfinished', True, 0):
            current = doc([unanalysed('g-a', cov(r1=['a1']))], [inv(1, ['a1'])])
            current['clusters'][0]['disposition']['analysis'] = bad
            self.assertTrue(m.validate(current), bad)

    def test_completed_development_groups_need_current_analysis(self):
        for state in ('KNOWN-CAUSE', 'CANDIDATE', 'UNEXPLAINED', 'NEW-BUG-NEEDED'):
            for field, value in (('depth', 'none'), ('depth', 'triage-only'), ('confidence', 'medium'),
                                 ('evidence', []), ('evidence', None)):
                with self.subTest(state=state, field=field, value=value):
                    c = cluster('g-a', cov(r1=['a1']), state=state,
                                proposal=proposal() if state == 'NEW-BUG-NEEDED' else None)
                    c['disposition']['analysis'][field] = value
                    self.assertTrue(m.validate(doc([c], [inv(1, ['a1'])])))

    def test_fresh_development_analysis_and_unfinished_work_remain_valid(self):
        for depth in ('deep-dive', 'oracle'):
            c = cluster('g-a', cov(r1=['a1']), depth=depth)
            self.assertEqual(m.validate(doc([c], [inv(1, ['a1'])])), [])
        self.assertEqual(m.validate(doc([unanalysed('g-a', cov(r1=['a1']))], [inv(1, ['a1'])])), [])

    def test_devel_carry_cannot_claim_supersedes_or_another_id(self):
        baseline = baseline_one()
        current = today([cluster('g-a', cov(r1=['a1', 'a2']))], [inv(1, ['a1', 'a2'])], baseline)
        carry(current['clusters'][0], ['a1'])
        self.assertEqual(m.validate(current), [])
        for field in ('relationship', 'id'):
            bad = copy.deepcopy(current)
            if field == 'relationship':
                bad['clusters'][0]['prior']['relationship'] = 'supersedes'
            else:
                bad['clusters'][0]['id'] = 'unrelated'
            self.assertTrue(m.validate(bad), field)

    def test_ga_names_are_one_family(self):
        base = {'schema_version': '1.0', 'policy': {'name': 'ga'}, 'clusters': []}
        self.assertTrue(prior.compatible(base))
        self.assertTrue(prior.compatible(base, 'post-ga'))
        base['policy']['name'] = 'post-ga'
        self.assertTrue(prior.compatible(base, 'ga'))

    def test_memory_never_crosses_families(self):
        ga = {'schema_version': '1.0', 'policy': {'name': 'post-ga'}, 'clusters': []}
        self.assertFalse(prior.compatible(ga, 'devel', SCOPE))
        self.assertFalse(prior.compatible(baseline_one()))
        self.assertFalse(prior.compatible(baseline_one(), 'ga'))
        self.assertFalse(prior.compatible(baseline_one(), 'unknown-policy'))

    def test_devel_needs_memory_version_and_equal_scope(self):
        base = baseline_one()
        self.assertTrue(prior.compatible(base, 'devel', SCOPE))
        self.assertTrue(prior.compatible(base, 'devel', {'views': ['5.1-main'], 'components': ['*']}))
        self.assertFalse(prior.compatible(base, 'devel', {'views': ['5.1-main'], 'components': ['Installer']}))
        self.assertFalse(prior.compatible(base, 'devel', {'views': ['5.0-main'], 'components': ['*']}))
        self.assertFalse(prior.compatible(base, 'devel', 'not a scope'))
        for bad in (None, 2, True, '1'):
            old = copy.deepcopy(base)
            old['policy']['memory_version'] = bad
            self.assertFalse(prior.compatible(old, 'devel', SCOPE), bad)
        legacy = copy.deepcopy(base)
        del legacy['policy']['memory_version']
        self.assertFalse(prior.compatible(legacy, 'devel', SCOPE))
        noscope = copy.deepcopy(base)
        noscope['policy']['scope'] = None
        self.assertFalse(prior.compatible(noscope, 'devel', SCOPE))

    def test_scope_order_and_duplicates_do_not_matter(self):
        base = baseline_one()
        base['policy']['scope'] = {'views': ['b', 'a'], 'components': ['y', 'x', 'x']}
        self.assertTrue(prior.compatible(base, 'devel', {'views': ['a', 'b'], 'components': ['x', 'y']}))

    def test_incompatible_baseline_attaches_no_prior(self):
        ga = {'schema_version': '1.0', 'policy': {'name': 'post-ga'},
              'clusters': [cluster('g-a', cov(r1=['a1']))]}
        cur = [cluster('g-a', cov(r1=['a1']))]
        prior.attach_priors(cur, ga, 'devel')
        self.assertIsNone(cur[0]['prior'])
        cur = [cluster('g-a', cov(r1=['a1']))]
        prior.attach_priors(cur, baseline_one(), 'devel', scope={'views': ['other'], 'components': []})
        self.assertIsNone(cur[0]['prior'])
        cur = [cluster('g-a', cov(r1=['a1']))]
        prior.attach_priors(cur, baseline_one())             # a devel baseline under the GA default
        self.assertIsNone(cur[0]['prior'])


class PairAncestryTest(unittest.TestCase):
    def test_same_window_continues_with_run_delta(self):
        cur = [cluster('g-a', cov(r1=['a2', 'a3'], r2=['b1']))]
        prior.attach_priors(cur, baseline_one(), 'devel')
        pr = cur[0]['prior']
        self.assertEqual(pr['relationship'], 'same-id')
        self.assertEqual(pr['run_delta'], {'added': cov(r1=['a3'], r2=['b1']), 'removed': cov(r1=['a1'])})
        self.assertEqual(pr['member_delta'], {'added': [2], 'removed': []})
        src = pr['sources'][0]
        self.assertEqual(src['coverage'], cov(r1=['a1', 'a2']))
        self.assertEqual(src['signature'], SIG)
        self.assertEqual(src['matched_member_ids'], [1])
        self.assertEqual(src['run_id'], 'r0')

    def test_disjoint_window_on_the_same_regression_has_no_prior(self):
        cur = [cluster('g-a', cov(r1=['a1'])), cluster('g-c', cov(r1=['c1', 'c2']))]
        prior.attach_priors(cur, baseline_one(), 'devel')
        self.assertEqual(cur[0]['prior']['relationship'], 'same-id')
        self.assertIsNone(cur[1]['prior'])

    def test_same_id_without_shared_pairs_is_not_a_source(self):
        cur = [cluster('g-a', cov(r1=['z9']))]
        prior.attach_priors(cur, baseline_one(), 'devel')
        self.assertIsNone(cur[0]['prior'])

    def test_supersedes_lineage_is_ignored(self):
        cur = [cluster('g-new', cov(r1=['z9']))]
        cur[0]['lineage']['supersedes'] = ['g-a']
        prior.attach_priors(cur, baseline_one(), 'devel')
        self.assertIsNone(cur[0]['prior'])

    def test_shared_pairs_under_another_id_are_overlap(self):
        cur = [cluster('g-other', cov(r1=['a1', 'a2']))]
        prior.attach_priors(cur, baseline_one(), 'devel')
        self.assertEqual(cur[0]['prior']['relationship'], 'overlap')

    def test_split_and_merge(self):
        cur = [cluster('g-a', cov(r1=['a1'])), cluster('g-b', cov(r1=['a2']))]
        prior.attach_priors(cur, baseline_one(), 'devel')
        self.assertEqual([c['prior']['relationship'] for c in cur], ['split', 'split'])
        self.assertEqual(cur[0]['prior']['run_delta'], {'added': [], 'removed': cov(r1=['a2'])})
        base = doc([cluster('g-a', cov(r1=['a1'])), cluster('g-b', cov(r1=['b1']))], [inv(1, ['a1', 'b1'])])
        cur = [cluster('g-a', cov(r1=['a1', 'b1']))]
        prior.attach_priors(cur, base, 'devel')
        self.assertEqual(cur[0]['prior']['relationship'], 'merge')
        self.assertEqual([s['cluster_id'] for s in cur[0]['prior']['sources']], ['g-a', 'g-b'])

    def test_zero_run_placeholder_is_never_ancestry(self):
        base = doc([unanalysed('u-1', cov(r1=[]))], [inv(1, [])])
        cur = [unanalysed('u-1', cov(r1=[]))]
        prior.attach_priors(cur, base, 'devel')
        self.assertIsNone(cur[0]['prior'])
        mixed = doc([cluster('g-a', [{'regression_id': 1, 'run_ids': []}, {'regression_id': 2, 'run_ids': ['b1']}])],
                    [inv(1, []), inv(2, ['b1'])])
        cur = [unanalysed('g-a', cov(r1=[]))]
        prior.attach_priors(cur, mixed, 'devel')
        self.assertIsNone(cur[0]['prior'])

    def test_malformed_baseline_coverage_gives_no_source_and_no_exception(self):
        base = baseline_one()
        base['clusters'][0]['members']['coverage'] = 'broken'
        base['clusters'].append('not a cluster')
        cur = [cluster('g-a', cov(r1=['a1']))]
        prior.attach_priors(cur, base, 'devel')
        self.assertIsNone(cur[0]['prior'])

    def test_baseline_is_not_mutated(self):
        base = baseline_one()
        before = copy.deepcopy(base)
        prior.attach_priors([cluster('g-a', cov(r1=['a1']))], base, 'devel')
        self.assertEqual(base, before)

    def test_ga_projection_has_no_devel_fields(self):
        ga = {'schema_version': '1.0', 'policy': {'name': 'post-ga'}, 'source_run': {'run_id': 'r0'},
              'observation': {'time': T0}, 'clusters': [cluster('g-a', cov(r1=['a1']))]}
        cur = [cluster('g-a', cov(r1=['zz']))]
        prior.attach_priors(cur, ga)
        pr = cur[0]['prior']
        self.assertEqual(pr['relationship'], 'same-id')         # GA still matches by regression id
        self.assertNotIn('run_delta', pr)
        for k in ('coverage', 'signature', 'new_bug_proposal', 'symptom_proposals'):
            self.assertNotIn(k, pr['sources'][0])


class ProposalProjectionTest(unittest.TestCase):
    def base(self):
        c = cluster('g-a', cov(r1=['a1']), state='NEW-BUG-NEEDED', proposal=proposal())
        c['disposition']['symptom_proposals'] = [{'label': 'EtcdTimeout', 'matcher': 'request timed out'}]
        return doc([c], [inv(1, ['a1'])])

    def test_draft_is_hashed_never_copied(self):
        cur = [cluster('g-a', cov(r1=['a1']))]
        prior.attach_priors(cur, self.base(), 'devel')
        p = cur[0]['prior']['sources'][0]['new_bug_proposal']
        self.assertNotIn('draft', p)
        self.assertEqual(p['draft_sha256'], hashlib.sha256(DRAFT.encode('utf-8')).hexdigest())
        self.assertEqual(p['draft_chars'], len(DRAFT))
        self.assertEqual((p['status'], p['component'], p['regression_ids']), ('not-filed', 'Etcd', [1]))
        self.assertEqual(cur[0]['prior']['sources'][0]['symptom_proposals'],
                         [{'label': 'EtcdTimeout', 'matcher': 'request timed out'}])
        self.assertNotIn('Full bug draft', repr(cur[0]['prior']))

    def test_unreadable_draft_has_no_hash(self):
        base = self.base()
        base['clusters'][0]['disposition']['new_bug_proposal']['draft'] = None
        cur = [cluster('g-a', cov(r1=['a1']))]
        prior.attach_priors(cur, base, 'devel')
        p = cur[0]['prior']['sources'][0]['new_bug_proposal']
        self.assertIsNone(p['draft_sha256'])
        self.assertIsNone(p['draft_chars'])

    def test_no_proposal_projects_null(self):
        cur = [cluster('g-a', cov(r1=['a1']))]
        prior.attach_priors(cur, baseline_one(), 'devel')
        self.assertIsNone(cur[0]['prior']['sources'][0]['new_bug_proposal'])
        self.assertIsNone(cur[0]['prior']['sources'][0]['symptom_proposals'])

    def test_retained_history_keeps_devel_fields_flat(self):
        day0 = self.base()
        day1_cluster = unanalysed('g-a', cov(r1=['a1']))
        day1 = today([day1_cluster], [inv(1, ['a1'])], day0)
        cur = [cluster('g-a', cov(r1=['a1']))]
        day1['source_run']['run_id'] = 'r1'
        prior.attach_priors(cur, day1, 'devel')
        sources = cur[0]['prior']['sources']
        self.assertEqual([(s['history_only'], s['unfinished'], s['run_id']) for s in sources],
                         [(False, True, 'r1'), (True, False, 'r0')])
        kept = sources[1]
        self.assertEqual(kept['coverage'], cov(r1=['a1']))
        self.assertEqual(kept['signature'], SIG)
        self.assertEqual(kept['new_bug_proposal']['draft_chars'], len(DRAFT))
        self.assertEqual(kept['state'], 'NEW-BUG-NEEDED')
        self.assertNotIn('prior', kept)
        self.assertEqual(cur[0]['prior']['run_delta'], {'added': [], 'removed': []})


class DevelManifestTest(unittest.TestCase):
    def valid(self):
        return doc([cluster('g-a', cov(r1=['a1', 'a2'])), cluster('g-c', cov(r1=['c1'], r2=['c1']))],
                   [inv(1, ['a1', 'a2', 'c1']), inv(2, ['c1']), inv(3, ['t1'], required=False)])

    def test_valid_document(self):
        self.assertEqual(m.validate(self.valid()), [])

    def test_ga_skeleton_keys_are_not_required_but_inventory_is(self):
        d = self.valid()
        del d['inventory']
        self.assertTrue(mentions(m.validate(d), 'inventory'))
        d = self.valid()
        del d['unanalysed']
        self.assertTrue(mentions(m.validate(d), 'unanalysed'))

    def test_policy_fields(self):
        for key, bad in (('memory_version', 2), ('memory_version', True), ('memory_mode', 'fast'),
                         ('scope', None), ('scope', {'views': [], 'components': []}),
                         ('scope', {'views': ['v'], 'components': 'x'})):
            d = self.valid()
            d['policy'][key] = bad
            self.assertTrue(mentions(m.validate(d), 'policy.' + key), (key, bad))

    def test_malformed_documents_return_errors(self):
        for mutate in (lambda d: d.update(inventory='x'), lambda d: d.update(inventory=[1, {'id': 'x'}]),
                       lambda d: d['inventory'][0].update(job_runs=None),
                       lambda d: d['inventory'][0].update(job_runs=[None, {}]),
                       lambda d: d['inventory'][0].update(required='yes'),
                       lambda d: d['inventory'].append(inv(1, ['dup'])),
                       lambda d: d['clusters'][0]['members'].update(coverage=None),
                       lambda d: d['clusters'][0]['members'].update(coverage=[{'regression_id': 1}]),
                       lambda d: d['clusters'][0].update(members=None),
                       lambda d: d['clusters'][0].update(signature='x'),
                       lambda d: d['clusters'][0].update(signature={'stage': 1, 'discriminator': None}),
                       lambda d: d['clusters'][0].pop('signature'),
                       lambda d: d['clusters'][0].update(disposition=None),
                       lambda d: d['clusters'][0]['disposition']['analysis'].update(evidence=[None, {'prowjob_run_id': []}]),
                       lambda d: d['clusters'].append(None),
                       lambda d: d.update(policy={'name': 'devel'}),
                       lambda d: d['clusters'][0].update(prior={'sources': [None], 'run_delta': 'x'})):
            d = self.valid()
            mutate(d)
            self.assertTrue(m.validate(d), mutate)

    def test_coverage_must_match_members(self):
        d = self.valid()
        d['clusters'][0]['members']['regression_ids'] = [1, 2]
        self.assertTrue(mentions(m.validate(d), 'g-a', 'coverage'))

    def test_coverage_must_be_listed_own_runs(self):
        d = self.valid()
        d['clusters'][0]['members']['coverage'][0]['run_ids'].append('foreign')
        self.assertTrue(mentions(m.validate(d), 'g-a', 'foreign'))
        d = self.valid()
        d['clusters'][0]['members']['coverage'] = cov(r9=['a1'])
        d['clusters'][0]['members']['regression_ids'] = [9]
        self.assertTrue(mentions(m.validate(d), 'g-a', 'inventory'))

    def test_integer_inventory_run_ids_match_string_coverage(self):
        d = doc([cluster('g-a', cov(r1=['101']))], [{'id': 1, 'required': True, 'job_runs': [{'prowjob_run_id': 101}]}])
        self.assertEqual(m.validate(d), [])

    def test_a_pair_belongs_to_one_cluster(self):
        d = self.valid()
        d['clusters'][1]['members']['coverage'][0]['run_ids'].append('a1')
        self.assertTrue(mentions(m.validate(d), 'a1', 'more than one cluster'))

    def test_required_runs_must_all_be_represented(self):
        d = self.valid()
        d['clusters'][0]['members']['coverage'][0]['run_ids'].remove('a2')
        self.assertTrue(mentions(m.validate(d), 'regression 1', 'a2', 'not represented'))
        d = self.valid()
        d['clusters'] = d['clusters'][:1]
        errs = m.validate(d)
        self.assertTrue(mentions(errs, 'regression 2', 'not represented'))

    def test_optional_regressions_may_be_absent_or_added(self):
        d = self.valid()
        d['clusters'].append(cluster('g-t', cov(r3=['t1'])))
        self.assertEqual(m.validate(d), [])

    def test_zero_run_regression_needs_a_placeholder(self):
        inventory = [inv(1, [])]
        self.assertTrue(mentions(m.validate(doc([], inventory)), 'regression 1', 'not represented'))
        self.assertEqual(m.validate(doc([unanalysed('u-1', cov(r1=[]))], inventory)), [])
        twice = doc([unanalysed('u-1', cov(r1=[])), unanalysed('u-2', cov(r1=[]))], inventory)
        self.assertTrue(mentions(m.validate(twice), 'regression 1', 'more than one cluster'))

    def test_placeholder_only_for_a_regression_without_runs(self):
        d = doc([unanalysed('u-1', cov(r1=[]))], [inv(1, ['a1'])])
        self.assertTrue(mentions(m.validate(d), 'u-1', 'regression 1', 'placeholder'))

    def test_zero_only_cluster_must_be_unanalysed(self):
        c = cluster('g-z', cov(r1=[]), state='UNEXPLAINED')
        errs = m.validate(doc([c], [inv(1, [])]))
        self.assertTrue(mentions(errs, 'g-z', 'UNANALYSED'))

    def test_evidence_must_be_a_pair_of_this_cluster(self):
        d = self.valid()
        # c1 is an own run of regression 1, but it belongs to the other window (g-c)
        d['clusters'][0]['disposition']['analysis']['evidence'][0]['prowjob_run_id'] = 'c1'
        self.assertTrue(mentions(m.validate(d), 'g-a', 'c1', 'not in this cluster'))
        d = self.valid()
        d['clusters'][1]['disposition']['analysis']['evidence'] = [
            {'claim': 'x', 'prowjob_run_id': 'c1', 'supports_regression_ids': [1, 2]}]
        self.assertEqual(m.validate(d), [])

    def test_new_bug_needed_requires_a_draft_and_permits_no_write(self):
        def one(**kw):
            return doc([cluster('g-a', cov(r1=['a1']), state='NEW-BUG-NEEDED', **kw)], [inv(1, ['a1'])])
        self.assertEqual(m.validate(one(proposal=proposal())), [])
        self.assertTrue(mentions(m.validate(one()), 'g-a', 'new_bug_proposal'))
        self.assertTrue(mentions(m.validate(one(proposal=proposal(draft=''))), 'g-a', 'draft'))
        d = one(proposal=proposal())
        d['clusters'][0]['disposition']['proposed_action'] = {'type': 'create_triage', 'regression_ids': [1]}
        self.assertTrue(mentions(m.validate(d), 'g-a', 'NEW-BUG-NEEDED', 'write'))
        d = one(proposal=proposal())
        d['clusters'][0]['actions'] = [{'type': 'extend_triage', 'triage_id': 1, 'regression_ids': [1],
                                        'status': 'skipped-report-mode'}]
        self.assertTrue(mentions(m.validate(d), 'g-a', 'NEW-BUG-NEEDED', 'write'))

    def test_new_bug_needed_is_devel_only(self):
        d = self.valid()
        d['clusters'][0]['disposition']['state'] = 'NEW-BUG-NEEDED'
        d['policy'] = {'name': 'post-ga'}
        self.assertTrue(mentions(m.validate(d), 'disposition.state', 'NEW-BUG-NEEDED'))
        self.assertNotIn('NEW-BUG-NEEDED', m.STATES)


class DevelPriorEnvelopeTest(unittest.TestCase):
    def day_two(self, **kw):
        base = baseline_one()
        return today([cluster('g-a', cov(r1=['a2', 'a3']))], [inv(1, ['a2', 'a3'])], base, **kw)

    def test_attached_prior_validates(self):
        self.assertEqual(m.validate(self.day_two()), [])

    def test_run_delta_must_be_exact(self):
        d = self.day_two()
        d['clusters'][0]['prior']['run_delta']['added'] = []
        self.assertTrue(mentions(m.validate(d), 'run_delta.added'))
        d = self.day_two()
        d['clusters'][0]['prior']['run_delta']['removed'] = cov(r1=['a1', 'zz'])
        self.assertTrue(mentions(m.validate(d), 'run_delta.removed'))
        d = self.day_two()
        del d['clusters'][0]['prior']['run_delta']
        self.assertTrue(mentions(m.validate(d), 'run_delta'))

    def test_immediate_source_must_share_a_pair(self):
        d = self.day_two()
        pr = d['clusters'][0]['prior']
        pr['sources'][0]['coverage'] = cov(r1=['old1'])
        pr['run_delta'] = {'added': cov(r1=['a2', 'a3']), 'removed': cov(r1=['old1'])}
        self.assertTrue(mentions(m.validate(d), 'shares no (regression, run) pair'))

    def test_source_never_carries_a_draft(self):
        d = self.day_two()
        d['clusters'][0]['prior']['sources'][0]['new_bug_proposal'] = {'draft': 'copied body', 'draft_sha256': 'x',
                                                                      'draft_chars': 11}
        self.assertTrue(mentions(m.validate(d), 'new_bug_proposal', 'draft'))

    def test_source_field_shapes(self):
        for key, bad in (('coverage', 'x'), ('signature', 'x'), ('symptom_proposals', {}), ('new_bug_proposal', [])):
            d = self.day_two()
            d['clusters'][0]['prior']['sources'][0][key] = bad
            self.assertTrue(mentions(m.validate(d), 'sources[0]', key), key)


class DevelCarryTest(unittest.TestCase):
    def carried(self, current=None, own=('a3',), base=None, inventory=None, **kw):
        base = base or baseline_one()
        cur = current or cluster('g-a', cov(r1=['a2', 'a3']))
        if current is None:
            cur['disposition']['analysis']['evidence'][0].update(prowjob_run_id='a3')
        d = today([cur], inventory or [inv(1, ['a2', 'a3'])], base, **kw)
        carry(d['clusters'][0], own)
        return d

    def test_carry_with_an_added_pair_checked(self):
        self.assertEqual(m.validate(self.carried()), [])

    def test_record_mode_rejects_carry(self):
        errs = m.validate(self.carried(mode='record'))
        self.assertTrue(mentions(errs, 'memory_mode record'))

    def test_record_mode_allows_reinvestigation_records(self):
        d = self.carried(mode='record')
        an = d['clusters'][0]['disposition']['analysis']
        an['depth'] = 'deep-dive'
        an['reverification']['outcome'] = 'reinvestigated'
        self.assertEqual(m.validate(d), [])

    def test_carry_needs_an_added_pair_not_just_an_old_run(self):
        cur = cluster('g-a', cov(r1=['a2', 'a3']))          # evidence on a2, a retained run
        errs = m.validate(self.carried(current=cur, own=('a2',)))
        self.assertTrue(mentions(errs, 'added', 'pair'))

    def test_added_run_shared_with_another_regression_does_not_count(self):
        # run s is retained for regression 1 and newly added for regression 2: evidence must support 2 on s
        base = doc([cluster('g-a', cov(r1=['s']))], [inv(1, ['s'])])
        cur = cluster('g-a', cov(r1=['s'], r2=['s']))
        cur['disposition']['analysis']['evidence'] = [
            {'claim': 'x', 'prowjob_run_id': 's', 'supports_regression_ids': [1]}]
        cur['members']['unlinked'] = [{'id': 2, 'reason': 'not checked'}]
        inventory = [inv(1, ['s']), inv(2, ['s'])]
        errs = m.validate(self.carried(current=cur, own=('s',), base=base, inventory=inventory))
        self.assertTrue(mentions(errs, 'added', 'pair'))
        good = copy.deepcopy(cur)
        good.pop('prior', None)
        good['disposition']['analysis'].pop('reverification', None)
        good['disposition']['analysis']['depth'] = 'deep-dive'
        good['disposition']['analysis']['evidence'][0]['supports_regression_ids'] = [1, 2]
        self.assertEqual(m.validate(self.carried(current=good, own=('s',), base=base, inventory=inventory)), [])

    def test_closed_window_carries_on_a_retained_run(self):
        cur = cluster('g-a', cov(r1=['a1', 'a2']))
        self.assertEqual(m.validate(self.carried(current=cur, own=('a1',), inventory=[inv(1, ['a1', 'a2'])])), [])

    def test_carry_requires_the_same_signature(self):
        for sig in ({'stage': 'bootstrap', 'discriminator': 'another line'},
                    {'stage': 'install', 'discriminator': SIG['discriminator']}):
            d = self.carried()
            d['clusters'][0]['signature'] = sig
            self.assertTrue(mentions(m.validate(d), 'signature'), sig)

    def test_empty_signature_cannot_be_carried(self):
        empty = {'stage': '', 'discriminator': ''}
        base = doc([cluster('g-a', cov(r1=['a1', 'a2']), signature=empty)], [inv(1, ['a1', 'a2'])])
        cur = cluster('g-a', cov(r1=['a1', 'a2']), signature=empty)
        errs = m.validate(self.carried(current=cur, own=('a1',), base=base, inventory=[inv(1, ['a1', 'a2'])]))
        self.assertTrue(mentions(errs, 'signature'))

    def test_overlap_under_a_new_id_cannot_be_carried(self):
        cur = cluster('g-renamed', cov(r1=['a1', 'a2']))
        errs = m.validate(self.carried(current=cur, own=('a1',), inventory=[inv(1, ['a1', 'a2'])]))
        self.assertTrue(mentions(errs, 'relationship'))

    def test_high_is_never_carried(self):
        cur = cluster('g-a', cov(r1=['a1', 'a2']), level='HIGH')
        errs = m.validate(self.carried(current=cur, own=('a1',), inventory=[inv(1, ['a1', 'a2'])]))
        self.assertTrue(mentions(errs, 'HIGH'))

    def new_bug(self, base_proposal=proposal(), current_proposal=proposal()):
        base = doc([cluster('g-a', cov(r1=['a1']), state='NEW-BUG-NEEDED', proposal=base_proposal)], [inv(1, ['a1'])])
        cur = cluster('g-a', cov(r1=['a1']), state='NEW-BUG-NEEDED', proposal=current_proposal)
        return self.carried(current=cur, own=('a1',), base=base, inventory=[inv(1, ['a1'])])

    def test_new_bug_needed_carries_with_source_proposal_metadata(self):
        self.assertEqual(m.validate(self.new_bug()), [])

    def test_new_bug_needed_carry_needs_a_readable_source_draft(self):
        errs = m.validate(self.new_bug(base_proposal=proposal(draft=None)))
        self.assertTrue(mentions(errs, 'NEW-BUG-NEEDED carry', 'draft_sha256'))

    def test_new_bug_needed_carry_rejects_a_candidate_that_met_the_bar(self):
        d = self.new_bug()
        d['clusters'][0]['prior']['sources'][0]['bug_search']['candidates'] = [{'key': 'OCPBUGS-9', 'bar_met': True}]
        self.assertTrue(mentions(m.validate(d), 'NEW-BUG-NEEDED carry'))


class MergeProtectionTest(unittest.TestCase):
    def prepass(self):
        d = doc([cluster('g-a', cov(r1=['a1']))], [inv(1, ['a1'])])
        for c in d['clusters']:
            for k in ('disposition', 'actions', 'escalation'):
                del c[k]
        del d['unanalysed']
        return d

    def disposition(self):
        return cluster('g-a', cov(r1=['a1']))['disposition']

    def test_merge_with_extra_validates(self):
        out = m.merge(self.prepass(), {'g-a': self.disposition()}, {}, extra={'unanalysed': []})
        self.assertEqual(m.validate(out), [])
        self.assertEqual(out['clusters'][0]['signature'], SIG)

    def test_extra_cannot_replace_deterministic_fields(self):
        for key in ('clusters', 'policy', 'inventory', 'observation', 'baseline_run', 'source_run', 'schema_version'):
            with self.assertRaises(ValueError, msg=key):
                m.merge(self.prepass(), {'g-a': self.disposition()}, {}, extra={key: {}})
        with self.assertRaises(ValueError):
            m.apply_extra(self.prepass(), ['not an object'])

    def test_disposition_cannot_set_cluster_owned_fields(self):
        for key in ('signature', 'coverage', 'members', 'prior'):
            disp = self.disposition()
            disp[key] = {}
            with self.assertRaises(ValueError, msg=key):
                m.merge(self.prepass(), {'g-a': disp}, {})

    def test_ga_extra_keeps_its_existing_freedom(self):
        ga = {'schema_version': '1.0', 'policy': {'name': 'post-ga'}, 'clusters': []}
        out = m.apply_extra(ga, {'observation': {'note': 'ga may still set this'}, 'audit': {}})
        self.assertEqual(out['observation'], {'note': 'ga may still set this'})
        with self.assertRaises(ValueError):
            m.apply_extra(ga, {'clusters': []})


if __name__ == '__main__':
    unittest.main()
