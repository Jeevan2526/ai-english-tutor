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
import bcrypt  # <--- NEW SECURITY LIBRARY

# --- CONFIGURATION ---
st.set_page_config(page_title="AI English Academy", page_icon="🏫", layout="wide")

# --- 1. DATABASE & AUTHENTICATION ---
def init_db():
    conn = sqlite3.connect("english_academy.db")
    c = conn.cursor()
    
    # User Table (Stores Username + Hashed Password)
    c.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password BLOB)")
    
    # Verb Table
    c.execute("CREATE TABLE IF NOT EXISTS verbs (v1 TEXT UNIQUE, v2 TEXT, v3 TEXT, v4 TEXT, v5 TEXT)")
    
    # Load Initial Verbs if empty
    c.execute("SELECT count(*) FROM verbs")
    if c.fetchone()[0] == 0:
        load_verbs(c)
        
    conn.commit()
    conn.close()

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

def load_verbs(c):
    c.executemany("INSERT OR IGNORE INTO verbs VALUES (?, ?, ?, ?, ?)", INITIAL_VERBS)

def signup_user(username, password):
    conn = sqlite3.connect("english_academy.db")
    c = conn.cursor()
    try:
        # Hash the password for security
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        c.execute("INSERT INTO users VALUES (?, ?)", (username, hashed))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # Username already exists
    finally:
        conn.close()

def check_login(username, password):
    conn = sqlite3.connect("english_academy.db")
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username=?", (username,))
    data = c.fetchone()
    conn.close()
    
    if data:
        # Check if password matches the hash
        return bcrypt.checkpw(password.encode('utf-8'), data[0])
    return False

def get_verbs():
    conn = sqlite3.connect("english_academy.db")
    c = conn.cursor()
    c.execute("SELECT * FROM verbs ORDER BY v1 ASC")
    data = c.fetchall()
    conn.close()
    return data

# --- 2. CURRICULUM ---
CURRICULUM = {
    "Level 1: Foundation": ["1. Greetings", "2. Articles", "3. To Be", "4. Present Simple"],
    "Level 2: Building": ["5. Past Simple", "6. Future Tense", "7. Modals", "8. Prepositions"],
    "Level 3: Fluency": ["9. Present Perfect", "10. Conditionals", "11. Passive Voice", "12. Business Email"]
}

# --- 3. AI ENGINE ---
@st.cache_data(show_spinner=False)
def get_groq_response(prompt, api_key):
    try:
        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a friendly English Tutor. Explain simply. Return JSON."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"ERROR: {e}"

def generate_safe(api_key, prompt):
    with st.spinner("🧠 Thinking..."):
        text = get_groq_response(prompt, api_key)
    return text

# --- 4. VOICE & AVATAR ---
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

# --- MAIN APP FLOW ---
init_db()

# --- AUTHENTICATION CHECK ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

if not st.session_state.logged_in:
    # SHOW LOGIN PAGE
    st.title("🏫 AI English Academy")
    tab1, tab2 = st.tabs(["🔑 Login", "📝 Sign Up"])
    
    with tab1:
        st.subheader("Login to your account")
        login_user = st.text_input("Username", key="login_user")
        login_pass = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if check_login(login_user, login_pass):
                st.session_state.logged_in = True
                st.session_state.username = login_user
                st.success("Login Successful!")
                st.rerun()
            else:
                st.error("Invalid Username or Password")

    with tab2:
        st.subheader("Create a New Account")
        new_user = st.text_input("Choose Username", key="new_user")
        new_pass = st.text_input("Choose Password", type="password", key="new_pass")
        if st.button("Sign Up"):
            if signup_user(new_user, new_pass):
                st.success("Account Created! You can now Login.")
            else:
                st.error("Username already taken. Try another.")

else:
    # SHOW MAIN APP (Only if logged in)
    with st.sidebar:
        st.title(f"👤 {st.session_state.username}")
        
        try: api_key = st.secrets["GROQ_API_KEY"]
        except: api_key = st.text_input("Groq API Key:", type="password")
        
        mode = st.radio("Menu:", ["📚 Learn Topic", "📜 Verb List", "💬 Practice Chat"])
        
        st.divider()
        st.write("🎙️ **Microphone**")
        audio = mic_recorder(start_prompt="Record", stop_prompt="Stop", key='recorder')
        if audio: st.session_state.voice_input = process_audio(audio['bytes'])
        
        st.divider()
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()

    if "voice_input" not in st.session_state: st.session_state.voice_input = None

    if api_key:
        st.title("🏫 English Academy")
        show_avatar(is_speaking=False)

        # --- MODE 1: LEARN ---
        if mode == "📚 Learn Topic":
            st.header("📚 Classroom")
            phase = st.selectbox("Select Level:", list(CURRICULUM.keys()))
            topic = st.selectbox("Select Topic:", CURRICULUM[phase])
            if st.button("Teach Me 👩‍🏫"):
                prompt = f"""
                Teach '{topic}'. 
                1. 'lesson': Simple Markdown explanation.
                2. 'audio_script': Friendly speech script.
                Return JSON: {{ "lesson": "...", "audio_script": "..." }}
                """
                res = generate_safe(api_key, prompt)
                try:
                    data = json.loads(res[res.find('{'):res.rfind('}')+1])
                    st.markdown(data['lesson'])
                    st.caption("🔊 Listen:")
                    speak_human(data['audio_script'])
                except: st.error("AI Error.")

        # --- MODE 2: VERB LIST ---
        elif mode == "📜 Verb List":
            st.header("📜 Verb Reference")
            verbs = get_verbs()
            df = pd.DataFrame(verbs, columns=["Base (V1)", "Past (V2)", "Perfect (V3)", "Continuous (V4)", "Simple (V5)"])
            st.dataframe(df, use_container_width=True, height=600)

        # --- MODE 3: CHAT ---
        elif mode == "💬 Practice Chat":
            st.header("💬 Conversation")
            if "chat" not in st.session_state: st.session_state.chat = []
            for msg in st.session_state.chat:
                st.chat_message(msg["role"]).write(msg["text"])
            
            if st.session_state.voice_input:
                user_text = st.session_state.voice_input
                st.session_state.voice_input = None
            else:
                user_text = st.chat_input("Type or Speak...")
                
            if user_text:
                st.session_state.chat.append({"role": "user", "text": user_text})
                st.chat_message("user").write(user_text)
                ai_reply = generate_safe(api_key, f"Reply to: {user_text}")
                st.session_state.chat.append({"role": "assistant", "text": ai_reply})
                st.chat_message("assistant").write(ai_reply)
                speak_human(ai_reply)
                st.rerun()
    else:
        st.info("Please enter your Name.")