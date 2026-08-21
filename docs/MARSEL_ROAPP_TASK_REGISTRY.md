# MARSEL ROAPP — ЕДИНЫЙ РЕЕСТР ЗАДАЧ

Дата контрольной точки: 2026-08-21

## Правило

MARSEL и ROAPP — один проект. Issue, PR, workflow, документация и код относятся к единому MARSEL ROAPP control plane.

Статус `DONE` допускается только при прямом evidence. Старые CI-запуски и исторические документы не закрывают текущие задачи.

## Реестр текущих контуров

| ID | Контур | Статус | Следующее действие |
|---|---|---|---|
| #19 | Production go-live | BLOCKED | backup → restore → reconciliation → dry-run → idempotency → rollback → post-write verification |
| #25 | Automation Health | REVIEW_REQUIRED | закрыть API completeness и свежий evidence |
| #27 | Gmail OAuth | REVIEW_REQUIRED | использовать актуальную реализацию и выполнить live read-only OAuth test |
| #30 | API/entity coverage | REVIEW_REQUIRED | подтвердить оставшиеся entities без угадывания ID |
| #31 | Control Protocol | CONSOLIDATED | правила перенесены в canonical control plane |
| #35 | Product-code collisions | REVIEW_REQUIRED | классифицировать 11 групп; не удалять автоматически |
| Warehouse | Warehouse API | NOT_VERIFIED | получить прямое доказательство официального GET-контракта |
| MCP | ChatGPT/Codex MCP | AUTH PENDING | пройти реальную authorization verification |
| Ads CAPI | OpenAI Ads | CODE CONSOLIDATED | production configuration требует внешних credentials/verification |
| PR #38 | Unified Gmail hardening | DRAFT / NOT MERGEABLE | пройти текущие CI, OAuth smoke test, secret/history scan и warehouse gate |
| PR #39 | RAFAEL AI OS runtime | DRAFT / NOT MERGEABLE | отдельная review/CI-проверка перед интеграцией в MARSEL control plane |

## Закрытые / superseded

- PR #28 — CLOSED, not merged; superseded Gmail implementation.
- PR #32 — закрыт как устаревшая/дублирующая Ads CAPI реализация.
- PR #36 — закрыт после переноса актуальной реализации в `main`.
- PR #37 — закрыт как superseded: canonical unified workflow уже находится в `main`.

## Production gate

`WRITE=0` является обязательным до полного прохождения safety gates. Наличие кода, документации, CI или PR не является доказательством production readiness.

## Архив

Исторические snapshots, старые control documents и заменённые changelog-файлы находятся в `старые данные/`. Архив не является текущим источником истины.

## Конечная цель

После прохождения технических gate система должна перейти от audit-only к управляемому ERP-контру MARSEL: клиенты → заказы → производство/ремонт → материалы → склад → себестоимость → оплаты → аналитика → автоматизация → повторные продажи.
