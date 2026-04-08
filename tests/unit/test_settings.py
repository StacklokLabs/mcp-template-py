from mcp_template_py.settings import Settings


class TestSettingsDefaults:
    def test_default_settings(self):
        settings = Settings()
        assert settings.debug is False
        assert settings.mcp_host == "0.0.0.0"
        assert settings.mcp_port == 8100
        assert settings.server_url == "http://localhost:8100"

    def test_debug_parsed_from_string(self):
        settings = Settings(debug="true")  # type: ignore[arg-type]  # pydantic coerces via validator
        assert settings.debug is True

    def test_debug_parsed_from_bool(self):
        settings = Settings(debug=False)
        assert settings.debug is False
