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
    Authorizer, THREAD_QUERY, ci_decision, collect_candidates, collect_snapshot,
    fetch_threads, main, paginated_items, run_gh,
)

HEAD = "a" * 40
FAILURE = {"name": "ci/prow/check with spaces | punctuation", "state": "FAILURE", "bucket": "fail", "link": ""}


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
            comment(1), comment(2, login="review-agent[bot]", in_reply_to_id=1, time="2026-10-02T13:30:00Z"),
            comment(3, body, time="2026-10-02T13:51:00Z", path="test.go", line=None, original_line=30),
            comment(4, "same for these", time="2026-10-02T13:53:00Z", path="other_test.go"),
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
            comment(1),
            comment(2, login="review-agent[bot]", in_reply_to_id=1, time="2026-10-02T13:30:00Z"),
            comment(3, "This still needs a change", in_reply_to_id=1, time="2026-10-02T14:00:00Z"),
        ]
        candidates, _ = self.collect(inline, threads={1: thread(1)})
        self.assertEqual([c["id"] for c in candidates], [3])

    def test_resolved_comments_are_skipped_before_authorization(self):
        authorize = Mock()
        candidates, skipped = self.collect([comment(1)], threads={1: thread(1, True)}, authorize=authorize)
        self.assertEqual(candidates, [])
        self.assertEqual(skipped["resolved"], 1)
        authorize.assert_not_called()

    def test_missing_thread_is_an_error_instead_of_idle(self):
        with self.assertRaisesRegex(RuntimeError, "missing"):
            self.collect([comment(1)])

    def test_commands_bots_unauthorized_and_review_states_are_filtered(self):
        authorize = Mock(return_value=False)
        reviews = [comment(4, state="APPROVED"), comment(5, state="PENDING")]
        conversation = [
            comment(1, "<!-- hidden -->\n/hold\n/test check"),
            comment(2, login="openshift-ci[bot]"),
            comment(3, login="stranger"),
        ]
        candidates, _ = self.collect(reviews=reviews, conversation=conversation, authorize=authorize)
        self.assertEqual(candidates, [])
        authorize.assert_called_once_with("stranger")

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

    def test_legacy_signature_counts_as_reply(self):
        candidates, _ = self.collect(
            [comment(1), comment(2, "*AI-assisted response via Claude Code*", login="other-agent", in_reply_to_id=1)],
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


class ApiTests(unittest.TestCase):
    @patch("collect_review_work.subprocess.run")
    def test_nonzero_checks_exit_with_json_is_accepted(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, json.dumps([FAILURE]), "checks failed")
        self.assertEqual(run_gh(["pr", "checks"], allow_failure_json=True), [FAILURE])
        with self.assertRaises(RuntimeError):
            run_gh(["api", "anything"])
        run.return_value.stdout = ""
        with self.assertRaisesRegex(RuntimeError, "valid JSON"):
            run_gh(["pr", "checks"], allow_failure_json=True)

    @patch("collect_review_work.run_gh", return_value=[[{"id": 1}], [{"id": 2}]])
    def test_rest_pages_are_flattened(self, run):
        self.assertEqual(paginated_items("endpoint"), [{"id": 1}, {"id": 2}])
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
        self.assertFalse(authorize("unapproved[bot]"))
        owners.assert_called_once_with("org", "repo")
        member.assert_called_once_with("org", "member")


class SnapshotTests(unittest.TestCase):
    @patch("collect_review_work.fetch_threads", return_value={})
    @patch("collect_review_work.paginated_items", return_value=[])
    @patch("collect_review_work.run_gh")
    def test_snapshot_has_explicit_no_and_preserves_json_checks(self, run, items, _threads):
        run.side_effect = [{"number": 184, "headRefOid": HEAD}, [FAILURE], {"headRefOid": HEAD}]
        snapshot = collect_snapshot("org/repo", 184, {"agent_login": "review-agent[bot]"})
        self.assertEqual(snapshot["comment_candidates"], [])
        self.assertEqual(snapshot["ci_work"], "yes")
        self.assertEqual(snapshot["failing_checks"], [FAILURE])
        self.assertEqual(items.call_count, 3)

    @patch("collect_review_work.fetch_threads", return_value={})
    @patch("collect_review_work.paginated_items", return_value=[])
    @patch("collect_review_work.run_gh")
    def test_head_change_invalidates_snapshot(self, run, _items, _threads):
        run.side_effect = [{"number": 184, "headRefOid": HEAD}, [], {"headRefOid": "b" * 40}]
        with self.assertRaisesRegex(RuntimeError, "head changed"):
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
