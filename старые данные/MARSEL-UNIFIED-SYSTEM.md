# MARSEL Unified System

## Purpose
Единая точка управления проектом MARSEL/Ro App. Старые версии аудиторов и workflow считаются историческими до подтверждённой миграции.

## Control plane
Канонический workflow: `.github/workflows/marsel-unified-control-plane.yml`.

Канонический принцип: один orchestration layer, единые safety gates, единый evidence artifact, единый статус.

## Layers
1. **Control** — единый orchestration workflow и concurrency.
2. **Security** — secrets только через GitHub Secrets; минимум permissions; никакого WRITE в production на этапе аудита.
3. **API** — V20.31 strict READ-ONLY inventory как текущий канонический API inventory.
4. **Data quality** — integrity/data-quality checks подключаются только после проверки совместимости с control plane.
5. **Evidence** — каждый запуск публикует проверяемый JSON evidence artifact.
6. **Change control** — backup → restore → reconciliation → dry-run → idempotency → rollback → controlled write → post-write verification.

## Canonical status model
- `VERIFIED` — результат подтверждён независимой проверкой.
- `FIXED` — изменение внесено и перепроверено.
- `UNVERIFIED` — доказательств недостаточно.
- `BLOCKED` — требуется внешний доступ/действие.

## Migration policy
Не удалять старые workflow автоматически. Сначала классифицировать каждый workflow:
- CANONICAL — переносится под control plane;
- DUPLICATE — заменяется каноническим workflow;
- HISTORICAL — оставляется как история, но не используется для текущего контроля;
- REQUIRED — сохраняется с документированной ролью.

Удаление/отключение разрешено только после проверки последнего успешного запуска, зависимостей, secrets, artifacts и отсутствия уникальной функции.

## Safety
До отдельного разрешения production WRITE все API проверки должны оставаться READ-ONLY. Наличие POST/PUT/PATCH/DELETE в документации не означает их выполнение.

## Next controlled phases
1. Завершить инвентаризацию всех workflow и скриптов.
2. Сверить V20.31, V20.36, backup и entity inventory.
3. Объединить уникальные проверки в control plane.
4. Удалить только подтверждённые дубли.
5. Провести полный live READ-ONLY audit.
6. Backup/restore/reconciliation.
7. Только после всех gates — controlled WRITE.
