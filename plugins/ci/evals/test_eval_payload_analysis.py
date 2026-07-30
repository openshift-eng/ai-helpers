#!/usr/bin/env python3

import os
import unittest

import yaml


EVAL_PATH = os.path.join(os.path.dirname(__file__), "eval-payload-analysis.yaml")


class ScoringPromptTest(unittest.TestCase):
    def test_shared_judge_uses_current_raw_rubric(self):
        with open(EVAL_PATH) as stream:
            config = yaml.safe_load(stream)
        prompt = next(
            judge["prompt"]
            for judge in config["judges"]
            if judge["name"] == "revert_scoring_accuracy"
        )

        self.assertIn("raw maximum is 120", prompt)
        self.assertNotIn("Maximum: 130", prompt)
        self.assertNotIn("Single candidate: +10", prompt)
        self.assertIn("Do not penalize a control output", prompt)


if __name__ == "__main__":
    unittest.main()
