# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from genlayer import *


class CalibratedCouncil(gl.Contract):
    ledger_address: Address
    endorsements: TreeMap[str, str]
    meta: TreeMap[str, str]

    def __init__(self, ledger_address_str: str):
        self.ledger_address = Address(ledger_address_str)

    def _ensure_meta_init(self) -> None:
        if "next_id" not in self.meta:
            self.meta["next_id"] = "1"
        if "recent" not in self.meta:
            self.meta["recent"] = "[]"

    @gl.public.write
    def endorse_policy(self, statement: str) -> str:
        self._ensure_meta_init()
        clean_statement = str(statement).strip()
        if not (10 <= len(clean_statement) <= 250):
            raise gl.vm.UserError("statement length must be between 10 and 250 chars")

        author = gl.message.sender_address.as_hex

        # Query calibration report directly from CalibrationLedger
        ledger = gl.get_contract_at(self.ledger_address)
        raw_report = ledger.view().get_calibration_report(author)

        if not raw_report:
            raise gl.vm.UserError("no calibration report found for caller")

        report = json.loads(raw_report)
        n_scored = int(report.get("n_scored", 0))
        brier = report.get("brier_score")

        if n_scored < 2:
            raise gl.vm.UserError("forecaster requires at least 2 scored predictions to join council")

        if brier is None or float(brier) > 0.15:
            raise gl.vm.UserError("forecaster Brier score exceeds calibrated council threshold of 0.15")

        rec_id = self.meta["next_id"]
        next_num = int(rec_id) + 1
        self.meta["next_id"] = str(next_num)

        record = {
            "id": rec_id,
            "author": author,
            "brier_score": brier,
            "statement": clean_statement,
        }
        self.endorsements[rec_id] = json.dumps(record, sort_keys=True, separators=(",", ":"))

        recent_list = json.loads(self.meta["recent"])
        recent_list.insert(0, rec_id)
        if len(recent_list) > 50:
            recent_list = recent_list[:50]
        self.meta["recent"] = json.dumps(recent_list)

        return rec_id

    @gl.public.view
    def get_endorsement(self, endorsement_id: str) -> str:
        eid = str(endorsement_id).strip()
        return self.endorsements.get(eid, "")

    @gl.public.view
    def list_recent(self, limit: int = 10) -> str:
        if "recent" not in self.meta:
            return "[]"
        try:
            items = json.loads(self.meta["recent"])
            bounded_limit = min(max(1, int(limit)), 20)
            return json.dumps(items[:bounded_limit])
        except Exception:
            return "[]"
