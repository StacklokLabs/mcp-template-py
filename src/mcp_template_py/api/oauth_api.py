from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import structlog
from starlette.datastructures import FormData
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

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


class OAuthApi:
    def __init__(
        self,
        token_store: TokenStore,
        auth_manager: AuthManager,
        settings: Settings | None = None,
    ):
        self._token_store = token_store
        self._auth_manager = auth_manager
        self._settings = settings or Settings()
        self._logger = structlog.get_logger()

    async def oauth_metadata(self, request: Request) -> JSONResponse:
        """
        OAuth 2.0 Authorization Server Metadata (RFC 8414).

        MCP clients discover OAuth endpoints by fetching:
        GET /.well-known/oauth-authorization-server

        This tells the client where to register, authorize, and get tokens.
        """
        self._logger.debug("OAuth metadata requested")
        return JSONResponse(
            {
                "issuer": self._settings.server_url,
                "authorization_endpoint": f"{self._settings.server_url}/authorize",
                "token_endpoint": f"{self._settings.server_url}/token",
                "registration_endpoint": f"{self._settings.server_url}/register",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code", "refresh_token"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none"],  # Public client
                "scopes_supported": ["mcp:tools", "mcp:resources"],
            }
        )

    async def register_client(self, request: Request) -> JSONResponse:
        """
        Dynamic Client Registration (RFC 7591).

        MCP clients automatically register themselves to get a client_id.
        This eliminates the need for manual client registration.

        Request body:
            {
                "client_name": "Claude Code",
                "redirect_uris": ["http://localhost:8080/callback"]
            }
        """
        body = await request.json()
        client_name = body.get("client_name", "Unknown MCP Client")
        self._logger.debug("Client registration requested", client_name=client_name)

        redirect_uris = body.get("redirect_uris", [])
        if not redirect_uris:
            self._logger.debug(
                "Client registration failed: redirect_uris required for client",
                client_name=client_name,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_request",
                    "error_description": "redirect_uris required",
                },
            )

        client_id = f"client_{self._auth_manager.generate_token()[:16]}"

        self._token_store.register_client(
            RegisteredClient(
                client_id=client_id,
                client_name=client_name,
                redirect_uris=redirect_uris,
                grant_types=body.get("grant_types", ["authorization_code"]),
                response_types=body.get("response_types", ["code"]),
                created_at=datetime.now(timezone.utc),
            )
        )

        self._logger.info(
            "Client registered successfully", client_id=client_id, name=client_name
        )
        return JSONResponse(
            status_code=201,
            content={
                "client_id": client_id,
                "client_name": client_name,
                "redirect_uris": redirect_uris,
                "grant_types": ["authorization_code"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
            },
        )

    async def authorize(self, request: Request) -> RedirectResponse | JSONResponse:
        """
        OAuth 2.0 Authorization Endpoint.

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
        params = request.query_params
        client_id = params.get("client_id")
        self._logger.debug("Authorization requested", client_id=client_id)

        # Validate response_type
        if params.get("response_type") != "code":
            self._logger.debug(
                "Authorization failed: unsupported_response_type",
                response_type=params.get("response_type"),
                client_id=client_id,
            )
            return JSONResponse(
                status_code=400,
                content={"error": "unsupported_response_type"},
            )

        # Validate PKCE (required for security)
        if params.get("code_challenge_method") != "S256":
            self._logger.debug(
                "Authorization failed: PKCE S256 required",
                code_challenge_method=params.get("code_challenge_method"),
                client_id=client_id,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_request",
                    "error_description": "PKCE with S256 required",
                },
            )

        code_challenge = params.get("code_challenge")
        if not code_challenge:
            self._logger.debug(
                "Authorization failed: code_challenge required", client_id=client_id
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_request",
                    "error_description": "code_challenge required",
                },
            )

        # Validate client
        if not client_id:
            self._logger.debug("Authorization failed: client_id required")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_request",
                    "error_description": "client_id required",
                },
            )
        client = self._token_store.get_registered_client(client_id)
        if not client:
            self._logger.debug(
                "Authorization failed: client not registered", client_id=client_id
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_client",
                    "error_description": "Client not registered",
                },
            )

        redirect_uri = params.get("redirect_uri")
        if redirect_uri not in client.redirect_uris:
            self._logger.debug(
                "Authorization failed: redirect_uri not registered",
                client_id=client_id,
                redirect_uri=redirect_uri,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_request",
                    "error_description": "redirect_uri not registered",
                },
            )

        # Store pending authorization (will be completed after external auth)
        external_state = self._auth_manager.generate_token()
        self._token_store.store_pending_auth(
            PendingAuth(
                mcp_state=params.get("state"),
                code_challenge=code_challenge,
                client_id=client_id,
                redirect_uri=redirect_uri,
                scope=params.get("scope", "mcp:tools"),
                created_at=datetime.now(timezone.utc),
            ),
            state=external_state,
        )

        # Redirect to external OAuth
        external_params = {
            "client_id": self._settings.oauth_client_id,
            "redirect_uri": self._settings.get_oauth_redirect_url(),
            "response_type": "code",
            "scope": " ".join(self._settings.get_oauth_scopes()),
            "state": external_state,
            "access_type": "offline",  # Request refresh token
            "prompt": "consent",  # Always show consent to get refresh token
        }

        external_auth_url = (
            f"{self._settings.oauth_external_auth_url}?{urlencode(external_params)}"
        )
        return RedirectResponse(url=external_auth_url)

    async def external_callback(
        self, request: Request
    ) -> RedirectResponse | JSONResponse:
        """
        External OAuth Callback Handler.

        Flow:
        1. External provider redirects user here after authentication
        2. We exchange external provider's code for tokens
        3. We generate our own authorization code
        4. We redirect user back to MCP client with our code
        """
        params = request.query_params
        state = params.get("state")
        self._logger.debug("External callback received")

        # Check for external errors
        if params.get("error"):
            self._logger.debug(
                "External callback failed",
                error=params.get("error"),
                error_description=params.get("error_description"),
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "external_auth_failed",
                    "error_description": params.get(
                        "error_description", params.get("error")
                    ),
                },
            )

        # Validate state and retrieve pending auth
        if not state:
            self._logger.debug("External callback failed: state parameter required")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_request",
                    "error_description": "state required",
                },
            )
        pending = self._token_store.pop_pending_auth(state)

        if not pending:
            self._logger.debug("External callback failed: state not found or expired")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_state",
                    "error_description": "State not found or expired",
                },
            )

        client_id = pending.client_id
        self._logger.debug("External callback: found pending auth", client_id=client_id)

        # Check if pending auth has expired (10 minute timeout)
        if datetime.now(timezone.utc) - pending.created_at > timedelta(minutes=10):
            self._logger.debug(
                "External callback failed: authorization request expired",
                client_id=client_id,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "expired",
                    "error_description": "Authorization request expired",
                },
            )

        # Exchange external provider authorization code for tokens
        external_code = params.get("code")
        if not external_code:
            self._logger.debug(
                "External callback failed: external authorization code missing",
                client_id=client_id,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_request",
                    "error_description": "External authorization code missing",
                },
            )
        try:
            self._logger.debug(
                "External callback: exchanging external code for tokens",
                client_id=client_id,
            )
            external_tokens = await self._auth_manager.exchange_external_code(
                external_code
            )
        except httpx.HTTPStatusError as e:
            self._logger.warning(
                "External callback failed: token exchange returned error status",
                client_id=client_id,
                status_code=e.response.status_code,
                error=str(e),
            )
            return JSONResponse(
                status_code=502,
                content={
                    "error": "token_exchange_failed",
                    "error_description": f"External provider returned status {e.response.status_code}",
                },
            )
        except httpx.HTTPError as e:
            self._logger.exception(
                "External callback failed: network error during token exchange",
                client_id=client_id,
                error=str(e),
            )
            return JSONResponse(
                status_code=503,
                content={
                    "error": "token_exchange_failed",
                    "error_description": "Network error contacting external provider",
                },
            )

        # Generate our own authorization code
        mcp_code = self._auth_manager.generate_token()
        self._token_store.store_auth_code(
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

        self._logger.info(
            "External callback successful: redirecting back to MCP client",
            client_id=client_id,
        )
        return RedirectResponse(url=redirect_url)

    async def token_endpoint(self, request: Request) -> JSONResponse:
        """
        OAuth 2.0 Token Endpoint.

        Handles two grant types:
        1. authorization_code: Exchange auth code for access token
        2. refresh_token: Get new access token using refresh token
        """
        form = await request.form()
        grant_type = form.get("grant_type")
        client_id = form.get("client_id")
        self._logger.debug(
            "Token endpoint called", grant_type=grant_type, client_id=client_id
        )

        if grant_type == "authorization_code":
            return await self._handle_authorization_code_grant(form)
        elif grant_type == "refresh_token":
            return await self._handle_refresh_token_grant(form)
        else:
            self._logger.debug(
                "Token endpoint failed, unsupported grant type",
                grant_type=grant_type,
                client_id=client_id,
            )
            return JSONResponse(
                status_code=400,
                content={"error": "unsupported_grant_type"},
            )

    async def _handle_authorization_code_grant(self, form: FormData) -> JSONResponse:
        """Handle authorization_code grant type."""
        code = form.get("code")
        redirect_uri = form.get("redirect_uri")
        client_id = form.get("client_id")
        code_verifier = form.get("code_verifier")

        self._logger.debug("Processing authorization code grant", client_id=client_id)

        # Ensure code is a string (not UploadFile)
        if not isinstance(code, str):
            self._logger.debug(
                "Authorization code grant failed: code must be a string",
                client_id=client_id,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_request",
                    "error_description": "code must be a string",
                },
            )

        # Retrieve and validate authorization code
        auth_code = self._token_store.get_auth_code(code)
        if not auth_code:
            self._logger.debug(
                "Authorization code grant failed: code not found", client_id=client_id
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_grant",
                    "error_description": "Code not found",
                },
            )

        # Check expiration (10 minute timeout)
        if datetime.now(timezone.utc) - auth_code.created_at > timedelta(minutes=10):
            self._token_store.delete_auth_code(code)
            self._logger.debug(
                "Authorization code grant failed: code expired", client_id=client_id
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_grant",
                    "error_description": "Code expired",
                },
            )

        # Verify PKCE
        if not isinstance(code_verifier, str) or not self._auth_manager.verify_pkce(
            code_verifier, auth_code.code_challenge
        ):
            self._logger.debug(
                "Authorization code grant failed: PKCE verification failed",
                client_id=client_id,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_grant",
                    "error_description": "PKCE verification failed",
                },
            )

        # Validate client_id and redirect_uri match
        if auth_code.client_id != client_id:
            self._logger.debug(
                "Authorization code grant failed: client_id mismatch",
                expected=auth_code.client_id,
                got=client_id,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_grant",
                    "error_description": "client_id mismatch",
                },
            )
        if auth_code.redirect_uri != redirect_uri:
            self._logger.debug(
                "Authorization code grant failed: redirect_uri mismatch",
                client_id=client_id,
                expected=auth_code.redirect_uri,
                got=redirect_uri,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_grant",
                    "error_description": "redirect_uri mismatch",
                },
            )

        # Consume the authorization code (one-time use)
        self._token_store.delete_auth_code(code)

        # Issue our access token
        access_token = f"mcp_template_py_{self._auth_manager.generate_token()}"
        refresh_token = f"mcp_template_py_refresh_{self._auth_manager.generate_token()}"
        expires_in = 3600  # 1 hour

        self._token_store.store_access_token(
            AccessToken(
                external_tokens=auth_code.external_tokens,
                client_id=auth_code.client_id,
                scope=auth_code.scope,
                refresh_token=refresh_token,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            ),
            token=access_token,
        )

        self._logger.info(
            "Authorization code grant successful: issued access token",
            client_id=client_id,
        )
        return JSONResponse(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": expires_in,
                "refresh_token": refresh_token,
                "scope": auth_code.scope,
            }
        )

    async def _handle_refresh_token_grant(self, form: FormData) -> JSONResponse:
        """Handle refresh_token grant type."""
        refresh_token = form.get("refresh_token")

        self._logger.debug("Refresh token grant: processing request")

        # Validate refresh_token is a string
        if not isinstance(refresh_token, str):
            self._logger.debug(
                "Refresh token grant failed: refresh_token must be a string"
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_request",
                    "error_description": "refresh_token must be a string",
                },
            )

        # Find the token entry with this refresh token
        result = self._token_store.get_access_token_by_refresh_token(refresh_token)

        if not result:
            self._logger.debug("Refresh token grant failed: refresh token not found")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_grant",
                    "error_description": "Refresh token not found",
                },
            )

        old_access_token, token_entry = result
        client_id = token_entry.client_id
        self._logger.debug(
            "Refresh token grant: found token entry", client_id=client_id
        )

        # Refresh external tokens if we have an external refresh token
        external_tokens = token_entry.external_tokens
        if external_tokens.refresh_token:
            try:
                self._logger.debug(
                    "Refresh token grant: refreshing external tokens",
                    client_id=client_id,
                )
                new_external_tokens_dict = (
                    await self._auth_manager.refresh_external_token(
                        external_tokens.refresh_token
                    )
                )
                # Preserve the refresh token if external provider doesn't return a new one
                if "refresh_token" not in new_external_tokens_dict:
                    new_external_tokens_dict["refresh_token"] = (
                        external_tokens.refresh_token
                    )
                external_tokens = ExternalTokens(**new_external_tokens_dict)
            except httpx.HTTPStatusError as e:
                self._logger.warning(
                    "Refresh token grant failed: external provider returned error status",
                    client_id=client_id,
                    status_code=e.response.status_code,
                    error=str(e),
                )
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "invalid_grant",
                        "error_description": "External token refresh failed",
                    },
                )
            except httpx.HTTPError as e:
                self._logger.exception(
                    "Refresh token grant failed: network error during external refresh",
                    client_id=client_id,
                    error=str(e),
                )
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "server_error",
                        "error_description": "Network error contacting external provider",
                    },
                )

        # Remove old token
        self._token_store.revoke_access_token(old_access_token)

        # Issue new tokens
        new_access_token = f"mcp_template_py_{self._auth_manager.generate_token()}"
        new_refresh_token = (
            f"mcp_template_py_refresh_{self._auth_manager.generate_token()}"
        )
        expires_in = 3600

        self._token_store.store_access_token(
            AccessToken(
                external_tokens=external_tokens,
                client_id=client_id,
                scope=token_entry.scope,
                refresh_token=new_refresh_token,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            ),
            token=new_access_token,
        )

        self._logger.info(
            "Refresh token grant successful: issued new access token",
            client_id=client_id,
        )
        return JSONResponse(
            {
                "access_token": new_access_token,
                "token_type": "Bearer",
                "expires_in": expires_in,
                "refresh_token": new_refresh_token,
                "scope": token_entry.scope,
            }
        )
