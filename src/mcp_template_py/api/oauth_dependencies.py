"""FastAPI dependency injection providers for OAuth endpoints."""

from contextvars import ContextVar
from typing import Annotated

from fastapi import Depends

from mcp_template_py.auth.auth_manager import AuthManager
from mcp_template_py.auth.token_store import TokenStore
from mcp_template_py.settings import Settings

# Context variables for app-level singletons
# These are set once during app initialization and accessed via dependencies
_token_store: ContextVar[TokenStore | None] = ContextVar("_token_store", default=None)
_auth_manager: ContextVar[AuthManager | None] = ContextVar(
    "_auth_manager", default=None
)
_settings: ContextVar[Settings | None] = ContextVar("_settings", default=None)


def get_token_store() -> TokenStore:
    """Get the TokenStore instance from context.

    Raises:
        RuntimeError: If TokenStore has not been initialized.
    """
    store = _token_store.get()
    if store is None:
        raise RuntimeError("TokenStore not initialized")
    return store


def get_auth_manager() -> AuthManager:
    """Get the AuthManager instance from context.

    Raises:
        RuntimeError: If AuthManager has not been initialized.
    """
    manager = _auth_manager.get()
    if manager is None:
        raise RuntimeError("AuthManager not initialized")
    return manager


def get_settings() -> Settings:
    """Get the Settings instance from context.

    Raises:
        RuntimeError: If Settings has not been initialized.
    """
    settings = _settings.get()
    if settings is None:
        raise RuntimeError("Settings not initialized")
    return settings


# Type aliases for cleaner endpoint signatures
TokenStoreDep = Annotated[TokenStore, Depends(get_token_store)]
AuthManagerDep = Annotated[AuthManager, Depends(get_auth_manager)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


# Setter functions for app initialization
def set_token_store(store: TokenStore) -> None:
    """Set the TokenStore instance in context."""
    _token_store.set(store)


def set_auth_manager(manager: AuthManager) -> None:
    """Set the AuthManager instance in context."""
    _auth_manager.set(manager)


def set_settings(settings: Settings) -> None:
    """Set the Settings instance in context."""
    _settings.set(settings)
