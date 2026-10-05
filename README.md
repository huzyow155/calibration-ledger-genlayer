# CalibrationLedger

**CalibrationLedger** is a standalone Intelligent Contract deployed to GenLayer studionet that benchmarks probabilistic forecasters on calibration and Brier score, rather than raw directional accuracy.

- **Contract Address**: [`0xAaD7A38119EeE71CAC50ddf112d4E12fBB00026a`](https://explorer-studio.genlayer.com/address/0xAaD7A38119EeE71CAC50ddf112d4E12fBB00026a)
- **Explorer**: [https://explorer-studio.genlayer.com/address/0xAaD7A38119EeE71CAC50ddf112d4E12fBB00026a](https://explorer-studio.genlayer.com/address/0xAaD7A38119EeE71CAC50ddf112d4E12fBB00026a)
- **Network**: GenLayer Studionet (Chain ID 61999)

---

## The Problem: Why Accuracy Alone Rewards Bad Forecasting

In conventional forecasting and prediction markets, participants are rewarded purely for directional accuracy or capital size:
- A forecaster who always claims 99% certainty on the favorite appears "accurate" whenever the favorite wins, but provides no signal about true likelihoods and conveys false certainty.
- Conversely, a forecaster who states 70% probability on 10 events and observes exactly 7 happen is exceptionally well-calibrated, yet is penalized under simplistic binary metrics when 3 events fail.

CalibrationLedger shifts incentives from raw accuracy to **statistical calibration**:
1. Anyone can register a probability in basis points (`1` to `9999`) for a specific future binary event before it resolves.
2. Once real-world evidence of the outcome exists, anyone can submit it.
3. GenLayer's multi-validator Intelligent Consensus extracts a grounded `YES`, `NO`, or `AMBIGUOUS` classification with verbatim quote verification.
4. Deterministic on-chain code computes each forecaster's **Brier score** and an **empirical decile calibration histogram**, fully reproducible and verifiable by anyone.

---

## The Trap Test: Demonstrated With Real Numbers

The Brier score strictly penalizes confident wrong calls quadratically:
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

Forecaster B achieves a lower, superior Brier score despite having the exact same raw accuracy, because their probability distribution genuinely reflects real-world frequency.

### Empirical On-Chain Demonstration
On GenLayer studionet, Forecaster A registered a 9900 bp prediction that failed and a 9000 bp prediction that succeeded, resulting in an on-chain Brier score of **0.49505**. Forecaster B registered honest calls (1000 bp on a failed event, 8500 bp on a successful event), achieving an on-chain Brier score of **0.01625** (over 30 times better).

---

## Why GenLayer?

Traditional EVM smart contracts cannot parse natural language news text or evaluate whether an unstructured press release verifies a forecasted event. Traditional oracles require manual committee votes or rigid numeric price feeds.

GenLayer enables:
1. **Intelligent Multi-Validator Consensus**: Independent validators run Large Language Models in a sandboxed GenVM environment to classify outcomes from free-text evidence.
2. **Deterministic Verbatim Grounding**: Python logic enforces that validator decisions cite verbatim quotations (>= 12 characters) present within the submitted evidence text, automatically converting unsupported claims to `AMBIGUOUS`.
3. **Equivalence Principle on Canonical Tokens**: Consensus is reached on compact canonical strings (`YES|GROUNDED`, `NO|GROUNDED`, `AMBIGUOUS|NONE`), guaranteeing validator quorum without prompt phrasing drift.

---

## Contract API Summary

| Method | Type | Parameters | Returns | Description |
| :--- | :--- | :--- | :--- | :--- |
| `register_prediction` | Write | `event_text`, `prob_bp`, `deadline_hint` | `prediction_id` (12 hex chars) | Registers an open prediction with probability in `[1, 9999]`. |
| `resolve_event` | Write | `prediction_id`, `evidence_text` | `outcome` (`YES`, `NO`, `AMBIGUOUS`) | Multi-validator LLM consensus with verbatim quote grounding. |
| `get_prediction` | View | `prediction_id` | JSON string | Returns complete prediction record. |
| `list_predictions_by_forecaster` | View | `forecaster`, `limit` | JSON array of IDs | Discovery view for dApps to query a forecaster's past predictions. |
| `get_calibration_report` | View | `forecaster` | JSON report | Freshly computes Brier score and decile calibration histogram. |

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
The test suite validates:
- **Layer 1 (Pure)**: Brier score calculations, boundary math, input limits, and the trap test demonstration.
- **Layer 2 (Mocked LLM)**: Double resolution protection, ungrounded quote fallback to AMBIGUOUS, exclusion of washes from Brier scores, and discovery view pagination.
- **Layer 3 (Consensus)**: Multi-validator equivalence agreement and divergence detection.

### Deploying to Studionet
```bash
node scripts/deploy/deploy_ledger.js
```

### Verifying Source Hash
```bash
node scripts/verify_source.js
```

---

## Known Limitations

1. **Evidence Quality Dependency**: The contract verifies whether submitted evidence text grounds the event; it does not crawl external websites to perform secondary fact-checking of the evidence itself.
2. **Wash Resolution on Ambiguity**: When evidence is inconclusive or quotations cannot be grounded verbatim, the event resolves to `AMBIGUOUS`. Ambiguous events increment `n_resolved` but are excluded from the Brier score average to prevent distorting a forecaster's score.
3. **Integer Basis Points Resolution**: Probabilities are bounded between 1 bp (0.01%) and 9999 bp (99.99%). Literal 0 and 10000 are forbidden because infinite/extreme Brier punishments occur on impossible claims.
4. **Sequential Nonce Ordering**: Identical events submitted by the same forecaster receive distinct IDs via a monotonic nonce disambiguator.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
