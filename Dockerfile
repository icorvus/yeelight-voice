FROM astral/uv:python3.12-trixie-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .

RUN useradd --create-home appuser
USER appuser

ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE ${PORT}

CMD uv run uvicorn app:app --host ${HOST} --port ${PORT}
