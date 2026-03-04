# Use official Python runtime as base image
FROM python:3.13-slim-trixie

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Install uv from Astral's GitHub Container Registry
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy project files
COPY pyproject.toml .
COPY uv.lock* ./
COPY README.md .
COPY src/ ./src/

# Install dependencies using uv
RUN uv sync --no-dev

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /usr/sbin/nologin --create-home appuser && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8100

# Run the application (--no-sync since deps are already installed)
CMD ["uv", "run", "--no-sync", "-m", "src.mcp_template_py"]
