from unittest.mock import patch

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestIndex:
    async def test_returns_200(self, client):
        resp = await client.get("/")
        assert resp.status_code == status.HTTP_200_OK


class TestApiText:
    async def test_returns_transcript_and_response(self, client):
        with (
            patch("app.llm") as mock_llm,
            patch("app.bulbs") as mock_bulbs,
        ):
            mock_llm.chat.return_value = "Turned on!"
            mock_bulbs.get_all_status.return_value = []
            resp = await client.post(
                "/api/text", json={"text": "turn on the light"}
            )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["transcript"] == "turn on the light"
        assert data["response"] == "Turned on!"
        assert data["bulbs"] == []


class TestApiVoice:
    async def test_rejects_short_audio(self, client):
        resp = await client.post(
            "/api/voice",
            files={"file": ("audio.webm", b"\x00" * 50, "audio/webm")},
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "too short" in resp.json()["error"].lower()

    async def test_valid_audio(self, client):
        with (
            patch("app.stt") as mock_stt,
            patch("app.llm") as mock_llm,
            patch("app.bulbs") as mock_bulbs,
        ):
            mock_stt.transcribe.return_value = "turn on"
            mock_llm.chat.return_value = "Done!"
            mock_bulbs.get_all_status.return_value = []
            resp = await client.post(
                "/api/voice",
                files={"file": ("audio.webm", b"\x00" * 200, "audio/webm")},
            )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["transcript"] == "turn on"
        assert data["response"] == "Done!"

    async def test_empty_transcript(self, client):
        with (
            patch("app.stt") as mock_stt,
            patch("app.bulbs") as mock_bulbs,
        ):
            mock_stt.transcribe.return_value = "   "
            mock_bulbs.get_all_status.return_value = []
            resp = await client.post(
                "/api/voice",
                files={"file": ("audio.webm", b"\x00" * 200, "audio/webm")},
            )
        assert resp.status_code == status.HTTP_200_OK
        assert "didn't catch" in resp.json()["response"].lower()


class TestApiBulbs:
    async def test_returns_bulb_list(self, client):
        with patch("app.bulbs") as mock_bulbs:
            mock_bulbs.get_all_status.return_value = [
                {
                    "id": "0x1",
                    "name": "desk",
                    "ip": "192.168.1.10",
                    "power": "on",
                    "brightness": 80,
                    "color": {"r": 255, "g": 0, "b": 0},
                    "color_temp": 4000,
                    "color_mode": 1,
                }
            ]
            resp = await client.get("/api/bulbs")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "desk"
        assert data[0]["color"] == {"r": 255, "g": 0, "b": 0}

    async def test_returns_empty_list(self, client):
        with patch("app.bulbs") as mock_bulbs:
            mock_bulbs.get_all_status.return_value = []
            resp = await client.get("/api/bulbs")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == []


class TestApiDiscover:
    async def test_returns_discovery_result(self, client):
        with patch("app.bulbs") as mock_bulbs:
            mock_bulbs.discover.return_value = {"bulbs": ["desk"], "count": 1}
            resp = await client.post("/api/discover")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["count"] == 1


class TestApiHistory:
    async def test_returns_pairs(self, client):
        with patch("app.llm") as mock_llm:
            mock_llm.get_visible_history.return_value = [
                {"role": "user", "content": "turn on"},
                {"role": "assistant", "content": "Done!"},
                {"role": "user", "content": "set blue"},
                {"role": "assistant", "content": "Set to blue."},
            ]
            resp = await client.get("/api/history")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert len(data) == 2
        assert data[0] == {"transcript": "turn on", "response": "Done!"}
        assert data[1] == {"transcript": "set blue", "response": "Set to blue."}

    async def test_empty_history(self, client):
        with patch("app.llm") as mock_llm:
            mock_llm.get_visible_history.return_value = []
            resp = await client.get("/api/history")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == []

    async def test_ignores_unpaired_user_message(self, client):
        with patch("app.llm") as mock_llm:
            mock_llm.get_visible_history.return_value = [
                {"role": "user", "content": "hello"},
            ]
            resp = await client.get("/api/history")
        assert resp.json() == []


class TestApiReset:
    async def test_resets_history(self, client):
        with patch("app.llm") as mock_llm:
            resp = await client.post("/api/reset")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {"ok": True}
        mock_llm.reset_history.assert_called_once()
