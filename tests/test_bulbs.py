from unittest.mock import MagicMock, patch

import pytest

import bulbs
from bulbs import BulbInfo, _decode_rgb


class TestDecodeRgb:
    def test_red(self):
        assert _decode_rgb(16711680) == {"r": 255, "g": 0, "b": 0}

    def test_zero(self):
        assert _decode_rgb(0) == {"r": 0, "g": 0, "b": 0}

    def test_white(self):
        assert _decode_rgb(16777215) == {"r": 255, "g": 255, "b": 255}


class TestGetBulb:
    def test_no_bulbs(self):
        with pytest.raises(ValueError, match="No bulbs discovered"):
            bulbs._get_bulb()

    def test_single_empty_id(self, populated_bulbs):
        info = bulbs._get_bulb("")
        assert info.name == "desk"

    def test_by_id(self, populated_bulbs):
        info = bulbs._get_bulb("desk")
        assert info.ip == "192.168.1.10"

    def test_unknown_id(self, populated_bulbs):
        with pytest.raises(ValueError, match="not found"):
            bulbs._get_bulb("unknown")

    def test_ambiguous(self, mock_bulb):
        bulbs._bulbs["desk"] = BulbInfo(bulb=mock_bulb, name="desk", ip="192.168.1.10")
        bulbs._bulbs["lamp"] = BulbInfo(
            bulb=MagicMock(), name="lamp", ip="192.168.1.11"
        )
        with pytest.raises(ValueError, match="not found"):
            bulbs._get_bulb("")


class TestDiscover:
    @patch("bulbs.Bulb")
    @patch("bulbs.discover_bulbs")
    def test_returns_correct_count(self, mock_discover, mock_bulb_cls):
        mock_discover.return_value = [
            {"ip": "192.168.1.10", "capabilities": {"name": "desk"}},
            {"ip": "192.168.1.11", "capabilities": {"name": "lamp"}},
        ]
        result = bulbs.discover()
        assert result["count"] == 2
        assert set(result["bulbs"]) == {"desk", "lamp"}

    @patch("bulbs.Bulb")
    @patch("bulbs.discover_bulbs")
    def test_empty(self, mock_discover, mock_bulb_cls):
        mock_discover.return_value = []
        result = bulbs.discover()
        assert result == {"bulbs": [], "count": 0}

    @patch("bulbs.Bulb")
    @patch("bulbs.discover_bulbs")
    def test_fallback_name(self, mock_discover, mock_bulb_cls):
        mock_discover.return_value = [{"ip": "192.168.1.10", "capabilities": {}}]
        result = bulbs.discover()
        assert result["bulbs"] == ["bulb_1"]


class TestGetStatus:
    def test_shape(self, populated_bulbs):
        status = bulbs.get_status("desk")
        assert status["name"] == "desk"
        assert status["power"] == "on"
        assert status["brightness"] == 80
        assert status["color"] == {"r": 255, "g": 0, "b": 0}
        assert status["color_temp"] == 4000


class TestTurnOnOff:
    def test_turn_on(self, populated_bulbs, mock_bulb):
        result = bulbs.turn_on("desk")
        assert result == {"ok": True}
        mock_bulb.turn_on.assert_called_once()

    def test_turn_off(self, populated_bulbs, mock_bulb):
        result = bulbs.turn_off("desk")
        assert result == {"ok": True}
        mock_bulb.turn_off.assert_called_once()


class TestSetBrightness:
    def test_clamps_low(self, populated_bulbs, mock_bulb):
        result = bulbs.set_brightness("desk", brightness=-5)
        assert result["brightness"] == 1
        mock_bulb.set_brightness.assert_called_once_with(1)

    def test_clamps_high(self, populated_bulbs, mock_bulb):
        result = bulbs.set_brightness("desk", brightness=200)
        assert result["brightness"] == 100
        mock_bulb.set_brightness.assert_called_once_with(100)


class TestSetColor:
    def test_clamps(self, populated_bulbs, mock_bulb):
        result = bulbs.set_color("desk", r=-10, g=300, b=128)
        assert result["color"] == {"r": 0, "g": 255, "b": 128}
        mock_bulb.set_rgb.assert_called_once_with(0, 255, 128)


class TestSetColorTemp:
    def test_clamps_low(self, populated_bulbs, mock_bulb):
        result = bulbs.set_color_temp("desk", temperature=500)
        assert result["color_temp"] == 1700
        mock_bulb.set_color_temp.assert_called_once_with(1700)

    def test_clamps_high(self, populated_bulbs, mock_bulb):
        result = bulbs.set_color_temp("desk", temperature=9000)
        assert result["color_temp"] == 6500
        mock_bulb.set_color_temp.assert_called_once_with(6500)
