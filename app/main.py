from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .audit import audit_order_pages
from .config import settings
from .gmail_oauth import gmail_oauth
from .mcp_auth import JWTTokenVerifier
from .mcp_server import create_mcp_server
from .roapp_client import RoAppClient

mcp_http = None
if settings.mcp_http_enabled:
    missing = [
        name
        for name, value in (
            ("MCP_RESOURCE_SERVER_URL", settings.mcp_resource_server_url),
            ("MCP_AUTH_ISSUER", settings.mcp_auth_issuer),
            ("MCP_AUTH_JWKS_URL", settings.mcp_auth_jwks_url),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("MCP HTTP mode requires: " + ", ".join(missing))
    verifier = JWTTokenVerifier(jwks_url=settings.mcp_auth_jwks_url, issuer=settings.mcp_auth_issuer, audience=settings.mcp_resource_server_url)
    mcp_http = create_mcp_server(verifier)
    mcp_http.settings.streamable_http_path = "/"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if mcp_http is None:
        yield
        return
    async with mcp_http.session_manager.run():
        yield


app = FastAPI(title="MARSEL RO App Connector", version="0.4.0", lifespan=lifespan)
if mcp_http is not None:
    app.mount("/mcp", mcp_http.streamable_http_app())

gmail_basic = HTTPBasic(auto_error=False)


def require_gmail_admin(credentials: Annotated[HTTPBasicCredentials | None, Depends(gmail_basic)]) -> None:
    username = os.getenv("GMAIL_ADMIN_USERNAME", "")
    password = os.getenv("GMAIL_ADMIN_PASSWORD", "")
    if not username or not password or credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Gmail administration is not configured or authorized", headers={"WWW-Authenticate": "Basic"})
    if not (secrets.compare_digest(credentials.username, username) and secrets.compare_digest(credentials.password, password)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Gmail administrator credentials", headers={"WWW-Authenticate": "Basic"})


def gmail_redirect_uri() -> str:
    redirect_uri = os.getenv("GMAIL_REDIRECT_URI", "").strip()
    if not redirect_uri.startswith("https://"):
        raise HTTPException(status_code=503, detail="Gmail OAuth redirect URI is not configured for HTTPS")
    return redirect_uri


@app.get("/health")
def health():
    return {"status": "ok", "service": "marsel-roapp-connector", "version": "0.4.0"}


@app.get("/ready")
def ready():
    return {
        "status": "ready" if settings.roapp_api_key else "not_configured",
        "api_base_configured": bool(settings.roapp_base_url),
        "api_key_configured": bool(settings.roapp_api_key),
        "timeout_seconds": settings.roapp_timeout_seconds,
        "max_retries": settings.roapp_max_retries,
        "mcp_http_enabled": settings.mcp_http_enabled,
        "mcp_auth_configured": bool(settings.mcp_auth_issuer and settings.mcp_resource_server_url),
        "gmail_admin_configured": bool(os.getenv("GMAIL_ADMIN_USERNAME") and os.getenv("GMAIL_ADMIN_PASSWORD")),
        "gmail_redirect_configured": bool(os.getenv("GMAIL_REDIRECT_URI")),
    }


@app.get("/roapp/orders")
async def orders(page: int = Query(1, ge=1)):
    try:
        return await RoAppClient().get_orders(page)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="RO App API temporarily unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="RO App API request failed") from exc


@app.get("/roapp/audit/orders")
async def audit_orders(max_pages: int = Query(10, ge=1, le=100)):
    try:
        pages = await RoAppClient().get_orders_pages(max_pages)
        return audit_order_pages(pages)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="RO App API temporarily unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="RO App API audit failed") from exc


@app.get("/gmail/status", dependencies=[Depends(require_gmail_admin)])
def gmail_status():
    return gmail_oauth.status()


@app.get("/gmail/connect", dependencies=[Depends(require_gmail_admin)])
def gmail_connect():
    try:
        return RedirectResponse(gmail_oauth.authorization_url(gmail_redirect_uri()), status_code=302)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Gmail OAuth is not configured") from exc


@app.get("/gmail/callback", name="gmail_callback", dependencies=[Depends(require_gmail_admin)])
def gmail_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        raise HTTPException(status_code=400, detail="Google authorization was denied")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing OAuth callback parameters")
    try:
        return gmail_oauth.handle_callback(code, state)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Gmail OAuth exchange failed") from exc


@app.get("/gmail/messages", dependencies=[Depends(require_gmail_admin)])
def gmail_messages(max_results: int = Query(10, ge=1, le=100)):
    try:
        return {"status": "ok", "messages": gmail_oauth.list_messages(max_results)}
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail="Gmail is not connected") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Gmail API request failed") from exc


@app.post("/gmail/disconnect", dependencies=[Depends(require_gmail_admin)])
def gmail_disconnect():
    gmail_oauth.disconnect()
    return {"status": "disconnected", "email": gmail_oauth.account_email}
