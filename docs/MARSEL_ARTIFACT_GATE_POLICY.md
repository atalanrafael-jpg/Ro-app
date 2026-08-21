# MARSEL Artifact Gate Policy

## Purpose

Keep the Unified Control Plane evidence-driven and fail-closed. Artifact results must not be upgraded to PASS by inference or by an undocumented API assumption.

## Product-code classification

`duplicate_code_group_count` is informational only. It is not a blocking condition by itself.

The blocking result is derived from the collision classifier:

- `LEGITIMATE_REUSE` — non-blocking
- `REAL_COLLISION` — blocking
- `UNRESOLVED` — blocking

The Unified Control Plane MUST use the collision-classification artifact as the authoritative product-code gate.

## Warehouse contract

A warehouse endpoint MUST NOT be marked `documented_contract=true` unless the exact method/path is present in the currently verified RO App API documentation.

A live HTTP 200 is not sufficient to establish documentation status. A documentation URL that cannot be independently verified is not evidence.

Required states:

- `VERIFIED` — exact documented contract and successful live read
- `LIVE_UNDOCUMENTED` — live endpoint exists but documentation is not verified; MUST NOT PASS
- `CONTRACT_NOT_ESTABLISHED` — documented list contract cannot be verified; MUST NOT PASS
- `LIVE_FAILED` — documented contract exists but live request failed; MUST NOT PASS

`/v2/warehouse/` MUST NOT be treated as a documented warehouse-list contract merely because it was previously named in an internal evidence file.

## Evidence integrity

Every artifact must report:

- commit SHA
- generation timestamp
- read-only mode
- `write_requests_made`
- `ro_app_data_mutated`
- source script/version
- result and blocking reasons

Missing or stale evidence causes `REVIEW_REQUIRED`, never PASS.

## Production safety

No artifact gate may authorize production WRITE. Production WRITE remains disabled until the independent production gates are satisfied and explicit authorization exists.
