# On-Chain Verification and Integrity Proof

This document provides on-chain verification data for CalibrationLedger deployed on GenLayer studionet.

---

## 1. Deployment and Network Metadata

- **Network**: GenLayer Studionet
- **Chain ID**: 61999
- **RPC Endpoint**: `https://studio.genlayer.com/api`
- **Explorer Base URL**: `https://explorer-studio.genlayer.com`
- **Contract Address**: `0xAaD7A38119EeE71CAC50ddf112d4E12fBB00026a`
- **Contract Explorer URL**: `https://explorer-studio.genlayer.com/address/0xAaD7A38119EeE71CAC50ddf112d4E12fBB00026a`
- **Deploy Transaction Hash**: `0xc2209c807b1c89eef8381102143dc890c7bdeee6c8cd7608aba9f77a7c4f5429`
- **Deploy Status**: `ACCEPTED` (Result: `MAJORITY_AGREE`, Leader Receipt: `SUCCESS`)
- **Git Commit Hash**: `233dc0260416f69d826e9c5b12a0f63cf7ee5ab3`

---

## 2. Source Code Cryptographic Hash Verification

Per GenLayer studionet verification procedure, the local source code was verified against the data committed on-chain by fetching the deployment transaction via `eth_getTransactionByHash`, base64-decoding the `data.contract_code` payload, and comparing SHA-256 digests.

- **Local Contract File**: `contracts/CalibrationLedger.py`
- **Local Source SHA-256**: `53805eef041b364b16f302c4c46209e5e4467788ed6cb3fcd2d19c2718274e91`
- **On-Chain Decoded Source SHA-256**: `53805eef041b364b16f302c4c46209e5e4467788ed6cb3fcd2d19c2718274e91`
- **Exact Hash Match**: `true`

---

## 3. On-Chain Transaction Log and Execution Evidence

Ten real write transactions (5 registration, 5 resolution) were executed across two independent forecaster accounts on studionet.

| Case | Forecaster Address | Event Description | Prob (bp) | Register Tx Hash | Register Status | Resolve Tx Hash | Resolve Outcome | Leader Execution | Consensus Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Case 1** | `0xc65E820fb874748Bf169739844f545a3543D0c50` | Apple iPhone 16 announcement | 9000 (90%) | `0x04fab4490524f53c240a5930a02ce0e8a9ee8b11d9b34089ce49d0ecb6f06f6b` | `ACCEPTED` (11.29s) | `0x5242c5dd7a125a7f2b1e40b4bb0989dcb154e05df75ba334ebc9818f588f8386` | `YES` (`GROUNDED`) | `SUCCESS` | 21.45s |
| **Case 2 (Trap)** | `0xc65E820fb874748Bf169739844f545a3543D0c50` | SpaceX lunar Starship before Oct 2026 | 9900 (99%) | `0xd8c391f128f96b96b2feef6a99e7efab1e72a86265ef0708e4a5e1a48105408e` | `ACCEPTED` (6.33s) | `0x539e6be7cc1aac843f0f3013895f3004d9d0ce5fbd72c28305ee3d3153661b0c` | `NO` (`GROUNDED`) | `SUCCESS` | 16.59s |
| **Case 3** | `0xc65E820fb874748Bf169739844f545a3543D0c50` | Atmospheric CO2 below 400ppm | 1500 (15%) | `0xb6d673c674195f49d19a2e6022e96ecb968031b4723884147d210065d6d4e26e` | `ACCEPTED` (9.55s) | `0xce67aa1da7498e95155a9a1e21885b8e06c149ea4c2e50bdc527506e69742d6a` | `AMBIGUOUS` (`NONE`) | `SUCCESS` | 19.29s |
| **Case 4** | `0x5365D235deed7c291Bb21aA36938F783EFFB2D29` | Bitcoin below 10,000 USD in Q4 2026 | 1000 (10%) | `0x16d0cc9587240924ed770849ea674e2f025b71938c2632fae994c7e92f29a671` | `ACCEPTED` (6.19s) | `0xeee9e005228f5b8627b89c8702da28a7a7e2e8ac3283d4c8f84e78cc55f2b414` | `NO` (`GROUNDED`) | `SUCCESS` | 13.25s |
| **Case 5** | `0x5365D235deed7c291Bb21aA36938F783EFFB2D29` | Paris 2024 Olympic Games conclusion | 8500 (85%) | `0xb393255c9413a0fc52cf7c3166a6d68b12c6714693569567d03490abdf23ebce` | `ACCEPTED` (6.70s) | `0xf39ed5e587798118933489f94ba7d5b5a441781a15d390e3215d8635e9309b29` | `YES` (`GROUNDED`) | `SUCCESS` | 17.31s |

---

## 4. On-Chain Calibration Reports Read-Back

### Forecaster A (Overconfident Forecaster - The Trap Demonstration)
```json
{
  "schema_version": "1",
  "forecaster": "0xc65E820fb874748Bf169739844f545a3543D0c50",
  "n_registered": 3,
  "n_resolved": 3,
  "n_scored": 2,
  "brier_score": 0.49505,
  "buckets": [
    {
      "range": "90-100",
      "n": 2,
      "hits": 1,
      "hit_rate": 0.5
    }
  ]
}
```
**Trap Analysis**: Forecaster A scored 0.49505 because their 9900 bp prediction resolved NO, triggering a severe $(0.99 - 0.0)^2 = 0.9801$ quadratic penalty. Case 3 resolved AMBIGUOUS and was safely washed out from the Brier score.

### Forecaster B (Well-Calibrated Forecaster)
```json
{
  "schema_version": "1",
  "forecaster": "0x5365D235deed7c291Bb21aA36938F783EFFB2D29",
  "n_registered": 2,
  "n_resolved": 2,
  "n_scored": 2,
  "brier_score": 0.01625,
  "buckets": [
    {
      "range": "10-20",
      "n": 1,
      "hits": 0,
      "hit_rate": 0.0
    },
    {
      "range": "80-90",
      "n": 1,
      "hits": 1,
      "hit_rate": 1.0
    }
  ]
}
```
**Calibration Analysis**: Forecaster B scored 0.01625 (more than 30 times better than Forecaster A) by assigning appropriate probabilities: 1000 bp on an improbable event that did not occur ($(0.10 - 0.0)^2 = 0.0100$) and 8500 bp on a likely event that occurred ($(0.85 - 1.0)^2 = 0.0225$).
