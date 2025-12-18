"""Unit tests for InMemoryTokenStore TTL-based expiration."""

from datetime import datetime, timezone

import pytest
from cachetools import TTLCache

from mcp_template_py.auth.token_store import (
    AccessToken,
    AuthCode,
    ExternalTokens,
    InMemoryTokenStore,
    PendingAuth,
    RegisteredClient,
)
from mcp_template_py.auth.token_store.in_memory_token_store import (
    _ACCESS_TOKEN_TTL_SECONDS,
    _AUTH_CODE_TTL_SECONDS,
    _MAX_CACHE_SIZE,
    _PENDING_AUTH_TTL_SECONDS,
)


class MockTimer:
    """A controllable timer for testing TTLCache expiration."""

    def __init__(self, start_time: float = 0.0):
        self._time = start_time

    def __call__(self) -> float:
        return self._time

    def advance(self, seconds: float) -> None:
        """Advance the timer by the specified number of seconds."""
        self._time += seconds


class InMemoryTokenStoreWithMockTimer(InMemoryTokenStore):
    """InMemoryTokenStore with controllable timers for testing TTL expiration."""

    def __init__(self, timer: MockTimer) -> None:
        # Don't call super().__init__() - we need to set up our own caches
        self.registered_clients: dict[str, RegisteredClient] = {}
        self.pending_auths: TTLCache[str, PendingAuth] = TTLCache(
            maxsize=_MAX_CACHE_SIZE, ttl=_PENDING_AUTH_TTL_SECONDS, timer=timer
        )
        self.auth_codes: TTLCache[str, AuthCode] = TTLCache(
            maxsize=_MAX_CACHE_SIZE, ttl=_AUTH_CODE_TTL_SECONDS, timer=timer
        )
        self.access_tokens: TTLCache[str, AccessToken] = TTLCache(
            maxsize=_MAX_CACHE_SIZE, ttl=_ACCESS_TOKEN_TTL_SECONDS, timer=timer
        )


@pytest.fixture
def token_store() -> InMemoryTokenStore:
    """Create a fresh InMemoryTokenStore instance."""
    return InMemoryTokenStore()


@pytest.fixture
def sample_external_tokens() -> ExternalTokens:
    """Create sample external tokens."""
    return ExternalTokens(
        access_token="ext_token",
        token_type="Bearer",
        expires_in=3600,
        refresh_token="ext_refresh",
    )


@pytest.fixture
def registered_client(token_store: InMemoryTokenStore) -> RegisteredClient:
    """Create and register a test client."""
    client = RegisteredClient(
        client_id="test_client",
        client_name="Test Client",
        redirect_uris=["http://localhost/callback"],
        grant_types=["authorization_code"],
        response_types=["code"],
        created_at=datetime.now(timezone.utc),
    )
    token_store.register_client(client)
    return client


class TestTTLCacheConfiguration:
    """Tests for TTLCache configuration."""

    def test_pending_auths_uses_ttl_cache(self, token_store: InMemoryTokenStore):
        """Pending auths storage uses TTLCache."""
        assert isinstance(token_store.pending_auths, TTLCache)

    def test_auth_codes_uses_ttl_cache(self, token_store: InMemoryTokenStore):
        """Auth codes storage uses TTLCache."""
        assert isinstance(token_store.auth_codes, TTLCache)

    def test_access_tokens_uses_ttl_cache(self, token_store: InMemoryTokenStore):
        """Access tokens storage uses TTLCache."""
        assert isinstance(token_store.access_tokens, TTLCache)

    def test_registered_clients_uses_regular_dict(
        self, token_store: InMemoryTokenStore
    ):
        """Registered clients use a regular dict (no expiration)."""
        assert isinstance(token_store.registered_clients, dict)
        assert not isinstance(token_store.registered_clients, TTLCache)

    def test_ttl_values_match_expected(self):
        """TTL values match the expected expiration times from oauth_api.py."""
        assert _PENDING_AUTH_TTL_SECONDS == 10 * 60  # 10 minutes
        assert _AUTH_CODE_TTL_SECONDS == 10 * 60  # 10 minutes
        assert _ACCESS_TOKEN_TTL_SECONDS == 60 * 60  # 1 hour


