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


class TestLoadFromDb:
    def test_restores_bulbs(self):
        with patch("bulbs.db") as mock_db:
            mock_db.load_bulbs.return_value = [
                {"bulb_id": "desk", "name": "desk", "ip": "192.168.1.10"},
                {"bulb_id": "lamp", "name": "lamp", "ip": "192.168.1.11"},
            ]
            with patch("bulbs.Bulb"):
                bulbs.load_from_db()
        assert "desk" in bulbs._bulbs
        assert "lamp" in bulbs._bulbs

    def test_skips_existing(self, populated_bulbs):
        with patch("bulbs.db") as mock_db:
            mock_db.load_bulbs.return_value = [
                {"bulb_id": "desk", "name": "desk", "ip": "192.168.1.99"},
            ]
            bulbs.load_from_db()
        assert bulbs._bulbs["desk"].ip == "192.168.1.10"


class TestGetAllStatus:
    def test_returns_list(self, populated_bulbs):
        result = bulbs.get_all_status()
        assert len(result) == 1
        assert result[0]["name"] == "desk"

    def test_empty(self):
        assert bulbs.get_all_status() == []


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


class TestToggle:
    def test_calls_toggle(self, populated_bulbs, mock_bulb):
        result = bulbs.toggle("desk")
        assert result == {"ok": True}
        mock_bulb.toggle.assert_called_once()


class TestSetHsv:
    def test_basic(self, populated_bulbs, mock_bulb):
        result = bulbs.set_hsv("desk", hue=120, saturation=80)
        assert result == {"ok": True, "hue": 120, "saturation": 80}
        mock_bulb.set_hsv.assert_called_once_with(120, 80, None)

    def test_with_value(self, populated_bulbs, mock_bulb):
        result = bulbs.set_hsv("desk", hue=0, saturation=100, value=50)
        assert result["value"] == 50
        mock_bulb.set_hsv.assert_called_once_with(0, 100, 50)

    def test_clamps_hue(self, populated_bulbs, mock_bulb):
        result = bulbs.set_hsv("desk", hue=400, saturation=50)
        assert result["hue"] == 359

    def test_clamps_saturation(self, populated_bulbs, mock_bulb):
        result = bulbs.set_hsv("desk", hue=0, saturation=150)
        assert result["saturation"] == 100

    def test_clamps_value(self, populated_bulbs, mock_bulb):
        result = bulbs.set_hsv("desk", hue=0, saturation=0, value=200)
        assert result["value"] == 100


class TestSetAdjust:
    def test_increase_bright(self, populated_bulbs, mock_bulb):
        result = bulbs.set_adjust("desk", "increase", "bright")
        assert result == {"ok": True, "action": "increase", "prop": "bright"}
        mock_bulb.set_adjust.assert_called_once_with("increase", "bright")

    def test_circle_color(self, populated_bulbs, mock_bulb):
        result = bulbs.set_adjust("desk", "circle", "color")
        assert result["action"] == "circle"

    def test_invalid_action(self, populated_bulbs):
        with pytest.raises(ValueError, match="Invalid action"):
            bulbs.set_adjust("desk", "bogus", "bright")

    def test_invalid_prop(self, populated_bulbs):
        with pytest.raises(ValueError, match="Invalid prop"):
            bulbs.set_adjust("desk", "increase", "bogus")


class TestSetDefault:
    def test_calls_set_default(self, populated_bulbs, mock_bulb):
        result = bulbs.set_default("desk")
        assert result == {"ok": True}
        mock_bulb.set_default.assert_called_once()


class TestSetName:
    def test_renames(self, populated_bulbs, mock_bulb):
        result = bulbs.set_name("desk", "office")
        assert result == {"ok": True, "old_name": "desk", "new_name": "office"}
        mock_bulb.set_name.assert_called_once_with("office")
        assert "office" in bulbs._bulbs
        assert "desk" not in bulbs._bulbs

    def test_empty_name(self, populated_bulbs):
        with pytest.raises(ValueError, match="Name cannot be empty"):
            bulbs.set_name("desk", "")


class TestStartFlow:
    def test_known_flow(self, populated_bulbs, mock_bulb):
        result = bulbs.start_flow("desk", "disco")
        assert result == {"ok": True, "flow": "disco"}
        mock_bulb.start_flow.assert_called_once()

    def test_flow_with_params(self, populated_bulbs, mock_bulb):
        result = bulbs.start_flow("desk", "disco", bpm=140)
        assert result["ok"] is True
        mock_bulb.start_flow.assert_called_once()

    def test_unknown_flow(self, populated_bulbs):
        result = bulbs.start_flow("desk", "nonexistent")
        assert "error" in result
        assert "available_flows" in result

    def test_ignores_extra_params(self, populated_bulbs, mock_bulb):
        result = bulbs.start_flow("desk", "strobe", bogus=999)
        assert result["ok"] is True


