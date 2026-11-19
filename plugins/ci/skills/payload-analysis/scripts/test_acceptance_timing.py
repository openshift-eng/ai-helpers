"""Behavioral coverage for acceptance timing independently of chain baselines."""

from datetime import datetime, timedelta
import unittest

from acceptance_timing import assess_acceptance_timing


class AcceptanceTimingTests(unittest.TestCase):
    target_time = datetime(2026, 11, 19, 12)

    def payload(self, phase, seconds_before_target, prefix="5.1.0-0.nightly"):
        cut = self.target_time - timedelta(seconds=seconds_before_target)
        return {"tag": f"{prefix}-{cut:%Y-%m-%d-%H%M%S}", "phase": phase}

    def summary(self, history):
        return {
            "payload_tag": self.payload("Rejected", 0)["tag"],
            "payloads": history,
            "baseline_tag": history[-1]["tag"],
            "hours_since_baseline": 48,
        }

    def test_newer_force_accepted_payload_overrides_an_older_green_baseline(self):
        newer = self.payload("Accepted", 10 * 3600)
        newer["jobs"] = {"blocking": [{"name": "e2e", "state": "Failed"}]}
        result = assess_acceptance_timing(self.summary([
            self.payload("Rejected", 0), newer, self.payload("Accepted", 48 * 3600),
        ]))
        self.assertEqual(result["status"], "not_met")
        self.assertEqual(result["accepted_payload_tag"], newer["tag"])
        self.assertEqual(result["hours_before_target"], 10)

    def test_history_without_acceptance_does_not_prove_timing(self):
        for baseline_phase in ("Rejected", "Ready"):
            with self.subTest(baseline_phase=baseline_phase):
                result = assess_acceptance_timing(self.summary([
                    self.payload("Rejected", 0), self.payload(baseline_phase, 48 * 3600),
                ]))
                self.assertEqual(result["status"], "unknown")
                self.assertIsNone(result["hours_before_target"])

    def test_threshold_uses_unrounded_elapsed_time(self):
        for seconds, expected in ((18 * 3600 - 1, "not_met"), (18 * 3600, "met")):
            with self.subTest(seconds=seconds):
                result = assess_acceptance_timing(self.summary([
                    self.payload("Rejected", 0), self.payload("Accepted", seconds),
                ]))
                self.assertEqual(result["status"], expected)

    def test_unreadable_phase_can_hide_a_newer_acceptance(self):
        unreadable = self.payload("Unknown", 6 * 3600)
        result = assess_acceptance_timing(self.summary([
            self.payload("Rejected", 0), unreadable, self.payload("Accepted", 48 * 3600),
        ]))
        self.assertEqual(result["status"], "unknown")

    def test_missing_cut_time_is_unknown(self):
        result = assess_acceptance_timing(self.summary([
            self.payload("Rejected", 0), {"tag": "unavailable", "phase": "Accepted"},
        ]))
        self.assertEqual(result["status"], "unknown")
        self.assertIsNone(result["hours_before_target"])

    def test_hypershift_component_tags_use_the_same_timing_policy(self):
        prefix = "0.1.87-0036-gd2d9578c4.nightly"
        target = self.payload("Rejected", 0, prefix)
        accepted = self.payload("Accepted", 24 * 3600, prefix)
        summary = self.summary([target, accepted])
        summary["payload_tag"] = target["tag"]
        result = assess_acceptance_timing(summary)
        self.assertEqual(result["status"], "met")
        self.assertEqual(result["hours_before_target"], 24)


if __name__ == "__main__":
    unittest.main()
