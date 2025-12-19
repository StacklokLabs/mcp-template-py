"""Integration tests for the full OAuth flow.

These tests use a MockedOAuthApi that bypasses the actual external OAuth redirect,
allowing end-to-end testing of the OAuth flow without requiring real external credentials.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient

from mcp_template_py.auth.token_store import InMemoryTokenStore
from tests.fixtures import (
    complete_oauth_flow,
    create_mcp_test_app,
    generate_pkce_pair,
)


@pytest.fixture
def integration_test_app():
    """Create a full test application with mocked external OAuth."""
    return create_mcp_test_app()


@pytest.fixture
def test_client(integration_test_app) -> TestClient:
    """Create a test client for the integration test app."""
    app, _, _ = integration_test_app
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def token_store(integration_test_app) -> InMemoryTokenStore:
    """Get the token store from the integration test app."""
    _, store, _ = integration_test_app
    return store


class TestFullOAuthFlow:
    """Integration tests for the complete OAuth flow."""

    def test_complete_oauth_flow(
        self, test_client: TestClient, token_store: InMemoryTokenStore
    ):
        """Test the complete OAuth flow from registration to token."""
        # Step 1: Discover OAuth metadata
        response = test_client.get("/.well-known/oauth-authorization-server")
        assert response.status_code == 200
        metadata = response.json()
        assert "authorization_endpoint" in metadata
        assert "token_endpoint" in metadata
        assert "registration_endpoint" in metadata

        # Step 2: Dynamic client registration
        response = test_client.post(
            "/oauth/register",
            json={
                "client_name": "Test Client",
                "redirect_uris": ["http://localhost:9999/callback"],
            },
        )
        assert response.status_code == 201
        client_data = response.json()
        client_id = client_data["client_id"]
        assert client_id.startswith("client_")

        # Step 3: Generate PKCE pair
        code_verifier, code_challenge = generate_pkce_pair()

        # Step 4: Start authorization (redirects to external provider)
        response = test_client.get(
            "/oauth/authorize",
            params={
                "client_id": client_id,
                "redirect_uri": "http://localhost:9999/callback",
                "response_type": "code",
                "state": "client_csrf_state",
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            },
        )
        assert response.status_code == 307  # Redirect to external provider

        # Extract state from external redirect URL
        external_redirect = response.headers["location"]
        parsed = urlparse(external_redirect)
        external_params = parse_qs(parsed.query)
        external_state = external_params["state"][0]

        # Step 5: Simulate external callback (with our mocked handler)
        response = test_client.get(
            "/oauth/callback",
            params={"state": external_state, "code": "fake_external_code"},
        )
        assert response.status_code == 307  # Redirect to client

        # Extract authorization code from client redirect
        client_redirect = response.headers["location"]
        parsed = urlparse(client_redirect)
        callback_params = parse_qs(parsed.query)
        auth_code = callback_params["code"][0]
        returned_state = callback_params["state"][0]
        assert returned_state == "client_csrf_state"

        # Step 6: Exchange code for token
        response = test_client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": "http://localhost:9999/callback",
                "client_id": client_id,
                "code_verifier": code_verifier,
            },
        )
        assert response.status_code == 200
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["access_token"].startswith("mcp-")
        assert "refresh_token" in token_data
        assert token_data["token_type"] == "Bearer"
        assert token_data["expires_in"] == 3600

        # Verify token is stored
        assert token_data["access_token"] in token_store.access_tokens

    def test_refresh_token_flow(
        self, test_client: TestClient, token_store: InMemoryTokenStore, httpx_mock
    ):
        """Test token refresh after completing OAuth flow."""
        # Complete OAuth flow first
        _, access_token, refresh_token = complete_oauth_flow(test_client)

        # Verify initial token works
        assert access_token in token_store.access_tokens

        # Mock external token refresh (since it will try to refresh external tokens too)
        httpx_mock.add_response(
            url="https://oauth2.example.com/token",
            method="POST",
            json={
                "access_token": "ya29.refreshed_external_token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )

        # Refresh the token
        response = test_client.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        assert response.status_code == 200
        new_tokens = response.json()

        # Verify new tokens are different
        assert new_tokens["access_token"] != access_token
        assert new_tokens["refresh_token"] != refresh_token

        # Old token should be invalidated
        assert access_token not in token_store.access_tokens

        # New token should be valid
        assert new_tokens["access_token"] in token_store.access_tokens


class TestMCPEndpointWithAuth:
    """Tests for MCP endpoint authentication."""

    def test_mcp_endpoint_without_token(self, test_client: TestClient):
        """Test that MCP endpoint returns 401 without token."""
        response = test_client.post("/mcp/")

        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "unauthorized"
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_mcp_endpoint_with_invalid_token(self, test_client: TestClient):
        """Test that MCP endpoint returns 401 with invalid token."""
        response = test_client.post(
            "/mcp/",
            headers={"Authorization": "Bearer invalid_token_12345"},
        )

        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "unauthorized"

    def test_mcp_endpoint_with_valid_token(self, test_client: TestClient):
        """Test that MCP endpoint accepts valid token."""
        # Complete OAuth flow to get a valid token
        _, access_token, _ = complete_oauth_flow(test_client)

        # Make request to MCP endpoint with valid token
        # Note: The actual MCP endpoint behavior depends on the request body
        # We're just testing that auth passes through
        response = test_client.post(
            "/mcp/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
        )

        # Should not be 401 - auth succeeded
        assert response.status_code != 401

    def test_mcp_endpoint_with_expired_token(
        self, test_client: TestClient, token_store: InMemoryTokenStore
    ):
        """Test that MCP endpoint returns 401 with expired token."""
        # Complete OAuth flow to get a valid token
        _, access_token, _ = complete_oauth_flow(test_client)

        # Manually expire the token
        token_data = token_store.access_tokens[access_token]
        token_store.access_tokens[access_token] = token_data.__class__(
            external_tokens=token_data.external_tokens,
            client_id=token_data.client_id,
            scope=token_data.scope,
            refresh_token=token_data.refresh_token,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
        )

        # Make request with expired token
        response = test_client.post(
            "/mcp/",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "expired" in data["error_description"].lower()


class TestConcurrentOAuthFlows:
    """Tests for handling concurrent OAuth flows."""

    def test_concurrent_oauth_flows_dont_interfere(
        self, test_client: TestClient, token_store: InMemoryTokenStore
    ):
        """Test that multiple simultaneous OAuth flows don't interfere."""
        # Start two OAuth flows with different clients
        clients = []
        states = []

        for i in range(2):
            # Register client
            response = test_client.post(
                "/oauth/register",
                json={
                    "client_name": f"Concurrent Client {i}",
                    "redirect_uris": [f"http://localhost:{9000 + i}/callback"],
                },
            )
            client_id = response.json()["client_id"]
            clients.append(
                {
                    "id": client_id,
                    "redirect_uri": f"http://localhost:{9000 + i}/callback",
                    "pkce": generate_pkce_pair(),
                    "state": f"client_state_{i}",
                }
            )

        # Start authorization for both
        for client in clients:
            response = test_client.get(
                "/oauth/authorize",
                params={
                    "client_id": client["id"],
                    "redirect_uri": client["redirect_uri"],
                    "response_type": "code",
                    "state": client["state"],
                    "code_challenge": client["pkce"][1],
                    "code_challenge_method": "S256",
                },
            )
            external_state = parse_qs(urlparse(response.headers["location"]).query)[
                "state"
            ][0]
            states.append(external_state)

        # Complete both flows
        tokens = []
        for i, (client, external_state) in enumerate(zip(clients, states)):
            # External callback
            response = test_client.get(
                "/oauth/callback", params={"state": external_state, "code": f"code_{i}"}
            )
            auth_code = parse_qs(urlparse(response.headers["location"]).query)["code"][
                0
            ]

            # Verify correct state was returned
            returned_state = parse_qs(urlparse(response.headers["location"]).query)[
                "state"
            ][0]
            assert returned_state == client["state"]

            # Token exchange
            response = test_client.post(
                "/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": auth_code,
                    "redirect_uri": client["redirect_uri"],
                    "client_id": client["id"],
                    "code_verifier": client["pkce"][0],
                },
            )
            assert response.status_code == 200
            tokens.append(response.json()["access_token"])

        # All tokens should be unique and valid
        assert len(set(tokens)) == 2
        for token in tokens:
            assert token in token_store.access_tokens
