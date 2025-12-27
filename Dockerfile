FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files and README (required by hatchling)
COPY pyproject.toml .
COPY uv.lock* .
COPY README.md .
COPY app/ app/

# Install dependencies
RUN uv sync --frozen --no-dev

# Create data directory
RUN mkdir -p data

# Expose port
EXPOSE 8080

# Run the application
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
