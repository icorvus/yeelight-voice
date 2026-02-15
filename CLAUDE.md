# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Voice-controlled Yeelight smart bulb application. Users speak or type natural language commands to discover and control Yeelight bulbs via a web UI. Uses LLM tool-calling (via OpenRouter) for intent parsing and bulb control, and OpenAI Whisper for speech-to-text.

## Commands

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn app:app --reload

# Run with Docker
docker compose up --build

# Lint and format
uv run ruff check
uv run ruff check --fix
uv run ruff format

# Run tests
uv run pytest
uv run pytest tests/test_app.py          # single file
uv run pytest -k test_name               # single test
```

## Architecture

**Request flow:** User input (voice/text) → FastAPI endpoint → STT transcription (voice only) → LLM tool-calling loop → bulb control → JSON response with bulb status.

**Source modules:**
- `app.py` — FastAPI server with Pydantic response models. Lifespan initializes DB, loads chat history, and attempts bulb discovery with DB fallback. Serves `static/index.html` at `/`.
- `llm.py` — LLM chat engine using pydantic-ai `Agent` with OpenRouter. Tool functions delegate to `bulbs` module. Maintains in-memory chat history (max 40 messages, auto-trimmed) with SQLite persistence.
- `db.py` — SQLite persistence layer (`data.db`). Stores chat history as serialized pydantic-ai message runs and caches discovered bulbs for offline startup.
- `bulbs.py` — Bulb discovery (SSDP multicast) and control via `yeelight` library. In-memory registry keyed by bulb name, with DB fallback when discovery fails. Values are clamped to valid ranges.
- `stt.py` — Thin wrapper around OpenAI `gpt-4o-transcribe` model.
- `static/index.html` — Single-page vanilla JS/CSS UI with hold-to-talk mic input, text input, and bulb status cards.

**Key design decisions:**
- Blocking I/O (bulb control, STT) runs in thread pool via `asyncio.to_thread`; LLM calls use pydantic-ai's native async
- State (bulb registry, chat history) is persisted to SQLite via `db.py`, with in-memory caches for runtime
- Docker uses host networking for SSDP multicast bulb discovery
- LLM model is configurable via `LLM_MODEL` env var (default: `google/gemini-2.5-flash`)

## Environment Variables

See `.env.example`. Required: `OPENAI_API_KEY` (Whisper), `OPENROUTER_API_KEY` (LLM). Optional: `LLM_MODEL`, `HOST`, `PORT`.

Yeelight bulbs must have LAN Control enabled and be on the same network.
