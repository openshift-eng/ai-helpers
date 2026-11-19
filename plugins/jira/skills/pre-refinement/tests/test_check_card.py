import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "check_card.py"
SPEC = importlib.util.spec_from_file_location("check_card", SCRIPT)
check_card = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_card)

WELL_REFINED = """As a Sippy developer, I want integration tests to run in the devcontainer,
so that I can validate changes against real integration behavior.

## Acceptance Criteria

* Integration tests run in the devcontainer with one documented command.
* The run records results that another developer can reproduce.
* The setup keeps existing security controls; any extra setup is documented.

## Additional Context

Earlier failures came from a missing container socket; this is unverified.
[Example failing run](https://prow.example/run/123)
"""


def card(**overrides):
    base = {
        "key": "TRT-1001",
        "issue_type": "Story",
        "status": "New",
        "summary": "Run integration tests in the devcontainer",
        "description": WELL_REFINED,
        "labels": [],
        "creator": "someone",
    }
    base.update(overrides)
    return base


class EligibilityTest(unittest.TestCase):
    def test_new_supported_card_is_eligible(self):
        result = check_card.check(card())
        self.assertTrue(result["eligible"])
        self.assertIsNone(result["skip_reason"])

    def test_labelled_card_is_skipped(self):
        result = check_card.check(card(labels=["ai-pre-refined", "sippy"]))
        self.assertFalse(result["eligible"])
        self.assertEqual(result["skip_reason"], "already labelled ai-pre-refined")

    def test_custom_label(self):
        result = check_card.check(card(labels=["groomed"]), label="groomed")
        self.assertFalse(result["eligible"])

    def test_card_past_new_is_skipped(self):
        result = check_card.check(card(status="Refinement"))
        self.assertFalse(result["eligible"])
        self.assertIn("Refinement", result["skip_reason"])

    def test_epic_is_unsupported(self):
        result = check_card.check(card(issue_type="Epic"))
        self.assertFalse(result["eligible"])
        self.assertFalse(result["supported_type"])
        self.assertEqual(result["skip_reason"], "unsupported type: Epic")
        self.assertNotIn("description", result)

    def test_supported_types_override(self):
        result = check_card.check(card(issue_type="Bug"), supported=["Story"])
        self.assertFalse(result["supported_type"])

    def test_type_match_is_case_insensitive(self):
        self.assertTrue(check_card.check(card(issue_type="story"))["eligible"])

    def test_unknown_project_is_refused(self):
        with self.assertRaises(ValueError):
            check_card.check(card(key="OCPBUGS-1"))

    def test_missing_status_is_not_eligible(self):
        result = check_card.check(card(status=None))
        self.assertFalse(result["eligible"])
        self.assertIn("status unknown", result["skip_reason"])

    def test_override_uses_configured_type_name(self):
        result = check_card.check(card(), supported=["story"])
        self.assertTrue(result["eligible"])
        self.assertEqual(result["issue_type"], "Story")
        self.assertEqual(result["description"]["guidance"], [120, 350])

    def test_override_type_without_template_is_unsupported(self):
        result = check_card.check(card(issue_type="Epic"), supported=["Story", "Epic"])
        self.assertFalse(result["eligible"])
        self.assertFalse(result["supported_type"])

    def test_malformed_field_is_refused(self):
        for bad in ({"status": {"name": "New"}}, {"labels": "x"}, {"proposed": "x"},
                    {"proposed": {"description": 3}}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                check_card.check(card(**bad))


    def test_non_string_key_is_a_value_error(self):
        for key in (123, ["TRT-1"], {"key": "TRT-1"}):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "'key' must be a string"):
                check_card.check(card(key=key))


