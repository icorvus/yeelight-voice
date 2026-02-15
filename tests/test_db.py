from types import SimpleNamespace
from unittest.mock import patch

import pytest

import db


@pytest.fixture(autouse=True)
def use_in_memory_db(tmp_path):
    """Redirect db._DB_PATH to a temp file so tests never touch the real DB."""
    test_db = tmp_path / "test.db"
    with patch.object(db, "_DB_PATH", test_db):
        db.init()
        yield


class TestInit:
    def test_creates_tables(self):
        conn = db._conn()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [row["name"] for row in tables]
        assert "messages" in names
        assert "bulbs" in names

    def test_idempotent(self):
        db.init()
        db.init()
        assert db.load_messages() == []


class TestSaveAndLoadMessages:
    def test_save_and_load(self):
        db.save_message("user", "hello")
        db.save_message("assistant", "hi there")
        msgs = db.load_messages()
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "hello"}
        assert msgs[1] == {"role": "assistant", "content": "hi there"}

    def test_tool_call_id(self):
        db.save_message("tool", '{"ok": true}', tool_call_id="call_123")
        msgs = db.load_messages()
        assert len(msgs) == 1
        assert msgs[0]["tool_call_id"] == "call_123"

    def test_tool_call_id_omitted_when_none(self):
        db.save_message("user", "test")
        msgs = db.load_messages()
        assert "tool_call_id" not in msgs[0]

    def test_null_content(self):
        db.save_message("assistant", None)
        msgs = db.load_messages()
        assert msgs[0]["content"] == ""

    def test_ordering(self):
        for i in range(5):
            db.save_message("user", f"msg{i}")
        msgs = db.load_messages()
        assert [m["content"] for m in msgs] == [f"msg{i}" for i in range(5)]


class TestClearMessages:
    def test_clear(self):
        db.save_message("user", "hello")
        db.save_message("assistant", "hi")
        db.clear_messages()
        assert db.load_messages() == []

    def test_clear_empty(self):
        db.clear_messages()
        assert db.load_messages() == []


class TestSaveAndLoadBulbs:
    def _make_bulbs(self):
        return {
            "desk": SimpleNamespace(name="desk", ip="192.168.1.10"),
            "lamp": SimpleNamespace(name="lamp", ip="192.168.1.11"),
        }

    def test_save_and_load(self):
        db.save_bulbs(self._make_bulbs())
        loaded = db.load_bulbs()
        assert len(loaded) == 2
        by_id = {b["bulb_id"]: b for b in loaded}
        assert by_id["desk"] == {"bulb_id": "desk", "name": "desk", "ip": "192.168.1.10"}
        assert by_id["lamp"] == {"bulb_id": "lamp", "name": "lamp", "ip": "192.168.1.11"}

    def test_upsert(self):
        db.save_bulbs({"desk": SimpleNamespace(name="desk", ip="192.168.1.10")})
        db.save_bulbs({"desk": SimpleNamespace(name="desk", ip="192.168.1.99")})
        loaded = db.load_bulbs()
        assert len(loaded) == 1
        assert loaded[0]["ip"] == "192.168.1.99"

    def test_empty(self):
        assert db.load_bulbs() == []


class TestClearBulbs:
    def test_clear(self):
        db.save_bulbs({"desk": SimpleNamespace(name="desk", ip="192.168.1.10")})
        db.clear_bulbs()
        assert db.load_bulbs() == []

    def test_clear_empty(self):
        db.clear_bulbs()
        assert db.load_bulbs() == []
