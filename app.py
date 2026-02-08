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

# --- CONFIGURATION ---
st.set_page_config(page_title="Easy English AI", page_icon="🧸", layout="wide")

# --- 1. SIMPLE ROADMAP (Clear & Easy) ---
CURRICULUM = {
    "Level 1: The Basics (Baby Steps)": [
        "1. Hello & Introduction (Start Here)",
        "2. Action Words (Eat, Sleep, Go)",
        "3. Describing Things (Colors, Big/Small)",
        "4. Daily Routine (I wake up...)",
    ],
    "Level 2: Connecting Ideas (Sentences)": [
        "5. Yesterday (Past Tense)",
        "6. Tomorrow (Future Plans)",
        "7. Asking Questions (Who, What, Where)",
        "8. Can & Cannot (Ability)",
    ],
    "Level 3: Fluent Speaking (Conversation)": [
        "9. Talking about Feelings",
        "10. Shopping & Bargaining",
        "11. Travel & Directions",
        "12. Office & Job Interview",
    ]
}

# --- 2. VERB DATABASE (Pre-loaded with 50 Common Verbs) ---
INITIAL_VERBS = [
    ("be", "was/were", "been"), ("have", "had", "had"), ("do", "did", "done"),
    ("say", "said", "said"), ("go", "went", "gone"), ("get", "got", "gotten"),
    ("make", "made", "made"), ("know", "knew", "known"), ("think", "thought", "thought"),
    ("take", "took", "taken"), ("see", "saw", "seen"), ("come", "came", "come"),
    ("want", "wanted", "wanted"), ("look", "looked", "looked"), ("use", "used", "used"),
    ("find", "found", "found"), ("give", "gave", "given"), ("tell", "told", "told"),
    ("work", "worked", "worked"), ("call", "called", "called"), ("try", "tried", "tried"),
    ("ask", "asked", "asked"), ("need", "needed", "needed"), ("feel", "felt", "felt"),
    ("become", "became", "become"), ("leave", "left", "left"), ("put", "put", "put"),
    ("mean", "meant", "meant"), ("keep", "kept", "kept"), ("let", "let", "let"),
    ("begin", "began", "begun"), ("seem", "seemed", "seemed"), ("help", "helped", "helped"),
    ("talk", "talked", "talked"), ("turn", "turned", "turned"), ("start", "started", "started"),
    ("show", "showed", "shown"), ("hear", "heard", "heard"), ("play", "played", "played"),
    ("run", "ran", "run"), ("move", "moved", "moved"), ("like", "liked", "liked"),
    ("live", "lived", "lived"), ("believe", "believed", "believed"), ("hold", "held", "held"),
    ("bring", "brought", "brought"), ("happen", "happened", "happened"), ("write", "wrote", "written"),
    ("provide", "provided", "provided"), ("sit", "sat", "sat")
]

def init_db():
    conn = sqlite3.connect("english_easy.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS verbs (v1 TEXT UNIQUE, v2 TEXT, v3 TEXT)")
    
    # Load verbs if empty
    c.execute("SELECT count(*) FROM verbs")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT OR IGNORE INTO verbs VALUES (?, ?, ?)", INITIAL_VERBS)
        conn.commit()
    conn.close()

def get_verbs():
    conn = sqlite3.connect("english_easy.db")
    c = conn.cursor()
    c.execute("SELECT * FROM verbs")
    data = c.fetchall()
    conn.close()
    return data

# --- AI ENGINE (UPDATED TO BE SIMPLE) ---
@st.cache_data(show_spinner=False)
def get_groq_response(prompt, api_key):
    try:
        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system", 
                    # --- THIS IS THE MAGIC CHANGE ---
                    "content": "You are a friendly, patient English Tutor for beginners. Explain everything in VERY SIMPLE words. Use real-life analogies (like cooking, driving, sports). Do not use complex grammar terms. Explain like I am 10 years old. Always support explanations with Hindi/Hinglish examples if helpful."
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
    with st.spinner("🧸 Simplifying the topic..."):
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
    text = re.sub(r'\[.*?\]', '', text).replace("*", "").replace("#", "")
    if not text.strip(): return
    communicate = edge_tts.Communicate(text, "en-IN-NeerjaNeural")
    await communicate.save("easy_voice.mp3")

def speak_human(text):
    try:
        avatar_spot = show_avatar(is_speaking=True)
        asyncio.run(generate_human_voice(text))
        if os.path.exists("easy_voice.mp3"):
            with open("easy_voice.mp3", "rb") as f:
                audio_bytes = f.read()
            st.audio(audio_bytes, format="audio/mp3", autoplay=True)
            est_time = len(text.split()) / 2.5
            time.sleep(est_time)
        avatar_spot.image("https://cdn-icons-png.flaticon.com/512/4140/4140048.png", width=200)
    except Exception as e:
        st.error(f"Audio Error: {e}")

