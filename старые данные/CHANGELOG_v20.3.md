# MARSEL RO App ERP — v20.3

Дата: 2026-08-04

## Цель релиза
Перевести текущую рабочую ветку проекта на контрольную версию v20.3 и автоматически прогнать существующий безопасный CI/read-only контроль.

## Контрольные требования
- Python tests (`pytest -q`)
- RO App API read-only smoke test
- MARSEL read-only orders audit
- MARSEL read-only order schema audit v2

## Безопасность
Релиз не добавляет операции `POST`, `PATCH` или `DELETE` в рабочую базу RO App. API-аудит использует только GET-запросы. API-ключ должен оставаться только в GitHub Secret `ROAPP_API_KEY` и не выводиться в логи.

## Критерий готовности
v20.3 считается технически подтверждённой только после успешного GitHub Actions run для commit релиза. Если API Secret отсутствует или RO App возвращает ошибку, релиз остаётся в состоянии `CI failed / deployment blocked` до устранения причины.