class StricterReviewTest(unittest.TestCase):
    def test_label_triggers(self):
        result = check_card.check(card(labels=["ai-generated-jira"]))
        self.assertEqual(result["stricter_review"], {"applied": True, "reasons": ["label"]})

    def test_creator_triggers_string_and_object(self):
        self.assertEqual(check_card.check(card(creator="ship-help-jira"))["stricter_review"]["reasons"],
                         ["creator"])
        obj = {"displayName": "Chai Bot", "name": "ship-help-jira"}
        self.assertEqual(check_card.check(card(creator=obj))["stricter_review"]["reasons"], ["creator"])

    def test_creator_matches_the_account_exactly(self):
        for other in ("ship-help-jira-sandbox", {"name": "not-ship-help-jira"}, {"displayName": "ship-help-jira"}):
            with self.subTest(creator=other):
                self.assertFalse(check_card.check(card(creator=other))["stricter_review"]["applied"])
        email = {"emailAddress": "Ship-Help-Jira@example.com"}
        self.assertTrue(check_card.check(card(creator=email))["stricter_review"]["applied"])

    def test_cloud_creator_account_id(self):
        cloud = {"accountId": "ship-help-jira", "displayName": "Chai Bot"}
        self.assertEqual(check_card.check(card(creator=cloud))["stricter_review"]["reasons"], ["creator"])
        # A real Cloud accountId is opaque; the caller passes the assistant's.
        opaque = {"accountId": "712020:5f1c-chai", "displayName": "Chai Bot"}
        self.assertFalse(check_card.check(card(creator=opaque))["stricter_review"]["applied"])
        result = check_card.check(card(creator=opaque), accounts=["712020:5f1c-chai"])
        self.assertEqual(result["stricter_review"]["reasons"], ["creator"])

    def test_both_signals(self):
        result = check_card.check(card(labels=["ai-generated-jira"], creator="ship-help-jira"))
        self.assertEqual(result["stricter_review"]["reasons"], ["label", "creator"])

    def test_ai_notice_alone_does_not_trigger(self):
        desc = WELL_REFINED + "\n_AI-generated. Review for accuracy._\n"
        result = check_card.check(card(description=desc))
        self.assertFalse(result["stricter_review"]["applied"])
        self.assertTrue(result["ai_notice_present"])

    def test_reporter_is_ignored(self):
        result = check_card.check(card(reporter="ship-help-jira"))
        self.assertFalse(result["stricter_review"]["applied"])

    def test_target_is_lower_half_only_when_strict(self):
        self.assertNotIn("target", check_card.check(card())["description"])
        strict = check_card.check(card(labels=["ai-generated-jira"]))
        self.assertEqual(strict["description"]["target"], [120, 235])


