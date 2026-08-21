from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
ACCOUNT_EMAIL = "atalanrafael@gmail.com"
DEFAULT_REDIRECT_URI = "http://localhost:8000/gmail/oauth/callback"

def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value

def _client_config() -> dict[str, Any]:
    return {"web": {"client_id": _required("GMAIL_CLIENT_ID"), "client_secret": _required("GMAIL_CLIENT_SECRET"), "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": [_redirect_uri()]}}

def _redirect_uri() -> str:
    return os.getenv("GMAIL_OAUTH_REDIRECT_URI", DEFAULT_REDIRECT_URI).strip()

def _state() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_required("GMAIL_OAUTH_STATE_SECRET"), salt="marsel-gmail-oauth")

def _fernet() -> Fernet:
    try:
        return Fernet(_required("GMAIL_TOKEN_ENCRYPTION_KEY").encode())
    except Exception as exc:
        raise RuntimeError("GMAIL_TOKEN_ENCRYPTION_KEY must be a valid Fernet key") from exc

def _token_path() -> Path:
    return Path(os.getenv("GMAIL_TOKEN_FILE", ".secrets/gmail-token.enc")).expanduser()

def _save(credentials: Credentials) -> None:
    path = _token_path(); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_fernet().encrypt(credentials.to_json().encode()))
    try: os.chmod(path, 0o600)
    except OSError: pass

def _load() -> Credentials | None:
    path = _token_path()
    if not path.exists(): return None
    try:
        raw = _fernet().decrypt(path.read_bytes())
        return Credentials.from_authorized_user_info(json.loads(raw.decode()), [GMAIL_READONLY_SCOPE])
    except (InvalidToken, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("Stored Gmail credentials are invalid") from exc

def authorization_url() -> str:
    flow = Flow.from_client_config(_client_config(), scopes=[GMAIL_READONLY_SCOPE], redirect_uri=_redirect_uri())
    state = _state().dumps({"nonce": secrets.token_urlsafe(24)})
    url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent", state=state)
    return url

def complete_callback(code: str, state: str) -> dict[str, Any]:
    try: _state().loads(state, max_age=600)
    except (BadSignature, SignatureExpired) as exc: raise RuntimeError("Invalid or expired OAuth state") from exc
    flow = Flow.from_client_config(_client_config(), scopes=[GMAIL_READONLY_SCOPE], state=state, redirect_uri=_redirect_uri())
    flow.fetch_token(code=code); credentials = flow.credentials
    if not set(credentials.scopes or []).issubset({GMAIL_READONLY_SCOPE}):
        raise RuntimeError("OAuth granted scopes exceed Gmail readonly scope")
    _save(credentials)
    return test_readonly_connection()

def test_readonly_connection() -> dict[str, Any]:
    credentials = _load()
    if credentials is None: return {"status": "unauthorized", "email": ACCOUNT_EMAIL}
    try:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request()); _save(credentials)
        if not credentials.valid: return {"status": "token_expired", "email": ACCOUNT_EMAIL}
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        profile = service.users().getProfile(userId="me").execute()
        email = str(profile.get("emailAddress", ""))
        if email.casefold() != ACCOUNT_EMAIL.casefold(): return {"status": "error", "reason": "account_mismatch"}
        return {"status": "connected", "email": email, "readonly": True, "scope": GMAIL_READONLY_SCOPE}
    except Exception as exc:
        if "invalid_grant" in str(exc).lower() or "revoked" in str(exc).lower(): return {"status": "unauthorized", "email": ACCOUNT_EMAIL}
        return {"status": "error", "email": ACCOUNT_EMAIL}

def status() -> dict[str, Any]:
    try: return test_readonly_connection()
    except RuntimeError: return {"status": "error", "email": ACCOUNT_EMAIL}

def disconnect() -> None:
    path = _token_path()
    if path.exists(): path.unlink()
