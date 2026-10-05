# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from genlayer import *


class Probe(gl.Contract):
    probe_results: str

    def __init__(self):
        sender = gl.message.sender_address
        sender_hex = sender.as_hex
        sender_str = str(sender)

        import hashlib
        h = hashlib.sha256(b"calibration_ledger_probe").hexdigest()[:12]
        user_error_ok = (gl.vm.UserError.__name__ == "UserError")

        initial_report = {
            "sender_address": sender_hex,
            "sender_str": sender_str,
            "hashlib_sha256_prefix": h,
            "user_error_class": "gl.vm.UserError" if user_error_ok else "UNKNOWN",
            "strict_eq_passed": False,
            "prompt_response_type": "",
            "prompt_raw_sample": "",
            "consensus_decision": "",
        }
        self.probe_results = json.dumps(initial_report)

    @gl.public.view
    def get_results(self) -> str:
        return self.probe_results

    @gl.public.write
    def probe_consensus(self) -> None:
        def compute_nondet() -> str:
            # Test prompt with response_format="json"
            prompt_res = gl.nondet.exec_prompt(
                'Provide JSON: {"status": "PONG", "value": 42}',
                response_format="json",
            )
            res_type = type(prompt_res).__name__
            raw_s = str(prompt_res).strip()

            # Deterministic extraction of decision
            decision = "PONG" if "PONG" in raw_s.upper() else "UNKNOWN"
            return f"TYPE_{res_type}|DEC_{decision}|RAW_{raw_s[:50]}"

        eq_val = gl.eq_principle.strict_eq(compute_nondet)

        curr = json.loads(self.probe_results)
        curr["strict_eq_passed"] = True
        curr["consensus_string"] = eq_val

        # Parse type and decision from consensus string
        parts = eq_val.split("|")
        for p in parts:
            if p.startswith("TYPE_"):
                curr["prompt_response_type"] = p.replace("TYPE_", "")
            elif p.startswith("DEC_"):
                curr["consensus_decision"] = p.replace("DEC_", "")
            elif p.startswith("RAW_"):
                curr["prompt_raw_sample"] = p.replace("RAW_", "")

        self.probe_results = json.dumps(curr)
