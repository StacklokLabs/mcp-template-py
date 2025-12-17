"""Unit tests for MCPAuthMiddleware."""

from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_template_py.auth.auth_manager import AuthManager
from mcp_template_py.auth.mcp_auth_middleware import MCPAuthMiddleware
from mcp_template_py.auth.token_store import (
    AccessToken,
    ExternalTokens,
    InMemoryTokenStore,
)
from mcp_template_py.settings import Settings
from tests.fixtures import create_test_settings


@pytest.fixture
def test_app(
    mock_settings: Settings,
    token_store: InMemoryTokenStore,
    auth_manager: AuthManager,
) -> Starlette:
    """Create a test Starlette app with auth middleware."""

    async def protected_endpoint(request: Request) -> JSONResponse:
        """A protected endpoint that requires authentication."""
        # Try to get external tokens from context to verify they're set
        try:
            tokens = auth_manager.get_external_tokens()
            return JSONResponse(
                {"status": "ok", "external_access_token": tokens.access_token}
            )
        except ValueError as e:
            return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

    async def raise_error_endpoint(request: Request) -> JSONResponse:
        """An endpoint that raises an exception."""
        raise RuntimeError("Test exception")

    app = Starlette(
        routes=[
            Route("/protected", protected_endpoint),
            Route("/error", raise_error_endpoint),
        ],
        middleware=[
            Middleware(
                cast(Any, MCPAuthMiddleware),
                settings=mock_settings,
                token_store=token_store,
                auth_manager=auth_manager,
            ),
        ],
    )
    return app


@pytest.fixture
def test_client(test_app: Starlette) -> TestClient:
    """Create a test client for the app."""
    return TestClient(test_app, raise_server_exceptions=False)


@pytest.fixture
def oauth_disabled_settings() -> Settings:
    """Create settings with OAuth disabled."""
    return create_test_settings(enable_oauth=False)


@pytest.fixture
def oauth_disabled_app(
    oauth_disabled_settings: Settings,
    token_store: InMemoryTokenStore,
    auth_manager: AuthManager,
) -> Starlette:
    """Create a test app with OAuth disabled."""

    async def protected_endpoint(request: Request) -> JSONResponse:
        """A protected endpoint."""
        return JSONResponse({"status": "ok", "message": "No auth required"})

    # Create a new auth manager with disabled settings
    disabled_auth_manager = AuthManager(oauth_disabled_settings)

    app = Starlette(
        routes=[
            Route("/protected", protected_endpoint),
        ],
        middleware=[
            Middleware(
                cast(Any, MCPAuthMiddleware),
                settings=oauth_disabled_settings,
                token_store=token_store,
                auth_manager=disabled_auth_manager,
            ),
        ],
    )
    return app


@pytest.fixture
def oauth_disabled_client(oauth_disabled_app: Starlette) -> TestClient:
    """Create a test client for the OAuth-disabled app."""
    return TestClient(oauth_disabled_app, raise_server_exceptions=False)


class TestMCPAuthMiddleware:
    """Tests for the MCP authentication middleware."""

    def test_valid_bearer_token(
        self,
        test_client: TestClient,
        valid_access_token: tuple[str, AccessToken],
    ):
        """Test that a valid bearer token passes through."""
        token, _ = valid_access_token

        response = test_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["external_access_token"] == "external_access_token_123"

    def test_missing_authorization_header(self, test_client: TestClient):
        """Test that missing Authorization header returns 401."""
        response = test_client.get("/protected")

        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "unauthorized"
        assert "Bearer token required" in data["error_description"]
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_invalid_authorization_scheme(self, test_client: TestClient):
        """Test that non-Bearer scheme returns 401."""
        response = test_client.get(
            "/protected",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "unauthorized"
        assert "Bearer token required" in data["error_description"]

    def test_token_not_found(self, test_client: TestClient):
        """Test that unknown token returns 401."""
        response = test_client.get(
            "/protected",
            headers={"Authorization": "Bearer unknown_token_12345"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "unauthorized"
        assert "not found or revoked" in data["error_description"]

    def test_expired_token_returns_401(
        self,
        test_client: TestClient,
        expired_access_token: tuple[str, AccessToken],
    ):
        """Test that expired token returns 401."""
        token, _ = expired_access_token

        response = test_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "unauthorized"
        assert "expired" in data["error_description"].lower()

    def test_expired_token_cleanup(
        self,
        test_client: TestClient,
        token_store: InMemoryTokenStore,
        expired_access_token: tuple[str, AccessToken],
    ):
        """Test that expired token is removed from store."""
        token, _ = expired_access_token

        # Verify token exists before request
        assert token in token_store.access_tokens

        # Make request with expired token
        test_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify token was removed
        assert token not in token_store.access_tokens

    def test_external_tokens_context_set(
        self,
        test_client: TestClient,
        valid_access_token: tuple[str, AccessToken],
    ):
        """Test that external tokens are available in context during request."""
        token, access_token = valid_access_token

        response = test_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        # The endpoint tries to get external tokens and returns them
        assert (
            data["external_access_token"] == access_token.external_tokens.access_token
        )

    def test_context_reset_after_request(
        self,
        test_client: TestClient,
        auth_manager: AuthManager,
        valid_access_token: tuple[str, AccessToken],
    ):
        """Test that context is reset after request completes."""
        token, _ = valid_access_token

        # Make a successful request
        response = test_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        # After request, context should be cleared
        with pytest.raises(ValueError, match="Not authenticated with external"):
            auth_manager.get_external_tokens()

    def test_context_reset_on_exception(
        self,
        test_client: TestClient,
        auth_manager: AuthManager,
        valid_access_token: tuple[str, AccessToken],
    ):
        """Test that context is reset even if handler raises exception."""
        token, _ = valid_access_token

        # Make a request that will raise an exception
        response = test_client.get(
            "/error",
            headers={"Authorization": f"Bearer {token}"},
        )
        # The exception should be caught by Starlette
        assert response.status_code == 500

        # Context should still be cleared despite the exception
        with pytest.raises(ValueError, match="Not authenticated with external"):
            auth_manager.get_external_tokens()

    def test_oauth_disabled_bypasses_auth(
        self,
        oauth_disabled_client: TestClient,
    ):
        """Test that requests pass through when OAuth is disabled."""
        # No Authorization header needed
        response = oauth_disabled_client.get("/protected")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["message"] == "No auth required"


class TestTokenExpiration:
    """Tests for token expiration edge cases."""

    def test_token_about_to_expire(
        self,
        test_client: TestClient,
        token_store: InMemoryTokenStore,
        registered_client,
        sample_external_tokens: ExternalTokens,
    ):
        """Test token that is about to expire but still valid."""
        # Create a token that expires in 5 seconds (still valid)
        token = "mcp_template_py_boundary_test"
        access_token = AccessToken(
            external_tokens=sample_external_tokens,
            client_id=registered_client.client_id,
            scope="mcp:tools",
            refresh_token="refresh_boundary",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=5),
        )
        token_store.access_tokens[token] = access_token

        response = test_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Token should still work since it expires in 5 seconds
        assert response.status_code == 200

    def test_token_just_expired(
        self,
        test_client: TestClient,
        token_store: InMemoryTokenStore,
        registered_client,
        sample_external_tokens: ExternalTokens,
    ):
        """Test token that just expired (1 second ago)."""
        token = "mcp_template_py_just_expired"
        access_token = AccessToken(
            external_tokens=sample_external_tokens,
            client_id=registered_client.client_id,
            scope="mcp:tools",
            refresh_token="refresh_just_expired",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        token_store.access_tokens[token] = access_token

        response = test_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
