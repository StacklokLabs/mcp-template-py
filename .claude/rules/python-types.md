---
paths:
  - "**/*.py"
description: Strict typing — no Any, no untyped dicts, decision tree for TypedDict/dataclass/Pydantic, boundary parsing, str Enum for discriminators.
---

# Python Type Strictness

The goal: any signature you read tells you exactly what flows through it. Untyped dicts and `Any` defeat that. **Strict by default.**

## Hard rules

1. **Every parameter and return value is typed.** No exceptions.
2. **No `Any` unless there's no other option.** When you use one, comment on the same line: `# any: <reason>`. Treat it like `# noqa` — admissible, but visible.
3. **No untyped `dict` / `list` / `tuple` / `set`.** `dict[str, int]` is fine; `dict` or `dict[str, Any]` is not — use `TypedDict`, `dataclass`, or `BaseModel`.
4. **No `**kwargs: Any` or `*args: Any`.** If a signature is that variadic, split it or accept a typed `TypedDict`.
5. **`task typecheck` clean is a merge gate.** A `# type: ignore[code]` requires a reason comment.
6. **No bare string literals for discriminators.** Use `str Enum` — see below.

## Decision tree

```
Does the value cross a process / network / disk boundary
(HTTP req/resp, MCP tool args, file IO, env vars, subprocess)?
├─ YES → pydantic.BaseModel with strict mode
└─ NO → Is it a JSON-shaped dict that has to stay a dict?
        (json.dumps target, or a library expecting a dict)
        ├─ YES → TypedDict
        └─ NO → @dataclass(frozen=True, slots=True)
```

### Pydantic for boundaries

Anything coming in from outside the process gets parsed at the boundary — same function that received the raw data. Downstream code never sees the raw shape.

```python
from pydantic import BaseModel, ConfigDict, Field

class ToolRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    name: str
    arguments: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float | None = None
```

`strict=True` rejects coerced values. `extra="forbid"` rejects unknown keys (typo → loud failure). Pydantic v2 only: `model_dump()` not `.dict()`, `model_validate()` not `parse_obj()`.

### TypedDict for typed JSON

Use when the value must stay a dict (json.dumps target, library API). `NotRequired[T]` per field for optional keys — never `total=False` (loses information).

### Frozen slotted dataclass for internal value objects

```python
@dataclass(frozen=True, slots=True)
class AuthContext:
    user_id: str
    scopes: frozenset[str]
    expires_at: float
```

`frozen` prevents mutation; `slots` saves memory and catches typo-attributes.

## Boundary parsing

I/O produces loose data (`json.loads` → `dict[str, object]`, env → `Mapping[str, str]`). That's fine **inside the boundary function**. Before the data crosses a function boundary, parse it into a typed model.

```python
# OK
async def fetch_user(user_id: str, client: httpx.AsyncClient) -> User:
    response = await client.get(f"/users/{user_id}")
    return User.model_validate(response.json())

# NOT OK — leaks dict[str, Any] up the stack
async def fetch_user(...) -> dict[str, Any]: ...
```

## Generics over `Any`

```python
# BAD: def first(items: list[Any]) -> Any
# GOOD (3.12+ syntax):
def first[T](items: list[T]) -> T: ...
```

`Any` says "stop checking"; `TypeVar` says "check the same thing flows through".

## `object` is preferable to `Any`

When you don't know the type and only pass it through, use `object`. The checker forces narrowing before use — usually what you wanted.

## Discriminated unions: `str Enum`, not bare `Literal` strings

When code dispatches on a closed set of strings, use a `str Enum`. **Never** scatter bare literals across call sites.

```python
# GOOD
class AuthMode(str, Enum):
    PASSTHROUGH = "passthrough"
    EXCHANGE = "exchange"

if config.auth_mode is AuthMode.PASSTHROUGH: ...
```

`Literal` is acceptable only for one-off self-documenting flags where nothing dispatches on the value (`direction: Literal["asc", "desc"]`). The moment code does `if x == "asc"` or `if x in (...)`, promote to `Enum`.

**Review signal**: a bare string compared against a `Literal`-typed field (`== "crash"`, `in ("a", "b")`) is a hard rule violation.

## Tests are typed too

Test files run through `ty`. Fixtures have return types. Mocks declare what they're mocking — `Mock(spec=Foo)` / `AsyncMock(spec=Foo)`. See `test-quality.md` Rule 11.

## Acceptable `Any` cases

Contained to one expression or one wrapper module:

- Between `json.loads` and a Pydantic model at the boundary.
- Decorators wrapping arbitrary callables (prefer `ParamSpec` + `TypeVar` first).
- Third-party libs with poor stubs — wrap them in a typed adapter that absorbs the `Any` once.

The moment `Any` spreads beyond that, it's the wrong tool.
