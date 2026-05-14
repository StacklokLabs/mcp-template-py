---
paths:
  - "**/*.py"
description: Python tooling, logging, naming, error handling, FastAPI/MCP patterns. Type-strictness rules live in python-types.md.
---

# Python Style

PEP 8 / 257 / 484 with the deltas below.

## Tooling

- **`uv` only.** `uv add` (or `uv add --dev`), `uv run`, `uv sync`. Never pip/poetry/conda.
- **`ty` for typecheck, `ruff` for lint+format.** Never mypy/black/isort/flake8.
- **Taskfile is the entry point.** `task lint` / `format` / `typecheck` / `test` / `security`. `task check` runs all of them.
- **`requires-python = ">=3.13"`.** Use 3.13 features without back-compat hedging.
- **`uv run python -c "..."`** over bare `python` to stay in the project venv.

## Logging

- **`structlog`, not stdlib `logging`.** `log = structlog.get_logger()`.
- Events are short snake_case names; data goes in kwargs:
  `log.info("tool_called", tool=name, user=user_id, duration_ms=elapsed)` — not f-strings.
- Silent on success. Log at state transitions or unexpected events. Never log secrets/PII.
- Logger configuration lives in `configure_logging.py`, not library modules.

## Naming

- `snake_case` functions/vars/modules, `PascalCase` classes/models, `UPPER_SNAKE_CASE` constants.
- Leading `_` = module-private; don't import `_name` from outside its module.
- Native types: `list[str]` not `List[str]`, `X | None` not `Optional[X]`.

## `__init__.py`

Default empty. Re-export only when defining a deliberate package surface — and declare `__all__` explicitly when you do.

## Docstrings

Every function and method. PEP 257. One-liner for trivial getters; multi-line when there's more than one parameter or non-obvious behavior. Class docstrings name the invariant or contract, not the contents. Test functions are exempt — the test name is the docstring.

## Error handling

- No bare `except:` or `except BaseException:`. Catch the narrowest type that means something.
- Never silently swallow. Either log at WARNING with `exc_info=True` and comment why continuing is safe, or use `contextlib.suppress(SpecificError)` for genuinely-anticipated no-action exceptions.
- Define a small per-package exception hierarchy (`McpTemplateError` → narrower subclasses). No bare `Exception` / `RuntimeError`.
- Cross module boundaries with `raise NewError(...) from err`.
- **Never put secrets, tokens, or PII in exception messages** — they end up in logs and tracebacks.

## I/O

- Accept collaborators (HTTP client, clock, subprocess) as parameters. No module-level `httpx.get` from business logic.
- `pathlib.Path` not `os.path`. `subprocess.run(..., check=True, text=True)`, no `shell=True`.
- `httpx.AsyncClient` for HTTP in async — never `requests` (blocks the event loop).

## Imports

- stdlib / third-party / first-party, blank-line separated. ruff's `I` rule enforces it.
- Absolute imports inside the package; relative imports max one level deep. No wildcards.
- `from __future__ import annotations` at the top of every module.

## Function signatures

- Type every parameter and return value — see `python-types.md`.
- Keyword-only for booleans and any function with >3 parameters: `def foo(*, debug: bool = False) -> None`.
- Default values must be immutable. No `def f(items: list[str] = [])`.

## FastAPI

- Pydantic models for every request/response body. Never `dict` or `Any` — the OpenAPI schema is part of the contract.
- Dependencies via `Depends(...)`. `app.dependency_overrides[real] = fake` is the test seam.
- Explicit status codes (`status_code=201`); errors raise `HTTPException` with a specific code.
- Async handlers unless the work is genuinely CPU-bound — a sync handler in an async app blocks the worker.

## MCP server

- **Tool functions are thin.** Validate input via Pydantic, call into the service layer, return a typed response. No business logic.
- **Tool docstrings are part of the API** — the MCP client surfaces them to users and LLMs. Name inputs, output shape, side effects.
- **Auth lives in `src/mcp_template_py/auth/`.** Never inline auth checks in tool functions.
- **Settings via `pydantic-settings`** in `settings.py`, loaded once, injected via `Depends`. No scattered `os.environ.get`.

## Security

- No credentials in code, tests, or committed config. `.env.example` for the schema, `.env` (gitignored) for real values.
- `task security` (bandit + pip-audit) must pass. Suppress a bandit finding only with `# nosec B<id>  # <reason>` naming the specific reason.
