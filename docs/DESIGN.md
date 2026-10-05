# Architecture and Consensus Design

This document details the design decisions, consensus mechanics, and scoring methodology of the CalibrationLedger Intelligent Contract.

---

## 1. Core Problem: Calibration vs. Raw Accuracy

In forecasting, rewarding raw accuracy incentivizes destructive behavior:
- A forecaster who predicts 99% probability on every favored outcome appears "accurate" whenever the favorite wins, but provides zero information about true likelihoods and conveys false certainty.
- Conversely, a forecaster who assigns 70% probability to 10 events and observes exactly 7 happen is exceptionally well-calibrated, despite being "wrong" on 3 of them.

CalibrationLedger uses a strictly proper scoring rule, the **Brier Score**, and an empirical **decile calibration histogram** computed on-chain.

### Mathematical Formulation
The Brier Score for a set of $N$ binary predictions is:
$$B = \frac{1}{N} \sum_{i=1}^{N} (p_i - o_i)^2$$

Where:
- $p_i \in [0.0001, 0.9999]$ is the forecast probability ($prob\_bp / 10000$).
- $o_i \in \{0.0, 1.0\}$ is the outcome ($1.0$ for YES, $0.0$ for NO).
- Lower Brier scores indicate superior calibration and precision ($0.0$ is perfect; $0.25$ is a random 50/50 guess).

### The Overconfidence Trap
The quadratic penalty $(p_i - o_i)^2$ severely punishes overconfidence:
- If a forecaster predicts 9900 bp ($0.99$) and the event occurs ($1.0$), their penalty is $(0.99 - 1.0)^2 = 0.0001$.
- However, if just one 9900 bp prediction fails ($0.0$), the penalty is $(0.99 - 0.0)^2 = 0.9801$ (nearly 10,000 times larger).
- An honest forecaster predicting 6000 bp ($0.60$) on balanced events incurs $(0.60 - 0.0)^2 = 0.3600$ on misses, achieving a much lower average Brier score across mixed sets than an overconfident predictor with identical raw hit rates.

---

## 2. Consensus Design & Equivalence Principle

In GenLayer, multiple independent validators execute Intelligent Contract methods. For nondeterministic operations (such as LLM inference or web lookups), validators must reach agreement via the Equivalence Principle (`gl.eq_principle.strict_eq`).

### Why Raw LLM Output Cannot Be Compared Directly
1. **Phony Non-Determinism**: Independent LLMs output slight variations in casing, token ordering, punctuation, or formatting even under low temperature.
2. **Quorum Splitting**: If validators compare raw JSON strings containing quotes or reasoning text, minor whitespace or punctuation discrepancies cause validator disagreement and transaction revert.

### The Canonical Consensus Token
To guarantee validator agreement while preserving semantic rigor, `resolve_event` enforces a two-tier extraction pipeline:
1. **Semantic Extraction**: The validator LLM processes the untrusted event text and evidence in delimited prompt blocks, extracting an outcome candidate (`YES`, `NO`, `AMBIGUOUS`) and a quote.
2. **Deterministic Verbatim Grounding**: Python code executes a strict verification:
   - Is `len(quote) >= 12` characters?
   - Does `quote` appear verbatim inside the submitted evidence text?
   - If either check fails, the outcome is forced to `AMBIGUOUS`.
3. **Canonical Token Reduction**: The validator returns strictly one of three canonical tokens:
   - `"YES|GROUNDED"`
   - `"NO|GROUNDED"`
   - `"AMBIGUOUS|NONE"`

`gl.eq_principle.strict_eq` compares this canonical token. Validators independently confirm that the evidence supports or contradicts the event, and agree on the canonical classification.

### Separation of Storage and Non-Deterministic Blocks
GenVM runtime rules forbid accessing contract state inside `strict_eq` nondeterministic closures.
- **Rule**: Read all required contract state into local variables before calling `strict_eq`.
- **Implementation**: `CalibrationLedger` reads the prediction record (`event_text`, `status`) from `self.predictions[pid]` prior to entering `def evaluate()`. Inside `evaluate()`, only local immutable variables are referenced.

---

## 3. Storage Architecture & Nonce Disambiguator

The contract relies entirely on `TreeMap[str, str]` holding canonical JSON strings.

### Collections
1. `predictions`: Maps `prediction_id` (12 hex characters) to the prediction JSON object.
2. `by_forecaster`: Maps `forecaster_hex.lower()` to a JSON list of prediction IDs registered by that address.
3. `meta`: Stores global counters: `nonce`, `total_registered`, `total_resolved`.

### Disambiguator Mechanics
`prediction_id` is computed deterministically as:
$$\text{prediction\_id} = \text{sha256}(forecaster \parallel event\_text \parallel prob\_bp \parallel deadline\_hint \parallel nonce)[:12]$$

By incorporating the monotonic `nonce` sequence stored in `self.meta["nonce"]`:
- A forecaster can submit identical event text with the same probability across multiple rounds (e.g., quarterly recurring questions) without key collision.
- Each prediction ID is guaranteed unique, compact (12 hex digits), and deterministic.

---

## 4. Calibration Report & Dynamic Aggregation

`get_calibration_report(forecaster)` computes all statistics fresh upon inquiry:
- **No Stored Aggregate Drift**: Because reports are generated directly from the underlying `predictions` storage, there is zero risk of cache desynchronization.
- **Handling of AMBIGUOUS**: Ambiguous resolutions represent unresolved evidence or wash events; they increment `n_resolved` but are strictly excluded from Brier score and bucket hit rate calculations, preventing distortion.
- **Decile Bucketing**: Bins are grouped in 1000 bp (10%) intervals:
  - `0-10`, `10-20`, `20-30`, `30-40`, `40-50`, `50-60`, `60-70`, `70-80`, `80-90`, `90-100`.
  - For each bin, empirical count `n`, successful outcomes `hits`, and `hit_rate` are reported.
