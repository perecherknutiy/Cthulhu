FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install "aiogram==3.33.0" "fastapi==0.165.0" "uvicorn[standard]>=0.38" \
    "sqlalchemy[asyncio]>=2.0.40,<2.2" "asyncpg>=0.30" "alembic>=1.16" "pydantic-settings>=2.6"

COPY app ./app
COPY migrations ./migrations
COPY webapp ./webapp
COPY alembic.ini ./

RUN useradd -m appuser
USER appuser

EXPOSE 8000
# миграции при старте, затем один воркер (polling-бот и in-memory rate limit рассчитаны на один процесс)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --proxy-headers"]
