"""Shared test fixtures and utilities for all tests.

This module provides common fixtures, factory functions, and test utilities
used across unit and integration tests.
"""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urlparse

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Mount
from starlette.testclient import TestClient
from fastapi import APIRouter, FastAPI

from mcp_template_py.api import oauth_router as oauth_router_module
from mcp_template_py.api.mcp_builder import MCPBuilder
from mcp_template_py.auth.auth_manager import AuthManager
from mcp_template_py.auth.mcp_auth_middleware import MCPAuthMiddleware
from mcp_template_py.auth.token_store import (
    AccessToken,
    AuthCode,
    ExternalTokens,
    InMemoryTokenStore,
    PendingAuth,
    RegisteredClient,
    TokenStore,
)
from mcp_template_py.settings import Settings

# =============================================================================
# Factory Functions (non-pytest, reusable utilities)
# =============================================================================


def create_test_settings(
    server_url: str = "http://testserver",
    oauth_client_id: str = "test_oauth_client_id",
    oauth_client_secret: str = "test_oauth_client_secret",
    oauth_external_auth_url: str = "https://accounts.example.com/o/oauth2/v2/auth",
    oauth_external_token_url: str = "https://oauth2.example.com/token",
    enable_oauth: bool = True,
    allow_token_passthrough: bool = False,
    minted_token_prefix: str = "mcp-",
) -> Settings:
    """Create test settings with fake OAuth credentials."""
    return Settings(
        server_url=server_url,
        oauth_client_id=oauth_client_id,
        oauth_client_secret=oauth_client_secret,
        oauth_external_auth_url=oauth_external_auth_url,
        oauth_external_token_url=oauth_external_token_url,
        oauth_external_scopes="openid,email,profile",
        enable_oauth=enable_oauth,
        allow_token_passthrough=allow_token_passthrough,
        minted_token_prefix=minted_token_prefix,
        mcp_host="127.0.0.1",
        mcp_port=8100,
    )


def generate_pkce_pair() -> tuple[str, str]:
    """Generate a valid PKCE code_verifier and code_challenge pair."""
    code_verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


def create_external_tokens(
    access_token: str = "external_access_token_123",
    refresh_token: str = "external_refresh_token_456",
    scope: str = "openid email profile",
) -> ExternalTokens:
    """Create sample external tokens for testing."""
    return ExternalTokens(
        access_token=access_token,
        token_type="Bearer",
        expires_in=3600,
        refresh_token=refresh_token,
        scope=scope,
    )


def create_registered_client(
    token_store: TokenStore,
    client_id: str = "client_test123",
    client_name: str = "Test MCP Client",
    redirect_uris: list[str] | None = None,
) -> RegisteredClient:
    """Create and register a test client."""
    if redirect_uris is None:
        redirect_uris = ["http://localhost:8080/callback"]

    client = RegisteredClient(
        client_id=client_id,
        client_name=client_name,
        redirect_uris=redirect_uris,
        grant_types=["authorization_code"],
        response_types=["code"],
        created_at=datetime.now(timezone.utc),
    )
    token_store.register_client(client)
    return client


def create_pending_auth(
    token_store: TokenStore,
    client: RegisteredClient,
    code_challenge: str,
    state: str | None = None,
    expired: bool = False,
) -> tuple[str, PendingAuth]:
    """Create a pending auth state and return (state_key, pending_auth)."""
    if state is None:
        state = secrets.token_urlsafe(16)

    created_at = datetime.now(timezone.utc)
    if expired:
        created_at = created_at - timedelta(minutes=15)

    pending = PendingAuth(
        mcp_state="client_state_abc",
        code_challenge=code_challenge,
        client_id=client.client_id,
        redirect_uri=client.redirect_uris[0],
        scope="mcp:tools",
        created_at=created_at,
    )
    token_store.store_pending_auth(pending, state)
    return state, pending


