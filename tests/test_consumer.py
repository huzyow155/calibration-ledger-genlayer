import unittest
import sys
import os
import json

# Ensure repo root and tests dir are on import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from contracts.CalibrationLedger import gl
from examples.consumer.CalibratedCouncil import CalibratedCouncil


class TestCalibratedCouncilConsumer(unittest.TestCase):
    """Test consumer contract that integrates with CalibrationLedger."""

    def setUp(self):
        self.council = CalibratedCouncil("0xAaD7A38119EeE71CAC50ddf112d4E12fBB00026a")
        self.council.endorsements = {}
        self.council.meta = {}

    def test_overconfident_forecaster_rejected_from_council(self):
        """Forecasters with Brier score exceeding 0.15 threshold are rejected."""
        # Mock get_contract_at to return report of overconfident forecaster (Brier 0.49505)
        class MockLedger:
            def view(self):
                return self
            def get_calibration_report(self, forecaster):
                return json.dumps({
                    "forecaster": forecaster,
                    "n_scored": 2,
                    "brier_score": 0.49505,
                })

        gl.get_contract_at = lambda addr: MockLedger()

        statement = "We recommend maintaining a 30 percent liquidity buffer for Q4 volatility."
        with self.assertRaises(gl.vm.UserError) as ctx:
            self.council.endorse_policy(statement)
        self.assertIn("exceeds calibrated council threshold", str(ctx.exception))

    def test_well_calibrated_forecaster_accepted(self):
        """Well-calibrated forecaster (Brier 0.01625 <= 0.15) successfully joins council."""
        class MockLedger:
            def view(self):
                return self
            def get_calibration_report(self, forecaster):
                return json.dumps({
                    "forecaster": forecaster,
                    "n_scored": 2,
                    "brier_score": 0.01625,
                })

        gl.get_contract_at = lambda addr: MockLedger()

        statement = "We recommend maintaining a 30 percent liquidity buffer for Q4 volatility."
        eid = self.council.endorse_policy(statement)
        self.assertEqual(eid, "1")

        rec = json.loads(self.council.get_endorsement("1"))
        self.assertEqual(rec["statement"], statement)
        self.assertEqual(rec["brier_score"], 0.01625)


if __name__ == "__main__":
    unittest.main()
