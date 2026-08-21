# MARSEL / ROAPP — ЕДИНАЯ КАНОНИЧЕСКАЯ СТРУКТУРА

Дата ревизии: 2026-08-21  
Ветка: `main`

## 1. Единая система

`MARSEL` и `ROAPP` — один продукт и один исходный контур: `atalanrafael-jpg/Ro-app`.

- MARSEL — бизнес-контур.
- ROAPP — технологический контур: API, данные, интеграции, автоматизация, MCP и CI/CD.
- `main` — каноническая ветка.
- Параллельные бизнес- и технические проекты не считаются отдельными источниками истины.

## 2. Единственная точка live-аудита RO App

`.github/workflows/marsel-unified-control-plane.yml`

Порядок:

1. API inventory — READ ONLY
2. Data quality — READ ONLY
3. Entity audit — READ ONLY
4. Product-code collision review — READ ONLY / advisory
5. Warehouse contract audit — READ ONLY
6. Unified safety/quality gate
7. Unified evidence artifact

Другие workflow не должны выполнять самостоятельный live-аудит RO App.

## 3. Канонические runtime-компоненты

- `scripts/marsel_api_inventory_v20_32.py` — текущая точка входа API inventory.
- `scripts/marsel_data_quality_v22_readonly.py` — data quality.
- `scripts/marsel_entity_audit_v20_35.py` — entity audit.
- `scripts/marsel_product_code_collision_audit_v22_1.py` — advisory collision review.
- `scripts/marsel_warehouse_contract_v20_36.py` — warehouse contract audit.
- `scripts/marsel_api_v2_probe_v1.py` — canonical read-only probe.
- `scripts/marsel_api_v2_canonical_registry_v1.py` — API evidence/registry support.
- `scripts/marsel_canonical_self_check.py` — structural self-check.

Старые versioned auditors сохраняются только как исторический материал и не подключаются к live Control Plane.

## 4. Единая прикладная структура

```text
Ro-app/
├── app/                 # application runtime
├── ai_service/          # AI service layer
├── config/              # configuration and fixtures
├── data/                # reference/catalog data
├── docs/                # canonical documentation and contracts
├── scripts/             # canonical + justified specialized checks
├── tests/               # tests
├── javascript/          # GPT integration
├── typescript/          # GPT integration
├── python/              # Python integration
├── .github/workflows/   # CI + Unified Control Plane
├── .agents/             # agent skills/contracts
├── старые данные/       # historical material; not active
└── requirements.txt     # Python dependencies
```

## 5. CI-разделение

- `marsel-unified-control-plane.yml` — единственный RO App live-audit workflow.
- `test.yml` — unit/compile/dependency validation; live RO App audit сюда не входит.
- `language-quality.yml` — языковые проверки.
- `generate-drafts.yml` — draft generation.
- `mcp-production.yml` — MCP-specific readiness checks.

## 6. Обязательные safety invariants

Канонический контур обязан подтверждать:

- `WRITE_REQUESTS_MADE=0`;
- `RO_APP_DATA_MUTATED=false`;
- `identifiers_guessed=false`;
- отсутствие POST/PUT/PATCH/DELETE в live-аудите;
- неполные live-данные = `REVIEW_REQUIRED`, никогда не `PASS`;
- старый успешный запуск не заменяет новый запуск на текущем `main`.

## 7. Правила архива

`старые данные/` предназначена только для исторических файлов, устаревших snapshots и заменённых реализаций.

Архивные материалы не являются источником текущего состояния и не должны подключаться в production workflow без отдельной миграции и повторной проверки.

Удаление исторических данных не производится, если их назначение нельзя подтвердить. В таком случае они остаются в архиве.

## 8. Критерий системной готовности

Проект не объявляется полностью готовым только на основании наличия кода или успешного CI.

Для production WRITE обязательны прямые evidence по:

`backup/export → restore integrity → schema reconciliation → full READ-ONLY inventory → duplicate/orphan/reference analysis → dry-run → idempotency → rollback → controlled write → post-write verification`.

До прохождения этих gate'ов production WRITE остаётся отключённым.
