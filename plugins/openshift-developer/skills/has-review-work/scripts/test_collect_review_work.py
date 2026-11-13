#!/usr/bin/env python3
"""Regression tests for the snapshot consumed by the has-review-work skill."""

import contextlib
import io
import json
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from collect_review_work import (
    Authorizer, GH_TIMEOUT, THREAD_QUERY, ci_decision, collect_candidates, collect_snapshot,
    fetch_threads, main, paginated_items, run_gh,
)
import label_checks as label_checks_cli
from label_checks import label_checks

HEAD = "a" * 40
FAILURE = {"name": "ci/prow/check with spaces | punctuation", "state": "FAILURE", "bucket": "fail", "link": ""}
REBASE: dict[str, str] = {"name": "label/needs-rebase", "state": "LABEL", "bucket": "rebase", "link": ""}


def comment(identifier, body="Please change this", login="reviewer", time="2026-10-02T13:00:00Z", **extra):
    return {"id": identifier, "body": body, "user": {"login": login}, "created_at": time, **extra}


def thread(identifier, resolved=False):
    return {"id": f"PRRT_{identifier}", "isResolved": resolved}


class CandidateTests(unittest.TestCase):
    def collect(self, inline=(), reviews=(), conversation=(), threads=None, authorize=None):
        return collect_candidates(
            list(inline), list(reviews), list(conversation), threads or {},
            "review-agent[bot]", authorize or (lambda login: login == "reviewer"),
        )

    def test_unanswered_inline_is_work_evidence_on_first_poll(self):
        # Earlier bot replies on unrelated threads must not hide fresh comments.
        body = "Use Go types | then marshal them.\nKeep whitespace and `quotes`."
        inline = [
            comment(1, line=10), comment(2, login="review-agent[bot]", in_reply_to_id=1, time="2026-10-02T13:30:00Z"),
            comment(3, body, time="2026-10-02T13:51:00Z", path="test.go", line=None, original_line=30),
            comment(4, "same for these", time="2026-10-02T13:53:00Z", path="other_test.go", line=40),
        ]
        candidates, skipped = self.collect(inline, threads={n: thread(n) for n in (1, 3, 4)})
        self.assertEqual([c["id"] for c in candidates], [3, 4])
        self.assertEqual(candidates[0]["body"], body)
        self.assertEqual(candidates[0]["type"], "review_comment")
        self.assertEqual(candidates[0]["thread_id"], "PRRT_3")
        self.assertEqual(candidates[0]["original_line"], 30)
        self.assertEqual(skipped["replied"], 1)

    def test_human_followup_in_answered_thread_remains_eligible(self):
        inline = [
            comment(1, line=10),
            comment(2, login="review-agent[bot]", in_reply_to_id=1, time="2026-10-02T13:30:00Z"),
            comment(3, "This still needs a change", in_reply_to_id=1, time="2026-10-02T14:00:00Z", line=20),
        ]
        candidates, _ = self.collect(inline, threads={1: thread(1)})
        self.assertEqual([c["id"] for c in candidates], [3])

    def test_shared_bot_matcher_keeps_other_automated_reviewers(self):
        conversation = [
            comment(1, "Done.", login="Review-Agent"),
            comment(2, "Please change this", login="coderabbitai[bot]"),
        ]

        candidates, skipped = self.collect(
            conversation=conversation, authorize=lambda _login: True,
        )

        self.assertEqual([candidate["id"] for candidate in candidates], [2])
        self.assertEqual(skipped["bot"], 1)

    def test_resolved_comments_are_skipped_before_authorization(self):
        authorize = Mock()
        candidates, skipped = self.collect([comment(1, line=10)], threads={1: thread(1, True)}, authorize=authorize)
        self.assertEqual(candidates, [])
        self.assertEqual(skipped["resolved"], 1)
        authorize.assert_not_called()

    def test_missing_thread_is_an_error_instead_of_idle(self):
        with self.assertRaisesRegex(RuntimeError, "missing"):
            self.collect([comment(1, line=10)])

    def test_commands_bots_unauthorized_and_review_states_are_filtered(self):
        authorize = Mock(return_value=False)
        reviews = [comment(4, "", state="APPROVED"), comment(5, state="PENDING")]
        conversation = [
            comment(1, "<!-- hidden -->\n/hold\n/test check"),
            comment(2, login="openshift-ci[bot]"),
            comment(3, login="stranger"),
        ]
        candidates, skipped = self.collect(reviews=reviews, conversation=conversation, authorize=authorize)
        self.assertEqual(candidates, [])
        self.assertEqual(skipped["review_state"], 2)
        authorize.assert_called_once_with("stranger")

    def test_body_size_limit_matches_worker_for_all_comment_types(self):
        inline = [
            comment(1, "i" * 5001, line=10),
            comment(2, "i" * 5000, login="coderabbitai[bot]", line=11),
        ]
        reviews = [
            dict(comment(3, "r" * 5001), submitted_at="2026-10-02T13:00:00Z", state="COMMENTED"),
            dict(
                comment(4, "r" * 5000, login="coderabbitai[bot]"),
                submitted_at="2026-10-02T13:00:00Z", state="COMMENTED",
            ),
        ]
        conversation = [comment(5, "c" * 5001), comment(6, "Please update the test")]

        candidates, skipped = self.collect(
            inline, reviews, conversation,
            threads={1: thread(1), 2: thread(2)},
            authorize=lambda _login: True,
        )

        self.assertEqual([candidate["id"] for candidate in candidates], [2, 4, 6])
        self.assertEqual([len(candidate["body"]) for candidate in candidates], [5000, 5000, 22])
        self.assertEqual(skipped["oversized"], 3)

    def test_only_truly_orphaned_inline_comment_is_filtered(self):
        inline = [
            comment(1, "Detached from the diff", line=None, original_line=None),
            comment(2, "Still applies to the old hunk", line=None, original_line=30),
        ]

        candidates, skipped = self.collect(inline, threads={2: thread(2)})

        self.assertEqual([candidate["id"] for candidate in candidates], [2])
        self.assertIsNone(candidates[0]["line"])
        self.assertEqual(candidates[0]["original_line"], 30)
        self.assertEqual(skipped["orphaned"], 1)

    def test_acknowledgments_and_mixed_prose_are_left_for_model(self):
        candidates, _ = self.collect(conversation=[comment(1, "Thanks!"), comment(2, "Please fix this.\n/lgtm")])
        self.assertEqual([c["body"] for c in candidates], ["Thanks!", "Please fix this.\n/lgtm"])

    def test_conversation_reply_timing_and_review_types(self):
        reviews = [dict(comment(9), submitted_at="2026-10-02T14:00:00Z", state="COMMENTED")]
        conversation = [
            comment(1), comment(2, login="review-agent", time="2026-10-02T13:30:00Z"),
            comment(3, time="2026-10-02T14:00:00Z"),
        ]
        candidates, _ = self.collect(reviews=reviews, conversation=conversation)
        self.assertEqual([(c["type"], c["id"]) for c in candidates], [("review", 9), ("issue_comment", 3)])

    def test_later_inline_reply_suppresses_stale_review(self):
        reviews = [
            dict(comment(5571697371), submitted_at="2026-10-19T12:43:14Z", state="COMMENTED"),
        ]
        inline = [
            comment(1, time="2026-10-19T12:40:00Z", line=10),
            comment(2, login="review-agent", in_reply_to_id=1, time="2026-10-19T13:00:00Z"),
        ]

        candidates, skipped = self.collect(inline=inline, reviews=reviews, threads={1: thread(1)})

        self.assertEqual(candidates, [])
        self.assertEqual(skipped["replied"], 2)

    def test_equal_second_reply_does_not_suppress_review(self):
        reviews = [
            dict(comment(9), submitted_at="2026-10-19T14:00:00Z", state="COMMENTED"),
        ]
        conversation = [
            comment(10, "Done.", login="review-agent", time="2026-10-19T14:00:00Z"),
        ]

        candidates, _ = self.collect(reviews=reviews, conversation=conversation)

        self.assertEqual([(c["type"], c["id"]) for c in candidates], [("review", 9)])

    def test_review_after_latest_bot_reply_remains_candidate(self):
        reviews = [
            dict(comment(5572473354), submitted_at="2026-10-19T13:45:25Z", state="COMMENTED"),
        ]
        inline = [
            comment(1, time="2026-10-19T12:40:00Z", line=10),
            comment(2, login="review-agent", in_reply_to_id=1, time="2026-10-19T13:00:00Z"),
        ]

        candidates, _ = self.collect(inline=inline, reviews=reviews, threads={1: thread(1)})

        self.assertEqual([(c["type"], c["id"]) for c in candidates], [("review", 5572473354)])

    def test_legacy_signature_counts_as_reply(self):
        candidates, _ = self.collect(
            [
                comment(1, line=10),
                comment(
                    2, "*AI-assisted response via Claude Code*", login="other-agent",
                    in_reply_to_id=1, time="2026-10-02T13:01:00Z",
                ),
            ],
            threads={1: thread(1)},
        )
        self.assertEqual(candidates, [])


