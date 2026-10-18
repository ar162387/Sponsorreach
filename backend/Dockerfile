FROM python:3.12-slim
RUN pip install --no-cache-dir uv==0.9.21
WORKDIR /app
COPY backend /app/backend
COPY supabase /app/supabase
WORKDIR /app/backend
RUN uv sync --locked --no-dev --extra local
RUN useradd --create-home app && chown -R app:app /app
USER app
EXPOSE 8001
CMD ["uv", "run", "--no-sync", "uvicorn", "sponsor_match.api:app", "--host", "0.0.0.0", "--port", "8001"]
