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
import io
from streamlit_mic_recorder import mic_recorder
from pydub import AudioSegment # <--- NEW LIBRARY

# --- CONFIGURATION ---
st.set_page_config(page_title="AI Human Tutor", page_icon="⚡", layout="wide")

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect("tutor_groq.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (name TEXT, xp INTEGER)")
    conn.commit()
    conn.close()

def update_xp(name, amount):
    conn = sqlite3.connect("tutor_groq.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE name=?", (name,))
    if not c.fetchone(): c.execute("INSERT INTO users VALUES (?, ?)", (name, 0))
    c.execute("UPDATE users SET xp = xp + ? WHERE name=?", (amount, name))
    conn.commit()
    conn.close()

# --- AI ENGINE ---
@st.cache_data(show_spinner=False)
def get_groq_response(prompt, api_key):
    try:
        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful English Tutor. Always return JSON when asked."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"ERROR: {e}"

def generate_safe(api_key, prompt):
    with st.spinner("⚡ Thinking..."):
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
    text = text.replace("JSON", "").replace("{", "").replace("}", "")
    if not text.strip(): return
    communicate = edge_tts.Communicate(text, "en-IN-NeerjaNeural")
    await communicate.save("speech_groq.mp3")

def speak_human(text):
    try:
        avatar_spot = show_avatar(is_speaking=True)
        asyncio.run(generate_human_voice(text))
        if os.path.exists("speech_groq.mp3"):
            with open("speech_groq.mp3", "rb") as f:
                audio_bytes = f.read()
            st.audio(audio_bytes, format="audio/mp3", autoplay=True)
            est_time = len(text.split()) / 2.5
            time.sleep(est_time)
        avatar_spot.image("https://cdn-icons-png.flaticon.com/512/4140/4140048.png", width=200)
    except Exception as e:
        st.error(f"Audio Error: {e}")

# --- UPDATED AUDIO PROCESSOR (THE FIX) ---
def process_audio(audio_bytes):
    """Converts WebM audio to WAV using FFmpeg + Pydub"""
    if audio_bytes:
        try:
            # 1. Load the raw bytes (likely WebM from browser)
            audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
            
            # 2. Export to a WAV buffer
            wav_io = io.BytesIO()
            audio.export(wav_io, format="wav")
            wav_io.seek(0) # Go back to start of file
            
            # 3. Use SpeechRecognition on the WAV data
            r = sr.Recognizer()
            with sr.AudioFile(wav_io) as source:
                audio_data = r.record(source)
                text = r.recognize_google(audio_data)
                return text
        except Exception as e:
            st.warning(f"Could not understand audio: {e}")
            return None
    return None

# --- APP START ---
init_db()

with st.sidebar:
    st.title("⚡ AI Tutor (Groq)")
    name = st.text_input("Name:")
    try: api_key = st.secrets["GROQ_API_KEY"]
    except: api_key = st.text_input("Groq Key:", type="password")
    mode = st.radio("Mode:", ["📚 Grammar", "📝 Quiz", "💬 Roleplay"])
    
    st.markdown("---")
    st.write("🎙️ **Voice Input**")
    audio = mic_recorder(start_prompt="🎤 Record", stop_prompt="Dn Stop", key='recorder')
    
    if audio:
        st.session_state.voice_input = process_audio(audio['bytes'])

    if st.button("🔄 Clear Memory"):
        st.cache_data.clear()

if "voice_input" not in st.session_state: st.session_state.voice_input = None

if api_key and name:
    st.title("🚀 AI English Academy")
    show_avatar(is_speaking=False)

    # --- GRAMMAR ---
    if mode == "📚 Grammar":
        st.header("📚 Grammar Class")
        with st.form("grammar_form"):
            topic = st.text_input("Topic:", "Present Tense")
            submitted = st.form_submit_button("Teach Me 👩‍🏫")
        if submitted:
            prompt = f"Teach '{topic}'. Return JSON: {{'lesson': 'markdown', 'summary': 'speech'}}"
            res_text = generate_safe(api_key, prompt)
            try:
                json_start = res_text.find('{')
                json_end = res_text.rfind('}') + 1
                data = json.loads(res_text[json_start:json_end])
                st.markdown(data["lesson"])
                speak_human(data["summary"])
            except: st.error("AI Error")

    # --- QUIZ ---
    elif mode == "📝 Quiz":
        st.header("📝 Voice Quiz")
        if st.button("New Question 🎲"):
            prompt = "Generate 1 grammar question. Return JSON: {'question': 'text', 'options': ['A)','B)'], 'answer': 'B', 'speak_text': 'text'}"
            res_text = generate_safe(api_key, prompt)
            try:
                json_start = res_text.find('{')
                json_end = res_text.rfind('}') + 1
                st.session_state.quiz = json.loads(res_text[json_start:json_end])
                speak_human(st.session_state.quiz["speak_text"])
            except: pass

        if "quiz" in st.session_state:
            q = st.session_state.quiz
            st.write(f"**{q['question']}**")
            st.write("\n".join(q['options']))
            with st.form("quiz_answer"):
                user_ans = st.text_input("Your Answer (A/B/C/D):")
                if st.session_state.voice_input: st.info(f"Voice: {st.session_state.voice_input}")
                check = st.form_submit_button("Check Answer")
            if check:
                final = st.session_state.voice_input if st.session_state.voice_input else user_ans
                match = re.search(r'\b([a-d])\b', str(final).lower())
                if match and match.group(1).upper() == q['answer']:
                    st.balloons()
                    st.success("Correct!")
                    st.session_state.quiz = None
                    st.session_state.voice_input = None
                    st.rerun()
                else: st.error("Wrong.")

    # --- ROLEPLAY ---
    elif mode == "💬 Roleplay":
        st.header("💬 Conversation")
        if "chat" not in st.session_state: st.session_state.chat = []
        for msg in st.session_state.chat:
            st.chat_message(msg["role"]).write(msg["text"])
        
        if st.session_state.voice_input: st.info(f"🎤 {st.session_state.voice_input}")
        user_msg = st.chat_input("Type...")
        final_msg = st.session_state.voice_input if st.session_state.voice_input else user_msg
        
        if final_msg:
            st.session_state.voice_input = None
            st.session_state.chat.append({"role": "user", "text": final_msg})
            st.chat_message("user").write(final_msg)
            prompt = f"Act as English Tutor. Reply to: '{final_msg}'"
            res_text = generate_safe(api_key, prompt)
            st.session_state.chat.append({"role": "assistant", "text": res_text})
            st.chat_message("assistant").write(res_text)
            speak_human(res_text)
            st.rerun()
else:
    st.info("Login in Sidebar")