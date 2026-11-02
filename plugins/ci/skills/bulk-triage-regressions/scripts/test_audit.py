import base64
import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

import audit


def jload(p):
    with open(p) as f:
        return json.load(f)


def jdump(o, p):
    with open(p, 'w') as f:
        json.dump(o, f)


def snap(triages, time="2026-10-12T01:00:00Z"):
    return {"time": time, "triages": triages}


def tri(regs, url="https://x/triages/1", resolved=None):
    return {"regression_ids": regs, "url": url, "resolved": resolved}


class AuditFetchTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(audit, "_default_audit_fetch", return_value=[])
        self.audit_fetch = patcher.start()
        self.addCleanup(patcher.stop)


class DiffTests(AuditFetchTests):
    def captured_snapshots(self):
        with mock.patch.object(audit, "datetime") as clock:
            clock.now.side_effect = [datetime(2026, 10, 12, 1, 0, 0, 250000, tzinfo=timezone.utc),
                                     datetime(2026, 10, 12, 1, 0, 1, 750000, tzinfo=timezone.utc)]
            before = audit.snapshot_triages(fetch=lambda: [])
            after = audit.snapshot_triages(fetch=lambda: [{"id": 7, "regressions": [{"id": 5}]}])
        return before, after

    def test_fractional_bot_before_captured_end_blocks_attribution(self):
        before, after = self.captured_snapshots()
        entries = [self.entry(created_at="2026-10-12T01:00:00.500000Z"),
                   self.entry(audit.BULK_TRIAGE_BOT_USER, "2026-10-12T01:00:01.500000Z")]
        result = audit.diff_triages(before, after, [], audit_fetch=lambda _: entries)
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["external"], [])
        self.assertEqual(result["undeclared"][0]["kind"], "created")

    def test_fractional_human_before_captured_end_is_external(self):
        before, after = self.captured_snapshots()
        result = audit.diff_triages(before, after, [], audit_fetch=lambda _: [
            self.entry(created_at="2026-10-12T01:00:01.500000Z")])
        self.assertEqual(result["status"], "match")
        self.assertEqual(result["undeclared"], [])
        self.assertEqual(result["external"][0]["users"], ["human"])

    def test_bot_after_captured_end_is_outside_window(self):
        before, after = self.captured_snapshots()
        entries = [self.entry(created_at="2026-10-12T01:00:00.500000Z"),
                   self.entry(audit.BULK_TRIAGE_BOT_USER, "2026-10-12T01:00:01.750000001Z")]
        result = audit.diff_triages(before, after, [], audit_fetch=lambda _: entries)
        self.assertEqual(result["status"], "match")
        self.assertEqual(result["external"][0]["users"], ["human"])

    def test_bot_before_captured_start_is_outside_window(self):
        before, after = self.captured_snapshots()
        entries = [self.entry(created_at="2026-10-12T01:00:00.500000Z"),
                   self.entry(audit.BULK_TRIAGE_BOT_USER, "2026-10-12T01:00:00.249999999Z")]
        result = audit.diff_triages(before, after, [], audit_fetch=lambda _: entries)
        self.assertEqual(result["status"], "match")
        self.assertEqual(result["external"][0]["users"], ["human"])

    def test_captured_snapshot_boundaries_are_inclusive(self):
        before, after = self.captured_snapshots()
        for timestamp in ("2026-10-12T03:00:00.250000000+02:00", "2026-10-12T01:00:01.750000000Z"):
            with self.subTest(timestamp=timestamp):
                entries = [self.entry(created_at="2026-10-12T01:00:00.500000Z"),
                           self.entry(audit.BULK_TRIAGE_BOT_USER, timestamp)]
                result = audit.diff_triages(before, after, [], audit_fetch=lambda _: entries)
                self.assertEqual(result["status"], "mismatch")
                self.assertEqual(result["external"], [])

    def test_second_only_snapshot_end_is_not_widened(self):
        entries = [self.entry(created_at="2026-10-12T01:00:00.500000Z"),
                   self.entry(audit.BULK_TRIAGE_BOT_USER, "2026-10-12T01:00:01.500000Z")]
        result = audit.diff_triages(snap({}, "2026-10-12T01:00:00Z"),
                                    snap({"7": tri([5])}, "2026-10-12T01:00:01Z"), [],
                                    audit_fetch=lambda _: entries)
        self.assertEqual(result["status"], "match")
        self.assertEqual(result["external"][0]["users"], ["human"])

    def entry(self, user="human", created_at="2026-10-12T01:30:00Z"):
        return {"operation": "update", "changes": [], "user": user, "created_at": created_at}

    def creation_diff(self, entries):
        return audit.diff_triages(snap({}), snap({"7": tri([5])}, "2026-10-12T02:00:00Z"), [],
                                  audit_fetch=lambda _: entries)

    def test_human_creation_is_external(self):
        result = self.creation_diff([self.entry()])
        self.assertEqual(result["status"], "match")
        self.assertEqual(result["undeclared"], [])
        self.assertEqual(result["created"], ["7"])
        self.assertEqual(result["external"], [{"kind": "created", "triage_id": "7",
                                             "url": "https://x/triages/1", "jira": None,
                                             "regression_ids": [5], "users": ["human"]}])

    def test_bot_creation_is_undeclared(self):
        result = self.creation_diff([self.entry(audit.BULK_TRIAGE_BOT_USER)])
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["external"], [])
        self.assertEqual(result["undeclared"][0]["kind"], "created")

    def test_human_missing_changes_is_external(self):
        entry = self.entry()
        del entry["changes"]
        result = self.creation_diff([entry])
        self.assertEqual(result["status"], "match")
        self.assertEqual(result["undeclared"], [])
        self.assertEqual(result["external"][0]["users"], ["human"])

    def test_bot_missing_changes_is_undeclared(self):
        entry = self.entry(audit.BULK_TRIAGE_BOT_USER)
        del entry["changes"]
        for entries in ([entry], [self.entry(), entry]):
            with self.subTest(entries=entries):
                result = self.creation_diff(entries)
                self.assertEqual(result["status"], "mismatch")
                self.assertEqual(result["external"], [])
                self.assertEqual(result["undeclared"][0]["kind"], "created")

    def test_present_non_list_changes_is_undeclared(self):
        for changes in (None, {}, "", "[]", 0, False, ()):
            with self.subTest(changes=changes):
                result = self.creation_diff([self.entry(), dict(self.entry(), changes=changes)])
                self.assertEqual(result["status"], "mismatch")
                self.assertEqual(result["external"], [])
                self.assertEqual(result["undeclared"][0]["kind"], "created")

    def test_mixed_human_and_bot_is_undeclared(self):
        for entries in ([self.entry(), self.entry(audit.BULK_TRIAGE_BOT_USER)],
                        [self.entry(audit.BULK_TRIAGE_BOT_USER), self.entry()]):
            with self.subTest(entries=entries):
                self.assertEqual(self.creation_diff(entries)["status"], "mismatch")

    def test_fetch_failure_is_undeclared(self):
        self.audit_fetch.side_effect = OSError("audit unavailable")
        result = audit.diff_triages(snap({}), snap({"7": tri([5])}), [])
        self.audit_fetch.assert_called_once_with("7")
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["external"], [])

    def test_only_outside_window_is_undeclared(self):
        entries = [self.entry(created_at="2026-10-12T00:59:59Z"),
                   self.entry(created_at="2026-10-12T02:00:00.000000001Z")]
        self.assertEqual(self.creation_diff(entries)["status"], "mismatch")
        self.assertEqual(self.creation_diff([])["status"], "mismatch")

    def test_inclusive_boundaries_and_offset_formats(self):
        for timestamp in ("2026-10-12T01:00:00Z", "2026-10-12T02:00:00Z",
                          "2026-10-12T03:00:00.000000000+02:00", "2026-10-11T21:00:00-04:00"):
            with self.subTest(timestamp=timestamp):
                self.assertEqual(self.creation_diff([self.entry(created_at=timestamp)])["status"], "match")

    def test_nanosecond_snapshot_boundary(self):
        timestamp = "2026-10-12T01:30:00.123456789Z"
        for created_at, status in ((timestamp, "match"), ("2026-10-12T01:30:00.123456788Z", "mismatch"),
                                   ("2026-10-12T01:30:00.123456790Z", "mismatch")):
            with self.subTest(created_at=created_at):
                result = audit.diff_triages(snap({}, timestamp), snap({"7": tri([5])}, timestamp), [],
                                            audit_fetch=lambda _: [self.entry(created_at=created_at)])
                self.assertEqual(result["status"], status)

    def test_malformed_audit_is_undeclared(self):
        valid = self.entry()
        malformed = [None, {}, "bad", [None], [dict(valid, user=None)], [dict(valid, user="")],
                     [dict(valid, user=" ")], [dict(valid, user={})],
                     [dict(valid, user=" " + audit.BULK_TRIAGE_BOT_USER)],
                     [dict(valid, operation=None)], [dict(valid, changes={})],
                     [dict(valid, changes=[None])], [dict(valid, changes=[{}])],
                     [dict(valid, changes=[{"field_name": "url", "original": None, "modified": "new"}])],
                     [dict(valid, changes=[{"field_name": "", "original": "old", "modified": "new"}])],
                     [{key: value for key, value in valid.items() if key != "user"}]]
        for entries in malformed:
            with self.subTest(entries=entries):
                self.assertEqual(self.creation_diff(entries)["status"], "mismatch")
                if isinstance(entries, list):
                    self.assertEqual(self.creation_diff([valid] + entries)["status"], "mismatch")
        for timestamp in (None, 0, "bad", "2026-10-12", "2026-10-12T01:30:00",
                          "2026-02-30T01:30:00Z", "2026-10-12T01:30:00.1234567890Z"):
            with self.subTest(timestamp=timestamp):
                self.assertEqual(self.creation_diff([valid, self.entry(created_at=timestamp)])["status"], "mismatch")

    def test_invalid_offsets_fail_closed_in_entries_and_bounds(self):
        for timestamp in ("2026-10-12T02:30:00+00:60", "2026-10-12T00:30:00-00:60",
                          "2026-10-13T01:30:00+24:00"):
            with self.subTest(timestamp=timestamp):
                self.assertEqual(self.creation_diff([self.entry(created_at=timestamp)])["status"], "mismatch")
                for start, end in ((timestamp, "2026-10-12T02:00:00Z"),
                                   ("2026-10-12T01:00:00Z", timestamp)):
                    result = audit.diff_triages(snap({}, start), snap({"7": tri([5])}, end), [],
                                                audit_fetch=lambda _: [self.entry()])
                    self.assertEqual(result["status"], "mismatch")

    def test_valid_field_change_attribution(self):
        entry = dict(self.entry(), changes=[{"field_name": "regressions", "original": "1", "modified": "1,2"}])
        self.assertEqual(self.creation_diff([entry])["status"], "match")

    def test_bad_snapshot_window_is_undeclared(self):
        for start, end in ((None, "bad"), ("bad", "2026-10-12T02:00:00Z"),
                           ("2026-10-12T02:00:00Z", "2026-10-12T01:00:00Z")):
            with self.subTest(start=start, end=end):
                result = audit.diff_triages(snap({}, start), snap({"7": tri([5])}, end), [],
                                            audit_fetch=lambda _: [self.entry()])
                self.assertEqual(result["status"], "mismatch")

    def test_regression_tracker_extension_is_external(self):
        result = audit.diff_triages(snap({"1": tri([1])}),
                                    snap({"1": tri([1, 2])}, "2026-10-12T02:00:00Z"), [],
                                    audit_fetch=lambda _: [self.entry("regression-tracker")])
        self.assertEqual(result["status"], "match")
        self.assertEqual(result["external"], [{"kind": "extended", "triage_id": "1", "added": [2],
                                             "users": ["regression-tracker"]}])

    def test_all_change_kinds_keep_shape_and_cache_audit(self):
        before = snap({"1": tri([1, 3]), "2": tri([4])})
        after = snap({"1": tri([1, 2], url="https://new"), "3": tri([5])}, "2026-10-12T02:00:00Z")
        baseline = audit.diff_triages(before, after, [], audit_fetch=lambda _: [])
        fetch = mock.Mock(return_value=[self.entry("other"), self.entry(), self.entry()])
        result = audit.diff_triages(before, after, [], audit_fetch=fetch)
        self.assertEqual(result["status"], "match")
        self.assertEqual(result["undeclared"], [])
        self.assertEqual(result["external"], [dict(change, users=["human", "other"])
                                             for change in baseline["undeclared"]])
        self.assertEqual({change["kind"] for change in result["external"]},
                         {"created", "extended", "removed", "deleted", "modified"})
        self.assertEqual(fetch.call_args_list, [mock.call("1"), mock.call("2"), mock.call("3")])

    def test_deleted_audit_unavailable_stays_undeclared(self):
        self.audit_fetch.side_effect = OSError("not found")
        result = audit.diff_triages(snap({"1": tri([1])}), snap({}), [])
        self.assertEqual(result["undeclared"][0]["kind"], "deleted")
        self.assertEqual(result["status"], "mismatch")

    def test_outside_bot_does_not_block_human_attribution(self):
        result = self.creation_diff([self.entry(), self.entry(audit.BULK_TRIAGE_BOT_USER,
                                                             "2026-10-12T00:00:00Z")])
        self.assertEqual(result["status"], "match")

    def test_external_creation_preserves_declaration_mismatch(self):
        declaration = [{"type": "create_triage", "triage_id": 8, "regression_ids": [5], "status": "done"}]
        result = audit.diff_triages(snap({}), snap({"7": tri([5])}, "2026-10-12T02:00:00Z"), declaration,
                                    audit_fetch=lambda _: [self.entry()])
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["declared_not_observed"], declaration)
        self.assertEqual(len(result["external"]), 1)

    def test_declared_creation_needs_no_attribution(self):
        declaration = [{"type": "create_triage", "triage_id": 7, "regression_ids": [5], "status": "done"}]
        result = audit.diff_triages(snap({}), snap({"7": tri([5])}), declaration)
        self.assertEqual(result["status"], "match")
        self.audit_fetch.assert_not_called()

    def test_description_only_sync_is_external_without_declaration(self):
        before = snap({"1": dict(tri([1]), description="old")})
        after = snap({"1": dict(tri([1]), description="synced")})
        result = audit.diff_triages(before, after, [])
        self.assertEqual(result["status"], "match")
        self.assertEqual(result["modified"], [{"triage_id": "1", "fields": ["description"]}])
        self.assertEqual(result["external"], [{"kind": "modified", "triage_id": "1", "fields": ["description"],
                                             "before": {"description": "old"}, "after": {"description": "synced"}}])
        self.assertEqual(result["undeclared"], [])

    def test_description_and_url_change_is_not_external(self):
        before = snap({"1": dict(tri([1]), description="old")})
        after = snap({"1": dict(tri([1], url="https://x/triages/2"), description="synced")})
        result = audit.diff_triages(before, after, [])
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["external"], [])
        self.assertEqual(result["undeclared"][0]["fields"], ["url", "description"])

    def test_description_and_undeclared_extension_is_not_external(self):
        before = snap({"1": dict(tri([1]), description="old")})
        after = snap({"1": dict(tri([1, 2]), description="synced")})
        result = audit.diff_triages(before, after, [])
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["external"], [])
        self.assertEqual([change["kind"] for change in result["undeclared"]], ["extended", "modified"])

    def test_three_triage_description_syncs_match(self):
        descriptions = {
            "250": ("Component Readiness: scaling calculation", "scaling calculation"),
            "508": ("Continued apiserver failure", "Continued disruption due to CPU exhaustion"),
            "567": ("Component Readiness: scaling calculation", "scaling calculation"),
        }
        before, after = {}, {}
        for triage_id, (old_description, new_description) in descriptions.items():
            record = dict(tri([int(triage_id)], url="https://x/triages/" + triage_id),
                          type="product", resolved=None, resolution_reason="")
            before[triage_id] = dict(record, description=old_description)
            after[triage_id] = dict(record, description=new_description)
        result = audit.diff_triages(snap(before), snap(after), [])
        self.assertEqual(result["status"], "match")
        self.assertEqual([change["triage_id"] for change in result["external"]], ["250", "508", "567"])
        self.assertTrue(all(change["fields"] == ["description"] for change in result["external"]))
        self.assertEqual(len(result["modified"]), 3)
        self.assertEqual(result["undeclared"], [])

    def test_description_with_protected_changes_remains_undeclared(self):
        before = snap({"1": dict(tri([1]), description="old")})
        for field, value in (("type", "product"), ("resolved", {"Time": "2026-10-01T00:00:00Z", "Valid": True}),
                             ("resolution_reason", "user")):
            with self.subTest(field=field):
                record = dict(tri([1]), description="synced")
                record[field] = value
                result = audit.diff_triages(before, snap({"1": record}), [])
                self.assertEqual(result["status"], "mismatch")
                self.assertEqual(result["external"], [])
                self.assertEqual(result["undeclared"][0]["fields"], [field, "description"])

    def test_description_with_membership_removal_is_not_external(self):
        before = snap({"1": dict(tri([1, 2]), description="old")})
        after = snap({"1": dict(tri([1]), description="synced")})
        declaration = [{"type": "extend_triage", "triage_id": 1, "regression_ids": [1], "status": "done"}]
        result = audit.diff_triages(before, after, declaration)
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["external"], [])
        self.assertEqual(result["undeclared"][0]["kind"], "removed")

    def test_external_sync_does_not_hide_unobserved_declaration(self):
        before = snap({"1": dict(tri([1]), description="old")})
        after = snap({"1": dict(tri([1]), description="synced")})
        declaration = [{"type": "extend_triage", "triage_id": 1, "regression_ids": [2], "status": "done"}]
        result = audit.diff_triages(before, after, declaration)
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(len(result["external"]), 1)
        self.assertEqual(result["declared_not_observed"], declaration)

    def test_undeclared_extension_detected(self):
        r = audit.diff_triages(snap({"1": tri([1])}), snap({"1": tri([1, 2])}), [])
        self.assertEqual(r["extended"], [{"triage_id": "1", "added": [2]}])
        self.assertEqual(len(r["undeclared"]), 1)
        self.assertEqual(r["status"], "mismatch")

    def test_declared_actions_match(self):
        decl = [{"type": "extend_triage", "triage_id": 1, "regression_ids": [2, 3], "status": "done"}]
        r = audit.diff_triages(snap({"1": tri([1, 3])}), snap({"1": tri([1, 2, 3])}), decl)   # 3 already linked
        self.assertEqual(r["undeclared"], [])
        self.assertEqual(r["status"], "match")
        # a declared id that never reached the triage is a write that did not happen → mismatch
        r = audit.diff_triages(snap({"1": tri([1])}), snap({"1": tri([1, 2])}), decl)
        self.assertEqual(r["status"], "mismatch")
        self.assertEqual(len(r["declared_not_observed"]), 1)

    def test_declared_create_matches_by_url_and_ids(self):
        decl = [{"type": "create_triage", "jira": "OCPBUGS-9", "regression_ids": [5, 6], "status": "done"}]
        after = snap({"7": tri([5, 6], url="https://j/browse/OCPBUGS-9")})
        r = audit.diff_triages(snap({}), after, decl)
        self.assertEqual(r["created"], ["7"])
        self.assertEqual(r["undeclared"], [])
        self.assertEqual(r["status"], "match")

    def test_catch_all_covers_extension(self):
        decl = [{"type": "catch_all", "triage_id": 1, "regression_ids": [2], "status": "done"}]
        r = audit.diff_triages(snap({"1": tri([1])}), snap({"1": tri([1, 2])}), decl)
        self.assertEqual(r["status"], "match")

    def test_created_must_cover_declared_ids(self):
        decl = [{"type": "create_triage", "jira": "OCPBUGS-9", "regression_ids": [5, 6], "status": "done"}]
        r = audit.diff_triages(snap({}), snap({"7": tri([5], url="https://j/OCPBUGS-9")}), decl)
        self.assertEqual(r["status"], "mismatch")

    def test_created_without_declaration(self):
        r = audit.diff_triages(snap({}), snap({"7": tri([5])}), [])
        self.assertEqual(r["status"], "mismatch")

    def test_removed_regressions_are_undeclared(self):
        decl = [{"type": "extend_triage", "triage_id": 1, "regression_ids": [1], "status": "done"}]
        r = audit.diff_triages(snap({"1": tri([1, 2])}), snap({"1": tri([1])}), decl)
        self.assertEqual(r["removed"], [{"triage_id": "1", "removed": [2]}])
        self.assertTrue(r["undeclared"])

    def test_declared_not_observed_is_mismatch(self):
        decl = [{"type": "extend_triage", "triage_id": 1, "regression_ids": [2], "status": "done"},
                {"type": "extend_triage", "triage_id": 9, "regression_ids": [2], "status": "failed"}]
        r = audit.diff_triages(snap({"1": tri([1])}), snap({"1": tri([1])}), decl)
        self.assertEqual(len(r["declared_not_observed"]), 1)
        self.assertEqual(r["status"], "mismatch")

    def test_malformed_snapshot_is_unknown(self):
        r = audit.diff_triages({"status": "unknown", "error": "boom"}, snap({}), [])
        self.assertEqual(r["status"], "unknown")
        self.assertIn("error", r)


