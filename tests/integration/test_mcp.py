"""Integration tests for the MCP server with authentication.

These tests verify the MCP server works correctly with the OAuth authentication layer.

There are two types of tests:
1. HTTP-level tests using Starlette TestClient - These test auth rejection and basic HTTP behavior
2. MCP client tests using the official MCP Python library - These require a running server and
   test the full MCP protocol including SSE streaming

The MCP client tests are marked with `mcp_client` and require:
- MCP_SERVER_URL environment variable pointing to a running server
- A valid access token obtained through the OAuth flow
"""

import os
from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from mcp_template_py.auth.token_store import AccessToken, InMemoryTokenStore
from tests.fixtures import create_mcp_test_app, get_access_token
from tests.integration.conftest import get_mcp_client_session


@pytest.fixture
def mcp_test_app():
    """Create a full test application with mocked external OAuth."""
    return create_mcp_test_app()


@pytest.fixture
def test_client(mcp_test_app):
    """Create a test client for the MCP test app."""
    app, _, _ = mcp_test_app
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def token_store(mcp_test_app) -> InMemoryTokenStore:
    """Get the token store from the test app."""
    _, store, _ = mcp_test_app
    return store


class TestMCPAuthRejection:
    """Tests for MCP endpoint authentication rejection (uses TestClient for HTTP-level tests)."""

    def test_mcp_endpoint_requires_auth(self, test_client: TestClient):
        """Test that MCP endpoint returns 401 without authentication."""
        response = test_client.post("/mcp/")

        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_mcp_endpoint_rejects_invalid_token(self, test_client: TestClient):
        """Test that MCP endpoint rejects invalid tokens."""
        response = test_client.post(
            "/mcp/",
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401

    def test_expired_token_rejected(
        self, test_client: TestClient, token_store: InMemoryTokenStore
    ):
        """Test that expired tokens are rejected."""
        access_token = get_access_token(test_client)

        # Manually expire the token
        token_data = token_store.access_tokens[access_token]
        token_store.access_tokens[access_token] = AccessToken(
            external_tokens=token_data.external_tokens,
            client_id=token_data.client_id,
            scope=token_data.scope,
            refresh_token=token_data.refresh_token,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        # Try to use expired token
        response = test_client.post(
            "/mcp/",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 401
        assert "expired" in response.json()["error_description"].lower()


# Skip MCP client tests if no server URL is configured
mcp_client = pytest.mark.skipif(
    not os.getenv("MCP_SERVER_URL"),
    reason="MCP_SERVER_URL environment variable not set. "
    "Set it to run MCP client integration tests against a live server.",
)


@mcp_client
class TestMCPClientWithAuth:
    """Integration tests using the official MCP Python client library.

    These tests require a running MCP server and valid access token.
    Set MCP_SERVER_URL and MCP_ACCESS_TOKEN environment variables to run.

    Example:
        export MCP_SERVER_URL=http://localhost:8100/mcp
        export MCP_ACCESS_TOKEN=<your_token>
        pytest tests/integration/test_mcp.py -v -k "TestMCPClientWithAuth"
    """

    @pytest.fixture
    def access_token(self) -> str:
        """Get the access token from environment."""
        token = os.getenv("MCP_ACCESS_TOKEN")
        if not token:
            pytest.skip("MCP_ACCESS_TOKEN not set")
        return token  # type: ignore[return-value]

    @pytest.mark.asyncio
    async def test_mcp_client_connection_with_auth(self, access_token: str):
        """Test MCP client connection with valid authentication."""
        async with get_mcp_client_session(access_token) as session:
            # Session is already initialized by get_mcp_client_session
            # Verify by sending a ping - this only works if initialized
            result = await session.send_ping()
            assert result is not None

    @pytest.mark.asyncio
    async def test_mcp_client_list_tools(self, access_token: str):
        """Test listing MCP tools using the official client."""
        async with get_mcp_client_session(access_token) as session:
            tools_result = await session.list_tools()

            assert tools_result.tools is not None
            tool_names = [tool.name for tool in tools_result.tools]
            assert len(tool_names) > 0
            assert "hello" in tool_names, f"Expected 'hello' tool, found: {tool_names}"

    @pytest.mark.asyncio
    async def test_mcp_client_call_hello_tool(self, access_token: str):
        """Test calling the hello tool using the official client."""
        async with get_mcp_client_session(access_token) as session:
            result = await session.call_tool("hello", arguments={"name": "Alice"})

            assert result is not None
            assert len(result.content) > 0

            # Verify the response contains the expected greeting
            text_contents = [item for item in result.content if hasattr(item, "text")]
            assert any("Hello, Alice!" in item.text for item in text_contents), (
                f"Expected greeting not found in response: {[item.text for item in text_contents]}"
            )
