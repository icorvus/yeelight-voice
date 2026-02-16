import json
from typing import Literal

from pydantic_ai import (
    Agent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UsageLimits,
    UserPromptPart,
)
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from yeelight_voice.core import bulbs, db
from yeelight_voice.settings import settings

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

FLOW_NAMES = Literal[
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
]

_model = OpenRouterModel(
    settings.llm_model,
    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
)
agent = Agent(_model, instructions=SYSTEM_PROMPT)


@agent.system_prompt
def inject_bulb_state() -> str:
    status = bulbs.get_all_status()
    if status:
        return f"Current bulb state:\n{json.dumps(status, indent=2)}"
    return ""


# --- Tool definitions ---


@agent.tool_plain
def discover_bulbs() -> dict:
    """Scan the local network for Yeelight smart bulbs."""
    return bulbs.discover()


@agent.tool_plain
def get_bulb_status(bulb_id: str = "") -> dict:
    """Get current state of a bulb."""
    return bulbs.get_status(bulb_id)


@agent.tool_plain
def turn_on(bulb_id: str = "") -> dict:
    """Turn on a bulb."""
    return bulbs.turn_on(bulb_id)


@agent.tool_plain
def turn_off(bulb_id: str = "") -> dict:
    """Turn off a bulb."""
    return bulbs.turn_off(bulb_id)


@agent.tool_plain
def toggle(bulb_id: str = "") -> dict:
    """Toggle a bulb on or off."""
    return bulbs.toggle(bulb_id)


@agent.tool_plain
def set_brightness(brightness: int, bulb_id: str = "") -> dict:
    """Set bulb brightness (1-100)."""
    return bulbs.set_brightness(bulb_id, brightness)


@agent.tool_plain
def set_color(r: int, g: int, b: int, bulb_id: str = "") -> dict:
    """Set bulb color using RGB values (0-255 each)."""
    return bulbs.set_color(bulb_id, r, g, b)


@agent.tool_plain
def set_color_temperature(temperature: int, bulb_id: str = "") -> dict:
    """Set bulb color temperature in Kelvin (1700=warm/yellow, 6500=cool/blue-white)."""
    return bulbs.set_color_temp(bulb_id, temperature)


@agent.tool_plain
def set_hsv(
    hue: int,
    saturation: int,
    value: int | None = None,
    bulb_id: str = "",
) -> dict:
    """Set bulb color using HSV values.

    Hue 0-359, saturation 0-100, value 0-100.
    Omit value to keep current brightness.
    """
    return bulbs.set_hsv(bulb_id, hue, saturation, value)


@agent.tool_plain
def set_adjust(
    action: Literal["increase", "decrease", "circle"],
    prop: Literal["bright", "ct", "color"],
    bulb_id: str = "",
) -> dict:
    """Adjust a bulb property incrementally without knowing the current value."""
    return bulbs.set_adjust(bulb_id, action, prop)


@agent.tool_plain
def set_default(bulb_id: str = "") -> dict:
    """Save the bulb's current state as its power-on default."""
    return bulbs.set_default(bulb_id)


@agent.tool_plain
def set_name(name: str, bulb_id: str = "") -> dict:
    """Rename a bulb. The new name becomes its identifier."""
    return bulbs.set_name(bulb_id, name)


@agent.tool_plain
def start_flow(
    flow_name: FLOW_NAMES,
    bulb_id: str = "",
    bpm: int | None = None,
    duration: int | None = None,
    brightness: int | None = None,
    count: int | None = None,
    sleep: int | None = None,
    red: int | None = None,
    green: int | None = None,
    blue: int | None = None,
) -> dict:
    """Start a light animation/flow effect on a bulb."""
    kwargs: dict = {}
    keys = ("bpm", "duration", "brightness", "count", "sleep", "red", "green", "blue")
    for key in keys:
        val = locals()[key]
        if val is not None:
            kwargs[key] = val
    return bulbs.start_flow(bulb_id=bulb_id, flow_name=flow_name, **kwargs)


@agent.tool_plain
def stop_flow(bulb_id: str = "") -> dict:
    """Stop the currently running flow/animation on a bulb."""
    return bulbs.stop_flow(bulb_id)


@agent.tool_plain
def set_scene_color(r: int, g: int, b: int, brightness: int, bulb_id: str = "") -> dict:
    """Set bulb to a specific RGB color and brightness.

    Turns on if off.
    """
    return bulbs.set_scene_color(bulb_id, r, g, b, brightness)


@agent.tool_plain
def set_scene_ct(temperature: int, brightness: int, bulb_id: str = "") -> dict:
    """Set bulb to a specific color temperature and brightness.

    Turns on if off.
    """
    return bulbs.set_scene_ct(bulb_id, temperature, brightness)


@agent.tool_plain
def set_scene_hsv(
    hue: int, saturation: int, brightness: int, bulb_id: str = ""
) -> dict:
    """Set bulb to a specific HSV color and brightness.

    Turns on if off.
    """
    return bulbs.set_scene_hsv(bulb_id, hue, saturation, brightness)


@agent.tool_plain
def set_auto_delay_off(brightness: int, minutes: int, bulb_id: str = "") -> dict:
    """Turn on the bulb and automatically turn it off after a delay."""
    return bulbs.set_auto_delay_off(bulb_id, brightness, minutes)


@agent.tool_plain
def set_sleep_timer(minutes: int, bulb_id: str = "") -> dict:
    """Set a sleep timer to turn off the bulb after a number of minutes."""
    return bulbs.set_sleep_timer(bulb_id, minutes)


@agent.tool_plain
def cancel_sleep_timer(bulb_id: str = "") -> dict:
    """Cancel a previously set sleep timer."""
    return bulbs.cancel_sleep_timer(bulb_id)


@agent.tool_plain
def set_power_mode(
    mode: Literal["last", "normal", "rgb", "hsv", "color_flow", "moonlight"],
    bulb_id: str = "",
) -> dict:
    """Switch the bulb to a specific power mode."""
    return bulbs.set_power_mode(bulb_id, mode)


# --- History management ---

_history: list[ModelMessage] = []
MAX_HISTORY = 40
MAX_TOOL_ROUNDS = 5


def _init_history():
    data = db.load_all_messages_json()
    if data:
        loaded = ModelMessagesTypeAdapter.validate_json(data)
        _history.extend(loaded)
        _trim_history()


def _trim_history():
    while len(_history) > MAX_HISTORY:
        _history.pop(0)


async def chat(user_text: str) -> str:
    """Send user text through the PydanticAI agent. Returns final response."""
    result = await agent.run(
        user_text,
        message_history=_history,
        usage_limits=UsageLimits(request_limit=MAX_TOOL_ROUNDS),
    )
    _history.extend(result.new_messages())
    _trim_history()
    db.save_messages_json(ModelMessagesTypeAdapter.dump_json(result.new_messages()))
    return result.output


def get_visible_history() -> list[dict]:
    """Return only user and plain assistant messages (no tool calls/results)."""
    visible = []
    for msg in _history:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart):
                    visible.append({"role": "user", "content": part.content})
        elif isinstance(msg, ModelResponse):
            has_tool_calls = any(isinstance(p, ToolCallPart) for p in msg.parts)
            if has_tool_calls:
                continue
            for part in msg.parts:
                if isinstance(part, TextPart):
                    visible.append({"role": "assistant", "content": part.content})
    return visible


def reset_history():
    _history.clear()
    db.clear_messages()
