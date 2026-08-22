from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from .config import settings

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DEFAULT_ACCOUNT_EMAIL = "atalanrafael@gmail.com"
DEFAULT_STORE_PATH = "~/.local/share/marsel/gmail_oauth.db"
STATE_TTL_SECONDS = 600
MAX_MESSAGES = 100


class GmailTokenStore:
    """Encrypted-token/state store for workers on one host."""

    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or os.getenv("GMAIL_TOKEN_STORE_PATH", DEFAULT_STORE_PATH)).expanduser()
        self._prepare_storage_path()
        self._initialize()

    def _prepare_storage_path(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        os.chmod(self.path, 0o600)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS oauth_state (state_hash TEXT PRIMARY KEY, redirect_uri TEXT NOT NULL, created_at INTEGER NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS gmail_credentials (account_email TEXT PRIMARY KEY, encrypted_credentials BLOB NOT NULL, updated_at INTEGER NOT NULL)")
        os.chmod(self.path, 0o600)

    def save_state(self, state: str, redirect_uri: str) -> None:
        state_hash = hashlib.sha256(state.encode()).hexdigest()
        now = int(time.time())
        with self._connect() as connection:
            connection.execute("DELETE FROM oauth_state WHERE created_at < ?", (now - STATE_TTL_SECONDS,))
            connection.execute("INSERT INTO oauth_state(state_hash, redirect_uri, created_at) VALUES (?, ?, ?)", (state_hash, redirect_uri, now))

    def consume_state(self, state: str) -> str | None:
        state_hash = hashlib.sha256(state.encode()).hexdigest()
        now = int(time.time())
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM oauth_state WHERE created_at < ?", (now - STATE_TTL_SECONDS,))
            row = connection.execute("SELECT redirect_uri, created_at FROM oauth_state WHERE state_hash = ?", (state_hash,)).fetchone()
            if row is None:
                return None
            connection.execute("DELETE FROM oauth_state WHERE state_hash = ?", (state_hash,))
            return str(row[0]) if row[1] >= now - STATE_TTL_SECONDS else None

    def save_credentials(self, account_email: str, encrypted_credentials: bytes) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO gmail_credentials(account_email, encrypted_credentials, updated_at) VALUES (?, ?, ?) ON CONFLICT(account_email) DO UPDATE SET encrypted_credentials=excluded.encrypted_credentials, updated_at=excluded.updated_at", (account_email, encrypted_credentials, int(time.time())))

    def load_credentials(self, account_email: str) -> bytes | None:
        with self._connect() as connection:
            row = connection.execute("SELECT encrypted_credentials FROM gmail_credentials WHERE account_email = ?", (account_email,)).fetchone()
        return None if row is None else bytes(row[0])

    def delete_credentials(self, account_email: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM gmail_credentials WHERE account_email = ?", (account_email,))


@dataclass
class PendingOAuth:
    state: str
    redirect_uri: str


class GmailOAuthService:
    def __init__(self, store: GmailTokenStore | None = None) -> None:
        self._store = store or GmailTokenStore()

    @property
    def account_email(self) -> str:
        return os.getenv("GMAIL_ALLOWED_ACCOUNT_EMAIL", DEFAULT_ACCOUNT_EMAIL).strip().casefold()

    def _fernet(self) -> Fernet:
        key = os.getenv("GMAIL_TOKEN_ENCRYPTION_KEY", "")
        if not key:
            raise RuntimeError("Gmail token encryption key is not configured")
        try:
            return Fernet(key.encode())
        except (ValueError, TypeError) as exc:
            raise RuntimeError("Gmail token encryption key is invalid") from exc

    def _client_config(self) -> dict[str, Any]:
        client_id = os.getenv("GMAIL_CLIENT_ID", "")
        client_secret = os.getenv("GMAIL_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            raise RuntimeError("Gmail OAuth client is not configured")
        return {"web": {"client_id": client_id, "client_secret": client_secret, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": []}}

    @staticmethod
    def _validate_scopes(credentials: Credentials) -> None:
        scopes = set(credentials.scopes or ())
        if scopes and scopes != {GMAIL_READONLY_SCOPE}:
            raise PermissionError("Authorized Gmail scope is not permitted")

    def _configured_account(self) -> str:
        account = settings.gmail_account_email.strip().lower()
        if not account:
            raise RuntimeError("GMAIL_ACCOUNT_EMAIL не задан")
        return account

    def authorization_url(self, redirect_uri: str) -> str:
        flow = Flow.from_client_config(self._client_config(), scopes=[GMAIL_READONLY_SCOPE], redirect_uri=redirect_uri)
        url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent", state=secrets.token_urlsafe(32))
        self._store.save_state(state, redirect_uri)
        return url

    def handle_callback(self, code: str, state: str) -> dict[str, Any]:
        redirect_uri = self._store.consume_state(state)
        if redirect_uri is None:
            raise ValueError("Invalid or expired OAuth state")
        flow = Flow.from_client_config(self._client_config(), scopes=[GMAIL_READONLY_SCOPE], state=state, redirect_uri=redirect_uri)
        flow.fetch_token(code=code)
        credentials = flow.credentials
        self._validate_scopes(credentials)
        profile = self._gmail_service(credentials).users().getProfile(userId="me").execute()
        email = str(profile.get("emailAddress", "")).strip().casefold()
        if email != self.account_email:
            raise PermissionError("Authorized Google account is not permitted")
        self._store.save_credentials(self.account_email, self._fernet().encrypt(credentials.to_json().encode()))
        return {"status": "connected", "email": email, "scope": GMAIL_READONLY_SCOPE, "messages_total": profile.get("messagesTotal"), "threads_total": profile.get("threadsTotal")}

    def _load_credentials(self) -> Credentials | None:
        encrypted = self._store.load_credentials(self.account_email)
        if encrypted is None:
            return None
        try:
            raw = self._fernet().decrypt(encrypted).decode()
            credentials = Credentials.from_authorized_user_info(json.loads(raw), scopes=[GMAIL_READONLY_SCOPE])
            self._validate_scopes(credentials)
            return credentials
        except (InvalidToken, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Stored Gmail credentials are invalid or cannot be decrypted") from exc

    def _refresh_if_needed(self, credentials: Credentials) -> Credentials:
        if not credentials.expired or not credentials.refresh_token:
            return credentials
        credentials.refresh(Request())
        self._validate_scopes(credentials)
        self._store.save_credentials(self.account_email, self._fernet().encrypt(credentials.to_json().encode()))
        return credentials

    def status(self) -> dict[str, Any]:
        # Validate the encryption boundary even when no credentials exist.
        # This prevents a misconfigured runtime from being reported as healthy.
        self._fernet()
        credentials = self._load_credentials()
        if credentials is None:
            return {"status": "unauthorized", "email": self.account_email}
        try:
            self._refresh_if_needed(credentials)
        except RefreshError:
            return {"status": "token_refresh_failed", "email": self.account_email}
        return {"status": "connected", "email": self.account_email, "scope": GMAIL_READONLY_SCOPE}

    def list_messages(self, max_results: int = 10) -> list[dict[str, Any]]:
        if not 1 <= max_results <= MAX_MESSAGES:
            raise ValueError("max_results must be between 1 and 100")
        credentials = self._load_credentials()
        if credentials is None:
        self._credentials = credentials

        profile = self._gmail_service().users().getProfile(userId="me").execute()
        email = str(profile.get("emailAddress") or "").strip().lower()
        configured_account = self._configured_account()
        if email != configured_account:
            self._credentials = None
            raise PermissionError("Authorized Google account does not match configured Gmail account")

        return {
            "status": "connected",
            "email": email,
            "scope": GMAIL_READONLY_SCOPE,
            "messages_total": profile.get("messagesTotal"),
            "threads_total": profile.get("threadsTotal"),
        }

    def status(self) -> dict[str, Any]:
        account = self._configured_account()
        if self._credentials is None:
            return {"status": "unauthorized", "email": account}
        if self._credentials.expired and self._credentials.refresh_token:
            try:
                self._credentials.refresh(Request())
            except Exception:
                self._credentials = None
                return {"status": "token_expired", "email": account}
        return {"status": "connected", "email": account, "scope": GMAIL_READONLY_SCOPE}

    def list_messages(self, max_results: int = 10) -> list[dict[str, Any]]:
        if not 1 <= max_results <= 100:
            raise ValueError("max_results должен быть от 1 до 100")
        if self._credentials is None:
            raise PermissionError("Gmail is not connected")
        response = self._gmail_service(self._refresh_if_needed(credentials)).users().messages().list(userId="me", maxResults=max_results).execute()
        return response.get("messages", [])

    def disconnect(self) -> None:
        self._store.delete_credentials(self.account_email)

    @staticmethod
    def _gmail_service(credentials: Credentials):
        return build("gmail", "v1", credentials=credentials, cache_discovery=False)


gmail_oauth = GmailOAuthService()
