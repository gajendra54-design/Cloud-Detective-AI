FROM python:3.12-slim
WORKDIR /app
COPY requirements-runtime.lock /app/requirements-runtime.lock
RUN --mount=type=cache,target=/root/.cache/pip pip install --retries 2 --timeout 60 --upgrade pip==26.2.1 && pip install --retries 2 --timeout 60 -r requirements-runtime.lock && python -m pip uninstall --yes pip && useradd --uid 10001 --create-home app
COPY backend/ /app/
USER 10001
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