class DescriptionFactsTest(unittest.TestCase):
    def test_well_refined_card_has_no_flags(self):
        result = check_card.check(card())
        self.assertEqual(result["rubric_flags"], [])
        self.assertEqual(result["completion_lists"][0]["items"], 3)
        self.assertEqual(result["description"]["position"], "below")
        self.assertTrue(result["sections"]["Acceptance Criteria"]["heading_found"])
        self.assertTrue(result["summary"]["in_range"])

    def test_more_than_five_criteria_is_flagged(self):
        items = "\n".join(f"* Verify that outcome {i} happens." for i in range(6))
        result = check_card.check(card(description=f"Statement.\n\n## Acceptance Criteria\n\n{items}\n"))
        self.assertTrue(result["completion_lists"][0]["over_limit"])
        self.assertTrue(any(f.startswith("Criteria:") for f in result["rubric_flags"]))

    def test_nested_sub_bullets_and_jira_wiki_headings(self):
        desc = "Statement.\n\nh2. Acceptance Criteria\n# First\n## detail\n## detail\n# Second\n"
        lst = check_card.check(card(description=desc))["completion_lists"][0]
        self.assertEqual((lst["items"], lst["nested_items"]), (2, 2))

    def test_completion_headings_with_trailing_colon(self):
        items = "\n".join(f"* outcome {i}" for i in range(20))
        for heading in ("## Acceptance Criteria:", "h2. Acceptance Criteria:"):
            with self.subTest(heading=heading):
                result = check_card.check(card(description=f"As a user, I want x.\n\n{heading}\n{items}\n"))
                self.assertEqual([(lst["heading"], lst["items"]) for lst in result["completion_lists"]],
                                 [("acceptance criteria", 20)])
                self.assertTrue(any(f.startswith("Criteria:") for f in result["rubric_flags"]))
                self.assertTrue(result["sections"]["Acceptance Criteria"]["heading_found"])

    def test_second_criteria_list_is_flagged(self):
        desc = ("S.\n\n## Acceptance Criteria\n\n* a\n\n"
                "## Additional acceptance criteria (for reuse by other teams)\n\n* b\n")
        flags = check_card.check(card(description=desc))["rubric_flags"]
        self.assertIn("Criteria: more than one list of completion conditions", flags)

    def test_long_log_and_raw_url_are_flagged(self):
        log = "\n".join(f"label-{i}" for i in range(20))
        url = "https://sippy.example/api/jobs?" + "filter=" + "x" * 120
        desc = f"Problem.\n\n```\n{log}\n```\n\nSee {url}\n\n[short](https://example.com/{'y' * 120})"
        result = check_card.check(card(issue_type="Bug", description=desc))
        self.assertEqual(result["long_log_excerpts"], [20])
        self.assertEqual(result["long_raw_urls"], [url])
        self.assertEqual(sum(f.startswith("Evidence:") for f in result["rubric_flags"]), 2)

    def test_short_excerpt_is_fine(self):
        desc = "Problem.\n\n{noformat}\nline 1\nline 2\n{noformat}\n"
        self.assertEqual(check_card.check(card(issue_type="Bug", description=desc))["long_log_excerpts"], [])

    def test_over_twice_guidance(self):
        desc = "word " * 800
        result = check_card.check(card(description=desc))
        self.assertEqual(result["description"]["position"], "over_twice")
        self.assertTrue(any(f.startswith("Length:") for f in result["rubric_flags"]))

    def test_boilerplate_is_not_counted(self):
        plain = check_card.check(card())["description"]["words"]
        desc = WELL_REFINED + "\nRequested by Some One via Chai Bot in #trt\n\n_AI-generated. Review for accuracy._\n"
        result = check_card.check(card(description=desc))
        self.assertEqual(result["description"]["words"], plain)
        self.assertEqual(result["attribution_line"], "Requested by Some One via Chai Bot in #trt")

    def test_summary_range(self):
        self.assertFalse(check_card.check(card(summary="Fix it"))["summary"]["in_range"])

    def test_ticket_uses_task_sections(self):
        result = check_card.check(card(issue_type="Ticket", description="Goal: x\n\nDone when:\n* y\n"))
        self.assertIn("Done when", result["sections"])
        self.assertEqual(result["description"]["guidance"], [100, 350])

    def test_task_scope_is_conditional(self):
        result = check_card.check(card(issue_type="Task", description="Goal: x\n\nDone when:\n* y\n"))
        self.assertEqual(result["sections"]["Scope"],
                         {"required": False, "heading_found": False, "required_when": "multi-step work"})
        self.assertTrue(result["sections"]["Done when"]["required"])

    def test_spike_deliverable_counts_as_completion_list(self):
        items = "\n".join(f"* outcome {i}" for i in range(6))
        result = check_card.check(card(issue_type="Spike", description=f"Q?\n\n## Deliverable\n{items}\n"))
        self.assertTrue(any(f.startswith("Criteria:") for f in result["rubric_flags"]))

    def test_fenced_lines_are_not_criteria_or_headings(self):
        items = "\n".join(f"* outcome {i}" for i in range(5))
        desc = f"S.\n\n## Acceptance Criteria\n{items}\n\n```\n* log line\n# not a heading\n```\n"
        result = check_card.check(card(description=desc))
        self.assertEqual([lst["items"] for lst in result["completion_lists"]], [5])


