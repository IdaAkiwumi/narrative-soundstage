import streamlit as st
from docx import Document
import re
import asyncio
import edge_tts
import io
import base64
import time
import streamlit.components.v1 as components

# --- 1. INITIALIZE STATE (MUST BE ABSOLUTELY FIRST) ---
def init_state():
    if "script_text" not in st.session_state: st.session_state.script_text = ""
    if "undo_stack" not in st.session_state: st.session_state.undo_stack = []
    if "redo_stack" not in st.session_state: st.session_state.redo_stack = []
    if "voice_map" not in st.session_state: st.session_state.voice_map = {"NARRATOR": "en-GB-RyanNeural"}
    if "playing" not in st.session_state: st.session_state.playing = False
    if "current_line_idx" not in st.session_state: st.session_state.current_line_idx = 0
    if "last_active_role" not in st.session_state: st.session_state.last_active_role = "NARRATOR"

init_state()

# --- LOGIC: FREE VOICE ENGINE ---
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

# --- UI SETUP ---
st.set_page_config(page_title="Narrative Soundstage: Pro", layout="wide")

st.markdown("""
    <style>
    .compact-header {
        font-family: 'Courier New', Courier, monospace;
        background-color: #262730;
        padding: 5px 15px;
        border-radius: 4px;
        color: #ffd600;
        font-size: 14px;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    div[data-testid="stTextArea"] textarea {
        font-family: 'Courier New', Courier, monospace !important;
        background-color: #ffffff !important;
        color: #000000 !important;
        font-size: 18px !important;
        line-height: 1.6 !important;
        padding: 40px !important;
    }
    .performance-monitor {
        background-color: #1e1e1e;
        color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        border-left: 8px solid #ffd600;
        font-family: 'Courier New', Courier, monospace;
        margin-bottom: 15px;
    }
    .active-line {
        color: #ffd600;
        font-weight: bold;
        font-size: 24px;
        display: block;
    }
    .stats-badge {
        background-color: #ffd600;
        color: #000;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-family: monospace;
    }
    </style>
""", unsafe_allow_html=True)

FREE_VOICES = {
    "Guy (Male - Resonant)": "en-US-GuyNeural",
    "Aria (Female - Clear)": "en-US-AriaNeural",
    "Christopher (Male - Deep)": "en-US-ChristopherNeural",
    "Jenny (Female - Friendly)": "en-US-JennyNeural",
    "Eric (Male - Narrative)": "en-GB-RyanNeural",
    "Sonia (Female - British)": "en-GB-SoniaNeural"
}

word_count = len(st.session_state.script_text.split()) if st.session_state.script_text else 0

