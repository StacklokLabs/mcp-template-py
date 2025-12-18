import pytest
from pydantic import ValidationError

from mcp_template_py.settings import parse_comma_separated_list, Settings


class TestParseCommaSeparatedList:
    def test_empty_string_returns_empty_list(self):
        assert parse_comma_separated_list("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert parse_comma_separated_list("   ") == []

    def test_single_value(self):
        assert parse_comma_separated_list("scope1") == ["scope1"]

    def test_multiple_values(self):
        assert parse_comma_separated_list("scope1,scope2,scope3") == [
            "scope1",
            "scope2",
            "scope3",
        ]

    def test_values_with_whitespace_are_stripped(self):
        assert parse_comma_separated_list("scope1, scope2 , scope3") == [
            "scope1",
            "scope2",
            "scope3",
        ]

    def test_empty_values_are_filtered(self):
        assert parse_comma_separated_list("scope1,,scope2") == ["scope1", "scope2"]

    def test_list_input_returns_list(self):
        assert parse_comma_separated_list(["a", "b"]) == ["a", "b"]


class TestSettingsOauthExternalScopes:
    def test_empty_env_var_results_in_empty_list(self, monkeypatch):
        monkeypatch.setenv("OAUTH_EXTERNAL_SCOPES", "")
        settings = Settings()
        assert settings.get_oauth_scopes() == []

    def test_comma_separated_scopes_parsed(self, monkeypatch):
        monkeypatch.setenv("OAUTH_EXTERNAL_SCOPES", "read,write,admin")
        settings = Settings()
        assert settings.get_oauth_scopes() == ["read", "write", "admin"]

    def test_scopes_with_whitespace_stripped(self, monkeypatch):
        monkeypatch.setenv("OAUTH_EXTERNAL_SCOPES", "read, write , admin")
        settings = Settings()
        assert settings.get_oauth_scopes() == ["read", "write", "admin"]


class TestOAuthSettingsValidation:
    """Tests for OAuth settings validation when enable_oauth is True."""

    def test_oauth_disabled_requires_no_credentials(self):
        """OAuth can be disabled without any credentials."""
        settings = Settings(enable_oauth=False)
        assert settings.enable_oauth is False

    def test_oauth_enabled_requires_client_id(self):
        """OAuth enabled requires oauth_client_id."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                enable_oauth=True,
                oauth_client_id="",
                oauth_client_secret="secret",
                oauth_external_auth_url="https://auth.example.com",
                oauth_external_token_url="https://token.example.com",
            )
        assert "OAuth client ID" in str(exc_info.value)

    def test_oauth_enabled_requires_client_secret(self):
        """OAuth enabled requires oauth_client_secret."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                enable_oauth=True,
                oauth_client_id="client_id",
                oauth_client_secret="",
                oauth_external_auth_url="https://auth.example.com",
                oauth_external_token_url="https://token.example.com",
            )
        assert "OAuth client secret" in str(exc_info.value)

    def test_oauth_enabled_requires_auth_url(self):
        """OAuth enabled requires oauth_external_auth_url."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                enable_oauth=True,
                oauth_client_id="client_id",
                oauth_client_secret="secret",
                oauth_external_auth_url="",
                oauth_external_token_url="https://token.example.com",
            )
        assert "OAuth external auth URL" in str(exc_info.value)

    def test_oauth_enabled_requires_token_url(self):
        """OAuth enabled requires oauth_external_token_url."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                enable_oauth=True,
                oauth_client_id="client_id",
                oauth_client_secret="secret",
                oauth_external_auth_url="https://auth.example.com",
                oauth_external_token_url="",
            )
        assert "OAuth external token URL" in str(exc_info.value)

    def test_oauth_enabled_with_all_settings_succeeds(self):
        """OAuth enabled with all required settings succeeds."""
        settings = Settings(
            enable_oauth=True,
            oauth_client_id="client_id",
            oauth_client_secret="secret",
            oauth_external_auth_url="https://auth.example.com",
            oauth_external_token_url="https://token.example.com",
        )
        assert settings.enable_oauth is True
        assert settings.oauth_client_id == "client_id"

    def test_oauth_enabled_reports_all_missing_fields(self):
        """OAuth enabled reports all missing fields at once."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                enable_oauth=True,
                oauth_client_id="",
                oauth_client_secret="",
                oauth_external_auth_url="",
                oauth_external_token_url="",
            )
        error_msg = str(exc_info.value)
        assert "OAuth client ID" in error_msg
        assert "OAuth client secret" in error_msg
        assert "OAuth external auth URL" in error_msg
        assert "OAuth external token URL" in error_msg
