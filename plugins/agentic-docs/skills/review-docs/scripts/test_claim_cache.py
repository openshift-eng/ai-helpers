"""Behavioral tests for immutable storage, provenance and conservative delta reuse."""

import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from claim_cache import Cache, digest


class ClaimCacheTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        (self.repo / "doc.md").write_text("Heading\nClaim A\nContext\nClaim B\n")
        (self.repo / "source.txt").write_text("source v1\n")
        self.git("add", ".")
        self.git("commit", "-qm", "baseline")
        self.cache = Cache(self.root / "cache")
        self.inventory = {"documents": ["doc.md"], "coverage_complete": True, "claims": [
            {"id": name, "assertion": "Claim " + name.upper(), "kind": "behavior",
             "occurrences": [{"path": "doc.md", "start": line, "end": line}],
             "depends_on": [], "source_scope": [{"repository": "example/component",
                 "revision": self.git("rev-parse", "HEAD"), "path": "source.txt",
                 "local_root": str(self.repo)}]}
            for name, line in (("a", 2), ("b", 4))]}

    def git(self, *arguments):
        return subprocess.check_output(["git", "-C", str(self.repo), *arguments], text=True,
                                       stderr=subprocess.DEVNULL).strip()

    def snapshot(self, inventory=None, version="review-policy-v1"):
        return self.cache.snapshot(self.repo, inventory or self.inventory, version)

    def evidence(self, role="reviewer", excerpt="source v1"):
        return {"reviewer": "independent-pass-1" if role == "reviewer" else "fixer",
                "role": role, "evidence": [{"source": "source.txt", "excerpt": excerpt}]}

    def verified(self, snapshot=None):
        snapshot = snapshot or self.snapshot()
        for claim in self.inventory["claims"]:
            self.cache.put(snapshot, claim["id"], "verified", self.evidence())
        return snapshot

    def edit(self, text, a=2, b=4):
        (self.repo / "doc.md").write_text(text)
        for claim, line in zip(self.inventory["claims"], [a, b]):
            claim["occurrences"][0].update(start=line, end=line)

    def test_publication_is_idempotent_and_never_overwrites(self):
        first = self.snapshot()
        path = self.cache.root / "snapshots" / (first + ".json")
        original = path.stat().st_mtime_ns
        self.assertEqual(first, self.snapshot())
        self.assertEqual(original, path.stat().st_mtime_ns)
        self.assertEqual(0o400, path.stat().st_mode & 0o777)
        self.assertEqual([], list(path.parent.glob(".pending-*")))
        path.chmod(0o600)
        path.write_text("corruption")
        with self.assertRaisesRegex(ValueError, "collision or corrupt"):
            self.snapshot()
        self.assertEqual("corruption", path.read_text())

    def test_forced_hash_collision_is_detected(self):
        with patch("claim_cache.digest", return_value="a" * 64):
            self.cache.publish("snapshots", {"schema": 1, "x": 1})
            with self.assertRaisesRegex(ValueError, "collision"):
                self.cache.publish("snapshots", {"schema": 1, "x": 2})

    def test_first_pass_is_full_even_with_fixer_verdicts(self):
        snapshot = self.snapshot()
        self.cache.put(snapshot, "a", "verified", self.evidence("fixer"))
        plan = self.cache.plan(snapshot)
        self.assertEqual("full", plan["mode"])
        self.assertEqual({"a", "b"}, set(plan["reverify"]))
        self.assertEqual({}, plan["reusable"])

    def test_identical_complete_inventory_reuses_every_claim(self):
        baseline = self.verified()
        plan = self.cache.plan(self.snapshot(), baseline)
        self.assertEqual({}, plan["reverify"])
        self.assertEqual({"a", "b"}, set(plan["reusable"]))

    def test_prepended_lines_only_shift_occurrences(self):
        baseline = self.verified()
        self.edit("New heading\nHeading\nClaim A\nContext\nClaim B\n", a=3, b=5)
        current = self.snapshot()
        plan = self.cache.plan(current, baseline)
        self.assertEqual({}, plan["reverify"])
        self.assertEqual(["doc.md"], plan["changed_documents"])
        self.assertEqual("verified", self.cache.observations(current, "a")["status"])
        # A third pass must still resolve the original immutable observation.
        self.edit("Another heading\nNew heading\nHeading\nClaim A\nContext\nClaim B\n", a=4, b=6)
        third = self.snapshot()
        self.assertEqual({}, self.cache.plan(third, current)["reverify"])
        resolved = self.cache.observations(third, "a")["observations"]
        self.assertEqual(baseline, resolved[0]["snapshot"])

    def test_changed_line_reverifies_only_overlapping_claim(self):
        baseline = self.verified()
        self.edit("Heading\nChanged A\nContext\nClaim B\n")
        current = self.snapshot()
        self.cache.put(current, "a", "verified", self.evidence("fixer"))
        plan = self.cache.plan(current, baseline)
        self.assertEqual({"a": ["changed_lines"]}, plan["reverify"])
        self.assertEqual({"b"}, set(plan["reusable"]))

    def test_insert_inside_multiline_claim_reverifies(self):
        self.inventory["claims"][0]["occurrences"][0]["end"] = 3
        baseline = self.verified()
        self.edit("Heading\nClaim A\nNew detail\nContext\nClaim B\n", b=5)
        self.inventory["claims"][0]["occurrences"][0]["end"] = 4
        self.assertEqual({"a"}, set(self.cache.plan(self.snapshot(), baseline)["reverify"]))

    def test_delete_inside_claim_reverifies(self):
        self.inventory["claims"][0]["occurrences"][0]["end"] = 3
        baseline = self.verified()
        self.edit("Heading\nClaim A\nClaim B\n", b=3)
        self.assertEqual({"a"}, set(self.cache.plan(self.snapshot(), baseline)["reverify"]))

    def test_delete_outside_claim_is_shift_only(self):
        baseline = self.verified()
        self.edit("Claim A\nContext\nClaim B\n", a=1, b=3)
        self.assertEqual({}, self.cache.plan(self.snapshot(), baseline)["reverify"])

    def test_dependency_closure(self):
        self.inventory["claims"][1]["depends_on"] = ["a"]
        self.inventory["claims"].append({"id": "c", "assertion": "C", "kind": "behavior",
            "occurrences": [{"path": "doc.md", "start": 1, "end": 1}],
            "source_scope": copy.deepcopy(self.inventory["claims"][0]["source_scope"]),
            "depends_on": ["b"]})
        baseline = self.verified()
        (self.repo / "doc.md").write_text("Heading\nChanged A\nContext\nClaim B\n")
        plan = self.cache.plan(self.snapshot(), baseline)
        self.assertEqual({"a", "b", "c"}, set(plan["reverify"]))
        self.assertEqual(["changed_dependency"], plan["reverify"]["c"])

    def test_local_dependency_dirty_content_invalidates_same_head(self):
        baseline = self.verified()
        head = self.git("rev-parse", "HEAD")
        (self.repo / "source.txt").write_text("source v2\n")
        current = self.snapshot()
        self.assertEqual(head, self.git("rev-parse", "HEAD"))
        self.assertNotEqual(baseline, current)
        self.assertEqual({"a", "b"}, set(self.cache.plan(current, baseline)["reverify"]))

    def test_snapshot_inventory_roundtrip_refreshes_local_source_bytes(self):
        baseline = self.verified()
        stored = self.cache.read("snapshots", baseline)
        inventory = {"documents": list(stored["documents"]), "coverage_complete": True,
                     "claims": list(stored["claims"].values())}
        old_source = stored["claims"]["a"]["source_scope"][0]
        self.assertEqual(str(self.repo.resolve()), old_source["local_root"])
        (self.repo / "source.txt").write_text("source changed after handoff\n")
        current = self.snapshot(inventory)
        new_source = self.cache.read("snapshots", current)["claims"]["a"]["source_scope"][0]
        self.assertNotEqual(old_source["sha256"], new_source["sha256"])
        self.assertEqual({"a", "b"}, set(self.cache.plan(current, baseline)["reverify"]))

    def test_prompt_version_invalidates_all(self):
        baseline = self.verified()
        plan = self.cache.plan(self.snapshot(version="review-policy-v2"), baseline)
        self.assertEqual({"a", "b"}, set(plan["reverify"]))

    def test_commit_changes_context_but_unaffected_claims_reuse(self):
        baseline = self.verified()
        self.edit("New heading\nHeading\nClaim A\nContext\nClaim B\n", a=3, b=5)
        self.git("add", "doc.md")
        self.git("commit", "-qm", "documentation-only commit")
        for claim in self.inventory["claims"]:
            claim["source_scope"][0]["revision"] = self.git("rev-parse", "HEAD")
        current = self.snapshot()
        self.assertNotEqual(self.cache.context(self.cache.read("snapshots", baseline), "a"),
                            self.cache.context(self.cache.read("snapshots", current), "a"))
        plan = self.cache.plan(current, baseline)
        self.assertEqual({}, plan["reverify"])
        self.assertEqual({"a", "b"}, set(plan["reusable"]))
        self.assertEqual(baseline, self.cache.observations(current, "a")["observations"][0]["snapshot"])

    def test_documentation_commit_still_selects_changed_claim(self):
        baseline = self.verified()
        self.edit("Heading\nChanged A\nContext\nClaim B\n")
        self.git("add", "doc.md")
        self.git("commit", "-qm", "change documented claim")
        for claim in self.inventory["claims"]:
            claim["source_scope"][0]["revision"] = self.git("rev-parse", "HEAD")
        plan = self.cache.plan(self.snapshot(), baseline)
        self.assertEqual({"a": ["changed_lines"]}, plan["reverify"])
        self.assertEqual({"b"}, set(plan["reusable"]))

    def test_remote_revision_change_cannot_reuse_supplied_hash(self):
        for claim in self.inventory["claims"]:
            source = claim["source_scope"][0]
            source.pop("local_root")
            source["sha256"] = "b" * 64
        baseline = self.verified()
        for claim in self.inventory["claims"]:
            claim["source_scope"][0]["revision"] = "a" * 40
        self.assertEqual({"a", "b"}, set(self.cache.plan(self.snapshot(), baseline)["reverify"]))

    def test_local_scope_metadata_change_requires_verification(self):
        baseline = self.verified()
        self.inventory["claims"][0]["source_scope"][0]["repository"] = "different/component"
        self.assertEqual({"a": ["changed_source_scope"]},
                         self.cache.plan(self.snapshot(), baseline)["reverify"])

    def test_snapshot_roundtrip_with_stale_local_pin_fails(self):
        baseline = self.snapshot()
        stored = self.cache.read("snapshots", baseline)
        inventory = {"documents": list(stored["documents"]), "coverage_complete": True,
                     "claims": list(stored["claims"].values())}
        self.git("commit", "--allow-empty", "-qm", "new local revision")
        with self.assertRaisesRegex(ValueError, "HEAD differs"):
            self.snapshot(inventory)

    def test_added_and_removed_claims(self):
        baseline = self.verified()
        self.edit("Heading\nNew claim\nContext\nClaim B\n")
        self.inventory["claims"][0]["id"] = "new-a"
        plan = self.cache.plan(self.snapshot(), baseline)
        self.assertEqual(["a"], plan["removed"])
        self.assertEqual({"new-a"}, set(plan["reverify"]))
        self.assertEqual({"b"}, set(plan["reusable"]))

    def test_unchanged_claim_cannot_disappear_from_inventory(self):
        baseline = self.verified()
        self.inventory["claims"].pop(0)
        plan = self.cache.plan(self.snapshot(), baseline)
        self.assertEqual("full", plan["mode"])
        self.assertTrue(plan["extraction_required"])
        self.assertFalse(plan["coverage_complete"])
        self.assertEqual([], plan["removed"])
        self.assertEqual("inventory_drop_without_deleted_occurrence", plan["unresolved"]["a"])

    def test_renamed_document_is_conservatively_reverified(self):
        baseline = self.verified()
        (self.repo / "doc.md").rename(self.repo / "renamed.md")
        self.inventory["documents"] = ["renamed.md"]
        for claim in self.inventory["claims"]:
            claim["occurrences"][0]["path"] = "renamed.md"
        self.assertEqual({"a", "b"}, set(self.cache.plan(self.snapshot(), baseline)["reverify"]))

    def test_incomplete_baseline_forces_full(self):
        incomplete = copy.deepcopy(self.inventory)
        incomplete["coverage_complete"] = False
        baseline = self.snapshot(incomplete)
        self.assertEqual("full", self.cache.plan(self.snapshot(), baseline)["mode"])

    def test_incomplete_current_requires_extraction(self):
        baseline = self.verified()
        self.inventory["coverage_complete"] = False
        plan = self.cache.plan(self.snapshot(), baseline)
        self.assertTrue(plan["extraction_required"])
        self.assertEqual("full", plan["mode"])

    def test_missing_baseline_forces_full(self):
        plan = self.cache.plan(self.snapshot(), "f" * 64)
        self.assertEqual("full", plan["mode"])
        self.assertTrue(plan["baseline_error"])

    def test_corrupt_evidence_requires_reverification(self):
        baseline = self.verified()
        observation = self.cache.observations(baseline, "a")["observations"][0]
        path = self.cache.root / observation["group"] / (observation["id"] + ".json")
        path.chmod(0o600)
        path.write_text("{}")
        plan = self.cache.plan(self.snapshot(), baseline)
        self.assertEqual(["cache_error"], plan["reverify"]["a"])
        self.assertEqual({"b"}, set(plan["reusable"]))

    def test_valid_other_claim_record_cannot_authorize_reuse(self):
        baseline = self.verified()
        observation = self.cache.observations(baseline, "a")["observations"][0]
        source = self.cache.root / observation["group"] / (observation["id"] + ".json")
        target_group = "observations/" + self.cache.context(self.cache.read("snapshots", baseline), "b")
        (self.cache.root / target_group / source.name).write_bytes(source.read_bytes())
        self.assertEqual("cache_error", self.cache.observations(baseline, "b")["reason"])
        self.assertEqual(["cache_error"], self.cache.plan(self.snapshot(), baseline)["reverify"]["b"])

    def test_conflicting_statuses_preserve_both_and_require_reverification(self):
        baseline = self.verified()
        self.cache.put(baseline, "a", "failed", self.evidence())
        result = self.cache.observations(baseline, "a")
        self.assertEqual(2, len(result["observations"]))
        self.assertEqual("conflicting_evidence", result["reason"])
        self.assertIn("a", self.cache.plan(self.snapshot(), baseline)["reverify"])

    def test_conflicting_evidence_without_status_change_is_not_newest_wins(self):
        baseline = self.verified()
        self.cache.put(baseline, "a", "verified", self.evidence(excerpt="contradicting source"))
        self.assertEqual("unverified", self.cache.observations(baseline, "a")["status"])

    def test_failed_and_unknown_statuses_never_become_verified(self):
        baseline = self.snapshot()
        for identifier, status in (("a", "failed"), ("b", "unverified")):
            self.cache.put(baseline, identifier, status, self.evidence())
        plan = self.cache.plan(self.snapshot(), baseline)
        self.assertEqual({}, plan["reusable"])
        self.assertEqual({"a": "failed", "b": "unverified"}, plan["unresolved"])

    def test_fixer_only_evidence_is_readable_but_not_independent(self):
        baseline = self.snapshot()
        self.cache.put(baseline, "a", "verified", self.evidence("fixer"))
        result = self.cache.observations(baseline, "a")
        self.assertEqual(1, len(result["observations"]))
        self.assertEqual("missing_independent_evidence", result["reason"])
        self.assertIn("a", self.cache.plan(self.snapshot(), baseline)["reverify"])

    def test_fresh_reviewer_confirmation_reuses_fixer_raw_evidence(self):
        baseline = self.snapshot()
        self.cache.put(baseline, "a", "verified", self.evidence("fixer"))
        self.cache.put(baseline, "a", "verified", self.evidence("reviewer"))
        self.assertEqual("verified", self.cache.observations(baseline, "a")["status"])
        self.assertIn("a", self.cache.plan(self.snapshot(), baseline)["reusable"])

    def test_compact_replaces_verified_observations_and_keeps_failures(self):
        baseline = self.snapshot()
        verified_id = self.cache.put(baseline, "a", "verified", self.evidence())
        failed_id = self.cache.put(baseline, "b", "failed", self.evidence())
        verified_group = self.cache.observations(baseline, "a")["observations"][0]["group"]
        failed_group = self.cache.observations(baseline, "b")["observations"][0]["group"]

        result = self.cache.compact(baseline)

        self.assertEqual(1, result["verified_count"])
        self.assertEqual(1, result["retained_count"])
        self.assertEqual(["b"], result["retained"])
        self.assertFalse((self.cache.root / verified_group / (verified_id + ".json")).exists())
        self.assertTrue((self.cache.root / failed_group / (failed_id + ".json")).exists())
        compacted = self.cache.observations(baseline, "a")
        self.assertEqual("verified", compacted["status"])
        self.assertEqual([], compacted["observations"])
        self.assertEqual(1, len(compacted["receipts"]))
        self.assertEqual("failed", self.cache.observations(baseline, "b")["status"])
        plan = self.cache.plan(self.snapshot(), baseline)
        self.assertEqual({"a"}, set(plan["reusable"]))
        self.assertEqual({"b"}, set(plan["reverify"]))

    def test_compacted_receipts_carry_across_shifted_lines(self):
        baseline = self.verified()
        self.cache.compact(baseline)
        self.assertEqual([], list((self.cache.root / "observations").glob("*/*.json")))
        self.edit("New heading\nHeading\nClaim A\nContext\nClaim B\n", a=3, b=5)
        current = self.snapshot()

        plan = self.cache.plan(current, baseline)

        self.assertEqual({}, plan["reverify"])
        self.assertEqual({"a", "b"}, set(plan["reusable"]))
        self.assertEqual("verified", self.cache.observations(current, "a")["status"])
        self.assertEqual(1, len(self.cache.observations(current, "a")["receipts"]))

    def test_compact_is_idempotent(self):
        baseline = self.verified()
        first = self.cache.compact(baseline)
        second = self.cache.compact(baseline)
        self.assertEqual(2, first["removed_records"])
        self.assertEqual(0, second["removed_records"])
        self.assertEqual(first["verified_count"], second["verified_count"])
        self.assertEqual("verified", self.cache.observations(baseline, "a")["status"])

    def test_new_conflict_invalidates_compacted_receipt(self):
        baseline = self.verified()
        self.cache.compact(baseline)
        self.cache.put(baseline, "a", "failed", self.evidence())
        result = self.cache.observations(baseline, "a")
        self.assertEqual("unverified", result["status"])
        self.assertEqual("conflicting_evidence", result["reason"])
        self.assertIn("a", self.cache.plan(self.snapshot(), baseline)["reverify"])

    def test_independent_correction_supersedes_without_overwriting(self):
        baseline = self.snapshot()
        original = self.cache.put(baseline, "a", "failed", self.evidence("fixer"))
        original_files = {str(path): path.read_bytes() for path in self.cache.root.rglob("*.json")}
        correction = self.evidence("reviewer", excerpt="correctly inspected source")
        correction["supersedes"] = [original]
        self.cache.put(baseline, "a", "verified", correction)
        result = self.cache.observations(baseline, "a")
        self.assertEqual("verified", result["status"])
        self.assertEqual([original], result["superseded"])
        self.assertEqual(1, len(result["observations"]))
        for path, content in original_files.items():
            self.assertEqual(content, Path(path).read_bytes())

    def test_fixer_and_cross_context_supersession_rejected(self):
        baseline = self.snapshot()
        original = self.cache.put(baseline, "a", "failed", self.evidence())
        correction = self.evidence("fixer")
        correction["supersedes"] = [original]
        with self.assertRaisesRegex(ValueError, "only independent"):
            self.cache.put(baseline, "a", "verified", correction)
        correction["role"] = "reviewer"
        with self.assertRaises(FileNotFoundError):
            self.cache.put(baseline, "b", "verified", correction)

    def test_later_origin_conflict_invalidates_carried_evidence(self):
        baseline = self.verified()
        self.edit("New heading\nHeading\nClaim A\nContext\nClaim B\n", a=3, b=5)
        current = self.snapshot()
        self.cache.plan(current, baseline)
        self.cache.put(baseline, "a", "failed", self.evidence())
        self.assertEqual("conflicting_evidence", self.cache.observations(current, "a")["reason"])

    def test_fresh_reviewer_can_supersede_current_context_carry(self):
        baseline = self.verified()
        self.edit("New heading\nHeading\nClaim A\nContext\nClaim B\n", a=3, b=5)
        current = self.snapshot()
        self.cache.plan(current, baseline)
        result = self.cache.observations(current, "a")
        correction = self.evidence("reviewer", excerpt="new independently checked evidence")
        correction["supersedes"] = [result["carries"][0]["id"]]
        self.cache.put(current, "a", "failed", correction)
        updated = self.cache.observations(current, "a")
        self.assertEqual("failed", updated["status"])
        self.assertEqual([], updated["carries"])

    def test_new_claim_qualifier_invalidates_reuse(self):
        baseline = self.verified()
        self.inventory["claims"][0]["qualification"] = "Only during initialization"
        self.assertEqual(["changed_qualification"], self.cache.plan(self.snapshot(), baseline)["reverify"]["a"])

    def test_dependency_evidence_conflict_invalidates_dependent_claim(self):
        self.inventory["claims"][1]["depends_on"] = ["a"]
        baseline = self.verified()
        self.cache.put(baseline, "a", "failed", self.evidence())
        plan = self.cache.plan(self.snapshot(), baseline)
        self.assertEqual({"a", "b"}, set(plan["reverify"]))
        self.assertEqual({}, plan["reusable"])

    def test_transitive_dependency_provenance_changes_context(self):
        self.inventory["claims"][1]["depends_on"] = ["a"]
        self.inventory["claims"][1]["source_scope"] = []
        baseline = self.snapshot()
        old_key = self.cache.context(self.cache.read("snapshots", baseline), "b")
        (self.repo / "source.txt").write_text("source v2\n")
        current = self.snapshot()
        self.assertNotEqual(old_key, self.cache.context(self.cache.read("snapshots", current), "b"))

    def test_same_assertion_reassigned_to_different_context_has_distinct_key(self):
        baseline = self.snapshot()
        self.inventory["claims"][0]["occurrences"][0].update(start=3, end=3)
        current = self.snapshot()
        self.assertNotEqual(self.cache.context(self.cache.read("snapshots", baseline), "a"),
                            self.cache.context(self.cache.read("snapshots", current), "a"))
        self.assertEqual(["changed_occurrences"], self.cache.plan(current, baseline)["reverify"]["a"])

    def test_verified_requires_pinned_scope(self):
        self.inventory["claims"][0]["source_scope"] = []
        snapshot = self.snapshot()
        with self.assertRaisesRegex(ValueError, "pinned source_scope"):
            self.cache.put(snapshot, "a", "verified", self.evidence())

    def test_current_conflict_blocks_old_evidence_carry(self):
        baseline = self.verified()
        self.edit("New heading\nHeading\nClaim A\nContext\nClaim B\n", a=3, b=5)
        current = self.snapshot()
        self.cache.put(current, "a", "failed", self.evidence("fixer"))
        self.assertEqual(["conflicting_evidence"], self.cache.plan(current, baseline)["reverify"]["a"])

    def test_record_refuses_conversation_and_empty_verification(self):
        snapshot = self.snapshot()
        payload = self.evidence()
        payload["messages"] = ["fixer conversation"]
        with self.assertRaisesRegex(ValueError, "conversation"):
            self.cache.put(snapshot, "a", "verified", payload)
        payload = self.evidence()
        payload["evidence"] = []
        with self.assertRaisesRegex(ValueError, "source evidence"):
            self.cache.put(snapshot, "a", "verified", payload)

    def test_unpinned_source_and_stale_local_revision_are_rejected(self):
        self.inventory["claims"][0]["source_scope"][0]["revision"] = "main"
        with self.assertRaisesRegex(ValueError, "immutable revision"):
            self.snapshot()
        self.inventory["claims"][0]["source_scope"][0]["revision"] = "a" * 40
        with self.assertRaisesRegex(ValueError, "HEAD differs"):
            self.snapshot()

    def test_path_escape_and_unknown_dependencies_are_rejected(self):
        self.inventory["documents"] = ["../secret"]
        with self.assertRaisesRegex(ValueError, "relative"):
            self.snapshot()
        self.inventory["documents"] = ["doc.md"]
        self.inventory["claims"][0]["depends_on"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "unknown claim dependency"):
            self.snapshot()


if __name__ == "__main__":
    unittest.main()
