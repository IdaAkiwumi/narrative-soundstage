import streamlit as st
from docx import Document
import re
import asyncio
import edge_tts
import io
import base64
import time

# --- LOGIC: FREE VOICE ENGINE ---
async def generate_voice_bytes(text, voice_id):
    try:
        communicate = edge_tts.Communicate(text, voice_id)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
    except Exception as e:
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
    div[data-testid="stTextArea"] textarea {
        font-family: 'Courier New', Courier, monospace !important;
        background-color: #ffffff !important;
        color: #000000 !important;
        font-size: 18px !important;
        line-height: 1.4 !important;
        border: 1px solid #cccccc !important;
        padding: 40px !important;
    }
    .performance-monitor {
        background-color: #1e1e1e;
        color: #ffffff;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 15px;
        border-left: 10px solid #ffd600;
        font-family: 'Courier New', Courier, monospace;
        min-height: 100px;
    }
    .active-line {
        color: #ffd600;
        font-weight: bold;
        font-size: 26px;
        display: block;
        margin-top: 5px;
    }
    .word-count-badge {
        font-family: monospace;
        background-color: #262730;
        padding: 4px 12px;
        border-radius: 4px;
        color: #ffffff;
    }
    </style>
""", unsafe_allow_html=True)

# --- STATE MANAGEMENT ---
if "script_text" not in st.session_state:
    st.session_state.script_text = ""
if "voice_map" not in st.session_state:
    st.session_state.voice_map = {"NARRATOR": "Eric (Male - Narrative)"}
if "playing" not in st.session_state:
    st.session_state.playing = False
if "current_line_idx" not in st.session_state:
    st.session_state.current_line_idx = 0
if "last_active_role" not in st.session_state:
    st.session_state.last_active_role = "NARRATOR"

FREE_VOICES = {
    "Guy (Male - Resonant)": "en-US-GuyNeural",
    "Aria (Female - Clear)": "en-US-AriaNeural",
    "Christopher (Male - Deep)": "en-US-ChristopherNeural",
    "Jenny (Female - Friendly)": "en-US-JennyNeural",
    "Eric (Male - Narrative)": "en-GB-RyanNeural",
    "Sonia (Female - British)": "en-GB-SoniaNeural"
}

# --- SIDEBAR ---
with st.sidebar:
    st.title("🎬 Studio Controls")
    
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

    if st.button("🗑️ CLEAR SCRIPT", use_container_width=True):
        st.session_state.script_text = ""
        st.session_state.current_line_idx = 0
        st.session_state.playing = False
        st.session_state.voice_map = {"NARRATOR": "Eric (Male - Narrative)"}
        st.rerun()

    st.divider()
    audio_engine_slot = st.empty()
    
    words = len(st.session_state.script_text.split()) if st.session_state.script_text else 0
    st.markdown(f"**Live Count:** <span class='word-count-badge'>{words} words</span>", unsafe_allow_html=True)
    
    st.divider()
    if st.session_state.script_text:
        docx_data = get_docx_download(st.session_state.script_text)
        st.download_button(
            label="💾 Download .docx",
            data=docx_data,
            file_name="Production_Script.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )

# --- MAIN INTERFACE ---
st.title("🎭 Narrative Soundstage")

uploaded_file = st.file_uploader("Upload Script (.docx)", type=["docx"], key="file_input")

if uploaded_file:
    doc = Document(uploaded_file)
    new_text = "\n".join([p.text for p in doc.paragraphs])
    if new_text != st.session_state.script_text:
        st.session_state.script_text = new_text
        st.session_state.current_line_idx = 0
        st.rerun()

if st.session_state.script_text:
    cast_list = extract_characters(st.session_state.script_text)
    
    with st.expander("👤 Casting Office", expanded=False):
        c1, c2 = st.columns(2)
        for i, name in enumerate(cast_list):
            with (c1 if i % 2 == 0 else c2):
                # Restored specific casting defaults
                default_idx = 0
                if "MALIK" in name.upper(): default_idx = 2 # Christopher
                elif "MIRA" in name.upper(): default_idx = 1 # Aria
                
                st.session_state.voice_map[name] = st.selectbox(
                    f"Role: {name}", list(FREE_VOICES.keys()), 
                    index=default_idx,
                    key=f"v_sel_{name}"
                )
        st.session_state.voice_map["NARRATOR"] = st.selectbox(
            "Narrator Voice", list(FREE_VOICES.keys()), index=4, key="v_sel_narrator"
        )

    performance_overlay = st.empty()
    
    prev_text = st.session_state.script_text
    st.session_state.script_text = st.text_area(
        "Script Page", 
        value=st.session_state.script_text, 
        height=600,
        key="editor"
    )
    
    if st.session_state.script_text != prev_text:
        st.session_state.playing = False

    # --- THE ATOMIC RUNTIME (One line per rerun) ---
    if st.session_state.playing:
        lines = [l.strip() for l in st.session_state.script_text.split("\n") if l.strip()]
        
        if st.session_state.current_line_idx < len(lines):
            idx = st.session_state.current_line_idx
            line_content = lines[idx]
            
            # Speaker Logic
            if line_content in cast_list:
                st.session_state.last_active_role = line_content
                current_voice_role = "NARRATOR"
                read_text = f"{line_content}."
            elif line_content.isupper() and any(x in line_content for x in ["INT.", "EXT.", "DAY", "NIGHT", "SLUG"]):
                st.session_state.last_active_role = "NARRATOR"
                current_voice_role = "NARRATOR"
                read_text = line_content
            else:
                current_voice_role = st.session_state.last_active_role
                read_text = re.sub(r'\(.*?\)', '', line_content)

            # Update Highlighter
            performance_overlay.markdown(f"""
                <div class="performance-monitor">
                    <small style="color:#ffd600; text-transform: uppercase;">Current Speaker: {current_voice_role}</small>
                    <span class="active-line">{line_content}</span>
                </div>
            """, unsafe_allow_html=True)

            # Audio Generation
            voice_choice = st.session_state.voice_map.get(current_voice_role, "Eric (Male - Narrative)")
            v_id = FREE_VOICES[voice_choice]
            
            loop = asyncio.new_event_loop()
            audio_data = loop.run_until_complete(generate_voice_bytes(read_text, v_id))
            
            if audio_data:
                b64 = base64.b64encode(audio_data).decode()
                # Unique ID forces browser to treat it as a new audio stream
                audio_tag = f'<audio autoplay="true" id="{time.time()}"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
                audio_engine_slot.markdown(audio_tag, unsafe_allow_html=True)

            # Timing & Progression
            w_count = len(read_text.split())
            wait_time = max(2.3, (w_count / 125) * 60)
            time.sleep(wait_time)
            
            st.session_state.current_line_idx += 1
            st.rerun()
        else:
            # Reached end of script
            st.session_state.playing = False
            st.session_state.current_line_idx = 0
            st.rerun()
    else:
        # Idle State
        if st.session_state.current_line_idx > 0:
            performance_overlay.warning(f"Production Paused at Line {st.session_state.current_line_idx + 1}")
        else:
            performance_overlay.info("Studio Ready. Click PLAY to start the table read.")