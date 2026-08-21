from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse

from .audit import audit_order_pages
from .config import settings
from .gmail_oauth import authorization_url, complete_callback, disconnect, status as gmail_status, test_readonly_connection
from .mcp_auth import JWTTokenVerifier
from .mcp_server import create_mcp_server
from .roapp_client import RoAppClient

mcp_http = None
if settings.mcp_http_enabled:
    missing = [name for name, value in (("MCP_RESOURCE_SERVER_URL", settings.mcp_resource_server_url), ("MCP_AUTH_ISSUER", settings.mcp_auth_issuer), ("MCP_AUTH_JWKS_URL", settings.mcp_auth_jwks_url)) if not value]
    if missing: raise RuntimeError("MCP HTTP mode requires: " + ", ".join(missing))
    verifier = JWTTokenVerifier(jwks_url=settings.mcp_auth_jwks_url, issuer=settings.mcp_auth_issuer, audience=settings.mcp_resource_server_url)
    mcp_http = create_mcp_server(verifier); mcp_http.settings.streamable_http_path = "/"

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if mcp_http is None:
        yield; return
    async with mcp_http.session_manager.run(): yield

app = FastAPI(title="MARSEL RO App Connector", version="0.5.0", lifespan=lifespan)
if mcp_http is not None: app.mount("/mcp", mcp_http.streamable_http_app())

@app.get("/health")
def health(): return {"status":"ok","service":"marsel-roapp-connector","version":"0.5.0"}

@app.get("/ready")
def ready():
    return {"status":"ready" if settings.roapp_api_key else "not_configured","api_base_configured":bool(settings.roapp_base_url),"api_key_configured":bool(settings.roapp_api_key),"timeout_seconds":settings.roapp_timeout_seconds,"max_retries":settings.roapp_max_retries,"mcp_http_enabled":settings.mcp_http_enabled,"mcp_auth_configured":bool(settings.mcp_auth_issuer and settings.mcp_resource_server_url),"gmail_oauth_configured":all(bool(__import__('os').getenv(x)) for x in ("GMAIL_CLIENT_ID","GMAIL_CLIENT_SECRET","GMAIL_OAUTH_STATE_SECRET","GMAIL_TOKEN_ENCRYPTION_KEY"))}

@app.get("/gmail/oauth/start")
def gmail_oauth_start():
    try: return RedirectResponse(authorization_url(), status_code=307)
    except RuntimeError as exc: raise HTTPException(status_code=503, detail="Gmail OAuth is not configured") from exc

@app.get("/gmail/oauth/callback")
def gmail_oauth_callback(code: str = Query(...), state: str = Query(...)):
    try: return complete_callback(code, state)
    except RuntimeError as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/gmail/status")
def gmail_connection_status(): return gmail_status()

@app.get("/gmail/test-readonly")
def gmail_test_readonly(): return test_readonly_connection()

@app.post("/gmail/disconnect")
def gmail_disconnect():
    disconnect(); return {"status":"unauthorized"}

@app.get("/roapp/orders")
async def orders(page: int = Query(1, ge=1)):
    try: return await RoAppClient().get_orders(page)
    except RuntimeError as exc: raise HTTPException(status_code=503, detail="RO App API temporarily unavailable") from exc
    except Exception as exc: raise HTTPException(status_code=502, detail="RO App API request failed") from exc

@app.get("/roapp/audit/orders")
async def audit_orders(max_pages: int = Query(10, ge=1, le=100)):
    try: return audit_order_pages(await RoAppClient().get_orders_pages(max_pages))
    except RuntimeError as exc: raise HTTPException(status_code=503, detail="RO App API temporarily unavailable") from exc
    except Exception as exc: raise HTTPException(status_code=502, detail="RO App API audit failed") from exc
