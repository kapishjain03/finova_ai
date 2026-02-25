import os
from flask import Flask, request, jsonify, send_file
import requests
from dotenv import load_dotenv

# Load local .env if it exists (not used in Vercel)
load_dotenv()

app = Flask(__name__)

# Constants - using os.environ.get is safer
SARVAM_KEY = os.environ.get("SARVAM_KEY")
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")

@app.route("/")
def home():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return send_file(os.path.join(current_dir, "index.html"))

@app.route("/api/translate", methods=["POST"])
def translate():
    if not SARVAM_KEY:
        return jsonify({"error": "SARVAM_KEY not configured"}), 500
    data = request.json
    url = "https://api.sarvam.ai/translate/v1"
    headers = {"Content-Type": "application/json", "api-key": SARVAM_KEY}
    try:
        response = requests.post(url, json=data, headers=headers)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ask", methods=["POST"])
def ask():
    if not OPENROUTER_KEY:
        return jsonify({"error": "OPENROUTER_KEY not configured"}), 500
    data = request.json
    question = data.get("question")
    history = data.get("history", [])
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = history + [{"role": "user", "content": question}]
    
    payload = {
        "model": "google/gemini-2.0-flash-exp:free",
        "messages": messages
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tts", methods=["POST"])
def tts():
    if not SARVAM_KEY:
        return jsonify({"error": "SARVAM_KEY not configured"}), 500
    data = request.json
    url = "https://api.sarvam.ai/text-to-speech"
    headers = {"Content-Type": "application/json", "api-key": SARVAM_KEY}
    try:
        response = requests.post(url, json=data, headers=headers)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/stt", methods=["POST"])
def stt():
    if not SARVAM_KEY:
        return jsonify({"error": "SARVAM_KEY not configured"}), 500
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    language_code = request.form.get('language_code', 'hi-IN')
    
    url = "https://api.sarvam.ai/speech-to-text"
    headers = {"api-key": SARVAM_KEY}
    
    files = {'file': (file.filename, file.stream, file.mimetype)}
    data = {'language_code': language_code}
    
    try:
        response = requests.post(url, files=files, data=data, headers=headers)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=5000)
