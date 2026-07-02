# ---- Stage 1: builder ----
FROM python:3.11-slim AS builder

ENV POETRY_VERSION=2.2.1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

WORKDIR /app

# Install dependencies first (layer cache)
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

# ---- Stage 2: runtime ----
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy the virtualenv from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Activate the virtualenv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="src" \
    PYTHONUNBUFFERED=1

# Copy application code and assets
COPY src/ src/
COPY assets/ assets/
COPY config/ config/
COPY pyproject.toml README.md ./

# Install the package itself (for the chaos-engine entry point)
RUN pip install --no-cache-dir --no-deps .

# Externalized configuration — API keys injected at runtime via env_file/.env
ENV ENVIRONMENT="production" \
    MOCK_MODE="true"

# Non-root user for production
RUN groupadd --gid 1000 chaos && \
    useradd --uid 1000 --gid chaos --shell /bin/sh chaos && \
    mkdir -p reports && chown chaos:chaos reports

USER chaos

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

ENTRYPOINT ["chaos-engine"]
CMD ["simulate", "--failure-rates", "0.05", "0.1", "0.2", "--experiments-per-rate", "100"]

# ---- Stage 3: test (optional target) ----
FROM builder AS test-builder

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root

FROM python:3.11-slim AS test

WORKDIR /app
COPY --from=test-builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="src" \
    PYTHONUNBUFFERED=1 \
    GOOGLE_API_KEY="test-dummy-key"

COPY src/ src/
COPY tests/ tests/
COPY assets/ assets/
COPY config/ config/
COPY pyproject.toml README.md ./

RUN pip install --no-cache-dir --no-deps .

CMD ["pytest", "tests/", "-v", "--tb=short"]