class PreservationTest(unittest.TestCase):
    ORIGINAL = (
        "Rescanning labels does not refresh the page. See TRT-77 and "
        "[the run](https://prow.example/run/9). Labels `GCPInstanceNotFound` appear after 7 days.\n\n"
        "Requested by Some One via Chai Bot in #trt\n\n_AI-generated. Review for accuracy._\n"
    )

    def compare(self, proposed_description, summary="Test details rescan does not refresh labels"):
        return check_card.check(card(issue_type="Bug", description=self.ORIGINAL,
                                     proposed={"summary": summary, "description": proposed_description}))[
            "preservation"]

    def test_faithful_proposal_passes(self):
        kept = ("Rescan does not refresh labels (TRT-77, [run](https://prow.example/run/9)): "
                "`GCPInstanceNotFound` after 7 days.\n\nRequested by Some One via Chai Bot in #trt\n")
        result = self.compare(kept)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["missing_numbers"], [])
        self.assertTrue(result["summary_words_in_range"])

    def test_dropped_link_key_identifier_and_attribution_fail(self):
        result = self.compare("Rescan does not refresh labels.\n")
        self.assertFalse(result["passed"])
        self.assertEqual(result["proposal_rubric_flags"], [])
        self.assertEqual(result["missing_links"], ["https://prow.example/run/9"])
        self.assertEqual(result["missing_issue_keys"], ["TRT-77"])
        self.assertEqual(result["missing_identifiers"], ["GCPInstanceNotFound"])
        self.assertEqual(result["missing_numbers"], ["7"])
        self.assertFalse(result["attribution_kept"])

    def test_dropped_identifiers_and_numbers_are_advisory(self):
        result = self.compare("Rescan does not refresh labels (TRT-77, [run](https://prow.example/run/9)).\n"
                              "Requested by Some One via Chai Bot in #trt\n")
        self.assertEqual(result["missing_identifiers"], ["GCPInstanceNotFound"])
        self.assertEqual(result["missing_numbers"], ["7"])
        self.assertTrue(result["passed"])

    def test_hyphenated_threshold_is_a_number(self):
        result = check_card.check(card(description="Use a 24-hour default for TRT-12 since 2026-10-02.\n",
                                       proposed={"description": "Use a 48-hour default.\n"}))
        # The issue key is not a number; the date is one value, not three.
        self.assertEqual(result["preservation"]["missing_numbers"], ["2026-10-02", "24"])

    def test_dates_signed_numbers_and_versions_are_values(self):
        cases = [
            ("Seen since 2026-10-02.", "Seen recently.", ["2026-10-02"]),
            ("Offset is -5 minutes.", "Offset is 5 minutes.", ["-5"]),
            ("Fixed in v1.2.3 of the tool.", "Fixed in the tool.", ["v1.2.3"]),
        ]
        for before, after, dropped in cases:
            with self.subTest(before=before):
                result = check_card.check(card(description=before, proposed={"description": after}))
                self.assertEqual(result["preservation"]["missing_numbers"], dropped)
        self.assertEqual(check_card.numbers("from 3-5 runs since 2026-10-02 on v1.2.3, -5% and 24-hour"),
                         ["-5%", "2026-10-02", "24", "3-5", "v1.2.3"])

    def test_changed_range_is_reported(self):
        for before, after, dropped in [("Retry within 3-5 days.", "Retry within 3-7 days.", ["3-5"]),
                                       ("Keep 1.5\u20132 GB free.", "Keep 1.5\u20133 GB free.", ["1.5\u20132"]),
                                       ("Allow 10-20% drift.", "Allow 10-25% drift.", ["10-20%"])]:
            with self.subTest(before=before):
                result = check_card.check(card(description=before, proposed={"description": after}))
                self.assertEqual(result["preservation"]["missing_numbers"], dropped)
        # Issue keys and list ordinals are still not numbers.
        self.assertEqual(check_card.numbers("TRT-3046 and OCPBUGS-12\n1. first\n2. second"), [])

    def test_link_destination_with_parentheses_is_compared_whole(self):
        before = "[run](https://example.test/a(v1)/old)\n"
        changed = check_card.check(card(description=before,
                                        proposed={"description": "[run](https://example.test/a(v1)/new)\n"}))
        self.assertEqual(changed["preservation"]["missing_links"], ["https://example.test/a(v1)/old"])
        caption = check_card.check(card(description=before,
                                        proposed={"description": "[the run](https://example.test/a(v1)/old)\n"}))
        self.assertEqual(caption["preservation"]["missing_links"], [])

    def test_link_destination_with_nested_parentheses_is_compared_whole(self):
        before = "[run](https://example.test/a(b(c)d)/old)\n"
        changed = check_card.check(card(description=before,
                                        proposed={"description": "[run](https://example.test/a(b(c)d)/new)\n"}))
        self.assertEqual(changed["preservation"]["missing_links"], ["https://example.test/a(b(c)d)/old"])
        caption = check_card.check(card(description=before,
                                        proposed={"description": "[the run](https://example.test/a(b(c)d)/old)\n"}))
        self.assertEqual(caption["preservation"]["missing_links"], [])
        self.assertEqual(check_card.raw_urls(before), [])

    def test_attribution_must_be_the_last_line(self):
        moved = ("Requested by Some One via Chai Bot in #trt\n\nRescan does not refresh labels "
                 "(TRT-77, [run](https://prow.example/run/9)).\n")
        result = self.compare(moved)
        self.assertFalse(result["attribution_kept"])
        self.assertFalse(result["passed"])

    def test_list_ordinals_are_not_numbers(self):
        result = check_card.check(card(description="S.\n\n## Acceptance Criteria\n1. a in 30 days\n2. b\n",
                                       proposed={"description": "S.\n\n## Acceptance Criteria\n* a in 30 days\n* b\n"}))
        self.assertEqual(result["preservation"]["missing_numbers"], [])

    def test_proposal_flags_describe_the_proposal(self):
        items = "\n".join(f"* outcome {i}" for i in range(6))
        result = check_card.check(card(proposed={"description": f"S.\n\n## Acceptance Criteria\n{items}\n"}))
        self.assertEqual(result["rubric_flags"], [])
        self.assertTrue(any(f.startswith("Criteria:") for f in result["preservation"]["proposal_rubric_flags"]))

    def test_link_text_may_change(self):
        result = self.compare("TRT-77 [example failing run](https://prow.example/run/9) "
                              "`GCPInstanceNotFound` 7\nRequested by Some One via Chai Bot in #trt\n")
        self.assertEqual(result["missing_links"], [])

    def test_ai_notice_must_be_dropped(self):
        result = self.compare(self.ORIGINAL)
        self.assertFalse(result["ai_notice_ok"])
        self.assertFalse(result["passed"])

    def test_summary_only_proposal_leaves_the_stored_notice_alone(self):
        for stored in (False, True):
            with self.subTest(stored=stored):
                result = check_card.check(card(issue_type="Bug", description=self.ORIGINAL,
                                               proposed={"summary": "Rescan leaves stale labels on GCP runs"}),
                                          stored=stored)["preservation"]
                self.assertTrue(result["ai_notice_ok"])
                self.assertIsNone(result["attribution_kept"])
                self.assertTrue(result["passed"], result)

    DRAFT = ("Rescan does not refresh labels (TRT-77, [run](https://prow.example/run/9)): "
             "`GCPInstanceNotFound` after 7 days.\n\nRequested by Some One via Chai Bot in #trt\n")

    def stored(self, text):
        return check_card.check(card(issue_type="Bug", description=self.ORIGINAL,
                                     proposed={"description": text}), stored=True)["preservation"]

    def test_final_stored_text_ends_with_one_tool_added_notice(self):
        # Exactly what each write path stores for a passing draft: the
        # Atlassian MCP path appends the notice line; chai-bot's writer adds a
        # rule and the italic notice after the attribution.
        for footer in ("\n_AI-generated. Review for accuracy._\n", "\n---\n*AI-generated. Review for accuracy.*\n"):
            final = self.DRAFT + footer
            with self.subTest(footer=footer):
                result = self.stored(final)
                self.assertTrue(result["passed"], result)
                self.assertTrue(result["attribution_kept"])
                self.assertTrue(result["ai_notice_ok"])
                # The same text is not a valid draft: drafts carry no notice.
                self.assertFalse(self.compare(final)["passed"])

    def test_final_stored_text_rejects_a_misplaced_or_repeated_notice(self):
        notice = "_AI-generated. Review for accuracy._"
        before_attribution = self.DRAFT.replace("Requested by", f"{notice}\n\nRequested by")
        twice = self.DRAFT + f"\n{notice}\n\n{notice}\n"
        cases = (("before the attribution", before_attribution), ("twice", twice),
                 ("missing", self.DRAFT), ("inside a line", self.DRAFT + f"\nSee {notice}\n"))
        for name, text in cases:
            with self.subTest(name):
                self.assertFalse(self.stored(text)["passed"])

    def test_final_stored_text_without_attribution_ends_with_the_notice(self):
        original = "Rescan does not refresh labels after 7 days (TRT-77).\n"
        result = check_card.check(card(issue_type="Bug", description=original,
                                       proposed={"description": original + "\n---\n*AI-generated. Review for accuracy.*\n"}),
                                  stored=True)["preservation"]
        self.assertIsNone(result["attribution_kept"])
        self.assertTrue(result["passed"], result)

    def test_criteria_over_limit_and_word_reduction(self):
        items = "\n".join(f"* outcome {i}" for i in range(6))
        result = check_card.check(card(proposed={"description": f"S.\n\n## Acceptance Criteria\n{items}\n"}))[
            "preservation"]
        self.assertTrue(result["completion_over_limit"])
        self.assertGreater(result["words"]["reduction_pct"], 0)

    def test_summary_only_proposal_keeps_description(self):
        result = check_card.check(card(proposed={"summary": "Run Sippy integration tests in the devcontainer"}))[
            "preservation"]
        self.assertTrue(result["passed"])
        self.assertEqual(result["words"]["reduction_pct"], 0)

    def test_no_attribution_means_nothing_to_keep(self):
        result = check_card.check(card(proposed={"description": WELL_REFINED}))["preservation"]
        self.assertIsNone(result["attribution_kept"])