# --- AUDIO PROCESSING ---
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
    st.title("🧸 Easy English")
    name = st.text_input("Name:")
    try: api_key = st.secrets["GROQ_API_KEY"]
    except: api_key = st.text_input("Groq Key:", type="password")
    
    # NAVIGATION
    mode = st.radio("Choose Activity:", ["🗺️ Learn Simply", "🏋️ Verb Practice", "💬 Talk to AI"])
    
    st.divider()
    st.write("🎙️ **Microphone**")
    audio = mic_recorder(start_prompt="Record", stop_prompt="Stop", key='recorder')
    if audio: st.session_state.voice_input = process_audio(audio['bytes'])

if "voice_input" not in st.session_state: st.session_state.voice_input = None

if api_key and name:
    st.title(f"Hi {name}! Let's Learn.")
    show_avatar(is_speaking=False)

    # --- MODE 1: SIMPLE LEARNING ---
    if mode == "🗺️ Learn Simply":
        st.header("🗺️ Simple Roadmap")
        
        phase = st.selectbox("Select Level:", list(CURRICULUM.keys()))
        topic = st.selectbox("Select Topic:", CURRICULUM[phase])
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Explain Simply 📖"):
                prompt = f"""
                Explain '{topic}' to a complete beginner. 
                Do NOT use grammar jargon. Use real life examples.
                Return JSON: {{'lesson': 'Simple markdown text', 'summary': 'Very short audio summary (2 sentences)'}}
                """
                res = generate_safe(api_key, prompt)
                try:
                    data = json.loads(res[res.find('{'):res.rfind('}')+1])
                    st.markdown(data['lesson'])
                    speak_human(data['summary'])
                except: st.error("AI Error")
        
        with col2:
            if st.button("Give me a Simple Quiz 📝"):
                prompt = f"Create a very easy quiz for '{topic}'. Return JSON: {{'question': 'text', 'options': ['A','B','C'], 'answer': 'A'}}"
                res = generate_safe(api_key, prompt)
                try:
                    st.session_state.quiz = json.loads(res[res.find('{'):res.rfind('}')+1])
                except: st.error("AI Error")

        if "quiz" in st.session_state:
            q = st.session_state.quiz
            st.info(f"**Quiz:** {q['question']}")
            ans = st.radio("Select:", q['options'])
            if st.button("Check Answer"):
                if ans.startswith(q['answer']):
                    st.success("Correct! 🎉")
                    st.balloons()
                    del st.session_state.quiz
                    st.rerun()
                else: st.error("Oops! Try again.")

    # --- MODE 2: VERB PRACTICE ---
    elif mode == "🏋️ Verb Practice":
        st.header("🏋️ Verbs (Action Words)")
        
        st.subheader("📖 Dictionary")
        search = st.text_input("Type a verb (like 'go' or 'eat'):")
        all_verbs = get_verbs()
        
        if search:
            found = [v for v in all_verbs if search.lower() in v[0]]
            if found:
                for v in found:
                    st.success(f"**{v[0].upper()}** (Present) -> **{v[1]}** (Past) -> **{v[2]}** (Perfect)")
            else:
                st.warning("I don't know that verb yet.")

        st.divider()
        st.subheader("🔥 Quick Practice")
        if "drill_verb" not in st.session_state:
            st.session_state.drill_verb = random.choice(all_verbs)
        
        target = st.session_state.drill_verb
        st.write(f"### What is the **Past Tense** of: `{target[0].upper()}`?")
        
        user_v2 = st.text_input("Type Answer:", key="v2_input")
        
        if st.button("Check"):
            if user_v2.lower().strip() in target[1].lower():
                st.success(f"Yes! {target[0]} -> {target[1]}")
                st.session_state.drill_verb = random.choice(all_verbs)
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"Not quite. It is **{target[1]}**.")
                speak_human(f"The past tense of {target[0]} is {target[1]}")

    # --- MODE 3: SIMPLE CHAT ---
    elif mode == "💬 Talk to AI":
        st.header("💬 Easy Conversation")
        if "chat" not in st.session_state: st.session_state.chat = []
        
        for msg in st.session_state.chat:
            st.chat_message(msg["role"]).write(msg["text"])
            
        user_input = st.chat_input("Say something...")
        if st.session_state.voice_input: 
            user_input = st.session_state.voice_input
            st.session_state.voice_input = None
            
        if user_input:
            st.session_state.chat.append({"role": "user", "text": user_input})
            st.chat_message("user").write(user_input)
            
            prompt = f"Reply to this beginner student: '{user_input}'. Use very simple English words. Correct any mistakes gently."
            res = generate_safe(api_key, prompt)
            
            st.session_state.chat.append({"role": "assistant", "text": res})
            st.chat_message("assistant").write(res)
            speak_human(res)
            st.rerun()

else:
    st.info("Please Login to start learning.")