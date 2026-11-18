"""Regression tests for the judges in plugins/jira/evals/eval-pre-refinement.yaml.

The code judges always run. The facts_preserved LLM judge runs against
evals/judge-cases/facts_preserved.yaml only when asked, because each case is a
paid model call (about $0.05):

    PRE_REFINEMENT_LLM_JUDGE=1 AGENT_EVAL_HARNESS=/path/to/agent-eval-harness \
        python3 plugins/jira/skills/pre-refinement/tests/test_eval_judges.py

with the harness's dependencies installed and model credentials set as for an
eval run.
"""

import json
import os
import sys
import textwrap
import unittest
from pathlib import Path

import yaml

EVALS = Path(__file__).parents[3] / "evals"
EVAL = EVALS / "eval-pre-refinement.yaml"
JUDGES = {j["name"]: j["check"] for j in yaml.safe_load(EVAL.read_text())["judges"] if "check" in j}
FACT_CASES = yaml.safe_load((EVALS / "judge-cases" / "facts_preserved.yaml").read_text())["cases"]


def annotations(case):
    return yaml.safe_load((EVALS / "cases" / "pre-refinement" / case / "annotations.yaml").read_text())


def judge(name, result, annotations):
    namespace = {}
    exec("def _judge(outputs):\n" + textwrap.indent(JUDGES[name], "    "), namespace)
    return namespace["_judge"]({"files": {"result.json": json.dumps(result)}, "annotations": annotations})


def proposal(description, summary=None):
    return {"outcome": "proposal", "proposed_summary": summary, "proposed_description": description}


class MustKeepTest(unittest.TestCase):
    def kept(self, description, value):
        return judge("proposal_preserves_facts", proposal(description), {"must_keep": [value]})[0]

    def test_value_inside_a_longer_word_is_not_kept(self):
        self.assertFalse(self.kept("Supports keyboarding shortcuts.", "keyboard"))
        self.assertTrue(self.kept("Reachable with the keyboard.", "keyboard"))
        self.assertTrue(self.kept("Reachable with the Keyboard, too.", "keyboard"))

    def test_value_inside_a_longer_number_is_not_kept(self):
        self.assertFalse(self.kept("Flag after 13 failed deliveries.", "3 failed deliveries"))
        self.assertFalse(self.kept("Flag after 3 failed deliveriesx.", "3 failed deliveries"))
        self.assertTrue(self.kept("Flag after 3 failed deliveries.", "3 failed deliveries"))

    def test_urls_match_exactly_and_whole(self):
        url = "https://github.com/openshift/sippy/pull/4321"
        self.assertTrue(self.kept(f"[Sippy PR]({url})", url))
        self.assertFalse(self.kept(f"[Sippy PR]({url}0)", url))
        self.assertFalse(self.kept("[Sippy PR](https://github.com/OpenShift/sippy/pull/4321)", url))

    def test_list_entry_accepts_any_alternative(self):
        result = judge("proposal_preserves_facts", proposal("Shown for 2 seconds."),
                       {"must_keep": [["two seconds", "2 seconds"]]})
        self.assertTrue(result[0], result)


class FactCasesTest(unittest.TestCase):
    def test_number_check_on_fact_cases(self):
        # Only the facts' numbers: must_keep and the other checks don't apply.
        for fc in FACT_CASES:
            with self.subTest(fc["name"]):
                ann = {"must_keep_facts": annotations(fc["case"])["must_keep_facts"]}
                passed, why = judge("proposal_preserves_facts", proposal(fc["proposed_description"]), ann)
                self.assertEqual(passed, fc["numbers_kept"], why)

    @unittest.skipUnless(os.environ.get("PRE_REFINEMENT_LLM_JUDGE") == "1",
                         "set PRE_REFINEMENT_LLM_JUDGE=1 to run the paid LLM judge cases")
    def test_facts_preserved_judge(self):
        sys.path.insert(0, str(Path(os.environ["AGENT_EVAL_HARNESS"]) / "skills" / "eval-run" / "scripts"))
        import score
        from agent_eval.config import EvalConfig

        config = EvalConfig.from_yaml(str(EVAL))
        config.judges = [j for j in config.judges if j.name == "facts_preserved"]
        ((_, scorer, _, _, _),) = score.load_judges(config)
        for fc in FACT_CASES:
            with self.subTest(fc["name"]):
                record = {"files": {"result.json": json.dumps(proposal(fc["proposed_description"]))},
                          "annotations": annotations(fc["case"])}
                passed, rationale = score._normalize_result(scorer(outputs=record))[:2]
                self.assertEqual(passed, fc["expected"], rationale)


if __name__ == "__main__":
    unittest.main()
