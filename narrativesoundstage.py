"""
PROJECT: Narrative Soundstage
VERSION: 1.2.0
AUTHOR: Ida Akiwumi
ROLE: Product Architect | Narrative Strategist | Screenwriter
TECH STACK: Python, Streamlit, Edge-TTS, Asyncio, Regex

DESCRIPTION:
An intelligent script-to-performance engine designed for screenwriters and producers. 
This tool automates voice-over table reads, maintains character consistency through 
dynamic casting, and provides a real-time "active-line" prompter for editing.

IDEAL FOR:
- Film & Television Pre-production, Script Development, Screenplay Revisions & Table Reads
- Game Design Narrative Logic
- Legal Thriller & Action Comedy Script Development
- Data Storytelling & AI-Assisted Workflows
"""

__author__ = "Ida Akiwumi"
__version__ = "1.2.0"
__license__ = "Proprietary"
__status__ = "Production / Portfolio"

import streamlit as st
from docx import Document
from docx.shared import Pt
from docx.enum.style import WD_STYLE_TYPE
import re
import asyncio
import edge_tts
import io
import base64
import time
import streamlit.components.v1 as components
import random

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
    if "editor_version" not in st.session_state: st.session_state.editor_version = 0
    if "trigger_scroll" not in st.session_state: st.session_state.trigger_scroll = False

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
    except Exception as e:
        st.error(f"Voice Error ({voice_id}): {e}") # This will tell you exactly which one failed
        return None

def normalize_script_spacing(text):
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def guess_gender(name):
    """
    Randomly assigns a voice from the appropriate category to maintain variety.
    """
    # Define pools from your FREE_VOICES dictionary
    males = [
        "en-US-GuyNeural", "en-US-ChristopherNeural", "en-GB-RyanNeural", 
        "en-GB-ThomasNeural", "en-AU-WilliamNeural", "en-NG-AbeoNeural", 
        "ar-AE-HamdanNeural", "ur-PK-AsadNeural", "en-CA-LiamNeural", 
        "en-US-AndrewNeural", "en-US-BrianNeural", "en-ZA-LukeNeural", 
        "en-KE-ChilembaNeural", "zu-ZA-ThembaNeural"
    ]
    
    females = [
        "en-US-AriaNeural", "en-US-JennyNeural", "en-GB-SoniaNeural", 
        "en-GB-LibbyNeural", "en-GB-MaisieNeural", "en-NG-EzinneNeural", 
        "en-AU-NatashaNeural", "ar-AE-FatimaNeural", "zh-HK-HiuGaaiNeural", 
        "es-US-PalomaNeural", "en-US-AvaNeural", "en-US-EmmaNeural", 
        "en-KE-AsiliaNeural", "en-TZ-ImaniNeural", "en-ZA-LeahNeural"
    ]

    fem_hints = ['ARIA', 'JENNY', 'SONIA', 'MARIAN', 'GIRL', 'WOMAN', 'SISTER', 'MOTHER', 'QUEEN', 'LADY']
    masc_hints = ['GUY', 'MAN', 'BOY', 'BROTHER', 'FATHER', 'KING', 'LORD', 'HENCHMAN', 'OFFICER', 'GUARD']
    
    name_up = name.upper()
    
    # Logic for selection
    if any(hint in name_up for hint in fem_hints) or name_up.endswith('A'):
        return random.choice(females)
    if any(hint in name_up for hint in masc_hints):
        return random.choice(males)
    
    # If no hint, pick from the entire pool for maximum randomness
    return random.choice(males + females)

