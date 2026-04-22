#!/usr/bin/env python3
"""Tests for _get_is_bot() and stratified_sample() in sample_and_estimate.py."""

import unittest
from sample_and_estimate import _get_is_bot, stratified_sample


class TestGetIsBot(unittest.TestCase):

    def test_bool_true(self):
        self.assertTrue(_get_is_bot({"IS_BOT": True}))

    def test_bool_false(self):
        self.assertFalse(_get_is_bot({"IS_BOT": False}))

    def test_string_true_lowercase(self):
        self.assertTrue(_get_is_bot({"IS_BOT": "true"}))

    def test_string_true_uppercase(self):
        self.assertTrue(_get_is_bot({"IS_BOT": "TRUE"}))

    def test_string_true_mixed_case(self):
        self.assertTrue(_get_is_bot({"IS_BOT": "True"}))

    def test_string_one(self):
        self.assertTrue(_get_is_bot({"IS_BOT": "1"}))

    def test_string_yes(self):
        self.assertTrue(_get_is_bot({"IS_BOT": "yes"}))

    def test_string_false(self):
        self.assertFalse(_get_is_bot({"IS_BOT": "false"}))

    def test_string_zero(self):
        self.assertFalse(_get_is_bot({"IS_BOT": "0"}))

    def test_string_no(self):
        self.assertFalse(_get_is_bot({"IS_BOT": "no"}))

    def test_int_one(self):
        self.assertTrue(_get_is_bot({"IS_BOT": 1}))

    def test_int_zero(self):
        self.assertFalse(_get_is_bot({"IS_BOT": 0}))

    def test_none_value(self):
        self.assertFalse(_get_is_bot({"IS_BOT": None}))

    def test_missing_key_defaults_false(self):
        self.assertFalse(_get_is_bot({}))

    def test_lowercase_key(self):
        self.assertTrue(_get_is_bot({"is_bot": True}))

    def test_lowercase_key_string(self):
        self.assertFalse(_get_is_bot({"is_bot": "false"}))

    def test_uppercase_takes_precedence(self):
        self.assertTrue(_get_is_bot({"IS_BOT": True, "is_bot": False}))


class TestStratifiedSample(unittest.TestCase):

    def _make_issues(self, specs):
        """Build issue list from (project, is_bot, count) tuples."""
        issues = []
        for proj, is_bot, count in specs:
            for i in range(count):
                issues.append({
                    "PROJECT_KEY": proj,
                    "IS_BOT": is_bot,
                    "ISSUEKEY": f"{proj}-{i}",
                })
        return issues

    def test_sample_size_exceeds_total_returns_all(self):
        issues = self._make_issues([("A", False, 5)])
        sample, counts = stratified_sample(issues, 100)
        self.assertEqual(len(sample), 5)
        self.assertEqual(counts[("A", "human")], 5)

    def test_sample_equals_total_returns_all(self):
        issues = self._make_issues([("A", False, 10)])
        sample, counts = stratified_sample(issues, 10)
        self.assertEqual(len(sample), 10)

    def test_every_stratum_gets_at_least_one(self):
        issues = self._make_issues([
            ("A", False, 100),
            ("A", True, 100),
            ("B", False, 5),
            ("B", True, 3),
        ])
        sample, counts = stratified_sample(issues, 10)
        self.assertEqual(len(sample), 10)
        self.assertGreaterEqual(counts[("A", "human")], 1)
        self.assertGreaterEqual(counts[("A", "bot")], 1)
        self.assertGreaterEqual(counts[("B", "human")], 1)
        self.assertGreaterEqual(counts[("B", "bot")], 1)

    def test_all_human_no_bot_strata(self):
        issues = self._make_issues([
            ("A", False, 50),
            ("B", False, 50),
        ])
        sample, counts = stratified_sample(issues, 20)
        self.assertEqual(len(sample), 20)
        self.assertNotIn(("A", "bot"), counts)
        self.assertNotIn(("B", "bot"), counts)
        self.assertIn(("A", "human"), counts)
        self.assertIn(("B", "human"), counts)

    def test_all_bot_no_human_strata(self):
        issues = self._make_issues([("A", True, 30)])
        sample, counts = stratified_sample(issues, 10)
        self.assertEqual(len(sample), 10)
        self.assertIn(("A", "bot"), counts)
        self.assertNotIn(("A", "human"), counts)

    def test_proportional_allocation(self):
        issues = self._make_issues([
            ("A", False, 900),
            ("A", True, 100),
        ])
        sample, counts = stratified_sample(issues, 100)
        self.assertEqual(len(sample), 100)
        self.assertGreater(counts[("A", "human")], counts[("A", "bot")])

    def test_deterministic_with_seed(self):
        issues = self._make_issues([
            ("A", False, 50),
            ("A", True, 50),
        ])
        s1, c1 = stratified_sample(issues, 20, seed=123)
        s2, c2 = stratified_sample(issues, 20, seed=123)
        self.assertEqual([i["ISSUEKEY"] for i in s1],
                         [i["ISSUEKEY"] for i in s2])

    def test_different_seeds_differ(self):
        issues = self._make_issues([
            ("A", False, 100),
            ("A", True, 100),
        ])
        s1, _ = stratified_sample(issues, 20, seed=1)
        s2, _ = stratified_sample(issues, 20, seed=2)
        keys1 = set(i["ISSUEKEY"] for i in s1)
        keys2 = set(i["ISSUEKEY"] for i in s2)
        self.assertNotEqual(keys1, keys2)

    def test_return_counts_use_tuple_keys(self):
        issues = self._make_issues([
            ("PROJ", False, 10),
            ("PROJ", True, 5),
        ])
        _, counts = stratified_sample(issues, 8)
        for key in counts:
            self.assertIsInstance(key, tuple)
            self.assertEqual(len(key), 2)

    def test_lowercase_keys_handled(self):
        issues = [
            {"project_key": "X", "is_bot": False, "ISSUEKEY": "X-1"},
            {"project_key": "X", "is_bot": True, "ISSUEKEY": "X-2"},
        ]
        sample, counts = stratified_sample(issues, 2)
        self.assertEqual(len(sample), 2)


if __name__ == "__main__":
    unittest.main()
