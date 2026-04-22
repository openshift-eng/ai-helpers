#!/usr/bin/env python3
"""Tests for sample_and_estimate.py: bot detection, stratified sampling,
sample size recommendation, and weighted overall estimation."""

import unittest
from sample_and_estimate import (
    _get_is_bot, stratified_sample, recommend_sample_size,
    recommend_sample_sizes, estimate_distribution,
    weighted_overall_estimate,
)


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
                    "ISSUEKEY": f"{proj}-{'b' if is_bot else 'h'}-{i}",
                })
        return issues

    def test_human_only_sample(self):
        issues = self._make_issues([("A", False, 50)])
        sample, meta = stratified_sample(issues, 10, 0)
        self.assertEqual(len(sample), 10)
        self.assertEqual(meta["human"]["total"], 10)
        self.assertEqual(meta["bot"]["total"], 0)

    def test_bot_only_sample(self):
        issues = self._make_issues([("A", True, 30)])
        sample, meta = stratified_sample(issues, 0, 10)
        self.assertEqual(len(sample), 10)
        self.assertEqual(meta["human"]["total"], 0)
        self.assertEqual(meta["bot"]["total"], 10)

    def test_both_populations_sampled_independently(self):
        issues = self._make_issues([
            ("A", False, 100),
            ("A", True, 50),
        ])
        sample, meta = stratified_sample(issues, 20, 15)
        self.assertEqual(len(sample), 35)
        self.assertEqual(meta["human"]["total"], 20)
        self.assertEqual(meta["bot"]["total"], 15)

    def test_budget_exceeds_population_caps_at_total(self):
        issues = self._make_issues([("A", False, 5), ("A", True, 3)])
        sample, meta = stratified_sample(issues, 100, 100)
        self.assertEqual(len(sample), 8)
        self.assertEqual(meta["human"]["total"], 5)
        self.assertEqual(meta["bot"]["total"], 3)

    def test_zero_budget_for_both(self):
        issues = self._make_issues([("A", False, 10), ("A", True, 5)])
        sample, meta = stratified_sample(issues, 0, 0)
        self.assertEqual(len(sample), 0)
        self.assertEqual(meta["human"]["total"], 0)
        self.assertEqual(meta["bot"]["total"], 0)

    def test_multi_project_human_sample(self):
        issues = self._make_issues([
            ("A", False, 100),
            ("B", False, 50),
            ("C", False, 10),
        ])
        sample, meta = stratified_sample(issues, 20, 0)
        self.assertEqual(len(sample), 20)
        self.assertEqual(meta["human"]["total"], 20)

    def test_multi_project_bot_sample(self):
        issues = self._make_issues([
            ("A", True, 80),
            ("B", True, 20),
        ])
        sample, meta = stratified_sample(issues, 0, 30)
        self.assertEqual(len(sample), 30)
        self.assertEqual(meta["bot"]["total"], 30)

    def test_mixed_projects_independent_sampling(self):
        issues = self._make_issues([
            ("A", False, 200),
            ("A", True, 100),
            ("B", False, 50),
            ("B", True, 10),
        ])
        sample, meta = stratified_sample(issues, 30, 20)
        self.assertEqual(meta["human"]["total"], 30)
        self.assertEqual(meta["bot"]["total"], 20)
        self.assertEqual(len(sample), 50)

    def test_deterministic_with_seed(self):
        issues = self._make_issues([
            ("A", False, 50),
            ("A", True, 50),
        ])
        s1, _ = stratified_sample(issues, 10, 10, seed=123)
        s2, _ = stratified_sample(issues, 10, 10, seed=123)
        self.assertEqual([i["ISSUEKEY"] for i in s1],
                         [i["ISSUEKEY"] for i in s2])

    def test_different_seeds_differ(self):
        issues = self._make_issues([
            ("A", False, 100),
            ("A", True, 100),
        ])
        s1, _ = stratified_sample(issues, 20, 20, seed=1)
        s2, _ = stratified_sample(issues, 20, 20, seed=2)
        keys1 = set(i["ISSUEKEY"] for i in s1)
        keys2 = set(i["ISSUEKEY"] for i in s2)
        self.assertNotEqual(keys1, keys2)

    def test_no_bots_in_population(self):
        issues = self._make_issues([
            ("A", False, 50),
            ("B", False, 50),
        ])
        sample, meta = stratified_sample(issues, 20, 10)
        self.assertEqual(meta["human"]["total"], 20)
        self.assertEqual(meta["bot"]["total"], 0)
        self.assertEqual(len(sample), 20)

    def test_no_humans_in_population(self):
        issues = self._make_issues([("A", True, 30)])
        sample, meta = stratified_sample(issues, 10, 10)
        self.assertEqual(meta["human"]["total"], 0)
        self.assertEqual(meta["bot"]["total"], 10)
        self.assertEqual(len(sample), 10)

    def test_lowercase_keys_handled(self):
        issues = [
            {"project_key": "X", "is_bot": False, "ISSUEKEY": "X-1"},
            {"project_key": "X", "is_bot": True, "ISSUEKEY": "X-2"},
        ]
        sample, meta = stratified_sample(issues, 1, 1)
        self.assertEqual(len(sample), 2)


