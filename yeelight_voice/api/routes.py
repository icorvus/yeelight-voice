import asyncio

from fastapi import APIRouter, UploadFile, status
from fastapi.responses import JSONResponse

from yeelight_voice.api.models import (
    BulbStatus,
    ChatResponse,
    DiscoverResponse,
    HistoryItem,
    ResetResponse,
    TextRequest,
)
from yeelight_voice.core import bulbs
from yeelight_voice.services import llm, stt

router = APIRouter(prefix="/api")

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


@router.post("/voice", response_model=ChatResponse)
async def voice(file: UploadFile):
    audio_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(audio_bytes) > MAX_UPLOAD_BYTES:
        return JSONResponse(
            {"error": "Audio file too large (max 25 MB)"},
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        )
    if len(audio_bytes) < 100:
        return JSONResponse(
            {"error": "Audio too short"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    filename = file.filename or "audio.webm"
    transcript = await asyncio.to_thread(stt.transcribe, audio_bytes, filename)

    if not transcript.strip():
        return {
            "transcript": "",
            "response": "I didn't catch that. Could you try again?",
            "bulbs": bulbs.get_all_status(),
        }

    response = await llm.chat(transcript)
    return {
        "transcript": transcript,
        "response": response,
        "bulbs": bulbs.get_all_status(),
    }


@router.post("/text", response_model=ChatResponse)
async def text(req: TextRequest):
    response = await llm.chat(req.text)
    return {
        "transcript": req.text,
        "response": response,
        "bulbs": bulbs.get_all_status(),
    }


@router.get("/bulbs", response_model=list[BulbStatus])
async def get_bulbs():
    return bulbs.get_all_status()


@router.post("/discover", response_model=DiscoverResponse)
async def discover():
    result = await asyncio.to_thread(bulbs.discover)
    return result


@router.get("/history", response_model=list[HistoryItem])
async def history():
    """Return user/assistant message pairs for the UI chat history."""
    pairs = []
    last_user = None
    for msg in llm.get_visible_history():
        if msg["role"] == "user":
            last_user = msg["content"]
        elif msg["role"] == "assistant" and last_user is not None:
            pairs.append({"transcript": last_user, "response": msg["content"]})
            last_user = None
    return pairs


@router.post("/reset", response_model=ResetResponse)
async def reset():
    llm.reset_history()
    return {"ok": True}
