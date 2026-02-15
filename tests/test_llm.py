from unittest.mock import patch

import pytest
from pydantic_ai import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.test import TestModel

import llm


@pytest.fixture(autouse=True)
def _reset():
    llm._history.clear()
    yield
    llm._history.clear()


class TestGetVisibleHistory:
    def test_returns_user_and_assistant(self):
        llm._history.extend(
            [
                ModelRequest(parts=[UserPromptPart(content="hello")]),
                ModelResponse(parts=[TextPart(content="hi there")]),
            ]
        )
        result = llm.get_visible_history()
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "hello"}
        assert result[1] == {"role": "assistant", "content": "hi there"}

    def test_filters_tool_messages(self):
        llm._history.extend(
            [
                ModelRequest(parts=[UserPromptPart(content="find bulbs")]),
                ModelResponse(
                    parts=[ToolCallPart(tool_name="discover_bulbs", args="{}")]
                ),
                ModelResponse(parts=[TextPart(content="Found 1 bulb!")]),
            ]
        )
        result = llm.get_visible_history()
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["content"] == "Found 1 bulb!"

    def test_empty_history(self):
        assert llm.get_visible_history() == []


class TestResetHistory:
    def test_clears(self):
        llm._history.append(ModelRequest(parts=[UserPromptPart(content="hi")]))
        llm.reset_history()
        assert llm._history == []


class TestTrimHistory:
    def test_trims_when_over_max(self):
        llm._history.extend(
            [ModelRequest(parts=[UserPromptPart(content=str(i))]) for i in range(50)]
        )
        llm._trim_history()
        assert len(llm._history) == llm.MAX_HISTORY

    def test_noop_when_short(self):
        llm._history.append(ModelRequest(parts=[UserPromptPart(content="hi")]))
        llm._trim_history()
        assert len(llm._history) == 1


class TestChat:
    @patch("bulbs.get_all_status", return_value=[])
    async def test_simple_response(self, mock_status):
        model = TestModel(call_tools=[], custom_output_text="Hello!")
        with llm.agent.override(model=model):
            result = await llm.chat("hi")
        assert result == "Hello!"
        assert len(llm._history) > 0

    @patch("bulbs.get_all_status", return_value=[])
    async def test_with_tool_call(self, mock_status):
        test_model = TestModel(
            call_tools=["discover_bulbs"],
            custom_output_text="Found 2 bulbs!",
        )
        mock_discover = {"count": 2, "bulbs": ["desk", "lamp"]}
        with (
            llm.agent.override(model=test_model),
            patch("bulbs.discover", return_value=mock_discover),
        ):
            result = await llm.chat("find bulbs")
        assert result == "Found 2 bulbs!"


