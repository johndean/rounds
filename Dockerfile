# syntax=docker/dockerfile:1.7
# Rounds — combined api + worker image.
# Uses the same image for both services; Railway start command selects role.

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /work/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
ENV VITE_API_MODE=live
RUN npm run build

FROM python:3.11-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.8.5 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        poppler-utils \
        ca-certificates \
        curl \
        gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

COPY pyproject.toml ./
RUN poetry install --only main --no-root --no-cache

COPY app/ ./app/
COPY migrations/ ./migrations/
COPY scripts/ ./scripts/
COPY --from=frontend-build /work/frontend/dist/ ./frontend/dist/

RUN mkdir -p /etc/gcp && chmod 755 /etc/gcp

EXPOSE 8000
ENTRYPOINT ["bash", "scripts/start.sh"]
CMD ["api"]
