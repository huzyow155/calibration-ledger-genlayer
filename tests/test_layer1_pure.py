import unittest
import sys
import os

# Ensure repo root and tests dir are on import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from contracts.CalibrationLedger import (
    _calculate_brier_score,
    _calculate_calibration_buckets,
    _parse_model_output,
    MAX_EVENT_TEXT_LEN,
    MIN_QUOTE_LEN,
)


class TestLayer1PureMath(unittest.TestCase):
    """Layer 1: Pure functions, boundary math, range validation, and the trap test."""

    def test_brier_score_known_values(self):
        # Empty list yields None
        self.assertIsNone(_calculate_brier_score([]))

        # Single prediction: 5000 bp (0.50) on YES -> (0.5 - 1.0)^2 = 0.25
        score_50_yes = _calculate_brier_score([(5000, "YES")])
        self.assertEqual(score_50_yes, 0.25)

        # Single prediction: 5000 bp (0.50) on NO -> (0.5 - 0.0)^2 = 0.25
        score_50_no = _calculate_brier_score([(5000, "NO")])
        self.assertEqual(score_50_no, 0.25)

        # High confidence correct: 9000 bp (0.90) on YES -> (0.9 - 1.0)^2 = 0.01
        score_90_yes = _calculate_brier_score([(9000, "YES")])
        self.assertEqual(score_90_yes, 0.01)

        # High confidence wrong: 9000 bp (0.90) on NO -> (0.9 - 0.0)^2 = 0.81
        score_90_no = _calculate_brier_score([(9000, "NO")])
        self.assertEqual(score_90_no, 0.81)

        # Two predictions: (8000, YES) -> 0.04, (2000, NO) -> 0.04 -> mean = 0.04
        score_two = _calculate_brier_score([(8000, "YES"), (2000, "NO")])
        self.assertEqual(score_two, 0.04)

    def test_trap_test_overconfident_vs_calibrated(self):
        """
        The Trap Test:
        Demonstrate with real numbers that an overconfident forecaster (always predicting 9900 bp)
        suffers a severe quadratic Brier score penalty when even one call is wrong, scoring much
        worse than an honest well-calibrated forecaster with the IDENTICAL raw hit-rate.
        """
        # Forecaster A: Always overconfident at 9900 bp (99%)
        # 10 total predictions: 9 resolve YES (hits), 1 resolves NO (miss)
        # Raw hit-rate: 9 / 10 = 90.0%
        predictions_overconfident = [(9900, "YES")] * 9 + [(9900, "NO")] * 1
        brier_overconfident = _calculate_brier_score(predictions_overconfident)

        # Forecaster B: Well-calibrated at 9000 bp (90%)
        # 10 total predictions: 9 resolve YES (hits), 1 resolves NO (miss)
        # Raw hit-rate: 9 / 10 = 90.0% (IDENTICAL raw hit rate)
        predictions_calibrated = [(9000, "YES")] * 9 + [(9000, "NO")] * 1
        brier_calibrated = _calculate_brier_score(predictions_calibrated)

        # Calculate exact quadratic breakdown
        # Overconfident penalty on 1 miss: (0.99 - 0.0)^2 = 0.9801
        # Overconfident penalty on 9 hits: 9 * (0.99 - 1.0)^2 = 9 * 0.0001 = 0.0009
        # Sum = 0.9810 / 10 = 0.0981
        # Calibrated penalty on 1 miss: (0.90 - 0.0)^2 = 0.8100
        # Calibrated penalty on 9 hits: 9 * (0.90 - 1.0)^2 = 9 * 0.0100 = 0.0900
        # Sum = 0.9000 / 10 = 0.0900

        print("\n=== THE TRAP TEST DEMONSTRATION ===")
        print(f"Both forecasters evaluated on 10 events: 9 YES, 1 NO (90.0% raw hit rate)")
        print(f"Forecaster A (Overconfident 9900 bp): Brier Score = {brier_overconfident:.6f}")
        print(f"Forecaster B (Calibrated 9000 bp):   Brier Score = {brier_calibrated:.6f}")
        diff = brier_overconfident - brier_calibrated
        pct_worse = (diff / brier_calibrated) * 100
        print(f"Penalty difference: Overconfident is {diff:.6f} worse (+{pct_worse:.2f}% penalty) due to quadratic punishment on the single failed prediction.")
        print("===================================\n")

        self.assertAlmostEqual(brier_overconfident, 0.0981, places=4)
        self.assertAlmostEqual(brier_calibrated, 0.0900, places=4)
        self.assertGreater(brier_overconfident, brier_calibrated)

    def test_calibration_buckets_boundaries(self):
        """Test bucket allocation and boundary hit rates."""
        predictions = [
            (1, "YES"),       # Bucket 0-10: 1 hit
            (999, "NO"),      # Bucket 0-10: 0 hit -> total 2, hits 1 (50%)
            (1000, "YES"),    # Bucket 10-20: 1 hit -> total 1, hits 1 (100%)
            (2500, "NO"),     # Bucket 20-30: 0 hit -> total 1, hits 0 (0%)
            (5000, "YES"),    # Bucket 50-60: 1 hit
            (5500, "YES"),    # Bucket 50-60: 1 hit -> total 2, hits 2 (100%)
            (9999, "NO"),     # Bucket 90-100: 0 hit -> total 1, hits 0 (0%)
        ]
        buckets = _calculate_calibration_buckets(predictions)
        bucket_by_range = {b["range"]: b for b in buckets}

        # Check Bucket 0-10
        self.assertIn("0-10", bucket_by_range)
        self.assertEqual(bucket_by_range["0-10"]["n"], 2)
        self.assertEqual(bucket_by_range["0-10"]["hits"], 1)
        self.assertEqual(bucket_by_range["0-10"]["hit_rate"], 0.5)

        # Check Bucket 10-20
        self.assertIn("10-20", bucket_by_range)
        self.assertEqual(bucket_by_range["10-20"]["n"], 1)
        self.assertEqual(bucket_by_range["10-20"]["hits"], 1)
        self.assertEqual(bucket_by_range["10-20"]["hit_rate"], 1.0)

        # Check Bucket 20-30
        self.assertIn("20-30", bucket_by_range)
        self.assertEqual(bucket_by_range["20-30"]["n"], 1)
        self.assertEqual(bucket_by_range["20-30"]["hits"], 0)
        self.assertEqual(bucket_by_range["20-30"]["hit_rate"], 0.0)

        # Check Bucket 50-60
        self.assertIn("50-60", bucket_by_range)
        self.assertEqual(bucket_by_range["50-60"]["n"], 2)
        self.assertEqual(bucket_by_range["50-60"]["hits"], 2)
        self.assertEqual(bucket_by_range["50-60"]["hit_rate"], 1.0)

        # Check Bucket 90-100
        self.assertIn("90-100", bucket_by_range)
        self.assertEqual(bucket_by_range["90-100"]["n"], 1)
        self.assertEqual(bucket_by_range["90-100"]["hits"], 0)
        self.assertEqual(bucket_by_range["90-100"]["hit_rate"], 0.0)

    def test_model_output_parsing_defensive(self):
        """Test defensive parsing of model outputs."""
        # Clean dict
        o, q = _parse_model_output({"outcome": "YES", "quote": "verbatim text"})
        self.assertEqual(o, "YES")
        self.assertEqual(q, "verbatim text")

        # JSON in Markdown fences
        md_json = "```json\n{\"outcome\": \"NO\", \"quote\": \"sample quote here\"}\n```"
        o, q = _parse_model_output(md_json)
        self.assertEqual(o, "NO")
        self.assertEqual(q, "sample quote here")

        # Free text containing regex match
        free_text = 'The resolution is {"outcome": "AMBIGUOUS", "quote": ""}'
        o, q = _parse_model_output(free_text)
        self.assertEqual(o, "AMBIGUOUS")

    def test_validation_rules_and_boundaries(self):
        """Test boundary rules: prob_bp in [1, 9999] and event_text <= 300 chars."""
        from contracts.CalibrationLedger import CalibrationLedger, gl

        ledger = CalibrationLedger()
        ledger.predictions = {}
        ledger.by_forecaster = {}
        ledger.meta = {}

        # Valid boundaries: 1 and 9999
        pid1 = ledger.register_prediction("Event at lower bound", 1, "2026-12-31")
        self.assertTrue(len(pid1) == 12)
        pid2 = ledger.register_prediction("Event at upper bound", 9999, "2026-12-31")
        self.assertTrue(len(pid2) == 12)

        # Certainty boundary violations: 0 and 10000 must be rejected
        with self.assertRaises(gl.vm.UserError) as ctx0:
            ledger.register_prediction("Event with 0 prob", 0, "2026-12-31")
        self.assertIn("prob_bp must be between 1 and 9999", str(ctx0.exception))

        with self.assertRaises(gl.vm.UserError) as ctx10k:
            ledger.register_prediction("Event with 10000 prob", 10000, "2026-12-31")
        self.assertIn("prob_bp must be between 1 and 9999", str(ctx10k.exception))

        # Negative and over-10000
        with self.assertRaises(gl.vm.UserError):
            ledger.register_prediction("Negative prob", -100, "2026-12-31")
        with self.assertRaises(gl.vm.UserError):
            ledger.register_prediction("Over 10000 prob", 15000, "2026-12-31")

        # Empty event text
        with self.assertRaises(gl.vm.UserError) as ctx_empty:
            ledger.register_prediction("   ", 5000, "2026-12-31")
        self.assertIn("empty event text", str(ctx_empty.exception))

        # Event text exceeding 300 characters
        long_text = "A" * 301
        with self.assertRaises(gl.vm.UserError) as ctx_long:
            ledger.register_prediction(long_text, 5000, "2026-12-31")
        self.assertIn("event text exceeds 300 characters", str(ctx_long.exception))

        # Event text exactly 300 characters is accepted
        valid_300 = "B" * 300
        pid300 = ledger.register_prediction(valid_300, 5000, "2026-12-31")
        self.assertEqual(len(pid300), 12)


if __name__ == "__main__":
    unittest.main()
