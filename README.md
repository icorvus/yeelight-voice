# Yeelight Voice

Voice-controlled Yeelight smart bulbs powered by LLM and speech recognition.

Speak or type natural language commands to discover and control your Yeelight bulbs — adjust brightness, change colors, toggle power, and more — all through a web interface.

## How it works

1. Voice is captured in the browser and transcribed using GPT-4o-transcribe
2. The transcript (or typed text) is sent to an LLM (via OpenRouter) with tool-calling capabilities
3. The LLM interprets the intent and calls bulb control functions (discover, on/off, brightness, color, color temperature)
4. Results are returned as a natural language response

## Setup

```bash
pip install -r requirements.txt
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
python app.py
```

Open `http://localhost:8000`, discover your bulbs, and start talking.

## Project structure

| File | Purpose |
|------|---------|
| `app.py` | FastAPI server and API endpoints |
| `bulbs.py` | Yeelight bulb discovery and control |
| `llm.py` | LLM chat with tool-calling |
| `stt.py` | Speech-to-text via GPT-4o-transcribe |
| `static/index.html` | Web UI |
