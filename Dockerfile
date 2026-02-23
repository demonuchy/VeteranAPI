FROM python:3.11-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync

COPY src/ ./src/

EXPOSE 8000

# Добавляем venv/bin в PATH
ENV PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]