class AuditHttpTests(unittest.TestCase):
    def test_default_get_and_json_failure(self):
        entry = {"operation": "CREATE", "changes": [], "user": "human", "created_at": "2026-10-12T01:00:00Z"}
        for payload, status in ((json.dumps([entry]).encode(), "match"), (b"not json", "mismatch")):
            with self.subTest(payload=payload), mock.patch.object(audit.urllib.request, "urlopen") as urlopen:
                response = urlopen.return_value.__enter__.return_value
                response.headers = {}
                response.read.return_value = payload
                result = audit.diff_triages(snap({}), snap({"7": tri([5])}), [])
                self.assertEqual(result["status"], status)
                request = urlopen.call_args.args[0]
                self.assertEqual(request.full_url,
                                 "https://sippy.dptools.openshift.org/api/component_readiness/triages/7/audit")
                self.assertEqual(request.get_method(), "GET")
                self.assertEqual(urlopen.call_args.kwargs["timeout"], audit.TIMEOUT)


class SnapshotTests(unittest.TestCase):
    def test_failed_snapshot_time_preserves_precision(self):
        with mock.patch.object(audit, "datetime") as clock:
            clock.now.return_value = datetime(2026, 10, 12, 1, 0, 1, 750000, tzinfo=timezone.utc)
            snapshot = audit.snapshot_triages(fetch=mock.Mock(side_effect=OSError("down")))
        self.assertEqual(snapshot["status"], "unknown")
        self.assertEqual(snapshot["time"], "2026-10-12T01:00:01.750000Z")

    def test_captured_snapshot_time_preserves_precision(self):
        with mock.patch.object(audit, "datetime") as clock:
            clock.now.return_value = datetime(2026, 10, 12, 1, 0, 1, 750000, tzinfo=timezone.utc)
            snapshot = audit.snapshot_triages(fetch=lambda: [])
            self.assertEqual(audit._now(), "2026-10-12T01:00:01Z")
        self.assertEqual(snapshot["time"], "2026-10-12T01:00:01.750000Z")
        self.assertEqual(audit._audit_timestamp(snapshot["time"]),
                         audit._audit_timestamp("2026-10-12T03:00:01.750000000+02:00"))

    def test_resolved_struct_preserved_in_snapshot(self):
        res = {"Time": "2026-05-14T12:25:28.941154Z", "Valid": True}
        data = [{"id": 3, "url": "u", "resolved": res,
                 "regressions": [{"id": 10, "x": 1}, {"id": 11}]}]
        s = audit.snapshot_triages(fetch=lambda: data)
        t = s["triages"]["3"]
        self.assertEqual((t["regression_ids"], t["url"], t["resolved"]), ([10, 11], "u", res))
        self.assertEqual(set(t), {"regression_ids", "url", "type", "description", "resolved", "resolution_reason"})

    def test_fetch_failure_is_unknown(self):
        def bad():
            raise OSError("down")
        s = audit.snapshot_triages(fetch=bad)
        self.assertEqual(s["status"], "unknown")
        self.assertIn("down", s["error"])