class TestAccessTokenExpiration:
    """Tests for access token TTL expiration."""

    def test_access_token_expires_after_ttl(
        self,
        sample_external_tokens: ExternalTokens,
    ):
        """Access token is not retrievable after TTL expires."""
        timer = MockTimer()
        store = InMemoryTokenStoreWithMockTimer(timer)

        client = RegisteredClient(
            client_id="test_client",
            client_name="Test Client",
            redirect_uris=["http://localhost/callback"],
            grant_types=["authorization_code"],
            response_types=["code"],
            created_at=datetime.now(timezone.utc),
        )
        store.register_client(client)

        token = AccessToken(
            external_tokens=sample_external_tokens,
            client_id=client.client_id,
            scope="mcp:tools",
            refresh_token="refresh",
            expires_at=datetime.now(timezone.utc),
        )
        store.store_access_token(token, "test_token")

        # Token should be retrievable immediately
        assert store.get_access_token("test_token") is not None

        # Advance time beyond TTL
        timer.advance(_ACCESS_TOKEN_TTL_SECONDS + 1)

        # Token should be expired and not retrievable
        assert store.get_access_token("test_token") is None

    def test_access_token_retrievable_within_ttl(
        self,
        token_store: InMemoryTokenStore,
        sample_external_tokens: ExternalTokens,
        registered_client: RegisteredClient,
    ):
        """Access token is retrievable within TTL window."""
        token = AccessToken(
            external_tokens=sample_external_tokens,
            client_id=registered_client.client_id,
            scope="mcp:tools",
            refresh_token="refresh",
            expires_at=datetime.now(timezone.utc),
        )
        token_store.store_access_token(token, "test_token")

        # Token should be retrievable immediately (within TTL)
        retrieved = token_store.get_access_token("test_token")
        assert retrieved is not None
        assert retrieved.client_id == registered_client.client_id


class TestAuthCodeExpiration:
    """Tests for authorization code TTL expiration."""

    def test_auth_code_expires_after_ttl(
        self,
        sample_external_tokens: ExternalTokens,
    ):
        """Auth code is not retrievable after TTL expires."""
        timer = MockTimer()
        store = InMemoryTokenStoreWithMockTimer(timer)

        client = RegisteredClient(
            client_id="test_client",
            client_name="Test Client",
            redirect_uris=["http://localhost/callback"],
            grant_types=["authorization_code"],
            response_types=["code"],
            created_at=datetime.now(timezone.utc),
        )
        store.register_client(client)

        code = AuthCode(
            external_tokens=sample_external_tokens,
            client_id=client.client_id,
            redirect_uri="http://localhost/callback",
            code_challenge="challenge",
            scope="mcp:tools",
            created_at=datetime.now(timezone.utc),
        )
        store.store_auth_code(code, "test_code")

        # Code should be retrievable immediately
        assert store.get_auth_code("test_code") is not None

        # Advance time beyond TTL
        timer.advance(_AUTH_CODE_TTL_SECONDS + 1)

        # Code should be expired
        assert store.get_auth_code("test_code") is None

    def test_auth_code_retrievable_within_ttl(
        self,
        token_store: InMemoryTokenStore,
        sample_external_tokens: ExternalTokens,
        registered_client: RegisteredClient,
    ):
        """Auth code is retrievable within TTL window."""
        code = AuthCode(
            external_tokens=sample_external_tokens,
            client_id=registered_client.client_id,
            redirect_uri="http://localhost/callback",
            code_challenge="challenge",
            scope="mcp:tools",
            created_at=datetime.now(timezone.utc),
        )
        token_store.store_auth_code(code, "test_code")

        retrieved = token_store.get_auth_code("test_code")
        assert retrieved is not None
        assert retrieved.client_id == registered_client.client_id


class TestPendingAuthExpiration:
    """Tests for pending authorization TTL expiration."""

    def test_pending_auth_expires_after_ttl(self):
        """Pending auth is not retrievable after TTL expires."""
        timer = MockTimer()
        store = InMemoryTokenStoreWithMockTimer(timer)

        client = RegisteredClient(
            client_id="test_client",
            client_name="Test Client",
            redirect_uris=["http://localhost/callback"],
            grant_types=["authorization_code"],
            response_types=["code"],
            created_at=datetime.now(timezone.utc),
        )
        store.register_client(client)

        pending = PendingAuth(
            mcp_state="state",
            code_challenge="challenge",
            client_id=client.client_id,
            redirect_uri="http://localhost/callback",
            scope="mcp:tools",
            created_at=datetime.now(timezone.utc),
        )
        store.store_pending_auth(pending, "test_state")

        # Pending auth should be retrievable immediately
        assert store.get_pending_auth("test_state") is not None

        # Advance time beyond TTL
        timer.advance(_PENDING_AUTH_TTL_SECONDS + 1)

        # Pending auth should be expired
        assert store.get_pending_auth("test_state") is None

    def test_pending_auth_retrievable_within_ttl(
        self,
        token_store: InMemoryTokenStore,
        registered_client: RegisteredClient,
    ):
        """Pending auth is retrievable within TTL window."""
        pending = PendingAuth(
            mcp_state="state",
            code_challenge="challenge",
            client_id=registered_client.client_id,
            redirect_uri="http://localhost/callback",
            scope="mcp:tools",
            created_at=datetime.now(timezone.utc),
        )
        token_store.store_pending_auth(pending, "test_state")

        retrieved = token_store.get_pending_auth("test_state")
        assert retrieved is not None
        assert retrieved.client_id == registered_client.client_id


