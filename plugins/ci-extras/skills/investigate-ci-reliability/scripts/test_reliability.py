#!/usr/bin/env python3
"""Behavioral tests for the independently validated issue export boundary."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import reliability as r


class ExportTest(unittest.TestCase):
    def setUp(self):
        scratch = Path.home() / 'tmp'
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / 'work'
        self.work.mkdir()
        for name in ('candidates', 'reviews', 'evidence'):
            (self.work / name).mkdir()
        r.write(self.work / 'config.json', {'max_issues': 1, 'max_candidates': 10})
        self.artifact = self.work / 'evidence' / 'source.txt'
        self.artifact.write_text('operation fails\nsource loses retry state\ncontrol retains state\n')

    def candidate(self, ident='lease-state', key=None, verdict='PROVEN_FIX', priority=1):
        c = dict(id=ident, defect_key=key or ident, title='Lost retry state', investigator='investigator-1',
                 owner='CI client owners', summary='A failed request loses ownership.', mechanism='Local state is deleted before acknowledgement.',
                 current_state='Pinned current client has the same ordering.', currently_unfixed=True,
                 proposed_change='Retain state until acknowledgement.', validation='Inject a failed request; assert a retry reaches the server.',
                 limitations='Does not guarantee the provider outage resolves.', verdict=verdict, priority=priority,
                 runs=[dict(run_id='2097026807415967744', job='example-job', url='https://example.org/run', result='F', blocking_failure=True)],
                 evidence=[dict(id=role, role=role, path='evidence/source.txt', sha256=hashlib.sha256(self.artifact.read_bytes()).hexdigest(),
                                source_url='https://example.org/source', line_start=1, line_end=3) for role in sorted(r.ROLES)])
        r.write(self.work / 'candidates' / (ident + '.json'), c)
        return c

    def review(self, c, verdict='PROVEN_FIX', reviewer='reviewer-2'):
        review = dict(candidate_id=c['id'], candidate_sha256=r.digest(c), reviewer=reviewer, verdict=verdict,
                      checked_evidence_ids=[e['id'] for e in c['evidence']], reasoning='The retained source demonstrates lost state.',
                      counterargument='Provider availability is separate and remains unresolved.', repair_scope='Repair retry state, not provider availability.')
        r.write(self.work / 'reviews' / (c['id'] + '.json'), review)
        return review

    def test_exports_portable_evidence_and_reviews(self):
        c = self.candidate(); self.review(c)
        out = self.root / 'out'
        self.assertEqual(r.publish(self.work, out)['validated_issues'], 1)
        target = out / 'issues' / c['id']
        exported = r.read(target / 'finding.json')
        for e in exported['evidence']:
            self.assertTrue((target / e['path']).is_file())
            self.assertEqual(hashlib.sha256((target / e['path']).read_bytes()).hexdigest(), e['sha256'])
        self.assertEqual(r.read(target / 'review.json')['exported_candidate_sha256'], r.digest(exported))
        self.assertIn('Independent review', (target / 'README.md').read_text())

    def test_no_promotion_without_both_reviews(self):
        for n, status in enumerate(['UNRESOLVED', 'ALREADY_FIXED', 'REJECTED']):
            c = self.candidate(f'candidate-{n}', verdict=status); self.review(c)
        c = self.candidate('missing-review')
        out = self.root / 'out'; r.publish(self.work, out)
        self.assertEqual(list((out / 'issues').iterdir()), [])
        self.assertEqual(len(r.read(out / 'unresolved.json')), 4)

    def test_independent_rejection_blocks_author(self):
        c = self.candidate(); self.review(c, 'UNRESOLVED')
        self.assertEqual(r.publish(self.work, self.root / 'out')['validated_issues'], 0)

    def test_stale_review_fails_before_output(self):
        c = self.candidate(); self.review(c)
        c['proposed_change'] = 'Different change'
        r.write(self.work / 'candidates' / (c['id'] + '.json'), c)
        with self.assertRaisesRegex(ValueError, 'exact current candidate'):
            r.publish(self.work, self.root / 'out')
        self.assertFalse((self.root / 'out').exists())

    def test_changed_artifact_rejected(self):
        c = self.candidate(); self.review(c); self.artifact.write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            r.publish(self.work, self.root / 'out')

    def test_self_review_rejected(self):
        c = self.candidate(); self.review(c, reviewer=c['investigator'])
        with self.assertRaisesRegex(ValueError, 'independently'):
            r.load(self.work)

    def test_deduplication_and_cap_apply_after_proof(self):
        for ident, key, priority in [('a', 'same-defect', 1), ('b', 'same-defect', 1), ('c', 'different-defect', 2)]:
            c = self.candidate(ident, key=key, priority=priority); self.review(c)
        out = self.root / 'out'; r.publish(self.work, out)
        self.assertEqual([p.name for p in (out / 'issues').iterdir()], ['a'])
        self.assertEqual({x['reason'] for x in r.read(out / 'unresolved.json')}, {'DUPLICATE_MECHANISM', 'VALIDATED_OVER_LIMIT'})

    def test_existing_output_is_preserved(self):
        out = self.root / 'out'; out.mkdir(); (out / 'manual.txt').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            r.publish(self.work, out)
        self.assertEqual((out / 'manual.txt').read_text(), 'keep')

    def test_path_escape_and_line_ranges(self):
        c = self.candidate()
        c['evidence'][0]['path'] = '../secret.txt'
        with self.assertRaises(ValueError):r.validate_candidate(self.work, c)
        c = self.candidate(); c['evidence'][0]['line_end'] = 99
        with self.assertRaisesRegex(ValueError, 'line range'):r.validate_candidate(self.work, c)

    def test_symlink_escape_rejected(self):
        outside = self.root / 'outside'; outside.write_text('private')
        (self.work / 'evidence' / 'link').symlink_to(outside)
        with self.assertRaises(ValueError):r.safe_file(self.work, 'evidence/link')

    def test_missing_control_and_green_only_rejected(self):
        c = self.candidate(); c['evidence'] = [e for e in c['evidence'] if e['role'] != 'control']
        with self.assertRaisesRegex(ValueError, 'control evidence'):r.validate_candidate(self.work, c)
        c = self.candidate(); c['runs'][0]['result'] = 'S'
        with self.assertRaisesRegex(ValueError, 'actual blocking'):r.validate_candidate(self.work, c)

    def test_nonterminal_unknown_and_success_aliases_cannot_prove_failure(self):
        for result in ('triggered', 'unknown', 'Success', 'success', 'pending', 'S', 'R', 'running'):
            with self.subTest(result=result):
                c = self.candidate(); c['runs'][0]['result'] = result
                with self.assertRaisesRegex(ValueError, 'actual blocking'):
                    r.validate_candidate(self.work, c)

    def test_html_titles_are_escaped(self):
        c = self.candidate(); c['title'] = '<script>alert(1)</script>'
        r.write(self.work / 'candidates' / (c['id'] + '.json'), c); self.review(c)
        out = self.root / 'out'; r.publish(self.work, out)
        self.assertNotIn('<script>', (out / 'index.html').read_text())


if __name__ == '__main__':
    unittest.main()
