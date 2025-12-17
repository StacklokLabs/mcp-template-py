import base64
import contextvars
import hashlib
import secrets
from typing import Any

import httpx

from mcp_template_py.auth.token_store import ExternalTokens
from mcp_template_py.settings import Settings


class AuthManager:
    def __init__(self, settings: Settings | None = None):
        self.current_external_tokens: contextvars.ContextVar[ExternalTokens | None] = (
            contextvars.ContextVar("current_external_tokens", default=None)
        )
        self._settings = settings or Settings()

    def get_external_tokens(self) -> ExternalTokens:
        """
        Get external (e.g. Google) tokens from current request context.

        Call this from within MCP tools to access the authenticated user's
        external credentials.

        Returns:
            ExternalTokens containing 'access_token', 'refresh_token', etc.

        Raises:
            ValueError: If called outside of an authenticated request context
        """
        tokens = self.current_external_tokens.get()
        if not tokens:
            raise ValueError("Not authenticated with external credentials.")
        return tokens

    def set_external_tokens(
        self, tokens: ExternalTokens
    ) -> contextvars.Token[ExternalTokens | None]:
        """Set external tokens in the current request context."""
        return self.current_external_tokens.set(tokens)

    def reset_external_tokens(
        self, ctx_token: contextvars.Token[ExternalTokens | None]
    ):
        """Reset external tokens in the current request context."""
        self.current_external_tokens.reset(ctx_token)

    def generate_token(self) -> str:
        """Generate a cryptographically secure random token."""
        return secrets.token_urlsafe(32)

    def verify_pkce(self, code_verifier: str, code_challenge: str) -> bool:
        """
        Verify PKCE code_verifier matches the stored code_challenge.

        Uses S256 method as required by OAuth 2.1:
        BASE64URL(SHA256(code_verifier)) == code_challenge
        """
        digest = hashlib.sha256(code_verifier.encode()).digest()
        computed_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return computed_challenge == code_challenge

    async def exchange_external_code(self, code: str) -> dict[str, Any]:
        """Exchange external authorization code for access and refresh tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._settings.oauth_external_token_url,
                data={
                    "code": code,
                    "client_id": self._settings.oauth_client_id,
                    "client_secret": self._settings.oauth_client_secret,
                    "redirect_uri": self._settings.get_oauth_redirect_url(),
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            return response.json()

    async def refresh_external_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh an expired external access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._settings.oauth_external_token_url,
                data={
                    "refresh_token": refresh_token,
                    "client_id": self._settings.oauth_client_id,
                    "client_secret": self._settings.oauth_client_secret,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            return response.json()
