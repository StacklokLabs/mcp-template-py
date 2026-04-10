"""Integration tests for the MCP server.

These tests verify the MCP server works correctly using the official MCP Python client library.
They require a running server (MCP_SERVER_URL environment variable).
"""

import os

import pytest

from tests.integration.conftest import get_mcp_client_session


# Skip MCP client tests if no server URL is configured
mcp_client = pytest.mark.skipif(
    not os.getenv("MCP_SERVER_URL"),
    reason="MCP_SERVER_URL environment variable not set. "
    "Set it to run MCP client integration tests against a live server.",
)


@mcp_client
class TestMCPClient:
    """Integration tests using the official MCP Python client library.

    These tests require a running MCP server.
    Set MCP_SERVER_URL environment variable to run.

    Example:
        export MCP_SERVER_URL=http://localhost:8100/mcp
        pytest tests/integration/test_mcp.py -v
    """

    @pytest.mark.asyncio
    async def test_mcp_client_connection(self):
        """Test MCP client connection."""
        async with get_mcp_client_session() as session:
            result = await session.send_ping()
            assert result is not None

    @pytest.mark.asyncio
    async def test_mcp_client_list_tools(self):
        """Test listing MCP tools using the official client."""
        async with get_mcp_client_session() as session:
            tools_result = await session.list_tools()

            assert tools_result.tools is not None
            tool_names = [tool.name for tool in tools_result.tools]
            assert len(tool_names) > 0
            assert "hello" in tool_names, f"Expected 'hello' tool, found: {tool_names}"

    @pytest.mark.asyncio
    async def test_mcp_client_call_hello_tool(self):
        """Test calling the hello tool using the official client."""
        async with get_mcp_client_session() as session:
            result = await session.call_tool("hello", arguments={"name": "Alice"})

            assert result is not None
            assert len(result.content) > 0

            text_contents = [item for item in result.content if hasattr(item, "text")]
            assert any("Hello, Alice!" in item.text for item in text_contents), (
                f"Expected greeting not found in response: {[item.text for item in text_contents]}"
            )
