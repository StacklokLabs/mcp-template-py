# Build stage: use uv to install dependencies into a virtual environment
# uv is not included in the final runtime image, mitigating CVE-2026-31812
# (quinn-proto DoS in uv's QUIC transport layer)
FROM python:3.13-slim-trixie AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Install uv from Astral's GitHub Container Registry
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

# Copy project files and install dependencies into the venv
COPY pyproject.toml uv.lock* README.md ./
COPY src/ ./src/
RUN uv sync --no-dev --frozen

# Runtime stage: plain Python image with no uv binary
FROM python:3.13-slim-trixie

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Copy the installed virtual environment and source from the builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /usr/sbin/nologin --create-home appuser && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8100

# Run the application directly with Python (no uv at runtime)
CMD ["python", "-m", "mcp_template_py"]
