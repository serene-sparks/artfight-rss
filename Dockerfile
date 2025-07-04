FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml ./
COPY artfight_webhook/ ./artfight_webhook/
COPY config.example.toml ./
COPY env.example ./
COPY README.md ./

# Install dependencies
RUN uv sync --frozen

# Create cache directory
RUN mkdir -p cache

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uv", "run", "python", "-m", "artfight_webhook.main"] 