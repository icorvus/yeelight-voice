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
        llm._history.extend([
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ])
        result = llm.get_visible_history()
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "hello"}
        assert result[1] == {"role": "assistant", "content": "hi there"}

    def test_filters_tool_messages(self):
        llm._history.extend([
            {"role": "user", "content": "find bulbs"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "tc1"}]},
            {"role": "tool", "tool_call_id": "tc1", "content": '{"count":1}'},
            {"role": "assistant", "content": "Found 1 bulb!"},
        ])
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
        llm._history.extend(
            [{"role": "user", "content": str(i)} for i in range(50)]
        )
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
        with patch.dict(
            llm._dispatch, {"discover_bulbs": lambda **_: {"count": 2}}
        ):
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
        with patch.dict(
            llm._dispatch, {"discover_bulbs": lambda **_: {"count": 0}}
        ):
            result = llm.chat("loop forever")
        assert result == "Sorry, I wasn't able to complete that action."
