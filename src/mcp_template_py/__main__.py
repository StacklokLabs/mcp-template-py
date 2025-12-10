"""Entry point for the MCP server."""

import asyncio
import logging
import structlog

from mcp.server.fastmcp import FastMCP
from mcp_template_py.settings import Settings


def build_server(logger: structlog.BoundLogger) -> FastMCP:
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
        logger.info("hello tool called", name=name)
        return f"Hello, {name}!"

    return mcp


if __name__ == "__main__":
    # Configure logging
    settings = Settings()
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
    )

    # Build and run the MCP server
    logger = structlog.get_logger()
    logger.info("debug mode", debug=settings.debug)
    server = build_server(logger)
    asyncio.run(server.run_streamable_http_async())