class CiTests(unittest.TestCase):
    def test_empty_ci_is_explicit_no_with_or_without_previous_failures(self):
        self.assertEqual(ci_decision([], HEAD, {}), "no")
        self.assertEqual(ci_decision([], HEAD, {"previous_head_ref_oid": HEAD, "previous_failing_checks": [FAILURE]}), "no")

    def test_new_head_or_changed_names_reopens_ci(self):
        prior = {"previous_head_ref_oid": HEAD, "previous_failing_checks": [FAILURE]}
        self.assertEqual(ci_decision([FAILURE], HEAD, prior), "no")
        self.assertEqual(ci_decision([FAILURE], "b" * 40, prior), "yes")
        self.assertEqual(ci_decision([FAILURE], HEAD, {}), "yes")
        self.assertEqual(ci_decision([FAILURE], HEAD, {**prior, "previous_failing_checks": []}), "yes")

    def test_new_run_of_same_check_on_same_head_reopens_ci(self):
        first = {**FAILURE, "link": "https://prow.ci.openshift.org/view/gs/bucket/pr-logs/pull/org_repo/184/job/1"}
        retest = {**first, "link": first["link"][:-1] + "2"}
        prior = {"previous_head_ref_oid": HEAD, "previous_failing_checks": [first]}
        self.assertEqual(ci_decision([first], HEAD, prior), "no")
        self.assertEqual(ci_decision([retest], HEAD, prior), "yes")

    def test_previous_checks_without_a_link_match_empty_link(self):
        prior = {"previous_head_ref_oid": HEAD, "previous_failing_checks": [{k: v for k, v in FAILURE.items() if k != "link"}]}
        self.assertEqual(ci_decision([FAILURE], HEAD, prior), "no")

    def test_rebase_label_is_ci_work_once_per_head(self):
        prior = {"previous_head_ref_oid": HEAD, "previous_failing_checks": [REBASE]}
        self.assertEqual(ci_decision([REBASE], HEAD, {}), "yes")
        self.assertEqual(ci_decision([REBASE], HEAD, prior), "no")
        self.assertEqual(ci_decision([REBASE], "b" * 40, prior), "yes")
        self.assertEqual(ci_decision([FAILURE, REBASE], HEAD, prior), "yes")


