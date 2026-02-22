import json
import tempfile

import streamlit as st
from groq import Groq

from core import extract_video_id, transcribe_audio_from_youtube, transcribe_local_audio, try_get_captions

st.set_page_config(page_title="Lecture Study Generator", page_icon="🎓", layout="wide")

st.markdown(
    """
<style>
    .stButton>button {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white; border: none; padding: 12px 30px;
        border-radius: 10px; font-size: 16px; font-weight: bold;
        width: 100%;
    }
    .section-header {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white; padding: 12px 20px; border-radius: 10px;
        font-size: 20px; font-weight: bold; margin: 25px 0 10px 0;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;
            padding:35px;border-radius:15px;text-align:center;margin-bottom:30px">
    <h1 style="margin:0;font-size:36px">🎓 Lecture Study Generator</h1>
    <p style="margin:10px 0 0;font-size:16px;opacity:0.9">
        Turn a lecture into notes, key terms, flashcards, quiz, timeline, and study tips.
    </p>
</div>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Setup")
    st.markdown("Get a **free** Groq API key at [console.groq.com](https://console.groq.com)")
    api_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...")
    st.markdown("---")
    st.markdown("**Input options**")
    st.markdown("- YouTube URL")
    st.markdown("- Local audio/video file (mp3, mp4, wav, m4a)")
    st.markdown("---")
    st.markdown("**Generates:**")
    for item in ["📝 Notes & Summary", "📖 Key Terms", "🃏 Flashcards", "✅ Quiz", "⏱️ Timeline", "💡 Study Tips"]:
        st.markdown(item)

source_type = st.radio("Choose lecture source", ["YouTube URL", "Upload file"], horizontal=True)
url = ""
uploaded_file = None
if source_type == "YouTube URL":
    url = st.text_input("YouTube URL", placeholder="Paste your YouTube URL here...", label_visibility="collapsed")
else:
    uploaded_file = st.file_uploader("Upload lecture audio/video", type=["mp3", "wav", "m4a", "mp4", "mov", "mkv"])

generate_btn = st.button("Generate Study Materials")


def ask_ai(client, prompt, transcript):
    words = transcript.split()
    if len(words) > 12000:
        transcript = " ".join(words[:12000])

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are an expert academic study assistant. Generate thorough, well-structured study materials using markdown.",
            },
            {"role": "user", "content": f"{prompt}\n\n---TRANSCRIPT---\n{transcript}"},
        ],
        max_tokens=4096,
        temperature=0.3,
    )
    return response.choices[0].message.content


PROMPTS = {
    "notes": "Write a 4-5 sentence SUMMARY then DETAILED NOTES with headers and bullets covering every concept. Start with ## Summary then ## Detailed Notes",
    "terms": "Extract 12-15 key terms.\n**[Term]**\n[Definition in 2-3 sentences]\n---\nStart with ## Key Terms & Definitions",
    "flashcards": "Create 18 flashcards.\n**Q:** [question]\n**A:** [answer]\n---\nStart with ## Flashcards",
    "quiz": "Create 10 multiple choice questions. Wrong answers must be plausible.\n**Question [N]: [text]**\nA) ... B) ... C) ... D) ...\nCorrect: [letter] — [explanation]\n---\n3 easy, 4 medium, 3 hard. Start with ## Quiz",
    "timeline": "Map the lecture as a topic timeline.\n**[Topic]**\nCovered: [2-3 sentences]\nLink to next: [1 sentence]\n---\nStart with ## Topic Timeline",
    "studytips": "Give 6 study tips SPECIFIC to this lecture content.\n**Tip [N]: [title]** — [2-3 sentences]\n---\n### What to prioritise — top 3 things\nStart with ## Study Tips",
}

SECTIONS = [
    ("notes", "📝 Notes & Summary"),
    ("terms", "📖 Key Terms & Definitions"),
    ("flashcards", "🃏 Flashcards"),
    ("quiz", "✅ Multiple Choice Quiz"),
    ("timeline", "⏱️ Topic Timeline"),
    ("studytips", "💡 Study Tips"),
]

if generate_btn:
    if not api_key:
        st.error("Please enter your Groq API key in the sidebar.")
    elif source_type == "YouTube URL" and not url:
        st.error("Please paste a YouTube URL.")
    elif source_type == "Upload file" and not uploaded_file:
        st.error("Please upload a lecture file.")
    else:
        client = Groq(api_key=api_key)

        with st.status("Working...", expanded=True) as status:
            transcript = None

            if source_type == "YouTube URL":
                vid = extract_video_id(url)
                if not vid:
                    st.error("Could not read that URL.")
                    st.stop()

                st.write("Fetching transcript...")
                transcript = try_get_captions(vid)
                if transcript:
                    st.write(f"✅ Captions found! ({len(transcript.split()):,} words)")
                else:
                    transcript = transcribe_audio_from_youtube(url, st.write)
            else:
                suffix = uploaded_file.name.split(".")[-1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}") as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name
                st.write("Transcribing uploaded file with Whisper...")
                transcript = transcribe_local_audio(tmp_path, st.write)

            if not transcript:
                status.update(label="Failed — see details above", state="error")
                st.stop()

            st.write(f"✅ Transcript ready. Generating study materials ({len(transcript.split()):,} words)...")
            results = {}
            for key, title in SECTIONS:
                st.write(f"Generating {title}...")
                try:
                    results[key] = ask_ai(client, PROMPTS[key], transcript)
                except Exception as error:
                    results[key] = f"Error: {error}"

            status.update(label="Done!", state="complete")

        for key, title in SECTIONS:
            if key in results:
                st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)
                st.markdown(results[key])

        st.download_button(
            "Download transcript (.txt)",
            data=transcript,
            file_name="lecture_transcript.txt",
            mime="text/plain",
        )
        st.download_button(
            "Download full study pack (.json)",
            data=json.dumps(results, indent=2),
            file_name="study_pack.json",
            mime="application/json",
        )
