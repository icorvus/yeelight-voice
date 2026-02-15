import json
import os

from dotenv import load_dotenv
from openai import OpenAI

import bulbs
import db

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
    {
        "type": "function",
        "function": {
            "name": "toggle",
            "description": "Toggle a bulb on or off",
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
            "name": "set_hsv",
            "description": "Set bulb color using HSV (hue/saturation/value) values",
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {"type": "string", "description": "Bulb identifier"},
                    "hue": {
                        "type": "integer",
                        "description": (
                            "Hue 0-359 (0=red, 60=yellow,"
                            " 120=green, 180=cyan,"
                            " 240=blue, 300=magenta)"
                        ),
                    },
                    "saturation": {
                        "type": "integer",
                        "description": "Saturation 0-100 (0=white, 100=full color)",
                    },
                    "value": {
                        "type": "integer",
                        "description": (
                            "Brightness 0-100. Omit to keep" " current brightness."
                        ),
                    },
                },
                "required": ["hue", "saturation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_adjust",
            "description": (
                "Adjust a bulb property incrementally"
                " without knowing the current value."
                " Use 'increase' or 'decrease' for"
                " brightness/color_temp,"
                " or 'circle' for color."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {"type": "string", "description": "Bulb identifier"},
                    "action": {
                        "type": "string",
                        "enum": ["increase", "decrease", "circle"],
                        "description": "Adjustment direction",
                    },
                    "prop": {
                        "type": "string",
                        "enum": ["bright", "ct", "color"],
                        "description": (
                            "Property to adjust: bright"
                            " (brightness), ct (color temp),"
                            " color (cycle, circle only)"
                        ),
                    },
                },
                "required": ["action", "prop"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_default",
            "description": "Save the bulb's current state as its power-on default",
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
            "name": "set_name",
            "description": "Rename a bulb. The new name becomes its identifier.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {
                        "type": "string",
                        "description": "Current bulb identifier",
                    },
                    "name": {"type": "string", "description": "New name for the bulb"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_flow",
            "description": (
                "Start a light animation/flow effect on a bulb. Available flows: "
                "disco, temp, strobe, pulse, strobe_color, alarm, police, police2, "
                "lsd, christmas, rgb, random_loop, slowdown, home, night_mode, "
                "date_night, movie, sunrise, sunset, romance, happy_birthday, "
                "candle_flicker, tea_time"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {"type": "string", "description": "Bulb identifier"},
                    "flow_name": {
                        "type": "string",
                        "description": "Name of the flow effect to start",
                        "enum": [
                            "disco",
                            "temp",
                            "strobe",
                            "pulse",
                            "strobe_color",
                            "alarm",
                            "police",
                            "police2",
                            "lsd",
                            "christmas",
                            "rgb",
                            "random_loop",
                            "slowdown",
                            "home",
                            "night_mode",
                            "date_night",
                            "movie",
                            "sunrise",
                            "sunset",
                            "romance",
                            "happy_birthday",
                            "candle_flicker",
                            "tea_time",
                        ],
                    },
                    "bpm": {
                        "type": "integer",
                        "description": "Beats per minute (disco only, default 120)",
                    },
                    "duration": {
                        "type": "integer",
                        "description": "Transition duration in ms (flow-specific)",
                    },
                    "brightness": {
                        "type": "integer",
                        "description": "Brightness 1-100 (flow-specific)",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Repeat count (pulse/random_loop/slowdown)",
                    },
                    "sleep": {
                        "type": "integer",
                        "description": (
                            "Sleep duration in ms between"
                            " transitions (christmas/rgb)"
                        ),
                    },
                    "red": {
                        "type": "integer",
                        "description": "Red 0-255 (pulse only)",
                    },
                    "green": {
                        "type": "integer",
                        "description": "Green 0-255 (pulse only)",
                    },
                    "blue": {
                        "type": "integer",
                        "description": "Blue 0-255 (pulse only)",
                    },
                },
                "required": ["flow_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop_flow",
            "description": "Stop the currently running flow/animation on a bulb",
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
            "name": "set_scene_color",
            "description": (
                "Set bulb to a specific RGB color and brightness"
                " simultaneously (turns on if off)"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {"type": "string", "description": "Bulb identifier"},
                    "r": {"type": "integer", "description": "Red 0-255"},
                    "g": {"type": "integer", "description": "Green 0-255"},
                    "b": {"type": "integer", "description": "Blue 0-255"},
                    "brightness": {
                        "type": "integer",
                        "description": "Brightness 1-100",
                    },
                },
                "required": ["r", "g", "b", "brightness"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_scene_ct",
            "description": (
                "Set bulb to a specific color temperature and"
                " brightness simultaneously (turns on if off)"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {"type": "string", "description": "Bulb identifier"},
                    "temperature": {
                        "type": "integer",
                        "description": "Color temperature 1700-6500K",
                    },
                    "brightness": {
                        "type": "integer",
                        "description": "Brightness 1-100",
                    },
                },
                "required": ["temperature", "brightness"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_scene_hsv",
            "description": (
                "Set bulb to a specific HSV color and brightness"
                " simultaneously (turns on if off)"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {"type": "string", "description": "Bulb identifier"},
                    "hue": {"type": "integer", "description": "Hue 0-359"},
                    "saturation": {
                        "type": "integer",
                        "description": "Saturation 0-100",
                    },
                    "brightness": {
                        "type": "integer",
                        "description": "Brightness 1-100",
                    },
                },
                "required": ["hue", "saturation", "brightness"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_auto_delay_off",
            "description": (
                "Turn on the bulb at a given brightness and"
                " automatically turn it off after a delay"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {"type": "string", "description": "Bulb identifier"},
                    "brightness": {
                        "type": "integer",
                        "description": "Brightness 1-100",
                    },
                    "minutes": {
                        "type": "integer",
                        "description": "Minutes until auto-off",
                    },
                },
                "required": ["brightness", "minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_sleep_timer",
            "description": (
                "Set a sleep timer to turn off the bulb" " after a number of minutes"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {"type": "string", "description": "Bulb identifier"},
                    "minutes": {
                        "type": "integer",
                        "description": "Minutes until the bulb turns off",
                    },
                },
                "required": ["minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_sleep_timer",
            "description": "Cancel a previously set sleep timer",
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
            "name": "set_power_mode",
            "description": (
                "Switch the bulb to a specific power mode. "
                "Modes: last (previous state), normal (white/CT), rgb, hsv, "
                "color_flow, moonlight (dim night light)"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bulb_id": {"type": "string", "description": "Bulb identifier"},
                    "mode": {
                        "type": "string",
                        "enum": [
                            "last",
                            "normal",
                            "rgb",
                            "hsv",
                            "color_flow",
                            "moonlight",
                        ],
                        "description": "Power mode to set",
                    },
                },
                "required": ["mode"],
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
(brighter/dimmer: ±20 brightness, warmer: -500K, cooler: +500K). \
You can also use set_adjust for simple incremental changes.
- Translate color names to RGB (e.g. "red" = 255,0,0).
- If the bulb is off and the user wants to change color/brightness, turn it on first.
- Use set_scene_color/set_scene_ct/set_scene_hsv when the user wants to set \
color and brightness together in one command (these also turn the bulb on).
- Use start_flow for animations and effects (e.g. "disco", "candle", "sunrise", \
"police lights", "romance", "movie mode"). Use stop_flow to stop them.
- Use set_sleep_timer when the user wants the bulb to turn off after some time \
(e.g. "turn off in 30 minutes"). Use cancel_sleep_timer to cancel.
- Use set_auto_delay_off for "turn on for X minutes then off" requests.
- Use set_power_mode to switch to moonlight/night mode or other modes.
- Use set_default to save the current state as the power-on default.
- Use set_name to rename a bulb when the user asks.
- Keep responses brief and friendly — one short sentence confirming what you did.
"""

_dispatch = {
    "discover_bulbs": lambda **_: bulbs.discover(),
    "get_bulb_status": lambda **kw: bulbs.get_status(kw.get("bulb_id", "")),
    "turn_on": lambda **kw: bulbs.turn_on(kw.get("bulb_id", "")),
    "turn_off": lambda **kw: bulbs.turn_off(kw.get("bulb_id", "")),
    "toggle": lambda **kw: bulbs.toggle(kw.get("bulb_id", "")),
    "set_brightness": lambda **kw: bulbs.set_brightness(
        kw.get("bulb_id", ""), kw["brightness"]
    ),
    "set_color": lambda **kw: bulbs.set_color(
        kw.get("bulb_id", ""), kw["r"], kw["g"], kw["b"]
    ),
    "set_color_temperature": lambda **kw: bulbs.set_color_temp(
        kw.get("bulb_id", ""), kw["temperature"]
    ),
    "set_hsv": lambda **kw: bulbs.set_hsv(
        kw.get("bulb_id", ""), kw["hue"], kw["saturation"], kw.get("value")
    ),
    "set_adjust": lambda **kw: bulbs.set_adjust(
        kw.get("bulb_id", ""), kw["action"], kw["prop"]
    ),
    "set_default": lambda **kw: bulbs.set_default(kw.get("bulb_id", "")),
    "set_name": lambda **kw: bulbs.set_name(kw.get("bulb_id", ""), kw["name"]),
    "start_flow": lambda **kw: bulbs.start_flow(
        bulb_id=kw.get("bulb_id", ""),
        flow_name=kw.get("flow_name", ""),
        **{k: v for k, v in kw.items() if k not in ("bulb_id", "flow_name")},
    ),
    "stop_flow": lambda **kw: bulbs.stop_flow(kw.get("bulb_id", "")),
    "set_scene_color": lambda **kw: bulbs.set_scene_color(
        kw.get("bulb_id", ""), kw["r"], kw["g"], kw["b"], kw["brightness"]
    ),
    "set_scene_ct": lambda **kw: bulbs.set_scene_ct(
        kw.get("bulb_id", ""), kw["temperature"], kw["brightness"]
    ),
    "set_scene_hsv": lambda **kw: bulbs.set_scene_hsv(
        kw.get("bulb_id", ""), kw["hue"], kw["saturation"], kw["brightness"]
    ),
    "set_auto_delay_off": lambda **kw: bulbs.set_auto_delay_off(
        kw.get("bulb_id", ""), kw["brightness"], kw["minutes"]
    ),
    "set_sleep_timer": lambda **kw: bulbs.set_sleep_timer(
        kw.get("bulb_id", ""), kw["minutes"]
    ),
    "cancel_sleep_timer": lambda **kw: bulbs.cancel_sleep_timer(kw.get("bulb_id", "")),
    "set_power_mode": lambda **kw: bulbs.set_power_mode(
        kw.get("bulb_id", ""), kw["mode"]
    ),
}

_history: list[dict] = []
MAX_HISTORY = 40
MAX_TOOL_ROUNDS = 5


def _init_history():
    loaded = db.load_messages()
    if loaded:
        _history.extend(loaded)
        _trim_history()


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
    db.save_message("user", user_text)
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
            db.save_message("assistant", content)
            _trim_history()
            return content

        # Append assistant message with tool calls
        assistant_msg = msg.model_dump(exclude_none=True)
        _history.append(assistant_msg)
        db.save_message("assistant", json.dumps(assistant_msg))

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
            db.save_message("tool", json.dumps(result), tool_call_id=tc.id)

    _trim_history()
    return "Sorry, I wasn't able to complete that action."


def reset_history():
    _history.clear()
    db.clear_messages()
