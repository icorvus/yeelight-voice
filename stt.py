import io
import os
from openai import OpenAI

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio bytes using OpenAI Whisper API."""
    buf = io.BytesIO(audio_bytes)
    buf.name = filename
    result = _client.audio.transcriptions.create(model="gpt-4o-transcribe", file=buf)
    return result.text
