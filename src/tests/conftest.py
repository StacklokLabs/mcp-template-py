"""Shared test fixtures for integration and unit tests."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@asynccontextmanager
async def get_mcp_client_session() -> AsyncIterator[ClientSession]:
    """Provide an initialized MCP client session for integration tests.

    This context manager:
    1. Connects to the MCP server using the MCP_SERVER_URL environment variable
    2. Creates and initializes a client session
    3. Yields the session for use in tests
    4. Cleans up the connection after the test

    Example usage:
        async with get_mcp_client_session() as session:
            tools = await session.list_tools()

    Yields:
        ClientSession: An initialized MCP client session
    """
    server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8100/mcp")

    # Connect to the MCP server using streamable HTTP client
    async with streamablehttp_client(server_url) as (read, write, _):
        # Create a client session
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()

            # Yield the session for use in tests
            yield session
