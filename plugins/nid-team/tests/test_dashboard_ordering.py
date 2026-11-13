"""Verify repeatable ordering through the same paginated API used by the helper."""

import contextlib
import copy
import datetime
import importlib.util
import io
import itertools
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pr-dashboard/order-open-prs.py"
spec = importlib.util.spec_from_file_location("dashboard_order", SCRIPT)
ordering = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ordering)


def item(number, **overrides):
    created = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    created += datetime.timedelta(minutes=number)
    result = {
        "id": f"ITEM_{number}", "createdAt": created.isoformat(), "isArchived": False,
        "content": {"__typename": "PullRequest", "state": "OPEN", "number": number,
                    "url": f"https://github.com/example/router/pull/{number}",
                    "repository": {"nameWithOwner": "example/router"}},
        "fields": {"Area": "Router", "Primary Reviewer": "Reviewer", "Priority": "High"},
    }
    result.update(overrides)
    return result


class FakeGitHub:
    def __init__(self, items, fail_moves=False):
        self.items = copy.deepcopy(items)
        self.moves = []
        self.pages = []
        self.fail_moves = fail_moves

    def __call__(self, query, **variables):
        if query == ordering.ITEMS_QUERY:
            offset = int(variables["after"] or 0)
            self.pages.append(offset)
            nodes = self.items[offset:offset + 100]
            more = offset + 100 < len(self.items)
            return {"node": {"items": {"nodes": copy.deepcopy(nodes), "pageInfo": {
                "hasNextPage": more, "endCursor": str(offset + 100) if more else None}}}}
        if query != ordering.MOVE_MUTATION:
            raise AssertionError("Unexpected mutation")
        if self.fail_moves:
            raise subprocess.CalledProcessError(1, ["gh"], stderr="permission denied")
        moving = next(i for i in self.items if i["id"] == variables["item"])
        self.items.remove(moving)
        position = 0 if variables["after"] is None else next(
            n + 1 for n, i in enumerate(self.items) if i["id"] == variables["after"])
        self.items.insert(position, moving)
        self.moves.append(variables)
        return {"updateProjectV2ItemPosition": {"clientMutationId": None}}


class DashboardOrderingTest(unittest.TestCase):
    def run_ordering(self, github, dry_run=False):
        with patch.object(ordering, "graphql", github), contextlib.redirect_stdout(io.StringIO()):
            return ordering.order_project("PROJECT", dry_run)

    def test_recent_pr_beyond_first_page_is_promoted_and_repeat_is_a_noop(self):
        original = [item(n) for n in range(1, 136)] + [item(888)]
        github = FakeGitHub(original)
        self.run_ordering(github)
        self.assertIn(100, github.pages)
        self.assertEqual(github.items[0]["content"]["number"], 888)
        self.assertEqual([i["content"]["number"] for i in github.items],
                         [888] + list(range(135, 0, -1)))
        self.assertEqual({i["id"]: i for i in github.items},
                         {i["id"]: i for i in original})
        prior_moves = len(github.moves)
        self.assertEqual(self.run_ordering(github), 0)
        self.assertEqual(len(github.moves), prior_moves)

    def test_only_new_addition_needs_to_move_on_a_later_sync(self):
        github = FakeGitHub([item(n) for n in range(70, 0, -1)] + [item(888)])
        self.assertEqual(self.run_ordering(github), 1)
        self.assertEqual(github.moves[0]["item"], "ITEM_888")
        self.assertIsNone(github.moves[0]["after"])

    def test_single_misplaced_old_item_does_not_rewrite_the_whole_order(self):
        github = FakeGitHub([item(1)] + [item(n) for n in range(70, 1, -1)])
        self.assertEqual(self.run_ordering(github), 1)
        self.assertEqual(github.moves[0]["item"], "ITEM_1")

    def test_equal_timestamps_preserve_existing_relative_order(self):
        github = FakeGitHub([item(2, createdAt="2026-01-01T00:00:00Z"),
                             item(1, createdAt="2026-01-01T00:00:00Z")])
        self.assertEqual(self.run_ordering(github), 0)

    def test_closed_archived_issues_and_inaccessible_content_are_untouched(self):
        closed = item(900)
        closed["content"]["state"] = "CLOSED"
        merged = item(901)
        merged["content"]["state"] = "MERGED"
        issue = item(902)
        issue["content"]["__typename"] = "Issue"
        untouched = [closed, merged, issue, item(903, isArchived=True), item(904, content=None)]
        github = FakeGitHub([item(1)] + untouched + [item(888)])
        self.run_ordering(github)
        self.assertTrue(all(move["item"] not in {i["id"] for i in untouched}
                            for move in github.moves))
        self.assertEqual([i for i in github.items if i in untouched], untouched)

    def test_dry_run_does_not_make_mutations(self):
        github = FakeGitHub([item(1), item(888)])
        self.assertGreater(self.run_ordering(github, dry_run=True), 0)
        self.assertEqual(github.moves, [])
        self.assertEqual([i["id"] for i in github.items], ["ITEM_1", "ITEM_888"])

    def test_graphql_errors_are_not_treated_as_empty_success(self):
        result = subprocess.CompletedProcess([], 0, json.dumps({"errors": [{"message": "denied"}]}), "")
        with patch.object(ordering.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "denied"):
                ordering.fetch_items("PROJECT")

    def test_mutation_failure_stops_and_returns_an_error(self):
        github = FakeGitHub([item(1), item(888)], fail_moves=True)
        errors = io.StringIO()
        with patch.object(ordering, "graphql", github), patch.object(
                ordering.sys, "argv", [str(SCRIPT), "--project-id", "PROJECT"]), \
                contextlib.redirect_stderr(errors):
            self.assertEqual(ordering.main(), 1)
        self.assertIn("permission denied", errors.getvalue())

    def test_move_plan_produces_correct_order_for_arbitrary_manual_order(self):
        for numbers in itertools.permutations(range(1, 6)):
            github = FakeGitHub([item(n) for n in numbers])
            self.run_ordering(github)
            self.assertEqual([i["content"]["number"] for i in github.items], [5, 4, 3, 2, 1])


if __name__ == "__main__":
    unittest.main()
