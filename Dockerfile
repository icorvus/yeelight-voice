FROM astral/uv:python3.12-trixie-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .

ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE ${PORT}

CMD uv run uvicorn yeelight_voice.app:app --host ${HOST} --port ${PORT}
