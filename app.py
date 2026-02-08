import streamlit as st
from groq import Groq
import sqlite3
import speech_recognition as sr
import edge_tts
import asyncio
import re
import os
import time
import json
import random
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment
import io
import pandas as pd

# --- CONFIGURATION ---
st.set_page_config(page_title="AI English Academy", page_icon="🏫", layout="wide")

# --- 1. CURRICULUM ---
CURRICULUM = {
    "Level 1: Foundation (Beginner)": [
        "1. Basic Greetings & Introductions",
        "2. Articles (A, An, The)",
        "3. To Be (Am, Is, Are)",
        "4. Nouns & Plurals (Cat -> Cats)",
        "5. Adjectives (Describing Colors/Size)",
        "6. Present Simple (Daily Habits)"
    ],
    "Level 2: Building Sentences (Intermediate)": [
        "7. Present Continuous (Happening Now)",
        "8. Past Simple (Yesterday)",
        "9. Future with 'Will' vs 'Going to'",
        "10. Prepositions (In, On, At)",
        "11. Modals (Can, Should, Must)"
    ],
    "Level 3: Fluency (Advanced)": [
        "12. Present Perfect (Have you ever...)",
        "13. Conditionals (If... then...)",
        "14. Passive Voice",
        "15. Phrasal Verbs",
        "16. Business Email Writing"
    ]
}

# --- 2. VERB DATABASE (5 Forms) ---
INITIAL_VERBS = [
    ("be", "was/were", "been", "being", "is"),
    ("have", "had", "had", "having", "has"),
    ("do", "did", "done", "doing", "does"),
    ("say", "said", "said", "saying", "says"),
    ("go", "went", "gone", "going", "goes"),
    ("get", "got", "gotten", "getting", "gets"),
    ("make", "made", "made", "making", "makes"),
    ("know", "knew", "known", "knowing", "knows"),
    ("think", "thought", "thought", "thinking", "thinks"),
    ("take", "took", "taken", "taking", "takes"),
    ("see", "saw", "seen", "seeing", "sees"),
    ("come", "came", "come", "coming", "comes"),
    ("want", "wanted", "wanted", "wanting", "wants"),
    ("look", "looked", "looked", "looking", "looks"),
    ("use", "used", "used", "using", "uses"),
    ("find", "found", "found", "finding", "finds"),
    ("give", "gave", "given", "giving", "gives"),
    ("tell", "told", "told", "telling", "tells"),
    ("work", "worked", "worked", "working", "works"),
    ("call", "called", "called", "calling", "calls"),
    ("try", "tried", "tried", "trying", "tries"),
    ("ask", "asked", "asked", "asking", "asks"),
    ("need", "needed", "needed", "needing", "needs"),
    ("feel", "felt", "felt", "feeling", "feels"),
    ("become", "became", "become", "becoming", "becomes"),
    ("leave", "left", "left", "leaving", "leaves"),
    ("put", "put", "put", "putting", "puts"),
    ("mean", "meant", "meant", "meaning", "means"),
    ("keep", "kept", "kept", "keeping", "keeps"),
    ("let", "let", "let", "letting", "lets"),
    ("begin", "began", "begun", "beginning", "begins"),
    ("seem", "seemed", "seemed", "seeming", "seems"),
    ("help", "helped", "helped", "helping", "helps"),
    ("talk", "talked", "talked", "talking", "talks"),
    ("turn", "turned", "turned", "turning", "turns"),
    ("start", "started", "started", "starting", "starts"),
    ("show", "showed", "shown", "showing", "shows"),
    ("hear", "heard", "heard", "hearing", "hears"),
    ("play", "played", "played", "playing", "plays"),
    ("run", "ran", "run", "running", "runs"),
    ("move", "moved", "moved", "moving", "moves"),
    ("like", "liked", "liked", "liking", "likes"),
    ("live", "lived", "lived", "living", "lives"),
    ("believe", "believed", "believed", "believing", "believes"),
    ("hold", "held", "held", "holding", "holds"),
    ("bring", "brought", "brought", "bringing", "brings"),
    ("happen", "happened", "happened", "happening", "happens"),
    ("write", "wrote", "written", "writing", "writes"),
    ("provide", "provided", "provided", "providing", "provides"),
    ("sit", "sat", "sat", "sitting", "sits")
]

def init_db():
    conn = sqlite3.connect("english_hybrid_v1.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS verbs (v1 TEXT UNIQUE, v2 TEXT, v3 TEXT, v4 TEXT, v5 TEXT)")
    c.execute("SELECT count(*) FROM verbs")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT OR IGNORE INTO verbs VALUES (?, ?, ?, ?, ?)", INITIAL_VERBS)
        conn.commit()
    conn.close()

def get_verbs():
    conn = sqlite3.connect("english_hybrid_v1.db")
    c = conn.cursor()
    c.execute("SELECT * FROM verbs ORDER BY v1 ASC")
    data = c.fetchall()
    conn.close()
    return data

# --- AI ENGINE ---
@st.cache_data(show_spinner=False)
def get_groq_response(prompt, api_key):
    try:
        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system", 
                    "content": "You are a friendly English Tutor. Explain simply. Always return JSON."
                },
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"ERROR: {e}"

def generate_safe(api_key, prompt):
    with st.spinner("🧠 Teacher is thinking..."):
        text = get_groq_response(prompt, api_key)
    return text

