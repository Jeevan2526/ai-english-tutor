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

# --- 1. CURRICULUM (Updated) ---
CURRICULUM = {
    "Phase 1: Foundation (A1/A2)": [
        "1. Basic Greetings & Numbers",
        "2. Articles (A, An, The) & Nouns",
        "3. To Be (Am, Is, Are)",
        "4. Adjectives (Describing Things)",
        "5. Prepositions (In, On, At, For)",
        "6. Present Simple (Habits)",
        "7. Present Continuous (Now)",
        "8. Past Simple (Finished Actions)"
    ],
    "Phase 2: Connections (B1/B2)": [
        "9. Adverbs (Slowly, Quickly, Always)",
        "10. Conjunctions (And, But, Because)",
        "11. Present Perfect (Experiences)",
        "12. Future Forms (Will vs Going to)",
        "13. Modals (Can, Should, Must)",
        "14. Conditionals 0, 1 & 2",
        "15. Passive Voice"
    ],
    "Phase 3: The Polish (C1/C2)": [
        "16. Advanced Phrasal Verbs",
        "17. Conditionals 3 & Mixed",
        "18. Reported Speech",
        "19. Inversion for Emphasis",
        "20. Business & Academic Writing"
    ]
}

# --- 2. VERB DATABASE (With All 5 Forms) ---
# V1 (Base), V2 (Past), V3 (Perfect), V4 (Ing), V5 (s/es)
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
    conn = sqlite3.connect("english_easy_v2.db")
    c = conn.cursor()
    # Create table with 5 columns for verbs
    c.execute("CREATE TABLE IF NOT EXISTS verbs (v1 TEXT UNIQUE, v2 TEXT, v3 TEXT, v4 TEXT, v5 TEXT)")
    
    # Load verbs if empty
    c.execute("SELECT count(*) FROM verbs")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT OR IGNORE INTO verbs VALUES (?, ?, ?, ?, ?)", INITIAL_VERBS)
        conn.commit()
    conn.close()

def get_verbs():
    conn = sqlite3.connect("english_easy_v2.db")
    c = conn.cursor()
    c.execute("SELECT * FROM verbs ORDER BY v1 ASC") # Sorted Alphabetically
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
                    "content": "You are a friendly, patient English Tutor for beginners. Explain everything in VERY SIMPLE words. Use real-life analogies. Do not use complex grammar terms. Explain like I am 10 years old. Support explanations with Hindi examples if asked."
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
    with st.spinner("🧸 Thinking..."):
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
    mode = st.radio("Choose Activity:", ["🗺️ Learn Simply", "📜 All Verbs List", "🏋️ Verb Practice", "💬 Talk to AI"])
    
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

    # --- MODE 2: ALL VERBS LIST (NEW) ---
    elif mode == "📜 All Verbs List":
        st.header("📜 Complete Verb List (5 Forms)")
        st.write("Here are the 5 forms of common verbs:")
        st.caption("V1: Base | V2: Past | V3: Perfect | V4: Continuous (-ing) | V5: Simple Present (-s/es)")
        
        # Get all verbs from DB
        verbs = get_verbs()
        
        # Create a nice table
        import pandas as pd
        df = pd.DataFrame(verbs, columns=["V1 (Base)", "V2 (Past)", "V3 (Perfect)", "V4 (Ing)", "V5 (s/es)"])
        st.dataframe(df, use_container_width=True, height=600)

    # --- MODE 3: VERB PRACTICE ---
    elif mode == "🏋️ Verb Practice":
        st.header("🏋️ Verbs (Action Words)")
        
        st.subheader("📖 Dictionary Search")
        search = st.text_input("Type a verb (like 'go'):")
        all_verbs = get_verbs()
        
        if search:
            found = [v for v in all_verbs if search.lower() in v[0]]
            if found:
                for v in found:
                    st.success(f"**{v[0].upper()}** -> Past: {v[1]} | Perfect: {v[2]} | Ing: {v[3]}")
            else:
                st.warning("I don't know that verb yet.")

        st.divider()
        st.subheader("🔥 Quick Practice")
        if "drill_verb" not in st.session_state:
            st.session_state.drill_verb = random.choice(all_verbs)
        
        target = st.session_state.drill_verb
        st.write(f"### What is the **Past Tense** (V2) of: `{target[0].upper()}`?")
        
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

    # --- MODE 4: SIMPLE CHAT ---
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