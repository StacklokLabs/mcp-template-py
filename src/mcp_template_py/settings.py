from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_comma_separated_list(value: str | list[str]) -> list[str]:
    """Parse a comma-separated string into a list, or return the list as-is."""
    if isinstance(value, list):
        return value
    if not value or not value.strip():
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Add your settings fields here
    debug: bool = Field(default=False, description="Enable debug logging if 'true'")
    mcp_host: str = Field(
        default="0.0.0.0", description="Host for the MCP server to listen on"
    )
    mcp_port: int = Field(
        default=8100, description="Port for the MCP server to listen on"
    )
    server_url: str = Field(
        default="http://localhost:8100", description="Base URL of the server"
    )
    enable_oauth: bool = Field(
        default=False, description="Enable OAuth authentication if 'true'"
    )
    oauth_client_id: str = Field(
        default="", description="OAuth client ID for authentication"
    )
    oauth_client_secret: str = Field(
        default="", description="OAuth client secret for authentication"
    )
    oauth_external_auth_url: str = Field(
        default="", description="URL for external OAuth authentication"
    )
    oauth_external_token_url: str = Field(
        default="", description="URL for external OAuth token exchange"
    )
    oauth_external_scopes: str = Field(
        default="",
        description="Comma-separated list of scopes for external OAuth authentication",
    )

    def get_oauth_scopes(self) -> list[str]:
        """Get the OAuth scopes as a list."""
        return parse_comma_separated_list(self.oauth_external_scopes)

    @field_validator("debug", "enable_oauth", mode="before")
    @classmethod
    def parse_bool(cls, value: str | bool) -> bool:
        """Parse a string or bool value to a boolean."""
        if isinstance(value, bool):
            return value
        return value.lower() in ("true", "1", "yes", "on")

    def get_oauth_redirect_url(self) -> str:
        """Get the OAuth2 redirect URL based on the server URL."""
        return f"{self.server_url}/oauth/callback"
