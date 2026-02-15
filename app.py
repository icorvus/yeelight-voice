import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import bulbs
import llm
import stt


@asynccontextmanager
async def lifespan(app: FastAPI):
    with contextlib.suppress(Exception):
        await asyncio.to_thread(bulbs.discover)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.post("/api/voice")
async def voice(file: UploadFile):
    audio_bytes = await file.read()
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

    response = await asyncio.to_thread(llm.chat, transcript)
    return {
        "transcript": transcript,
        "response": response,
        "bulbs": bulbs.get_all_status(),
    }


class TextRequest(BaseModel):
    text: str


@app.post("/api/text")
async def text(req: TextRequest):
    response = await asyncio.to_thread(llm.chat, req.text)
    return {
        "transcript": req.text,
        "response": response,
        "bulbs": bulbs.get_all_status(),
    }


@app.post("/api/discover")
async def discover():
    result = await asyncio.to_thread(bulbs.discover)
    return result


@app.post("/api/reset")
async def reset():
    llm.reset_history()
    return {"ok": True}