st.markdown(f'''
    <div class="compact-header">
        <span>🎭 NARRATIVE SOUNDSTAGE: PRO</span>
        <span>WORDS: <span class="stats-badge">{word_count}</span></span>
    </div>
''', unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🎬 Studio Controls")
    
    speed_factor = st.slider("Playback Speed", 0.5, 2.0, 1.0, 0.1, key="speed")
    rate_str = f"{int((speed_factor - 1) * 100):+d}%"
    
    col1, col2 = st.columns(2)
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
        if st.button("🔄 RESET", use_container_width=True):
            st.session_state.current_line_idx = 0
            st.session_state.playing = False
            st.rerun()

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

    if st.button("🗑️ CLEAR SCRIPT", use_container_width=True):
        if st.session_state.script_text:
            st.session_state.undo_stack.append(st.session_state.script_text)
        st.session_state.script_text = ""
        st.session_state.current_line_idx = 0
        st.session_state.playing = False
        st.rerun()

    st.divider()
    
    # Improved Manual Jump
    jump_line = st.number_input("Jump to Line #", min_value=1, value=st.session_state.current_line_idx + 1)
    if st.button("🚀 Jump"):
        st.session_state.current_line_idx = int(jump_line) - 1
        st.rerun()

    audio_engine_slot = st.empty()
    
    if st.session_state.script_text:
        docx_data = get_docx_download(st.session_state.script_text)
        st.download_button("💾 Export .docx", docx_data, "Script_Updated.docx", use_container_width=True)

# --- MAIN INTERFACE ---
uploaded_file = st.file_uploader("Upload Script", type=["docx"], key="file_input", label_visibility="collapsed")

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
    
    with st.expander("👤 Casting Office"):
        c1, c2 = st.columns(2)
        for i, name in enumerate(cast_list):
            with (c1 if i % 2 == 0 else c2):
                st.session_state.voice_map[name] = st.selectbox(f"Role: {name}", list(FREE_VOICES.keys()), key=f"v_sel_{name}")
        st.session_state.voice_map["NARRATOR"] = st.selectbox("Narrator Voice", list(FREE_VOICES.keys()), index=4)

    # --- HIGHLIGHTER ---
    lines = [l.strip() for l in st.session_state.script_text.split("\n") if l.strip()]
    if lines:
        curr_idx = min(st.session_state.current_line_idx, len(lines)-1)
        current_line_text = lines[curr_idx]
        
        st.markdown(f"""
            <div class="performance-monitor">
                <div style="display: flex; justify-content: space-between;">
                    <small style="color:#ffd600;">LINE {curr_idx + 1} OF {len(lines)}</small>
                    <small style="color:#ffd600;">{"● RECORDING" if st.session_state.playing else "○ STANDBY"}</small>
                </div>
                <span class="active-line">{current_line_text}</span>
            </div>
        """, unsafe_allow_html=True)
        
        if st.button("🖱️ CLICK TO EDIT THIS LINE", use_container_width=True):
            st.session_state.playing = False
            # Enhanced JS Scroll logic
            components.html(f"""
                <script>
                var textArea = window.parent.document.querySelector('textarea');
                if (textArea) {{
                    var totalLines = {len(lines)};
                    var targetLine = {curr_idx};
                    var percent = targetLine / totalLines;
                    textArea.scrollTop = textArea.scrollHeight * percent;
                    textArea.focus();
                }}
                </script>
            """, height=0)

    # Script Editor Area
    prev_text = st.session_state.script_text
    st.session_state.script_text = st.text_area(
        "Script Content", value=st.session_state.script_text, height=500, key="editor", label_visibility="collapsed"
    )
    
    # Save to undo stack ONLY on actual changes
    if st.session_state.script_text != prev_text:
        if prev_text.strip() != "":
            st.session_state.undo_stack.append(prev_text)
        st.session_state.redo_stack = [] 
        st.session_state.playing = False

    # --- RUNTIME ---
    if st.session_state.playing and lines:
        if st.session_state.current_line_idx < len(lines):
            idx = st.session_state.current_line_idx
            line_content = lines[idx]
            
            # Speaker Selection Logic
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

            # Voice Generation
            v_label = st.session_state.voice_map.get(current_role, "Eric (Male - Narrative)")
            v_id = FREE_VOICES.get(v_label, "en-GB-RyanNeural")
            
            # Direct execution to avoid "Reset" lag
            loop = asyncio.new_event_loop()
            audio_data = loop.run_until_complete(generate_voice_bytes(read_text, v_id, rate=rate_str))
            
            if audio_data:
                b64 = base64.b64encode(audio_data).decode()
                audio_tag = f'<audio autoplay="true" id="play_{time.time()}"><source src="data:audio/mp3;base64,{b64}"></audio>'
                audio_engine_slot.markdown(audio_tag, unsafe_allow_html=True)

            # Smart Wait
            w_count = len(read_text.split())
            wait_time = (max(2.1, (w_count / 125) * 60)) / speed_factor
            time.sleep(wait_time)
            
            st.session_state.current_line_idx += 1
            st.rerun()
        else:
            st.session_state.playing = False
            st.session_state.current_line_idx = 0
            st.rerun()