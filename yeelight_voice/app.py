import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from yeelight_voice.api.routes import router
from yeelight_voice.core import bulbs, db
from yeelight_voice.services import llm

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


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
app.include_router(router)


@app.get("/")
async def index():
    return FileResponse(_STATIC_DIR / "index.html")
