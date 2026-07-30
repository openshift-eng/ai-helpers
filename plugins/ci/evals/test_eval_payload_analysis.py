#!/usr/bin/env python3

import os
import textwrap
import unittest

import yaml


EVAL_PATH = os.path.join(os.path.dirname(__file__), "eval-payload-analysis.yaml")


def load_judge(name):
    with open(EVAL_PATH) as stream:
        config = yaml.safe_load(stream)
    return next(judge for judge in config["judges"] if judge["name"] == name)


def load_check(name):
    judge = load_judge(name)
    namespace = {}
    exec(
        "def check(outputs):\n" + textwrap.indent(judge["check"], "    "),
        namespace,
    )
    return namespace["check"]


class CaseConstraintsTest(unittest.TestCase):
    def setUp(self):
        self.check = load_check("case_constraints")
        self.annotations = {
            "has_revert_candidates": True,
            "expected_candidates": [
                {
                    "pr_url": "https://github.com/openshift/example/pull/42",
                    "min_confidence": 85,
                    "expected_confidence": 95,
                }
            ],
        }

    def outputs(self, revert_eligible):
        results = {
            "candidates": [
                {
                    "pr_url": "https://github.com/openshift/example/pull/42",
                    "confidence_score": 95,
                    "revert_eligible": revert_eligible,
                }
            ]
        }
        return {
            "annotations": self.annotations,
            "files": {"payload-results-test.yaml": yaml.safe_dump(results)},
            "modified_files": {},
        }

    def test_expected_revert_must_remain_actionable(self):
        passed, message = self.check(self.outputs(revert_eligible=False))

        self.assertFalse(passed)
        self.assertIn("was not marked revert_eligible", message)

    def test_expected_actionable_revert_passes(self):
        passed, message = self.check(self.outputs(revert_eligible=True))

        self.assertTrue(passed, message)


class ScoringPromptTest(unittest.TestCase):
    def test_shared_judge_uses_current_raw_rubric(self):
        prompt = load_judge("revert_scoring_accuracy")["prompt"]

        self.assertIn("raw maximum is 120", prompt)
        self.assertNotIn("Maximum: 130", prompt)
        self.assertNotIn("Single candidate: +10", prompt)
        self.assertIn("Do not penalize a control output", prompt)


if __name__ == "__main__":
    unittest.main()
