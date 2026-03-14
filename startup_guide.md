# 1. Open VS Code and ensure you are in the project folder (should see this in Terminal)
cd "C:\Users\...\GitHub\narrative-soundstage"

# 2. Wake up the environment (The Handshake)
.\venv\Scripts\activate

# 3. Launch the UI
python -m streamlit run narrativesoundstage.py

# 4. If you ever get a "Module Not Found" error, run this:
# pip install -r requirements.txt