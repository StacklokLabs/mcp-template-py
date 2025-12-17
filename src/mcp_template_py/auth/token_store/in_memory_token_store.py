from mcp_template_py.auth.token_store.models import (
    AccessToken,
    AuthCode,
    PendingAuth,
    RegisteredClient,
)
from mcp_template_py.auth.token_store.token_store import TokenStore


class InMemoryTokenStore(TokenStore):
    """
    In-memory implementation of TokenStore.

    Suitable for development and testing. For production, consider using
    Redis or PostgreSQL-backed implementations.
    """

    def __init__(self) -> None:
        self.registered_clients: dict[str, RegisteredClient] = {}
        self.pending_auths: dict[str, PendingAuth] = {}
        self.auth_codes: dict[str, AuthCode] = {}
        self.access_tokens: dict[str, AccessToken] = {}

    def store_pending_auth(self, pending_auth: PendingAuth, state: str) -> None:
        """Store a pending authorization keyed by state."""
        self.pending_auths[state] = pending_auth

    def get_pending_auth(self, state: str) -> PendingAuth | None:
        """Retrieve a pending authorization by state."""
        return self.pending_auths.get(state)

    def pop_pending_auth(self, state: str) -> PendingAuth | None:
        """Retrieve and remove a pending authorization by state."""
        return self.pending_auths.pop(state, None)

    def store_auth_code(self, auth_code: AuthCode, code: str) -> None:
        """Store an authorization code."""
        self.auth_codes[code] = auth_code

    def get_auth_code(self, code: str) -> AuthCode | None:
        """Retrieve an authorization code."""
        return self.auth_codes.get(code)

    def delete_auth_code(self, code: str) -> None:
        """Delete an authorization code."""
        self.auth_codes.pop(code, None)

    def store_access_token(self, access_token: AccessToken, token: str) -> None:
        """Store an access token."""
        self.access_tokens[token] = access_token

    def get_access_token(self, token: str) -> AccessToken | None:
        """Retrieve an access token by token string."""
        return self.access_tokens.get(token)

    def revoke_access_token(self, token: str) -> None:
        """Revoke an access token."""
        self.access_tokens.pop(token, None)

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
