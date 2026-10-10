import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "investigation_queue.py"
SPEC = importlib.util.spec_from_file_location("investigation_queue", SCRIPT)
queue = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(queue)
NOW = datetime(2026, 10, 8, 18, tzinfo=timezone.utc)


def workspace(root, total=7, **scope_overrides):
    root.mkdir(parents=True)
    settings = {"release": "5.1", "architecture": "amd64", "stream": "nightly",
                "max_recommendations": 10, "max_candidates": 100, "time_budget_minutes": 120}
    settings.update(scope_overrides)
    manifest = {"schema_version": 1, "analysis_id": root.name, "stage": "RANKED",
                "selection_version": 1, "collected_at": queue.stamp(NOW), "effective_inputs": settings}
    cohorts = [{"cohort_id": "job-%d" % index, "rank": index, "population_role": "current",
                "release": "5.1", "architecture": "amd64", "stream": "nightly",
                "run_ids": [str(100 + index)], "metrics": {"unique_run_success": {"value": 0}}}
               for index in range(1, total + 1)]
    queue.write_json(root / "manifest.json", manifest)
    queue.write_json(root / "job-rankings.json", {"schema_version": 1, "selection_version": 1,
                     "current": cohorts, "previous_release_history": []})
    return root


def finding(root, cohort_id, status="COMPLETE_BOUNDED"):
    path = root / "findings" / (cohort_id + ".json")
    queue.write_json(path, {"schema_version": 1, "cohort_id": cohort_id,
        "investigation_status": status, "disposition": "INSUFFICIENT_EVIDENCE",
        "summary": "Setup failed; no supported repair was found.",
        "next_action": "Wait for catalogue evidence from the owner.",
        "revisit_condition": "Owner provides catalogue publication evidence."})
    return path


def complete(root, cohort_id):
    queue.begin(root, cohort_id, now=NOW)
    return queue.record(root, finding(root, cohort_id), now=NOW)


