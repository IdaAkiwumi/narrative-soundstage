import streamlit as st
from docx import Document
import io

# UX Header
st.title("🎭 Narrative Soundstage")
st.subheader("Turn your screenplay into a live table read.")

# Sidebar for Voice Settings (Leo Midheaven Authority)
with st.sidebar:
    st.header("Cast Settings")
    tone = st.selectbox("Select Scene Tone", ["Thriller", "Action-Comedy", "Drama"])
    speed = st.slider("Reading Pace", 0.5, 1.5, 1.0)

# File Uploader - Handling .doc and .fountain
uploaded_file = st.file_uploader("Upload your script (.docx or .fountain)", type=["docx", "fountain"])

if uploaded_file is not None:
    st.success("Script Loaded Successfully!")
    
    # Logic to handle .docx
    if uploaded_file.name.endswith(".docx"):
        doc = Document(uploaded_file)
        full_text = [para.text for para in doc.paragraphs]
        script_content = "\n".join(full_text)
    else:
        script_content = uploaded_file.read().decode("utf-8")

    # Display a preview to the user
    st.text_area("Script Preview", script_content, height=300)
    
    if st.button("Generate Table Read"):
        st.info("Parsing characters and generating voices... (This is where the magic happens)")