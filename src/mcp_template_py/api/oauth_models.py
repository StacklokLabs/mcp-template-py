"""Pydantic models for OAuth 2.0 API request/response validation."""

from pydantic import BaseModel, Field


class ClientRegistrationRequest(BaseModel):
    """Request body for dynamic client registration (RFC 7591)."""

    client_name: str = Field(
        default="Unknown MCP Client",
        description="Human-readable name of the client",
    )
    redirect_uris: list[str] = Field(
        description="List of redirect URIs for authorization callbacks"
    )
    grant_types: list[str] = Field(
        default=["authorization_code"],
        description="OAuth 2.0 grant types supported by this client",
    )
    response_types: list[str] = Field(
        default=["code"],
        description="OAuth 2.0 response types supported by this client",
    )


class ClientRegistrationResponse(BaseModel):
    """Response for successful client registration."""

    client_id: str = Field(description="Unique client identifier")
    client_name: str = Field(description="Human-readable name of the client")
    redirect_uris: list[str] = Field(
        description="Registered redirect URIs for this client"
    )
    grant_types: list[str] = Field(
        description="OAuth 2.0 grant types supported by this client"
    )
    response_types: list[str] = Field(
        description="OAuth 2.0 response types supported by this client"
    )
    token_endpoint_auth_method: str = Field(
        description="Authentication method for token endpoint (none for public clients)"
    )


class OAuthMetadataResponse(BaseModel):
    """OAuth 2.0 Authorization Server Metadata (RFC 8414)."""

    issuer: str = Field(description="Authorization server issuer identifier")
    authorization_endpoint: str = Field(description="URL of the authorization endpoint")
    token_endpoint: str = Field(description="URL of the token endpoint")
    registration_endpoint: str = Field(
        description="URL of the dynamic client registration endpoint"
    )
    response_types_supported: list[str] = Field(
        description="List of supported OAuth 2.0 response types"
    )
    grant_types_supported: list[str] = Field(
        description="List of supported OAuth 2.0 grant types"
    )
    code_challenge_methods_supported: list[str] = Field(
        description="List of supported PKCE code challenge methods"
    )
    token_endpoint_auth_methods_supported: list[str] = Field(
        description="List of supported client authentication methods at token endpoint"
    )
    scopes_supported: list[str] = Field(
        description="List of supported OAuth 2.0 scopes"
    )


class TokenResponse(BaseModel):
    """Response for successful token issuance."""

    access_token: str = Field(description="The access token issued by the server")
    token_type: str = Field(description="The type of token (typically 'Bearer')")
    expires_in: int = Field(description="Token lifetime in seconds")
    refresh_token: str = Field(description="The refresh token for obtaining new tokens")
    scope: str = Field(description="The scope of the access token")


class OAuthErrorResponse(BaseModel):
    """Standardized OAuth 2.0 error response."""

    error: str = Field(description="Error code as defined in RFC 6749")
    error_description: str | None = Field(
        default=None, description="Human-readable error description"
    )
