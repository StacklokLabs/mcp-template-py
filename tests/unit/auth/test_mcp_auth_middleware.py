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
        """Test that unknown internal token returns 401."""
        # Token must start with mcp- prefix to be treated as internal token
        response = test_client.get(
            "/protected",
            headers={"Authorization": "Bearer mcp-unknown_token_12345"},
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
        token = "mcp-boundary_test"
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
        token = "mcp-just_expired"
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


class TestTokenPassthrough:
    """Tests for token passthrough functionality (upstream external tokens)."""

    @pytest.fixture
    def passthrough_app(
        self,
        passthrough_settings: Settings,
        token_store: InMemoryTokenStore,
        auth_manager: AuthManager,
    ) -> Starlette:
        """Create a test app with passthrough enabled."""
        # Create a new auth manager with passthrough settings
        passthrough_auth_manager = AuthManager(passthrough_settings)

        async def protected_endpoint(request: Request) -> JSONResponse:
            """A protected endpoint that requires authentication."""
            try:
                tokens = passthrough_auth_manager.get_external_tokens()
                return JSONResponse(
                    {"status": "ok", "external_access_token": tokens.access_token}
                )
            except ValueError as e:
                return JSONResponse(
                    {"status": "error", "message": str(e)}, status_code=500
                )

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
                    settings=passthrough_settings,
                    token_store=token_store,
                    auth_manager=passthrough_auth_manager,
                ),
            ],
        )
        return app

    @pytest.fixture
    def passthrough_client(self, passthrough_app: Starlette) -> TestClient:
        """Create a test client for the passthrough app."""
        return TestClient(passthrough_app, raise_server_exceptions=False)

    @pytest.fixture
    def passthrough_auth_manager(self, passthrough_settings: Settings) -> AuthManager:
        """Create an AuthManager with passthrough settings."""
        return AuthManager(passthrough_settings)

    def test_passthrough_token_accepted(
        self,
        passthrough_client: TestClient,
    ):
        """Token without internal prefix passes through as external token."""
        raw_external_token = "ya29.some_external_access_token"

        response = passthrough_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {raw_external_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        # The passthrough wraps the token directly as ExternalTokens.access_token
        assert data["external_access_token"] == raw_external_token

    def test_passthrough_token_sets_correct_access_token(
        self,
        passthrough_client: TestClient,
    ):
        """The raw token becomes ExternalTokens.access_token in context."""
        external_token = "external_upstream_token_xyz"

        response = passthrough_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {external_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        # Verify the exact token value is passed through
        assert data["external_access_token"] == external_token

    def test_passthrough_context_reset_after_request(
        self,
        passthrough_settings: Settings,
        token_store: InMemoryTokenStore,
    ):
        """Context is cleared after passthrough request completes."""
        # Create a fresh auth manager to check context after request
        passthrough_auth_manager = AuthManager(passthrough_settings)

        async def protected_endpoint(request: Request) -> JSONResponse:
            tokens = passthrough_auth_manager.get_external_tokens()
            return JSONResponse({"external_access_token": tokens.access_token})

        app = Starlette(
            routes=[Route("/protected", protected_endpoint)],
            middleware=[
                Middleware(
                    cast(Any, MCPAuthMiddleware),
                    settings=passthrough_settings,
                    token_store=token_store,
                    auth_manager=passthrough_auth_manager,
                ),
            ],
        )
        test_client = TestClient(app, raise_server_exceptions=False)

        raw_token = "passthrough_token_for_reset_test"

        response = test_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        assert response.status_code == 200

        # After request, context should be cleared
        with pytest.raises(ValueError, match="Not authenticated with external"):
            passthrough_auth_manager.get_external_tokens()

    def test_passthrough_context_reset_on_exception(
        self,
        passthrough_settings: Settings,
        token_store: InMemoryTokenStore,
    ):
        """Context is cleared even if handler raises exception."""
        passthrough_auth_manager = AuthManager(passthrough_settings)

        async def raise_error_endpoint(request: Request) -> JSONResponse:
            raise RuntimeError("Test exception")

        app = Starlette(
            routes=[Route("/error", raise_error_endpoint)],
            middleware=[
                Middleware(
                    cast(Any, MCPAuthMiddleware),
                    settings=passthrough_settings,
                    token_store=token_store,
                    auth_manager=passthrough_auth_manager,
                ),
            ],
        )
        test_client = TestClient(app, raise_server_exceptions=False)

        raw_token = "passthrough_token_for_exception_test"

        response = test_client.get(
            "/error",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        # The exception should be caught by Starlette
        assert response.status_code == 500

        # Context should still be cleared despite the exception
        with pytest.raises(ValueError, match="Not authenticated with external"):
            passthrough_auth_manager.get_external_tokens()

    def test_passthrough_token_not_in_store(
        self,
        passthrough_client: TestClient,
        token_store: InMemoryTokenStore,
    ):
        """Passthrough tokens bypass the token store entirely."""
        external_token = "external_oauth_token_xyz"

        # Verify token is NOT in store
        assert token_store.get_access_token(external_token) is None

        response = passthrough_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {external_token}"},
        )

        # Should succeed despite not being in store
        assert response.status_code == 200

    def test_external_token_format_passthrough(
        self,
        passthrough_client: TestClient,
    ):
        """External token format (ya29.xxx) passes through."""
        external_token = "ya29.a0AfH6SMBx1234567890abcdefghijklmnopqrstuvwxyz"

        response = passthrough_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {external_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["external_access_token"] == external_token


class TestPrefixConfiguration:
    """Tests for token prefix configuration behavior."""

    def test_custom_prefix_distinguishes_internal_tokens(
        self,
        token_store: InMemoryTokenStore,
        registered_client,
        sample_external_tokens: ExternalTokens,
    ):
        """Tokens matching custom prefix use store lookup."""
        # Create settings with custom prefix
        custom_settings = create_test_settings(
            server_url="http://localhost:8100",
            minted_token_prefix="custom-prefix-",
            allow_token_passthrough=True,
        )
        custom_auth_manager = AuthManager(custom_settings)

        # Create token with custom prefix and store it
        token = "custom-prefix-test_token_123"
        access_token = AccessToken(
            external_tokens=sample_external_tokens,
            client_id=registered_client.client_id,
            scope="mcp:tools",
            refresh_token="refresh_custom",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        token_store.store_access_token(access_token, token)

        # Create app with custom settings
        async def protected_endpoint(request: Request) -> JSONResponse:
            tokens = custom_auth_manager.get_external_tokens()
            return JSONResponse({"external_access_token": tokens.access_token})

        app = Starlette(
            routes=[Route("/protected", protected_endpoint)],
            middleware=[
                Middleware(
                    cast(Any, MCPAuthMiddleware),
                    settings=custom_settings,
                    token_store=token_store,
                    auth_manager=custom_auth_manager,
                ),
            ],
        )
        test_client = TestClient(app, raise_server_exceptions=False)

        response = test_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        # Should return the stored ExternalTokens.access_token, not the minted token
        assert data["external_access_token"] == sample_external_tokens.access_token

    def test_token_exactly_matching_prefix(
        self,
        token_store: InMemoryTokenStore,
        mock_settings: Settings,
    ):
        """Token that exactly equals prefix (no suffix) is handled correctly."""
        auth_manager = AuthManager(mock_settings)

        # A token that is exactly "mcp-" with nothing after it
        token = "mcp-"

        # Create app
        async def protected_endpoint(request: Request) -> JSONResponse:
            tokens = auth_manager.get_external_tokens()
            return JSONResponse({"external_access_token": tokens.access_token})

        app = Starlette(
            routes=[Route("/protected", protected_endpoint)],
            middleware=[
                Middleware(
                    cast(Any, MCPAuthMiddleware),
                    settings=mock_settings,
                    token_store=token_store,
                    auth_manager=auth_manager,
                ),
            ],
        )
        test_client = TestClient(app, raise_server_exceptions=False)

        response = test_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Token starts with prefix, so it goes through store lookup
        # Since it's not in store, should return 401
        assert response.status_code == 401
        data = response.json()
        assert "not found or revoked" in data["error_description"]

    def test_passthrough_disabled_rejects_external_tokens(
        self,
        token_store: InMemoryTokenStore,
    ):
        """External tokens are rejected when passthrough is disabled."""
        # Create settings with passthrough disabled (the default)
        settings = create_test_settings(
            server_url="http://localhost:8100",
            allow_token_passthrough=False,
        )
        auth_manager = AuthManager(settings)

        # Create app
        async def protected_endpoint(request: Request) -> JSONResponse:
            tokens = auth_manager.get_external_tokens()
            return JSONResponse({"external_access_token": tokens.access_token})

        app = Starlette(
            routes=[Route("/protected", protected_endpoint)],
            middleware=[
                Middleware(
                    cast(Any, MCPAuthMiddleware),
                    settings=settings,
                    token_store=token_store,
                    auth_manager=auth_manager,
                ),
            ],
        )
        test_client = TestClient(app, raise_server_exceptions=False)

        # Try to use an external token (doesn't start with mcp- prefix)
        response = test_client.get(
            "/protected",
            headers={"Authorization": "Bearer ya29.external_oauth_token"},
        )

        # Should be rejected since passthrough is disabled
        assert response.status_code == 401
        data = response.json()
        assert "not found or revoked" in data["error_description"]
