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
    if "edit_history" not in st.session_state: st.session_state.edit_history = []
    if "voice_map" not in st.session_state: 
        st.session_state.voice_map = {"NARRATOR": "en-GB-RyanNeural"}
    if "playing" not in st.session_state: st.session_state.playing = False
    if "current_line_idx" not in st.session_state: st.session_state.current_line_idx = 0
    if "last_active_role" not in st.session_state: st.session_state.last_active_role = "NARRATOR"
    # Essential for forcing the text_area to refresh when Undo/Redo is clicked
    if "editor_version" not in st.session_state: st.session_state.editor_version = 0

init_state()

# --- LOGIC: AUDIO ENGINE ---
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

def normalize_script_spacing(text):
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def guess_gender(name):
    fem_hints = ['ARIA', 'JENNY', 'SONIA', 'MARIAN', 'GIRL', 'WOMAN', 'SISTER', 'MOTHER']
    name_up = name.upper()
    if any(hint in name_up for hint in fem_hints) or name_up.endswith('A'):
        return "en-US-AriaNeural"
    return "en-US-GuyNeural"

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

# CSS: Keeping it clean to ensure Side Nav visibility
st.markdown("""
    <style>
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0rem !important;
        max-width: 95% !important;
    }
    [data-testid="stVerticalBlock"] > div {
        gap: 0.1rem !important;
    }
    /* Fixed header modified to not overlap sidebar toggle */
    .compact-header {
        font-family: 'Courier New', Courier, monospace;
        background-color: #262730; 
        padding: 10px 20px; 
        border-radius: 4px;
        color: #ffd600; 
        font-size: 16px; 
        margin-bottom: 10px;
        display: flex; 
        justify-content: space-between; 
        align-items: center;
        border: 1px solid #ffd600;
    }
    div[data-testid="stTextArea"] textarea {
        font-family: 'Courier New', Courier, monospace !important;
        background-color: #ffffff !important; color: #000000 !important;
        font-size: 18px !important; line-height: 1.6 !important; padding: 40px !important;
    }
    .performance-monitor {
        background-color: #1e1e1e; color: #ffffff; padding: 15px;
        border-radius: 8px; border-left: 10px solid #ffd600;
        font-family: 'Courier New', Courier, monospace; margin-bottom: 10px;
    }
    .active-line { color: #ffd600; font-weight: bold; font-size: 24px; display: block; margin-top: 5px; }
    .stats-badge { background-color: #ffd600; color: #000; padding: 2px 10px; border-radius: 4px; font-weight: bold; }
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

VOICE_LABELS = {v: k for k, v in FREE_VOICES.items()}
word_count = len(st.session_state.script_text.split()) if st.session_state.script_text else 0

# --- HEADER ---
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

    st.divider()
    st.subheader("🔍 Find & Replace")
    f_text = st.text_input("Find...")
    r_text = st.text_input("Replace with...")
    if st.button("Apply Replace", use_container_width=True):
        if f_text:
            st.session_state.undo_stack.append(st.session_state.script_text)
            st.session_state.script_text = st.session_state.script_text.replace(f_text, r_text)
            st.session_state.editor_version += 1
            st.rerun()

    st.divider()
    h_col1, h_col2 = st.columns(2)
    with h_col1:
        if st.button("↩️ UNDO", use_container_width=True, disabled=len(st.session_state.undo_stack) < 1):
            st.session_state.redo_stack.append(st.session_state.script_text)
            st.session_state.script_text = st.session_state.undo_stack.pop()
            st.session_state.editor_version += 1 
            st.rerun()
    with h_col2:
        if st.button("↪️ REDO", use_container_width=True, disabled=len(st.session_state.redo_stack) < 1):
            st.session_state.undo_stack.append(st.session_state.script_text)
            st.session_state.script_text = st.session_state.redo_stack.pop()
            st.session_state.editor_version += 1 
            st.rerun()

    st.divider()
    st.subheader("📍 Jump History")
    if st.session_state.edit_history:
        for item in reversed(st.session_state.edit_history[-5:]):
            if st.button(f"L{item['block']}: {item['text'][:15]}...", key=f"hist_{item['time']}", use_container_width=True):
                st.session_state.current_line_idx = item['idx']
                st.rerun()

    st.divider()
    jump_line = st.number_input("Jump to Block #", min_value=1, value=st.session_state.current_line_idx + 1)
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
    raw_text = "\n".join([p.text for p in doc.paragraphs])
    normalized_text = normalize_script_spacing(raw_text)
    if normalized_text != st.session_state.script_text:
        st.session_state.undo_stack.append(st.session_state.script_text)
        st.session_state.script_text = normalized_text
        st.session_state.current_line_idx = 0
        st.rerun()

if st.session_state.script_text:
    cast_list = extract_characters(st.session_state.script_text)
    
    with st.expander("👤 Casting Office"):
        c1, c2 = st.columns(2)
        current_n_id = st.session_state.voice_map.get("NARRATOR", "en-GB-RyanNeural")
        n_label = VOICE_LABELS.get(current_n_id, "Eric (Male - Narrative)")
        chosen_n = st.selectbox("Narrator Voice", list(FREE_VOICES.keys()), index=list(FREE_VOICES.keys()).index(n_label))
        st.session_state.voice_map["NARRATOR"] = FREE_VOICES[chosen_n]

        for i, name in enumerate(cast_list):
            if name not in st.session_state.voice_map:
                st.session_state.voice_map[name] = guess_gender(name)
            with (c1 if i % 2 == 0 else c2):
                current_v_id = st.session_state.voice_map[name]
                v_label = VOICE_LABELS.get(current_v_id, "Guy (Male - Resonant)")
                chosen_v = st.selectbox(f"Role: {name}", list(FREE_VOICES.keys()), index=list(FREE_VOICES.keys()).index(v_label), key=f"v_sel_{name}")
                st.session_state.voice_map[name] = FREE_VOICES[chosen_v]

    raw_split = st.session_state.script_text.split('\n')
    lines = []
    for i, line in enumerate(raw_split):
        stripped = line.strip()
        if not stripped: continue
        is_dialogue = False
        if i > 0:
            prev = raw_split[i-1].strip()
            if prev in cast_list or (prev.startswith('(') and prev.endswith(')')):
                is_dialogue = True
        lines.append({"text": stripped, "is_dialogue": is_dialogue, "raw_line_num": i})

    if lines:
        curr_idx = min(st.session_state.current_line_idx, len(lines)-1)
        current_line_text = lines[curr_idx]["text"]
        target_raw_line = lines[curr_idx]["raw_line_num"]
        
        st.markdown(f"""
            <div class="performance-monitor">
                <div style="display: flex; justify-content: space-between;">
                    <small style="color:#ffd600;">BLOCK {curr_idx + 1} OF {len(lines)}</small>
                    <small style="color:#ffd600;">{"● READING" if st.session_state.playing else "○ STANDBY"}</small>
                </div>
                <span class="active-line">{current_line_text}</span>
            </div>
        """, unsafe_allow_html=True)
        
        scroll_js = f"""
            <script>
            setTimeout(function() {{
                var textArea = window.parent.document.querySelector('textarea');
                if (textArea) {{
                    var text = textArea.value;
                    var lines = text.split('\\n');
                    var charPos = 0;
                    for (var i = 0; i < Math.min({target_raw_line}, lines.length); i++) {{
                        charPos += lines[i].length + 1;
                    }}
                    textArea.focus();
                    textArea.setSelectionRange(charPos, charPos + (lines[{target_raw_line}] ? lines[{target_raw_line}].length : 0));
                    var scrollPos = ({target_raw_line} / lines.length) * textArea.scrollHeight;
                    textArea.scrollTop = scrollPos - (textArea.clientHeight / 2);
                }}
            }}, 100);
            </script>
        """

        if st.button("🖱️ CLICK TO EDIT THIS LINE", use_container_width=True):
            st.session_state.playing = False
            st.session_state.edit_history.append({
                "block": curr_idx + 1, "text": current_line_text, "idx": curr_idx, "time": time.time()
            })
            if not st.session_state.undo_stack or st.session_state.undo_stack[-1] != st.session_state.script_text:
                st.session_state.undo_stack.append(st.session_state.script_text)
            components.html(scroll_js, height=0)

    # Editor Area - versioned key ensures refresh on Undo/Redo
    current_editor_val = st.text_area(
        "Script", 
        value=st.session_state.script_text, 
        height=500, 
        key=f"editor_v{st.session_state.editor_version}", 
        label_visibility="collapsed"
    )
    
    if current_editor_val != st.session_state.script_text:
        # Prevent undo-spam for single keystrokes
        if abs(len(current_editor_val) - len(st.session_state.script_text)) > 1:
            st.session_state.undo_stack.append(st.session_state.script_text)
        st.session_state.script_text = current_editor_val
        st.session_state.playing = False

    # --- RUNTIME ---
    if st.session_state.playing and lines:
        if st.session_state.current_line_idx < len(lines):
            components.html(scroll_js, height=0)
            
            idx = st.session_state.current_line_idx
            line_data = lines[idx]
            line_content = line_data["text"]
            
            if line_content in cast_list:
                st.session_state.last_active_role = line_content
                current_role = "NARRATOR"
                read_text = f"{line_content}."
            elif line_content.isupper() and any(x in line_content for x in ["INT.", "EXT.", "DAY", "NIGHT"]):
                st.session_state.last_active_role = "NARRATOR"
                current_role = "NARRATOR"
                read_text = line_content
            elif line_data["is_dialogue"]:
                current_role = st.session_state.last_active_role
                read_text = line_content
            else:
                st.session_state.last_active_role = "NARRATOR"
                current_role = "NARRATOR"
                read_text = line_content

            v_id = st.session_state.voice_map.get(current_role, st.session_state.voice_map["NARRATOR"])
            loop = asyncio.new_event_loop()
            audio_data = loop.run_until_complete(generate_voice_bytes(read_text, v_id, rate=rate_str))
            
            if audio_data:
                b64 = base64.b64encode(audio_data).decode()
                audio_tag = f'<audio autoplay="true" id="p_{time.time()}"><source src="data:audio/mp3;base64,{b64}"></audio>'
                audio_engine_slot.markdown(audio_tag, unsafe_allow_html=True)
                w_count = len(read_text.split())
                wait_time = (max(1.8, (w_count / 140) * 60)) / speed_factor
                time.sleep(wait_time + 0.3)
            
            st.session_state.current_line_idx += 1
            st.rerun()
        else:
            st.session_state.playing = False
            st.session_state.current_line_idx = 0
            st.rerun()