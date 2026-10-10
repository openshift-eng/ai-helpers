import hashlib
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

SCRIPT = Path(__file__).parents[1] / "scripts" / "export_report.py"
SPEC = importlib.util.spec_from_file_location("export_report", SCRIPT)
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)
QUEUE_SPEC = importlib.util.spec_from_file_location("investigation_queue", SCRIPT.with_name("investigation_queue.py"))
queue = importlib.util.module_from_spec(QUEUE_SPEC)
QUEUE_SPEC.loader.exec_module(queue)


def setup_workspace(root):
    root = Path(root)
    root.mkdir(parents=True)
    manifest = {"schema_version": 1, "analysis_id": "analysis", "stage": "RANKED",
                "selection_version": 1, "effective_inputs": {"release": "5.1", "architecture": "amd64",
                "stream": "nightly"}, "counts": {"payloads_inspected": 3, "selected_payloads": 2},
                "missing_evidence": [], "current_window": {"start": "2026-09-22T00:00:00Z",
                "end": "2026-10-06T00:00:00Z"}}
    cohort = {"cohort_id": "cohort", "verification_aliases": ["alias"], "actual_prow_jobs": [],
              "provisional_prow_jobs": ["periodic-job"], "metrics": {"unique_run_success":
              {"numerator": 0, "denominator": 5, "value": 0}, "association_success":
              {"numerator": 0, "denominator": 7, "value": 0}, "distinct_runs": 5,
              "payload_exposures": 3}, "sample_sufficient": True, "rank": 1}
    rankings = {"schema_version": 1, "selection_version": 1, "current": [cohort],
                "previous_release_history": []}
    (root / "manifest.json").write_text(json.dumps(manifest))
    (root / "payloads.json").write_text(json.dumps({"schema_version": 1, "payloads": []}))
    (root / "associations.json").write_text(json.dumps({"schema_version": 1, "associations": []}))
    (root / "job-rankings.json").write_text(json.dumps(rankings))
    return root


def finding_record(**overrides):
    finding = {"schema_version": 1, "cohort_id": "cohort", "disposition": "INSUFFICIENT_EVIDENCE",
               "investigation_status": "COMPLETE_BOUNDED", "intended_verification_purpose": "conformance",
               "title": "Investigate the catalog setup failure", "summary": "All five runs failed; two inspected runs stopped before tests. The catalog cause remains unknown.",
               "next_action": "Ask the catalog owners to inspect exact-version synchronization.",
               "owner": "Catalog maintainers", "execution": {"phase": "SETUP_FAILED",
               "real_test_count": 0, "failed_real_test_count": 0, "synthetic_case_count": 1},
               "investigator_context_identity": "investigator-a", "evidence": []}
    finding.update(overrides)
    return finding


def write_finding(root, finding):
    directory = root / "findings"
    directory.mkdir(exist_ok=True)
    (directory / "friendly-name.json").write_text(json.dumps(finding))


def local_links(path):
    return [path.parent / unquote(target) for target in re.findall(r"\]\(([^)]+)\)", path.read_text())
            if not target.startswith(("http:", "https:"))]


