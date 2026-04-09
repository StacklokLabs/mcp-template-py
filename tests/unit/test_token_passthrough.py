import pytest
from typing import Any, cast

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_template_py.auth import TokenPassthroughMiddleware, get_bearer_token


async def echo_token(request: Request) -> JSONResponse:
    """Test endpoint that returns the current bearer token."""
    return JSONResponse({"token": get_bearer_token()})


async def raise_error(request: Request) -> JSONResponse:
    """Test endpoint that raises an exception."""
    raise RuntimeError("handler error")


@pytest.fixture
def client() -> TestClient:
    app = Starlette(
        routes=[
            Route("/test", echo_token),
            Route("/error", raise_error),
        ],
        middleware=[Middleware(cast(Any, TokenPassthroughMiddleware))],
    )
    return TestClient(app, raise_server_exceptions=False)


class TestTokenPassthrough:
    def test_bearer_token_extracted(self, client: TestClient):
        response = client.get("/test", headers={"Authorization": "Bearer my-token-123"})
        assert response.status_code == 200
        assert response.json()["token"] == "my-token-123"

    def test_no_auth_header_returns_none(self, client: TestClient):
        response = client.get("/test")
        assert response.status_code == 200
        assert response.json()["token"] is None

    def test_non_bearer_auth_returns_none(self, client: TestClient):
        response = client.get("/test", headers={"Authorization": "Basic abc123"})
        assert response.status_code == 200
        assert response.json()["token"] is None

    def test_empty_bearer_returns_none(self, client: TestClient):
        response = client.get("/test", headers={"Authorization": "Bearer "})
        assert response.status_code == 200
        assert response.json()["token"] is None

    def test_context_reset_after_handler_exception(self, client: TestClient):
        """Verify context variable is cleaned up even when the handler raises."""
        client.get("/error", headers={"Authorization": "Bearer leaked-token"})
        assert get_bearer_token() is None