def create_auth_code(
    token_store: TokenStore,
    client: RegisteredClient,
    external_tokens: ExternalTokens,
    code_challenge: str,
    code: str | None = None,
    expired: bool = False,
) -> tuple[str, AuthCode]:
    """Create an authorization code."""
    if code is None:
        code = secrets.token_urlsafe(32)

    created_at = datetime.now(timezone.utc)
    if expired:
        created_at = created_at - timedelta(minutes=15)

    auth_code = AuthCode(
        external_tokens=external_tokens,
        client_id=client.client_id,
        redirect_uri=client.redirect_uris[0],
        code_challenge=code_challenge,
        scope="mcp:tools",
        created_at=created_at,
    )
    token_store.store_auth_code(auth_code, code)
    return code, auth_code


def create_access_token(
    token_store: TokenStore,
    client: RegisteredClient,
    external_tokens: ExternalTokens,
    expired: bool = False,
) -> tuple[str, AccessToken]:
    """Create an access token."""
    token = f"mcp-{secrets.token_urlsafe(32)}"
    refresh_token = f"mcp-{secrets.token_urlsafe(32)}"

    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    if expired:
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

    access_token = AccessToken(
        external_tokens=external_tokens,
        client_id=client.client_id,
        scope="mcp:tools",
        refresh_token=refresh_token,
        expires_at=expires_at,
    )
    token_store.store_access_token(access_token, token)
    return token, access_token


# =============================================================================
# Mock External OAuth Response Data
# =============================================================================


def get_mock_external_token_response() -> dict[str, Any]:
    """Mock successful external token exchange response."""
    return {
        "access_token": "ya29.external_access_token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": "1//external_refresh_token",
        "scope": "openid email profile",
    }


def get_mock_external_refresh_response() -> dict[str, Any]:
    """Mock successful external token refresh response (no refresh_token returned)."""
    return {
        "access_token": "ya29.new_external_access_token",
        "token_type": "Bearer",
        "expires_in": 3600,
    }


# =============================================================================
# Mocked OAuth App for Integration Tests
# =============================================================================


def create_mocked_oauth_callback_endpoint(
    token_store: TokenStore, auth_manager: AuthManager
):
    """Create a mocked external_callback endpoint for integration testing.

    This function creates a FastAPI endpoint that simulates an external
    provider returning with an authorization code, bypassing the actual redirect
    to the external OAuth server.

    Args:
        token_store: TokenStore instance for accessing pending auth
        auth_manager: AuthManager instance for generating tokens

    Returns:
        Async endpoint function for mocked external callback
    """
    from typing import Annotated

    from fastapi import Query
    from fastapi.responses import JSONResponse, RedirectResponse

    async def mocked_external_callback(
        state: Annotated[str | None, Query()] = None,
        code: Annotated[str | None, Query()] = None,
        error: Annotated[str | None, Query()] = None,
        error_description: Annotated[str | None, Query()] = None,
    ) -> RedirectResponse | JSONResponse:
        """Mocked external callback that bypasses actual external OAuth."""
        # Handle errors the same way
        if error or not state:
            if error:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "external_auth_failed",
                        "error_description": error_description or error,
                    },
                )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_request",
                    "error_description": "state required",
                },
            )

        pending = token_store.pop_pending_auth(state)
        if not pending:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_state",
                    "error_description": "State not found or expired",
                },
            )

        if datetime.now(timezone.utc) - pending.created_at > timedelta(minutes=10):
            return JSONResponse(
                status_code=400,
                content={
                    "error": "expired",
                    "error_description": "Authorization request expired",
                },
            )

        # Create fake external tokens (no actual HTTP call)
        fake_external_tokens = ExternalTokens(
            access_token="ya29.test_external_access_token",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="1//test_external_refresh_token",
            scope="openid email profile",
        )

        # Generate our own authorization code
        mcp_code = auth_manager.generate_token()
        token_store.store_auth_code(
            AuthCode(
                external_tokens=fake_external_tokens,
                client_id=pending.client_id,
                redirect_uri=pending.redirect_uri,
                code_challenge=pending.code_challenge,
                scope=pending.scope,
                created_at=datetime.now(timezone.utc),
            ),
            code=mcp_code,
        )

        # Redirect back to MCP client with our authorization code
        redirect_params = {"code": mcp_code, "state": pending.mcp_state}
        return RedirectResponse(
            url=f"{pending.redirect_uri}?{urlencode(redirect_params)}"
        )

    return mocked_external_callback


