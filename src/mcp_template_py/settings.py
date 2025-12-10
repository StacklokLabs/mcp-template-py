from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Add your settings fields here
    debug: bool = Field(default=False, description="Enable debug logging if 'true'")

    @field_validator("debug", mode="before")
    @classmethod
    def parse_bool(cls, value: str | bool) -> bool:
        """Parse a string or bool value to a boolean."""
        if isinstance(value, bool):
            return value
        return value.lower() in ("true", "1", "yes", "on")