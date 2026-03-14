import streamlit as st
from docx import Document
import re
import asyncio
import edge_tts
import io
import base64
import time
import streamlit.components.v1 as components

# --- 1. INITIALIZE STATE ---
def init_state():
    if "script_text" not in st.session_state: st.session_state.script_text = ""
    if "undo_stack" not in st.session_state: st.session_state.undo_stack = []
    if "redo_stack" not in st.session_state: st.session_state.redo_stack = []
    if "voice_map" not in st.session_state: st.session_state.voice_map = {"NARRATOR": "en-GB-RyanNeural"}
    if "playing" not in st.session_state: st.session_state.playing = False
    if "current_line_idx" not in st.session_state: st.session_state.current_line_idx = 0
    if "last_active_role" not in st.session_state: st.session_state.last_active_role = "NARRATOR"

init_state()

# --- 2. LOGIC FUNCTIONS ---
async def generate_voice_bytes(text, voice_id, rate="+0%"):
    try:
        communicate = edge_tts.Communicate(text, voice_id, rate=rate)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except Exception:
        return None

def extract_characters(script_text):
    potential_names = re.findall(r'^[A-Z][A-Z\s]+$', script_text, re.MULTILINE)
    exclude = ["INT.", "EXT.", "CUT TO:", "FADE IN:", "FADE OUT:", "CONTINUED:", "V.O.", "O.C.", "THE END", "ACT ONE", "SCENE", "TITLE", "CARD", "PAGE", "DAY", "NIGHT"]
    clean_names = [n.strip() for n in potential_names if n.strip() not in exclude and len(n.strip()) > 1]
    return sorted(list(set(clean_names)))

def get_docx_download(text):
    doc = Document()
    for line in text.split('\n'):
        doc.add_paragraph(line)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- 3. UI SETUP & CSS ---