class ExportTests(unittest.TestCase):
    def test_prior_history_is_exported_as_scheduling_context_without_current_finding(self):
        with tempfile.TemporaryDirectory() as directory:
            old = setup_workspace(Path(directory) / "old")
            manifest = exporter.read_json(old / "manifest.json")
            manifest["collected_at"] = "2026-10-06T00:00:00Z"
            exporter.write_json(old / "manifest.json", manifest)
            write_finding(old, finding_record())
            fresh = setup_workspace(Path(directory) / "fresh")
            manifest["analysis_id"] = "fresh"
            exporter.write_json(fresh / "manifest.json", manifest)
            state = queue.plan(fresh, new_session=True)
            self.assertEqual("QUEUE_EXHAUSTED", state["stop_reason"])
            output = Path(directory) / "report"
            exported = exporter.run(fresh, output)
            self.assertEqual(0, exported["report_counts"]["findings"])
            self.assertEqual(0, exported["report_counts"]["proven_fixes"])
            self.assertEqual(1, exported["investigation_workflow"]["deferred"])
            self.assertEqual("QUEUE_EXHAUSTED", exported["investigation_workflow"]["stop_reason"])
            self.assertTrue((output / "investigation-queue.json").is_file())
            readme = output / "findings/cohort/README.md"
            self.assertIn(finding_record()["summary"], readme.read_text())
            self.assertIn("not a current diagnosis", readme.read_text())
            self.assertFalse(readme.with_name("finding.json").exists())
            self.assertTrue(all(path.is_file() for path in local_links(output / "README.md")))
            unresolved = exporter.read_json(output / "unresolved.json")["items"]
            self.assertEqual("DEFERRED", unresolved[0]["status"])

    def test_export_rejects_queue_from_an_older_selection_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = setup_workspace(Path(directory) / "work")
            manifest = exporter.read_json(root / "manifest.json")
            manifest["collected_at"] = "2026-10-06T00:00:00Z"
            exporter.write_json(root / "manifest.json", manifest)
            queue.plan(root, new_session=True)
            state = exporter.read_json(root / "investigation-queue.json")
            state["selection_version"] = 0
            exporter.write_json(root / "investigation-queue.json", state)
            with self.assertRaisesRegex(exporter.ExportError, "queue is stale"):
                exporter.run(root, Path(directory) / "report")

    def test_execution_classification_rejects_synthetic_case_as_real_test(self):
        finding = finding_record(execution={"phase": "REAL_TEST_FAILURE", "real_test_count": 0,
                                            "failed_real_test_count": 0, "synthetic_case_count": 1})
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(exporter.ExportError):
                exporter.validate_finding(Path(directory), Path("finding.json"), finding, {"cohort"})

    def test_execution_phase_shapes_cover_supported_cases(self):
        cases = [
            ("SETUP_FAILED", None, None, 1, False),
            ("WORKLOAD_FAILED_BEFORE_REAL_TESTS", 0, 0, 1, False),
            ("REAL_TEST_FAILURE", 10, 2, 0, False),
            ("POST_TEST_FAILURE", 10, 0, 0, False),
            ("INTENTIONAL_TESTLESS", 0, 0, 0, True),
        ]
        with tempfile.TemporaryDirectory() as directory:
            for phase, real, failed, synthetic, testless in cases:
                finding = finding_record(execution={"phase": phase, "real_test_count": real,
                                         "failed_real_test_count": failed, "synthetic_case_count": synthetic,
                                         "intended_testless": testless})
                exporter.validate_finding(Path(directory), Path("finding.json"), finding, {"cohort"})

    def test_investigated_handoff_requires_authored_summary_and_action(self):
        with tempfile.TemporaryDirectory() as directory:
            for key in ("title", "summary", "next_action"):
                for value in (None, "  ", {"invented": "text"}):
                    with self.subTest(key=key, value=value):
                        finding = finding_record(**{key: value})
                        with self.assertRaisesRegex(exporter.ExportError, key):
                            exporter.validate_finding(Path(directory), Path("finding.json"), finding, {"cohort"})

    def test_zero_fix_report_preserves_pending_cohort(self):
        with tempfile.TemporaryDirectory() as directory:
            root = setup_workspace(Path(directory) / "work")
            output = Path(directory) / "report"
            manifest = exporter.run(root, output)
            unresolved = json.loads((output / "unresolved.json").read_text())["items"]
            self.assertEqual("PENDING", unresolved[0]["status"])
            self.assertEqual(0, manifest["report_counts"]["proven_fixes"])
            self.assertTrue((output / "fixes").is_dir())
            self.assertEqual(1, manifest["report_counts"]["cohort_summaries"])
            readme = output / "findings/cohort/README.md"
            self.assertTrue(readme.is_file())
            self.assertFalse(readme.with_name("finding.json").exists())
            self.assertIn("cause and action remain unassessed", readme.read_text())
            self.assertTrue(all(path.is_file() for path in local_links(output / "README.md")))
            with self.assertRaises(exporter.ExportError):
                exporter.run(root, output)

    def test_all_populations_have_linked_summaries_and_separate_windows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = setup_workspace(Path(directory) / "work")
            rankings = exporter.read_json(root / "job-rankings.json")
            historical = dict(rankings["current"][0], cohort_id="previous-cohort", release="5.0",
                              sample_sufficient=False, pending_reason="Investigation budget exhausted.")
            historical["metrics"] = dict(historical["metrics"], unique_run_success={
                "numerator": 0, "denominator": 1, "value": 0})
            rankings["previous_release_history"] = [historical]
            exporter.write_json(root / "job-rankings.json", rankings)
            manifest = exporter.read_json(root / "manifest.json")
            manifest["history"] = {"window": {"start": "2026-08-01T00:00:00Z", "end": "2026-08-15T00:00:00Z"}}
            exporter.write_json(root / "manifest.json", manifest)
            output = Path(directory) / "report"
            exported = exporter.run(root, output)
            index_links = local_links(output / "README.md")
            self.assertEqual(2, exported["report_counts"]["cohort_summaries"])
            self.assertEqual(2, len(index_links))
            self.assertTrue(all(path.is_file() for path in index_links))
            current = (output / "findings/cohort/README.md").read_text()
            history = (output / "findings/previous-cohort/README.md").read_text()
            self.assertIn("2026-09-22", current)
            self.assertNotIn("2026-08-01", current)
            self.assertIn("2026-08-01", history)
            self.assertNotIn("2026-09-22", history)
            self.assertIn("5.0 / amd64 / nightly", history)
            self.assertIn("Sparse", history)
            self.assertIn("0/1", history)
            self.assertIn("Investigation budget exhausted", history)
            self.assertFalse((output / "findings/previous-cohort/finding.json").exists())

    def test_readable_proposal_preserves_scope_denominators_and_evidence_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = setup_workspace(Path(directory) / "work")
            retained = root / "evidence/failure (sample).txt"
            retained.parent.mkdir()
            retained.write_text("fixture timeout\n")
            finding = finding_record(disposition="PROPOSE_FIX", title="Repair the locator | retain the tests",
                summary="Two sampled failures have an absent locator; other failures remain unexplained.",
                next_action="Change only the locator; keep the assertions and investigate the other failures.",
                mechanism={"primary": "Rendered grid lacks the requested test ID."},
                current_source_state={"revision": "abc123", "repair": "Not adopted."},
                proposed_change={"scope": "node locator only", "unapplied": True},
                acceptance_criteria=["All assertions still execute on a confirming run."],
                limitations=["No repaired run exists; this is a partial proposal."],
                sampled_runs=[{"run_id": "123", "url": "https://example.invalid/run/123", "payload_id": "p1"},
                              {"prow_run_id": "124", "prow_url": "https://example.invalid/run/124", "payload_id": "p2"}],
                evidence=[{"source_url": "https://example.invalid/log", "retrieved_at": "2026-10-06T00:00:00Z",
                           "sha256": exporter.file_digest(retained), "retained_path": "evidence/failure (sample).txt",
                           "location": "line 1", "role": "observed failure"}])
            write_finding(root, finding)
            output = Path(directory) / "report"
            exported = exporter.run(root, output)
            readme = output / "findings/cohort/README.md"
            text = readme.read_text()
            self.assertIn(finding["summary"], text)
            self.assertIn(finding["next_action"], text)
            self.assertIn("0/5", text)
            self.assertIn("0/7", text)
            self.assertIn("Deeply inspected runs: 2", text)
            self.assertIn("Not adopted.", text)
            self.assertIn("UNKNOWN", text)  # Sample phases were not supplied.
            self.assertIn("No repaired run exists", text)
            self.assertIn("UNAVAILABLE / PENDING", text)
            self.assertEqual(0, exported["report_counts"]["proven_fixes"])
            self.assertEqual(1, exported["report_counts"]["unresolved"])
            for page in (readme, output / "README.md"):
                self.assertTrue(all(path.is_file() for path in local_links(page)))
            self.assertEqual(finding, exporter.read_json(readme.with_name("finding.json")))

    def test_analysis_review_is_digest_bound_and_does_not_prove_a_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = setup_workspace(Path(directory) / "work")
            finding = finding_record()
            write_finding(root, finding)
            document = {"selection_version_checked": 1, "reviewer_context_identity": "reviewer-b",
                        "reviewed_at": "2026-10-06T01:00:00Z", "scope": "Analysis of the sampled setup failures",
                        "findings": [{"cohort_id": "cohort", "finding_sha256": exporter.digest(finding),
                        "verdict": "SUPPORTED_WITH_LIMITATIONS", "reasoning": "Cause remains unknown.",
                        "evidence_checked": ["retained log"]}]}
            exporter.write_json(root / "analysis-review.json", document)
            output = Path(directory) / "first"
            exported = exporter.run(root, output)
            text = (output / "findings/cohort/README.md").read_text()
            self.assertIn("SUPPORTED_WITH_LIMITATIONS".replace("_", "\\_"), text)
            self.assertEqual(0, exported["report_counts"]["proven_fixes"])
            self.assertTrue(all(path.is_file() for path in local_links(output / "findings/cohort/README.md")))
            finding["summary"] += " A newly observed failure changes applicability."
            write_finding(root, finding)
            second = Path(directory) / "second"
            exporter.run(root, second)
            text = (second / "findings/cohort/README.md").read_text()
            self.assertIn("STALE_OR_INCOMPLETE", text)
            self.assertNotIn("SUPPORTED", text)
            write_finding(root, finding_record())
            for label, update in (("same-context", {"reviewer_context_identity": "investigator-a"}),
                                  ("old-selection", {"selection_version_checked": 0}),
                                  ("missing-scope", {"scope": None})):
                with self.subTest(case=label):
                    exporter.write_json(root / "analysis-review.json", dict(document, **update))
                    report = Path(directory) / label
                    exporter.run(root, report)
                    text = (report / "findings/cohort/README.md").read_text()
                    self.assertIn("STALE_OR_INCOMPLETE", text)
                    self.assertNotIn("SUPPORTED", text)

    def test_empty_population_exports_no_invented_job_summaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = setup_workspace(Path(directory) / "work")
            rankings = exporter.read_json(root / "job-rankings.json")
            rankings["current"] = []
            exporter.write_json(root / "job-rankings.json", rankings)
            report = Path(directory) / "report"
            result = exporter.run(root, report)
            self.assertEqual(0, result["report_counts"]["cohort_summaries"])
            self.assertEqual([], local_links(report / "README.md"))
            self.assertEqual([], list((report / "findings").glob("*/README.md")))

    def test_cohort_directory_identity_cannot_escape_or_overwrite_another_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = setup_workspace(Path(directory) / "work")
            baseline = exporter.read_json(root / "job-rankings.json")
            for case in ("traversal", "duplicate"):
                with self.subTest(case=case):
                    rankings = json.loads(json.dumps(baseline))
                    if case == "traversal":
                        rankings["current"][0]["cohort_id"] = "../outside"
                    else:
                        rankings["previous_release_history"] = rankings["current"]
                    exporter.write_json(root / "job-rankings.json", rankings)
                    report = Path(directory) / case
                    with self.assertRaises(exporter.ExportError):
                        exporter.run(root, report)
                    self.assertFalse(report.exists())

    def test_digest_bound_independent_retirement_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = setup_workspace(Path(directory) / "work")
            evidence_path = root / "evidence" / "failure.txt"
            evidence_path.parent.mkdir()
            evidence_path.write_text("recurring setup failure\n")
            proof = {"source_url": "https://example.invalid/run", "retrieved_at": "2026-10-06T00:00:00Z",
                     "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
                     "retained_path": "evidence/failure.txt", "location": "line:1", "role": "observed_failure"}
            candidate = {"schema_version": 1, "cohort_id": "cohort", "disposition": "RETIREMENT_CANDIDATE",
                         "population": {"terminal_runs": 5, "payloads": 3},
                         "persistence": {"recent": True}, "localization": {"job_local": True},
                         "investigation": {"scope": "three failures and one control", "supported_repairs": []},
                         "configuration": {"verification_entry": "alias", "prow_job": "periodic-job",
                           "source_revision": "abc123", "periodic_definition": "ci-operator/jobs/example.yaml",
                           "current_schedule": {"interval": "24h"},
                           "proposed_yearly_schedule": {"cron": "0 0 1 1 *", "timezone": "UTC"},
                           "unapplied_change": "replace interval with cron"},
                         "impact": {"consumers": ["5.1/amd64/nightly"], "coverage_risk": "documented"},
                         "restoration_condition": "restore after three consecutive healthy payload runs",
                         "investigator_context_identity": "investigator-a", "evidence": [proof]}
            candidates = root / "retirement-candidates"
            candidates.mkdir()
            path = candidates / "cohort.json"
            path.write_text(json.dumps(candidate))
            review = {"recommendation_digest": exporter.digest(exporter.recommendation_body(candidate)),
                      "reviewer_context_identity": "reviewer-b", "reviewed_at": "2026-10-06T01:00:00Z",
                      "evidence_checked": ["failure.txt"], "counterarguments": ["coverage gap"],
                      "verdict": "VALIDATED_CANDIDATE", "outstanding_concerns": ["owner approval"]}
            (candidates / "cohort.review.json").write_text(json.dumps(review))
            output = Path(directory) / "report"
            manifest = exporter.run(root, output)
            self.assertEqual(1, manifest["report_counts"]["validated_retirements"])
            self.assertTrue((output / "retirement-candidates/cohort/recommendation.json").is_file())
            self.assertTrue((output / "evidence/failure.txt").is_file())
            summary = output / "findings/cohort/README.md"
            self.assertIn("VALIDATED\\_CANDIDATE", summary.read_text())
            self.assertTrue(all(path.is_file() for path in local_links(summary)))
            (candidates / "cohort.review.json").unlink()
            unreviewed = Path(directory) / "unreviewed"
            exported = exporter.run(root, unreviewed)
            self.assertEqual(0, exported["report_counts"]["validated_retirements"])
            self.assertIn("UNREVIEWED", (unreviewed / "findings/cohort/README.md").read_text())

    def test_edited_candidate_invalidates_review(self):
        candidate = {"schema_version": 1, "cohort_id": "cohort"}
        first = exporter.digest(exporter.recommendation_body(candidate))
        candidate["impact"] = {"changed": True}
        self.assertNotEqual(first, exporter.digest(exporter.recommendation_body(candidate)))


if __name__ == "__main__":
    unittest.main()
