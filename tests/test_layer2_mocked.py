import unittest
import sys
import os
import json

# Ensure repo root and tests dir are on import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from contracts.CalibrationLedger import CalibrationLedger, gl


class TestLayer2MockedContract(unittest.TestCase):
    """Layer 2: Contract state machine, mocked LLM, quote grounding, and calibration reporting."""

    def setUp(self):
        self.ledger = CalibrationLedger()
        self.ledger.predictions = {}
        self.ledger.by_forecaster = {}
        self.ledger.meta = {}

    def test_double_resolution_rejected(self):
        """resolve_event rejects a second resolution of the same prediction."""
        # Setup mock prompt handler to return valid YES with quote
        evidence = "The official election commission declared candidate Alice won the mayoral election on Tuesday."
        gl.nondet.prompt_handler = lambda prompt: {
            "outcome": "YES",
            "quote": "candidate Alice won the mayoral election",
        }

        pid = self.ledger.register_prediction("Will Alice win the mayoral election?", 7000, "2026-11-01")
        res1 = self.ledger.resolve_event(pid, evidence)
        self.assertEqual(res1, "YES")

        # Second resolution attempt must raise UserError
        with self.assertRaises(gl.vm.UserError) as ctx:
            self.ledger.resolve_event(pid, evidence)
        self.assertIn("resolving an already-resolved prediction", str(ctx.exception))

    def test_resolve_nonexistent_prediction_rejected(self):
        """resolve_event rejects unknown prediction IDs."""
        with self.assertRaises(gl.vm.UserError) as ctx:
            self.ledger.resolve_event("nonexistent12", "Some valid evidence text")
        self.assertIn("prediction not found", str(ctx.exception))

    def test_ungrounded_quote_forces_ambiguous(self):
        """An ungrounded/invented quote not present in evidence forces outcome = AMBIGUOUS."""
        evidence = "The European Central Bank kept interest rates unchanged at 3.50 percent during its monetary meeting."
        
        # Mock LLM hallucinates a quote not present in evidence
        gl.nondet.prompt_handler = lambda prompt: {
            "outcome": "YES",
            "quote": "The European Central Bank decreased interest rates by 50 basis points",
        }

        pid = self.ledger.register_prediction("Will ECB cut rates in October?", 6000, "2026-10-31")
        outcome = self.ledger.resolve_event(pid, evidence)
        self.assertEqual(outcome, "AMBIGUOUS")

        record = json.loads(self.ledger.get_prediction(pid))
        self.assertEqual(record["outcome"], "AMBIGUOUS")
        self.assertEqual(record["resolution_quote"], "NONE")

    def test_short_quote_forces_ambiguous(self):
        """A quote shorter than 12 characters forces outcome = AMBIGUOUS even if substring exists."""
        evidence = "The SpaceX Starship Flight 6 completed all orbital test objectives successfully."

        # Mock LLM returns quote that exists in text but has only 8 characters
        gl.nondet.prompt_handler = lambda prompt: {
            "outcome": "YES",
            "quote": "SpaceX",
        }

        pid = self.ledger.register_prediction("Will Starship complete Flight 6?", 8000, "2026-12-31")
        outcome = self.ledger.resolve_event(pid, evidence)
        self.assertEqual(outcome, "AMBIGUOUS")

    def test_ambiguous_excluded_from_brier_but_counted_in_resolved(self):
        """AMBIGUOUS predictions are excluded from Brier score average but still counted in n_resolved."""
        forecaster_addr = gl.message.sender_address.as_hex

        # Prediction 1: 8000 bp -> Resolves YES (grounded)
        ev1 = "Company Q3 revenue rose 25 percent exceeding Wall Street expectations significantly."
        gl.nondet.prompt_handler = lambda p: {"outcome": "YES", "quote": "revenue rose 25 percent exceeding Wall Street"}
        pid1 = self.ledger.register_prediction("Will Company Q3 revenue beat estimates?", 8000, "2026-10-15")
        self.ledger.resolve_event(pid1, ev1)

        # Prediction 2: 7000 bp -> Resolves AMBIGUOUS (invented quote)
        ev2 = "The local weather station noted fluctuating wind patterns without conclusive rain data."
        gl.nondet.prompt_handler = lambda p: {"outcome": "YES", "quote": "It rained over two inches throughout the city"}
        pid2 = self.ledger.register_prediction("Will it rain more than 2 inches?", 7000, "2026-10-16")
        self.ledger.resolve_event(pid2, ev2)

        # Prediction 3: 2000 bp -> Resolves NO (grounded)
        ev3 = "The team officially confirmed the spacecraft launch was scrubbed due to sensor anomaly."
        gl.nondet.prompt_handler = lambda p: {"outcome": "NO", "quote": "spacecraft launch was scrubbed due to sensor anomaly"}
        pid3 = self.ledger.register_prediction("Will the spacecraft launch on schedule?", 2000, "2026-10-17")
        self.ledger.resolve_event(pid3, ev3)

        # Generate fresh calibration report
        report_json = self.ledger.get_calibration_report(forecaster_addr)
        report = json.loads(report_json)

        self.assertEqual(report["n_registered"], 3)
        self.assertEqual(report["n_resolved"], 3)
        self.assertEqual(report["n_scored"], 2)  # Ambiguous excluded from scoring

        # Brier score computed on the 2 scored events:
        # Event 1: (0.80 - 1.0)^2 = 0.0400
        # Event 3: (0.20 - 0.0)^2 = 0.0400
        # Average: (0.04 + 0.04) / 2 = 0.0400
        self.assertAlmostEqual(report["brier_score"], 0.0400, places=4)

        # Buckets: should contain 20-30 and 80-90
        bucket_ranges = {b["range"]: b for b in report["buckets"]}
        self.assertIn("80-90", bucket_ranges)
        self.assertEqual(bucket_ranges["80-90"]["n"], 1)
        self.assertEqual(bucket_ranges["80-90"]["hits"], 1)
        self.assertEqual(bucket_ranges["80-90"]["hit_rate"], 1.0)

        self.assertIn("20-30", bucket_ranges)
        self.assertEqual(bucket_ranges["20-30"]["n"], 1)
        self.assertEqual(bucket_ranges["20-30"]["hits"], 0)
        self.assertEqual(bucket_ranges["20-30"]["hit_rate"], 0.0)

    def test_discovery_view_pagination(self):
        """list_predictions_by_forecaster returns registered IDs with bounds."""
        forecaster_addr = gl.message.sender_address.as_hex
        pids = []
        for i in range(15):
            pid = self.ledger.register_prediction(f"Event number {i}", 5000, "2026-12-31")
            pids.append(pid)

        # List with default limit
        listed_default = json.loads(self.ledger.list_predictions_by_forecaster(forecaster_addr))
        self.assertEqual(len(listed_default), 15)

        # List with custom limit
        listed_custom = json.loads(self.ledger.list_predictions_by_forecaster(forecaster_addr, limit=5))
        self.assertEqual(len(listed_custom), 5)
        self.assertEqual(listed_custom, pids[:5])

        # Unknown forecaster
        unknown_list = json.loads(self.ledger.list_predictions_by_forecaster("0x9999999999999999999999999999999999999999"))
        self.assertEqual(unknown_list, [])


if __name__ == "__main__":
    unittest.main()
