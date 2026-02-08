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
from streamlit_mic_recorder import mic_recorder # <--- NEW IMPORT

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

# --- AI ENGINE (GROQ) ---
@st.cache_data(show_spinner=False)
def get_groq_response(prompt, api_key):
    try:
        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful English Tutor. Always return JSON when asked."
                },
                {
                    "role": "user",
                    "content": prompt,
                }
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
            audio_file = open("speech_groq.mp3", "rb")
            audio_bytes = audio_file.read()
            st.audio(audio_bytes, format="audio/mp3", autoplay=True)
            est_time = len(text.split()) / 2.5
            time.sleep(est_time)
        avatar_spot.image("https://cdn-icons-png.flaticon.com/512/4140/4140048.png", width=200)
    except Exception as e:
        st.error(f"Audio Error: {e}")

# --- NEW FUNCTION: BROWSER RECORDER ---
def process_audio(audio_bytes):
    """Converts the browser audio to text"""
    if audio_bytes:
        # Save the bytes to a temporary file
        with open("temp_audio.wav", "wb") as f:
            f.write(audio_bytes)
        
        # Use SpeechRecognition on the FILE, not the microphone
        r = sr.Recognizer()
        with sr.AudioFile("temp_audio.wav") as source:
            audio_data = r.record(source)
            try:
                text = r.recognize_google(audio_data)
                return text
            except sr.UnknownValueError:
                return None
            except sr.RequestError:
                return None
    return None

# --- APP START ---
init_db()

with st.sidebar:
    st.title("⚡ AI Tutor (Groq)")
    name = st.text_input("Name:")
    
    try: api_key = st.secrets["GROQ_API_KEY"]
    except: api_key = st.text_input("Groq API Key (gsk_...):", type="password")
    
    mode = st.radio("Mode:", ["📚 Grammar", "📝 Quiz", "💬 Roleplay"])
    
    st.markdown("---")
    st.write("🎙️ **Voice Input**")
    
    # --- NEW RECORDER WIDGET ---
    # This creates a button: Click to Record -> Click to Stop
    audio = mic_recorder(
        start_prompt="🎤 Start Recording",
        stop_prompt="Dn Stop Recording",
        key='recorder'
    )
    
    if audio:
        # If we have audio, process it immediately
        st.session_state.voice_input = process_audio(audio['bytes'])

    if st.button("🔄 Clear Memory"):
        st.cache_data.clear()

if "voice_input" not in st.session_state: st.session_state.voice_input = None

if api_key and name:

    st.title("🚀 AI English Academy")
    show_avatar(is_speaking=False)

    # --- MODE 1: GRAMMAR ---
    if mode == "📚 Grammar":
        st.header("📚 Grammar Class")
        
        with st.form("grammar_form"):
            topic = st.text_input("Enter Topic:", "Present Tense")
            submitted = st.form_submit_button("Teach Me 👩‍🏫")
        
        if submitted:
            prompt = f"""
            Teach '{topic}'. Return ONLY valid JSON with no extra text:
            {{ "lesson": "Markdown explanation with Hindi examples.", "summary": "Short speech text." }}
            """
            res_text = generate_safe(api_key, prompt)
            try:
                json_start = res_text.find('{')
                json_end = res_text.rfind('}') + 1
                if json_start != -1:
                    data = json.loads(res_text[json_start:json_end])
                    st.markdown(data["lesson"])
                    speak_human(data["summary"])
            except:
                st.error("AI Error. Try again.")

    # --- MODE 2: QUIZ ---
    elif mode == "📝 Quiz":
        st.header("📝 Voice Quiz")
        
        if st.button("New Question 🎲"):
            prompt = """
            Generate 1 grammar question. Return ONLY valid JSON:
            { "question": "Q text", "options": ["A) x", "B) y", "C) z", "D) w"], "answer": "B", "speak_text": "Q text" }
            """
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
                if st.session_state.voice_input:
                     st.info(f"Voice detected: {st.session_state.voice_input}")
                check = st.form_submit_button("Check Answer")
                
            if check:
                final_ans = st.session_state.voice_input if st.session_state.voice_input else user_ans
                match = re.search(r'\b([a-d])\b', str(final_ans).lower())
                if match and match.group(1).upper() == q['answer']:
                    st.balloons()
                    st.success("Correct!")
                    update_xp(name, 10)
                    st.session_state.quiz = None
                    st.session_state.voice_input = None
                    st.rerun()
                else:
                    st.error(f"Wrong.")

    # --- MODE 3: ROLEPLAY ---
    elif mode == "💬 Roleplay":
        st.header("💬 Conversation")
        if "chat" not in st.session_state: st.session_state.chat = []

        for msg in st.session_state.chat:
            st.chat_message(msg["role"]).write(msg["text"])

        # Show voice input if it exists
        if st.session_state.voice_input:
            st.info(f"🎤 You said: {st.session_state.voice_input}")

        user_msg = st.chat_input("Type...")
        
        # Use voice if available, else text
        final_msg = st.session_state.voice_input if st.session_state.voice_input else user_msg
        
        if final_msg:
            # Clear voice for next time
            st.session_state.voice_input = None
            
            st.session_state.chat.append({"role": "user", "text": final_msg})
            st.chat_message("user").write(final_msg)
            
            prompt = f"Act as an English Tutor. Reply to: '{final_msg}'. Keep it short."
            res_text = generate_safe(api_key, prompt)
            
            st.session_state.chat.append({"role": "assistant", "text": res_text})
            st.chat_message("assistant").write(res_text)
            speak_human(res_text)
            # Force rerun to show the chat
            st.rerun()

else:
    st.info("Enter Name and Groq Key in Sidebar")