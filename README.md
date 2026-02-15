# Yeelight Voice

Voice-controlled Yeelight smart bulbs powered by LLM and speech recognition.

Speak or type natural language commands to discover and control your Yeelight bulbs — adjust brightness, change colors, toggle power, and more — all through a web interface.

## How it works

1. Voice is captured in the browser and transcribed using GPT-4o-transcribe
2. The transcript (or typed text) is sent to a LLM agent
3. The agent interprets the intent and calls bulb control tools (discover, on/off, brightness, color, color temperature, flows, scenes, timers, and more)
4. Results are returned as a natural language response

## Setup

```bash
uv sync
```

Copy `.env.example` to `.env` and fill in your API keys:

```
OPENAI_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...
LLM_MODEL=google/gemini-2.5-flash
```

Your Yeelight bulbs must have LAN Control enabled and be on the same network.

## Usage

```bash
uv run uvicorn app:app
```

Open `http://localhost:8000`, discover your bulbs, and start talking.

### Docker

```bash
docker compose up --build
```

Host networking is used so the container can discover Yeelight bulbs on your LAN via SSDP multicast.

## Project structure

| File | Purpose |
|------|---------|
| `app.py` | FastAPI server and API endpoints |
| `bulbs.py` | Yeelight bulb discovery and control |
| `llm.py` | PydanticAI agent with tool-calling |
| `db.py` | SQLite persistence for chat history and bulbs |
| `stt.py` | Speech-to-text via GPT-4o-transcribe |
| `static/index.html` | Web UI |

## Security

This app has no built-in authentication. Anyone who can reach the server can control your bulbs and trigger LLM/STT API calls (which cost money). By default it is meant to run on your local network only.

If you want to access it remotely, put it behind an authentication layer first. For example, you can use [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) with [Cloudflare Zero Trust](https://developers.cloudflare.com/cloudflare-one/) to securely expose the app to the internet without opening any ports on your router.

## Testing

```bash
uv run pytest
```
