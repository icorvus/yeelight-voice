import io

from openai import OpenAI

from yeelight_voice.settings import settings

_client = OpenAI(api_key=settings.openai_api_key)


def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio bytes using OpenAI API."""
    buf = io.BytesIO(audio_bytes)
    buf.name = filename
    result = _client.audio.transcriptions.create(
        model="gpt-4o-transcribe",
        file=buf,
        prompt="The user is controlling smart home Yeelight bulbs via voice commands. "
        "The audio is in either Polish or English language.",
    )
    return result.text
