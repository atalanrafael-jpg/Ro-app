# RO App Warehouse Contract Registry

**Status:** REVIEW_REQUIRED  
**Mode:** READ-ONLY  
**Last verified:** 2026-08-21

## Canonical contract status

| Contract | Status | Evidence / rule |
|---|---|---|
| Warehouse list | `DOCUMENTED_LIVE_UNVERIFIED` | Official RO App v2 documentation defines `GET https://api.roapp.io/v2/warehouse/` with optional `branch_id` and `type` (`product` / `asset`). The audit now tests the documented query variants explicitly. Current live verification remains unresolved until at least one documented variant returns HTTP 200 with valid warehouse identifiers. |
| Warehouse stock | `DOCUMENTED_LIVE_UNVERIFIED` | Official documentation defines `GET https://api.roapp.io/warehouse/goods/{warehouse_id}`. Successful READ-ONLY verification is required for every warehouse discovered through the documented list contract. |
| Warehouse by ID / goods | `LIVE_VERIFIED_HISTORY` | Earlier CI evidence confirmed 11 warehouse-related live GET responses, but that evidence is not sufficient to establish completeness of the documented warehouse list. Current evidence must be regenerated against the canonical contract. |
| Undocumented compatibility endpoints | `DIAGNOSTIC_ONLY` | May be probed for investigation but can never produce `PASS` or replace the documented contract. |
| Warehouse WRITE | `DISABLED` | No write requests are permitted by the audit gate. |

## Official documentation

- Warehouse list: https://roappua.readme.io/reference/get-warehouses
- Warehouse stock: https://roappua.readme.io/reference/get-stock

The warehouse-list documentation defines `GET https://api.roapp.io/v2/warehouse/` and documents `branch_id` plus `type` (`product` / `asset`).

## Gate rule

`PASS` requires:

1. at least one documented warehouse-list variant to return HTTP 200 with valid JSON containing warehouse identifiers;
2. the documented warehouse-stock operation to return successful READ-ONLY responses for every warehouse discovered by that list operation;
3. repeatable CI evidence for both operations; and
4. `write_requests_made=0` and `ro_app_data_mutated=false`.

A guessed or undocumented endpoint must never be promoted to the canonical contract.

## Current blocker

The warehouse-list contract is **documented**, but it is **not currently live-verified** for MARSEL. Earlier testing returned HTTP 404 for the documented endpoint. The next audit explicitly tests the documented `type=product`, `type=asset`, and no-`type` variants (plus `branch_id` when configured) before any diagnostic fallback is considered.

This is materially different from saying that the endpoint is undocumented: the endpoint is documented, but the current live result does not yet match the documented contract.

## Required evidence to close the blocker

1. Successful read-only request to a documented warehouse-list variant.
2. Valid response containing warehouse identifiers.
3. Successful read-only stock requests for all discovered warehouse IDs.
4. Repeatable CI verification with evidence artifacts.

Until all conditions are satisfied, do not change the gate to `PASS` and do not enable production WRITE.
