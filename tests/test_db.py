import json
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
        assert "message_runs" in names
        assert "bulbs" in names

    def test_idempotent(self):
        db.init()
        db.init()
        assert db.load_all_messages_json() is None


class TestSaveAndLoadMessagesJson:
    def test_save_and_load_single_run(self):
        msgs = [{"kind": "request", "parts": [{"content": "hello"}]}]
        db.save_messages_json(json.dumps(msgs).encode())
        loaded = db.load_all_messages_json()
        assert loaded is not None
        assert json.loads(loaded) == msgs

    def test_multi_run_merge(self):
        run1 = [{"kind": "request", "parts": [{"content": "hello"}]}]
        run2 = [{"kind": "response", "parts": [{"content": "hi"}]}]
        db.save_messages_json(json.dumps(run1).encode())
        db.save_messages_json(json.dumps(run2).encode())
        loaded = db.load_all_messages_json()
        assert loaded is not None
        merged = json.loads(loaded)
        assert len(merged) == 2
        assert merged[0] == run1[0]
        assert merged[1] == run2[0]

    def test_empty(self):
        assert db.load_all_messages_json() is None


class TestClearMessages:
    def test_clear(self):
        msgs = [{"kind": "request"}]
        db.save_messages_json(json.dumps(msgs).encode())
        db.clear_messages()
        assert db.load_all_messages_json() is None

    def test_clear_empty(self):
        db.clear_messages()
        assert db.load_all_messages_json() is None


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
        assert by_id["desk"] == {
            "bulb_id": "desk",
            "name": "desk",
            "ip": "192.168.1.10",
        }
        assert by_id["lamp"] == {
            "bulb_id": "lamp",
            "name": "lamp",
            "ip": "192.168.1.11",
        }

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
