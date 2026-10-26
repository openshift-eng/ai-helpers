"""Offline collection-to-report checks for both payload verification roles."""
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from test_collection import FakeHTTP, collector, job, tag


def load_script(name):
    path = Path(__file__).parents[1] / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ranking = load_script("rank_jobs")
queue = load_script("investigation_queue")
exporter = load_script("export_report")
NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)


class PipelineTests(unittest.TestCase):
    def test_collection_to_report_for_each_role_without_payload_agent(self):
        for role in ("informing", "blocking"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "workspace"
                args = collector.build_parser().parse_args([
                    "4.18", role, "--architecture", "amd64", "--stream", "nightly",
                    "--history-release", "none", "--workspace", str(root), "--min-payloads", "1",
                    "--min-job-runs", "1", "--min-job-payloads", "1"])
                payloads = [tag(1, "rejected", phase="Rejected", release="4.18"),
                            tag(2, "accepted", release="4.18")]
                rejected = [job(1, "Blocking", "Failed", "1", alias="blocking-job")]
                accepted = [job(2, "Blocking", "Succeeded", "2", alias="blocking-job")]
                if role == "informing":
                    rejected.append(job(3, "Informing", "Failed", "1", alias="informing-job"))
                    accepted.append(job(4, "Informing", "Failed", "2", alias="informing-job"))
                http = FakeHTTP([json.dumps(value).encode() for value in (payloads, rejected, accepted)])
                client = collector.Client(root / "raw", opener=http)
                collector.run(args, client, collected_at=NOW)
                rankings, manifest = ranking.run(root)
                expected_payloads = ["1", "2"] if role == "blocking" else ["2"]
                self.assertEqual(expected_payloads, manifest["selected_payload_ids"])
                self.assertEqual(1, len(rankings["current"]))
                cohort = rankings["current"][0]
                self.assertEqual(["periodic-" + role + "-job"], cohort["provisional_prow_jobs"])
                self.assertEqual(role, cohort["job_role"])
                metric = cohort["metrics"]["unique_run_success"]
                self.assertEqual({"numerator": 1, "denominator": 2, "value": .5} if role == "blocking"
                                 else {"numerator": 0, "denominator": 1, "value": 0}, metric)
                state = queue.plan(root, now=NOW)
                self.assertEqual([cohort["cohort_id"]], [item["cohort_id"] for item in state["queue"]])
                report = Path(directory) / "report"
                exported = exporter.run(root, report)
                self.assertEqual(role, exported["effective_inputs"]["job_role"])
                self.assertIn("# Payload %s-job analysis" % role, (report / "README.md").read_text())
                summary = report / "findings" / cohort["cohort_id"] / "README.md"
                self.assertIn("Job role: " + role, summary.read_text())
                self.assertEqual(3, client.requests)

    def test_role_mismatch_is_rejected_by_queue_and_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            exporter.write_json(root / "manifest.json", {"stage": "RANKED", "selection_version": 1,
                                "effective_inputs": {"job_role": "blocking"}})
            exporter.write_json(root / "job-rankings.json", {"selection_version": 1, "job_role": "informing"})
            exporter.write_json(root / "payloads.json", {"payloads": []})
            with self.assertRaisesRegex(queue.QueueError, "frozen job role"):
                queue.load_workspace(root)
            with self.assertRaisesRegex(exporter.ExportError, "job role does not match"):
                exporter.run(root, root / "report")
            self.assertFalse((root / "report").exists())


if __name__ == "__main__":
    unittest.main()
