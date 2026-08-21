# MARSEL / ROAPP — CURRENT STATE — 2026-08-21

## Canonical system

- Repository: `atalanrafael-jpg/Ro-app`.
- `main` is the canonical production source branch.
- MARSEL and ROAPP are one system.
- `.github/workflows/marsel-unified-control-plane.yml` is the single live RO App audit control plane.

## Safety

- RO App production WRITE is disabled.
- Canonical live auditing is READ-ONLY.
- Parameterized identifiers are never guessed.
- Incomplete evidence must result in `REVIEW_REQUIRED`, never a false `PASS`.
- Historical snapshots do not override current evidence.

## Canonical audit components

- API inventory: `scripts/marsel_api_inventory_v20_32.py`.
- Data quality: `scripts/marsel_data_quality_v22_readonly.py`.
- Entity audit: `scripts/marsel_entity_audit_v20_35.py`.
- Product-code review: `scripts/marsel_product_code_collision_audit_v22_1.py`.
- Warehouse contract: `scripts/marsel_warehouse_contract_v20_36.py`.
- Structural self-check: `scripts/marsel_canonical_self_check.py`.

## Verified unresolved gates

The repository evidence reviewed on 2026-08-21 does not prove:

1. complete RO App entity/API coverage;
2. production backup plus successful restore test;
3. complete warehouse contract coverage;
4. live Gmail OAuth authorization and mailbox smoke test;
5. direct official RO App MCP authorization in the current ChatGPT environment;
6. final classification/reconciliation of the 11 product-code collision groups.

These are blockers to production WRITE, not reasons to guess or force a PASS.

## Archive

Superseded dated snapshots, old control documents and historical changelogs are stored in `старые данные/` and are not active configuration.