class InvestigationQueueTests(unittest.TestCase):
    def test_five_no_fix_investigations_advance_to_sixth_and_persist_across_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = workspace(Path(directory) / "first")
            queue.plan(root, now=NOW)
            for index in range(1, 6):
                state = complete(root, "job-%d" % index)
            self.assertEqual("job-6", state["queue"][0]["cohort_id"])
            self.assertEqual(5, len(state["attempted_cohorts"]))
            self.assertEqual(0, state["validated_recommendations"])
            self.assertIsNone(state["stop_reason"])
            fresh = workspace(Path(directory) / "second")
            state = queue.plan(fresh, now=NOW)
            self.assertEqual(["job-6", "job-7"], [item["cohort_id"] for item in state["queue"]])
            self.assertEqual(5, len(state["deferred"]))

    def test_changed_runs_queue_rechecks_after_pending_without_importing_new_diagnosis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = workspace(Path(directory) / "first", total=2)
            queue.plan(root, now=NOW)
            complete(root, "job-1")
            fresh = workspace(Path(directory) / "second", total=2)
            rankings = queue.read_json(fresh / "job-rankings.json")
            rankings["current"][0]["run_ids"] = ["new-run"]
            queue.write_json(fresh / "job-rankings.json", rankings)
            state = queue.plan(fresh, now=NOW)
            self.assertEqual(["job-2", "job-1"], [item["cohort_id"] for item in state["queue"]])
            self.assertEqual("RECHECK", state["queue"][1]["status"])
            self.assertFalse((fresh / "findings").exists())

    def test_partial_attempt_remains_pending_and_resumes_without_double_counting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = workspace(Path(directory) / "first")
            queue.plan(root, now=NOW)
            queue.begin(root, "job-1", now=NOW)
            path = finding(root, "job-1", "PARTIAL")
            with self.assertRaisesRegex(queue.QueueError, "not a completed"):
                queue.record(root, path, now=NOW)
            state = queue.begin(root, "job-1", now=NOW)
            self.assertEqual(["job-1"], state["attempted_cohorts"])
            self.assertEqual("job-1", state["queue"][0]["cohort_id"])

    def test_budgets_persist_and_new_session_explicitly_resumes_pending_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = workspace(Path(directory) / "first", max_candidates=1)
            queue.plan(root, now=NOW)
            state = complete(root, "job-1")
            self.assertEqual("CANDIDATE_LIMIT", state["stop_reason"])
            with self.assertRaisesRegex(queue.QueueError, "CANDIDATE_LIMIT"):
                queue.begin(root, "job-2", now=NOW)
            with self.assertRaisesRegex(queue.QueueError, "limits are frozen"):
                queue.plan(root, now=NOW, max_candidates=100)
            state = queue.plan(root, new_session=True, max_candidates=100, now=NOW + timedelta(minutes=1))
            self.assertEqual([], state["attempted_cohorts"])
            self.assertEqual("job-2", state["queue"][0]["cohort_id"])
            queue.begin(root, "job-2", now=NOW + timedelta(minutes=1))

    def test_time_and_recommendation_limits_stop_new_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = workspace(Path(directory) / "first")
            queue.plan(root, now=NOW)
            with self.assertRaisesRegex(queue.QueueError, "TIME_LIMIT"):
                queue.begin(root, "job-1", now=NOW + timedelta(minutes=121))

            queue.plan(root, new_session=True, now=NOW)
            with self.assertRaisesRegex(queue.QueueError, "RECOMMENDATION_LIMIT"):
                queue.begin(root, "job-1", validated_recommendations=10, now=NOW)
            self.assertEqual(10, queue.plan(root, now=NOW)["validated_recommendations"])
            with self.assertRaisesRegex(queue.QueueError, "cannot decrease"):
                queue.plan(root, now=NOW, validated_recommendations=0)
            queue.plan(root, new_session=True, max_candidates=1, now=NOW)
            queue.begin(root, "job-1", now=NOW)
            with self.assertRaisesRegex(queue.QueueError, "TIME_LIMIT"):
                queue.begin(root, "job-1", now=NOW + timedelta(minutes=121))

    def test_early_discovery_stop_is_recorded_and_requires_a_new_session_to_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = workspace(Path(directory) / "first")
            queue.plan(root, now=NOW, closed_reason="REVIEW_EXPORT_RESERVE")
            self.assertEqual("REVIEW_EXPORT_RESERVE", queue.plan(root, now=NOW)["stop_reason"])
            with self.assertRaisesRegex(queue.QueueError, "REVIEW_EXPORT_RESERVE"):
                queue.begin(root, "job-1", now=NOW)
            self.assertIsNone(queue.plan(root, new_session=True, now=NOW)["stop_reason"])

    def test_history_is_scoped_and_bootstraps_existing_completed_findings(self):
        with tempfile.TemporaryDirectory() as directory:
            old = workspace(Path(directory) / "old", total=2)
            finding(old, "job-1")
            fresh = workspace(Path(directory) / "new", total=2)
            state = queue.plan(fresh, now=NOW)
            self.assertEqual("job-2", state["queue"][0]["cohort_id"])
            other = workspace(Path(directory) / "arm", total=2, architecture="arm64")
            self.assertEqual(2, len(queue.plan(other, now=NOW)["queue"]))

    def test_history_discovery_gaps_survive_replanning_and_subsequent_invocations(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            for index in range(51):
                queue.write_json(parent / ("older-%d" % index) / "manifest.json", {})
            root = workspace(parent / "first")
            state = queue.plan(root, now=NOW)
            self.assertTrue(state["history_gaps"])
            self.assertEqual(state["history_gaps"], queue.plan(root, now=NOW)["history_gaps"])
            fresh = workspace(parent / "second")
            self.assertEqual(state["history_gaps"], queue.plan(fresh, now=NOW)["history_gaps"])

    def test_revisit_requires_evidence_survives_replan_and_clears_after_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = workspace(Path(directory) / "first", total=2)
            queue.plan(root, now=NOW)
            complete(root, "job-1")
            decisions = Path(directory) / "revisit.json"
            queue.write_json(decisions, {"revisits": [{"cohort_id": "job-1", "reason": "New artifact"}]})
            with self.assertRaisesRegex(queue.QueueError, "reason and evidence"):
                queue.plan(root, revisit_path=decisions, now=NOW)
            queue.write_json(decisions, {"revisits": [{"cohort_id": "job-1", "reason": "New artifact",
                                                       "evidence": ["artifact retrieved"]}]})
            queue.plan(root, revisit_path=decisions, now=NOW)
            with self.assertRaisesRegex(queue.QueueError, "order needs"):
                queue.begin(root, "job-1", now=NOW)
            queue.begin(root, "job-1", reason="New artifact enables the recorded follow-up", now=NOW)
            state = queue.record(root, finding(root, "job-1"), now=NOW)
            self.assertEqual(["job-2"], [item["cohort_id"] for item in state["queue"]])

    def test_reranking_does_not_relabel_old_finding_as_new_investigation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = workspace(Path(directory) / "first", total=2)
            queue.plan(root, now=NOW)
            complete(root, "job-1")
            rankings = queue.read_json(root / "job-rankings.json")
            rankings["current"][0]["investigation_inputs"] = {"config_revision": "new"}
            queue.write_json(root / "job-rankings.json", rankings)
            state = queue.plan(root, now=NOW)
            self.assertEqual("RECHECK", state["queue"][1]["status"])
            queue.begin(root, "job-1", reason="Review changed configuration", now=NOW)
            rankings["current"][0]["investigation_inputs"] = {"config_revision": "newer"}
            queue.write_json(root / "job-rankings.json", rankings)
            with self.assertRaisesRegex(queue.QueueError, "inputs changed"):
                queue.record(root, finding(root, "job-1"), now=NOW)

    def test_changed_or_missing_retained_finding_reopens_prior_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = workspace(Path(directory) / "first", total=2)
            queue.plan(root, now=NOW)
            complete(root, "job-1")
            path = root / "findings/job-1.json"
            changed = queue.read_json(path)
            changed["summary"] = "Changed without renewed investigation."
            queue.write_json(path, changed)
            state = queue.plan(root, now=NOW)
            self.assertEqual("RECHECK", state["queue"][1]["status"])
            path.unlink()
            self.assertEqual("RECHECK", queue.plan(root, now=NOW)["queue"][1]["status"])


if __name__ == "__main__":
    unittest.main()
