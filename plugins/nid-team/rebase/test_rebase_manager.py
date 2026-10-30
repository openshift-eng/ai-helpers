"""Synthetic local Git/state contracts; no network or historical replay."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("rebase_manager.py")


def digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class RebaseManagerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rebase-manager-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.state_dir = self.root / "state"
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1",
                        GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_AUTHOR_NAME="Test Author",
                        GIT_AUTHOR_EMAIL="author@example.invalid",
                        GIT_COMMITTER_NAME="Test Committer",
                        GIT_COMMITTER_EMAIL="committer@example.invalid")
        self.git("init", "-b", "main")
        self.base = self.commit("source.txt", "base\n", "Base release")
        self.git("tag", "v1.0.0")
        self.git("checkout", "-b", "downstream")
        self.carry = self.commit("downstream.txt", "carry\n", "Downstream change")
        self.git("checkout", "-b", "upstream", self.base)
        self.upstream = self.commit("source.txt", "upstream\n", "Upstream release")
        self.git("tag", "v1.1.0")
        self.git("checkout", "downstream")
        self.plan = {
            "schema_version": 1,
            "repo": str(self.repo),
            "downstream_ref": "downstream",
            "downstream_sha": self.carry,
            "upstream_tag": "v1.1.0",
            "upstream_sha": self.upstream,
            "previous_upstream_sha": self.base,
            "branch": "rebase-v1.1.0",
            "carries": [{
                "id": "carry-1", "source_sha": self.carry,
                "action": "cherry-pick", "rationale": "Preserve downstream behavior",
            }],
            "tree_deltas": [{
                "path": "downstream.txt", "status": "A",
                "disposition": "retain", "rationale": "Accounted for by carry-1",
            }],
            "validations": [{"id": "unit", "command": "python3 -m unittest",
                             "required": True}],
        }

    def git(self, *args):
        result = subprocess.run(["git", *args], cwd=self.repo, env=self.env,
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def commit(self, path, content, message):
        (self.repo / path).write_text(content)
        self.git("add", path)
        self.git("commit", "-m", message)
        return self.git("rev-parse", "HEAD")

    def write_json(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value))
        return str(path)

    def cli(self, *args, success=True):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--state-dir", str(self.state_dir), *args],
            cwd=self.repo, env=self.env, text=True, capture_output=True, timeout=15)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def initialize(self):
        self.cli("init", "--plan", self.write_json("input-plan.json", self.plan))

    def create_candidate(self):
        self.git("checkout", "-b", self.plan["branch"], self.upstream)
        self.git("merge", "--no-ff", "-s", "ours", "downstream", "-m", "Merge baseline")
        self.git("cherry-pick", self.carry)
        self.picked = self.git("rev-parse", "HEAD")
        return self.picked

    def result(self, head=None):
        return {"plan_sha256": digest(self.plan),
                "head_sha": head or self.git("rev-parse", "HEAD"),
                "carries": [{"id": "carry-1", "result_sha": self.picked,
                             "outcome": "picked", "rationale": "Replayed downstream change"}],
                "repairs": []}

    def applied(self):
        self.initialize()
        self.create_candidate()
        self.cli("advance", "--to", "applied", "--result",
                 self.write_json("result.json", self.result()))

    def record(self, gate, verdict="PASS", head=None, **changes):
        head = head or self.git("rev-parse", "HEAD")
        log = self.root / (gate + ".log")
        log.write_text(f"HEAD: {head}\nSynthetic {gate}: {verdict}\n")
        evidence = {"plan_sha256": digest(self.plan), "head_sha": head,
                    "verdict": verdict, "log": str(log),
                    "rationale": "Synthetic check observed the stated result"}
        evidence.update(changes)
        return self.cli("record", "--gate", gate, "--evidence",
                        self.write_json(gate + ".json", evidence))

    def record_all(self):
        for gate in ("carry-accounting", "tree-accounting", "review", "unit"):
            self.record(gate)

    def validated(self):
        self.applied()
        self.record_all()
        self.cli("advance", "--to", "validated")

    def snapshot(self, **changes):
        value = {"number": 42, "url": "https://github.com/example/downstream/pull/42",
                 "target_repository": "example/downstream", "base_ref": "downstream",
                 "head_ref": self.plan["branch"],
                 "head_sha": self.git("rev-parse", "HEAD"),
                 "state": "OPEN", "draft": True}
        value.update(changes)
        return self.write_json("pr-snapshot.json", value)

    def feedback(self, body="Please explain this carry"):
        event = {"id": "issue:12", "body": body,
                 "url": "https://github.com/example/downstream/pull/42#issuecomment-12",
                 "updated_at": "2026-10-30T12:00:00Z"}
        return self.cli("feedback", "--input", self.write_json("feedback.json", [event]))

    def test_init_is_idempotent_without_losing_recorded_progress(self):
        self.applied()
        before = (self.state_dir / "state.json").read_bytes()
        self.initialize()
        self.assertEqual((self.state_dir / "state.json").read_bytes(), before)

    def test_init_accepts_initial_plan_in_the_state_directory(self):
        self.state_dir.mkdir()
        plan_path = self.state_dir / "plan.json"
        plan_path.write_text(json.dumps(self.plan))
        status = json.loads(self.cli("init", "--plan", str(plan_path)).stdout)
        self.assertEqual(status["phase"], "planned")
        self.assertEqual(status["plan_sha256"], digest(self.plan))
        self.assertEqual(json.loads(plan_path.read_text()), self.plan)

    def test_carry_must_be_accounted_for_before_applied(self):
        self.initialize()
        self.create_candidate()
        incomplete = self.result()
        incomplete["carries"] = []
        self.cli("advance", "--to", "applied", "--result",
                 self.write_json("result.json", incomplete), success=False)

    def test_original_carry_ancestry_does_not_prove_a_replayed_patch(self):
        self.initialize()
        self.git("checkout", "-b", self.plan["branch"], self.upstream)
        self.git("merge", "--no-ff", "-s", "ours", "downstream", "-m", "Merge baseline")
        self.git("merge-base", "--is-ancestor", self.carry, "HEAD")
        self.assertFalse((self.repo / "downstream.txt").exists())
        self.picked = self.carry
        self.cli("advance", "--to", "applied", "--result",
                 self.write_json("result.json", self.result()), success=False)

    def test_undecided_carry_cannot_advance(self):
        self.plan["carries"][0]["action"] = "undecided"
        self.initialize()
        self.create_candidate()
        self.cli("advance", "--to", "applied", "--result",
                 self.write_json("result.json", self.result()), success=False)

    def test_explicit_drop_is_accounted_without_a_result_commit(self):
        self.plan["carries"][0]["action"] = "drop"
        self.plan["carries"][0]["rationale"] = "Obsolete downstream behavior"
        self.plan["tree_deltas"][0]["disposition"] = "drop"
        self.initialize()
        self.git("checkout", "-b", self.plan["branch"], self.upstream)
        self.git("merge", "--no-ff", "-s", "ours", "downstream", "-m", "Merge baseline")
        result = {"plan_sha256": digest(self.plan), "head_sha": self.git("rev-parse", "HEAD"),
                  "carries": [{"id": "carry-1", "result_sha": None, "outcome": "dropped",
                               "rationale": "Obsolete downstream behavior"}], "repairs": []}
        self.cli("advance", "--to", "applied", "--result",
                 self.write_json("result.json", result))

    def test_required_gates_and_failures_block_validation(self):
        self.applied()
        for gate in ("carry-accounting", "tree-accounting", "review"):
            self.record(gate)
        self.cli("advance", "--to", "validated", success=False)
        for verdict in ("FAIL", "INCONCLUSIVE", "SKIP"):
            with self.subTest(verdict=verdict):
                self.record("unit", verdict)
                self.cli("advance", "--to", "validated", success=False)
        self.record("unit")
        self.cli("advance", "--to", "validated")

    def test_new_commit_invalidates_old_evidence(self):
        self.applied()
        self.record_all()
        self.commit("source.txt", "new repair\n", "Repair")
        self.cli("advance", "--to", "validated", success=False)

    def test_changed_result_invalidates_evidence_even_at_the_same_head(self):
        self.applied()
        self.record_all()
        result = self.result()
        result["carries"][0]["rationale"] = "Corrected carry-accounting explanation"
        self.cli("advance", "--to", "applied", "--result",
                 self.write_json("result.json", result))
        self.cli("advance", "--to", "validated", success=False)
        self.record_all()
        self.cli("advance", "--to", "validated")

    def test_dirty_checkout_cannot_validate(self):
        self.applied()
        self.record_all()
        self.cli("advance", "--to", "validated")
        (self.repo / "source.txt").write_text("uncommitted repair\n")
        status = json.loads(self.cli("status").stdout)
        self.assertEqual(status["phase"], "validated")
        self.assertTrue(status["checkout_problem"])
        self.cli("advance", "--to", "validated", success=False)

    def test_clean_index_with_unfinished_cherry_pick_cannot_validate(self):
        self.applied()
        self.record_all()
        marker = Path(self.git("rev-parse", "--git-path", "CHERRY_PICK_HEAD"))
        if not marker.is_absolute():
            marker = self.repo / marker
        marker.write_text(self.carry + "\n")
        self.assertEqual(self.git("status", "--porcelain"), "")
        status = json.loads(self.cli("status").stdout)
        self.assertTrue(status["checkout_problem"])
        self.cli("advance", "--to", "validated", success=False)

    def test_changed_plan_cannot_reuse_existing_evidence(self):
        self.applied()
        self.record_all()
        modified = dict(self.plan, branch="different-target")
        (self.state_dir / "plan.json").write_text(json.dumps(modified))
        self.cli("advance", "--to", "validated", success=False)

    def test_missing_log_is_rejected(self):
        self.applied()
        evidence = {"plan_sha256": digest(self.plan), "head_sha": self.picked,
                    "verdict": "PASS", "log": str(self.root / "missing.log"),
                    "rationale": "Claim without retained output"}
        self.cli("record", "--gate", "unit", "--evidence",
                 self.write_json("missing-log.json", evidence), success=False)

    def test_changed_log_invalidates_recorded_evidence(self):
        self.applied()
        self.record_all()
        (self.root / "unit.log").write_text("Replacement output\n")
        self.cli("advance", "--to", "validated", success=False)

    def test_feedback_is_not_completed_by_receipt_and_duplicate_receipt_is_stable(self):
        self.validated()
        self.cli("sync-pr", "--input", self.snapshot())
        self.feedback()
        first = (self.state_dir / "state.json").read_bytes()
        self.feedback()
        self.assertEqual((self.state_dir / "state.json").read_bytes(), first)
        self.cli("sync-pr", "--input", self.snapshot(draft=False), success=False)
        self.cli("resolve-feedback", "--id", "issue:12", "--outcome", "no-change",
                 "--rationale", "Existing carry rationale answers this request")
        self.cli("sync-pr", "--input", self.snapshot(draft=False))
        self.feedback("Please remove the carry instead")
        self.cli("sync-pr", "--input", self.snapshot(draft=False), success=False)

    def test_draft_can_bootstrap_ci_but_cannot_bypass_readiness(self):
        self.applied()
        for gate in ("carry-accounting", "tree-accounting", "review"):
            self.record(gate)
        self.record("unit", "INCONCLUSIVE")
        self.cli("sync-pr", "--input", self.snapshot())
        state = json.loads((self.state_dir / "state.json").read_text())
        self.assertEqual(state["phase"], "draft")
        self.cli("sync-pr", "--input", self.snapshot(draft=False), success=False)
        self.record("unit")
        self.cli("sync-pr", "--input", self.snapshot(draft=False))

    def test_addressed_feedback_needs_a_new_validated_revision(self):
        self.validated()
        self.cli("sync-pr", "--input", self.snapshot())
        self.feedback("Please change the downstream text")
        self.cli("resolve-feedback", "--id", "issue:12", "--outcome", "addressed",
                 "--rationale", "Changed the downstream text", success=False)
        repair = self.commit("downstream.txt", "repaired\n", "Address requested change")
        self.cli("resolve-feedback", "--id", "issue:12", "--outcome", "addressed",
                 "--rationale", "Changed the downstream text", success=False)
        result = self.result()
        result["repairs"] = [{"result_sha": repair, "rationale": "Address issue:12"}]
        self.cli("advance", "--to", "applied", "--result",
                 self.write_json("result.json", result))
        self.record_all()
        self.cli("advance", "--to", "validated")
        self.cli("resolve-feedback", "--id", "issue:12", "--outcome", "addressed",
                 "--rationale", "Changed the downstream text and validated the repair")

    def test_merged_pr_is_recognized_using_saved_identity(self):
        self.validated()
        self.cli("sync-pr", "--input", self.snapshot())
        self.cli("sync-pr", "--input", self.snapshot(state="MERGED", draft=False))
        state = json.loads((self.state_dir / "state.json").read_text())
        self.assertIn("complete", state.values())
        self.assertTrue((self.state_dir / "plan.json").exists())

    def test_merged_remote_revision_preserves_local_validation_provenance(self):
        self.validated()
        candidate = self.git("rev-parse", "HEAD")
        self.cli("sync-pr", "--input", self.snapshot())
        self.git("checkout", "-b", "remote-human", candidate)
        remote_head = self.commit("source.txt", "remote fix\n", "Remote human fix")
        self.git("branch", "-f", "downstream", remote_head)
        self.git("checkout", self.plan["branch"])

        self.cli("sync-pr", "--input", self.snapshot(head_sha=remote_head), success=False)
        status = json.loads(self.cli("sync-pr", "--input", self.snapshot(
            state="MERGED", draft=False, head_sha=remote_head)).stdout)
        state = json.loads((self.state_dir / "state.json").read_text())
        self.assertEqual(state["phase"], "complete")
        self.assertEqual(state["head_sha"], candidate)
        self.assertEqual(state["pr"]["head_sha"], remote_head)
        self.assertTrue(status["pr_head_differs"])
        self.assertEqual({gate["head_sha"] for gate in state["gates"].values()}, {candidate})

    def test_downstream_advance_blocks_readiness_for_old_candidate(self):
        self.validated()
        self.cli("sync-pr", "--input", self.snapshot())
        self.git("checkout", "downstream")
        self.commit("new-downstream.txt", "new carry\n", "New downstream change")
        self.git("checkout", self.plan["branch"])
        self.cli("sync-pr", "--input", self.snapshot(draft=False), success=False)

    def test_unrelated_pr_cannot_replace_saved_identity(self):
        self.validated()
        self.cli("sync-pr", "--input", self.snapshot())
        self.cli("sync-pr", "--input", self.snapshot(
            number=43, url="https://github.com/example/downstream/pull/43"), success=False)


if __name__ == "__main__":
    unittest.main()