def extract_characters(script_text):
    # Regex finds all-caps lines
    potential_names = re.findall(r'^(?!INT\.|EXT\.|SCENE|ACT)[A-Z][A-Z\d\s\.]+$', script_text, re.MULTILINE)
    
    # Expanded exclusion list for transitions and technical beats
    exclude = [
        "INT.", "EXT.", "CUT TO:", "FADE IN:", "FADE OUT:", "CONTINUED:", 
        "V.O.", "O.C.", "THE END", "ACT ONE", "ACT TWO", "ACT THREE", 
        "SCENE", "TITLE", "CARD", "PAGE", "DAY", "NIGHT", "DISSOLVE TO:",
        "MOMENTS LATER", "LATER", "PROLOGUE", "EPILOGUE", "FADE TO:", 
        "FADE TO BLACK.", "BEAT.", "MATCH CUT:", "JUMP CUT:", "BACK TO:"
    ]
    
    clean_names = []
    for n in potential_names:
        name = n.strip()
        # Filter: 
        # 1. Not in exclude list
        # 2. Not ending in a period (usually a transition/beat)
        # 3. Not just a number
        # 4. Length > 1
        if (name not in exclude and 
            not name.endswith('.') and 
            len(name) > 1 and 
            not re.match(r'^\d+\.$', name)):
            clean_names.append(name)
            
    return sorted(list(set(clean_names)))



def get_docx_download(text):
    doc = Document()
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Courier New'
    font.size = Pt(12)
    
    for line in text.split('\n'):
        p = doc.add_paragraph()
        run = p.add_run(line)
        run.font.name = 'Courier New'
        run.font.size = Pt(12)
        
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- UI SETUP ---
st.set_page_config(
    page_title="Narrative Soundstage | Designed by Ida Akiwumi", 
    page_icon="🎭",
    layout="wide"
)
# CUSTOM CSS FOR STYLING
st.markdown("""
    <style>
    /* 1. FIX SIDEBAR TOGGLE & REMOVE OVERLAP */
    [data-testid="stHeader"] {
        background-color: rgba(0,0,0,0) !important;
        color: white !important;
    }

    .compact-header {
        margin-top: 35px !important; 
        z-index: 999999;
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
        position: relative;
    }

    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 0rem !important;
        max-width: 95% !important;
    }

    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}

    .sticky-prompter {
        position: -webkit-sticky;
        position: sticky;
        top: 0;
        z-index: 999;
        background-color: #0e1117;
        padding-bottom: 15px;
        border-bottom: 1px solid #333;
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
        border-left: 10px solid #ffd600;
        font-family: 'Courier New', Courier, monospace;
    }
    .active-line { color: #ffd600; font-weight: bold; font-size: 24px; display: block; margin-top: 5px; }
    .stats-badge { background-color: #ffd600; color: #000; padding: 2px 10px; border-radius: 4px; font-weight: bold; }
   
   @keyframes pulse-yellow {
        0% { box-shadow: 0 0 0 0 rgba(255, 214, 0, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(255, 214, 0, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 214, 0, 0); }
    }

    .mobile-hint {
        display: none;
        background-color: #ffd600;
        color: #000;
        padding: 12px;
        border-radius: 4px;
        text-align: center;
        font-family: 'Courier New', Courier, monospace;
        font-weight: bold;
        margin-top: 10px;
        margin-bottom: 15px;
        border: 2px solid #000;
        animation: pulse-yellow 2s infinite;
    }

    @media (max-width: 768px) {
        .mobile-hint {
            display: block;
        }
    }
   
    </style>
""", unsafe_allow_html=True)

