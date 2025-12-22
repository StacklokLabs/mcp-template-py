"""FastAPI router for OAuth 2.0 endpoints.

This module implements OAuth 2.0 Authorization Server functionality using FastAPI.
It provides endpoints for client registration, authorization, token issuance, and
external OAuth provider integration.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter, Form, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse

from mcp_template_py.api.oauth_dependencies import (
    AuthManagerDep,
    SettingsDep,
    TokenStoreDep,
)
from mcp_template_py.api.oauth_models import (
    ClientRegistrationRequest,
    ClientRegistrationResponse,
    OAuthMetadataResponse,
    TokenResponse,
)
from mcp_template_py.auth.auth_manager import AuthManager
from mcp_template_py.auth.token_store import (
    AccessToken,
    AuthCode,
    ExternalTokens,
    PendingAuth,
    RegisteredClient,
    TokenStore,
)
from mcp_template_py.settings import Settings

router = APIRouter(tags=["OAuth 2.0"])
logger = structlog.get_logger()


@router.get(
    "/.well-known/oauth-authorization-server",
    summary="OAuth 2.0 Authorization Server Metadata",
    description="OAuth 2.0 Authorization Server Metadata (RFC 8414) for MCP client discovery",
)
async def oauth_metadata(settings: SettingsDep) -> OAuthMetadataResponse:
    """OAuth 2.0 Authorization Server Metadata (RFC 8414).

    MCP clients discover OAuth endpoints by fetching:
    GET /.well-known/oauth-authorization-server

    This tells the client where to register, authorize, and get tokens.
    """
    logger.debug("OAuth metadata requested")
    return OAuthMetadataResponse(
        issuer=settings.server_url,
        authorization_endpoint=f"{settings.server_url}/oauth/authorize",
        token_endpoint=f"{settings.server_url}/oauth/token",
        registration_endpoint=f"{settings.server_url}/oauth/register",
        response_types_supported=["code"],
        grant_types_supported=["authorization_code", "refresh_token"],
        code_challenge_methods_supported=["S256"],
        token_endpoint_auth_methods_supported=["none"],  # Public client
        scopes_supported=["mcp:tools", "mcp:resources"],
    )


@router.post(
    "/oauth/register",
    status_code=status.HTTP_201_CREATED,
    summary="Dynamic Client Registration",
    description="Dynamic Client Registration (RFC 7591) - MCP clients automatically register to get a client_id",
    responses={
        201: {"description": "Client successfully registered"},
        400: {"description": "Invalid request (e.g., missing redirect_uris)"},
    },
)
async def register_client(
    registration: ClientRegistrationRequest,
    token_store: TokenStoreDep,
    auth_manager: AuthManagerDep,
) -> ClientRegistrationResponse:
    """Dynamic Client Registration (RFC 7591).

    MCP clients automatically register themselves to get a client_id.
    This eliminates the need for manual client registration.

    Request body:
        {
            "client_name": "Claude Code",
            "redirect_uris": ["http://localhost:8100/oauth/callback"]
        }
    """
    client_name = registration.client_name
    logger.debug("Client registration requested", client_name=client_name)

    if not registration.redirect_uris:
        logger.debug(
            "Client registration failed: redirect_uris required for client",
            client_name=client_name,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "error_description": "redirect_uris required",
            },
        )

    client_id = f"client_{auth_manager.generate_token()[:16]}"

    token_store.register_client(
        RegisteredClient(
            client_id=client_id,
            client_name=client_name,
            redirect_uris=registration.redirect_uris,
            grant_types=registration.grant_types,
            response_types=registration.response_types,
            created_at=datetime.now(timezone.utc),
        )
    )

    logger.info("Client registered successfully", client_id=client_id, name=client_name)
    return ClientRegistrationResponse(
        client_id=client_id,
        client_name=client_name,
        redirect_uris=registration.redirect_uris,
        grant_types=["authorization_code"],
        response_types=["code"],
        token_endpoint_auth_method="none",
    )


@router.get(
    "/oauth/authorize",
    response_class=RedirectResponse,
    summary="OAuth 2.0 Authorization Endpoint",
    description="Start OAuth 2.0 authorization flow with PKCE",
    responses={
        307: {"description": "Redirect to external OAuth provider"},
        400: {"description": "Invalid request parameters"},
    },
)
async def authorize(
    token_store: TokenStoreDep,
    auth_manager: AuthManagerDep,
    settings: SettingsDep,
    client_id: Annotated[str | None, Query()] = None,
    redirect_uri: Annotated[str | None, Query()] = None,
    response_type: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    code_challenge: Annotated[str | None, Query()] = None,
    code_challenge_method: Annotated[str | None, Query()] = None,
    scope: Annotated[str | None, Query()] = None,
) -> Response:
    """OAuth 2.0 Authorization Endpoint.

    Flow:
    1. MCP client redirects user here with PKCE challenge
    2. We validate the request and store pending auth state
    3. We redirect user to e.g. Google for authentication
    4. After external auth, user returns to /oauth/callback

    Required query parameters:
        - client_id: Registered client ID
        - redirect_uri: Must match registered URI
        - response_type: Must be "code"
        - state: CSRF protection token
        - code_challenge: PKCE challenge
        - code_challenge_method: Must be "S256"
    """
    logger.debug("Authorization requested", client_id=client_id)

    # Validate response_type
    if response_type != "code":
        logger.debug(
            "Authorization failed: unsupported_response_type",
            response_type=response_type,
            client_id=client_id,
        )
        raise HTTPException(
            status_code=400,
            detail={"error": "unsupported_response_type"},
        )

    # Validate PKCE (required for security)
    if code_challenge_method != "S256":
        logger.debug(
            "Authorization failed: PKCE S256 required",
            code_challenge_method=code_challenge_method,
            client_id=client_id,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "error_description": "PKCE with S256 required",
            },
        )

    if not code_challenge:
        logger.debug(
            "Authorization failed: code_challenge required", client_id=client_id
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "error_description": "code_challenge required",
            },
        )

    # Validate client
    if not client_id:
        logger.debug("Authorization failed: client_id required")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "error_description": "client_id required",
            },
        )
    client = token_store.get_registered_client(client_id)
    if not client:
        logger.debug("Authorization failed: client not registered", client_id=client_id)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_client",
                "error_description": "Client not registered",
            },
        )

    if redirect_uri not in client.redirect_uris:
        logger.debug(
            "Authorization failed: redirect_uri not registered",
            client_id=client_id,
            redirect_uri=redirect_uri,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "error_description": "redirect_uri not registered",
            },
        )

    # Store pending authorization (will be completed after external auth)
    external_state = auth_manager.generate_token()
    token_store.store_pending_auth(
        PendingAuth(
            mcp_state=state,
            code_challenge=code_challenge,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope or "mcp:tools",
            created_at=datetime.now(timezone.utc),
        ),
        state=external_state,
    )

    # Redirect to external OAuth
    external_params = {
        "client_id": settings.oauth_client_id,
        "redirect_uri": settings.get_oauth_redirect_url(),
        "response_type": "code",
        "scope": " ".join(settings.get_oauth_scopes()),
        "state": external_state,
        "access_type": "offline",  # Request refresh token
        "prompt": "consent",  # Always show consent to get refresh token
    }

    external_auth_url = (
        f"{settings.oauth_external_auth_url}?{urlencode(external_params)}"
    )
    return RedirectResponse(url=external_auth_url)


@router.get(
    "/oauth/callback",
    response_class=RedirectResponse,
    summary="External OAuth Callback Handler",
    description="Handles callback from external OAuth provider",
    responses={
        307: {"description": "Redirect to MCP client with authorization code"},
        400: {"description": "Error in external auth or invalid state"},
        502: {"description": "Error from external OAuth provider"},
        503: {"description": "Network error contacting external provider"},
    },
)
async def external_callback(
    token_store: TokenStoreDep,
    auth_manager: AuthManagerDep,
    settings: SettingsDep,
    state: Annotated[str | None, Query()] = None,
    code: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
) -> Response:
    """External OAuth Callback Handler.

    Flow:
    1. External provider redirects user here after authentication
    2. We exchange external provider's code for tokens
    3. We generate our own authorization code
    4. We redirect user back to MCP client with our code
    """
    logger.debug("External callback received")

    # Check for external errors
    if error:
        logger.debug(
            "External callback failed",
            error=error,
            error_description=error_description,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "external_auth_failed",
                "error_description": error_description or error,
            },
        )

    # Validate state and retrieve pending auth
    if not state:
        logger.debug("External callback failed: state parameter required")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "error_description": "state required",
            },
        )
    pending = token_store.pop_pending_auth(state)

    if not pending:
        logger.debug("External callback failed: state not found or expired")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_state",
                "error_description": "State not found or expired",
            },
        )

    client_id = pending.client_id
    logger.debug("External callback: found pending auth", client_id=client_id)

    # Check if pending auth has expired (10 minute timeout)
    if datetime.now(timezone.utc) - pending.created_at > timedelta(minutes=10):
        logger.debug(
            "External callback failed: authorization request expired",
            client_id=client_id,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "expired",
                "error_description": "Authorization request expired",
            },
        )

    # Exchange external provider authorization code for tokens
    external_code = code
    if not external_code:
        logger.debug(
            "External callback failed: external authorization code missing",
            client_id=client_id,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "error_description": "External authorization code missing",
            },
        )
    try:
        logger.debug(
            "External callback: exchanging external code for tokens",
            client_id=client_id,
        )
        external_tokens = await auth_manager.exchange_external_code(external_code)
    except httpx.HTTPStatusError as e:
        logger.warning(
            "External callback failed: token exchange returned error status",
            client_id=client_id,
            status_code=e.response.status_code,
            error=str(e),
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "token_exchange_failed",
                "error_description": f"External provider returned status {e.response.status_code}",
            },
        )
    except httpx.HTTPError as e:
        logger.exception(
            "External callback failed: network error during token exchange",
            client_id=client_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "token_exchange_failed",
                "error_description": "Network error contacting external provider",
            },
        )

    # Generate our own authorization code
    mcp_code = auth_manager.generate_token()
    token_store.store_auth_code(
        AuthCode(
            external_tokens=ExternalTokens(**external_tokens),
            client_id=pending.client_id,
            redirect_uri=pending.redirect_uri,
            code_challenge=pending.code_challenge,
            scope=pending.scope,
            created_at=datetime.now(timezone.utc),
        ),
        code=mcp_code,
    )

    # Redirect back to MCP client with our authorization code
    redirect_params = {
        "code": mcp_code,
        "state": pending.mcp_state,
    }
    redirect_url = f"{pending.redirect_uri}?{urlencode(redirect_params)}"

    logger.info(
        "External callback successful: redirecting back to MCP client",
        client_id=client_id,
    )
    return RedirectResponse(url=redirect_url)


@router.post(
    "/oauth/token",
    summary="OAuth 2.0 Token Endpoint",
    description="Exchange authorization code for access token or refresh tokens",
    responses={
        200: {"description": "Access token issued successfully"},
        400: {"description": "Invalid grant or unsupported grant type"},
        503: {"description": "Error refreshing external tokens"},
    },
)
async def token_endpoint(
    token_store: TokenStoreDep,
    auth_manager: AuthManagerDep,
    settings: SettingsDep,
    grant_type: Annotated[str, Form()],
    client_id: Annotated[str | None, Form()] = None,
    code: Annotated[str | None, Form()] = None,
    redirect_uri: Annotated[str | None, Form()] = None,
    code_verifier: Annotated[str | None, Form()] = None,
    refresh_token: Annotated[str | None, Form()] = None,
) -> TokenResponse:
    """OAuth 2.0 Token Endpoint.

    Handles two grant types:
    1. authorization_code: Exchange auth code for access token
    2. refresh_token: Get new access token using refresh token
    """
    logger.debug("Token endpoint called", grant_type=grant_type, client_id=client_id)

    if grant_type == "authorization_code":
        return await handle_authorization_code_grant(
            code=code,
            redirect_uri=redirect_uri,
            client_id=client_id,
            code_verifier=code_verifier,
            token_store=token_store,
            auth_manager=auth_manager,
            settings=settings,
        )
    elif grant_type == "refresh_token":
        return await handle_refresh_token_grant(
            refresh_token=refresh_token,
            token_store=token_store,
            auth_manager=auth_manager,
            settings=settings,
        )
    else:
        logger.debug(
            "Token endpoint failed, unsupported grant type",
            grant_type=grant_type,
            client_id=client_id,
        )
        raise HTTPException(
            status_code=400,
            detail={"error": "unsupported_grant_type"},
        )


# Helper functions


async def handle_authorization_code_grant(
    code: str | None,
    redirect_uri: str | None,
    client_id: str | None,
    code_verifier: str | None,
    token_store: TokenStore,
    auth_manager: AuthManager,
    settings: Settings,
) -> TokenResponse:
    """Handle authorization_code grant type."""
    logger.debug("Processing authorization code grant", client_id=client_id)

    # Ensure code is a string (not UploadFile)
    if not isinstance(code, str):
        logger.debug(
            "Authorization code grant failed: code must be a string",
            client_id=client_id,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "error_description": "code must be a string",
            },
        )

    # Retrieve and validate authorization code
    auth_code = token_store.get_auth_code(code)
    if not auth_code:
        logger.debug(
            "Authorization code grant failed: code not found", client_id=client_id
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_grant",
                "error_description": "Code not found",
            },
        )

    # Check expiration (10 minute timeout)
    if datetime.now(timezone.utc) - auth_code.created_at > timedelta(minutes=10):
        token_store.delete_auth_code(code)
        logger.debug(
            "Authorization code grant failed: code expired", client_id=client_id
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_grant",
                "error_description": "Code expired",
            },
        )

    # Verify PKCE
    if not isinstance(code_verifier, str) or not auth_manager.verify_pkce(
        code_verifier, auth_code.code_challenge
    ):
        logger.debug(
            "Authorization code grant failed: PKCE verification failed",
            client_id=client_id,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_grant",
                "error_description": "PKCE verification failed",
            },
        )

    # Validate client_id and redirect_uri match
    if auth_code.client_id != client_id:
        logger.debug(
            "Authorization code grant failed: client_id mismatch",
            expected=auth_code.client_id,
            got=client_id,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_grant",
                "error_description": "client_id mismatch",
            },
        )
    if auth_code.redirect_uri != redirect_uri:
        logger.debug(
            "Authorization code grant failed: redirect_uri mismatch",
            client_id=client_id,
            expected=auth_code.redirect_uri,
            got=redirect_uri,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_grant",
                "error_description": "redirect_uri mismatch",
            },
        )

    # Consume the authorization code (one-time use)
    token_store.delete_auth_code(code)

    # Issue our access token
    access_token = f"{settings.minted_token_prefix}{auth_manager.generate_token()}"
    refresh_token = f"{settings.minted_token_prefix}{auth_manager.generate_token()}"
    expires_in = 3600  # 1 hour

    token_store.store_access_token(
        AccessToken(
            external_tokens=auth_code.external_tokens,
            client_id=auth_code.client_id,
            scope=auth_code.scope,
            refresh_token=refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        ),
        token=access_token,
    )

    logger.info(
        "Authorization code grant successful: issued access token",
        client_id=client_id,
    )
    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=expires_in,
        refresh_token=refresh_token,
        scope=auth_code.scope,
    )


async def handle_refresh_token_grant(
    refresh_token: str | None,
    token_store: TokenStore,
    auth_manager: AuthManager,
    settings: Settings,
) -> TokenResponse:
    """Handle refresh_token grant type."""
    logger.debug("Refresh token grant: processing request")

    # Validate refresh_token is a string
    if not isinstance(refresh_token, str):
        logger.debug("Refresh token grant failed: refresh_token must be a string")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "error_description": "refresh_token must be a string",
            },
        )

    # Find the token entry with this refresh token
    result = token_store.get_access_token_by_refresh_token(refresh_token)

    if not result:
        logger.debug("Refresh token grant failed: refresh token not found")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_grant",
                "error_description": "Refresh token not found",
            },
        )

    old_access_token, token_entry = result
    client_id = token_entry.client_id
    logger.debug("Refresh token grant: found token entry", client_id=client_id)

    # Refresh external tokens if we have an external refresh token
    external_tokens = token_entry.external_tokens
    if external_tokens.refresh_token:
        try:
            logger.debug(
                "Refresh token grant: refreshing external tokens",
                client_id=client_id,
            )
            new_external_tokens_dict = await auth_manager.refresh_external_token(
                external_tokens.refresh_token
            )
            # Preserve the refresh token if external provider doesn't return a new one
            if "refresh_token" not in new_external_tokens_dict:
                new_external_tokens_dict["refresh_token"] = (
                    external_tokens.refresh_token
                )
            external_tokens = ExternalTokens(**new_external_tokens_dict)
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Refresh token grant failed: external provider returned error status",
                client_id=client_id,
                status_code=e.response.status_code,
                error=str(e),
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_grant",
                    "error_description": "External token refresh failed",
                },
            )
        except httpx.HTTPError as e:
            logger.exception(
                "Refresh token grant failed: network error during external refresh",
                client_id=client_id,
                error=str(e),
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "server_error",
                    "error_description": "Network error contacting external provider",
                },
            )

    # Remove old token
    token_store.revoke_access_token(old_access_token)

    # Issue new tokens
    new_access_token = f"{settings.minted_token_prefix}{auth_manager.generate_token()}"
    new_refresh_token = f"{settings.minted_token_prefix}{auth_manager.generate_token()}"
    expires_in = 3600

    token_store.store_access_token(
        AccessToken(
            external_tokens=external_tokens,
            client_id=client_id,
            scope=token_entry.scope,
            refresh_token=new_refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        ),
        token=new_access_token,
    )

    logger.info(
        "Refresh token grant successful: issued new access token",
        client_id=client_id,
    )
    return TokenResponse(
        access_token=new_access_token,
        token_type="Bearer",
        expires_in=expires_in,
        refresh_token=new_refresh_token,
        scope=token_entry.scope,
    )


# FastAPI app factory


def create_oauth_fastapi_app(
    token_store: TokenStore,
    auth_manager: AuthManager,
    settings: Settings,
):
    """Create FastAPI app with OAuth router and configured dependencies.

    This factory function creates a FastAPI application with the OAuth router
    included and sets up dependency injection for the token store, auth manager,
    and settings.

    Args:
        token_store: TokenStore instance for managing OAuth tokens and clients
        auth_manager: AuthManager instance for cryptographic operations
        settings: Settings instance for OAuth configuration

    Returns:
        FastAPI application with OAuth endpoints configured
    """
    from fastapi import FastAPI

    from mcp_template_py.api.oauth_dependencies import (
        set_auth_manager,
        set_settings,
        set_token_store,
    )

    # Set context variables for dependency injection
    set_token_store(token_store)
    set_auth_manager(auth_manager)
    set_settings(settings)

    # Create FastAPI app
    app = FastAPI(
        title="MCP OAuth Server",
        description="OAuth 2.0 authentication for MCP",
        version="1.0.0",
        docs_url=None,  # Disable docs in production
        redoc_url=None,
    )

    # Include OAuth router
    app.include_router(router)

    return app
