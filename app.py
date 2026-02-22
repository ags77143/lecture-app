import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from groq import Groq
import re, os, tempfile, subprocess

st.set_page_config(page_title="Lecture Study Generator", page_icon="🎓", layout="wide")

st.markdown("""
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
""", unsafe_allow_html=True)

st.markdown("""
<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:white;
            padding:35px;border-radius:15px;text-align:center;margin-bottom:30px">
    <h1 style="margin:0;font-size:36px">🎓 Lecture Study Generator</h1>
    <p style="margin:10px 0 0;font-size:16px;opacity:0.9">
        Paste any YouTube lecture URL — get notes, flashcards, quiz and more
    </p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Setup")
    st.markdown("Get a **free** Groq API key at [console.groq.com](https://console.groq.com)")
    api_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...")
    st.markdown("---")
    st.markdown("**Generates:**")
    for item in ["📝 Notes & Summary","📖 Key Terms","🃏 Flashcards","✅ Quiz","⏱️ Timeline","💡 Study Tips"]:
        st.markdown(item)

url = st.text_input("", placeholder="Paste your YouTube URL here...")
generate_btn = st.button("Generate Study Materials")

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

def transcribe_audio(url, log):
    log.write("No captions found — downloading audio with yt-dlp...")

    # Check yt-dlp is available
    check = subprocess.run(['which', 'yt-dlp'], capture_output=True, text=True)
    if not check.stdout.strip():
        log.write("yt-dlp not found, trying pip install...")
        subprocess.run(['pip', 'install', 'yt-dlp', '-q'])

    # Check ffmpeg
    check2 = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
    ffmpeg_path = check2.stdout.strip()
    log.write(f"ffmpeg path: {ffmpeg_path or 'NOT FOUND'}")

    tmpdir = tempfile.mkdtemp()
    audio_path = os.path.join(tmpdir, 'audio.%(ext)s')
    out_path = os.path.join(tmpdir, 'audio.mp3')

    cmd = [
        'yt-dlp',
        '-x',
        '--audio-format', 'mp3',
        '--audio-quality', '5',
        '-o', audio_path,
        '--no-playlist',
        url
    ]

    log.write(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    log.write(f"stdout: {result.stdout[-500:] if result.stdout else 'none'}")
    log.write(f"stderr: {result.stderr[-500:] if result.stderr else 'none'}")

    # Find the output file
    files = os.listdir(tmpdir)
    log.write(f"Files in tmpdir: {files}")

    audio_file = None
    for f in files:
        if f.startswith('audio'):
            audio_file = os.path.join(tmpdir, f)
            break

    if not audio_file:
        log.write("Audio download failed — no file found")
        return None

    log.write(f"Audio file found: {audio_file} ({os.path.getsize(audio_file)} bytes)")
    log.write("Loading Whisper model and transcribing...")

    try:
        import whisper
        model = whisper.load_model('base')
        result = model.transcribe(audio_file, fp16=False)
        os.remove(audio_file)
        return result['text']
    except Exception as e:
        log.write(f"Whisper error: {e}")
        return None

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
    'notes': 'Write a 4-5 sentence SUMMARY then DETAILED NOTES with headers and bullets covering every concept. Start with ## Summary then ## Detailed Notes',
    'terms': 'Extract 12-15 key terms.\n**[Term]**\n[Definition in 2-3 sentences]\n---\nStart with ## Key Terms & Definitions',
    'flashcards': 'Create 18 flashcards.\n**Q:** [question]\n**A:** [answer]\n---\nStart with ## Flashcards',
    'quiz': 'Create 10 multiple choice questions. Wrong answers must be plausible.\n**Question [N]: [text]**\nA) ... B) ... C) ... D) ...\nCorrect: [letter] — [explanation]\n---\n3 easy, 4 medium, 3 hard. Start with ## Quiz',
    'timeline': 'Map the lecture as a topic timeline.\n**[Topic]**\nCovered: [2-3 sentences]\nLink to next: [1 sentence]\n---\nStart with ## Topic Timeline',
    'studytips': 'Give 6 study tips SPECIFIC to this lecture content.\n**Tip [N]: [title]** — [2-3 sentences]\n---\n### What to prioritise — top 3 things\nStart with ## Study Tips',
}

SECTIONS = [
    ('notes',      '📝 Notes & Summary'),
    ('terms',      '📖 Key Terms & Definitions'),
    ('flashcards', '🃏 Flashcards'),
    ('quiz',       '✅ Multiple Choice Quiz'),
    ('timeline',   '⏱️ Topic Timeline'),
    ('studytips',  '💡 Study Tips'),
]

if generate_btn:
    if not api_key:
        st.error("Please enter your Groq API key in the sidebar.")
    elif not url:
        st.error("Please paste a YouTube URL.")
    else:
        vid = extract_video_id(url)
        if not vid:
            st.error("Could not read that URL.")
        else:
            client = Groq(api_key=api_key)
            with st.status("Working...", expanded=True) as status:
                st.write("Fetching transcript...")
                transcript = try_get_captions(vid)
                if transcript:
                    st.write(f"✅ Captions found! ({len(transcript.split()):,} words)")
                else:
                    transcript = transcribe_audio(url, st)
                if not transcript:
                    status.update(label="Failed", state="error")
                    st.stop()
                st.write(f"✅ Transcript ready. Generating study materials...")
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
                    st.markdown(results[key])
