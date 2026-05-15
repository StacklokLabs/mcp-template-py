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

## Deployment

- `task run` runs the server locally.
- `task compose` builds and deploys via docker-compose.

## Code Structure
- The main module is located in `src/mcp_template_py/`.

## Implementation guidelines

- Use FastAPI for the API layer.
- Elicit feedback or confirmation when deciding to use a new framework or library.
- Integration tests live in `tests/integration/` and skip cleanly when configuration (e.g. API keys) is missing.
