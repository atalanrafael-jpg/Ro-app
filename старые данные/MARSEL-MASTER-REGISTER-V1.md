# MARSEL MASTER REGISTER V1

Дата контрольной точки: 2026-08-12

## Правила статусов

- **CONFIRMED** — подтверждено фактическим результатом, кодом, тестом или доступным артефактом.
- **DESIGNED** — архитектура/спецификация создана, но production-внедрение не подтверждено.
- **IN_PROGRESS** — работа запущена, финальный результат ещё не подтверждён.
- **BLOCKED** — невозможно безопасно завершить без внешнего условия.
- **NOT_IN_SCOPE** — сознательно исключено из текущего проекта.

## Критическое правило

Ни одна проектная спецификация не считается фактическим изменением рабочей базы RO App без подтверждённой write-операции и последующего reconciliation.

## MASTER-реестр

| Контур | Статус | Что подтверждено | Следующее действие |
|---|---|---|---|
| RO App API read-only | CONFIRMED | READ-only аудит и безопасный клиент существуют | Продолжать endpoint/data-quality аудит |
| Orders audit | CONFIRMED | Проверено 4 373 заказа; уникальные ID подтверждены предыдущими аудитами | Расширить аудит на связанные сущности |
| Master audit V20.20 | DESIGNED/READY | Скрипт V20.20 формирует snapshot, report и SHA256; write запрещён | Запустить и сохранить artifact |
| Full DB backup | BLOCKED | V20.20 прямо указывает, что это не полный backup БД | Получить подтверждённый механизм экспорта/backup и test-restore |
| Endpoint matrix | IN_PROGRESS | Созданы диагностические сценарии GET | Зафиксировать фактические endpoint/HTTP results |
| Data quality | IN_PROGRESS | Заказы проверены; полная БД не проверена | Проверить clients/products/services/warehouses/documents |
| Duplicate control | DESIGNED | Правила дублей определены | Сформировать read-only кандидатов дублей |
| Mobile phone policy | DESIGNED | Только категория «Мобильный» | Сопоставить с реальным полем Ro App перед записью |
| Repair workflow | DESIGNED | Диагностика → согласование → ремонт → QC → выдача → гарантия | Сопоставить с фактическими сущностями Ro App |
| Repair glasses | DESIGNED | Категория ремонта очков предусмотрена | Проверить фактический справочник услуг |
| Master Catalog | DESIGNED | Канонический MARSEL ID/SKU и assets определены | Наполнить только реальными записями |
| Online Try-On | DESIGNED | Preview/3D/temporary assets flow определён | Реализовывать только после выбора технического провайдера/API |
| Marketplace Preflight | DESIGNED | PASS/REVIEW/BLOCKED и проверки публикации определены | Проверить фактические API конкретных площадок |
| Marketplace stock sync | DESIGNED | Idempotency/reconciliation/conflict rules определены | Реализовывать после API verification |
| Marketplace orders | DESIGNED | External Order ID → MARSEL order mapping определён | Реализовывать после API verification |
| CRM | DESIGNED | Клиентская история и lifecycle определены | Сопоставить с Ro App |
| Financial control | DESIGNED | Revenue/cost/margin model определён | Подтвердить источники финансовых данных |
| Control Tower | DESIGNED | KPI/exception dashboard определён | Реализовать поверх подтверждённых данных |
| Document Master | DESIGNED | Единый ID/версия/связи определены | Сопоставить реальные документы |
| RBAC | DESIGNED | Роли и ограничения определены | Проверить реальные права API/account |
| Data Visibility Matrix | DESIGNED | INTERNAL/PARTNER/PUBLIC уровни определены | Применить только после проверки доступов |
| Quality management | DESIGNED | QC/rework/warranty controls определены | Добавить в рабочие статусы только после проверки схемы |
| Business continuity | DESIGNED | Backup/failover/manual fallback принципы определены | Провести restore/failure test |
| CI/CD | CONFIRMED | GitHub Actions и read-only audit scripts присутствуют | Проверять artifacts и фактические runs |
| Production writes | NOT_IN_SCOPE | Не разрешены текущим этапом | Только после backup + dry-run + approval |
| Государственные регистрации | NOT_IN_SCOPE | По прямому указанию пользователя исключены | Не анализировать/не изменять в рамках этого этапа |

## P0 — обязательные блокеры перед write

1. Подтвердить полный backup рабочей базы либо документировать безопасный экспорт, доступный через Ro App.
2. Выполнить test-restore/проверку целостности backup.
3. Завершить фактическую endpoint matrix.
4. Выполнить полный READ-only audit сущностей.
5. Сформировать кандидатов исправлений.
6. Выполнить dry-run.
7. Только после этого разрешать точечные write-операции.
8. После каждой серии изменений выполнять reconciliation.

## Что не считается выполненным

- наличие документа вместо фактической настройки Ro App;
- наличие API-клиента вместо подтверждённого endpoint результата;
- успешный CI job с пропущенным API шагом;
- создание Master Catalog без реальных записей;
- проектирование marketplace sync без проверки API площадки;
- проектирование online try-on без фактического провайдера/API;
- backup без проверенного восстановления.

## Источник истины

- **Master Product ID** — канонический идентификатор MARSEL.
- **Ro App** — источник фактических ERP-данных только в пределах подтверждённых сущностей/API.
- **Marketplace** — источник внешнего Order ID и внешнего статуса заказа.
- **Master Catalog** — каноническое представление товарной карточки для внешних каналов.
- **Государственные системы** — вне текущего scope по прямому указанию пользователя.

## Production safety

Текущий проектный режим: **READ-ONLY FIRST**.

Запрещено выполнять массовые POST/PATCH/PUT/DELETE до прохождения P0 и отдельной проверки конкретного endpoint.