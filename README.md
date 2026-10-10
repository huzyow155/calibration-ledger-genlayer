# CalibrationLedger

**CalibrationLedger** is an Intelligent Contract deployed to GenLayer studionet that benchmarks probabilistic forecasters on calibration and Brier score, rather than raw directional accuracy.

- **Contract Address**: [`0x7D98a9272f23cDeD5E54A62fbC0d3A535ac7B7da`](https://explorer-studio.genlayer.com/address/0x7D98a9272f23cDeD5E54A62fbC0d3A535ac7B7da)
- **Explorer**: [https://explorer-studio.genlayer.com/address/0x7D98a9272f23cDeD5E54A62fbC0d3A535ac7B7da](https://explorer-studio.genlayer.com/address/0x7D98a9272f23cDeD5E54A62fbC0d3A535ac7B7da)
- **Network**: GenLayer Studionet (Chain ID 61999)
- **Consumer Contract (CalibratedCouncil)**: [`0x7B567289162C9D87a02B160B5494fb2Dfa3277ca`](https://explorer-studio.genlayer.com/address/0x7B567289162C9D87a02B160B5494fb2Dfa3277ca)

---

## The Problem: Why Accuracy Alone Rewards Bad Forecasting

In conventional forecasting and prediction markets, participants are rewarded purely for directional accuracy or capital size:
- A forecaster who always claims 99% certainty on the favorite appears "accurate" whenever the favorite wins, but provides no signal about true likelihoods and conveys false certainty.
- Conversely, a forecaster who states 70% probability on 10 events and observes exactly 7 happen is exceptionally well-calibrated, yet is penalized under simplistic binary metrics when 3 events fail.

CalibrationLedger shifts incentives from raw accuracy to **statistical calibration**:
1. Forecasters register an open probability in basis points (`1` to `9999`) along with an enforced resolution deadline (`resolve_after` in ISO-8601 UTC) and a committed source URL from an authoritative publisher allowlist.
2. The resolution source is committed at registration time. The contract itself retrieves the page content via GenVM web APIs; callers provide zero self-authored evidence text.
3. GenLayer's multi-validator Intelligent Consensus evaluates whether the fetched page verifies the event, enforcing verbatim quote grounding against the retrieved text.
4. Resolutions follow a contestable lifecycle: `OPEN -> PROVISIONAL -> SETTLED`. A 300-second contest window prevents premature or hostile first settlements.
5. Deterministic on-chain code computes each forecaster's **Brier score** and an **empirical decile calibration histogram**, counting exclusively settled predictions.

---

## Trust Model and Source Authentication

- **Fixed Contract Allowlist**: Source URLs must belong to a hard-coded allowlist of authoritative publisher domains. The contract validates structured URL components using `urllib.parse.urlsplit` (requiring `https`, no userinfo, port 443 or omitted, no fragment, pure ASCII, no IP literals, and domain suffix matching).
- **Authorized Publisher Domains**:
  1. `raw.githubusercontent.com`: Authoritative reproducible research fixtures and code archives.
  2. `github.com`: Software releases and source commit provenance.
  3. `reuters.com`: Independent global wire service.
  4. `apnews.com`: Associated Press wire service.
  5. `bbc.com`: Public global broadcast journalism.
  6. `bloomberg.com`: Financial and macroeconomic market data.
  7. `wikipedia.org`: Collaborative reference documentation for settled historical events.
  8. `noaa.gov`: Official meteorological, oceanographic, and climate scientific reports.
  9. `nasa.gov`: Spaceflight and astronomical scientific agency releases.
  10. `ecb.europa.eu`: European Central Bank monetary policy rates and official releases.
- **Honest Trust Boundary**: "Source authentication" means the resolution source URL belongs to an allowlisted domain. The contract does not independently verify the publisher's external accuracy. Known limitation: trivially certain events can be registered to cultivate a favorable Brier score; downstream consumers (such as CalibratedCouncil) serve as an illustrative demonstration consumer rather than a Sybil-resistant identity protocol.

---

## State Lifecycle and Contestation

```
[ OPEN ] 
   │
   │  resolve_event(pid) [after resolve_after, web fetch, grounded quote]
   ▼
[ PROVISIONAL ] ── contest_resolution(pid, alt_source_url) [within 300s window]
   │
   │  settle(pid) [after 300s contest window expires]
   ▼
[ SETTLED ] ── counted by get_calibration_report & CalibratedCouncil
```

- **`resolve_after` Timing**: Must be at least 300 seconds in the future relative to the deterministic transaction execution timestamp (`gl.message_raw["datetime"]`). Registration in the past or under this lead time reverts.
- **Provisional Stage**: First successful grounded resolution marks status `PROVISIONAL` and stores the outcome, resolved timestamp, quote grounding flag, and SHA-256 hash of the fetched text snapshot. Ambiguous results or fetch failures leave status `OPEN`.
- **Contest Window**: Within 300 seconds of resolution, anyone may contest the provisional outcome once. If the fresh grounded evaluation flips the result, the provisional outcome is updated.
- **Settlement**: After 300 seconds have elapsed from provisional resolution, any caller may invoke `settle(pid)` to transition the prediction to `SETTLED`.
- **Downstream Consumer Gate**: `get_calibration_report` and `CalibratedCouncil.endorse_policy` count only `SETTLED` predictions. Predictions remaining in `PROVISIONAL` status do not count toward council eligibility.

---

## The Trap Test: Demonstrated With Real Numbers

The Brier score penalizes confident wrong calls quadratically:
$$B = \frac{1}{N} \sum_{i=1}^{N} (p_i - o_i)^2$$

Consider two forecasters evaluated over 10 events where 9 resolve YES and 1 resolves NO (both have an **identical raw hit rate of 90.0%**):

- **Forecaster A (Overconfident 9900 bp / 99%)**:
  - 9 hits: $9 \times (0.99 - 1.0)^2 = 9 \times 0.0001 = 0.0009$
  - 1 miss: $1 \times (0.99 - 0.0)^2 = 1 \times 0.9801 = 0.9801$
  - **Total Brier Score: 0.098100** (severe penalty caused by the single failed prediction)

- **Forecaster B (Well-Calibrated 9000 bp / 90%)**:
  - 9 hits: $9 \times (0.90 - 1.0)^2 = 9 \times 0.0100 = 0.0900$
  - 1 miss: $1 \times (0.90 - 0.0)^2 = 1 \times 0.8100 = 0.8100$
  - **Total Brier Score: 0.090000**

---

## Contract API Summary

| Method | Type | Parameters | Returns | Description |
| :--- | :--- | :--- | :--- | :--- |
| `register_prediction` | Write | `event_text`, `prob_bp`, `resolve_after`, `source_url` | `prediction_id` | Registers an open prediction with future ISO-8601 UTC resolve deadline and allowlisted source URL. |
| `resolve_event` | Write | `prediction_id` | `outcome` (`YES`, `NO`, `AMBIGUOUS`) | Contract fetches committed source URL; sets status to `PROVISIONAL` on grounded YES/NO, leaves `OPEN` on ambiguous. |
| `contest_resolution` | Write | `prediction_id`, `alt_source_url` | `outcome` | Re-evaluates provisional resolution within 300s contest window; at most once per prediction. |
| `settle` | Write | `prediction_id` | `"SETTLED"` | Transitions status from `PROVISIONAL` to `SETTLED` once the 300s contest window has passed. |
| `get_prediction` | View | `prediction_id` | JSON string | Returns complete prediction record. |
| `list_predictions_by_forecaster` | View | `forecaster`, `limit` | JSON array of IDs | Discovery view for dApps to query a forecaster's past predictions. |
| `get_calibration_report` | View | `forecaster` | JSON report | Computes Brier score and decile calibration histogram over `SETTLED` predictions only. |

---

## Deploy and Test Reproduction

### Prerequisites
- Node.js v18+
- Python 3.10+
- `genlayer-js` v1.1.8+

### Setup
```bash
git clone https://github.com/huzyow155/calibration-ledger-genlayer.git
cd calibration-ledger-genlayer
npm install
```

### Running the Test Suite
```bash
python -m unittest discover tests
```

### Deploying to Studionet
```bash
node scripts/deploy/deploy_ledger.js
node scripts/deploy/deploy_consumer.js
```

### Verifying Source Hash
```bash
npm run verify:source
```
Source verification queries the deployment transaction receipt via JSON-RPC (`eth_getTransactionByHash`) and decodes `result.data.contract_code` to confirm that the on-chain code matches the local source SHA-256 character-for-character.
