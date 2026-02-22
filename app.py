import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from groq import Groq
import re, os, tempfile, whisper

st.set_page_config(page_title="Lecture Study Generator", page_icon="🎓", layout="wide")

st.markdown("""
<style>
    .main { background: #f0f2f6; }
    .stButton>button {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white; border: none; padding: 12px 30px;
        border-radius: 10px; font-size: 16px; font-weight: bold;
        width: 100%; cursor: pointer;
    }
    .section-header {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white; padding: 12px 20px; border-radius: 10px;
        font-size: 20px; font-weight: bold; margin: 25px 0 10px 0;
    }
    .section-body {
        background: white; border-left: 4px solid #667eea;
        padding: 20px; border-radius: 0 10px 10px 0;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────
st.markdown("""
<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;
            padding:35px;border-radius:15px;text-align:center;margin-bottom:30px">
    <h1 style="margin:0;font-size:36px">🎓 Lecture Study Generator</h1>
    <p style="margin:10px 0 0;font-size:16px;opacity:0.9">
        Paste any YouTube lecture URL — get notes, flashcards, quiz and more
    </p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar — API Key ────────────────────────────────────────
with st.sidebar:
    st.markdown("### Setup")
    st.markdown("Get a **free** Groq API key at [console.groq.com](https://console.groq.com)")
    api_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...")
    st.markdown("---")
    st.markdown("**What gets generated:**")
    st.markdown("📝 Notes & Summary")
    st.markdown("📖 Key Terms")
    st.markdown("🃏 Flashcards")
    st.markdown("✅ Quiz")
    st.markdown("⏱️ Topic Timeline")
    st.markdown("💡 Study Tips")
    st.markdown("---")
    st.markdown("Works on any YouTube video — even livestreams with no captions.")

# ── Main input ───────────────────────────────────────────────
url = st.text_input("", placeholder="Paste your YouTube URL here e.g. https://youtube.com/watch?v=...")
generate_btn = st.button("Generate Study Materials")

# ── Helpers ──────────────────────────────────────────────────
def extract_video_id(url):
    for p in [r'(?:v=|\/)([0-9A-Za-z_-]{11})', r'youtu\.be\/([0-9A-Za-z_-]{11})']:
        m = re.search(p, url)
        if m: return m.group(1)
    return None

def try_get_captions(video_id):
    try:
        data = YouTubeTranscriptApi.get_transcript(video_id)
        text = ' '.join([t['text'] for t in data])
        if len(text.split()) > 50:
            return text
    except:
        pass
    try:
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
        for t in transcripts:
            data = t.fetch()
            text = ' '.join([x['text'] for x in data])
            if len(text.split()) > 50:
                return text
    except:
        pass
    return None

def transcribe_audio(url, progress):
    progress.write("No captions found. Downloading audio (this takes a few minutes)...")
    tmpdir = tempfile.mkdtemp()
    audio_path = os.path.join(tmpdir, 'audio.mp3')
    os.system(f'yt-dlp -x --audio-format mp3 --audio-quality 5 -o "{audio_path}" "{url}" -q')
    if not os.path.exists(audio_path):
        matches = [f for f in os.listdir(tmpdir) if f.startswith('audio')]
        if matches:
            audio_path = os.path.join(tmpdir, matches[0])
        else:
            return None
    progress.write("Transcribing with Whisper AI...")
    model = whisper.load_model('base')
    result = model.transcribe(audio_path, fp16=False)
    os.remove(audio_path)
    return result['text']

def ask_ai(client, prompt, transcript):
    words = transcript.split()
    if len(words) > 12000:
        transcript = ' '.join(words[:12000])
    response = client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[
            {'role': 'system', 'content': 'You are an expert academic study assistant. Generate thorough, well-structured study materials using markdown.'},
            {'role': 'user', 'content': f'{prompt}\n\n---TRANSCRIPT---\n{transcript}'}
        ],
        max_tokens=4096,
        temperature=0.3
    )
    return response.choices[0].message.content

PROMPTS = {
    'notes': '''Write a 4-5 sentence SUMMARY then DETAILED NOTES with headers and bullets covering every concept.
A student should be able to study entirely from these. Start with ## Summary then ## Detailed Notes''',
    'terms': '''Extract 12-15 key terms.
**[Term]**
[Definition in 2-3 sentences from this lecture]
---
Start with ## Key Terms & Definitions''',
    'flashcards': '''Create 18 flashcards for spaced repetition.
**Q:** [question]
**A:** [answer in 1-3 sentences]
---
Start with ## Flashcards''',
    'quiz': '''Create a 10-question multiple choice quiz. Wrong answers must be plausible.
**Question [N]: [text]**
A) ... B) ... C) ... D) ...
Correct: [letter] — [explanation]
---
3 easy, 4 medium, 3 hard. Start with ## Quiz''',
    'timeline': '''Map the lecture as a topic timeline in order taught.
**[Topic]**
Covered: [2-3 sentences]
Link to next: [1 sentence]
---
Start with ## Topic Timeline''',
    'studytips': '''Give 6 study tips SPECIFIC to this lecture. Every tip must reference actual concepts from the video.
**Tip [N]: [title]** — [2-3 specific sentences]
---
End with ### What to prioritise — top 3 things from this lecture.
Start with ## Study Tips''',
}

SECTIONS = [
    ('notes',      '📝 Notes & Summary'),
    ('terms',      '📖 Key Terms & Definitions'),
    ('flashcards', '🃏 Flashcards'),
    ('quiz',       '✅ Multiple Choice Quiz'),
    ('timeline',   '⏱️ Topic Timeline'),
    ('studytips',  '💡 Study Tips'),
]

# ── Run ───────────────────────────────────────────────────────
if generate_btn:
    if not api_key:
        st.error("Please enter your Groq API key in the sidebar first.")
    elif not url:
        st.error("Please paste a YouTube URL.")
    else:
        vid = extract_video_id(url)
        if not vid:
            st.error("Could not read that URL. Make sure it is a valid YouTube link.")
        else:
            client = Groq(api_key=api_key)
            with st.status("Working...", expanded=True) as status:
                st.write("Fetching transcript...")
                transcript = try_get_captions(vid)
                if transcript:
                    st.write(f"Captions found! ({len(transcript.split()):,} words)")
                else:
                    transcript = transcribe_audio(url, st)
                if not transcript:
                    st.error("Could not get transcript. Video may be private or age-restricted.")
                    st.stop()
                st.write(f"Generating all study materials...")
                results = {}
                for key, title in SECTIONS:
                    st.write(f"Generating {title}...")
                    try:
                        results[key] = ask_ai(client, PROMPTS[key], transcript)
                    except Exception as e:
                        results[key] = f"Error: {e}"
                status.update(label="Done!", state="complete")

            for key, title in SECTIONS:
                if key in results:
                    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="section-body">', unsafe_allow_html=True)
                    st.markdown(results[key])
                    st.markdown('</div>', unsafe_allow_html=True)