class CliTest(unittest.TestCase):
    def run_cli(self, payload, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], input=payload,
                              capture_output=True, text=True)

    def test_cli_round_trip(self):
        proc = self.run_cli(json.dumps(card()), "--supported-types", "Story, Bug")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["eligible"])

    def test_cli_bad_input(self):
        proc = self.run_cli("not json")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("error", json.loads(proc.stdout))
        self.assertEqual(self.run_cli("[]").returncode, 1)
        proc = self.run_cli(json.dumps(card(status={"name": "New"})))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("status", json.loads(proc.stdout)["error"])

    def test_cli_malformed_key(self):
        for key in (123, ["TRT-1"]):
            with self.subTest(key=key):
                proc = self.run_cli(json.dumps(card(key=key)))
                self.assertEqual(proc.returncode, 1, proc.stderr)
                self.assertEqual(proc.stderr, "")
                self.assertIn("'key' must be a string", json.loads(proc.stdout)["error"])

    def test_cli_stored_text_and_assistant_account(self):
        original = "Labels stay stale after 7 days.\n\nRequested by Some One via Chai Bot in #trt\n"
        final = original + "\n_AI-generated. Review for accuracy._\n"
        payload = json.dumps(card(description=original, creator={"accountId": "712020:chai"},
                                  proposed={"description": final}))
        out = json.loads(self.run_cli(payload, "--stored", "--assistant-account", "712020:chai").stdout)
        self.assertTrue(out["preservation"]["passed"], out["preservation"])
        self.assertEqual(out["stricter_review"]["reasons"], ["creator"])
        self.assertFalse(json.loads(self.run_cli(payload).stdout)["preservation"]["passed"])


if __name__ == "__main__":
    unittest.main()