class LabelTests(unittest.TestCase):
    def test_only_mapped_labels_become_checks(self):
        self.assertEqual(label_checks([]), [])
        self.assertEqual(label_checks([{"name": "lgtm"}, {"name": "needs-rebase"}]), [REBASE])

    def test_label_checks_are_copies(self):
        label_checks([{"name": "needs-rebase"}])[0]["link"] = "mutated"
        self.assertEqual(label_checks([{"name": "needs-rebase"}]), [REBASE])

    def run_cli(self, stdin):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "stdin", io.StringIO(stdin)), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = label_checks_cli.main()
        return code, stdout.getvalue(), stderr.getvalue()

    def test_cli_maps_gh_pr_view_labels(self):
        code, stdout, _ = self.run_cli(json.dumps({"labels": [{"name": "needs-rebase"}, {"name": "lgtm"}]}))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout), [REBASE])
        code, stdout, _ = self.run_cli(json.dumps({"labels": []}))
        self.assertEqual((code, json.loads(stdout)), (0, []))

    def test_cli_rejects_invalid_input_without_output(self):
        for stdin in ("", "not json", "[]", json.dumps({"labels": [{"id": 1}]}), json.dumps({})):
            code, stdout, stderr = self.run_cli(stdin)
            self.assertEqual((code, stdout), (1, ""), stdin)
            self.assertIn("cannot map PR labels", stderr)


