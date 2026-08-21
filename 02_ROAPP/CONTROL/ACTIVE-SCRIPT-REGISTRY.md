# MARSEL / Ro App — Active Script Registry

Дата контрольной ревизии: 2026-08-21
Ветка: `main`

## 1. ACTIVE / CORE — фактически вызывается Unified Control Plane

| Роль | Файл | Статус |
|---|---|---|
| Structure self-check | `scripts/marsel_canonical_self_check.py` | ACTIVE |
| API inventory entrypoint | `scripts/marsel_api_inventory_v20_32.py` | ACTIVE |
| Data quality | `scripts/marsel_data_quality_v22_readonly.py` | ACTIVE |
| Entity audit | `scripts/marsel_entity_audit_v20_35.py` | ACTIVE |
| Product collision | `scripts/marsel_product_code_collision_audit_v22_1.py` | ACTIVE |
| Warehouse contract | `scripts/marsel_warehouse_contract_v20_45.py` | ACTIVE |

Источник истины для ACTIVE-набора: `.github/workflows/marsel-unified-control-plane.yml`.

## 2. REQUIRED INTERNAL DEPENDENCIES

Эти файлы не являются самостоятельными entrypoints Unified Control Plane, но обязательны для ACTIVE-кода:

- `scripts/marsel_api_inventory_v20_31.py` — импортируется напрямую из `marsel_api_inventory_v20_32.py`; содержит реализацию inventory.
- `scripts/marsel_api_inventory_v20_29.py` — используется как базовый модуль из `marsel_api_inventory_v20_31.py`.

Следовательно, `v20_29` и `v20_31` не являются кандидатами на архивирование до рефакторинга dependency chain.

## 3. SUPPORT

- `scripts/marsel_api_v2_canonical_registry_v1.py` — API registry/evidence support.
- `scripts/marsel_api_v2_probe_v1.py` — read-only API probe support.
- `scripts/generate_drafts.py` — draft-generation support; не относится к live Ro App audit.

## 4. LEGACY / REVIEW CANDIDATES

Следующие файлы требуют отдельного dependency audit; их нельзя архивировать только по номеру версии:

- `scripts/marsel_entity_audit_v20_32.py`
- `scripts/marsel_data_contract_v20_26.py`
- `scripts/marsel_coverage_audit_v20_25.py`
- другие исторические варианты, не входящие в ACTIVE entrypoint set и не подтверждённые как internal dependencies.

## 5. Исправленные расхождения

- CORE inventory entrypoint: `v20_32`.
- `v20_31` и `v20_29` ранее были ошибочно отмечены как legacy candidates; фактическая import chain делает их REQUIRED INTERNAL DEPENDENCIES.
- CORE collision: `marsel_product_code_collision_audit_v22_1.py`.
- CORE warehouse: `marsel_warehouse_contract_v20_45.py`; внутреннее поле версии обновлено до `20.48`.
- Официальный Warehouse List contract подтверждён документацией v2.0.1: `GET /v2/warehouse/`, `branch_id` optional, `type` optional с default `product`, allowed `product|asset`.
- `get-locations` больше не используется как источник branch IDs: доступная страница этого метода относится к v1.4 и документирует другой путь `/branches/`, поэтому использование `/v2/company/locations` удалено из warehouse audit.
- Warehouse List PASS теперь зависит именно от успешного документированного list GET с реально извлечёнными warehouse IDs; stock GET больше не может компенсировать провал list contract.
- Недокументированные compatibility endpoints не используются для PASS.
- Старый путь `scripts/marsel_warehouse_contract_v20_36.py` выведен из ACTIVE и сохранён в `старые данные/` как исторический след.

## 6. Правила

1. Workflow является источником истины для фактического ACTIVE execution set.
2. Import/dependency graph является источником истины для REQUIRED INTERNAL DEPENDENCIES.
3. Более новая версия не заменяет старую автоматически.
4. Архивирование = перенос только после dependency audit и проверки test discovery.
5. История Git/GitHub Actions сохраняется.
6. После любого изменения ACTIVE execution set или dependency chain требуется новый Unified Control Plane run.
7. Warehouse Contract PASS запрещён без успешного documented list GET и подтверждённых warehouse IDs.
