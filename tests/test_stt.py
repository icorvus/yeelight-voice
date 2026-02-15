from unittest.mock import MagicMock, patch

import stt


class TestTranscribe:
    @patch.object(stt, "_client")
    def test_returns_text(self, mock_client):
        mock_client.audio.transcriptions.create.return_value = MagicMock(
            text="hello world"
        )
        result = stt.transcribe(b"\x00" * 200, "test.webm")
        assert result == "hello world"

    @patch.object(stt, "_client")
    def test_sets_filename(self, mock_client):
        mock_client.audio.transcriptions.create.return_value = MagicMock(text="hi")
        stt.transcribe(b"\x00" * 200, "recording.webm")
        call_kwargs = mock_client.audio.transcriptions.create.call_args
        buf = call_kwargs.kwargs.get("file") or call_kwargs[1].get("file")
        assert buf.name == "recording.webm"
