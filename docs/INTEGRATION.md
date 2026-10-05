# Integration Guide and API Specification

This document provides complete technical specifications, exact view schemas from on-chain read-backs, error conditions, and measured latencies for integrating with the `CalibrationLedger` contract.

---

## 1. Contract Overview

- **Contract Address**: `0xAaD7A38119EeE71CAC50ddf112d4E12fBB00026a`
- **Network**: GenLayer Studionet (Chain ID 61999)
- **RPC URL**: `https://studio.genlayer.com/api`
- **Explorer URL**: `https://explorer-studio.genlayer.com/address/0xAaD7A38119EeE71CAC50ddf112d4E12fBB00026a`

---

## 2. Public Methods

### `register_prediction(event_text: str, prob_bp: int, deadline_hint: str) -> str`

Registers a probabilistic forecast for a future binary event before resolution evidence is available.

- **Parameters**:
  - `event_text` (`str`): Natural language description of the binary event. Must be non-empty and `<= 300` characters.
  - `prob_bp` (`int`): Forecast probability in basis points (`1` to `9999`, where 10000 = 100%). Literal certainty (`0` or `10000`) is rejected.
  - `deadline_hint` (`str`): Date or milestone reference indicating the timeframe (e.g., `"2026-12-31"`).
- **Returns**: `prediction_id` (`str`): A 12-character hex identifier derived deterministically from `sha256(forecaster|event_text|prob_bp|deadline_hint|nonce)[:12]`.
- **Measured Latency**: 6.19s - 11.29s (Average ~8.0s)
- **Example Call (`genlayer-js`)**:
  ```javascript
  const txHash = await client.writeContract({
    address: "0xAaD7A38119EeE71CAC50ddf112d4E12fBB00026a",
    functionName: "register_prediction",
    args: [
      "Did Apple announce the iPhone 16 series with Apple Intelligence in September 2024?",
      9000,
      "2024-09-30"
    ]
  });
  ```

---

### `resolve_event(prediction_id: str, evidence_text: str) -> str`

Triggers multi-validator LLM consensus to evaluate real-world evidence against the registered event. Anyone can call this method once evidence is available.

- **Parameters**:
  - `prediction_id` (`str`): The 12-character hex ID of an `OPEN` prediction.
  - `evidence_text` (`str`): Text excerpt from news reporting, press releases, or official transcripts documenting the outcome.
- **Returns**: `consensus_outcome` (`str`): One of `"YES"`, `"NO"`, or `"AMBIGUOUS"`.
- **Consensus Mechanics**:
  - Independent validators process the untrusted event text and evidence in a structured prompt.
  - A quote is extracted and verified: if shorter than 12 characters or not found verbatim in `evidence_text`, the outcome automatically falls back to `"AMBIGUOUS"`.
  - Validators reach consensus via `gl.eq_principle.strict_eq` on a canonical token (`"YES|GROUNDED"`, `"NO|GROUNDED"`, `"AMBIGUOUS|NONE"`).
- **Measured Latency**: 13.25s - 21.45s (Average ~17.8s)
- **Example Call (`genlayer-js`)**:
  ```javascript
  const txHash = await client.writeContract({
    address: "0xAaD7A38119EeE71CAC50ddf112d4E12fBB00026a",
    functionName: "resolve_event",
    args: [
      "8bb0c3ef8d2d",
      "Apple officially unveiled the iPhone 16 family powered by Apple Intelligence during its 'It's Glowtime' keynote event on September 9 2024 in Cupertino."
    ]
  });
  ```

---

## 3. View Methods and Real Read-Back Schemas

### `get_prediction(prediction_id: str) -> str`

Fetches the complete canonical record for a specific prediction.

- **Real Read-Back Example (Resolved YES)**:
  ```json
  {
    "created_at_round": "1",
    "deadline_hint": "2024-09-30",
    "event_text": "Did Apple announce the iPhone 16 series with Apple Intelligence in September 2024?",
    "forecaster": "0xc65E820fb874748Bf169739844f545a3543D0c50",
    "outcome": "YES",
    "prediction_id": "8bb0c3ef8d2d",
    "prob_bp": 9000,
    "resolution_evidence": "Apple officially unveiled the iPhone 16 family powered by Apple Intelligence during its 'It's Glowtime' keynote event on September 9 2024 in Cupertino.",
    "resolution_quote": "GROUNDED",
    "schema_version": "1",
    "status": "RESOLVED"
  }
  ```

---

### `list_predictions_by_forecaster(forecaster: str, limit: int = 20) -> str`

Discovery view that returns a JSON list of prediction IDs registered by the given forecaster address.

- **Real Read-Back Example**:
  ```json
  ["8bb0c3ef8d2d", "40b6e6aa4f33", "51fba249d92a"]
  ```

---

### `get_calibration_report(forecaster: str) -> str`

Computes a fresh Brier score and decile calibration bucket histogram for a forecaster on demand.

- **Real Read-Back Example (Forecaster A - Overconfident)**:
  ```json
  {
    "brier_score": 0.49505,
    "buckets": [
      {
        "hit_rate": 0.5,
        "hits": 1,
        "n": 2,
        "range": "90-100"
      }
    ],
    "forecaster": "0xc65E820fb874748Bf169739844f545a3543D0c50",
    "n_registered": 3,
    "n_resolved": 3,
    "n_scored": 2,
    "schema_version": "1"
  }
  ```

- **Real Read-Back Example (Forecaster B - Well-Calibrated)**:
  ```json
  {
    "brier_score": 0.01625,
    "buckets": [
      {
        "hit_rate": 0.0,
        "hits": 0,
        "n": 1,
        "range": "10-20"
      },
      {
        "hit_rate": 1.0,
        "hits": 1,
        "n": 1,
        "range": "80-90"
      }
    ],
    "forecaster": "0x5365D235deed7c291Bb21aA36938F783EFFB2D29",
    "n_registered": 2,
    "n_resolved": 2,
    "n_scored": 2,
    "schema_version": "1"
  }
  ```

---

## 4. User Errors Reference

All errors inherit from `gl.vm.UserError` with explicit error descriptions:

| Error String | Trigger Condition |
| :--- | :--- |
| `empty event text` | `event_text` is empty or whitespace-only |
| `event text exceeds 300 characters` | `len(event_text) > 300` |
| `prob_bp must be between 1 and 9999` | `prob_bp < 1` or `prob_bp > 9999` (literal 0 and 10000 forbidden) |
| `prediction not found` | `prediction_id` does not exist in `predictions` storage |
| `resolving an already-resolved prediction` | `resolve_event` invoked on a prediction with `status == "RESOLVED"` |
| `evidence text cannot be empty` | Submitted `evidence_text` is empty or whitespace |
