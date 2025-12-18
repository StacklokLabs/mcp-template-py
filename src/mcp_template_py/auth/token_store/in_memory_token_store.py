from cachetools import TTLCache

from mcp_template_py.auth.token_store.models import (
    AccessToken,
    AuthCode,
    PendingAuth,
    RegisteredClient,
)
from mcp_template_py.auth.token_store.token_store import TokenStore

# TTL constants matching the expiration logic in oauth_api.py
_PENDING_AUTH_TTL_SECONDS = 10 * 60  # 10 minutes
_AUTH_CODE_TTL_SECONDS = 10 * 60  # 10 minutes
_ACCESS_TOKEN_TTL_SECONDS = 60 * 60  # 1 hour

# Maximum number of entries per cache (prevents unbounded growth)
_MAX_CACHE_SIZE = 10000


class InMemoryTokenStore(TokenStore):
    """
    In-memory implementation of TokenStore using TTLCache for automatic expiration.

    Suitable for development and testing. For production, consider using
    Redis or PostgreSQL-backed implementations.
    """

    def __init__(self) -> None:
        # Registered clients don't expire
        self.registered_clients: dict[str, RegisteredClient] = {}
        # Use TTLCache for automatic expiration of temporary tokens
        self.pending_auths: TTLCache[str, PendingAuth] = TTLCache(
            maxsize=_MAX_CACHE_SIZE, ttl=_PENDING_AUTH_TTL_SECONDS
        )
        self.auth_codes: TTLCache[str, AuthCode] = TTLCache(
            maxsize=_MAX_CACHE_SIZE, ttl=_AUTH_CODE_TTL_SECONDS
        )
        self.access_tokens: TTLCache[str, AccessToken] = TTLCache(
            maxsize=_MAX_CACHE_SIZE, ttl=_ACCESS_TOKEN_TTL_SECONDS
        )

    def store_pending_auth(self, pending_auth: PendingAuth, state: str) -> None:
        """Store a pending authorization keyed by state."""
        self.pending_auths[state] = pending_auth

    def get_pending_auth(self, state: str) -> PendingAuth | None:
        """Retrieve a pending authorization by state."""
        try:
            return self.pending_auths[state]
        except KeyError:
            return None

    def pop_pending_auth(self, state: str) -> PendingAuth | None:
        """Retrieve and remove a pending authorization by state."""
        try:
            return self.pending_auths.pop(state)
        except KeyError:
            return None

    def store_auth_code(self, auth_code: AuthCode, code: str) -> None:
        """Store an authorization code."""
        self.auth_codes[code] = auth_code

    def get_auth_code(self, code: str) -> AuthCode | None:
        """Retrieve an authorization code."""
        try:
            return self.auth_codes[code]
        except KeyError:
            return None

    def delete_auth_code(self, code: str) -> None:
        """Delete an authorization code."""
        try:
            del self.auth_codes[code]
        except KeyError:
            pass

    def store_access_token(self, access_token: AccessToken, token: str) -> None:
        """Store an access token."""
        self.access_tokens[token] = access_token

    def get_access_token(self, token: str) -> AccessToken | None:
        """Retrieve an access token by token string."""
        try:
            return self.access_tokens[token]
        except KeyError:
            return None

    def revoke_access_token(self, token: str) -> None:
        """Revoke an access token."""
        try:
            del self.access_tokens[token]
        except KeyError:
            pass

    def get_access_token_by_refresh_token(
        self, refresh_token: str
    ) -> tuple[str, AccessToken] | None:
        """Find an access token by its refresh token. Returns (token, AccessToken) or None."""
        for token, data in self.access_tokens.items():
            if data.refresh_token == refresh_token:
                return (token, data)
        return None

    def register_client(self, client: RegisteredClient) -> None:
        """Register a new OAuth client."""
        self.registered_clients[client.client_id] = client

    def get_registered_client(self, client_id: str) -> RegisteredClient | None:
        """Retrieve a registered client by client ID."""
        return self.registered_clients.get(client_id)

    def list_registered_clients(self) -> list[RegisteredClient]:
        """List all registered clients."""
        return list(self.registered_clients.values())

    def revoke_registered_client(self, client_id: str) -> None:
        """Revoke a registered client."""
        self.registered_clients.pop(client_id, None)
