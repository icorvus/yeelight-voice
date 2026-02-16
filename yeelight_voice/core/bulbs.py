from dataclasses import dataclass

from yeelight import Bulb, discover_bulbs
from yeelight import flows as yee_flows
from yeelight.enums import CronType, PowerMode, SceneClass

from yeelight_voice.core import db


@dataclass
class BulbInfo:
    bulb: Bulb
    name: str
    ip: str


_bulbs: dict[str, BulbInfo] = {}


def discover() -> dict:
    """Discover Yeelight bulbs on the LAN via SSDP."""
    _bulbs.clear()
    found = discover_bulbs()
    for i, entry in enumerate(found):
        ip = entry["ip"]
        cap = entry.get("capabilities", {})
        name = cap.get("name") or f"bulb_{i + 1}"
        bulb_id = name
        b = Bulb(ip)
        _bulbs[bulb_id] = BulbInfo(bulb=b, name=name, ip=ip)
    if _bulbs:
        db.save_bulbs(_bulbs)
    return {"bulbs": list(_bulbs.keys()), "count": len(_bulbs)}


def load_from_db():
    """Restore bulb registry from the database."""
    saved = db.load_bulbs()
    for entry in saved:
        bulb_id = entry["bulb_id"]
        if bulb_id not in _bulbs:
            b = Bulb(entry["ip"])
            _bulbs[bulb_id] = BulbInfo(bulb=b, name=entry["name"], ip=entry["ip"])


def _get_bulb(bulb_id: str = "") -> BulbInfo:
    if not _bulbs:
        raise ValueError("No bulbs discovered. Run discover_bulbs first.")
    if not bulb_id and len(_bulbs) == 1:
        return next(iter(_bulbs.values()))
    if bulb_id in _bulbs:
        return _bulbs[bulb_id]
    raise ValueError(f"Bulb '{bulb_id}' not found. Known bulbs: {list(_bulbs.keys())}")


def _decode_rgb(rgb_int: int) -> dict:
    rgb_int = int(rgb_int)
    return {
        "r": (rgb_int >> 16) & 0xFF,
        "g": (rgb_int >> 8) & 0xFF,
        "b": rgb_int & 0xFF,
    }


def get_status(bulb_id: str = "") -> dict:
    info = _get_bulb(bulb_id)
    props = info.bulb.get_properties()
    rgb = _decode_rgb(props.get("rgb", 0))
    return {
        "id": bulb_id or next(iter(_bulbs)),
        "name": info.name,
        "ip": info.ip,
        "power": props.get("power", "off"),
        "brightness": int(props.get("bright", 0)),
        "color": rgb,
        "color_temp": int(props.get("ct", 4000)),
        "color_mode": int(props.get("color_mode", 2)),
    }


def get_all_status() -> list[dict]:
    return [get_status(bid) for bid in _bulbs]


def turn_on(bulb_id: str = "") -> dict:
    _get_bulb(bulb_id).bulb.turn_on()
    return {"ok": True}


def turn_off(bulb_id: str = "") -> dict:
    _get_bulb(bulb_id).bulb.turn_off()
    return {"ok": True}


def set_brightness(bulb_id: str = "", brightness: int = 100) -> dict:
    brightness = max(1, min(100, int(brightness)))
    _get_bulb(bulb_id).bulb.set_brightness(brightness)
    return {"ok": True, "brightness": brightness}


def set_color(bulb_id: str = "", r: int = 255, g: int = 255, b: int = 255) -> dict:
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    _get_bulb(bulb_id).bulb.set_rgb(r, g, b)
    return {"ok": True, "color": {"r": r, "g": g, "b": b}}


def set_color_temp(bulb_id: str = "", temperature: int = 4000) -> dict:
    temperature = max(1700, min(6500, int(temperature)))
    _get_bulb(bulb_id).bulb.set_color_temp(temperature)
    return {"ok": True, "color_temp": temperature}


def toggle(bulb_id: str = "") -> dict:
    _get_bulb(bulb_id).bulb.toggle()
    return {"ok": True}


