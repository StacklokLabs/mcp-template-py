"""Shared test fixtures for integration tests."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


@asynccontextmanager
async def get_mcp_client_session() -> AsyncIterator[ClientSession]:
    """Provide an initialized MCP client session for integration tests.

    Connects to the MCP server using the MCP_SERVER_URL environment variable,
    creates and initializes a client session, and yields it for use in tests.

    Example usage:
        async with get_mcp_client_session() as session:
            tools = await session.list_tools()
    """
    server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8100/mcp")

    async with streamablehttp_client(server_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