class ApiTests(unittest.TestCase):
    @patch("collect_review_work.subprocess.run")
    def test_nonzero_checks_exit_with_json_is_accepted(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, json.dumps([FAILURE]), "checks failed")
        self.assertEqual(run_gh(["pr", "checks"], allow_failure_json=True), [FAILURE])
        self.assertEqual(run.call_args.kwargs["timeout"], GH_TIMEOUT)
        with self.assertRaises(RuntimeError):
            run_gh(["api", "anything"])
        run.return_value.stdout = ""
        self.assertEqual(run_gh(["pr", "checks"], allow_failure_json=True), [])
        run.return_value.stdout = "no checks reported on the 'case-001' branch\n"
        self.assertEqual(run_gh(["pr", "checks"], allow_failure_json=True), [])
        run.return_value.returncode = 0
        run.return_value.stdout = "not json"
        with self.assertRaisesRegex(RuntimeError, "valid JSON"):
            run_gh(["api", "anything"])

    @patch("collect_review_work.run_gh", return_value=[[{"id": 1}], [{"id": 2}]])
    def test_rest_pages_are_flattened(self, run):
        self.assertEqual(paginated_items("endpoint", run), [{"id": 1}, {"id": 2}])
        self.assertIn("--paginate", run.call_args.args[0])
        self.assertIn("--slurp", run.call_args.args[0])

    @patch("collect_review_work.run_gh")
    def test_all_thread_pages_map_rest_roots_without_nested_pagination(self, run):
        def page(identifier):
            node = {**thread(identifier), "comments": {"nodes": [{"databaseId": identifier}]}}
            return {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [node]}}}}}
        run.return_value = [page(1), page(101)]
        self.assertEqual(set(fetch_threads("org", "repo", 184)), {1, 101})
        self.assertIn("after:$endCursor", THREAD_QUERY)
        self.assertIn("pageInfo { hasNextPage endCursor }", THREAD_QUERY)
        self.assertIn("comments(first:1)", THREAD_QUERY)

    @patch("collect_review_work.run_gh", return_value=[{"errors": [{"message": "unavailable"}]}])
    def test_graphql_errors_are_not_empty_threads(self, _run):
        with self.assertRaises(RuntimeError):
            fetch_threads("org", "repo", 184)

    @patch("collect_review_work.check_authorized.is_org_member", return_value=True)
    @patch("collect_review_work.check_authorized.get_authorized_users", return_value={"Reviewer"})
    def test_authorization_policy_is_cached(self, owners, member):
        authorize = Authorizer("org", "repo")
        self.assertTrue(authorize("reviewer"))
        self.assertTrue(authorize("reviewer"))
        self.assertTrue(authorize("member"))
        self.assertTrue(authorize("member"))
        self.assertTrue(authorize("coderabbitai[bot]"))
        self.assertTrue(authorize("redhat-chai-bot"))
        self.assertFalse(authorize("unapproved[bot]"))
        owners.assert_called_once_with("org", "repo")
        member.assert_called_once_with("org", "member")


