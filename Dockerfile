FROM python:3.11-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY requirements-training.txt .
RUN pip install -r requirements-training.txt

COPY training/ ./training/

# Cloud Run supplies PORT. The filesystem is ephemeral, so SQLite here is fine
# for a trial and resets on redeploy — set DATABASE_URL to Postgres to keep data.
ENV PORT=8080
CMD exec python -m uvicorn training.main:app --host 0.0.0.0 --port ${PORT}
