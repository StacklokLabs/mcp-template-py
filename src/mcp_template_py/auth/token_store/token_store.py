from abc import ABC, abstractmethod

from mcp_template_py.auth.token_store.models import (
    AccessToken,
    AuthCode,
    PendingAuth,
    RegisteredClient,
)


class TokenStore(ABC):
    """
    Abstract base class for token storage.

    Production recommendations:
    - Redis: Fast, supports TTL for automatic expiration, good for sessions
    - PostgreSQL: Durable, supports complex queries, good for audit trails
    """

    @abstractmethod
    def store_pending_auth(self, pending_auth: PendingAuth, state: str) -> None:
        """Store a pending authorization keyed by state."""
        ...

    @abstractmethod
    def get_pending_auth(self, state: str) -> PendingAuth | None:
        """Retrieve a pending authorization by state."""
        ...

    @abstractmethod
    def pop_pending_auth(self, state: str) -> PendingAuth | None:
        """Retrieve and remove a pending authorization by state."""
        ...

    @abstractmethod
    def store_auth_code(self, auth_code: AuthCode, code: str) -> None:
        """Store an authorization code."""
        ...

    @abstractmethod
    def get_auth_code(self, code: str) -> AuthCode | None:
        """Retrieve an authorization code."""
        ...

    @abstractmethod
    def delete_auth_code(self, code: str) -> None:
        """Delete an authorization code."""
        ...

    @abstractmethod
    def store_access_token(self, access_token: AccessToken, token: str) -> None:
        """Store an access token."""
        ...

    @abstractmethod
    def get_access_token(self, token: str) -> AccessToken | None:
        """Retrieve an access token by token string."""
        ...

    @abstractmethod
    def revoke_access_token(self, token: str) -> None:
        """Revoke an access token."""
        ...

    @abstractmethod
    def get_access_token_by_refresh_token(
        self, refresh_token: str
    ) -> tuple[str, AccessToken] | None:
        """Find an access token by its refresh token. Returns (token, AccessToken) or None."""
        ...

    @abstractmethod
    def register_client(self, client: RegisteredClient) -> None:
        """Register a new OAuth client."""
        ...

    @abstractmethod
    def get_registered_client(self, client_id: str) -> RegisteredClient | None:
        """Retrieve a registered client by client ID."""
        ...

    @abstractmethod
    def list_registered_clients(self) -> list[RegisteredClient]:
        """List all registered clients."""
        ...

    @abstractmethod
    def revoke_registered_client(self, client_id: str) -> None:
        """Revoke a registered client."""
        ...
