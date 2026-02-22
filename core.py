import os
import re
import tempfile
import subprocess
from typing import Callable, Optional

from youtube_transcript_api import YouTubeTranscriptApi


def extract_video_id(url: str) -> Optional[str]:
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11})",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def try_get_captions(video_id: str) -> Optional[str]:
    try:
        data = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join([t["text"] for t in data])
        if len(text.split()) > 50:
            return text
    except Exception:
        pass

    try:
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
        for transcript in transcripts:
            data = transcript.fetch()
            text = " ".join([x["text"] for x in data])
            if len(text.split()) > 50:
                return text
    except Exception:
        pass

    return None


def _run_download_command(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def transcribe_audio_from_youtube(url: str, log: Callable[[str], None]) -> Optional[str]:
    log("No captions found — downloading audio...")

    tmpdir = tempfile.mkdtemp()
    audio_template = os.path.join(tmpdir, "audio.%(ext)s")

    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "5",
        "-o",
        audio_template,
        "--no-playlist",
        "--extractor-args",
        "youtube:player_client=web,mweb",
        "--user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "--add-header",
        "Accept-Language:en-US,en;q=0.9",
        url,
    ]

    log("Downloading audio...")
    result = _run_download_command(cmd)

    if result.returncode != 0:
        log(f"Download error: {result.stderr[-300:]}")

    audio_file = None
    for filename in os.listdir(tmpdir):
        if filename.startswith("audio"):
            audio_file = os.path.join(tmpdir, filename)
            break

    if not audio_file:
        log("Audio download failed.")
        return None

    file_size = os.path.getsize(audio_file)
    log(f"Audio downloaded ({file_size // 1024} KB). Transcribing with Whisper...")

    return transcribe_local_audio(audio_file, log)


def transcribe_local_audio(path: str, log: Callable[[str], None]) -> Optional[str]:
    try:
        import whisper

        model = whisper.load_model("base")
        result = model.transcribe(path, fp16=False)
        return result["text"]
    except Exception as error:
        log(f"Whisper error: {error}")
        return None
