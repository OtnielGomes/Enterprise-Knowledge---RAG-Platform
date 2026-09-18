FROM python:3.12-slim

WORKDIR /app

COPY api/pyproject.toml ./
COPY api/ask ./ask
COPY snapshot ./snapshot

ENV SNAPSHOT_DIR=/app/snapshot

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "ask.http:app", "--host", "0.0.0.0", "--port", "8000"]