def set_hsv(
    bulb_id: str = "", hue: int = 0, saturation: int = 100, value: int | None = None
) -> dict:
    hue = max(0, min(359, int(hue)))
    saturation = max(0, min(100, int(saturation)))
    if value is not None:
        value = max(0, min(100, int(value)))
    _get_bulb(bulb_id).bulb.set_hsv(hue, saturation, value)
    result = {"ok": True, "hue": hue, "saturation": saturation}
    if value is not None:
        result["value"] = value
    return result


def set_adjust(
    bulb_id: str = "", action: str = "increase", prop: str = "bright"
) -> dict:
    valid_actions = ("increase", "decrease", "circle")
    valid_props = ("bright", "ct", "color")
    if action not in valid_actions:
        raise ValueError(f"Invalid action '{action}'. Must be one of {valid_actions}")
    if prop not in valid_props:
        raise ValueError(f"Invalid prop '{prop}'. Must be one of {valid_props}")
    _get_bulb(bulb_id).bulb.set_adjust(action, prop)
    return {"ok": True, "action": action, "prop": prop}


def set_default(bulb_id: str = "") -> dict:
    _get_bulb(bulb_id).bulb.set_default()
    return {"ok": True}


def set_name(bulb_id: str = "", name: str = "") -> dict:
    if not name:
        raise ValueError("Name cannot be empty")
    info = _get_bulb(bulb_id)
    info.bulb.set_name(name)
    old_id = bulb_id or next(iter(_bulbs))
    # Update the registry with the new name
    _bulbs.pop(old_id, None)
    info.name = name
    _bulbs[name] = info
    db.save_bulbs(_bulbs)
    return {"ok": True, "old_name": old_id, "new_name": name}


# Mapping of flow names to factory functions from yeelight.flows
_FLOW_PRESETS: dict[str, dict] = {
    "disco": {"fn": yee_flows.disco, "params": ["bpm"]},
    "temp": {"fn": yee_flows.temp, "params": []},
    "strobe": {"fn": yee_flows.strobe, "params": []},
    "pulse": {
        "fn": yee_flows.pulse,
        "params": ["red", "green", "blue", "duration", "brightness", "count"],
    },
    "strobe_color": {"fn": yee_flows.strobe_color, "params": ["brightness"]},
    "alarm": {"fn": yee_flows.alarm, "params": ["duration"]},
    "police": {
        "fn": yee_flows.police,
        "params": ["duration", "brightness"],
    },
    "police2": {
        "fn": yee_flows.police2,
        "params": ["duration", "brightness"],
    },
    "lsd": {"fn": yee_flows.lsd, "params": ["duration", "brightness"]},
    "christmas": {
        "fn": yee_flows.christmas,
        "params": ["duration", "brightness", "sleep"],
    },
    "rgb": {
        "fn": yee_flows.rgb,
        "params": ["duration", "brightness", "sleep"],
    },
    "random_loop": {
        "fn": yee_flows.random_loop,
        "params": ["duration", "brightness", "count"],
    },
    "slowdown": {
        "fn": yee_flows.slowdown,
        "params": ["duration", "brightness", "count"],
    },
    "home": {"fn": yee_flows.home, "params": ["duration", "brightness"]},
    "night_mode": {"fn": yee_flows.night_mode, "params": ["duration", "brightness"]},
    "date_night": {"fn": yee_flows.date_night, "params": ["duration", "brightness"]},
    "movie": {"fn": yee_flows.movie, "params": ["duration", "brightness"]},
    "sunrise": {"fn": yee_flows.sunrise, "params": []},
    "sunset": {"fn": yee_flows.sunset, "params": []},
    "romance": {"fn": yee_flows.romance, "params": []},
    "happy_birthday": {"fn": yee_flows.happy_birthday, "params": []},
    "candle_flicker": {"fn": yee_flows.candle_flicker, "params": []},
    "tea_time": {"fn": yee_flows.tea_time, "params": ["duration", "brightness"]},
}


