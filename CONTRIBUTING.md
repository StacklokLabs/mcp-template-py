# Contributing to mcp-template-py

Thanks for your interest! This repo is a template — most contributions will be improvements to the template itself (new MCP tooling patterns, better docs, CI/CD hardening).

## Development setup

```bash
# Prerequisites: Python 3.13+, uv, Task (see README)
task install
cp .env.example .env
task run
```

## Before opening a PR

Run the full check suite locally. It mirrors CI:

```bash
task check      # lint + format + typecheck + test + security
```

Individual tasks are listed in `README.md`. All of them must pass before CI will.

## PR conventions

- **Title format:** [Conventional Commits](https://www.conventionalcommits.org/) — enforced by `lint-pr-title.yml`. Examples:
  - `feat(tools): add a rate-limited search tool`
  - `fix(auth): handle missing Bearer token header`
  - `docs: clarify DHI setup`
  - `chore: bump dependencies`
- **Scope:** keep PRs focused. Smaller PRs review faster.
- **Tests:** unit tests in `tests/unit/` (alongside the module), integration tests in `tests/integration/`.

## Developer Certificate of Origin (DCO)

All commits must be signed off, certifying that you have the right to submit the contribution:

```bash
git commit -s -m "your message"
```

The `-s` flag appends a `Signed-off-by` trailer. See the [DCO](https://developercertificate.org/) for the full text.

## Reporting issues

- **Bugs / feature requests:** open an issue.
- **Security vulnerabilities:** see [SECURITY.md](SECURITY.md) — do not file a public issue.

## Code of Conduct

By participating in this project, you agree to abide by the [StacklokLabs Code of Conduct](https://github.com/StacklokLabs/.github/blob/main/CODE_OF_CONDUCT.md).
