# MCP Server Template (Python)

A production-ready template for building Python MCP (Model Context Protocol) servers using [FastMCP](https://github.com/jlowin/fastmcp).

## What's Included

- **FastMCP server** with example tool implementation
- **Configurable OAuth 2.0 authentication** with PKCE support
- **Pydantic** for data validation and type safety
- **Task automation** via [Taskfile](https://taskfile.dev/) for common operations
- **Testing infrastructure** with pytest and pytest-asyncio
- **Code quality tools**: ruff (linting/formatting), ty (type checking)
- **Security scanning**: safety, bandit, pip-audit, cyclonedx-bom
- **Docker support** with multi-platform builds (amd64/arm64)
- **GitHub Actions** for CI/CD, code quality, and automated builds (release not included)

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- [Task](https://taskfile.dev/) (optional but recommended)

### Setup

```bash
# Install dependencies
task install

# Or without task:
uv sync --dev --all-packages --group security

# Copy .env (needed for `task compose` even if empty)
cp .env.example .env
```

### Run the Server

```bash
# Run locally
task run

# Or with Docker Compose
task compose
```

The server runs on `http://0.0.0.0:8100` by default.

## Implementing New Tools

Tools are implemented in [src/mcp_template_py/api/tools.py](src/mcp_template_py/api/tools.py) as methods on the `Tools` class, and registered in [src/mcp_template_py/api/mcp_builder.py](src/mcp_template_py/api/mcp_builder.py):

**1. Define request/response models in [src/mcp_template_py/api/models.py](src/mcp_template_py/api/models.py):**

```python
from pydantic import BaseModel, Field

class HelloRequest(BaseModel):
    name: str = Field(..., description="The name of the user making the request.")

class HelloResponse(BaseModel):
    result: str = Field(..., description="The greeting message.")
```

**2. Implement the tool in [src/mcp_template_py/api/tools.py](src/mcp_template_py/api/tools.py):**

```python
class Tools:
    async def hello(self, request: HelloRequest) -> HelloResponse:
        """Say hello to the user."""
        return HelloResponse(result=f"Hello, {request.name}!")
```

**3. Register the tool in [src/mcp_template_py/api/mcp_builder.py](src/mcp_template_py/api/mcp_builder.py):**

```python
tools = Tools()
mcp.add_tool(tools.hello)
```

**Key points:**
- Tools are async methods on the `Tools` class
- Docstrings become tool descriptions for MCP clients
- Use Pydantic models for type-safe input validation and output schemas
- Tools are registered via `mcp.add_tool()` in the MCP builder

## Task Commands

| Command | Description |
|---------|-------------|
| `task install` | Install all dependencies (dev + security) |
| `task run` | Run the MCP server locally |
| `task compose` | Start server with Docker Compose |
| `task lint` | Run ruff linter |
| `task format` | Format code and fix lint issues |
| `task typecheck` | Run ty type checker |
| `task test` | Run pytest tests |
| `task check` | Run all checks (lint, typecheck, test, security) |

## Project Structure

```
src/mcp_template_py/
├── __main__.py              # Server entry point
├── settings.py              # Configuration and environment variables
├── configure_logging.py     # Logging configuration
├── api/
│   ├── app_builder.py       # Starlette application factory
│   ├── mcp_builder.py       # FastMCP server builder
│   ├── oauth_api.py         # OAuth endpoint handlers
│   ├── tools.py             # MCP tool implementations
│   └── models.py            # Pydantic models for tools
└── auth/
    ├── auth_manager.py      # OAuth token management and PKCE
    ├── mcp_auth_middleware.py  # Authentication middleware
    └── token_store/
        ├── token_store.py   # Abstract token store interface
        ├── in_memory_token_store.py  # In-memory implementation
        └── models.py        # Token-related models

tests/
├── unit/                    # Unit tests with mocked dependencies
│   ├── auth/                # Auth module tests
│   └── test_settings.py     # Settings validation tests
└── integration/             # Integration tests (requires running server)
    ├── test_mcp.py          # MCP tool tests
    └── test_oauth_flow.py   # OAuth flow tests
```

## Configuration

Configuration is managed through environment variables. Copy `.env.example` to `.env` and configure as needed.

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug logging |
| `MCP_HOST` | `0.0.0.0` | Host for the MCP server to listen on |
| `MCP_PORT` | `8100` | Port for the MCP server to listen on |
| `SERVER_URL` | `http://localhost:8100` | Base URL of the server (used for OAuth callbacks) |

### OAuth Configuration

OAuth is disabled by default. To enable authentication:

1. Set `ENABLE_OAUTH=true`
2. Configure your OAuth provider credentials

| Variable | Required | Description |
|----------|----------|-------------|
| `ENABLE_OAUTH` | No | Enable OAuth authentication (`true`/`false`) |
| `OAUTH_CLIENT_ID` | When OAuth enabled | OAuth client ID from your provider |
| `OAUTH_CLIENT_SECRET` | When OAuth enabled | OAuth client secret from your provider |
| `OAUTH_EXTERNAL_AUTH_URL` | When OAuth enabled | Authorization endpoint URL (e.g., `https://accounts.google.com/o/oauth2/v2/auth`) |
| `OAUTH_EXTERNAL_TOKEN_URL` | When OAuth enabled | Token exchange endpoint URL (e.g., `https://oauth2.googleapis.com/token`) |
| `OAUTH_EXTERNAL_SCOPES` | No | Comma-separated list of OAuth scopes |

#### Example: Google OAuth Configuration

```bash
ENABLE_OAUTH=true
OAUTH_CLIENT_ID="your-client-id.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET="your-client-secret"
OAUTH_EXTERNAL_AUTH_URL="https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_EXTERNAL_TOKEN_URL="https://oauth2.googleapis.com/token"
OAUTH_EXTERNAL_SCOPES="openid,email,profile"
```

#### OAuth Endpoints

When OAuth is enabled, the server exposes the following endpoints:

| Endpoint | Description |
|----------|-------------|
| `/.well-known/oauth-authorization-server` | OAuth server metadata |
| `/oauth/register` | Dynamic client registration (POST) |
| `/oauth/authorize` | Authorization endpoint (GET) |
| `/oauth/callback` | OAuth callback handler (GET) |
| `/oauth/token` | Token exchange endpoint (POST) |

#### Disabling OAuth

To run the server without authentication (development mode):

```bash
ENABLE_OAUTH=false
# OAuth credentials are not required when disabled
```

## Testing

**Note**: Integration tests (`tests/integration/`) require the MCP server to be running (`task run` or `task compose`) and will be skipped if unreachable.

```bash
# Run all tests
task test

# Run with coverage
uv run pytest --cov=src/mcp_template_py
```

## License

See [LICENSE](LICENSE) for details.
