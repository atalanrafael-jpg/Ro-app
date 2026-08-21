# MARSEL / Ro App — Active Script Registry

Дата контрольной ревизии: 2026-08-21
Ветка: `fix/unified-issues-19-25-27-30-31-35-42`

## 1. ACTIVE / CORE — фактически вызывается Unified Control Plane

| Роль | Файл | Статус |
|---|---|---|
| Structure self-check | `scripts/marsel_canonical_self_check.py` | ACTIVE |
| API inventory entrypoint | `scripts/marsel_api_inventory_v20_32.py` | ACTIVE |
| Data quality | `scripts/marsel_data_quality_v22_readonly.py` | ACTIVE |
| Entity audit | `scripts/marsel_entity_audit_v20_35.py` | ACTIVE |
| Product collision | `scripts/marsel_product_code_collision_audit_v22_1.py` — internal `22.3` | ACTIVE |
| Warehouse contract | `scripts/marsel_warehouse_contract_v20_45.py` — internal `20.49` | ACTIVE |

Источник истины для ACTIVE-набора: `.github/workflows/marsel-unified-control-plane.yml`.

## 2. REQUIRED INTERNAL DEPENDENCIES

- `scripts/marsel_api_inventory_v20_31.py` — импортируется из `marsel_api_inventory_v20_32.py`.
- `scripts/marsel_api_inventory_v20_29.py` — используется как базовый модуль из `marsel_api_inventory_v20_31.py`.

Эти зависимости не архивируются до завершения dependency audit.

## 3. SUPPORT

- `scripts/marsel_api_v2_canonical_registry_v1.py`
- `scripts/marsel_api_v2_probe_v1.py`
- `scripts/generate_drafts.py`

## 4. LEGACY / REVIEW CANDIDATES

Исторические варианты не архивируются автоматически по номеру версии. Перед переносом требуется dependency audit и проверка test discovery.

## 5. Текущие исправления

- Product collision audit обновлён до внутренней версии `22.3`: `REAL_COLLISION` и `UNRESOLVED` блокируют unified PASS; `LEGITIMATE_REUSE` не блокирует.
- Warehouse contract audit обновлён до внутренней версии `20.49`: PASS возможен только при успешном documented `GET /v2/warehouse/` с реальными warehouse IDs.
- `/v2/company/locations` больше не используется как источник branch IDs для warehouse PASS.
- Stock GET не заменяет Warehouse List GET.
- Недокументированные compatibility endpoints не используются для PASS.

## 6. Правила

1. Workflow является источником истины для ACTIVE execution set.
2. Import/dependency graph является источником истины для REQUIRED INTERNAL DEPENDENCIES.
3. Более новая версия не заменяет старую автоматически.
4. Архивирование выполняется только после dependency audit и проверки test discovery.
5. История Git/GitHub Actions сохраняется.
6. После любого изменения ACTIVE execution set или dependency chain требуется новый Unified Control Plane run.
7. Production WRITE запрещён до прохождения production safety gates из Issue #19.
