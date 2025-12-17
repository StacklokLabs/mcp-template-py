from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp
import structlog

from mcp_template_py.auth.auth_manager import AuthManager
from mcp_template_py.auth.token_store import TokenStore
from mcp_template_py.settings import Settings


class MCPAuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for the MCP endpoint.

    This middleware is ONLY attached to the MCP Starlette app,
    so it never runs on OAuth routes. This is more efficient and explicit
    than checking the path in every request.

    Responsibilities:
    1. Extract Bearer token from Authorization header
    2. Validate token exists and is not expired
    3. Set external tokens in contextvars for tool access
    4. Return 401 to trigger OAuth flow if authentication fails
    """

    def __init__(
        self,
        app: ASGIApp,
        settings: Settings,
        token_store: TokenStore,
        auth_manager: AuthManager,
    ):
        self._settings = settings
        self._token_store = token_store
        self._auth_manager = auth_manager
        self._logger = structlog.get_logger(__name__)
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if not self._settings.enable_oauth:
            # OAuth is disabled - skip auth and proceed to next middleware
            self._logger.debug("OAuth disabled - skipping authentication")
            return await call_next(request)

        # Extract Bearer token from Authorization header
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return self._unauthorized_response("Bearer token required")

        token = auth_header[7:]  # Remove "Bearer " prefix
        token_data = self._token_store.get_access_token(token)

        # Check if token exists
        if not token_data:
            return self._unauthorized_response("Token not found or revoked")

        # Check if token is expired
        if datetime.now(timezone.utc) > token_data.expires_at:
            self._token_store.revoke_access_token(token)
            return self._unauthorized_response("Token expired")

        # Token is valid - set external tokens in context for tool access
        ctx_token = self._auth_manager.set_external_tokens(token_data.external_tokens)
        try:
            return await call_next(request)
        finally:
            # Always reset context to prevent leaks between requests
            self._auth_manager.reset_external_tokens(ctx_token)

    def _unauthorized_response(self, message: str) -> JSONResponse:
        """
        Return 401 Unauthorized response.

        The WWW-Authenticate header tells MCP clients to initiate OAuth flow.
        """
        return JSONResponse(
            status_code=401,
            content={
                "error": "unauthorized",
                "error_description": message,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
