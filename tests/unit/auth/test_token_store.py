"""Unit tests for InMemoryTokenStore cleanup methods."""

from datetime import datetime, timedelta, timezone

import pytest

from mcp_template_py.auth.token_store import (
    AccessToken,
    AuthCode,
    ExternalTokens,
    InMemoryTokenStore,
    PendingAuth,
    RegisteredClient,
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


class TestCleanupExpiredTokens:
    """Tests for access token cleanup."""

    def test_cleanup_removes_expired_tokens(
        self,
        token_store: InMemoryTokenStore,
        sample_external_tokens: ExternalTokens,
        registered_client: RegisteredClient,
    ):
        """Expired access tokens are removed."""
        # Create an expired token
        expired_token = AccessToken(
            external_tokens=sample_external_tokens,
            client_id=registered_client.client_id,
            scope="mcp:tools",
            refresh_token="refresh",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        token_store.store_access_token(expired_token, "expired_token")

        assert "expired_token" in token_store.access_tokens
        removed = token_store.cleanup_expired_tokens()
        assert removed == 1
        assert "expired_token" not in token_store.access_tokens

    def test_cleanup_preserves_valid_tokens(
        self,
        token_store: InMemoryTokenStore,
        sample_external_tokens: ExternalTokens,
        registered_client: RegisteredClient,
    ):
        """Valid access tokens are preserved."""
        valid_token = AccessToken(
            external_tokens=sample_external_tokens,
            client_id=registered_client.client_id,
            scope="mcp:tools",
            refresh_token="refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        token_store.store_access_token(valid_token, "valid_token")

        removed = token_store.cleanup_expired_tokens()
        assert removed == 0
        assert "valid_token" in token_store.access_tokens

    def test_cleanup_mixed_tokens(
        self,
        token_store: InMemoryTokenStore,
        sample_external_tokens: ExternalTokens,
        registered_client: RegisteredClient,
    ):
        """Cleanup correctly handles mix of expired and valid tokens."""
        # Create expired tokens
        for i in range(3):
            expired = AccessToken(
                external_tokens=sample_external_tokens,
                client_id=registered_client.client_id,
                scope="mcp:tools",
                refresh_token=f"refresh_{i}",
                expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
            token_store.store_access_token(expired, f"expired_{i}")

        # Create valid tokens
        for i in range(2):
            valid = AccessToken(
                external_tokens=sample_external_tokens,
                client_id=registered_client.client_id,
                scope="mcp:tools",
                refresh_token=f"valid_refresh_{i}",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
            token_store.store_access_token(valid, f"valid_{i}")

        removed = token_store.cleanup_expired_tokens()
        assert removed == 3
        assert len(token_store.access_tokens) == 2


class TestCleanupExpiredAuthCodes:
    """Tests for authorization code cleanup."""

    def test_cleanup_removes_old_auth_codes(
        self,
        token_store: InMemoryTokenStore,
        sample_external_tokens: ExternalTokens,
        registered_client: RegisteredClient,
    ):
        """Old authorization codes are removed."""
        old_code = AuthCode(
            external_tokens=sample_external_tokens,
            client_id=registered_client.client_id,
            redirect_uri="http://localhost/callback",
            code_challenge="challenge",
            scope="mcp:tools",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=15),
        )
        token_store.store_auth_code(old_code, "old_code")

        removed = token_store.cleanup_expired_auth_codes(max_age_minutes=10)
        assert removed == 1
        assert "old_code" not in token_store.auth_codes

    def test_cleanup_preserves_recent_auth_codes(
        self,
        token_store: InMemoryTokenStore,
        sample_external_tokens: ExternalTokens,
        registered_client: RegisteredClient,
    ):
        """Recent authorization codes are preserved."""
        recent_code = AuthCode(
            external_tokens=sample_external_tokens,
            client_id=registered_client.client_id,
            redirect_uri="http://localhost/callback",
            code_challenge="challenge",
            scope="mcp:tools",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        token_store.store_auth_code(recent_code, "recent_code")

        removed = token_store.cleanup_expired_auth_codes(max_age_minutes=10)
        assert removed == 0
        assert "recent_code" in token_store.auth_codes


class TestCleanupExpiredPendingAuths:
    """Tests for pending authorization cleanup."""

    def test_cleanup_removes_old_pending_auths(
        self,
        token_store: InMemoryTokenStore,
        registered_client: RegisteredClient,
    ):
        """Old pending authorizations are removed."""
        old_pending = PendingAuth(
            mcp_state="state",
            code_challenge="challenge",
            client_id=registered_client.client_id,
            redirect_uri="http://localhost/callback",
            scope="mcp:tools",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=15),
        )
        token_store.store_pending_auth(old_pending, "old_state")

        removed = token_store.cleanup_expired_pending_auths(max_age_minutes=10)
        assert removed == 1
        assert "old_state" not in token_store.pending_auths

    def test_cleanup_preserves_recent_pending_auths(
        self,
        token_store: InMemoryTokenStore,
        registered_client: RegisteredClient,
    ):
        """Recent pending authorizations are preserved."""
        recent_pending = PendingAuth(
            mcp_state="state",
            code_challenge="challenge",
            client_id=registered_client.client_id,
            redirect_uri="http://localhost/callback",
            scope="mcp:tools",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        token_store.store_pending_auth(recent_pending, "recent_state")

        removed = token_store.cleanup_expired_pending_auths(max_age_minutes=10)
        assert removed == 0
        assert "recent_state" in token_store.pending_auths


class TestCleanupAllExpired:
    """Tests for cleanup_all_expired method."""

    def test_cleanup_all_removes_expired_entries(
        self,
        token_store: InMemoryTokenStore,
        sample_external_tokens: ExternalTokens,
        registered_client: RegisteredClient,
    ):
        """cleanup_all_expired removes all expired entries."""
        # Create expired access token
        expired_token = AccessToken(
            external_tokens=sample_external_tokens,
            client_id=registered_client.client_id,
            scope="mcp:tools",
            refresh_token="refresh",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        token_store.store_access_token(expired_token, "expired_token")

        # Create old auth code
        old_code = AuthCode(
            external_tokens=sample_external_tokens,
            client_id=registered_client.client_id,
            redirect_uri="http://localhost/callback",
            code_challenge="challenge",
            scope="mcp:tools",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=15),
        )
        token_store.store_auth_code(old_code, "old_code")

        # Create old pending auth
        old_pending = PendingAuth(
            mcp_state="state",
            code_challenge="challenge",
            client_id=registered_client.client_id,
            redirect_uri="http://localhost/callback",
            scope="mcp:tools",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=15),
        )
        token_store.store_pending_auth(old_pending, "old_state")

        result = token_store.cleanup_all_expired()

        assert result == {
            "access_tokens": 1,
            "auth_codes": 1,
            "pending_auths": 1,
        }
        assert len(token_store.access_tokens) == 0
        assert len(token_store.auth_codes) == 0
        assert len(token_store.pending_auths) == 0

    def test_cleanup_all_returns_zero_counts_when_nothing_expired(
        self,
        token_store: InMemoryTokenStore,
    ):
        """cleanup_all_expired returns zero counts when nothing is expired."""
        result = token_store.cleanup_all_expired()
        assert result == {
            "access_tokens": 0,
            "auth_codes": 0,
            "pending_auths": 0,
        }
