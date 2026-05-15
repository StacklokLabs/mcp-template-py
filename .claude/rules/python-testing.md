---
paths:
  - "**/tests/**/*.py"
  - "**/test_*.py"
description: Pytest patterns — layout, fixtures, mocking discipline, no-network rule, async. Quality rubric in test-quality.md. Style/tooling in python-style.md; typing rules in python-types.md.
---

# Python Testing

How to **write** a test. The rubric for evaluating one lives in `test-quality.md`.

## Layout

Tests mirror `src/<package_name>/`. Target layout (add directories as the suite grows):

```
tests/
  conftest.py      # top-level shared fixtures (add when needed)
  unit/            # fast, no network, no real I/O beyond tmp_path
  integration/     # real services; skips cleanly if config missing
  fixtures/        # recorded payloads, golden files (add when needed)
```

- `conftest.py` at every level that needs shared fixtures.
- One `test_<module>.py` per non-trivial source module.

## Pytest, not unittest

- No `unittest.TestCase` classes. Plain functions named `test_<what_it_proves>`.
- Group tests in a class only for shared fixture setup that doesn't fit a regular pytest fixture — organizational, not behavioral. No `setUp` / `tearDown`.

## Fixtures

- Yield-based for teardown:

  ```python
  @pytest.fixture
  def tmp_settings(tmp_path: Path) -> Iterator[Settings]:
      env_file = tmp_path / ".env"
      env_file.write_text("REQUIRE_BEARER_TOKEN=false\n")
      yield Settings(_env_file=env_file)
  ```

- Type fixture parameters and return types — `ty` checks them.
- Default `function` scope; widen only when genuinely expensive AND read-only.
- Don't accept fixtures you don't use.

## Parametrize over loops

```python
# BAD: for raw, expected in [...]: assert normalize(raw) == expected
@pytest.mark.parametrize("raw, expected", [("Open", Status.OPEN), ("DONE", Status.DONE)])
def test_normalize(raw: str, expected: Status) -> None:
    assert normalize(raw) == expected
```

Parametrized cases report each input separately. Loops collapse failures into one opaque assertion.

## `tmp_path` over `tempfile`

Use `tmp_path` / `tmp_path_factory`. Pytest cleans them up automatically. `tempfile.mkdtemp()` leaks dirs when teardown is skipped.

## Mock at I/O boundaries only

Mock the things logic talks to — HTTP, subprocess, clock, filesystem. Run the logic for real.

```python
# GOOD: real logic, fake collaborator
async def test_fetch_user_returns_normalized_record() -> None:
    fake = FakeHttpClient(responses={"/users/42": {"id": 42, "name": "Ada"}})
    user = await fetch_user("42", client=fake)
    assert user == User(id=42, name="Ada")

# BAD: mocked the unit under test → tests nothing
async def test_fetch_user() -> None:
    fetch = AsyncMock(return_value=User(id=42))
```

When you do use `unittest.mock`, declare the spec: `Mock(spec=Foo)` / `AsyncMock(spec=Foo)`. Bare `Mock()` accepts any attribute and swallows typos.

## No network in unit tests

Unit tests run offline. Record fixtures in `tests/fixtures/<source>/<scenario>.json`; inject via a fake adapter. For httpx, `respx` is acceptable when DI isn't an option.

Integration tests live in `tests/integration/` and skip cleanly when config is missing (`pytest.skip("MCP_API_KEY not set")`).

## Async tests

- `asyncio_mode = "auto"` is set — `async def test_...` just works, no decorator needed.
- Async fixtures are `async def`. Use `AsyncMock(spec=Foo)` for async collaborators.
- Don't mix sync and async assertions in the same test.
- `asyncio_default_fixture_loop_scope = "function"` is set in `pyproject.toml`. If you widen an async fixture's scope (`scope="module"` / `"session"`), match it with `loop_scope=...` on the fixture or you'll hit `Future attached to a different loop` at runtime.

## FastAPI tests

- `fastapi.testclient.TestClient` for sync style, `httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")` for async (httpx 0.28 removed the `app=` shortcut).
- Override deps in a fixture: `app.dependency_overrides[real] = fake`; clear on teardown.
- Assert status code AND body shape — a 200-with-error-envelope passes a status-only assertion.

## MCP tests

- Test tool functions directly when the logic is pure — they're just Python functions.
- For end-to-end MCP behavior, use the in-memory transport (`mcp.shared.memory`) — no socket needed.
- Tool docstrings are part of the contract. Assert on them when a tool is renamed/reshaped.

## Determinism

- No `time.sleep` in test bodies. Waits belong in named helpers (`wait_until_status_open(...)`) that describe what they're waiting for.
- Inject the clock — code that calls `time.time()` / `datetime.now()` accepts a callable defaulting to the real one. Or `freezegun` for module-level control.
- Seed random generators in fixtures.

## Coverage

The repo runs `pytest --cov` by default. Coverage is a diagnostic, not a target. A 98% suite that mocks the unit under test is worse than 70% that proves behavior. Don't add `# pragma: no cover` to hit a number.