class TestRecommendSampleSizes(unittest.TestCase):

    def _make_issues(self, human_count, bot_count, project="A"):
        issues = []
        for i in range(human_count):
            issues.append({"PROJECT_KEY": project, "IS_BOT": False,
                           "ISSUEKEY": f"{project}-h-{i}"})
        for i in range(bot_count):
            issues.append({"PROJECT_KEY": project, "IS_BOT": True,
                           "ISSUEKEY": f"{project}-b-{i}"})
        return issues

    def test_both_populations_get_independent_sizes(self):
        issues = self._make_issues(1000, 500)
        sizes = recommend_sample_sizes(issues, target_width=0.10)
        self.assertEqual(sizes["human_pop"], 1000)
        self.assertEqual(sizes["bot_pop"], 500)
        self.assertGreater(sizes["human_n"], 0)
        self.assertGreater(sizes["bot_n"], 0)
        self.assertEqual(sizes["human_n"],
                         recommend_sample_size(1000, target_width=0.10))
        self.assertEqual(sizes["bot_n"],
                         recommend_sample_size(500, target_width=0.10))

    def test_small_bot_population_gets_census(self):
        issues = self._make_issues(1000, 5)
        sizes = recommend_sample_sizes(issues, target_width=0.10)
        self.assertEqual(sizes["bot_n"], 5)

    def test_no_bots_returns_zero(self):
        issues = self._make_issues(1000, 0)
        sizes = recommend_sample_sizes(issues, target_width=0.10)
        self.assertEqual(sizes["bot_n"], 0)
        self.assertEqual(sizes["bot_pop"], 0)
        self.assertGreater(sizes["human_n"], 0)

    def test_no_humans_returns_zero_human(self):
        issues = self._make_issues(0, 500)
        sizes = recommend_sample_sizes(issues, target_width=0.10)
        self.assertEqual(sizes["human_n"], 0)
        self.assertEqual(sizes["human_pop"], 0)
        self.assertGreater(sizes["bot_n"], 0)

    def test_target_width_affects_size(self):
        issues = self._make_issues(5000, 2000)
        narrow = recommend_sample_sizes(issues, target_width=0.05)
        wide = recommend_sample_sizes(issues, target_width=0.15)
        self.assertGreater(narrow["human_n"], wide["human_n"])
        self.assertGreater(narrow["bot_n"], wide["bot_n"])


class TestWeightedOverallEstimate(unittest.TestCase):

    def _make_classified(self, category, count, is_bot=False):
        return [{"activity_type": category, "is_bot": is_bot}
                for _ in range(count)]

    def test_single_population_human_only(self):
        human = self._make_classified("Product / Portfolio Work", 50)
        result = weighted_overall_estimate(human, [], 100, 0, seed=42)
        self.assertIn("estimates", result)
        self.assertNotIn("weighting", result)

    def test_single_population_bot_only(self):
        bot = self._make_classified("Quality / Stability / Reliability", 30,
                                    is_bot=True)
        result = weighted_overall_estimate([], bot, 0, 60, seed=42)
        self.assertIn("estimates", result)
        self.assertNotIn("weighting", result)

    def test_weighting_shifts_toward_larger_population(self):
        human = self._make_classified("Product / Portfolio Work", 50)
        bot = self._make_classified("Quality / Stability / Reliability", 50,
                                    is_bot=True)
        result = weighted_overall_estimate(
            human, bot, 900, 100, seed=42
        )
        est_by_cat = {e["category"]: e for e in result["estimates"]}
        self.assertGreater(est_by_cat["Product / Portfolio Work"]["posterior_mean"],
                           est_by_cat["Quality / Stability / Reliability"]["posterior_mean"])

    def test_equal_populations_roughly_equal_weight(self):
        human = self._make_classified("Product / Portfolio Work", 50)
        bot = self._make_classified("Quality / Stability / Reliability", 50,
                                    is_bot=True)
        result = weighted_overall_estimate(
            human, bot, 500, 500, seed=42
        )
        w = result["weighting"]
        self.assertAlmostEqual(w["human_weight"], 0.5, places=2)
        self.assertAlmostEqual(w["bot_weight"], 0.5, places=2)

    def test_weights_sum_to_one(self):
        human = self._make_classified("Product / Portfolio Work", 30)
        bot = self._make_classified("Quality / Stability / Reliability", 10,
                                    is_bot=True)
        result = weighted_overall_estimate(
            human, bot, 1000, 200, seed=42
        )
        w = result["weighting"]
        self.assertAlmostEqual(w["human_weight"] + w["bot_weight"], 1.0,
                               places=4)

    def test_sample_size_is_total(self):
        human = self._make_classified("Product / Portfolio Work", 30)
        bot = self._make_classified("Quality / Stability / Reliability", 10,
                                    is_bot=True)
        result = weighted_overall_estimate(
            human, bot, 1000, 200, seed=42
        )
        self.assertEqual(result["sample_size"], 40)

    def test_ci_present_for_all_categories(self):
        human = (self._make_classified("Product / Portfolio Work", 20) +
                 self._make_classified("Incidents & Support", 10))
        bot = self._make_classified("Quality / Stability / Reliability", 15,
                                    is_bot=True)
        result = weighted_overall_estimate(
            human, bot, 500, 100, seed=42
        )
        for est in result["estimates"]:
            self.assertIn("ci_low", est)
            self.assertIn("ci_high", est)
            self.assertLessEqual(est["ci_low"], est["posterior_mean"])
            self.assertGreaterEqual(est["ci_high"], est["posterior_mean"])


if __name__ == "__main__":
    unittest.main()
