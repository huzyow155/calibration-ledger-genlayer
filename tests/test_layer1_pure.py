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
    _validate_source_url,
    _parse_iso8601_utc,
    MAX_EVENT_TEXT_LEN,
    MAX_URL_LEN,
    MIN_QUOTE_LEN,
    gl,
)


class TestLayer1PureMathAndValidation(unittest.TestCase):
    """Layer 1: Pure functions, boundary math, URL validation allowlist, and datetime parsing."""

    def test_brier_score_known_values(self):
        self.assertIsNone(_calculate_brier_score([]))
        self.assertEqual(_calculate_brier_score([(5000, "YES")]), 0.25)
        self.assertEqual(_calculate_brier_score([(5000, "NO")]), 0.25)
        self.assertEqual(_calculate_brier_score([(9000, "YES")]), 0.01)
        self.assertEqual(_calculate_brier_score([(9000, "NO")]), 0.81)
        self.assertEqual(_calculate_brier_score([(8000, "YES"), (2000, "NO")]), 0.04)

    def test_trap_test_overconfident_vs_calibrated(self):
        """The Trap Test: 10 predictions (9 hits, 1 miss)."""
        predictions_overconfident = [(9900, "YES")] * 9 + [(9900, "NO")] * 1
        brier_overconfident = _calculate_brier_score(predictions_overconfident)

        predictions_calibrated = [(9000, "YES")] * 9 + [(9000, "NO")] * 1
        brier_calibrated = _calculate_brier_score(predictions_calibrated)

        print("\n=== THE TRAP TEST DEMONSTRATION ===")
        print(f"Forecaster A (Overconfident 9900 bp): Brier Score = {brier_overconfident:.6f}")
        print(f"Forecaster B (Calibrated 9000 bp):   Brier Score = {brier_calibrated:.6f}")
        self.assertAlmostEqual(brier_overconfident, 0.0981, places=4)
        self.assertAlmostEqual(brier_calibrated, 0.0900, places=4)
        self.assertGreater(brier_overconfident, brier_calibrated)

    def test_calibration_buckets_boundaries(self):
        predictions = [
            (1, "YES"),
            (999, "NO"),
            (1000, "YES"),
            (2500, "NO"),
            (5000, "YES"),
            (5500, "YES"),
            (9999, "NO"),
        ]
        buckets = _calculate_calibration_buckets(predictions)
        bucket_by_range = {b["range"]: b for b in buckets}
        self.assertIn("0-10", bucket_by_range)
        self.assertEqual(bucket_by_range["0-10"]["n"], 2)
        self.assertEqual(bucket_by_range["0-10"]["hits"], 1)

    def test_url_validation_strict_allowlist_and_attack_matrix(self):
        """Comprehensive verification of real parser vs naive attack variants."""
        # Valid URLs
        valid_samples = [
            "https://raw.githubusercontent.com/huzyow155/fixtures/main/case.md",
            "https://reuters.com/business/finance-news-2026",
            "https://apnews.com/article/election-results-12345",
            "https://bbc.com/news/world-67890",
            "https://ALLOWED.com/x", # case-normalization
            "https://reuters.com:443/article", # explicit port 443
            "https://reuters.com./article", # trailing dot stripped
        ]
        # Temporarily mock ALLOWED_DOMAINS to include allowed.com for attack test suite
        from contracts import CalibrationLedger as ledger_mod
        orig_allowed = ledger_mod.ALLOWED_DOMAINS
        ledger_mod.ALLOWED_DOMAINS = orig_allowed + ("allowed.com",)

        try:
            # Valid URLs must pass
            self.assertEqual(
                _validate_source_url("https://raw.githubusercontent.com/test"),
                "https://raw.githubusercontent.com/test",
            )
            self.assertEqual(
                _validate_source_url("https://ALLOWED.com/x"),
                "https://ALLOWED.com/x",
            )
            self.assertEqual(
                _validate_source_url("https://allowed.com./x"),
                "https://allowed.com./x",
            )

            # Strict attack vectors required by specification
            attack_cases = [
                ("https://allowed.com.evil.com/x", "subdomain trick"),
                ("https://evil.com/#allowed.com", "fragment trick"),
                ("https://evil.com/?u=allowed.com", "query trick"),
                ("https://allowed.com@evil.com/x", "userinfo trick"),
                ("https://allowed.com:443@evil.com/x", "userinfo with port trick"),
                ("http://allowed.com/x", "non-https scheme"),
                ("https://xn--llowed-7ya.com/x", "punycode lookalike"),
                ("https://allowed.com:8443/x", "non-standard port"),
                ("https://allowed.com/" + ("a" * 301), "url length exceeds cap"),
                ("https://127.0.0.1/x", "ip literal host"),
                ("https:///path/without/host", "missing hostname"),
            ]

            for bad_url, description in attack_cases:
                with self.assertRaises(gl.vm.UserError, msg=f"Failed to reject {description}: {bad_url}"):
                    _validate_source_url(bad_url)

        finally:
            ledger_mod.ALLOWED_DOMAINS = orig_allowed

    def test_iso8601_utc_datetime_parsing(self):
        """Strict ISO-8601 UTC datetime parser."""
        valid_dt = "2026-10-10T15:00:00Z"
        ts = _parse_iso8601_utc(valid_dt)
        self.assertGreater(ts, 1700000000)

        # Invalid variants must raise UserError
        invalid_dts = [
            "2026-10-10 15:00:00",  # missing T and Z
            "2026-10-10T15:00:00+02:00",  # non-UTC offset
            "tomorrow at 5pm",  # free text
            "2026-13-10T15:00:00Z",  # invalid month
            "2026-10-10T15:00:00",  # missing Z
        ]
        for bad_dt in invalid_dts:
            with self.assertRaises(gl.vm.UserError):
                _parse_iso8601_utc(bad_dt)


if __name__ == "__main__":
    unittest.main()
