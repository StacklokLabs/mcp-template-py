"""Unit tests for AuthManager."""

import pytest
from httpx import HTTPStatusError

from mcp_template_py.auth.auth_manager import AuthManager
from mcp_template_py.auth.token_store import ExternalTokens


class TestVerifyPKCE:
    """Tests for PKCE verification."""

    def test_verify_pkce_valid(
        self, auth_manager: AuthManager, pkce_pair: tuple[str, str]
    ):
        """Test PKCE verification with valid verifier/challenge pair."""
        code_verifier, code_challenge = pkce_pair
        assert auth_manager.verify_pkce(code_verifier, code_challenge) is True

    def test_verify_pkce_invalid_verifier(
        self, auth_manager: AuthManager, pkce_pair: tuple[str, str]
    ):
        """Test PKCE verification with invalid verifier."""
        _, code_challenge = pkce_pair
        assert auth_manager.verify_pkce("wrong_verifier", code_challenge) is False

    def test_verify_pkce_invalid_challenge(
        self, auth_manager: AuthManager, pkce_pair: tuple[str, str]
    ):
        """Test PKCE verification with invalid challenge."""
        code_verifier, _ = pkce_pair
        assert auth_manager.verify_pkce(code_verifier, "wrong_challenge") is False

    def test_verify_pkce_empty_strings(self, auth_manager: AuthManager):
        """Test PKCE verification with empty strings."""
        # Empty verifier creates a specific hash that won't match empty challenge
        assert auth_manager.verify_pkce("", "") is False


class TestGenerateToken:
    """Tests for token generation."""

    def test_generate_token_returns_string(self, auth_manager: AuthManager):
        """Test that generate_token returns a string."""
        token = auth_manager.generate_token()
        assert isinstance(token, str)
        assert len(token) > 20  # URL-safe base64 of 32 bytes

    def test_generate_token_unique(self, auth_manager: AuthManager):
        """Test that tokens are unique."""
        tokens = {auth_manager.generate_token() for _ in range(100)}
        assert len(tokens) == 100  # All unique


class TestExchangeExternalCode:
    """Tests for external code exchange with mocked httpx."""

    @pytest.mark.asyncio
    async def test_exchange_external_code_success(
        self,
        auth_manager: AuthManager,
        mock_external_token_response: dict,
        httpx_mock,
    ):
        """Test successful external code exchange."""
        httpx_mock.add_response(
            url="https://oauth2.example.com/token",
            method="POST",
            json=mock_external_token_response,
        )

        result = await auth_manager.exchange_external_code("valid_auth_code")

        assert result == mock_external_token_response
        assert result["access_token"] == "ya29.external_access_token"

    @pytest.mark.asyncio
    async def test_exchange_external_code_invalid_code(
        self,
        auth_manager: AuthManager,
        httpx_mock,
    ):
        """Test external code exchange with invalid code."""
        httpx_mock.add_response(
            url="https://oauth2.example.com/token",
            method="POST",
            status_code=400,
            json={"error": "invalid_grant", "error_description": "Bad Request"},
        )

        with pytest.raises(HTTPStatusError) as exc_info:
            await auth_manager.exchange_external_code("invalid_code")

        assert exc_info.value.response.status_code == 400

    @pytest.mark.asyncio
    async def test_exchange_external_code_server_error(
        self,
        auth_manager: AuthManager,
        httpx_mock,
    ):
        """Test external code exchange with server error."""
        httpx_mock.add_response(
            url="https://oauth2.example.com/token",
            method="POST",
            status_code=500,
            json={"error": "server_error"},
        )

        with pytest.raises(HTTPStatusError) as exc_info:
            await auth_manager.exchange_external_code("valid_code")

        assert exc_info.value.response.status_code == 500


class TestRefreshExternalToken:
    """Tests for external token refresh with mocked httpx."""

    @pytest.mark.asyncio
    async def test_refresh_external_token_success(
        self,
        auth_manager: AuthManager,
        mock_external_refresh_response: dict,
        httpx_mock,
    ):
        """Test successful external token refresh."""
        httpx_mock.add_response(
            url="https://oauth2.example.com/token",
            method="POST",
            json=mock_external_refresh_response,
        )

        result = await auth_manager.refresh_external_token("valid_refresh_token")

        assert result["access_token"] == "ya29.new_external_access_token"

    @pytest.mark.asyncio
    async def test_refresh_external_token_revoked(
        self,
        auth_manager: AuthManager,
        httpx_mock,
    ):
        """Test external token refresh with revoked token."""
        httpx_mock.add_response(
            url="https://oauth2.example.com/token",
            method="POST",
            status_code=400,
            json={
                "error": "invalid_grant",
                "error_description": "Token has been revoked",
            },
        )

        with pytest.raises(HTTPStatusError):
            await auth_manager.refresh_external_token("revoked_refresh_token")


class TestExternalTokensContext:
    """Tests for context variable management."""

    def test_set_and_get_external_tokens(
        self, auth_manager: AuthManager, sample_external_tokens: ExternalTokens
    ):
        """Test setting and getting external tokens in context."""
        ctx_token = auth_manager.set_external_tokens(sample_external_tokens)
        try:
            retrieved = auth_manager.get_external_tokens()
            assert retrieved == sample_external_tokens
        finally:
            auth_manager.reset_external_tokens(ctx_token)

    def test_get_external_tokens_not_set(self, auth_manager: AuthManager):
        """Test getting tokens when none are set."""
        with pytest.raises(ValueError, match="Not authenticated with external"):
            auth_manager.get_external_tokens()

    def test_reset_external_tokens(
        self, auth_manager: AuthManager, sample_external_tokens: ExternalTokens
    ):
        """Test that reset properly clears context."""
        ctx_token = auth_manager.set_external_tokens(sample_external_tokens)
        auth_manager.reset_external_tokens(ctx_token)

        with pytest.raises(ValueError):
            auth_manager.get_external_tokens()
