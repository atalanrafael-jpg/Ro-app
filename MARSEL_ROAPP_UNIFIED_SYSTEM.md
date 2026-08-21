# MARSEL ROAPP — ЕДИНАЯ СИСТЕМА

Дата контрольной ревизии: 2026-08-21

MARSEL и ROAPP — единая система ювелирной студии, а не независимые проекты.

- MARSEL — бизнес-контур: клиенты, заказы, изделия, ремонт, производство, склад, материалы, финансы, продажи и маркетинг.
- ROAPP — технологический контур той же системы: API, данные, интеграции, автоматизация, MCP и CI/CD.
- `atalanrafael-jpg/Ro-app` — единый исходный контур.
- `main` — каноническая ветка.
- Единый источник истины запрещает параллельные MARSEL/ROAPP control planes и дублирующие live-аудиты.

## Canonical control plane

`.github/workflows/marsel-unified-control-plane.yml` — единственный live RO App audit workflow.

Он последовательно выполняет READ-ONLY:

`API inventory → data quality → entity audit → product-code review → warehouse contract → unified safety gate → evidence artifact`.

## Canonical implementations

- `scripts/marsel_api_inventory_v20_32.py`
- `scripts/marsel_data_quality_v22_readonly.py`
- `scripts/marsel_entity_audit_v20_35.py`
- `scripts/marsel_product_code_collision_audit_v22_1.py`
- `scripts/marsel_warehouse_contract_v20_36.py`
- `scripts/marsel_api_v2_probe_v1.py`
- `scripts/marsel_api_v2_canonical_registry_v1.py`
- `scripts/marsel_canonical_self_check.py`

Старые versioned реализации находятся в `старые данные/` и не являются активным control plane.

## Production safety

**Production WRITE remains disabled.** Production mutations remain disabled until direct evidence exists for:

`backup/export → restore integrity → schema reconciliation → READ-ONLY inventory → duplicate/orphan/reference analysis → dry-run → idempotency → rollback → controlled write → post-write verification`.

Наличие write-методов в документации или клиенте не означает, что они выполнялись.

## External verification gates

Следующие состояния нельзя объявлять выполненными без прямого evidence из фактической среды:

- Gmail OAuth live authorization;
- официальный RO App MCP authorization;
- production backup/restore;
- warehouse contract completeness;
- production data mutation/reconciliation.

## Current control rule

Каждая задача должна завершаться свежей проверкой. Старый успешный запуск не заменяет проверку текущего `main`.

`старые данные/` — только исторический архив; его содержимое не является текущим источником истины.
