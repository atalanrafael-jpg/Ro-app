from concurrent.futures import ThreadPoolExecutor
import stat

import pytest
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials

import app.gmail_oauth as gmail_oauth_module
from app.gmail_oauth import (
    DEFAULT_ACCOUNT_EMAIL,
    GMAIL_READONLY_SCOPE,
    STATE_TTL_SECONDS,
    GmailOAuthService,
    GmailTokenStore,
)


def test_constants_are_read_only():
    assert DEFAULT_ACCOUNT_EMAIL == "atalanrafael@gmail.com"
    assert GMAIL_READONLY_SCOPE.endswith("gmail.readonly")


def test_state_is_persistent_and_single_use(tmp_path):
    store = GmailTokenStore(str(tmp_path / "oauth.db"))
    store.save_state("state-123", "https://example.com/gmail/callback")
    assert store.consume_state("state-123") == "https://example.com/gmail/callback"
    assert store.consume_state("state-123") is None


def test_state_is_single_use_under_concurrency(tmp_path):
    store = GmailTokenStore(str(tmp_path / "oauth.db"))
    store.save_state("concurrent-state", "https://example.com/gmail/callback")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: store.consume_state("concurrent-state"), range(2)))

    assert sorted(result is not None for result in results) == [False, True]


def test_expired_state_is_rejected_and_deleted(tmp_path, monkeypatch):
    store = GmailTokenStore(str(tmp_path / "oauth.db"))
    now = 1_000_000
    monkeypatch.setattr(gmail_oauth_module.time, "time", lambda: now)
    store.save_state("state-expired", "https://example.com/gmail/callback")
    monkeypatch.setattr(gmail_oauth_module.time, "time", lambda: now + STATE_TTL_SECONDS + 1)
    assert store.consume_state("state-expired") is None
    assert store.consume_state("state-expired") is None


def test_storage_permissions_are_owner_only(tmp_path):
    database = tmp_path / "secure" / "oauth.db"
    GmailTokenStore(str(database))
    assert stat.S_IMODE(database.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(database.stat().st_mode) == 0o600


def test_credentials_are_stored_as_ciphertext(tmp_path):
    store = GmailTokenStore(str(tmp_path / "oauth.db"))
    plaintext = b'{"refresh_token":"secret"}'
    encrypted = Fernet(Fernet.generate_key()).encrypt(plaintext)
    store.save_credentials(DEFAULT_ACCOUNT_EMAIL, encrypted)
    stored = store.load_credentials(DEFAULT_ACCOUNT_EMAIL)
    assert stored == encrypted
    assert plaintext not in stored


def test_missing_encryption_key_is_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv("GMAIL_TOKEN_ENCRYPTION_KEY", raising=False)
    service = GmailOAuthService(GmailTokenStore(str(tmp_path / "oauth.db")))
    with pytest.raises(RuntimeError, match="encryption key is not configured"):
        service.status()


def test_invalid_encryption_key_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GMAIL_TOKEN_ENCRYPTION_KEY", "not-a-fernet-key")
    service = GmailOAuthService(GmailTokenStore(str(tmp_path / "oauth.db")))
    with pytest.raises(RuntimeError, match="encryption key is invalid"):
        service.status()


def test_unauthorized_status_with_valid_runtime_key(tmp_path, monkeypatch):
    monkeypatch.setenv("GMAIL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    service = GmailOAuthService(GmailTokenStore(str(tmp_path / "oauth.db")))
    assert service.status() == {"status": "unauthorized", "email": DEFAULT_ACCOUNT_EMAIL}


def test_authorization_requires_client_configuration(tmp_path, monkeypatch):
    monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("GMAIL_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("GMAIL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    service = GmailOAuthService(GmailTokenStore(str(tmp_path / "oauth.db")))
    with pytest.raises(RuntimeError, match="not configured"):
        service.authorization_url("https://example.com/gmail/callback")


def test_invalid_callback_state_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GMAIL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    service = GmailOAuthService(GmailTokenStore(str(tmp_path / "oauth.db")))
    with pytest.raises(ValueError, match="Invalid or expired OAuth state"):
        service.handle_callback("code", "invalid-state")


def test_disallowed_scopes_are_rejected():
    credentials = Credentials(token="test-token", scopes=["https://www.googleapis.com/auth/gmail.modify"])
    with pytest.raises(PermissionError, match="scope is not permitted"):
        GmailOAuthService._validate_scopes(credentials)


def test_allowed_scope_is_accepted():
    credentials = Credentials(token="test-token", scopes=[GMAIL_READONLY_SCOPE])
    GmailOAuthService._validate_scopes(credentials)


def test_max_results_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv("GMAIL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    service = GmailOAuthService(GmailTokenStore(str(tmp_path / "oauth.db")))
    with pytest.raises(ValueError, match="between 1 and 100"):
        service.list_messages(101)
