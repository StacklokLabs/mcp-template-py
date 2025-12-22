"""FastAPI dependency injection providers for OAuth endpoints."""

from typing import Annotated

from fastapi import Depends, Request

from mcp_template_py.auth.auth_manager import AuthManager
from mcp_template_py.auth.token_store import TokenStore
from mcp_template_py.settings import Settings


def get_token_store(request: Request) -> TokenStore:
    """Get the TokenStore instance from app state.

    Args:
        request: FastAPI request object containing app state.

    Returns:
        TokenStore instance from app state.

    Raises:
        RuntimeError: If TokenStore has not been initialized in app state.
    """
    if not hasattr(request.app.state, "token_store"):
        raise RuntimeError("TokenStore not initialized in app state")
    return request.app.state.token_store


def get_auth_manager(request: Request) -> AuthManager:
    """Get the AuthManager instance from app state.

    Args:
        request: FastAPI request object containing app state.

    Returns:
        AuthManager instance from app state.

    Raises:
        RuntimeError: If AuthManager has not been initialized in app state.
    """
    if not hasattr(request.app.state, "auth_manager"):
        raise RuntimeError("AuthManager not initialized in app state")
    return request.app.state.auth_manager


def get_settings(request: Request) -> Settings:
    """Get the Settings instance from app state.

    Args:
        request: FastAPI request object containing app state.

    Returns:
        Settings instance from app state.

    Raises:
        RuntimeError: If Settings has not been initialized in app state.
    """
    if not hasattr(request.app.state, "settings"):
        raise RuntimeError("Settings not initialized in app state")
    return request.app.state.settings


# Type aliases for cleaner endpoint signatures
TokenStoreDep = Annotated[TokenStore, Depends(get_token_store)]
AuthManagerDep = Annotated[AuthManager, Depends(get_auth_manager)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