def issue(key, created):
    return {"key": key, "fields": {"created": created, "summary": "s"}}


class DiffReviewTests(AuditFetchTests):
    """Findings C1/C2 of the pre-merge review: coverage must be exact and every write observable."""

    def test_created_triage_with_undeclared_extra_member_is_mismatch(self):
        decl = [{"type": "create_triage", "jira": "OCPBUGS-9", "regression_ids": [5], "status": "done"}]
        r = audit.diff_triages(snap({}), snap({"7": tri([5, 999], url="https://j/browse/OCPBUGS-9")}), decl)
        self.assertEqual(r["status"], "mismatch")
        self.assertEqual(r["undeclared"][0]["kind"], "created")

    def test_jira_key_match_is_exact_not_substring(self):
        decl = [{"type": "create_triage", "jira": "OCPBUGS-9", "regression_ids": [5], "status": "done"}]
        r = audit.diff_triages(snap({}), snap({"7": tri([5], url="https://j/browse/OCPBUGS-99")}), decl)
        self.assertEqual(r["status"], "mismatch")
        r = audit.diff_triages(snap({}), snap({"7": tri([5], url="https://j/browse/OCPBUGS-9")}), decl)
        self.assertEqual(r["status"], "match")

    def test_created_triage_matches_by_returned_triage_id(self):
        decl = [{"type": "create_triage", "triage_id": 7, "regression_ids": [5], "status": "done"}]
        r = audit.diff_triages(snap({}), snap({"7": tri([5], url="https://j/browse/OCPBUGS-1")}), decl)
        self.assertEqual(r["status"], "match")

    def test_two_clusters_extending_one_triage_are_aggregated(self):
        decl = [{"type": "extend_triage", "triage_id": 1, "regression_ids": [i], "status": "done"} for i in (2, 3)]
        r = audit.diff_triages(snap({"1": tri([1])}), snap({"1": tri([1, 2, 3])}), decl)
        self.assertEqual(r["status"], "match", r)

    def test_deleted_triage_is_undeclared(self):
        r = audit.diff_triages(snap({"1": tri([1])}), snap({}), [])
        self.assertEqual(r["status"], "mismatch")
        self.assertEqual(r["deleted"], ["1"])
        self.assertEqual(r["undeclared"][0]["kind"], "deleted")

    def test_protected_field_changes_are_undeclared_even_with_declared_extension(self):
        decl = [{"type": "extend_triage", "triage_id": 1, "regression_ids": [2], "status": "done"}]
        before = snap({"1": tri([1], url="https://j/browse/OCPBUGS-1")})
        for field, value in (("url", "https://j/browse/OCPBUGS-999"), ("type", "product"),
                             ("resolved", {"Time": "2026-10-01T00:00:00Z", "Valid": True}),
                             ("resolution_reason", "user")):
            t = tri([1, 2], url="https://j/browse/OCPBUGS-1")
            t[field] = value
            r = audit.diff_triages(before, snap({"1": t}), decl)
            self.assertEqual(r["status"], "mismatch", field)
            self.assertTrue(any(o["kind"] == "modified" and field in o["fields"] for o in r["undeclared"]), field)

    def test_description_change_is_covered_by_a_declared_extension_only(self):
        before = snap({"1": tri([1])}); before["triages"]["1"]["description"] = "old"
        after = snap({"1": tri([1, 2])}); after["triages"]["1"]["description"] = "old + new"
        decl = [{"type": "extend_triage", "triage_id": 1, "regression_ids": [2], "status": "done"}]
        self.assertEqual(audit.diff_triages(before, after, decl)["status"], "match")
        self.assertEqual(audit.diff_triages(before, after, [])["status"], "mismatch")

    def test_equivalent_resolved_timestamps_are_not_a_change(self):
        before = snap({"1": tri([1], resolved={"Time": "2026-10-01T00:00:00Z", "Valid": True})})
        after = snap({"1": tri([1], resolved={"Time": "2026-10-01T00:00:00+00:00", "Valid": True})})
        self.assertEqual(audit.diff_triages(before, after, [])["status"], "match")

    def test_snapshot_captures_protected_fields(self):
        data = [{"id": 1, "url": "u", "type": "ci-infra", "description": "d", "resolved": None,
                 "resolution_reason": "jira-progression", "regressions": [{"id": 3}]}]
        t = audit.snapshot_triages(fetch=lambda: data)["triages"]["1"]
        self.assertEqual(t["type"], "ci-infra"); self.assertEqual(t["description"], "d")
        self.assertEqual(t["resolution_reason"], "jira-progression")