class TestKeyErrorHandling:
    """Tests for KeyError handling when entries don't exist or are expired."""

    def test_get_pending_auth_returns_none_for_missing_key(
        self, token_store: InMemoryTokenStore
    ):
        """get_pending_auth returns None for non-existent key."""
        assert token_store.get_pending_auth("nonexistent") is None

    def test_pop_pending_auth_returns_none_for_missing_key(
        self, token_store: InMemoryTokenStore
    ):
        """pop_pending_auth returns None for non-existent key."""
        assert token_store.pop_pending_auth("nonexistent") is None

    def test_get_auth_code_returns_none_for_missing_key(
        self, token_store: InMemoryTokenStore
    ):
        """get_auth_code returns None for non-existent key."""
        assert token_store.get_auth_code("nonexistent") is None

    def test_delete_auth_code_handles_missing_key(
        self, token_store: InMemoryTokenStore
    ):
        """delete_auth_code handles non-existent key gracefully."""
        # Should not raise an exception
        token_store.delete_auth_code("nonexistent")

    def test_get_access_token_returns_none_for_missing_key(
        self, token_store: InMemoryTokenStore
    ):
        """get_access_token returns None for non-existent key."""
        assert token_store.get_access_token("nonexistent") is None

    def test_revoke_access_token_handles_missing_key(
        self, token_store: InMemoryTokenStore
    ):
        """revoke_access_token handles non-existent key gracefully."""
        # Should not raise an exception
        token_store.revoke_access_token("nonexistent")


class TestRegisteredClientsNeverExpire:
    """Tests for registered clients (which should never expire)."""

    def test_registered_client_persists_indefinitely(
        self, token_store: InMemoryTokenStore
    ):
        """Registered clients are not subject to TTL expiration."""
        client = RegisteredClient(
            client_id="persistent_client",
            client_name="Persistent Client",
            redirect_uris=["http://localhost/callback"],
            grant_types=["authorization_code"],
            response_types=["code"],
            created_at=datetime.now(timezone.utc),
        )
        token_store.register_client(client)

        # Client should be retrievable
        retrieved = token_store.get_registered_client("persistent_client")
        assert retrieved is not None
        assert retrieved.client_name == "Persistent Client"

    def test_list_registered_clients_returns_all_clients(
        self, token_store: InMemoryTokenStore
    ):
        """list_registered_clients returns all registered clients."""
        for i in range(3):
            client = RegisteredClient(
                client_id=f"client_{i}",
                client_name=f"Client {i}",
                redirect_uris=["http://localhost/callback"],
                grant_types=["authorization_code"],
                response_types=["code"],
                created_at=datetime.now(timezone.utc),
            )
            token_store.register_client(client)

        clients = token_store.list_registered_clients()
        assert len(clients) == 3


class TestRefreshTokenLookup:
    """Tests for looking up access tokens by refresh token."""

    def test_get_access_token_by_refresh_token_found(
        self,
        token_store: InMemoryTokenStore,
        sample_external_tokens: ExternalTokens,
        registered_client: RegisteredClient,
    ):
        """Can find access token by its refresh token."""
        token = AccessToken(
            external_tokens=sample_external_tokens,
            client_id=registered_client.client_id,
            scope="mcp:tools",
            refresh_token="unique_refresh_token",
            expires_at=datetime.now(timezone.utc),
        )
        token_store.store_access_token(token, "access_token_key")

        result = token_store.get_access_token_by_refresh_token("unique_refresh_token")
        assert result is not None
        token_key, retrieved_token = result
        assert token_key == "access_token_key"
        assert retrieved_token.refresh_token == "unique_refresh_token"

    def test_get_access_token_by_refresh_token_not_found(
        self, token_store: InMemoryTokenStore
    ):
        """Returns None when refresh token is not found."""
        result = token_store.get_access_token_by_refresh_token("nonexistent")
        assert result is None
