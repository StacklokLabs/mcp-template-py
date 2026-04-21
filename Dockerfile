# Multi-stage Dockerfile for MCP Template Server (Python).
#
# Uses DHI (Docker Hardened Images) for both build and runtime:
#   - dhi.io/python:3.13-alpine3.23-dev (build — includes shell, pip & build tools)
#   - dhi.io/python:3.13-alpine3.23     (runtime — non-root by default, no shell)
#
# Alpine 3.23 chosen for zero known CVEs (Debian variants carry
# CVE-2025-69720 in ncurses with no upstream fix).
#
# DHI images require authentication: docker login dhi.io
# See https://docs.docker.com/dhi/how-to/use/ for details.

# ---------------------------------------------------------------------------
# Stage 1: Install dependencies into a virtual environment
# ---------------------------------------------------------------------------
FROM dhi.io/python:3.13-alpine3.23-dev@sha256:c13970a65d92df51053ffbc9fb2696b694078e0c8f3aa7e9de01e91d810c2de7 AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

COPY pyproject.toml uv.lock* README.md ./
COPY src/ ./src/
RUN uv sync --no-dev --frozen

# ---------------------------------------------------------------------------
# Stage 2: Production runtime — DHI Python (non-root by default)
# ---------------------------------------------------------------------------
FROM dhi.io/python:3.13-alpine3.23@sha256:904d8d2f5ccf6a2ebb63ca1c7a43aa0bafdeb03dae72f1174a82cc134bc530b0

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

EXPOSE 8100

CMD ["python", "-m", "mcp_template_py"]
