# Runtime Notes (Milestone 0 Probe)

This document records the empirical behavior of the GenLayer studionet runtime as probed by the `Probe` contract deployment and write transaction.

## 1. Verified Header

The contract header must be verbatim:

```python
# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
```

All source files must contain strictly pure ASCII characters to prevent schema generation failures in Studio.

## 2. Probe Execution Findings

- **Probe Contract Address**: `0x90802806d41af106Baeb3858b0f42d710c523708`
- **Deploy Tx Hash**: `0xad1eebbadee7e71b693b5ac727cfe7c03357bafffae681080a95c0b348953bff`
- **Deploy Status**: `ACCEPTED` (Result: `MAJORITY_AGREE`)
- **Consensus Tx Hash**: `0x297daeab676757c998e90ed0acae6dfdb2875539f4fae33672b5378b9a7827b1`
- **Consensus Status**: `ACCEPTED` (Result: `MAJORITY_AGREE`, `leader_receipt[0].execution_result: SUCCESS`)
- **Measured Consensus Latency**: 23.63 seconds

### Sender Address Accessor
- Accessor: `gl.message.sender_address`
- String representation: both `gl.message.sender_address.as_hex` and `str(gl.message.sender_address)` yield the checksummed hex address string (e.g. `0xA12f5f77bC1596e27751D10BF809fbcfdc5B7828`).
- In contract storage and views, storing `gl.message.sender_address.as_hex` provides consistent casing.

### Cryptographic and Standard Libraries
- `import hashlib` succeeds inside contract methods.
- `hashlib.sha256(b"...").hexdigest()[:12]` executes without error.

### Error Handling Class
- `gl.vm.UserError` is the standard user-facing exception class recognized by the GenVM runtime for parameter validation and assertion failures.

### Equivalence Principle & Consensus
- `gl.eq_principle.strict_eq(fn)` executes the provided nondeterministic closure across independent validators and verifies string equality.
- Quorum is achieved when a majority of validators agree on the return string.

### LLM Prompt Execution (`gl.nondet.exec_prompt`)
- Calling `gl.nondet.exec_prompt(prompt, response_format="json")` returns a Python `dict` object on this runtime version.
- **Defensive parsing rule**: To guarantee resilience against potential model variations or runtime updates, contracts must defensively handle:
  1. Direct `dict` return (`obj.get(...)`)
  2. String return with JSON content (`json.loads(text)`)
  3. String wrapped in Markdown code fences (`re.sub(r"^```(?:json)?", "", text)`)
  4. Regex extraction fallback for key patterns (`re.search(...)`).
- Decisions must always be reduced to a tiny canonical string (e.g., `"YES|GROUNDED"`, `"NO|GROUNDED"`, `"AMBIGUOUS|NONE"`) before being returned to `gl.eq_principle.strict_eq`.
