import unittest
import sys
import os
import json
import inspect
import time

# Ensure repo root and tests dir are on import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from contracts.CalibrationLedger import CalibrationLedger, gl
from examples.consumer.CalibratedCouncil import CalibratedCouncil


class TestLayer2MockedContract(unittest.TestCase):
    """Layer 2: Contract state machine, schema inspection, timing enforcement, contestation, and settlement."""

    def setUp(self):
        self.ledger = CalibrationLedger()
        self.ledger.predictions = {}
        self.ledger.by_forecaster = {}
        self.ledger.meta = {}

        # Default simulated time: 2026-10-10T12:00:00Z
        gl.message_raw = {"datetime": "2026-10-10T12:00:00Z"}
        gl.message.sender_address.as_hex = "0x1111111111111111111111111111111111111111"

        # Mock web responses
        gl.nondet.web.pages = {}
        gl.nondet.prompt_handler = None

    def test_resolve_event_signature_has_no_evidence_argument(self):
        """Assert via reflection/schema that resolve_event takes NO evidence argument."""
        sig = inspect.signature(CalibrationLedger.resolve_event)
        params = list(sig.parameters.keys())
        # Expected parameters: ['self', 'prediction_id']
        self.assertEqual(params, ["self", "prediction_id"])
        self.assertNotIn("evidence", params)
        self.assertNotIn("evidence_text", params)

    def test_register_timing_reverts(self):
        """Registration reverts if resolve_after is in the past or under MIN_LEAD_SECONDS (300s)."""
        valid_source = "https://raw.githubusercontent.com/org/repo/main/doc.md"

        # 1. Past resolve_after
        with self.assertRaises(gl.vm.UserError) as ctx:
            self.ledger.register_prediction(
                "Will inflation exceed 3 percent?", 6000, "2026-10-10T11:00:00Z", valid_source
            )
        self.assertIn("at least 300 seconds in the future", str(ctx.exception))

        # 2. Too short lead time (e.g. 120s in future: 12:02:00Z when now is 12:00:00Z)
        with self.assertRaises(gl.vm.UserError) as ctx:
            self.ledger.register_prediction(
                "Will inflation exceed 3 percent?", 6000, "2026-10-10T12:02:00Z", valid_source
            )
        self.assertIn("at least 300 seconds in the future", str(ctx.exception))

        # 3. Sufficient lead time (>= 300s: 12:05:00Z) succeeds
        pid = self.ledger.register_prediction(
            "Will inflation exceed 3 percent?", 6000, "2026-10-10T12:10:00Z", valid_source
        )
        self.assertTrue(len(pid) > 0)

    def test_early_resolve_reverts(self):
        """resolve_event reverts if called before resolve_after deadline."""
        valid_source = "https://raw.githubusercontent.com/org/repo/main/doc.md"
        pid = self.ledger.register_prediction(
            "Will mission succeed?", 8000, "2026-10-10T12:10:00Z", valid_source
        )

        # Current time is 12:00:00Z, deadline is 12:10:00Z
        with self.assertRaises(gl.vm.UserError) as ctx:
            self.ledger.resolve_event(pid)
        self.assertIn("cannot resolve before resolve_after deadline", str(ctx.exception))

    def test_fetch_failure_leaves_prediction_open(self):
        """If web fetch fails or returns empty, prediction stays OPEN for later retries."""
        valid_source = "https://raw.githubusercontent.com/org/repo/main/empty.md"
        pid = self.ledger.register_prediction(
            "Will mission succeed?", 8000, "2026-10-10T12:10:00Z", valid_source
        )

        # Advance time to 12:15:00Z (past deadline)
        gl.message_raw = {"datetime": "2026-10-10T12:15:00Z"}

        # Empty page
        gl.nondet.web.pages[valid_source] = ""
        res = self.ledger.resolve_event(pid)
        self.assertEqual(res, "AMBIGUOUS")

        record = json.loads(self.ledger.get_prediction(pid))
        self.assertEqual(record["status"], "OPEN")
        self.assertEqual(record["outcome"], None)
        self.assertEqual(record["last_attempt"], "2026-10-10T12:15:00Z")

    def test_unmentioned_page_gives_ambiguous_and_leaves_open(self):
        """If fetched text does not contain event outcome, returns AMBIGUOUS and stays OPEN."""
        valid_source = "https://raw.githubusercontent.com/org/repo/main/fixture.md"
        pid = self.ledger.register_prediction(
            "Did satellite launch achieve orbit?", 7500, "2026-10-10T12:10:00Z", valid_source
        )

        gl.message_raw = {"datetime": "2026-10-10T12:15:00Z"}
        gl.nondet.web.pages[valid_source] = "The cafeteria menu today included soup and sandwiches."
        gl.nondet.prompt_handler = lambda p: {"outcome": "AMBIGUOUS", "quote": ""}

        res = self.ledger.resolve_event(pid)
        self.assertEqual(res, "AMBIGUOUS")

        record = json.loads(self.ledger.get_prediction(pid))
        self.assertEqual(record["status"], "OPEN")

    def test_successful_resolution_and_caller_independence(self):
        """Any caller resolving the prediction produces the identical provisional outcome."""
        valid_source = "https://raw.githubusercontent.com/org/repo/main/launch.md"
        page_text = "Space Agency officially confirms the satellite reached planned geostationary orbit at 14:00 UTC."
        gl.nondet.web.pages[valid_source] = page_text
        gl.nondet.prompt_handler = lambda p: {
            "outcome": "YES",
            "quote": "satellite reached planned geostationary orbit",
        }

        pid = self.ledger.register_prediction(
            "Did satellite reach planned orbit?", 8500, "2026-10-10T12:10:00Z", valid_source
        )

        gl.message_raw = {"datetime": "2026-10-10T12:15:00Z"}
        # Caller 1 resolves
        gl.message.sender_address.as_hex = "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        res1 = self.ledger.resolve_event(pid)
        self.assertEqual(res1, "YES")

        record = json.loads(self.ledger.get_prediction(pid))
        self.assertEqual(record["status"], "PROVISIONAL")
        self.assertEqual(record["outcome"], "YES")
        self.assertEqual(record["resolution_quote"], "GROUNDED")
        self.assertTrue(len(record["source_hash"]) > 0)
        self.assertFalse(record["contested"])

    def test_contest_lifecycle_and_settlement(self):
        """
        Contest window workflow:
        1. Provisional outcome is YES.
        2. Within contest window (300s), contester submits valid alt source that proves NO.
        3. Outcome flips to NO, marked contested=True.
        4. Second contest attempt reverts.
        5. Contest after window reverts.
        6. Settle before window reverts.
        7. Settle after window succeeds -> SETTLED.
        """
        source_url = "https://raw.githubusercontent.com/org/repo/main/initial.md"
        alt_source_url = "https://raw.githubusercontent.com/org/repo/main/corrected.md"

        gl.nondet.web.pages[source_url] = "Initial announcement: Candidate Baker ahead in early tally."
        gl.nondet.web.pages[alt_source_url] = "Final official audit certified Candidate Baker lost the runoff election."

        gl.nondet.prompt_handler = lambda p: {
            "outcome": "YES",
            "quote": "Candidate Baker ahead in early tally",
        }

        pid = self.ledger.register_prediction(
            "Did Candidate Baker win the runoff?", 9000, "2026-10-10T12:10:00Z", source_url
        )

        # Resolve at 12:15:00Z -> Status: PROVISIONAL, outcome: YES
        gl.message_raw = {"datetime": "2026-10-10T12:15:00Z"}
        res = self.ledger.resolve_event(pid)
        self.assertEqual(res, "YES")

        # Attempt to settle before window (e.g. at 12:17:00Z, only 120s passed, window is 300s)
        gl.message_raw = {"datetime": "2026-10-10T12:17:00Z"}
        with self.assertRaises(gl.vm.UserError) as ctx:
            self.ledger.settle(pid)
        self.assertIn("contest window is still active", str(ctx.exception))

        # Contester calls contest_resolution within window (at 12:18:00Z)
        gl.message_raw = {"datetime": "2026-10-10T12:18:00Z"}
        gl.message.sender_address.as_hex = "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
        gl.nondet.prompt_handler = lambda p: {
            "outcome": "NO",
            "quote": "Candidate Baker lost the runoff election",
        }

        fresh_out = self.ledger.contest_resolution(pid, alt_source_url)
        self.assertEqual(fresh_out, "NO")

        rec_contested = json.loads(self.ledger.get_prediction(pid))
        self.assertEqual(rec_contested["status"], "PROVISIONAL")
        self.assertEqual(rec_contested["outcome"], "NO")
        self.assertTrue(rec_contested["contested"])
        self.assertEqual(rec_contested["contester"], "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB")

        # Second contest attempt must revert
        with self.assertRaises(gl.vm.UserError) as ctx:
            self.ledger.contest_resolution(pid, alt_source_url)
        self.assertIn("already been contested", str(ctx.exception))

        # (To test post-window contest revert, we use a prediction resolved at 12:15:00Z without prior contest)
        gl.message_raw = {"datetime": "2026-10-10T12:00:00Z"}
        pid2 = self.ledger.register_prediction(
            "Event 2", 5000, "2026-10-10T12:10:00Z", source_url
        )
        gl.message_raw = {"datetime": "2026-10-10T12:15:00Z"}
        gl.nondet.prompt_handler = lambda p: {
            "outcome": "YES",
            "quote": "Candidate Baker ahead in early tally",
        }
        self.ledger.resolve_event(pid2)

        # Advance time past contest window (12:21:00Z > 12:15:00Z + 300s)
        gl.message_raw = {"datetime": "2026-10-10T12:21:00Z"}
        with self.assertRaises(gl.vm.UserError) as ctx:
            self.ledger.contest_resolution(pid2)
        self.assertIn("contest window has expired", str(ctx.exception))

        # Settle after window succeeds
        settle_res = self.ledger.settle(pid)
        self.assertEqual(settle_res, "SETTLED")

        rec_settled = json.loads(self.ledger.get_prediction(pid))
        self.assertEqual(rec_settled["status"], "SETTLED")
        self.assertEqual(rec_settled["outcome"], "NO")

    def test_unsettled_provisional_predictions_excluded_from_calibration_and_council(self):
        """Unsettled PROVISIONAL predictions are excluded from n_scored and reject council endorsement."""
        forecaster_addr = "0x1111111111111111111111111111111111111111"
        gl.message.sender_address.as_hex = forecaster_addr
        source = "https://raw.githubusercontent.com/org/repo/main/data.md"
        gl.nondet.web.pages[source] = "The quarterly metric was officially published at 100."
        gl.nondet.prompt_handler = lambda p: {"outcome": "YES", "quote": "quarterly metric was officially published"}

        pid1 = self.ledger.register_prediction("Metric beats 50?", 8000, "2026-10-10T12:10:00Z", source)
        pid2 = self.ledger.register_prediction("Metric beats 80?", 9000, "2026-10-10T12:10:00Z", source)

        # Resolve both at 12:15:00Z -> Both are PROVISIONAL
        gl.message_raw = {"datetime": "2026-10-10T12:15:00Z"}
        self.ledger.resolve_event(pid1)
        self.ledger.resolve_event(pid2)

        # Read calibration report while both are PROVISIONAL
        rep_raw = self.ledger.get_calibration_report(forecaster_addr)
        rep = json.loads(rep_raw)
        self.assertEqual(rep["n_registered"], 2)
        self.assertEqual(rep["n_provisional"], 2)
        self.assertEqual(rep["n_settled"], 0)
        self.assertEqual(rep["n_scored"], 0)
        self.assertIsNone(rep["brier_score"])

        # Setup mock CalibratedCouncil connected to ledger
        council = CalibratedCouncil("0x1234")
        council.endorsements = {}
        council.meta = {}
        
        # Mock gl.get_contract_at to return self.ledger
        class MockContractProxy:
            def view(self):
                return self
            def get_calibration_report(self, addr):
                return self_ledger.get_calibration_report(addr)

        self_ledger = self.ledger
        gl.get_contract_at = lambda addr: MockContractProxy()

        # Endorsement MUST fail while predictions are only PROVISIONAL
        with self.assertRaises(gl.vm.UserError) as ctx:
            council.endorse_policy("Forecaster Alice policy proposal")
        self.assertIn("at least 2 scored predictions", str(ctx.exception))

        # Advance time and settle both predictions
        gl.message_raw = {"datetime": "2026-10-10T12:21:00Z"}
        self.ledger.settle(pid1)
        self.ledger.settle(pid2)

        # Report now has n_settled = 2, n_scored = 2, and valid Brier score
        rep_settled = json.loads(self.ledger.get_calibration_report(forecaster_addr))
        self.assertEqual(rep_settled["n_settled"], 2)
        self.assertEqual(rep_settled["n_scored"], 2)
        self.assertEqual(rep_settled["n_provisional"], 0)
        self.assertIsNotNone(rep_settled["brier_score"])
        # Both predicted YES and resolved YES: (0.8-1)^2 = 0.04, (0.9-1)^2 = 0.01 -> mean = 0.025
        self.assertAlmostEqual(rep_settled["brier_score"], 0.025, places=3)

        # Endorsement MUST now succeed!
        endorse_id = council.endorse_policy("Forecaster Alice policy proposal")
        self.assertEqual(endorse_id, "1")


if __name__ == "__main__":
    unittest.main()