class TestToolFunctions:
    """Test tool functions directly as plain functions."""

    def test_discover_bulbs(self):
        with patch("bulbs.discover", return_value={"count": 1, "bulbs": ["desk"]}):
            result = llm.discover_bulbs()
        assert result == {"count": 1, "bulbs": ["desk"]}

    def test_turn_on(self):
        with patch("bulbs.turn_on", return_value={"ok": True}) as m:
            llm.turn_on(bulb_id="desk")
            m.assert_called_once_with("desk")

    def test_turn_off(self):
        with patch("bulbs.turn_off", return_value={"ok": True}) as m:
            llm.turn_off(bulb_id="desk")
            m.assert_called_once_with("desk")

    def test_toggle(self):
        with patch("bulbs.toggle", return_value={"ok": True}) as m:
            llm.toggle(bulb_id="desk")
            m.assert_called_once_with("desk")

    def test_set_brightness(self):
        with patch("bulbs.set_brightness", return_value={"ok": True}) as m:
            llm.set_brightness(brightness=50, bulb_id="desk")
            m.assert_called_once_with("desk", 50)

    def test_set_color(self):
        with patch("bulbs.set_color", return_value={"ok": True}) as m:
            llm.set_color(r=255, g=0, b=0, bulb_id="desk")
            m.assert_called_once_with("desk", 255, 0, 0)

    def test_set_color_temperature(self):
        with patch("bulbs.set_color_temp", return_value={"ok": True}) as m:
            llm.set_color_temperature(temperature=3000, bulb_id="desk")
            m.assert_called_once_with("desk", 3000)

    def test_set_hsv(self):
        with patch("bulbs.set_hsv", return_value={"ok": True}) as m:
            llm.set_hsv(hue=120, saturation=80, bulb_id="desk")
            m.assert_called_once_with("desk", 120, 80, None)

    def test_set_hsv_with_value(self):
        with patch("bulbs.set_hsv", return_value={"ok": True}) as m:
            llm.set_hsv(hue=120, saturation=80, value=50, bulb_id="desk")
            m.assert_called_once_with("desk", 120, 80, 50)

    def test_set_adjust(self):
        with patch("bulbs.set_adjust", return_value={"ok": True}) as m:
            llm.set_adjust(action="increase", prop="bright")
            m.assert_called_once_with("", "increase", "bright")

    def test_set_default(self):
        with patch("bulbs.set_default", return_value={"ok": True}) as m:
            llm.set_default()
            m.assert_called_once_with("")

    def test_set_name(self):
        with patch("bulbs.set_name", return_value={"ok": True}) as m:
            llm.set_name(name="office", bulb_id="desk")
            m.assert_called_once_with("desk", "office")

    def test_start_flow(self):
        with patch("bulbs.start_flow", return_value={"ok": True}) as m:
            llm.start_flow(flow_name="disco", bpm=140)
            m.assert_called_once_with(bulb_id="", flow_name="disco", bpm=140)

    def test_start_flow_no_extra_params(self):
        with patch("bulbs.start_flow", return_value={"ok": True}) as m:
            llm.start_flow(flow_name="strobe")
            m.assert_called_once_with(bulb_id="", flow_name="strobe")

    def test_stop_flow(self):
        with patch("bulbs.stop_flow", return_value={"ok": True}) as m:
            llm.stop_flow(bulb_id="desk")
            m.assert_called_once_with("desk")

    def test_set_scene_color(self):
        with patch("bulbs.set_scene_color", return_value={"ok": True}) as m:
            llm.set_scene_color(r=255, g=0, b=0, brightness=80, bulb_id="desk")
            m.assert_called_once_with("desk", 255, 0, 0, 80)

    def test_set_scene_ct(self):
        with patch("bulbs.set_scene_ct", return_value={"ok": True}) as m:
            llm.set_scene_ct(temperature=3000, brightness=50, bulb_id="desk")
            m.assert_called_once_with("desk", 3000, 50)

    def test_set_scene_hsv(self):
        with patch("bulbs.set_scene_hsv", return_value={"ok": True}) as m:
            llm.set_scene_hsv(hue=180, saturation=50, brightness=75, bulb_id="desk")
            m.assert_called_once_with("desk", 180, 50, 75)

    def test_set_auto_delay_off(self):
        with patch("bulbs.set_auto_delay_off", return_value={"ok": True}) as m:
            llm.set_auto_delay_off(brightness=50, minutes=10, bulb_id="desk")
            m.assert_called_once_with("desk", 50, 10)

    def test_set_sleep_timer(self):
        with patch("bulbs.set_sleep_timer", return_value={"ok": True}) as m:
            llm.set_sleep_timer(minutes=30, bulb_id="desk")
            m.assert_called_once_with("desk", 30)

    def test_cancel_sleep_timer(self):
        with patch("bulbs.cancel_sleep_timer", return_value={"ok": True}) as m:
            llm.cancel_sleep_timer(bulb_id="desk")
            m.assert_called_once_with("desk")

    def test_set_power_mode(self):
        with patch("bulbs.set_power_mode", return_value={"ok": True}) as m:
            llm.set_power_mode(mode="moonlight", bulb_id="desk")
            m.assert_called_once_with("desk", "moonlight")