class DiffReviewWave2Tests(AuditFetchTests):
    """Review wave 2: N1 — creation identity and composition."""

    def created(self, ids, key="OCPBUGS-9"):
        return tri(ids, url="https://j/browse/" + key)

    def test_explicit_id_declaration_does_not_cover_a_second_creation_by_key(self):
        decl = [{"type": "create_triage", "triage_id": 7, "jira": "OCPBUGS-9", "regression_ids": [5], "status": "done"}]
        r = audit.diff_triages(snap({}), snap({"7": self.created([5]), "8": self.created([5])}), decl)
        self.assertEqual(r["status"], "mismatch")
        self.assertEqual([o["triage_id"] for o in r["undeclared"]], ["8"])

    def test_declared_id_and_key_must_both_agree(self):
        decl = [{"type": "create_triage", "triage_id": 7, "jira": "OCPBUGS-9", "regression_ids": [5], "status": "done"}]
        r = audit.diff_triages(snap({}), snap({"7": self.created([5], "OCPBUGS-99")}), decl)
        self.assertEqual(r["status"], "mismatch")

    def test_create_then_extend_same_run_is_legitimate(self):
        decl = [{"type": "create_triage", "triage_id": 7, "jira": "OCPBUGS-9", "regression_ids": [5], "status": "done"},
                {"type": "extend_triage", "triage_id": 7, "regression_ids": [6], "status": "done"}]
        self.assertEqual(audit.diff_triages(snap({}), snap({"7": self.created([5, 6])}), decl)["status"], "match")

    def test_two_clusters_sharing_one_creation_with_and_without_id(self):
        decl = [{"type": "create_triage", "triage_id": 7, "jira": "OCPBUGS-9", "regression_ids": [5], "status": "done"},
                {"type": "create_triage", "jira": "OCPBUGS-9", "regression_ids": [6], "status": "done"}]
        self.assertEqual(audit.diff_triages(snap({}), snap({"7": self.created([5, 6])}), decl)["status"], "match")

    def test_key_only_declaration_covers_exactly_one_creation(self):
        decl = [{"type": "create_triage", "jira": "OCPBUGS-9", "regression_ids": [5], "status": "done"}]
        r = audit.diff_triages(snap({}), snap({"7": self.created([5]), "8": self.created([5])}), decl)
        self.assertEqual(r["status"], "mismatch")      # the duplicate triage for the same bug is undeclared
        self.assertEqual(len(r["undeclared"]), 1)


