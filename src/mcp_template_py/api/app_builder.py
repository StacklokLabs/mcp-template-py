import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import structlog
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Mount, Route

from mcp_template_py.api.mcp_builder import MCPBuilder
from mcp_template_py.api.oauth_api import OAuthApi
from mcp_template_py.auth.auth_manager import AuthManager
from mcp_template_py.auth.mcp_auth_middleware import MCPAuthMiddleware
from mcp_template_py.auth.token_store import InMemoryTokenStore
from mcp_template_py.settings import Settings


class AppBuilder:
    logger = structlog.get_logger()

    @staticmethod
    def build_app(settings: Settings | None = None) -> Starlette:
        # configure logging
        settings = settings or Settings()
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

        # build Starlette app with OAuth and MCP endpoints
        token_store = InMemoryTokenStore()
        auth_manager = AuthManager(settings)

        mcp = MCPBuilder.build_mcp(settings)
        mcp_http_app = mcp.streamable_http_app()

        # Lifespan to properly initialize the MCP session manager.
        # When mounting streamable_http_app() as a sub-app, Starlette doesn't
        # trigger its lifespan, so we must run the session manager explicitly.
        # See: https://github.com/modelcontextprotocol/python-sdk/issues/1467
        @asynccontextmanager
        async def lifespan(_app: Starlette) -> AsyncIterator[None]:
            async with mcp.session_manager.run():
                AppBuilder.logger.info("MCP session manager started")
                yield
            AppBuilder.logger.info("MCP session manager stopped")

        if settings.enable_oauth:
            AppBuilder.logger.info("Enabling OAuth endpoints")
            oauth = OAuthApi(token_store, auth_manager, settings)
            oauth_routes = [
                Route("/.well-known/oauth-authorization-server", oauth.oauth_metadata),
                Route("/oauth/register", oauth.register_client, methods=["POST"]),
                Route("/oauth/authorize", oauth.authorize, methods=["GET"]),
                Route("/oauth/callback", oauth.external_callback, methods=["GET"]),
                Route("/oauth/token", oauth.token_endpoint, methods=["POST"]),
            ]
            middleware = [
                Middleware(
                    cast(Any, MCPAuthMiddleware),
                    settings=settings,
                    token_store=token_store,
                    auth_manager=auth_manager,
                ),
            ]
        else:
            AppBuilder.logger.info("Disabling OAuth endpoints")
            oauth_routes = []
            middleware = []

        # Mount the MCP HTTP app at root - it already defines the /mcp route
        routes = oauth_routes + [Mount("/", app=mcp_http_app, middleware=middleware)]

        app = Starlette(
            routes=routes,
            lifespan=lifespan,
        )

        return app
