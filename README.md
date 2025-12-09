# MCP Server Template (Python)

A production-ready template for building Python MCP (Model Context Protocol) servers using [FastMCP](https://github.com/jlowin/fastmcp).

## What's Included

- **FastMCP server** with example tool implementation
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

Tools are defined in [src/mcp_template_py/__main__.py](src/mcp_template_py/__main__.py) using the `@mcp.tool()` decorator:

```python
@mcp.tool()
async def hello(name: str) -> str:
    """Say hello to the user.

    Args:
        name: Name of the user
    Returns:
        Greeting message
    """
    return f"Hello, {name}!"
```

**Key points:**
- Tools are async functions decorated with `@mcp.tool()`
- Docstrings become tool descriptions for MCP clients
- Function parameters become tool arguments
- Use type hints for validation

For complex inputs/outputs, define Pydantic models in [src/mcp_template_py/models.py](src/mcp_template_py/models.py).

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
src/
├── mcp_template_py/
│   ├── __main__.py    # Server entry point - define tools here
│   └── models.py      # Pydantic models for tool arguments/results
└── tests/
    └── integration/
        └── test_mcp.py  # Integration tests for MCP tools
```

## Configuration

- **Environment variables**: Copy `.env.example` to `.env` and configure as needed
- **Debug mode**: Set `DEBUG=true` in `.env` for verbose logging
- **Server port**: Default is 8100, modify in `__main__.py`

## Testing

```bash
# Run all tests
task test

# Run with coverage
uv run pytest --cov=src/mcp_template_py
```

Integration tests connect to a running MCP server and verify tool functionality. They gracefully skip if the server is unavailable.

## License

See [LICENSE](LICENSE) for details.