# --- VOICE & AVATAR ---
def show_avatar(is_speaking=False):
    SILENT_URL = "https://cdn-icons-png.flaticon.com/512/4140/4140048.png"
    TALKING_URL = "https://media.tenor.com/5mY0_O8AzWwAAAAi/talking-speaking.gif"
    place = st.empty()
    if is_speaking:
        place.image(TALKING_URL, width=200)
    else:
        place.image(SILENT_URL, width=200)
    return place

async def generate_human_voice(text):
    text = re.sub(r'\[.*?\]', '', text).replace("*", "").replace("#", "").replace("`", "")
    if not text.strip(): return
    communicate = edge_tts.Communicate(text, "en-IN-NeerjaNeural")
    await communicate.save("lesson_voice.mp3")

def speak_human(text):
    try:
        avatar_spot = show_avatar(is_speaking=True)
        asyncio.run(generate_human_voice(text))
        if os.path.exists("lesson_voice.mp3"):
            with open("lesson_voice.mp3", "rb") as f:
                audio_bytes = f.read()
            st.audio(audio_bytes, format="audio/mp3", autoplay=True)
            est_time = len(text.split()) / 2.5
            time.sleep(est_time)
        avatar_spot.image("https://cdn-icons-png.flaticon.com/512/4140/4140048.png", width=200)
    except Exception as e:
        st.error(f"Audio Error: {e}")

def process_audio(audio_bytes):
    if audio_bytes:
        try:
            audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
            wav_io = io.BytesIO()
            audio.export(wav_io, format="wav")
            wav_io.seek(0)
            r = sr.Recognizer()
            with sr.AudioFile(wav_io) as source:
                audio_data = r.record(source)
                return r.recognize_google(audio_data)
        except: return None
    return None

# --- APP START ---
init_db()

with st.sidebar:
    st.title("🏫 English Academy")
    name = st.text_input("Student Name:")
    try: api_key = st.secrets["GROQ_API_KEY"]
    except: api_key = st.text_input("Groq API Key:", type="password")
    
    mode = st.radio("Menu:", ["📚 Learn Topic", "📜 Verb List (5 Forms)", "💬 Practice Chat"])
    
    st.divider()
    st.write("🎙️ **Microphone**")
    audio = mic_recorder(start_prompt="Record", stop_prompt="Stop", key='recorder')
    if audio: st.session_state.voice_input = process_audio(audio['bytes'])

if "voice_input" not in st.session_state: st.session_state.voice_input = None

if api_key and name:
    st.title(f"Welcome, {name}! 🎓")
    show_avatar(is_speaking=False)

    # --- MODE 1: LEARN (TEXT + AUDIO) ---
    if mode == "📚 Learn Topic":
        st.header("📚 Classroom")
        
        phase = st.selectbox("Select Level:", list(CURRICULUM.keys()))
        topic = st.selectbox("Select Topic:", CURRICULUM[phase])
        
        if st.button("Teach Me 👩‍🏫"):
            # Prompt asks for BOTH lesson (text) AND audio_script (speech)
            prompt = f"""
            Teach the topic '{topic}' to a beginner.
            1. 'lesson': Write a simple explanation with examples in Markdown. Use emojis.
            2. 'audio_script': Write a friendly speech script (what you will SAY to the student). 
               Keep the speech simple and encouraging.
            Return ONLY JSON: {{ "lesson": "...", "audio_script": "..." }}
            """
            res = generate_safe(api_key, prompt)
            
            try:
                # Parse JSON
                json_start = res.find('{')
                json_end = res.rfind('}') + 1
                data = json.loads(res[json_start:json_end])
                
                # 1. SHOW TEXT
                st.markdown(data['lesson'])
                
                # 2. PLAY AUDIO
                st.caption("🔊 Listen to the teacher:")
                speak_human(data['audio_script'])
                
            except:
                st.error("AI Error. Please try again.")

    # --- MODE 2: VERB LIST (TEXT REFERENCE) ---
    elif mode == "📜 Verb List (5 Forms)":
        st.header("📜 Complete Verb Reference")
        st.write("Review these verbs to improve your vocabulary.")
        
        verbs = get_verbs()
        df = pd.DataFrame(verbs, columns=["Base (V1)", "Past (V2)", "Perfect (V3)", "Continuous (V4)", "Simple (V5)"])
        st.dataframe(df, use_container_width=True, height=600)

    # --- MODE 3: CHAT (TEXT + AUDIO) ---
    elif mode == "💬 Practice Chat":
        st.header("💬 Conversation Practice")
        
        # Show chat history
        if "chat" not in st.session_state: st.session_state.chat = []
        for msg in st.session_state.chat:
            st.chat_message(msg["role"]).write(msg["text"])
        
        # Handle Input
        if st.session_state.voice_input:
            user_text = st.session_state.voice_input
            st.session_state.voice_input = None
        else:
            user_text = st.chat_input("Type or Speak...")
            
        if user_text:
            # User Message
            st.session_state.chat.append({"role": "user", "text": user_text})
            st.chat_message("user").write(user_text)
            
            # AI Reply
            prompt = f"Reply to: '{user_text}'. Correct any grammar mistakes kindly. Keep it short."
            ai_reply = generate_safe(api_key, prompt)
            
            # AI Message
            st.session_state.chat.append({"role": "assistant", "text": ai_reply})
            st.chat_message("assistant").write(ai_reply)
            speak_human(ai_reply)
            st.rerun()

else:
    st.info("Please enter Name and API Key to start.")