class DiffReviewWave3Tests(AuditFetchTests):
    """Review wave 3: W2-1 — each declaration group resolves to exactly one physical creation."""

    def created(self, ids, key="OCPBUGS-9"):
        return tri(ids, url="https://j/browse/" + key)

    def test_key_only_members_are_not_consumed_twice(self):
        decl = [{"type": "create_triage", "triage_id": 7, "jira": "OCPBUGS-9", "regression_ids": [5], "status": "done"},
                {"type": "create_triage", "jira": "OCPBUGS-9", "regression_ids": [6], "status": "done"}]
        after = snap({"7": self.created([5, 6]), "8": self.created([6])})
        r = audit.diff_triages(snap({}), after, decl)
        self.assertEqual(r["status"], "mismatch")
        self.assertEqual([o["triage_id"] for o in r["undeclared"]], ["8"])

    def test_conflicting_keys_for_one_returned_id_are_rejected(self):
        decl = [{"type": "create_triage", "triage_id": 7, "jira": "OCPBUGS-9", "regression_ids": [5], "status": "done"},
                {"type": "create_triage", "triage_id": 7, "jira": "TRT-1", "regression_ids": [6], "status": "done"}]
        r = audit.diff_triages(snap({}), snap({"7": self.created([5, 6])}), decl)
        self.assertEqual(r["status"], "mismatch")

    def test_key_only_group_prefers_the_explicitly_declared_triage(self):
        decl = [{"type": "create_triage", "triage_id": 8, "jira": "OCPBUGS-9", "regression_ids": [5], "status": "done"},
                {"type": "create_triage", "jira": "OCPBUGS-9", "regression_ids": [6], "status": "done"}]
        # created 7 (lower id) for the same key is NOT where the key-only cluster's ids went: 8 holds 5 and 6
        r = audit.diff_triages(snap({}), snap({"7": self.created([9]), "8": self.created([5, 6])}), decl)
        self.assertEqual(r["status"], "mismatch")
        self.assertEqual([o["triage_id"] for o in r["undeclared"]], ["7"])
        r = audit.diff_triages(snap({}), snap({"8": self.created([5, 6])}), decl)
        self.assertEqual(r["status"], "match")


W = ("2026-10-12T01:00:00Z", "2026-10-12T02:00:00Z")


