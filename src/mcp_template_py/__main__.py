"""Entry point for the MCP server."""

import asyncio
import logging
import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP


def build_server() -> FastMCP:
    """Build and configure the MCP server.

    Creates a FastMCP instance with an example tool.

    Returns:
        Configured FastMCP server instance
    """
    mcp = FastMCP("agent-mcp", host="0.0.0.0", port=8100)

    @mcp.tool()
    async def hello(name: str) -> str:
        """Say hello to the user.

        Args:
            name: Name of the user
        Returns:
            Greeting message
        """
        return f"Hello, {name}!"

    return mcp


if __name__ == "__main__":
    # Load environment variables from .env file
    load_dotenv()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG
        if os.getenv("DEBUG", "").lower() in ("true", "1", "yes")
        else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Build and run the MCP server
    server = build_server()
    asyncio.run(server.run_streamable_http_async())
