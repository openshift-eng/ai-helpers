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

    def test_url_must_be_a_complete_link_target(self):
        url = "https://sippy.example/jobs?release=4.18"
        self.assertTrue(self.kept(f"[jobs]({url}).", url))
        self.assertTrue(self.kept(f"See [the job list]({url}) and <{url}>.", url))
        self.assertFalse(self.kept(f"[jobs]({url}&page=2)", url))
        self.assertFalse(self.kept(f"See {url}&page=2 for more.", url))
        nested = "https://example.test/a(b(c)d)/old"
        self.assertTrue(self.kept(f"[run]({nested})", nested))
        self.assertFalse(self.kept(f"[run]({nested}er)", nested))

    def test_list_entry_accepts_any_alternative(self):
        result = judge("proposal_preserves_facts", proposal("Shown for 2 seconds."),
                       {"must_keep": [["two seconds", "2 seconds"]]})
        self.assertTrue(result[0], result)


def record(**fields):
    base = {"key": "TRT-1", "issue_type": "Story", "outcome": "no_change", "readiness": "ready",
            "stricter_review": {"applied": False, "reasons": []}, "rubric": None, "duplicate_of": None,
            "related": [], "proposed_links": [], "proposed_summary": None, "proposed_description": None,
            "gap_comment": None, "change_notes": None, "preservation_passed": None, "skip_reason": None}
    return {**base, **fields}


class ValidOutputTest(unittest.TestCase):
    def valid(self, **fields):
        return judge("valid_output_json", record(**fields), {})

    def test_baseline_record_is_valid(self):
        self.assertTrue(self.valid()[0], self.valid())

    def test_non_string_outcome_is_invalid_not_an_error(self):
        for outcome in ([], {}, 3, None):
            with self.subTest(outcome=outcome):
                self.assertFalse(self.valid(outcome=outcome)[0])

    def test_proposal_cannot_report_failed_preservation(self):
        self.assertFalse(self.valid(outcome="proposal", preservation_passed=False)[0])
        self.assertTrue(self.valid(outcome="proposal", preservation_passed=True)[0])
        # null: reviewed by hand because check_card.py failed.
        self.assertTrue(self.valid(outcome="proposal", preservation_passed=None)[0])

    def test_related_is_null_only_for_skipped_cards(self):
        self.assertTrue(self.valid(outcome="skipped", related=None)[0])
        for outcome in ("no_change", "proposal", "gaps_only", "duplicate", "unsupported", "blocked"):
            with self.subTest(outcome=outcome):
                self.assertFalse(self.valid(outcome=outcome, related=None)[0])
                self.assertTrue(self.valid(outcome=outcome, related=[])[0])


class LinksTest(unittest.TestCase):
    def test_links_use_jiras_related_type_name(self):
        # Jira's link type is named "Related" ("relates to"); there is no "Relates".
        def links(link_type):
            return judge("links_correct", record(outcome="no_change", related=["TRT-2"], proposed_links=[
                {"key": "TRT-2", "link_type": link_type, "rationale": "follow-up to TRT-2's alert"}]),
                {"expected_links": ["TRT-2"]})
        self.assertTrue(links("Related")[0], links("Related"))
        self.assertFalse(links("Relates")[0])


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
