import io
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio bytes using OpenAI Whisper API."""
    buf = io.BytesIO(audio_bytes)
    buf.name = filename
    result = _client.audio.transcriptions.create(
        model="gpt-4o-transcribe",
        file=buf,
        prompt="The user is controlling smart home Yeelight bulbs via voice commands. "
        "The audio is in either Polish or English language.",
    )
    return result.text
