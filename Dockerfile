FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN pip install --upgrade pip && pip install poetry

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --only main --no-root

COPY app ./app
COPY ui ./ui

ENV PORT=8080 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8080 \
    SQLITE_DB_PATH=/tmp/tasks.db \
    YOUTUBE_GRPC_HOST=localhost \
    YOUTUBE_GRPC_PORT=50051 \
    SHEETS_GRPC_HOST=localhost \
    SHEETS_GRPC_PORT=50052

EXPOSE 8080

CMD ["python", "-m", "app.startup"]