FREE_VOICES = {
    # --- MALE ---
    "Guy (Male - US)": "en-US-GuyNeural",
    "Christopher (Male - Deep)": "en-US-ChristopherNeural",
    "Eric (Male - UK Narrative)": "en-GB-RyanNeural",
    "Thomas (Male - UK Formal)": "en-GB-ThomasNeural",
    "Natascha (Male - AU Aboriginal Hint)": "en-AU-WilliamNeural",
    "Abeo (Male - African/NG)": "en-NG-AbeoNeural",
    "Hamdan (Male - Arabic/UAE)": "ar-AE-HamdanNeural",
    "Asad (Male - Asian/PK)": "ur-PK-AsadNeural",
    "Liam (Male - Canadian)": "en-CA-LiamNeural", # Ensure en-CA prefix
    "Andrew (Male - Energetic/Afro-Latino)": "en-US-AndrewNeural",
    "Brian (Male - Casual US/Afro-Latino)": "en-US-BrianNeural",
    "Luke (Male - Caribbean/SA Hint)": "en-ZA-LukeNeural",
    "Chilemba (Male - East African)": "en-KE-ChilembaNeural",
    "Themba (Male - Zulu/Southern African)": "zu-ZA-ThembaNeural",
    "Gonzalo (Male - Latino-Strong)": "es-CO-GonzaloNeural",
    "Emilio (Male - Latino)": "es-DO-EmilioNeural",
    # --- FEMALE ---
    "Aria (Female - US Pro)": "en-US-AriaNeural",
    "Jenny (Female - US Friendly)": "en-US-JennyNeural",
    "Sonia (Female - UK Soft)": "en-GB-SoniaNeural",
    "Libby (Female - UK Bright/Informal Brit)": "en-GB-LibbyNeural",
    "Maisie (Female - Informal Brit)": "en-GB-MaisieNeural",
    "Anike (Female - African/NG)": "en-NG-EzinneNeural",
    "Natasha (Female - AU Aboriginal Hint)": "en-AU-NatashaNeural",
    "Fatima (Female - Arabic/UAE)": "ar-AE-FatimaNeural",
    "Yan (Female - Asian/HK)": "zh-HK-HiuGaaiNeural",
    "Clara (Female - US Latino Hint)": "es-US-PalomaNeural",
    "Ava (Female - US Gen-Z/AA Hint)": "en-US-AvaNeural",
    "Emma (Female - Casual US)": "en-US-EmmaNeural",
    "Asilia (Female - African/KE)": "en-KE-AsiliaNeural", # Ensure en-KE prefix
    "Imani (Female - East African)": "en-TZ-ImaniNeural",
    "Leah (Female - Southern African)": "en-ZA-LeahNeural",
    "Ramona (Female - Latina)": "es-DO-RamonaNeural",
    "Belkys (Female - Afro Latina/Latina)": "es-CU-BelkysNeural",
}

VOICE_LABELS = {v: k for k, v in FREE_VOICES.items()}
word_count = len(st.session_state.script_text.split()) if st.session_state.script_text else 0

st.markdown(f'''
    <div class="compact-header">
        <span>🎭 NARRATIVE SOUNDSTAGE</span>
        <span>WORDS: <span class="stats-badge">{word_count}</span></span>
    </div>
''', unsafe_allow_html=True)
# This only renders the div; the CSS above handles hiding it on Desktop
st.markdown('<div class="mobile-hint">⬅️ OPEN SIDEBAR FOR STUDIO CONTROLS</div>', unsafe_allow_html=True)


