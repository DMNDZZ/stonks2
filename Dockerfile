FROM ghcr.io/astral-sh/uv:0.9.5 AS uv

FROM python:3.13-slim

COPY --from=uv /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY config.py bot.py bot_clear.py doc_generator.py google_sheets.py inventory_manager.py ./
COPY templates/ ./templates/

ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "bot.py"]