class SnapshotTests(unittest.TestCase):
    @patch("collect_review_work.fetch_threads", return_value={})
    @patch("collect_review_work.paginated_items", return_value=[])
    @patch("collect_review_work.run_gh")
    def test_snapshot_has_explicit_no_and_preserves_json_checks(self, run, items, _threads):
        run.side_effect = [{"number": 184, "headRefOid": HEAD, "labels": []}, [FAILURE], {"headRefOid": HEAD}]
        snapshot = collect_snapshot("org/repo", 184, {"agent_login": "review-agent[bot]"})
        self.assertEqual(snapshot["comment_candidates"], [])
        self.assertEqual(snapshot["ci_work"], "yes")
        self.assertEqual(snapshot["failing_checks"], [FAILURE])
        self.assertEqual(items.call_count, 3)

    @patch("collect_review_work.fetch_threads", return_value={})
    @patch("collect_review_work.paginated_items", return_value=[])
    @patch("collect_review_work.run_gh")
    def test_no_checks_is_ci_work_no(self, run, _items, _threads):
        run.side_effect = [{"number": 184, "headRefOid": HEAD, "labels": []}, [], {"headRefOid": HEAD}]
        snapshot = collect_snapshot("org/repo", 184, {"agent_login": "review-agent[bot]"})
        self.assertEqual(snapshot["ci_work"], "no")
        self.assertEqual(snapshot["failing_checks"], [])

    @patch("collect_review_work.fetch_threads", return_value={})
    @patch("collect_review_work.paginated_items", return_value=[])
    @patch("collect_review_work.run_gh")
    def test_head_change_invalidates_snapshot(self, run, _items, _threads):
        run.side_effect = [{"number": 184, "headRefOid": HEAD, "labels": []}, [], {"headRefOid": "b" * 40}]
        with self.assertRaisesRegex(RuntimeError, "head changed"):
            collect_snapshot("org/repo", 184, {"agent_login": "review-agent[bot]"})

    @patch("collect_review_work.fetch_threads", return_value={})
    @patch("collect_review_work.paginated_items", return_value=[])
    @patch("collect_review_work.run_gh")
    def test_needs_rebase_label_is_reported_as_failing_check(self, run, _items, _threads):
        run.side_effect = [
            {"number": 184, "headRefOid": HEAD, "labels": [{"name": "needs-rebase"}]}, [], {"headRefOid": HEAD},
        ]
        snapshot = collect_snapshot("org/repo", 184, {"agent_login": "review-agent[bot]"})
        self.assertEqual(snapshot["ci_work"], "yes")
        self.assertEqual(snapshot["failing_checks"], [REBASE])
        self.assertIn("number,headRefOid,labels", run.call_args_list[0].args[0])

    @patch("collect_review_work.fetch_threads", return_value={})
    @patch("collect_review_work.paginated_items", return_value=[])
    @patch("collect_review_work.run_gh")
    def test_invalid_labels_are_rejected(self, run, _items, _threads):
        run.side_effect = [{"number": 184, "headRefOid": HEAD, "labels": [{"id": 1}]}]
        with self.assertRaisesRegex(ValueError, "labels"):
            collect_snapshot("org/repo", 184, {"agent_login": "review-agent[bot]"})

    @patch("collect_review_work.collect_snapshot", side_effect=RuntimeError("API unavailable"))
    def test_failed_collection_emits_no_success_json(self, _collect):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["collect", "--pr", "184", "--repo", "org/repo"]), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(main(), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("API unavailable", stderr.getvalue())

    @patch("collect_review_work.collect_snapshot", return_value={"ci_work": "no", "failing_checks": []})
    def test_context_heredoc_keeps_check_names_as_json(self, collect):
        context = {"agent_login": "review-agent[bot]", "previous_failing_checks": [FAILURE], "previous_head_ref_oid": HEAD}
        with patch.object(sys, "argv", ["collect", "--pr", "184", "--repo", "org/repo", "--context-stdin"]), patch.object(sys, "stdin", io.StringIO(json.dumps(context))), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(), 0)
        collect.assert_called_once_with("org/repo", 184, context)


if __name__ == "__main__":
    unittest.main()