class JqlTests(unittest.TestCase):
    def test_jql_failure_is_unknown_not_zero(self):
        def bad(jql, tok=None):
            raise OSError("net")
        r = audit.jql_creations(*W, "bot", search=bad)
        self.assertEqual(r["status"], "unknown")
        self.assertIsNone(r["count"])
        self.assertIn("net", r["error"])

    def test_anonymous_fallback_header_is_unknown_not_zero(self):
        # Jira Cloud answers 200 + X-Seraph-LoginReason: AUTHENTICATED_FAILED for bad basic auth and
        # silently falls back to anonymous; that must never count as a clean audit.
        class Resp:
            headers = {"X-Seraph-LoginReason": "AUTHENTICATED_FAILED"}
            def read(self): return b'{"issues": [], "isLast": true}'
            def __enter__(self): return self
            def __exit__(self, *a): return False
        with mock.patch.dict(os.environ, {"JIRA_USERNAME": "u", "JIRA_API_TOKEN": "t"}), \
             mock.patch("urllib.request.urlopen", return_value=Resp()):
            r = audit.jql_creations(*W, "bot")
        self.assertEqual(r["status"], "unknown")
        self.assertIsNone(r["count"])
        self.assertIn("authentic", r["error"].lower())

    def test_myself_401_is_unknown_not_zero(self):
        import urllib.error
        def urlopen(req, timeout=None):
            if req.full_url.endswith("/rest/api/3/myself"):
                raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)
            raise AssertionError("search must not be attempted when /myself fails")
        with mock.patch.dict(os.environ, {"JIRA_USERNAME": "u", "JIRA_API_TOKEN": "t"}), \
             mock.patch("urllib.request.urlopen", side_effect=urlopen):
            r = audit.jql_creations(*W, "bot")
        self.assertEqual(r["status"], "unknown")
        self.assertIsNone(r["count"])
        self.assertIn("401", r["error"])

    def test_nonterminal_page_without_token_is_unknown_not_complete_zero(self):
        r = audit.jql_creations(*W, "bot", search=lambda *_: {"issues": [], "isLast": False})
        self.assertEqual(r["status"], "unknown")
        self.assertIsNone(r["count"])
        r = audit.jql_creations(*W, "bot", search=lambda *_: {"issues": []})  # no isLast, no token
        self.assertEqual(r["status"], "unknown")
        r = audit.jql_creations(*W, "bot", search=lambda *_: {"issues": [], "isLast": True})
        self.assertEqual((r["status"], r["count"]), ("ok", 0))

    def test_missing_credentials_unknown(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            r = audit.jql_creations(*W, "bot")
        self.assertEqual(r["status"], "unknown")
        self.assertIsNone(r["count"])

    def test_window_filter_and_offsets(self):
        page = {"isLast": True, "issues": [
            issue("IN-1", "2026-10-12T01:30:00.904+0000"),
            issue("IN-2", "2026-10-12T03:15:00+02:00"),
            issue("IN-3", "2026-10-12T01:45:00Z"),
            issue("OUT-1", "2026-10-11T20:00:00.5+0000")]}
        seen = []

        def search(jql, tok=None):
            seen.append(jql)
            return page
        r = audit.jql_creations(*W, "bot", search=search)
        self.assertEqual([i["key"] for i in r["issues"]], ["IN-1", "IN-2", "IN-3"])
        self.assertEqual((r["count"], r["raw_matched"], r["truncated"]), (3, 4, False))
        self.assertIn('created >= "2026-10-11 01:00"', seen[0])
        self.assertIn('created <= "2026-10-13 02:00"', seen[0])

    def test_pagination_follows_token(self):
        pages = [{"isLast": False, "nextPageToken": "t1", "issues": [issue("A-1", "2026-10-12T01:10:00Z")]},
                 {"isLast": True, "issues": [issue("A-2", "2026-10-12T01:20:00Z")]}]
        toks = []

        def search(jql, tok=None):
            toks.append(tok)
            return pages[len(toks) - 1]
        r = audit.jql_creations(*W, "bot", search=search)
        self.assertEqual(toks, [None, "t1"])
        self.assertEqual(r["count"], 2)
        self.assertFalse(r["truncated"])

    def test_pagination_cap_sets_truncated(self):
        n = []

        def search(jql, tok=None):
            n.append(1)
            return {"isLast": False, "nextPageToken": "t", "issues": [issue("A-%d" % len(n), "2026-10-12T01:10:00Z")]}
        r = audit.jql_creations(*W, "bot", search=search)
        self.assertEqual(len(n), 10)
        self.assertTrue(r["truncated"])
        self.assertEqual(r["count"], 10)

    def test_jql_builds_exact_string_and_auth_header(self):
        self.assertEqual(
            audit.build_jql("2026-10-12T01:05:59Z", "2026-10-12T02:00:00+00:00", "bot"),
            'reporter = "bot" AND created >= "2026-10-12 01:05" AND created <= "2026-10-12 02:00" ORDER BY created ASC')
        h = audit.build_auth_header("u", "t")
        self.assertEqual(h, "Basic " + base64.b64encode(b"u:t").decode())

    def test_jql_non_utc_offset_converts_and_reporter_escaped(self):
        q = audit.build_jql("2026-10-12T03:00:00+02:00", "2026-10-12T04:00:00+0200", 'a"b\\c')
        self.assertIn('reporter = "a\\"b\\\\c"', q)
        self.assertIn('created >= "2026-10-12 01:00"', q)
        self.assertIn('created <= "2026-10-12 02:00"', q)


class ReceiptTests(unittest.TestCase):
    def rc(self, jira=None, diff=None, run="r1"):
        return {"run_id": run, "audit": {
            "jira_creations": jira or {"status": "ok", "count": 0},
            "sippy_catalog_diff": diff or {"status": "match", "undeclared": []}}}

    def test_receipt_with_creation_forces_report(self):
        d, origin, why = audit.read_receipt_decision(self.rc(jira={"status": "ok", "count": 1, "issues": [{"key": "A-1"}]}))
        self.assertEqual((d, origin), ("report", "r1"))
        self.assertIn("A-1", why)

    def test_receipt_ack_restores_configured(self):
        rc = self.rc(jira={"status": "ok", "count": 1, "issues": []})
        d, origin, why = audit.read_receipt_decision(rc, ack_run_id="r1")
        self.assertEqual((d, origin), ("configured", ""))
        self.assertIn("r1", why)

    def test_missing_receipt_forces_report(self):
        self.assertEqual(audit.read_receipt_decision(None),
                         ("report", "", "no receipt from the latest preceding attempt"))

    def test_malformed_receipt(self):
        self.assertEqual(audit.read_receipt_decision({"run_id": "x"})[0], "report")
        self.assertTrue(audit.read_receipt_decision([])[2].startswith("receipt unreadable"))

    def test_inherited_downgrade_forces_report_with_origin(self):
        # Run B was forced to report by A's violation; B's own audit is clean but carries the pending downgrade.
        rc = self.rc(run="rB")
        rc["downgrade"] = {"pending": True, "origin": "rA", "reason": "Jira issues created during previous run: X-1 (count 1)"}
        d, origin, why = audit.read_receipt_decision(rc)
        self.assertEqual((d, origin), ("report", "rA"))
        self.assertIn("inherited", why)
        self.assertIn("rA", why)

    def test_ack_of_origin_clears_inherited_downgrade(self):
        rc = self.rc(run="rB"); rc["downgrade"] = {"pending": True, "origin": "rA", "reason": "x"}
        self.assertEqual(audit.read_receipt_decision(rc, ack_run_id="rA")[0], "configured")

    def test_ack_of_clean_carrier_run_does_not_clear_inherited_downgrade(self):
        rc = self.rc(run="rB"); rc["downgrade"] = {"pending": True, "origin": "rA", "reason": "x"}
        d, origin, _ = audit.read_receipt_decision(rc, ack_run_id="rB")
        self.assertEqual((d, origin), ("report", "rA"))

    def test_carrier_failure_does_not_replace_inherited_origin(self):
        rc = self.rc(run="B", jira={"status": "unknown", "count": None, "error": "timeout"})
        rc["downgrade"] = {"pending": True, "origin": "A", "reason": "creation in A"}
        d, origin, why = audit.read_receipt_decision(rc, ack_run_id="B")
        self.assertEqual(d, "report")
        self.assertEqual(origin, "A")           # A is still outstanding after acking B
        self.assertIn("A", why)
        d, origin, _ = audit.read_receipt_decision(rc)
        self.assertEqual(d, "report")
        self.assertEqual(set(origin.split(",")), {"A", "B"})   # both outstanding, both propagated

    def test_ack_of_all_outstanding_origins_restores_configured(self):
        rc = self.rc(run="B", jira={"status": "ok", "count": 1, "issues": [{"key": "X-1"}]})
        rc["downgrade"] = {"pending": True, "origin": "A", "reason": "r"}
        self.assertEqual(audit.read_receipt_decision(rc, ack_run_id="A,B")[0], "configured")
        self.assertEqual(audit.read_receipt_decision(rc, ack_run_id="A")[0], "report")

    def test_malformed_or_incomplete_audit_is_never_clean(self):
        for jira, diff in (({}, {}),
                           ({"status": "ok", "count": None}, {"status": "match"}),
                           ({"status": "weird", "count": 0}, {"status": "match"}),
                           ({"status": "ok", "count": 0}, {"status": "weird"}),
                           ({"status": "ok", "count": 0}, {})):
            d, _, why = audit.read_receipt_decision({"run_id": "X", "audit": {"jira_creations": jira, "sippy_catalog_diff": diff}})
            self.assertEqual(d, "report", (jira, diff, why))

    def test_malformed_carrier_keeps_inherited_origins(self):
        bad = {"run_id": "B", "downgrade": {"pending": True, "origin": "A", "reason": "creation in A"},
               "audit": {"jira_creations": None, "sippy_catalog_diff": {"status": "match"}}}
        d, origin, why = audit.read_receipt_decision(bad)
        self.assertEqual(d, "report")
        self.assertEqual(set(origin.split(",")), {"A", "B"})     # A survives, B (unreadable audit) joins
        self.assertIn("A", why)
        bad["audit"] = "not a dict"
        self.assertEqual(set(audit.read_receipt_decision(bad)[1].split(",")), {"A", "B"})

    def test_negative_count_is_not_clean(self):
        rc = {"run_id": "X", "audit": {"jira_creations": {"status": "ok", "count": -1}, "sippy_catalog_diff": {"status": "match"}}}
        self.assertEqual(audit.read_receipt_decision(rc)[0], "report")

    def test_inherited_reasons_are_bounded_per_origin(self):
        # N9: a clean carrier chain must not grow the reason text; per-origin reasons stay bounded.
        rc = {"run_id": "C0", "downgrade": {"pending": True, "origins": ["A", "B"], "reason": "x" * 50,
                                            "reasons": {"A": "creation in A", "B": "mismatch in B"}},
              "audit": {"jira_creations": {"status": "ok", "count": 0}, "sippy_catalog_diff": {"status": "match"}}}
        lengths = []
        with tempfile.TemporaryDirectory() as t:
            for i in range(1, 13):
                d, origin, reason = audit.read_receipt_decision(rc)
                self.assertEqual((d, set(origin.split(","))), ("report", {"A", "B"}))
                lengths.append(len(reason))
                p = os.path.join(t, "r.json")
                audit.write_receipt(p, run_id="C%d" % i, mode_requested="auto", mode_effective="report",
                                    audit={"jira_creations": {"status": "ok", "count": 0}, "sippy_catalog_diff": {"status": "match"}},
                                    previous_run="C%d" % (i - 1),
                                    downgrade={"pending": True, "origins": origin.split(","), "reason": reason,
                                               "previous_receipt": rc})
                with open(p) as f:
                    rc = json.load(f)
                self.assertEqual(set(rc["downgrade"]["origins"]), {"A", "B"})
                self.assertIn("creation in A", rc["downgrade"]["reasons"]["A"])
        self.assertLess(max(lengths), 400)
        self.assertEqual(lengths[-1], lengths[1])        # stable, not growing

    def test_unreadable_latest_receipt_is_not_ackable_but_a_carried_one_is(self):
        # Rule (narrowed, wave 3): an unreadable receipt cannot be acknowledged while it IS the latest receipt;
        # once a later readable receipt carries it as an origin, a manager who reviewed that run may ack it.
        bad = {"run_id": "B", "downgrade": {"pending": True, "origins": ["A"], "reasons": {"A": "creation in A"}},
               "audit": {"jira_creations": None, "sippy_catalog_diff": {"status": "match"}}}
        self.assertEqual(audit.read_receipt_decision(bad, "A,B")[1], "B")
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "c.json")
            d, origin, reason = audit.read_receipt_decision(bad)
            audit.write_receipt(p, run_id="C", mode_requested="auto", mode_effective="report",
                                audit={"jira_creations": {"status": "ok", "count": 0}, "sippy_catalog_diff": {"status": "match"}},
                                previous_run="B", downgrade={"pending": True, "origins": origin.split(","), "reason": reason, "previous_receipt": bad})
            with open(p) as f:
                c = json.load(f)
        self.assertEqual(audit.read_receipt_decision(c)[1], "A,B")
        self.assertEqual(audit.read_receipt_decision(c, "A")[1], "B")
        self.assertEqual(audit.read_receipt_decision(c, "A,B")[0], "configured")

    def test_malformed_previous_receipt_never_blocks_receipt_write(self):
        prev = {"run_id": "B", "downgrade": "not an object",
                "audit": {"jira_creations": {"status": "unknown", "error": "timeout"}, "sippy_catalog_diff": {"status": "match"}}}
        with tempfile.TemporaryDirectory() as t:
            pp = os.path.join(t, "prev.json")
            with open(pp, "w") as f:
                json.dump(prev, f)
            for name, obj in (("j.json", {"status": "ok", "count": 0}), ("s.json", {"status": "match"})):
                with open(os.path.join(t, name), "w") as f:
                    json.dump(obj, f)
            out = os.path.join(t, "c.json")
            code = audit.main(["receipt-write", "--out", out, "--run-id", "C", "--mode-requested", "auto", "--mode-effective", "report",
                               "--jira-creations", os.path.join(t, "j.json"), "--sippy-diff", os.path.join(t, "s.json"),
                               "--downgrade-origin", "B", "--downgrade-reason", "Jira audit unknown", "--previous-receipt", pp])
            self.assertEqual(code, 0)
            with open(out) as f:
                c = json.load(f)
            self.assertEqual(c["downgrade"]["origins"], ["B"])
            # and a previous-receipt file that is not even JSON
            with open(pp, "w") as f:
                f.write("{ not json")
            code = audit.main(["receipt-write", "--out", out, "--run-id", "C", "--mode-requested", "auto", "--mode-effective", "report",
                               "--jira-creations", os.path.join(t, "j.json"), "--sippy-diff", os.path.join(t, "s.json"),
                               "--downgrade-origin", "B", "--previous-receipt", pp])
            self.assertEqual(code, 0)

    def test_write_receipt_records_downgrade(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "r.json")
            audit.write_receipt(p, run_id="rB", mode_requested="auto", mode_effective="report",
                                audit={"jira_creations": {"status": "ok", "count": 0}, "sippy_catalog_diff": {"status": "match"}},
                                previous_run="rA", downgrade={"pending": True, "origin": "rA", "reason": "x"})
            with open(p) as f:
                r = json.load(f)
            self.assertEqual(r["downgrade"], {"pending": True, "origin": "rA", "origins": ["rA"], "reasons": {"rA": "x"}, "reason": "rA: x"})
            audit.write_receipt(p, run_id="rC", mode_requested="auto", mode_effective="auto",
                                audit={"jira_creations": {"status": "ok", "count": 0}, "sippy_catalog_diff": {"status": "match"}},
                                previous_run="rB")
            with open(p) as f:
                self.assertIsNone(json.load(f)["downgrade"])

    def test_receipt_unknown_audit_forces_report(self):
        d, _, why = audit.read_receipt_decision(self.rc(jira={"status": "unknown", "count": None, "error": "no creds"}))
        self.assertEqual(d, "report")
        self.assertIn("unknown", why); self.assertIn("no creds", why)

    def test_mismatch_forces_report(self):
        d, _, why = audit.read_receipt_decision(self.rc(diff={"status": "mismatch", "undeclared": [{"kind": "created"}]}))
        self.assertEqual(d, "report")

    def test_receipt_truncated_jira_audit_forces_report(self):
        rc = self.rc(jira={"status": "ok", "count": 0, "truncated": True, "issues": []})
        rc["audit"]["sippy_catalog_diff"] = {"status": "match"}
        d, _, why = audit.read_receipt_decision(rc)
        self.assertEqual(d, "report")
        self.assertIn("truncated", why)
        rc["audit"]["jira_creations"]["truncated"] = False
        self.assertEqual(audit.read_receipt_decision(rc), ("configured", "", ""))
        rc["audit"]["jira_creations"]["truncated"] = True
        self.assertEqual(audit.read_receipt_decision(rc, ack_run_id="r1")[0], "configured")

    def test_ack_does_not_override_missing_or_malformed(self):
        self.assertEqual(audit.read_receipt_decision(None, "r1")[0], "report")
        self.assertEqual(audit.read_receipt_decision({"run_id": "r1"}, "r1")[0], "report")

    def test_clean_receipt_configured(self):
        self.assertEqual(audit.read_receipt_decision(self.rc()), ("configured", "", ""))

    def test_write_receipt_shape(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "r.json")
            audit.write_receipt(p, run_id="r", mode_requested="a", mode_effective="b",
                                audit={"jira_creations": {}, "sippy_catalog_diff": {}}, previous_run=None)
            d = jload(p)
        self.assertEqual(d["schema_version"], "1.0")
        self.assertEqual(set(d["audit"]), {"jira_creations", "sippy_catalog_diff"})
        self.assertIn("written_at", d)


