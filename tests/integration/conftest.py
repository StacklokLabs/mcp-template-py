"""Shared test fixtures for integration tests.

This module provides fixtures for connecting to the MCP server for both
test client and live server integration tests.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@asynccontextmanager
async def get_mcp_client_session(
    access_token: str | None = None,
) -> AsyncIterator[ClientSession]:
    """Provide an initialized MCP client session for integration tests.

    This context manager:
    1. Connects to the MCP server using the MCP_SERVER_URL environment variable
    2. Creates and initializes a client session with optional auth
    3. Yields the session for use in tests
    4. Cleans up the connection after the test

    Args:
        access_token: Optional Bearer token for authentication. If not provided,
            will attempt to read from MCP_ACCESS_TOKEN environment variable.

    Example usage:
        async with get_mcp_client_session(token) as session:
            tools = await session.list_tools()

    Yields:
        ClientSession: An initialized MCP client session
    """
    server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8100/mcp")

    # Get token from parameter or environment
    token = access_token or os.getenv("MCP_ACCESS_TOKEN")

    # Build headers with auth if token is available
    headers: dict[str, str] | None = None
    if token:
        headers = {"Authorization": f"Bearer {token}"}

    # Connect to the MCP server using streamable HTTP client
    async with streamablehttp_client(server_url, headers=headers) as (
        read,
        write,
        _,
    ):
        # Create a client session
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()

            # Yield the session for use in tests
            yield session
