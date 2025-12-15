"""Integration tests for the MCP server."""

import pytest
from httpx import ConnectError
from mcp.shared.exceptions import McpError

from tests.integration.conftest import get_mcp_client_session


@pytest.mark.asyncio
async def test_mcp_server_connection() -> None:
    """Test basic connection to the deployed agent_mcp server.

    This test verifies that:
    1. The MCP server is accessible via HTTP
    2. A client session can be established
    3. The server responds to initialization

    This test will be skipped if the MCP server is not running.
    """
    try:
        async with get_mcp_client_session() as session:
            # Verify the session is initialized
            assert session is not None

            # List available tools to verify server functionality
            tools = await session.list_tools()
            assert tools is not None

            # Verify the hello tool exists
            tool_names = [tool.name for tool in tools.tools]
            assert "hello" in tool_names, f"Expected 'hello' tool, found: {tool_names}"
    except* (McpError, OSError, ConnectionError, ConnectError) as e:
        pytest.skip(f"MCP server is not available: {e}")


@pytest.mark.asyncio
async def test_mcp_server_hello_tool() -> None:
    """Test calling the hello tool on the deployed mcp_template_py server.

    This test verifies that:
    1. The hello tool can be called successfully
    2. The agent returns a valid response

    This test will be skipped if the MCP server is not running.
    """
    try:
        async with get_mcp_client_session() as session:
            # Call the hello tool with a simple query
            result = await session.call_tool("hello", arguments={"name": "Alice"})

            # Verify we got a response
            assert result is not None
            assert len(result.content) > 0

            # Verify the response contains text
            text_contents = [item for item in result.content if hasattr(item, "text")]
            assert any("Hello, Alice!" in item.text for item in text_contents), (
                f"Expected greeting not found in response: {[item.text for item in text_contents]}"
            )
    except* (McpError, OSError, ConnectionError, ConnectError) as e:
        pytest.skip(f"MCP server is not available: {e}")
