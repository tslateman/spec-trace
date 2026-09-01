FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

COPY pyproject.toml README.md LICENSE demos.yaml ./
COPY spectrace-flows ./spectrace-flows
COPY spectrace ./spectrace

RUN uv pip install --system -e ./spectrace-flows -e .

RUN SECRET_KEY=build-only DEBUG=false python spectrace/manage.py collectstatic --no-input

EXPOSE 8000

CMD ["gunicorn", "spectrace.wsgi:application", "--chdir", "spectrace", "--bind", "0.0.0.0:8000", "--workers", "2"]
