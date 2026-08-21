# MARSEL Gmail OAuth 2.0

## Scope
The integration is read-only and requests only `https://www.googleapis.com/auth/gmail.readonly`.

## Google Cloud setup
1. Create/select the Google Cloud project used for MARSEL.
2. Enable the Gmail API.
3. Configure the OAuth consent screen.
4. Create an OAuth 2.0 Web application client.
5. Add the exact `GMAIL_OAUTH_REDIRECT_URI` to the authorized redirect URIs.
6. Store the client ID and client secret only in the deployment secret store / GitHub Actions Secrets.

## Required secrets
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_OAUTH_STATE_SECRET`
- `GMAIL_TOKEN_ENCRYPTION_KEY`

Generate a Fernet key with Python's `cryptography` package. Never commit it.

## Flow
- `GET /gmail/oauth/start` creates a signed, short-lived state and redirects to Google.
- `GET /gmail/oauth/callback` verifies state, exchanges the authorization code, checks that only the readonly scope was granted, encrypts the credentials, and performs a Gmail read-only profile test.
- `GET /gmail/status` reports `connected`, `unauthorized`, `token_expired`, or `error` without exposing tokens.
- `GET /gmail/test-readonly` performs the same read-only connection check.
- `POST /gmail/disconnect` removes the encrypted local token.

## Security
OAuth state expires after 10 minutes. Credentials are encrypted at rest with Fernet and the token file is restricted to owner permissions where supported. No password, access token, refresh token, or client secret belongs in Git.

For multi-instance production deployment, set `GMAIL_TOKEN_FILE` to a protected persistent location or replace the file store with the deployment's encrypted secret/data store. The application never logs credential contents.

## Live acceptance test
A real acceptance test requires the user to authorize `atalanrafael@gmail.com` in Google's consent flow. GitHub cannot grant that authorization automatically. After authorization, `/gmail/test-readonly` must return `connected` and `readonly=true`.
