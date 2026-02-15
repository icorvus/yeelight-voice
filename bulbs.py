from dataclasses import dataclass

from yeelight import Bulb, discover_bulbs


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
    return {"bulbs": list(_bulbs.keys()), "count": len(_bulbs)}


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