def create_mocked_oauth_app(
    token_store: TokenStore,
    auth_manager: AuthManager,
    settings: Settings,
):
    """Create a FastAPI OAuth app with mocked external callback.

    This creates an OAuth FastAPI app but replaces the external_callback
    endpoint with a mocked version that doesn't make actual HTTP calls.

    Args:
        token_store: TokenStore instance
        auth_manager: AuthManager instance
        settings: Settings instance

    Returns:
        FastAPI app with mocked external callback
    """
    router = APIRouter(tags=["OAuth 2.0"])

    # Register all endpoints except external_callback from the original router
    for route in oauth_router_module.router.routes:
        if hasattr(route, "path") and route.path != "/oauth/callback":
            router.routes.append(route)

    # Add the mocked external_callback endpoint
    mocked_callback = create_mocked_oauth_callback_endpoint(token_store, auth_manager)
    router.add_api_route(
        "/oauth/callback",
        mocked_callback,
        methods=["GET"],
        response_model=None,
        summary="Mocked External OAuth Callback Handler",
    )

    # Create FastAPI app
    app = FastAPI(
        title="MCP OAuth Server (Test)",
        description="OAuth 2.0 authentication for MCP (with mocked callback)",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
    )

    # Store dependencies in app state for FastAPI's standard DI pattern
    app.state.token_store = token_store
    app.state.auth_manager = auth_manager
    app.state.settings = settings

    # Include the router
    app.include_router(router)

    return app


# =============================================================================
# Integration Test App Builders
# =============================================================================


def create_mcp_test_app(
    settings: Settings | None = None,
) -> tuple[Starlette, InMemoryTokenStore, AuthManager]:
    """Create a full test application with mocked external OAuth.

    Returns:
        Tuple of (app, token_store, auth_manager)
    """
    if settings is None:
        settings = create_test_settings()

    token_store = InMemoryTokenStore()
    auth_manager = AuthManager(settings)

    # Create mocked OAuth FastAPI app
    oauth_app = create_mocked_oauth_app(token_store, auth_manager, settings)

    # Create MCP app
    mcp = MCPBuilder.build_mcp(settings)
    mcp_http_app = mcp.streamable_http_app()

    mcp_app = Starlette(
        routes=[Mount("/", app=mcp_http_app)],
        middleware=[
            Middleware(
                cast(Any, MCPAuthMiddleware),
                settings=settings,
                token_store=token_store,
                auth_manager=auth_manager,
            ),
        ],
    )

    # Combine OAuth and MCP apps
    # We need to mount MCP first with a specific path, then OAuth routes
    # Because OAuth is mounted at "/" it would capture all routes if placed first
    app = Starlette(
        routes=[
            Mount("/mcp", app=mcp_app),  # Mount MCP app at /mcp
            Mount("/", app=oauth_app),  # Mount OAuth FastAPI app at root
        ],
    )

    return app, token_store, auth_manager


# =============================================================================
# OAuth Flow Helpers
# =============================================================================


def complete_oauth_flow(client: TestClient) -> tuple[str, str, str]:
    """Complete OAuth flow and return (client_id, access_token, refresh_token)."""
    # Register client
    response = client.post(
        "/oauth/register",
        json={
            "client_name": "Test Client",
            "redirect_uris": ["http://localhost:9999/callback"],
        },
    )
    client_id = response.json()["client_id"]

    # Generate PKCE
    code_verifier, code_challenge = generate_pkce_pair()

    # Authorize
    response = client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": "http://localhost:9999/callback",
            "response_type": "code",
            "state": "test_state",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        },
    )
    external_state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]

    # External callback (mocked)
    response = client.get(
        "/oauth/callback", params={"state": external_state, "code": "x"}
    )
    auth_code = parse_qs(urlparse(response.headers["location"]).query)["code"][0]

    # Token exchange
    response = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": "http://localhost:9999/callback",
            "client_id": client_id,
            "code_verifier": code_verifier,
        },
    )
    tokens = response.json()
    return client_id, tokens["access_token"], tokens["refresh_token"]


def get_access_token(client: TestClient) -> str:
    """Complete OAuth flow and return just the access token."""
    _, access_token, _ = complete_oauth_flow(client)
    return access_token