def start_flow(bulb_id: str = "", flow_name: str = "", **kwargs) -> dict:
    if flow_name not in _FLOW_PRESETS:
        return {
            "error": f"Unknown flow '{flow_name}'",
            "available_flows": list(_FLOW_PRESETS.keys()),
        }
    preset = _FLOW_PRESETS[flow_name]
    # Filter kwargs to only valid params for this flow
    valid_kwargs = {k: v for k, v in kwargs.items() if k in preset["params"]}
    # Convert numeric params to int
    for k, v in valid_kwargs.items():
        valid_kwargs[k] = int(v)
    flow = preset["fn"](**valid_kwargs)
    _get_bulb(bulb_id).bulb.start_flow(flow)
    return {"ok": True, "flow": flow_name}


def stop_flow(bulb_id: str = "") -> dict:
    _get_bulb(bulb_id).bulb.stop_flow()
    return {"ok": True}


def set_scene_color(
    bulb_id: str = "", r: int = 255, g: int = 255, b: int = 255, brightness: int = 100
) -> dict:
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    brightness = max(1, min(100, int(brightness)))
    _get_bulb(bulb_id).bulb.set_scene(SceneClass.COLOR, r, g, b, brightness)
    return {
        "ok": True,
        "scene": "color",
        "r": r,
        "g": g,
        "b": b,
        "brightness": brightness,
    }


def set_scene_ct(
    bulb_id: str = "", temperature: int = 4000, brightness: int = 100
) -> dict:
    temperature = max(1700, min(6500, int(temperature)))
    brightness = max(1, min(100, int(brightness)))
    _get_bulb(bulb_id).bulb.set_scene(SceneClass.CT, temperature, brightness)
    return {
        "ok": True,
        "scene": "ct",
        "temperature": temperature,
        "brightness": brightness,
    }


def set_scene_hsv(
    bulb_id: str = "", hue: int = 0, saturation: int = 100, brightness: int = 100
) -> dict:
    hue = max(0, min(359, int(hue)))
    saturation = max(0, min(100, int(saturation)))
    brightness = max(1, min(100, int(brightness)))
    _get_bulb(bulb_id).bulb.set_scene(SceneClass.HSV, hue, saturation, brightness)
    return {
        "ok": True,
        "scene": "hsv",
        "hue": hue,
        "saturation": saturation,
        "brightness": brightness,
    }


def set_auto_delay_off(
    bulb_id: str = "", brightness: int = 100, minutes: int = 1
) -> dict:
    brightness = max(1, min(100, int(brightness)))
    minutes = max(1, int(minutes))
    _get_bulb(bulb_id).bulb.set_scene(SceneClass.AUTO_DELAY_OFF, brightness, minutes)
    return {
        "ok": True,
        "scene": "auto_delay_off",
        "brightness": brightness,
        "minutes": minutes,
    }


def set_sleep_timer(bulb_id: str = "", minutes: int = 30) -> dict:
    minutes = max(1, int(minutes))
    _get_bulb(bulb_id).bulb.cron_add(CronType.off, minutes)
    return {"ok": True, "sleep_timer_minutes": minutes}


def cancel_sleep_timer(bulb_id: str = "") -> dict:
    _get_bulb(bulb_id).bulb.cron_del(CronType.off)
    return {"ok": True}


def set_power_mode(bulb_id: str = "", mode: str = "normal") -> dict:
    mode_map = {
        "last": PowerMode.LAST,
        "normal": PowerMode.NORMAL,
        "rgb": PowerMode.RGB,
        "hsv": PowerMode.HSV,
        "color_flow": PowerMode.COLOR_FLOW,
        "moonlight": PowerMode.MOONLIGHT,
    }
    if mode not in mode_map:
        return {
            "error": f"Unknown mode '{mode}'",
            "available_modes": list(mode_map.keys()),
        }
    _get_bulb(bulb_id).bulb.set_power_mode(mode_map[mode])
    return {"ok": True, "mode": mode}
