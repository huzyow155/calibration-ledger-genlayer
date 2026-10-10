import unittest
import sys
import os

# Ensure repo root and tests dir are on import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from contracts.CalibrationLedger import CalibrationLedger, gl


class TestLayer3ConsensusEquivalence(unittest.TestCase):
    """Layer 3: Multi-validator equivalence principle and consensus agreement/disagreement."""

    def setUp(self):
        self.ledger = CalibrationLedger()
        self.ledger.predictions = {}
        self.ledger.by_forecaster = {}
        self.ledger.meta = {}

        gl.message_raw = {"datetime": "2026-10-10T12:00:00Z"}
        gl.message.sender_address.as_hex = "0x1111111111111111111111111111111111111111"

    def test_validators_agree_on_identical_grounded_outcomes(self):
        """Validators returning identical canonical outcomes achieve consensus."""
        source = "https://reuters.com/article/fomc.md"
        page_text = "The Federal Reserve Chairman announced a 25bp interest rate cut following the November FOMC meeting."
        gl.nondet.web.pages[source] = page_text

        pid = self.ledger.register_prediction(
            "Will Federal Reserve cut rates by 25bp?", 8000, "2026-10-10T12:10:00Z", source
        )

        gl.message_raw = {"datetime": "2026-10-10T12:15:00Z"}

        # Simulate 3 validators that all independently return YES with a grounded quote
        validator_outputs = [
            {"outcome": "YES", "quote": "Federal Reserve Chairman announced a 25bp interest rate cut"},
            {"outcome": "YES", "quote": "a 25bp interest rate cut following the November FOMC meeting"},
            {"outcome": "YES", "quote": "Federal Reserve Chairman announced a 25bp interest rate cut"},
        ]

        def multi_validator_strict_eq(eval_fn):
            tokens = []
            for out in validator_outputs:
                gl.nondet.prompt_handler = lambda p, o=out: o
                tokens.append(eval_fn())
            first = tokens[0]
            if not all(t == first for t in tokens):
                raise RuntimeError("Consensus failure: validators disagreed")
            return first

        original_strict_eq = gl.eq_principle.strict_eq
        try:
            gl.eq_principle.strict_eq = multi_validator_strict_eq
            res = self.ledger.resolve_event(pid)
            self.assertEqual(res, "YES")
        finally:
            gl.eq_principle.strict_eq = original_strict_eq

    def test_validators_disagree_on_divergent_outcomes(self):
        """Validators returning divergent outcomes fail to reach consensus."""
        source = "https://reuters.com/article/startup.md"
        page_text = "The startup released beta previews to select developers, but general public availability remains delayed."
        gl.nondet.web.pages[source] = page_text

        pid = self.ledger.register_prediction(
            "Did startup launch AI search in Q3?", 5000, "2026-10-10T12:10:00Z", source
        )

        gl.message_raw = {"datetime": "2026-10-10T12:15:00Z"}

        # Validator 1 extracts YES, Validator 2 extracts NO
        validator_outputs = [
            {"outcome": "YES", "quote": "startup released beta previews to select developers"},
            {"outcome": "NO", "quote": "general public availability remains delayed"},
        ]

        def multi_validator_strict_eq(eval_fn):
            tokens = []
            for out in validator_outputs:
                gl.nondet.prompt_handler = lambda p, o=out: o
                tokens.append(eval_fn())
            first = tokens[0]
            if not all(t == first for t in tokens):
                raise RuntimeError("Consensus failure: validators disagreed on outcome token")
            return first

        original_strict_eq = gl.eq_principle.strict_eq
        try:
            gl.eq_principle.strict_eq = multi_validator_strict_eq
            with self.assertRaises(RuntimeError) as ctx:
                self.ledger.resolve_event(pid)
            self.assertIn("validators disagreed", str(ctx.exception))
        finally:
            gl.eq_principle.strict_eq = original_strict_eq


if __name__ == "__main__":
    unittest.main()