st.set_page_config(page_title="Narrative Soundstage: Pro", layout="wide")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; max-width: 95% !important; }
    section[data-testid="stSidebar"] { width: 300px !important; }
    
    .compact-header {
        font-family: 'Courier New', Courier, monospace;
        background-color: #1a1a1a;
        padding: 8px 15px;
        border-radius: 4px;
        border-bottom: 2px solid #ffd600;
        color: #ffd600;
        font-size: 13px;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    div[data-testid="stTextArea"] textarea {
        font-family: 'Courier New', Courier, monospace !important;
        background-color: #fdfdfd !important;
        color: #111 !important;
        font-size: 17px !important;
        line-height: 1.5 !important;
        padding: 35px !important;
    }

    .performance-monitor {
        background-color: #1e1e1e;
        color: #ffffff;
        padding: 12px;
        border-radius: 4px;
        border-left: 5px solid #ffd600;
        font-family: 'Courier New', Courier, monospace;
        margin-bottom: 10px;
    }
    .active-line { color: #ffd600; font-weight: bold; font-size: 20px; display: block; margin-top: 5px; }
    
    /* Clean up Streamlit UI */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

FREE_VOICES = {
    "Guy (Male)": "en-US-GuyNeural",
    "Aria (Female)": "en-US-AriaNeural",
    "Christopher (Deep)": "en-US-ChristopherNeural",
    "Jenny (Friendly)": "en-US-JennyNeural",
    "Eric (Narrative)": "en-GB-RyanNeural",
    "Sonia (British)": "en-GB-SoniaNeural"
}

# --- 4. SIDEBAR CONTROLS ---
with st.sidebar:
    st.markdown("### 🎬 **STUDIO CONTROLS**")
    
    # Transport Controls
    col1, col2 = st.columns([2, 1])
    with col1:
        if st.session_state.playing:
            if st.button("⏸️ PAUSE", use_container_width=True):
                st.session_state.playing = False
                st.rerun()
        else:
            if st.button("▶️ PLAY", use_container_width=True, type="primary"):
                st.session_state.playing = True
                st.rerun()
    with col2:
        if st.button("🔄", use_container_width=True, help="Reset to Top"):
            st.session_state.current_line_idx = 0
            st.session_state.playing = False
            st.rerun()

    speed_factor = st.slider("Playback Speed", 0.5, 2.0, 1.0, 0.1)
    rate_str = f"{int((speed_factor - 1) * 100):+d}%"

    st.markdown("---")
    
    # Navigation and History
    h_col1, h_col2 = st.columns(2)
    with h_col1:
        if st.button("↩️ UNDO", use_container_width=True, disabled=not st.session_state.undo_stack):
            st.session_state.redo_stack.append(st.session_state.script_text)
            st.session_state.script_text = st.session_state.undo_stack.pop()
            st.rerun()
    with h_col2:
        if st.button("↪️ REDO", use_container_width=True, disabled=not st.session_state.redo_stack):
            st.session_state.undo_stack.append(st.session_state.script_text)
            st.session_state.script_text = st.session_state.redo_stack.pop()
            st.rerun()

    st.markdown("---")
    
    # Jump Logic
    j1, j2 = st.columns([1, 1])
    with j1:
        jump_line = st.number_input("Line", min_value=1, value=st.session_state.current_line_idx + 1, label_visibility="collapsed")
    with j2:
        if st.button("🚀 JUMP", use_container_width=True):
            st.session_state.current_line_idx = int(jump_line) - 1
            st.rerun()

    # Audio Engine Slot (Hidden)
    audio_engine_slot = st.empty()

    if st.session_state.script_text:
        st.markdown("---")
        docx_data = get_docx_download(st.session_state.script_text)
        st.download_button("💾 EXPORT DOCX", docx_data, "Script_Updated.docx", use_container_width=True)

# --- 5. MAIN CONTENT ---
word_count = len(st.session_state.script_text.split()) if st.session_state.script_text else 0

st.markdown(f'''
    <div class="compact-header">
        <span>🎭 NARRATIVE SOUNDSTAGE: PRO</span>
        <span>WORDS: <b>{word_count}</b></span>
    </div>
''', unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload", type=["docx"], key="file_input", label_visibility="collapsed")

if uploaded_file:
    doc = Document(uploaded_file)
    new_text = "\n".join([p.text for p in doc.paragraphs])
    if new_text != st.session_state.script_text:
        st.session_state.undo_stack.append(st.session_state.script_text)
        st.session_state.script_text = new_text
        st.session_state.current_line_idx = 0
        st.rerun()

if st.session_state.script_text:
    cast_list = extract_characters(st.session_state.script_text)
    
    with st.expander("👤 CASTING OFFICE"):
        c1, c2 = st.columns(2)
        for i, name in enumerate(cast_list):
            with (c1 if i % 2 == 0 else c2):
                st.session_state.voice_map[name] = st.selectbox(f"Role: {name}", list(FREE_VOICES.keys()), key=f"v_sel_{name}")
        st.session_state.voice_map["NARRATOR"] = st.selectbox("Narrator Voice", list(FREE_VOICES.keys()), index=4)

    # Highlighter / Performance Monitor
    lines = [l.strip() for l in st.session_state.script_text.split("\n") if l.strip()]
    if lines:
        curr_idx = min(st.session_state.current_line_idx, len(lines)-1)
        current_line_text = lines[curr_idx]
        
        st.markdown(f"""
            <div class="performance-monitor">
                <small style="color:#ffd600;">LINE {curr_idx + 1} / {len(lines)} | {"● PLAYING" if st.session_state.playing else "○ READY"}</small>
                <span class="active-line">{current_line_text}</span>
            </div>
        """, unsafe_allow_html=True)

    # Editor
    prev_text = st.session_state.script_text
    st.session_state.script_text = st.text_area("Editor", value=st.session_state.script_text, height=450, key="editor", label_visibility="collapsed")
    
    if st.session_state.script_text != prev_text:
        st.session_state.undo_stack.append(prev_text)
        st.session_state.redo_stack = [] 
        st.session_state.playing = False

# --- 6. RUNTIME TTS ---
if st.session_state.playing and lines:
    if st.session_state.current_line_idx < len(lines):
        idx = st.session_state.current_line_idx
        line_content = lines[idx]
        
        # Determine Speaker
        if line_content in cast_list:
            st.session_state.last_active_role = line_content
            current_role = "NARRATOR"
            read_text = f"{line_content}."
        elif line_content.isupper() and any(x in line_content for x in ["INT.", "EXT.", "DAY", "NIGHT"]):
            st.session_state.last_active_role = "NARRATOR"
            current_role = "NARRATOR"
            read_text = line_content
        else:
            current_role = st.session_state.last_active_role
            read_text = re.sub(r'\(.*?\)', '', line_content)

        v_label = st.session_state.voice_map.get(current_role, "Eric (Narrative)")
        v_id = FREE_VOICES.get(v_label, "en-GB-RyanNeural")
        
        loop = asyncio.new_event_loop()
        audio_data = loop.run_until_complete(generate_voice_bytes(read_text, v_id, rate=rate_str))
        
        if audio_data:
            b64 = base64.b64encode(audio_data).decode()
            audio_tag = f'<audio autoplay="true" id="p_{time.time()}"><source src="data:audio/mp3;base64,{b64}"></audio>'
            audio_engine_slot.markdown(audio_tag, unsafe_allow_html=True)

        # Pause duration based on words
        wait_time = (max(2.0, (len(read_text.split()) / 130) * 60)) / speed_factor
        time.sleep(wait_time)
        
        st.session_state.current_line_idx += 1
        st.rerun()
    else:
        st.session_state.playing = False
        st.session_state.current_line_idx = 0
        st.rerun()