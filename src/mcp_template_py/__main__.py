"""Entry point for the MCP server."""

import asyncio
import logging
from mcp_template_py.configure_logging import configure_logging
import structlog

from mcp.server.fastmcp import FastMCP
from mcp_template_py.settings import Settings


def build_server(settings: Settings, logger: structlog.BoundLogger) -> FastMCP:
    """Build and configure the MCP server.

    Creates a FastMCP instance with an example tool.

    Returns:
        Configured FastMCP server instance
    """
    mcp = FastMCP("agent-mcp", host="0.0.0.0", port=settings.mcp_port)

    @mcp.tool()
    async def hello(name: str) -> str:
        """Say hello to the user.

        Args:
            name: Name of the user
        Returns:
            Greeting message
        """
        logger.info("hello tool called", name=name)
        return f"Hello, {name}!"

    return mcp


if __name__ == "__main__":
    # Configure logging
    settings = Settings()
    log_level = "DEBUG" if settings.debug else "INFO"
    configure_logging(log_level=log_level)

    # Build and run the MCP server
    logger = structlog.get_logger()
    logger.info("debug mode", debug=settings.debug)
    server = build_server(settings, logger)
    asyncio.run(server.run_streamable_http_async())
