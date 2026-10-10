import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "rank_jobs.py"
SPEC = importlib.util.spec_from_file_location("rank_jobs", SCRIPT)
ranking = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ranking)


def payload(identifier, when, passed, failed=0, phase="Accepted"):
    return {"schema_version": 1, "id": str(identifier), "tag": "payload-" + str(identifier), "release": "5.1",
            "architecture": "amd64", "stream": "nightly", "population_role": "current",
            "release_time": when, "phase": phase, "forced": False, "inventory_complete": True,
            "outcome_counts": {"blocking": {"Succeeded": passed, "Failed": failed},
                               "informing": {}, "unknown_role": {}}, "eligibility": "UNREVIEWED",
            "reason_codes": [], "evidence": []}


def association(identifier, payload_id, run_id, outcome, role="INFORMING", upgrade=False):
    return {"schema_version": 1, "payload_id": str(payload_id), "payload_tag": "payload-" + str(payload_id),
            "release": "5.1", "architecture": "amd64", "stream": "nightly", "population_role": "current",
            "association_id": str(identifier), "raw_alias": "alias", "raw_role": "Informing",
            "normalized_role": role, "raw_state": outcome.title(), "normalized_outcome": outcome,
            "prow_run_id": str(run_id), "prow_url": "https://example/run", "actual_prow_job": None,
            "provisional_prow_job": "periodic-job", "identity_state": "PROVISIONAL_URL",
            "transition_time": "2026-10-02T09:00:00Z", "retries": 0,
            "upgrade_route": {"upgrade": upgrade, "from": "4.19" if upgrade else None,
                              "to": "5.1" if upgrade else None}, "labels": []}


def workspace(directory, payloads, associations, **overrides):
    root = Path(directory)
    settings = {"release": "5.1", "architecture": "amd64", "stream": "nightly",
                "healthy_payloads": 10, "min_healthy_payloads": 1, "min_job_runs": 2,
                "min_job_payloads": 2, "min_blocker_pass_rate": .9, "poor_job_pass_rate": .5,
                "max_candidates": 100, "max_recommendations": 10, "time_budget_minutes": 120}
    settings.update(overrides)
    manifest = {"schema_version": 1, "analysis_id": "analysis", "stage": "COLLECTED",
                "collected_at": "2026-10-06T00:00:00Z", "selection_version": 0,
                "effective_inputs": settings, "counts": {"payloads_inspected": len(payloads)},
                "missing_evidence": []}
    (root / "manifest.json").write_text(json.dumps(manifest))
    (root / "payloads.json").write_text(json.dumps({"schema_version": 1, "payloads": payloads}))
    (root / "associations.json").write_text(json.dumps({"schema_version": 1, "associations": associations}))
    return root


class RankingTests(unittest.TestCase):
    def test_unhealthy_payload_excluded_and_duplicate_runs_do_not_inflate_rate(self):
        payloads = [payload(1, "2026-10-03T00:00:00Z", 10, 0),
                    payload(2, "2026-10-02T00:00:00Z", 10, 0),
                    payload(3, "2026-10-05T00:00:00Z", 6, 10, "Rejected")]
        associations = [association(1, 1, 10000000001, "FAILED"),
                        association(2, 2, 10000000001, "FAILED"),
                        association(3, 2, 10000000002, "SUCCEEDED"),
                        association(4, 3, 10000000003, "FAILED")]
        with tempfile.TemporaryDirectory() as directory:
            root = workspace(directory, payloads, associations)
            result, manifest = ranking.run(root)
            cohort = result["current"][0]
            self.assertEqual({"numerator": 1, "denominator": 3, "value": 1 / 3},
                             cohort["metrics"]["association_success"])
            self.assertEqual({"numerator": 1, "denominator": 2, "value": .5},
                             cohort["metrics"]["unique_run_success"])
            self.assertEqual(["1", "2"], manifest["selected_payload_ids"])
            updated = json.loads((root / "payloads.json").read_text())["payloads"]
            rejected = next(item for item in updated if item["id"] == "3")
            self.assertIn("LOW_BLOCKER_HEALTH", rejected["reason_codes"])

    def test_unknown_and_blocking_roles_do_not_enter_ranking_and_routes_split(self):
        payloads = [payload(1, "2026-10-03T00:00:00Z", 10), payload(2, "2026-10-02T00:00:00Z", 10)]
        rows = [association(1, 1, 10000000001, "FAILED"),
                association(2, 2, 10000000002, "FAILED", upgrade=True),
                association(3, 1, 10000000003, "FAILED", role="UNKNOWN"),
                association(4, 1, 10000000004, "FAILED", role="BLOCKING")]
        with tempfile.TemporaryDirectory() as directory:
            result, _ = ranking.run(workspace(directory, payloads, rows, min_job_runs=1, min_job_payloads=1))
            self.assertEqual(2, len(result["current"]))
            self.assertEqual({False, True}, {item["upgrade_route"]["upgrade"] for item in result["current"]})

    def test_confirmed_shared_failure_requires_and_retains_evidence(self):
        payloads = [payload(1, "2026-10-03T00:00:00Z", 10)]
        with tempfile.TemporaryDirectory() as directory:
            root = workspace(directory, payloads, [association(1, 1, 10000000001, "FAILED")],
                             min_job_runs=1, min_job_payloads=1)
            decisions = Path(directory) / "shared.json"
            decisions.write_text(json.dumps({"payload_decisions": [{"payload_id": "1",
                "classification": "CONFIRMED_SHARED_FAILURE", "evidence": ["same new signature in four families"]}]}))
            result, manifest = ranking.run(root, decisions)
            self.assertEqual([], result["current"])
            self.assertEqual([], manifest["selected_payload_ids"])


if __name__ == "__main__":
    unittest.main()