class PermissionsTests(unittest.TestCase):
    def test_permissions_records_create_flag_per_project(self):
        def fetch(project):
            return {"permissions": {"CREATE_ISSUES": {"havePermission": project != "TRT"},
                                    "EDIT_ISSUES": {"havePermission": True},
                                    "BROWSE_PROJECTS": {"havePermission": True}}}
        r = audit.permissions(["OCPBUGS", "TRT"], fetch=fetch)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["projects"], ["OCPBUGS", "TRT"])
        self.assertEqual(r["create_issues"], True)   # any project with create → True (write-capable token)
        self.assertEqual(r["edit_issues"], True)
        self.assertEqual(r["per_project"]["TRT"]["CREATE_ISSUES"], False)

    def test_permissions_missing_observations_stay_unknown(self):
        r = audit.permissions(["OCPBUGS"], fetch=lambda _: {})
        self.assertNotEqual(r["status"], "ok")
        self.assertIsNone(r["create_issues"]); self.assertIsNone(r["edit_issues"])
        self.assertIsNone(r["per_project"]["OCPBUGS"]["CREATE_ISSUES"])

    def test_permissions_failure_is_unknown(self):
        def fetch(project):
            raise OSError("boom")
        r = audit.permissions(["OCPBUGS"], fetch=fetch)
        self.assertEqual(r["status"], "unknown")
        self.assertIsNone(r["create_issues"])
        self.assertIn("boom", r["error"])


