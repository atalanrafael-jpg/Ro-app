# MARSEL × ROAPP — Master Roadmap

**Date:** 2026-08-21  
**Status:** canonical planning document  
**Production WRITE:** disabled

## Purpose

Develop ROAPP as the operational core of MARSEL, the jewelry and watch studio, with a single controlled model for customers, products, orders, production, repairs, inventory, pricing, finance, channels, automation, analytics and AI.

## Non-negotiable engineering rules

1. One canonical control plane.
2. One canonical source for each business entity.
3. READ-ONLY by default for live audits.
4. No production WRITE without explicit gate approval and evidence.
5. No guessed identifiers, endpoints, schemas or credentials.
6. Ambiguous data is `REVIEW_REQUIRED`, not silently repaired.
7. Historical material is archived, not silently deleted.
8. Every critical mutation must be auditable and reversible.
9. New automation must have measurable business value.
10. AI proposes before it acts on sensitive production operations.

## P0 — Reliability and control

- [ ] Resolve Warehouse Contract verification with the actual confirmed Ro App API contract.
- [ ] Obtain a fresh passing Unified Control Plane run.
- [ ] Complete API inventory and contract registry reconciliation.
- [ ] Complete entity/data-quality reconciliation with evidence.
- [ ] Validate backup and restore procedure.
- [ ] Validate rollback and idempotency controls.
- [ ] Confirm MCP production authorization separately from readiness tests.
- [ ] Verify secrets are never exposed in code, artifacts or logs.
- [ ] Keep production WRITE disabled until all mandatory gates pass.

## P1 — MARSEL operational core

### Master Data
- [ ] Define canonical Customer, Product, Material, Metal, Stone, Watch, Part, Service, Order, Repair, ProductionJob, Warehouse, Stock, StockMovement, Payment, Employee, Supplier, Channel and Document entities.
- [ ] Define immutable IDs and external-reference rules.
- [ ] Establish MARSEL Master Catalog ownership and governance.

### Orders and production
- [ ] Implement/verify order lifecycle from lead/quote through completion and after-sales.
- [ ] Model production jobs and material consumption.
- [ ] Track planned vs actual metal, stones, labor and total cost.
- [ ] Add QC and responsible-person checkpoints.

### Repair
- [ ] Create a dedicated jewelry/watch repair lifecycle.
- [ ] Capture intake condition, photos, diagnosis, estimate, approval, parts, labor, QC and warranty.

### Inventory
- [ ] Model on-hand, reserved, available, incoming, consumed, damaged, slow-moving and dead stock states where supported by the actual system contract.
- [ ] Add inventory valuation and reconciliation controls.

## P2 — Commercial growth

- [ ] Build/validate unified Master Catalog for studio, website and future channels.
- [ ] Introduce versioned pricing logic based on confirmed business rules.
- [ ] Add customer 360° and purchase/repair history.
- [ ] Add sales funnel, follow-up and repeat-purchase tracking.
- [ ] Add marketplace preflight before publication.
- [ ] Implement channel synchronization only after API contracts are verified.
- [ ] Add consent-aware customer communication workflows.

## P3 — Management intelligence

- [ ] Owner dashboard: revenue, margin, orders, repairs, overdue work and inventory exposure.
- [ ] Product/category margin analysis.
- [ ] Customer LTV, repeat rate and average order value.
- [ ] Inventory turnover, days of inventory and dead-stock value.
- [ ] Supplier performance metrics.
- [ ] Business Alert Engine for material exceptions rather than notification noise.
- [ ] MARSEL Data Health score with a documented calculation method.

## P4 — Automation

- [ ] Event model for OrderCreated, PaymentReceived, ProductionStarted, MaterialConsumed, RepairStarted, RepairCompleted, StockChanged and similar confirmed events.
- [ ] Workflow engine for assignments, overdue orders, ready-for-pickup, low-stock and integration failures.
- [ ] Unified integration layer for Ro App API, MCP, e-commerce, marketplaces and analytics.
- [ ] Observability: API health, latency, errors, sync lag and workflow failures.

## P5 — AI control plane

- [ ] AI Sales Assistant — read/analyze/recommend first.
- [ ] AI Operations Assistant — anomalies, overdue work and inventory analysis.
- [ ] AI Finance Analyst — margin, cost and profitability analysis.
- [ ] AI Inventory Analyst — stock and purchasing recommendations.
- [ ] AI Marketing Assistant — segmentation and campaign recommendations.
- [ ] Executive AI — owner-level summaries and next-best-action recommendations.
- [ ] Central permission layer for all AI agents.
- [ ] Human approval before sensitive production actions.
- [ ] Audit and post-action verification for every approved AI mutation.

## P6 — Resilience and governance

- [ ] Define and test RPO/RTO.
- [ ] Separate development, staging and production credentials/environments.
- [ ] Maintain immutable audit trail for critical operations.
- [ ] Maintain change/version/evidence registry.
- [ ] Periodically review archived material in `старые данные/` and move only genuinely superseded artifacts there.

## Definition of Done

A task is complete only when:

`implemented → tested → verified against the real contract → evidence captured → integrated into the canonical control plane → documented`.

A roadmap item is **not** considered production-ready merely because code or documentation exists.

## Priority rule

`P0 reliability → P1 operational core → P2 commercial growth → P3 management intelligence → P4 automation → P5 AI → P6 resilience/governance`.

No lower-priority feature should bypass an unresolved P0 safety or data-integrity blocker.
