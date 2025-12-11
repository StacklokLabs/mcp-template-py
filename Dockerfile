# Use official Python runtime as base image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Install uv from Astral's GitHub Container Registry
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy project files
COPY pyproject.toml .
COPY uv.lock* ./
COPY README.md .
COPY src/ ./src/

# Install dependencies using uv
RUN uv sync --no-dev

# Expose port
EXPOSE 8100

# Run the application
CMD ["uv", "run", "-m", "src.mcp_template_py"]