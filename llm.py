import json
import os

from dotenv import load_dotenv
from openai import OpenAI

import bulbs

load_dotenv()

_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)
_model = os.getenv("LLM_MODEL", "google/gemini-2.5-flash")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "discover_bulbs",
            "description": "Scan the local network for Yeelight smart bulbs",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bulb_status",
            "description": (
                "Get current state of a bulb"
                " (power, brightness, color, color_temp, color_mode)"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {
                        "type": "string",
                        "description": (
                            "Bulb identifier. Leave empty if only one bulb exists."
                        ),
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_on",
            "description": "Turn on a bulb",
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {"type": "string", "description": "Bulb identifier"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_off",
            "description": "Turn off a bulb",
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {"type": "string", "description": "Bulb identifier"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_brightness",
            "description": "Set bulb brightness (1-100)",
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {"type": "string", "description": "Bulb identifier"},
                    "brightness": {
                        "type": "integer",
                        "description": "Brightness level 1-100",
                    },
                },
                "required": ["brightness"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_color",
            "description": "Set bulb color using RGB values (0-255 each)",
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {"type": "string", "description": "Bulb identifier"},
                    "r": {"type": "integer", "description": "Red 0-255"},
                    "g": {"type": "integer", "description": "Green 0-255"},
                    "b": {"type": "integer", "description": "Blue 0-255"},
                },
                "required": ["r", "g", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_color_temperature",
            "description": (
                "Set bulb color temperature in Kelvin"
                " (1700=warm/yellow, 6500=cool/blue-white)"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {"type": "string", "description": "Bulb identifier"},
                    "temperature": {
                        "type": "integer",
                        "description": "Color temperature 1700-6500K",
                    },
                },
                "required": ["temperature"],
            },
        },
    },
]

SYSTEM_PROMPT = """\
You are a smart home assistant that controls Yeelight bulbs.

Rules:
- If no bulbs are known yet, call discover_bulbs first.
- If only one bulb exists, you don't need to specify bulb_id.
- If user doesn't specify which bulbs to control, assume all available bulbs.
- For relative commands like "brighter", "dimmer", "warmer", "cooler": \
call get_bulb_status first to read the current value, then adjust \
(brighter/dimmer: ±20 brightness, warmer: -500K, cooler: +500K).
- Translate color names to RGB (e.g. "red" = 255,0,0).
- If the bulb is off and the user wants to change color/brightness, turn it on first.
- Keep responses brief and friendly — one short sentence confirming what you did.
"""

_dispatch = {
    "discover_bulbs": lambda **_: bulbs.discover(),
    "get_bulb_status": lambda **kw: bulbs.get_status(kw.get("bulb_id", "")),
    "turn_on": lambda **kw: bulbs.turn_on(kw.get("bulb_id", "")),
    "turn_off": lambda **kw: bulbs.turn_off(kw.get("bulb_id", "")),
    "set_brightness": lambda **kw: bulbs.set_brightness(
        kw.get("bulb_id", ""), kw["brightness"]
    ),
    "set_color": lambda **kw: bulbs.set_color(
        kw.get("bulb_id", ""), kw["r"], kw["g"], kw["b"]
    ),
    "set_color_temperature": lambda **kw: bulbs.set_color_temp(
        kw.get("bulb_id", ""), kw["temperature"]
    ),
}

_history: list[dict] = []
MAX_HISTORY = 40
MAX_TOOL_ROUNDS = 5


def _trim_history():
    while len(_history) > MAX_HISTORY:
        _history.pop(0)


def _build_messages() -> list[dict]:
    status = bulbs.get_all_status()
    system = SYSTEM_PROMPT
    if status:
        system += f"\n\nCurrent bulb state:\n{json.dumps(status, indent=2)}"
    return [{"role": "system", "content": system}] + _history


def chat(user_text: str) -> str:
    """Send user text through the LLM tool-calling loop. Returns final response."""
    _history.append({"role": "user", "content": user_text})
    _trim_history()

    for _ in range(MAX_TOOL_ROUNDS):
        resp = _client.chat.completions.create(
            model=_model,
            messages=_build_messages(),
            tools=TOOLS,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            content = msg.content or ""
            _history.append({"role": "assistant", "content": content})
            _trim_history()
            return content

        # Append assistant message with tool calls
        _history.append(msg.model_dump(exclude_none=True))

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                args = (
                    json.loads(tc.function.arguments) if tc.function.arguments else {}
                )
                handler = _dispatch.get(fn_name)
                if not handler:
                    result = {"error": f"Unknown tool: {fn_name}"}
                else:
                    result = handler(**args)
            except Exception as e:
                result = {"error": str(e)}

            _history.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                }
            )

    _trim_history()
    return "Sorry, I wasn't able to complete that action."


def reset_history():
    _history.clear()
