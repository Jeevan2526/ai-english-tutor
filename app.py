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

# --- CONFIGURATION ---
st.set_page_config(page_title="AI Human Tutor (Groq)", page_icon="⚡", layout="wide")

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
            # --- UPDATED MODEL NAME ---
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
    # Free placeholders (Replace with your own URLs if you want)
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
        # 1. Show Talking Avatar
        avatar_spot = show_avatar(is_speaking=True)
        
        # 2. Generate Audio
        asyncio.run(generate_human_voice(text))
        
        # 3. Play Audio
        if os.path.exists("speech_groq.mp3"):
            audio_file = open("speech_groq.mp3", "rb")
            audio_bytes = audio_file.read()
            st.audio(audio_bytes, format="audio/mp3", autoplay=True)
            
            # Estimate duration to keep avatar moving (approx 2.5 words/sec)
            est_time = len(text.split()) / 2.5
            time.sleep(est_time)
            
        # 4. Revert to Silent
        avatar_spot.image("https://cdn-icons-png.flaticon.com/512/4140/4140048.png", width=200)
            
    except Exception as e:
        st.error(f"Audio Error: {e}")

def listen_to_user():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        st.toast("🎤 Listening...", icon="👂")
        try:
            audio = r.listen(source, timeout=5)
            return r.recognize_google(audio)
        except: return None

# --- APP START ---
init_db()

with st.sidebar:
    st.title("⚡ AI Tutor (Groq)")
    name = st.text_input("Name:")
    
    # GROQ KEY INPUT
    try: api_key = st.secrets["GROQ_API_KEY"]
    except: api_key = st.text_input("Groq API Key (gsk_...):", type="password")
    
    mode = st.radio("Mode:", ["📚 Grammar", "📝 Quiz", "💬 Roleplay"])
    
    st.markdown("---")
    if st.button("🎤 Click to Speak"):
        st.session_state.voice_input = listen_to_user()
    
    if st.button("🔄 Clear Memory"):
        st.cache_data.clear()

if "voice_input" not in st.session_state: st.session_state.voice_input = None

if api_key and name:

    st.title("🚀 AI English Academy (High Speed)")
    show_avatar(is_speaking=False) # Default Silent Avatar

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
                # Cleaning Llama 3 output to find JSON
                json_start = res_text.find('{')
                json_end = res_text.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = res_text[json_start:json_end]
                    data = json.loads(json_str)
                    
                    st.markdown(data["lesson"])
                    speak_human(data["summary"])
                else:
                    st.error("AI did not return JSON. Trying again...")
            except:
                st.error("AI Output Error. Raw text:")
                st.write(res_text)

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
                json_str = res_text[json_start:json_end]
                st.session_state.quiz = json.loads(json_str)
                speak_human(st.session_state.quiz["speak_text"])
            except: 
                st.error("Try again.")

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
                    st.error(f"Wrong. Answer was {q['answer']}")

    # --- MODE 3: ROLEPLAY ---
    elif mode == "💬 Roleplay":
        st.header("💬 Conversation")
        if "chat" not in st.session_state: st.session_state.chat = []

        for msg in st.session_state.chat:
            st.chat_message(msg["role"]).write(msg["text"])

        user_msg = st.chat_input("Type...")
        if st.session_state.voice_input:
            user_msg = st.session_state.voice_input
            st.session_state.voice_input = None 

        if user_msg:
            st.session_state.chat.append({"role": "user", "text": user_msg})
            st.chat_message("user").write(user_msg)
            
            # Simple chat prompt
            prompt = f"Act as an English Tutor. Reply to this student: '{user_msg}'. Keep it short."
            res_text = generate_safe(api_key, prompt)
            
            st.session_state.chat.append({"role": "assistant", "text": res_text})
            st.chat_message("assistant").write(res_text)
            speak_human(res_text)

else:
    st.info("Enter your Name and Groq API Key in Sidebar")