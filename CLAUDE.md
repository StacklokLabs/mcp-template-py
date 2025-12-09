## Project

A python MCP server template repository.

## Technical considerations
- Use uv as package manager. `uv add <package>` for adding a package. `uv add <package> --dev` for development packages for linting and testing
- Use the taskfile for running linting and formatting
    - `task format` for running formatters
    - `task lint` for running linters
    - `task typecheck` for running typecheckers
    - `task test` for running tests
- Use the taskfile for deployment
    - `task run_agent` for running the agent locally
    - `task compose_agent_local` for building and deploying the agent using docker-compose
- Use `pydantic` for validating structured data
- pyproject.toml should be the central place for configuring the project, i.e. linters, typecheckers, testing, etc
- Always prefer to use native Python types over custom types, e.g. use `list` instead of `List`, `dict` instead of `Dict`, etc.
- Prefer using `uv run python -c "import this"` instead of `python -c "import this"`. This ensures that the correct python version and environment is used.

## Code Structure
- The main module is located in `src/mcp_template_py/`.

## Implementation guidelines

### Product code
- Use pydantic models for type safety, especially at API boundaries.
- Use FastAPI for the API layer.
- Elicit feedback or confirmation when deciding to use a new framework or library.

### Test code
- Use pytest style tests, leveraging pytest-asyncio when appropriate.
- Unit tests should be in a `tests/` folder co-located with the source code being tested. Unit tests should mock external dependencies.
- Integration tests should be in `src/tests/integration` and should avoid mocking external dependencies. They can be skipped if requirements like configuration (e.g. API keys) are missing.
