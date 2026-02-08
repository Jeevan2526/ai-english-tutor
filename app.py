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
st.set_page_config(page_title="Ultimate English Master", page_icon="🏛️", layout="wide")

# --- 1. THE CEFR ROADMAP (Your Syllabus) ---
CURRICULUM = {
    "Phase 1: Foundation (A1/A2)": [
        "1. Basic Greetings & Numbers",
        "2. To Be (Am, Is, Are)",
        "3. Present Simple (Habits)",
        "4. Present Continuous (Now)",
        "5. Past Simple (Finished Actions)"
    ],
    "Phase 2: Connections (B1/B2)": [
        "6. Present Perfect (Experiences)",
        "7. Future Forms (Will vs Going to)",
        "8. Modals (Can, Should, Must)",
        "9. Conditionals 0, 1 & 2",
        "10. Passive Voice"
    ],
    "Phase 3: The Polish (C1/C2)": [
        "11. Advanced Phrasal Verbs",
        "12. Conditionals 3 & Mixed",
        "13. Reported Speech",
        "14. Inversion for Emphasis",
        "15. Business & Academic Writing"
    ]
}

# --- 2. VERB DATABASE (The 1000+ Verb Vault) ---
# We preload top 50 common verbs. In a real app, we would import a CSV of 1000.
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
    conn = sqlite3.connect("english_master.db")
    c = conn.cursor()
    # Student Progress Table
    c.execute("CREATE TABLE IF NOT EXISTS progress (name TEXT, level TEXT, xp INTEGER)")
    # Verb Table
    c.execute("CREATE TABLE IF NOT EXISTS verbs (v1 TEXT UNIQUE, v2 TEXT, v3 TEXT)")
    
    # Populate Verbs if empty
    c.execute("SELECT count(*) FROM verbs")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT OR IGNORE INTO verbs VALUES (?, ?, ?)", INITIAL_VERBS)
        conn.commit()
    conn.close()

def get_verbs():
    conn = sqlite3.connect("english_master.db")
    c = conn.cursor()
    c.execute("SELECT * FROM verbs")
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
                {"role": "system", "content": "You are an Expert English Professor (CEFR C2 Certified)."},
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
    await communicate.save("master_voice.mp3")

def speak_human(text):
    try:
        avatar_spot = show_avatar(is_speaking=True)
        asyncio.run(generate_human_voice(text))
        if os.path.exists("master_voice.mp3"):
            with open("master_voice.mp3", "rb") as f:
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
    st.title("🏛️ English Master")
    name = st.text_input("Name:")
    try: api_key = st.secrets["GROQ_API_KEY"]
    except: api_key = st.text_input("Groq Key:", type="password")
    
    # NAVIGATION
    mode = st.radio("Select Mode:", ["🗺️ Roadmap Learning", "🏋️ Verb Drill (1000+)", "💬 AI Roleplay"])
    
    st.divider()
    st.write("🎙️ **Microphone**")
    audio = mic_recorder(start_prompt="Record", stop_prompt="Stop", key='recorder')
    if audio: st.session_state.voice_input = process_audio(audio['bytes'])

if "voice_input" not in st.session_state: st.session_state.voice_input = None

if api_key and name:
    st.title(f"Welcome, {name}!")
    show_avatar(is_speaking=False)

    # --- MODE 1: ROADMAP LEARNING ---
    if mode == "🗺️ Roadmap Learning":
        st.header("🗺️ Your Path to Fluency")
        
        phase = st.selectbox("Select Phase:", list(CURRICULUM.keys()))
        topic = st.selectbox("Select Topic:", CURRICULUM[phase])
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Teach This Topic 📖"):
                prompt = f"Explain '{topic}' for an ESL student. Return JSON: {{'lesson': 'markdown explanation', 'summary': 'short audio summary'}}"
                res = generate_safe(api_key, prompt)
                try:
                    data = json.loads(res[res.find('{'):res.rfind('}')+1])
                    st.markdown(data['lesson'])
                    speak_human(data['summary'])
                except: st.error("AI Error")
        
        with col2:
            if st.button("Generate Quiz 📝"):
                prompt = f"Create a quiz for '{topic}'. Return JSON: {{'question': 'text', 'options': ['A','B','C'], 'answer': 'A'}}"
                res = generate_safe(api_key, prompt)
                try:
                    st.session_state.quiz = json.loads(res[res.find('{'):res.rfind('}')+1])
                except: st.error("AI Error")

        if "quiz" in st.session_state:
            q = st.session_state.quiz
            st.info(f"**Quiz:** {q['question']}")
            ans = st.radio("Select:", q['options'])
            if st.button("Submit Answer"):
                if ans.startswith(q['answer']):
                    st.success("Correct!")
                    st.balloons()
                    del st.session_state.quiz
                    st.rerun()
                else: st.error("Try again.")

    # --- MODE 2: VERB DRILL (THE VAULT) ---
    elif mode == "🏋️ Verb Drill (1000+)":
        st.header("🏋️ The Verb Vault")
        
        # 1. Search Tool
        st.subheader("📖 Dictionary")
        search = st.text_input("Search for a verb (e.g., 'go'):")
        all_verbs = get_verbs()
        
        if search:
            found = [v for v in all_verbs if search.lower() in v[0]]
            if found:
                for v in found:
                    st.success(f"**{v[0].upper()}** -> Past: *{v[1]}* | Participle: *{v[2]}*")
            else:
                st.warning("Verb not found in database.")

        st.divider()
        
        # 2. Random Drill
        st.subheader("🔥 Quick Fire Drill")
        if "drill_verb" not in st.session_state:
            st.session_state.drill_verb = random.choice(all_verbs)
        
        target = st.session_state.drill_verb
        st.write(f"### What is the **Past Tense (V2)** of: `{target[0].upper()}`?")
        
        user_v2 = st.text_input("Type Answer:", key="v2_input")
        
        if st.button("Check Verb"):
            # Check if answer matches V2 (handling multiple forms like 'was/were')
            if user_v2.lower().strip() in target[1].lower():
                st.success(f"Correct! {target[0]} -> {target[1]}")
                st.session_state.drill_verb = random.choice(all_verbs)
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"Wrong. It is **{target[1]}**.")
                speak_human(f"The past tense of {target[0]} is {target[1]}")

    # --- MODE 3: AI ROLEPLAY ---
    elif mode == "💬 AI Roleplay":
        st.header("💬 Conversation Practice")
        if "chat" not in st.session_state: st.session_state.chat = []
        
        for msg in st.session_state.chat:
            st.chat_message(msg["role"]).write(msg["text"])
            
        user_input = st.chat_input("Type message...")
        if st.session_state.voice_input: 
            user_input = st.session_state.voice_input
            st.session_state.voice_input = None
            
        if user_input:
            st.session_state.chat.append({"role": "user", "text": user_input})
            st.chat_message("user").write(user_input)
            
            prompt = f"Reply to this English student: '{user_input}'. Correct any grammar mistakes politely."
            res = generate_safe(api_key, prompt)
            
            st.session_state.chat.append({"role": "assistant", "text": res})
            st.chat_message("assistant").write(res)
            speak_human(res)
            st.rerun()

else:
    st.info("Please Login to access the Ultimate Course.")