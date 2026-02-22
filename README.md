# Lecture Study Generator

Turn lecture content into a complete study pack:
- Notes + summary
- Key terms + definitions
- Flashcards
- Multiple-choice quiz
- Topic timeline
- Study tips

## Inputs supported
1. YouTube URL (uses captions when available)
2. Uploaded local audio/video file (Whisper transcription)

If a YouTube video has no captions, the app downloads audio with `yt-dlp` and transcribes it with Whisper.

## Setup
```bash
pip install -r requirements.txt
```

## Run
```bash
streamlit run app.py
```

Then enter your Groq API key in the sidebar.

## Notes
- `ffmpeg` is required (listed in `packages.txt`).
- Large lectures are truncated before LLM generation to stay inside token limits.
- You can download both transcript (`.txt`) and full study pack (`.json`) from the app.
