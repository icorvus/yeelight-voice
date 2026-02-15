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


class TestApiDiscover:
    async def test_returns_discovery_result(self, client):
        with patch("app.bulbs") as mock_bulbs:
            mock_bulbs.discover.return_value = {"bulbs": ["desk"], "count": 1}
            resp = await client.post("/api/discover")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["count"] == 1


class TestApiReset:
    async def test_resets_history(self, client):
        with patch("app.llm") as mock_llm:
            resp = await client.post("/api/reset")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {"ok": True}
        mock_llm.reset_history.assert_called_once()
