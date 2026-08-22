# Gmail OAuth для MARSEL ROAPP

Интеграция предоставляет только `gmail.readonly` и является частью единого MARSEL ROAPP.

## Runtime secrets

Обязательные переменные:

```text
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...
GMAIL_TOKEN_ENCRYPTION_KEY=<Fernet key>
GMAIL_ADMIN_USERNAME=...
GMAIL_ADMIN_PASSWORD=...
GMAIL_REDIRECT_URI=https://YOUR-DOMAIN/gmail/callback
```

Опционально:

```text
GMAIL_ALLOWED_ACCOUNT_EMAIL=atalanrafael@gmail.com
GMAIL_TOKEN_STORE_PATH=/var/lib/marsel/gmail_oauth.db
```

`GMAIL_CLIENT_SECRET`, `GMAIL_TOKEN_ENCRYPTION_KEY` и `GMAIL_ADMIN_PASSWORD` нельзя хранить в Git, issue, PR, логах или artifacts. Используйте секрет-хранилище окружения.

## Google Cloud

1. Включите Gmail API.
2. Создайте OAuth Client ID типа Web application.
3. Зарегистрируйте **точно тот же** HTTPS URI, который указан в `GMAIL_REDIRECT_URI`.
4. Запрашивайте только `https://www.googleapis.com/auth/gmail.readonly`.
5. Для production используйте HTTPS.

Redirect URI берётся только из runtime configuration, а не из HTTP `Host` заголовка. Это предотвращает подмену callback origin.

## Storage

OAuth state хранится в SQLite как SHA-256 hash, имеет TTL 10 минут и потребляется атомарно один раз. Gmail credentials хранятся только в зашифрованном виде Fernet. Каталог базы имеет `0700`, файл базы `0600`.

SQLite предназначен для одного хоста. Для нескольких контейнеров/хостов нужен общий транзакционный token/state store; локальный файл нельзя использовать как shared storage.

## Защита endpoints

Все `/gmail/*` endpoints требуют HTTP Basic credentials из `GMAIL_ADMIN_USERNAME`/`GMAIL_ADMIN_PASSWORD`. Отсутствие этих secrets блокирует доступ. Production должен использовать HTTPS.

Endpoints:

- `GET /gmail/connect` — начать OAuth.
- `GET /gmail/callback` — OAuth callback.
- `GET /gmail/status` — статус.
- `GET /gmail/messages?max_results=10` — read-only список ID сообщений.
- `POST /gmail/disconnect` — удалить локальные credentials.

## Production gates

Перед production необходимо подтвердить:

1. GitHub Actions PASS для текущего HEAD.
2. Live Google OAuth для разрешённого аккаунта.
3. Read-only Gmail API smoke test.
4. Secret/history scan.
5. Storage validation для фактической topology deployment.

Unit tests не заменяют live verification.

Production WRITE RO App этой интеграцией не включается.