class TestStopFlow:
    def test_calls_stop_flow(self, populated_bulbs, mock_bulb):
        result = bulbs.stop_flow("desk")
        assert result == {"ok": True}
        mock_bulb.stop_flow.assert_called_once()


class TestSetSceneColor:
    def test_basic(self, populated_bulbs, mock_bulb):
        result = bulbs.set_scene_color("desk", r=255, g=0, b=0, brightness=80)
        assert result["scene"] == "color"
        assert result["brightness"] == 80
        from yeelight.enums import SceneClass

        mock_bulb.set_scene.assert_called_once_with(SceneClass.COLOR, 255, 0, 0, 80)

    def test_clamps(self, populated_bulbs, mock_bulb):
        result = bulbs.set_scene_color("desk", r=300, g=-1, b=128, brightness=0)
        assert result["r"] == 255
        assert result["g"] == 0
        assert result["brightness"] == 1


class TestSetSceneCt:
    def test_basic(self, populated_bulbs, mock_bulb):
        result = bulbs.set_scene_ct("desk", temperature=3000, brightness=50)
        assert result["scene"] == "ct"
        assert result["temperature"] == 3000
        from yeelight.enums import SceneClass

        mock_bulb.set_scene.assert_called_once_with(SceneClass.CT, 3000, 50)

    def test_clamps(self, populated_bulbs, mock_bulb):
        result = bulbs.set_scene_ct("desk", temperature=100, brightness=200)
        assert result["temperature"] == 1700
        assert result["brightness"] == 100


class TestSetSceneHsv:
    def test_basic(self, populated_bulbs, mock_bulb):
        result = bulbs.set_scene_hsv("desk", hue=180, saturation=50, brightness=75)
        assert result["scene"] == "hsv"
        from yeelight.enums import SceneClass

        mock_bulb.set_scene.assert_called_once_with(SceneClass.HSV, 180, 50, 75)

    def test_clamps(self, populated_bulbs, mock_bulb):
        result = bulbs.set_scene_hsv("desk", hue=400, saturation=150, brightness=0)
        assert result["hue"] == 359
        assert result["saturation"] == 100
        assert result["brightness"] == 1


class TestSetAutoDelayOff:
    def test_basic(self, populated_bulbs, mock_bulb):
        result = bulbs.set_auto_delay_off("desk", brightness=50, minutes=10)
        assert result["scene"] == "auto_delay_off"
        assert result["minutes"] == 10
        from yeelight.enums import SceneClass

        mock_bulb.set_scene.assert_called_once_with(SceneClass.AUTO_DELAY_OFF, 50, 10)

    def test_clamps_min(self, populated_bulbs, mock_bulb):
        result = bulbs.set_auto_delay_off("desk", brightness=0, minutes=0)
        assert result["brightness"] == 1
        assert result["minutes"] == 1


class TestSleepTimer:
    def test_set(self, populated_bulbs, mock_bulb):
        result = bulbs.set_sleep_timer("desk", minutes=30)
        assert result == {"ok": True, "sleep_timer_minutes": 30}
        from yeelight.enums import CronType

        mock_bulb.cron_add.assert_called_once_with(CronType.off, 30)

    def test_clamps_min(self, populated_bulbs, mock_bulb):
        result = bulbs.set_sleep_timer("desk", minutes=0)
        assert result["sleep_timer_minutes"] == 1

    def test_cancel(self, populated_bulbs, mock_bulb):
        result = bulbs.cancel_sleep_timer("desk")
        assert result == {"ok": True}
        from yeelight.enums import CronType

        mock_bulb.cron_del.assert_called_once_with(CronType.off)


class TestSetPowerMode:
    def test_normal(self, populated_bulbs, mock_bulb):
        result = bulbs.set_power_mode("desk", "normal")
        assert result == {"ok": True, "mode": "normal"}
        from yeelight.enums import PowerMode

        mock_bulb.set_power_mode.assert_called_once_with(PowerMode.NORMAL)

    def test_moonlight(self, populated_bulbs, mock_bulb):
        result = bulbs.set_power_mode("desk", "moonlight")
        assert result["mode"] == "moonlight"

    def test_unknown_mode(self, populated_bulbs):
        result = bulbs.set_power_mode("desk", "bogus")
        assert "error" in result
        assert "available_modes" in result
