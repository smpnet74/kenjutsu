# Stage 1: Build
FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml .
COPY kenjutsu/ kenjutsu/

RUN pip install --no-cache-dir .

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY kenjutsu/ kenjutsu/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()" || exit 1

CMD ["uvicorn", "kenjutsu.app:app", "--host", "0.0.0.0", "--port", "8000"]
