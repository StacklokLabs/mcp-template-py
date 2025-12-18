from datetime import datetime

from pydantic import BaseModel


class ExternalTokens(BaseModel):
    """External (e.g. Google) OAuth tokens."""

    access_token: str
    token_type: str
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None


class RegisteredClient(BaseModel):
    """A registered OAuth client."""

    client_id: str
    client_name: str
    redirect_uris: list[str]
    grant_types: list[str]
    response_types: list[str]
    created_at: datetime


class PendingAuth(BaseModel):
    """Pending authorization waiting for external callback."""

    mcp_state: str | None
    code_challenge: str
    client_id: str
    redirect_uri: str
    scope: str
    created_at: datetime


class AuthCode(BaseModel):
    """Authorization code issued after external auth."""

    external_tokens: ExternalTokens
    client_id: str
    redirect_uri: str
    code_challenge: str
    scope: str
    created_at: datetime


class AccessToken(BaseModel):
    """Issued access token with associated external tokens."""

    external_tokens: ExternalTokens
    client_id: str
    scope: str
    refresh_token: str
    expires_at: datetime
