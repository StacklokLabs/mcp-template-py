## Project

A python MCP server template repository.

## Rules index

Detailed conventions live in `.claude/rules/` and auto-load when you
touch matching files. The summary below points at the source of truth:

- `.claude/rules/python-style.md` — tooling (`uv`, `ruff`, `ty`),
  structlog logging, naming, docstrings, error handling, FastAPI and
  MCP patterns. Loads for `**/*.py`.
- `.claude/rules/python-types.md` — strict typing: no `Any`, no
  untyped dicts, decision tree for `Pydantic` / `TypedDict` /
  `dataclass`, boundary parsing, `str Enum` for discriminators. Loads
  for `**/*.py`.
- `.claude/rules/python-testing.md` — pytest layout, fixtures,
  parametrize, mock-at-I/O-only, no-network-in-unit-tests, async,
  FastAPI/MCP test patterns. Loads for test files.
- `.claude/rules/test-quality.md` — 11-rule rubric used by code
  reviewers (human and agent) to evaluate test design. Loads for
  test files.

When the rules below conflict with anything in `.claude/rules/`, the
rule file wins.

## Technical considerations
- Use uv as package manager. `uv add <package>` for adding a package. `uv add <package> --dev` for development packages for linting and testing
- Use the taskfile for running linting and formatting
    - `task format` for running formatters
    - `task lint` for running linters
    - `task typecheck` for running typecheckers
    - `task test` for running tests
    - `task security` for running security checks
- Use the taskfile for deployment
    - `task run` for running the server locally
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
- Integration tests should be in `tests/integration` and should avoid mocking external dependencies. They can be skipped if requirements like configuration (e.g. API keys) are missing.