# --- SIDEBAR ---
with st.sidebar:
    st.title("🎬 Studio Controls")
    st.subheader("⏱️ Reading Controls")
    pause_buffer = st.slider("Line Pause Buffer (Secs)", 0.0, 2.0, 1.3, 0.1)
    speed_factor = st.slider("Playback Speed", 0.5, 2.0, 1.4, 0.1, key="speed")
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
        if st.button("🔄 RESTART", use_container_width=True):
            st.session_state.current_line_idx = 0
            st.session_state.playing = False
            st.rerun()
            
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

    if st.session_state.script_text:
        if st.button("🖱️ EDIT CURRENT LINE", use_container_width=True):
            st.session_state.playing = False
            st.session_state.trigger_scroll = True
            st.rerun()

    st.subheader("🔍 Find & Replace")
    f_text = st.text_input("Find text...")
    r_text = st.text_input("Replace with...")
    
    if st.button("Apply Replace", use_container_width=True):
        if f_text:
            st.session_state.undo_stack.append(st.session_state.script_text)
            st.session_state.script_text = st.session_state.script_text.replace(f_text, r_text)
            st.session_state.editor_version += 1
            st.rerun()

    st.subheader("📍 Navigation")
    jump_line = st.number_input("Jump to Block #", min_value=1, value=st.session_state.current_line_idx + 1)
    if st.button("🚀 Jump", use_container_width=True):
        st.session_state.current_line_idx = int(jump_line) - 1
        st.rerun()

    audio_engine_slot = st.empty()
    if st.session_state.script_text:
        docx_data = get_docx_download(st.session_state.script_text)
        st.download_button("💾 Export .docx", docx_data, "Script_Updated.docx", use_container_width=True)
        
        # --- CREATOR INFO ---
    st.markdown("---")
    st.markdown("""
        **Developed by Ida Akiwumi**,  *Product Architect & Narrative Strategist* Specializing in AI-assisted workflows for Film, Gaming, and Data Storytelling.
    """)




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
        st.session_state.editor_version += 1 
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
        # Parentheticals should be read by the Narrator, not treated as dialogue
        is_parenthetical = stripped.startswith('(') and stripped.endswith(')')
        
        if i > 0 and not is_parenthetical:
            prev = raw_split[i-1].strip()
            # Only trigger dialogue if the previous line was a Character or another Parenthetical
            if prev in cast_list or (prev.startswith('(') and prev.endswith(')')):
                is_dialogue = True
        
        lines.append({
            "text": stripped, 
            "is_dialogue": is_dialogue, 
            "is_parenthetical": is_parenthetical, # New flag
            "raw_line_num": i
        })

    if lines:
        curr_idx = min(st.session_state.current_line_idx, len(lines)-1)
        current_line_text = lines[curr_idx]["text"]
        target_raw_line = lines[curr_idx]["raw_line_num"]
        
        st.markdown(f"""
            <div class="sticky-prompter">
                <div class="performance-monitor">
                    <div style="display: flex; justify-content: space-between;">
                        <small style="color:#ffd600;">BLOCK {curr_idx + 1} OF {len(lines)}</small>
                        <small style="color:#ffd600;">{"● READING" if st.session_state.playing else "○ STANDBY"}</small>
                    </div>
                    <span class="active-line">{current_line_text}</span>
                </div>
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
                    
                    if ({target_raw_line} > 0) {{
                        var totalScroll = textArea.scrollHeight;
                        var relativePos = {target_raw_line} / lines.length;
                        textArea.scrollTop = (totalScroll * relativePos) - 150;
                    }}
                }}
            }}, 100);
            </script>
        """

        if st.session_state.trigger_scroll:
            components.html(scroll_js, height=0)
            st.session_state.trigger_scroll = False

    current_editor_val = st.text_area(
        "Script", 
        value=st.session_state.script_text, 
        height=900, 
        key=f"editor_v{st.session_state.editor_version}", 
        label_visibility="collapsed"
    )
    
    if current_editor_val != st.session_state.script_text:
        st.session_state.script_text = current_editor_val
        st.session_state.playing = False

    # --- RUNTIME (FIXED SCROLL & SOUND) ---
    if st.session_state.playing and lines:
        if st.session_state.current_line_idx < len(lines):
            
            # TRIGGER SCROLL ONLY AFTER LINE 50 
            if st.session_state.current_line_idx > 50:
                components.html(scroll_js, height=0)
            
            idx = st.session_state.current_line_idx
            line_data = lines[idx]
            line_content = line_data["text"]
            
            # --- VOICE SELECTION LOGIC ---
            if line_content in cast_list:
                st.session_state.last_active_role = line_content
                current_role = "NARRATOR"
                read_text = f"{line_content}."
            elif line_data.get("is_parenthetical"):
                current_role = "NARRATOR"
                read_text = line_content
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

            # --- AUDIO EXECUTION ---
            v_id = st.session_state.voice_map.get(current_role, st.session_state.voice_map["NARRATOR"])
            loop = asyncio.new_event_loop()
            audio_data = loop.run_until_complete(generate_voice_bytes(read_text, v_id, rate=rate_str))
            
            if audio_data:
                b64 = base64.b64encode(audio_data).decode()
                audio_tag = f'<audio autoplay="true" id="p_{time.time()}"><source src="data:audio/mp3;base64,{b64}"></audio>'
                audio_engine_slot.markdown(audio_tag, unsafe_allow_html=True)
                
                # Timing calculation
                w_count = len(read_text.split())
                wait_time = ((max(2.2, (w_count / 140) * 60)) / speed_factor) + pause_buffer
                time.sleep(wait_time)
            
            st.session_state.current_line_idx += 1
            st.rerun()
        else:
            st.session_state.playing = False
            st.session_state.current_line_idx = 0
            st.rerun()