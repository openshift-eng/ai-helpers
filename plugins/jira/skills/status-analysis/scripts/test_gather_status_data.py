#!/usr/bin/env python3
"""Tests for status-analysis data gathering helpers.

Covers the events_in_window assembly pipeline: timestamp normalization
and ordering, PR identity, status-only transitions, merge events, bot
filtering, author shape, and changelog pagination (with _fetch_json
replaced by a fake that mirrors Jira's oldest-first, 100-per-page
semantics).
"""

import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import gather_status_data as g


def make_gatherer(
    start: date = date(2026, 2, 1), end: date = date(2026, 2, 7)
) -> g.StatusDataGatherer:
    config = g.GatherConfig(
        project="TEST",
        jira_url="https://test.atlassian.net",
        jira_token="token",
        jira_username="user",
        github_token="token",
        output_dir=Path(tempfile.mkdtemp()),
        date_range=g.DateRange(start=start, end=end),
    )
    return g.StatusDataGatherer(config)


def synthetic_changelog(count: int) -> list:
    """Oldest-first changelog entries with unique, sortable timestamps."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "created": (base + timedelta(minutes=i)).isoformat().replace("+00:00", "Z"),
            "author": {"emailAddress": f"user{i}@example.com", "displayName": f"User {i}"},
            "items": [{"field": "status", "fromString": "A", "toString": "B"}],
        }
        for i in range(count)
    ]


class ParseIsoDatetimeTests(unittest.TestCase):
    def test_parses_offset_bearing_formats(self) -> None:
        expected = datetime(2026, 2, 1, 9, 0, tzinfo=timezone.utc)
        expected_millis = datetime(2026, 2, 1, 9, 0, 0, 500000, tzinfo=timezone.utc)
        for value, want in (
            ("2026-02-01T09:00:00Z", expected),
            ("2026-02-01T09:00:00.500+0000", expected_millis),
            ("2026-02-01T04:00:00.500-05:00", expected_millis),
        ):
            with self.subTest(value=value):
                self.assertEqual(g.parse_iso_datetime(value), want)

    def test_naive_treated_as_utc(self) -> None:
        self.assertEqual(
            g.parse_iso_datetime("2026-02-01T09:00:00"),
            datetime(2026, 2, 1, 9, 0, tzinfo=timezone.utc),
        )

    def test_missing_or_garbage_returns_none(self) -> None:
        self.assertIsNone(g.parse_iso_datetime(None))
        self.assertIsNone(g.parse_iso_datetime(""))
        self.assertIsNone(g.parse_iso_datetime("not-a-date"))


class NormalizeTimestampTests(unittest.TestCase):
    def test_normalizes_to_utc_z_suffix(self) -> None:
        self.assertEqual(
            g._normalize_timestamp("2026-02-01T04:00:00.500-05:00"),
            "2026-02-01T09:00:00.500000Z",
        )
        self.assertEqual(
            g._normalize_timestamp("2026-02-01T09:00:00"),
            "2026-02-01T09:00:00Z",
        )

    def test_unparseable_passthrough(self) -> None:
        self.assertEqual(g._normalize_timestamp("not-a-date"), "not-a-date")
        self.assertIsNone(g._normalize_timestamp(None))


class DateRangeTests(unittest.TestCase):
    def test_membership_is_utc_consistent(self) -> None:
        # 2026-02-01T23:30-05:00 is 2026-02-02T04:30 UTC.
        dt = datetime(2026, 2, 1, 23, 30, tzinfo=timezone(timedelta(hours=-5)))
        feb1 = g.DateRange(start=date(2026, 2, 1), end=date(2026, 2, 1))
        feb2 = g.DateRange(start=date(2026, 2, 2), end=date(2026, 2, 2))
        self.assertFalse(feb1.contains(dt))
        self.assertTrue(feb2.contains(dt))

    def test_naive_and_none(self) -> None:
        dr = g.DateRange(start=date(2026, 2, 1), end=date(2026, 2, 7))
        self.assertTrue(dr.contains(datetime(2026, 2, 3, 12, 0)))
        self.assertFalse(dr.contains(None))


class GithubBotDetectionTests(unittest.TestCase):
    def test_detects_bots(self) -> None:
        for login in ("coderabbitai[bot]", "openshift-merge-bot", "github-actions[bot]", "jenkins-ci"):
            with self.subTest(login=login):
                self.assertTrue(g._is_github_bot(login=login))
        self.assertTrue(g._is_github_bot(name="OpenShift Merge Robot"))
        # App bot emails carry the [bot] suffix as a token.
        self.assertTrue(
            g._is_github_bot(email="41898282+github-actions[bot]@users.noreply.github.com")
        )
        self.assertTrue(g._is_github_bot(email="merge-bot@redhat.com"))

    def test_humans_pass(self) -> None:
        # Substring safety: 'bot' inside a name or login must not flag.
        for login in ("abotkin", "octocat", "t-botkin"):
            with self.subTest(login=login):
                self.assertFalse(g._is_github_bot(login=login))
        self.assertFalse(g._is_github_bot(name="Alice Botti"))
        self.assertFalse(g._is_github_bot(email="user@redhat.com"))
        self.assertFalse(g._is_github_bot())
        # Personal privacy addresses belong to human accounts.
        for email in (
            "12345+alice@users.noreply.github.com",
            "alice@users.noreply.github.com",
        ):
            with self.subTest(email=email):
                self.assertFalse(g._is_github_bot(email=email))


class JiraBotDetectionTests(unittest.TestCase):
    def test_detects_automation_identities(self) -> None:
        for name in ("Automation for Jira", "GitHub", "Jenkins CI", "CI Bot"):
            with self.subTest(name=name):
                self.assertTrue(g._is_jira_bot(name=name))
        self.assertTrue(g._is_jira_bot(email="bot@redhat.com"))
        self.assertTrue(g._is_jira_bot(email="github@connect.atlassian.com"))

    def test_humans_pass(self) -> None:
        # Substring safety: 'Mary Abbott' contains 'bot' but no whole
        # automation token; personal GitHub privacy addresses are
        # exempt from the 'github' token.
        self.assertFalse(g._is_jira_bot(name="Mary Abbott"))
        self.assertFalse(g._is_jira_bot(name="Mary Abbott", email="mabbott@redhat.com"))
        self.assertFalse(g._is_jira_bot(email="12345+alice@users.noreply.github.com"))
        self.assertFalse(g._is_jira_bot())



class StatusSummaryScanTests(unittest.TestCase):
    def test_scan_finds_newest(self) -> None:
        changelog = [
            {"created": "2026-01-01T00:00:00Z", "items": [{"field": "status"}]},
            {"created": "2026-01-02T00:00:00Z", "items": [{"field": "Status Summary"}]},
            {"created": "2026-01-03T00:00:00Z", "items": [{"field": "labels"}]},
        ]
        self.assertEqual(
            g._scan_last_status_summary_update(changelog), "2026-01-02T00:00:00Z"
        )
        self.assertIsNone(g._scan_last_status_summary_update([]))

    def test_item_matcher(self) -> None:
        self.assertTrue(g._is_status_summary_item({"field": "Status Summary"}))
        self.assertFalse(g._is_status_summary_item({"field": "status"}))
        self.assertFalse(g._is_status_summary_item({"field": "summary"}))


class BuildEventsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gatherer = make_gatherer()
        self.date_range = self.gatherer.config.date_range

    def test_only_status_changes_are_transitions(self) -> None:
        changelog = [
            {"date": "2026-02-01T09:00:00Z", "author": "a@x.com", "author_name": "A",
             "items": [{"field": "status", "from": "To Do", "to": "In Progress"}]},
            {"date": "2026-02-01T10:00:00Z", "author": "a@x.com", "author_name": "A",
             "items": [{"field": "labels", "to": "x"}]},
            {"date": "2026-02-01T11:00:00Z", "author": "a@x.com", "author_name": "A",
             "items": [{"field": "RemoteWorkItemLink", "to": "x"}]},
            {"date": "2026-02-01T12:00:00Z", "author": "a@x.com", "author_name": "A",
             "items": [{"field": "Workflow", "to": "x"}]},
        ]
        events = self.gatherer._build_events_in_range(changelog, [], [], self.date_range)
        self.assertEqual([e["type"] for e in events], ["jira_transition"])
        # Field matching is case-insensitive ("Status" is used by some instances).
        changelog.append(
            {"date": "2026-02-01T13:00:00Z", "author": "a@x.com", "author_name": "A",
             "items": [{"field": "Status", "from": "A", "to": "B"}]}
        )
        events = self.gatherer._build_events_in_range(changelog, [], [], self.date_range)
        self.assertEqual([e["type"] for e in events], ["jira_transition", "jira_transition"])

    def test_comment_items_stripped_from_transitions(self) -> None:
        changelog = [
            {"date": "2026-02-01T09:00:00Z", "author": "a@x.com", "author_name": "A",
             "items": [{"field": "status", "to": "B"}, {"field": "comment", "to": "text"}]},
        ]
        events = self.gatherer._build_events_in_range(changelog, [], [], self.date_range)
        self.assertEqual(
            [item["field"] for item in events[0]["changes"]], ["status"]
        )

    def test_bot_and_human_comments(self) -> None:
        comments = [
            {"date": "2026-02-01T09:00:00Z", "author_name": "Human", "author_email": "h@x.com",
             "body": "real", "is_bot": False},
            {"date": "2026-02-02T09:00:00Z", "author_name": "Bot", "author_email": "b@x.com",
             "body": "auto", "is_bot": True},
        ]
        events = self.gatherer._build_events_in_range([], comments, [], self.date_range)
        self.assertEqual([e["type"] for e in events], ["jira_comment"])
        self.assertEqual(events[0]["author"], "Human")
        self.assertEqual(events[0]["author_email"], "h@x.com")

    def test_filter_comments_marks_bots_token_based(self) -> None:
        # Raw Jira comment shape. Substring matching would mark
        # 'Mary Abbott' as a bot ('bot' inside 'abbott').
        raw = [
            {"created": "2026-02-01T09:00:00.000+0000",
             "author": {"displayName": "Mary Abbott", "emailAddress": "mabbott@redhat.com"},
             "body": "human comment"},
            {"created": "2026-02-02T09:00:00.000+0000",
             "author": {"displayName": "Automation for Jira",
                        "emailAddress": "noreply@atlassian.com"},
             "body": "auto comment"},
            {"created": "2026-01-01T09:00:00.000+0000",  # out of range
             "author": {"displayName": "Mary Abbott", "emailAddress": "mabbott@redhat.com"},
             "body": "old"},
        ]
        filtered = self.gatherer._filter_comments_to_range(raw, self.date_range)
        self.assertEqual(
            [(c["author_name"], c["is_bot"]) for c in filtered],
            [("Mary Abbott", False), ("Automation for Jira", True)],
        )
        self.assertEqual(filtered[0]["body"], "human comment")

    def test_privacy_hidden_jira_author_falls_back(self) -> None:
        changelog = [
            {"date": "2026-02-01T09:00:00Z", "author": None, "author_name": None,
             "items": [{"field": "status", "to": "B"}]},
        ]
        events = self.gatherer._build_events_in_range(changelog, [], [], self.date_range)
        self.assertEqual(events[0]["author"], "Unknown")
        self.assertIsNone(events[0]["author_email"])

    def test_events_sorted_by_parsed_instants(self) -> None:
        # Lexicographic sorting would order '.500+0000' before the plain
        # 'Z' timestamp at the same second.
        changelog = [
            {"date": "2026-02-01T09:00:00.500+0000", "author": None, "author_name": "A",
             "items": [{"field": "status", "to": "B"}]},
            {"date": "2026-02-01T09:00:00Z", "author": None, "author_name": "A",
             "items": [{"field": "status", "to": "B"}]},
        ]
        events = self.gatherer._build_events_in_range(changelog, [], [], self.date_range)
        self.assertEqual(
            [e["occurred_at"] for e in events],
            ["2026-02-01T09:00:00Z", "2026-02-01T09:00:00.500000Z"],
        )

    def test_unparseable_timestamp_sorts_last(self) -> None:
        changelog = [
            {"date": "not-a-date", "author": None, "author_name": "A",
             "items": [{"field": "status", "to": "B"}]},
            {"date": "2026-02-01T09:00:00Z", "author": None, "author_name": "A",
             "items": [{"field": "status", "to": "B"}]},
        ]
        events = self.gatherer._build_events_in_range(changelog, [], [], self.date_range)
        self.assertEqual(events[-1]["occurred_at"], "not-a-date")

    def test_pr_identity_not_url_matching(self) -> None:
        # The Jira-scraped URL spelling must not affect event emission.
        pr = {
            "url": "http://github.com/org/repo/pull/123",  # not canonical
            "owner": "org", "repo": "repo", "number": 123,
            "dates": {"merged_at": None},
            "reviews_in_range": [
                {"submitted_at": "2026-02-01T10:00:00Z", "author": "human1",
                 "author_name": "Human One", "is_bot": False, "state": "APPROVED", "body": ""},
            ],
            "commits_in_range": [
                {"date": "2026-02-02T11:00:00Z", "author": "d@x.com",
                 "author_name": "Dev", "is_bot": False, "sha": "abc1234", "message": "m"},
            ],
        }
        events = self.gatherer._build_events_in_range([], [], [pr], self.date_range)
        self.assertEqual([e["type"] for e in events], ["github_review", "github_commit"])
        for event in events:
            self.assertEqual(event["pr"], "org/repo#123")
            self.assertEqual(event["pr_url"], "http://github.com/org/repo/pull/123")

    def test_pr_without_identity_contributes_nothing(self) -> None:
        pr = {"url": "https://github.com/org/repo/pull/123", "dates": {},
              "reviews_in_range": [{"submitted_at": "2026-02-01T10:00:00Z", "author": "x",
                                    "author_name": "X", "is_bot": False}],
              "commits_in_range": []}
        events = self.gatherer._build_events_in_range([], [], [pr], self.date_range)
        self.assertEqual(events, [])

    def test_merge_event_window_and_authority(self) -> None:
        def pr_with_merge(merged_at, merged_by=None):
            return {"url": "https://github.com/org/repo/pull/123", "owner": "org",
                    "repo": "repo", "number": 123,
                    "dates": {"merged_at": merged_at},
                    "merged_by": merged_by, "merged_by_name": merged_by,
                    "reviews_in_range": [], "commits_in_range": []}

        in_window = pr_with_merge("2026-02-03T16:00:00Z", "openshift-merge-bot")
        before = pr_with_merge("2026-01-15T16:00:00Z", "merger")
        after = pr_with_merge("2026-02-20T16:00:00Z", "merger")
        open_pr = pr_with_merge(None)

        events = self.gatherer._build_events_in_range(
            [], [], [in_window, before, after, open_pr], self.date_range
        )
        self.assertEqual([e["type"] for e in events], ["github_merge"])
        # A bot-performed merge is kept: the merge itself is the evidence.
        self.assertEqual(events[0]["author_login"], "openshift-merge-bot")

        # Without a date range, no merge filtering is possible.
        events = self.gatherer._build_events_in_range([], [], [in_window])
        self.assertEqual(events, [])

    def test_bot_reviews_and_commits_excluded(self) -> None:
        pr = {
            "url": "https://github.com/org/repo/pull/123", "owner": "org",
            "repo": "repo", "number": 123, "dates": {},
            "reviews_in_range": [
                {"submitted_at": "2026-02-01T10:00:00Z", "author": "coderabbitai[bot]",
                 "author_name": "coderabbitai[bot]", "is_bot": True, "state": "COMMENTED", "body": ""},
                {"submitted_at": "2026-02-01T11:00:00Z", "author": "human1",
                 "author_name": "Human One", "is_bot": False, "state": "APPROVED", "body": ""},
            ],
            "commits_in_range": [
                {"date": "2026-02-01T12:00:00Z", "author": "merge-bot@noreply",
                 "author_name": "OpenShift Merge Robot", "is_bot": True, "sha": "aaa", "message": "auto"},
                {"date": "2026-02-01T13:00:00Z", "author": "d@x.com",
                 "author_name": "Dev", "is_bot": False, "sha": "bbb", "message": "real"},
            ],
        }
        events = self.gatherer._build_events_in_range([], [], [pr], self.date_range)
        self.assertEqual(
            [(e["type"], e["author"]) for e in events],
            [("github_review", "Human One"), ("github_commit", "Dev")],
        )
        self.assertEqual(events[0]["author_login"], "human1")
        self.assertEqual(events[1]["author_email"], "d@x.com")


class FakeJiraPages:
    """Replaces JiraClient._fetch_json with Jira changelog semantics.

    Serves oldest-first slices of a prebuilt entry list with the
    total/isLast/maxResults metadata the real endpoint returns. Can
    simulate the list growing between requests (entries appended at
    the newest end).
    """

    def __init__(self, entries: list, grow_after_first_request: int = 0):
        self.entries = list(entries)
        self.grow_after_first_request = grow_after_first_request
        # startAt -> remaining number of requests to fail (None response)
        self.fail_offsets: dict = {}
        self.requests = 0

    async def __call__(self, url: str, **kwargs):
        self.requests += 1
        if self.requests == 2 and self.grow_after_first_request:
            extra = synthetic_changelog(len(self.entries) + self.grow_after_first_request)
            self.entries.extend(extra[len(self.entries):])
        query = parse_qs(urlparse(url).query)
        max_results = min(int(query["maxResults"][0]), 100)  # API clamps to 100
        start = int(query.get("startAt", ["0"])[0])
        if self.fail_offsets.get(start, 0) > 0:
            self.fail_offsets[start] -= 1
            return None
        values = self.entries[start : start + max_results]
        return {
            "startAt": start,
            "maxResults": max_results,
            "total": len(self.entries),
            "isLast": start + max_results >= len(self.entries) or not values,
            "values": values,
        }


class ChangelogPaginationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        g.JIRA_CHANGELOG_DELAY_SECONDS = 0  # keep tests fast
        g.JIRA_PAGE_RETRY_DELAY_SECONDS = 0

    def make_client(self, entries, grow=0):
        client = g.JiraClient(
            "https://test.atlassian.net", "token", "user"
        )
        fake = FakeJiraPages(entries, grow_after_first_request=grow)
        client._fetch_json = fake
        return client, fake

    async def test_single_page_issue_costs_one_request(self) -> None:
        entries = synthetic_changelog(50)
        client, fake = self.make_client(entries)
        result = await client.get_issue_changelog("KEY-1")
        self.assertEqual(result, entries)
        self.assertEqual(fake.requests, 1)

    async def test_multi_page_covers_exactly_once(self) -> None:
        # 167 entries: tail jump plus one partial page; the pages must
        # neither overlap (a fixed page size would) nor leave a gap.
        entries = synthetic_changelog(167)
        client, fake = self.make_client(entries)
        result = await client.get_issue_changelog("KEY-1")
        self.assertEqual(len(result), 167)
        self.assertEqual([e["created"] for e in result],
                         sorted(e["created"] for e in entries))
        self.assertEqual(fake.requests, 3)  # probe + tail + remainder

    async def test_window_bound_keeps_crossing_page_and_newest(self) -> None:
        entries = synthetic_changelog(167)
        bound = g.parse_iso_datetime(entries[151]["created"])
        client, fake = self.make_client(entries)
        result = await client.get_issue_changelog(
            "KEY-1", not_older_than=bound
        )
        # Newest present, oldest fetched predates the bound (crossing
        # page kept), and only the tail page was fetched.
        self.assertEqual(result[-1]["created"], entries[-1]["created"])
        self.assertLess(
            g.parse_iso_datetime(result[0]["created"]), bound
        )
        self.assertEqual(len(result), 100)
        self.assertEqual(fake.requests, 2)

    async def test_growth_mid_walk_triggers_rejump(self) -> None:
        entries = synthetic_changelog(167)
        client, fake = self.make_client(entries, grow=3)
        result = await client.get_issue_changelog("KEY-1")
        self.assertEqual(len(result), 170)
        self.assertEqual(
            result[-1]["created"], synthetic_changelog(170)[-1]["created"]
        )
        created = [e["created"] for e in result]
        self.assertEqual(created, sorted(created))
        self.assertEqual(len(created), len(set(created)))

    async def test_transient_page_failure_is_retried(self) -> None:
        # 167 entries: probe (startAt=0), tail (startAt=67), remainder
        # (startAt=0 again). Fail the tail page once — the retry must
        # recover and the changelog must still be complete.
        entries = synthetic_changelog(167)
        client, fake = self.make_client(entries)
        fake.fail_offsets[67] = 1
        result = await client.get_issue_changelog("KEY-1")
        self.assertEqual(len(result), 167)
        self.assertEqual(fake.requests, 4)  # 3 pagination requests + 1 retry

    async def test_persistent_page_failure_raises(self) -> None:
        # A failed page mid-walk must not yield a partial changelog
        # that passes as complete.
        entries = synthetic_changelog(167)
        client, fake = self.make_client(entries)
        fake.fail_offsets[67] = g.JIRA_PAGE_RETRY_ATTEMPTS + 5
        with self.assertRaises(RuntimeError):
            await client.get_issue_changelog("KEY-1")

    async def test_find_last_change_matching_returns_newest(self) -> None:
        entries = [
            {"created": "2026-01-01T00:00:00Z",
             "items": [{"field": "Status Summary"}]},
            {"created": "2026-01-02T00:00:00Z", "items": [{"field": "labels"}]},
            {"created": "2026-01-03T00:00:00Z",
             "items": [{"field": "Status Summary"}, {"field": "status"}]},
        ]
        client, _ = self.make_client(entries)
        found = await client.find_last_change_matching(
            "KEY-1", g._is_status_summary_item
        )
        self.assertEqual(found, "2026-01-03T00:00:00Z")
        self.assertIsNone(
            await client.find_last_change_matching("KEY-1", lambda item: False)
        )

    async def test_find_last_change_matching_stops_fetching_at_match(self) -> None:
        # 250 entries = probe + 3 walk pages. A match on the newest page
        # must stop after the tail jump instead of walking all history.
        entries = synthetic_changelog(250)
        entries[249]["items"] = [{"field": "Status Summary"}]
        client, fake = self.make_client(entries)
        found = await client.find_last_change_matching(
            "KEY-1", g._is_status_summary_item
        )
        self.assertEqual(found, entries[249]["created"])
        self.assertEqual(fake.requests, 2)  # probe + newest page only

        # No match anywhere: the full history is still walked.
        client, fake = self.make_client(synthetic_changelog(250))
        self.assertIsNone(
            await client.find_last_change_matching("KEY-1", lambda item: False)
        )
        self.assertEqual(fake.requests, 4)


if __name__ == "__main__":
    unittest.main()
