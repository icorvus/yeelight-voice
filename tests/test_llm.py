from unittest.mock import MagicMock, patch

import pytest

import llm


@pytest.fixture(autouse=True)
def _reset():
    llm._history.clear()
    yield
    llm._history.clear()


def _make_response(content=None, tool_calls=None):
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    msg.model_dump.return_value = {
        "role": "assistant",
        "content": content,
        "tool_calls": (
            [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ]
            if tool_calls
            else None
        ),
    }
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    return resp


def _make_tool_call(tc_id, name, arguments="{}"):
    tc = MagicMock()
    tc.id = tc_id
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


class TestGetVisibleHistory:
    def test_returns_user_and_assistant(self):
        llm._history.extend(
            [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
            ]
        )
        result = llm.get_visible_history()
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "hello"}
        assert result[1] == {"role": "assistant", "content": "hi there"}

    def test_filters_tool_messages(self):
        llm._history.extend(
            [
                {"role": "user", "content": "find bulbs"},
                {"role": "assistant", "content": None, "tool_calls": [{"id": "tc1"}]},
                {"role": "tool", "tool_call_id": "tc1", "content": '{"count":1}'},
                {"role": "assistant", "content": "Found 1 bulb!"},
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
        llm._history.append({"role": "user", "content": "hi"})
        llm.reset_history()
        assert llm._history == []


class TestTrimHistory:
    def test_trims_when_over_max(self):
        llm._history.extend([{"role": "user", "content": str(i)} for i in range(50)])
        llm._trim_history()
        assert len(llm._history) == llm.MAX_HISTORY

    def test_noop_when_short(self):
        llm._history.extend([{"role": "user", "content": "hi"}])
        llm._trim_history()
        assert len(llm._history) == 1


class TestBuildMessages:
    @patch("bulbs.get_all_status", return_value=[])
    def test_no_bulbs(self, mock_status):
        llm._history.append({"role": "user", "content": "hello"})
        msgs = llm._build_messages()
        assert msgs[0]["role"] == "system"
        assert "Current bulb state" not in msgs[0]["content"]
        assert msgs[-1]["content"] == "hello"

    @patch(
        "bulbs.get_all_status",
        return_value=[{"id": "desk", "power": "on"}],
    )
    def test_with_bulbs(self, mock_status):
        msgs = llm._build_messages()
        assert "Current bulb state" in msgs[0]["content"]


class TestChat:
    @patch("bulbs.get_all_status", return_value=[])
    @patch.object(llm, "_client")
    def test_simple_response(self, mock_client, mock_status):
        mock_client.chat.completions.create.return_value = _make_response(
            content="Hello!"
        )
        result = llm.chat("hi")
        assert result == "Hello!"
        assert any(m["content"] == "Hello!" for m in llm._history)

    @patch("bulbs.get_all_status", return_value=[])
    @patch.object(llm, "_client")
    def test_with_tool_call(self, mock_client, mock_status):
        tc = _make_tool_call("tc1", "discover_bulbs")
        mock_client.chat.completions.create.side_effect = [
            _make_response(tool_calls=[tc]),
            _make_response(content="Found 2 bulbs!"),
        ]
        with patch.dict(llm._dispatch, {"discover_bulbs": lambda **_: {"count": 2}}):
            result = llm.chat("find bulbs")
        assert result == "Found 2 bulbs!"

    @patch("bulbs.get_all_status", return_value=[])
    @patch.object(llm, "_client")
    def test_unknown_tool(self, mock_client, mock_status):
        tc = _make_tool_call("tc1", "nonexistent_tool")
        mock_client.chat.completions.create.side_effect = [
            _make_response(tool_calls=[tc]),
            _make_response(content="Error occurred"),
        ]
        llm.chat("do something")
        tool_msgs = [m for m in llm._history if m.get("role") == "tool"]
        assert any("Unknown tool" in m["content"] for m in tool_msgs)

    @patch("bulbs.get_all_status", return_value=[])
    @patch.object(llm, "_client")
    def test_max_rounds_exceeded(self, mock_client, mock_status):
        tc = _make_tool_call("tc1", "discover_bulbs")
        mock_client.chat.completions.create.return_value = _make_response(
            tool_calls=[tc]
        )
        with patch.dict(llm._dispatch, {"discover_bulbs": lambda **_: {"count": 0}}):
            result = llm.chat("loop forever")
        assert result == "Sorry, I wasn't able to complete that action."

    @patch("bulbs.get_all_status", return_value=[])
    @patch.object(llm, "_client")
    def test_toggle_dispatch(self, mock_client, mock_status):
        tc = _make_tool_call("tc1", "toggle", '{"bulb_id": "desk"}')
        mock_client.chat.completions.create.side_effect = [
            _make_response(tool_calls=[tc]),
            _make_response(content="Toggled!"),
        ]
        with patch.dict(llm._dispatch, {"toggle": lambda **kw: {"ok": True}}):
            result = llm.chat("toggle the light")
        assert result == "Toggled!"

    @patch("bulbs.get_all_status", return_value=[])
    @patch.object(llm, "_client")
    def test_start_flow_dispatch(self, mock_client, mock_status):
        tc = _make_tool_call("tc1", "start_flow", '{"flow_name": "disco", "bpm": 140}')
        mock_client.chat.completions.create.side_effect = [
            _make_response(tool_calls=[tc]),
            _make_response(content="Disco time!"),
        ]
        captured = {}

        def fake_start_flow(**kw):
            captured.update(kw)
            return {"ok": True}

        with patch.dict(llm._dispatch, {"start_flow": fake_start_flow}):
            result = llm.chat("start disco")
        assert result == "Disco time!"
        assert captured["flow_name"] == "disco"
        assert captured["bpm"] == 140

    @patch("bulbs.get_all_status", return_value=[])
    @patch.object(llm, "_client")
    def test_sleep_timer_dispatch(self, mock_client, mock_status):
        tc = _make_tool_call("tc1", "set_sleep_timer", '{"minutes": 30}')
        mock_client.chat.completions.create.side_effect = [
            _make_response(tool_calls=[tc]),
            _make_response(content="Timer set!"),
        ]
        with patch.dict(
            llm._dispatch,
            {"set_sleep_timer": lambda **kw: {"ok": True}},
        ):
            result = llm.chat("turn off in 30 min")
        assert result == "Timer set!"


class TestDispatchWiring:
    """Verify _dispatch entries call the right bulbs functions."""

    def test_all_tools_have_dispatch(self):
        tool_names = {t["function"]["name"] for t in llm.TOOLS}
        dispatch_names = set(llm._dispatch.keys())
        assert tool_names == dispatch_names

    def test_toggle(self):
        with patch("bulbs.toggle", return_value={"ok": True}) as m:
            llm._dispatch["toggle"](bulb_id="desk")
            m.assert_called_once_with("desk")

    def test_set_hsv(self):
        with patch("bulbs.set_hsv", return_value={"ok": True}) as m:
            llm._dispatch["set_hsv"](bulb_id="desk", hue=120, saturation=80)
            m.assert_called_once_with("desk", 120, 80, None)

    def test_set_hsv_with_value(self):
        with patch("bulbs.set_hsv", return_value={"ok": True}) as m:
            llm._dispatch["set_hsv"](bulb_id="desk", hue=120, saturation=80, value=50)
            m.assert_called_once_with("desk", 120, 80, 50)

    def test_set_adjust(self):
        with patch("bulbs.set_adjust", return_value={"ok": True}) as m:
            llm._dispatch["set_adjust"](action="increase", prop="bright")
            m.assert_called_once_with("", "increase", "bright")

    def test_set_default(self):
        with patch("bulbs.set_default", return_value={"ok": True}) as m:
            llm._dispatch["set_default"]()
            m.assert_called_once_with("")

    def test_set_name(self):
        with patch("bulbs.set_name", return_value={"ok": True}) as m:
            llm._dispatch["set_name"](bulb_id="desk", name="office")
            m.assert_called_once_with("desk", "office")

    def test_start_flow(self):
        with patch("bulbs.start_flow", return_value={"ok": True}) as m:
            llm._dispatch["start_flow"](flow_name="disco", bpm=140)
            m.assert_called_once_with(bulb_id="", flow_name="disco", bpm=140)

    def test_stop_flow(self):
        with patch("bulbs.stop_flow", return_value={"ok": True}) as m:
            llm._dispatch["stop_flow"](bulb_id="desk")
            m.assert_called_once_with("desk")

    def test_set_scene_color(self):
        with patch("bulbs.set_scene_color", return_value={"ok": True}) as m:
            llm._dispatch["set_scene_color"](
                bulb_id="desk", r=255, g=0, b=0, brightness=80
            )
            m.assert_called_once_with("desk", 255, 0, 0, 80)

    def test_set_scene_ct(self):
        with patch("bulbs.set_scene_ct", return_value={"ok": True}) as m:
            llm._dispatch["set_scene_ct"](
                bulb_id="desk", temperature=3000, brightness=50
            )
            m.assert_called_once_with("desk", 3000, 50)

    def test_set_scene_hsv(self):
        with patch("bulbs.set_scene_hsv", return_value={"ok": True}) as m:
            llm._dispatch["set_scene_hsv"](
                bulb_id="desk", hue=180, saturation=50, brightness=75
            )
            m.assert_called_once_with("desk", 180, 50, 75)

    def test_set_auto_delay_off(self):
        with patch("bulbs.set_auto_delay_off", return_value={"ok": True}) as m:
            llm._dispatch["set_auto_delay_off"](
                bulb_id="desk", brightness=50, minutes=10
            )
            m.assert_called_once_with("desk", 50, 10)

    def test_set_sleep_timer(self):
        with patch("bulbs.set_sleep_timer", return_value={"ok": True}) as m:
            llm._dispatch["set_sleep_timer"](bulb_id="desk", minutes=30)
            m.assert_called_once_with("desk", 30)

    def test_cancel_sleep_timer(self):
        with patch("bulbs.cancel_sleep_timer", return_value={"ok": True}) as m:
            llm._dispatch["cancel_sleep_timer"](bulb_id="desk")
            m.assert_called_once_with("desk")

    def test_set_power_mode(self):
        with patch("bulbs.set_power_mode", return_value={"ok": True}) as m:
            llm._dispatch["set_power_mode"](bulb_id="desk", mode="moonlight")
            m.assert_called_once_with("desk", "moonlight")
