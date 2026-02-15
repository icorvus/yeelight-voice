import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

import bulbs
import db
import llm
import stt


class BulbColor(BaseModel):
    r: int
    g: int
    b: int


class BulbStatus(BaseModel):
    id: str
    name: str
    ip: str
    power: str
    brightness: int
    color: BulbColor
    color_temp: int
    color_mode: int


class ChatResponse(BaseModel):
    transcript: str
    response: str
    bulbs: list[BulbStatus]


class DiscoverResponse(BaseModel):
    bulbs: list[str]
    count: int


class HistoryItem(BaseModel):
    transcript: str
    response: str


class ResetResponse(BaseModel):
    ok: bool


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    llm._init_history()
    try:
        result = await asyncio.to_thread(bulbs.discover)
        if not result.get("count"):
            bulbs.load_from_db()
    except Exception:
        bulbs.load_from_db()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def index():
    return FileResponse("static/index.html")


MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


@app.post("/api/voice", response_model=ChatResponse)
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


class TextRequest(BaseModel):
    text: str = Field(max_length=1000)


@app.post("/api/text", response_model=ChatResponse)
async def text(req: TextRequest):
    response = await llm.chat(req.text)
    return {
        "transcript": req.text,
        "response": response,
        "bulbs": bulbs.get_all_status(),
    }


@app.get("/api/bulbs", response_model=list[BulbStatus])
async def get_bulbs():
    return bulbs.get_all_status()


@app.post("/api/discover", response_model=DiscoverResponse)
async def discover():
    result = await asyncio.to_thread(bulbs.discover)
    return result


@app.get("/api/history", response_model=list[HistoryItem])
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


@app.post("/api/reset", response_model=ResetResponse)
async def reset():
    llm.reset_history()
    return {"ok": True}
