---
paths:
  - "**/tests/**/*.py"
  - "**/test_*.py"
  - "**/*_test.py"
description: Test quality rubric — 11 rules reviewers apply to judge test design and assertion strength.
---

# Test Quality Rubric

Rubric used by reviewers (human or agent) to evaluate a PR's tests. Change a rule here and every consumer picks it up.

## Principles

When a rule outcome feels ambiguous, return to these:

1. **Tests must be easy to read and trust.** A reviewer should skim a test and see what user-visible behavior is verified and why the assertion proves it. Tests are documentation that compiles.
2. **Tests must validate behavior users care about** — MCP tool call, HTTP request, public API. Coverage of internal state creates false confidence: green tests while real behavior breaks.
3. **Tests must be a safety net for refactors.** If a behavior-preserving refactor forces tests to change, the tests were coupled to implementation, not behavior.

**Findings are conversation starters, not vetoes.** A `blocker:` flags a risk for explicit discussion. The author can defend the choice, the reviewer can approve through it, or both can agree to close the gap. What's NOT valid is silently letting the risk slide.

## Outcomes & severity

- `✅` passes / `❌` fails (Finding) / `—` not applicable (justify briefly).
- `blocker:` must resolve before merge / `suggestion:` non-blocking / `question:` clarification. **No nitpicks** — drop purely stylistic concerns.

## The 11 rules

### Rule 1 — Behavior over internal state
Does the test exercise the way users invoke the code (MCP tool, HTTP, public function) and assert an observable outcome (return value, raised exception, written file, recorded event)? Asserting on internal dataclass shape, private function calls, or pure helpers whose output never reaches a public site does NOT count.
- **❌ when:** behavior-affecting code ships without a test that exercises the public surface.
- **Severity:** `blocker:`. Downgrade to `suggestion:` only for explicit refactors where existing tests still exercise the renamed path.

### Rule 2 — Right surface
Place each test at the right tier — unit (pure function), integration (real I/O against fixtures), or end-to-end (real FastAPI app / MCP server entry point). A new MCP tool or HTTP route needs an end-to-end test, not just unit tests of helpers.
- **❌ when:** tested at the wrong tier.
- **Severity:** `suggestion:`, or `blocker:` if the user-visible path is never exercised.

### Rule 3 — Fixture economy
Does the PR add a new top-level fixture when an existing one would serve? Reuse via `conftest.py`.
- **❌ when:** the new fixture mostly duplicates an existing one.
- **Severity:** `blocker:`. Cleared by parametrizing under the existing fixture, or naming a concrete divergence that requires separation.

### Rule 4 — Framework helper reuse
Hand-rolling polling, HTTP mocking, or assertions when a helper exists in `conftest.py` / `tests/helpers/` is how subtle test bugs ship — wrong sentinel, missing retry, off-by-one.
- **❌ when:** a helper exists for the work being done by hand.
- **Severity:** `blocker:`.

### Rule 5 — Implementation-detail coupling
Does the test reach into `pkg._internal`, `obj._cache`, or generated artifacts when an external observable would suffice?
- **❌ when:** an external observable would work and the test reaches inward.
- **Severity:** `blocker:`. Coupling makes tests brittle and quietly wrong — implementation refactored, test still passes against stale internal state.

### Rule 6 — Assertion strength

| Tier | Pattern | Verdict |
|---|---|---|
| 1 | `print(...)`, `caplog.records` without assertion | Not a test. ❌ blocker. |
| 2 | `assert x`, `is not None`, `len(x)` | Weak. Allowed only with a comment naming why exact comparison is impossible (UUIDs, timestamps). |
| 3 | `assert "needle" in haystack` | Acceptable for non-deterministic parts. |
| 4 | `assert x == expected` | Preferred. |
| 5 | Boundary on numeric rule (`assert got_429_at <= 6`) | Preferred for thresholds. |

- **❌ when:** log-only, or `assert x` / `is not None` on values that could be exact-compared.
- **Severity:** `blocker:`. Tier 1–2 silently pass when behavior breaks — worse than no test.

### Rule 7 — Boundary assertions on numeric rules
For rate limits, retry counts, timeouts: assert "got the limit at request N" (boundary) — not "got it eventually" (poll until success). Eventually-assertions don't prove the limit is enforced at the right threshold.
- **❌ when:** numeric enforcement is asserted with a poll-until-success pattern.
- **Severity:** `blocker:` when the numeric rule IS the change under test.

### Rule 8 — Comment-instead-of-test
`# IMPORTANT:` / `# WARNING:` / `# DO NOT` / `# SECURITY:` / `# MUST:` comments without a test exercising the invariant. Prose-asserted invariants rot.
- **❌ when:** such a comment is added with no guarding test.
- **Severity:** `blocker:` for fail-closed / security-critical / data-integrity invariants. `suggestion:` otherwise.

### Rule 9 — Test deletion / weakening
Deleted tests, `@pytest.mark.skip`, `xfail`, or softened assertions (`==` → `in`, exact value → `pytest.approx`) without a documented contract change.
- **Scope:** every test file in the diff, not just tests for the headline claim.
- **❌ when:** unjustified.
- **Severity:** `blocker:`.

### Rule 10 — Determinism signals
Tests read deterministically. Polling / sleeps / retries belong in named helpers whose name describes the wait condition.
- **❌ when:** raw `time.sleep`, inline polling loops, or hard-coded timing constants in the test body. Also when a helper exists but has a generic name like `wait()` callers can't reason about.
- **Severity:** `blocker:`. Cleared by extracting to a helper named for the wait condition (`poll_until_status_ready`, not `wait_500ms`).

### Rule 11 — Type-checked tests
Tests run through `ty`. Fixtures have return types. Mocks use `Mock(spec=Foo)` / `AsyncMock(spec=Foo)` so attribute typos fail at construction. No `Any`, no untyped fixture parameters.
- **❌ when:** the test file fails type checking, a fixture/test has untyped parameters or return type, or `Mock()` is constructed without `spec=`.
- **Severity:** `suggestion:` for missing return types on individual test functions; `blocker:` when the file fails type checking or constructs unspecced Mocks for the unit under test.