class CliTests(AuditFetchTests):
    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = audit.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_receipt_decide_cli_prints_decision_and_reason(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "r.json")
            jdump({"run_id": "r1", "audit": {
                "jira_creations": {"status": "ok", "count": 2, "issues": [{"key": "A-1"}]},
                "sippy_catalog_diff": {"status": "match"}}}, p)
            code, out, _ = self.run_cli(["receipt-decide", "--receipt", p])
            self.assertEqual(code, 0)
            self.assertTrue(out.startswith("report\tr1\t"), out)
            code, out, _ = self.run_cli(["receipt-decide", "--receipt", p, "--ack", "r1"])
            self.assertTrue(out.startswith("configured\t\t"), out)

    def test_receipt_decide_missing_file(self):
        code, out, _ = self.run_cli(["receipt-decide", "--receipt", "/nonexistent/x"])
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("report\t"))

    def test_diff_cli(self):
        with tempfile.TemporaryDirectory() as t:
            def w(n, o):
                p = os.path.join(t, n)
                jdump(o, p)
                return p
            b = w("b", snap({"1": tri([1])}))
            a = w("a", snap({"1": tri([1, 2])}))
            m = w("m", {"clusters": [{"actions": [
                {"type": "extend_triage", "triage_id": 1, "regression_ids": [2], "status": "done"}]}]})
            o = os.path.join(t, "o")
            code, out, _ = self.run_cli(["diff", "--before", b, "--after", a, "--manifest", m, "--out", o])
            self.assertEqual((code, out.strip()), (0, "match"))

    def test_diff_cli_tolerates_malformed_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            def w(n, o):
                p = os.path.join(t, n)
                jdump(o, p)
                return p
            b = w("b", snap({}))
            for man in ({"clusters": 5}, {"clusters": [{"actions": "x"}, 3]}, []):
                m = w("m", man)
                code, out, err = self.run_cli(["diff", "--before", b, "--after", b, "--manifest", m,
                                               "--out", os.path.join(t, "o")])
                self.assertEqual((code, out.strip()), (0, "match"))

    def test_decide_output_is_single_tab_line(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "r.json")
            jdump({"run_id": "r", "audit": {"jira_creations": {"status": "unknown", "error": "a\tb\nc"},
                                            "sippy_catalog_diff": {"status": "match"}}}, p)
            _, out, _ = self.run_cli(["receipt-decide", "--receipt", p])
            self.assertEqual(out.count("\t"), 2)
            self.assertEqual(len(out.splitlines()), 1)

    def test_diff_cli_bad_json_exits_1(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "bad")
            with open(p, "w") as f:
                f.write("{")
            code, _, err = self.run_cli(["diff", "--before", p, "--after", p, "--manifest", p,
                                         "--out", os.path.join(t, "o")])
            self.assertEqual(code, 1)
            self.assertEqual(len(err.strip().splitlines()), 1)

    def test_jql_cli_writes_unknown_on_failure(self):
        with tempfile.TemporaryDirectory() as t:
            o = os.path.join(t, "o")
            with mock.patch.dict(os.environ, {}, clear=True):
                code, _, _ = self.run_cli(["jql", "--start", "2026-10-12T01:00:00Z",
                                           "--end", "2026-10-12T02:00:00Z", "--reporter", "b", "--out", o])
            self.assertEqual(code, 0)
            self.assertEqual(jload(o)["status"], "unknown")


if __name__ == '__main__':
    unittest.main()
