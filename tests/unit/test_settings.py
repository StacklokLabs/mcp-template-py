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
