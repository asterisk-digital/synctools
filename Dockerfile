FROM python:3.11-slim

# Install uv (fast Python installer)
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy project files
COPY pyproject.toml /app/
COPY src/ /app/src/

# Create venv and install dependencies
RUN uv venv \
 && . .venv/bin/activate \
 && uv pip install --no-cache-dir .

# Make sure the venv is used by default
ENV PATH="/app/.venv/bin:${PATH}"

# Run via console script
CMD ["./.venv/bin/python", "-m", "python_template"]
