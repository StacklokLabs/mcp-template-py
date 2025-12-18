"""Shared fixtures for auth unit tests.

This module uses the shared fixtures from tests.fixtures and adds
auth-specific fixtures as needed.
"""

import pytest

from mcp_template_py.auth.auth_manager import AuthManager
from mcp_template_py.auth.token_store import (
    AccessToken,
    AuthCode,
    ExternalTokens,
    InMemoryTokenStore,
    PendingAuth,
    RegisteredClient,
    TokenStore,
)
from mcp_template_py.settings import Settings
from tests.fixtures import (
    create_access_token,
    create_auth_code,
    create_external_tokens,
    create_pending_auth,
    create_registered_client,
    create_test_settings,
    generate_pkce_pair,
    get_mock_external_refresh_response,
    get_mock_external_token_response,
)


@pytest.fixture
def mock_settings() -> Settings:
    """Create test settings with fake OAuth credentials."""
    return create_test_settings(server_url="http://localhost:8100")


@pytest.fixture
def token_store() -> InMemoryTokenStore:
    """Create a fresh InMemoryTokenStore instance."""
    return InMemoryTokenStore()


@pytest.fixture
def auth_manager(mock_settings: Settings) -> AuthManager:
    """Create an AuthManager with test settings."""
    return AuthManager(mock_settings)


@pytest.fixture
def sample_external_tokens() -> ExternalTokens:
    """Create sample external tokens for testing."""
    return create_external_tokens()


@pytest.fixture
def pkce_pair() -> tuple[str, str]:
    """Generate a valid PKCE code_verifier and code_challenge pair."""
    return generate_pkce_pair()


@pytest.fixture
def registered_client(token_store: TokenStore) -> RegisteredClient:
    """Register and return a test client."""
    return create_registered_client(token_store)


@pytest.fixture
def pending_auth(
    token_store: TokenStore,
    registered_client: RegisteredClient,
    pkce_pair: tuple[str, str],
) -> tuple[str, PendingAuth]:
    """Create a pending auth state and return (state_key, pending_auth)."""
    _, code_challenge = pkce_pair
    return create_pending_auth(token_store, registered_client, code_challenge)


@pytest.fixture
def valid_auth_code(
    token_store: TokenStore,
    registered_client: RegisteredClient,
    sample_external_tokens: ExternalTokens,
    pkce_pair: tuple[str, str],
) -> tuple[str, AuthCode]:
    """Create a valid authorization code."""
    _, code_challenge = pkce_pair
    return create_auth_code(
        token_store, registered_client, sample_external_tokens, code_challenge
    )


@pytest.fixture
def valid_access_token(
    token_store: TokenStore,
    registered_client: RegisteredClient,
    sample_external_tokens: ExternalTokens,
) -> tuple[str, AccessToken]:
    """Create a valid access token."""
    return create_access_token(token_store, registered_client, sample_external_tokens)


@pytest.fixture
def expired_access_token(
    token_store: TokenStore,
    registered_client: RegisteredClient,
    sample_external_tokens: ExternalTokens,
) -> tuple[str, AccessToken]:
    """Create an expired access token."""
    return create_access_token(
        token_store, registered_client, sample_external_tokens, expired=True
    )


@pytest.fixture
def mock_external_token_response() -> dict:
    """Mock successful external token exchange response."""
    return get_mock_external_token_response()


@pytest.fixture
def mock_external_refresh_response() -> dict:
    """Mock successful external token refresh response."""
    return get_mock_external_refresh_response()
