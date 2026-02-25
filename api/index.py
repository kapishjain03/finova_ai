import os
from flask import Flask, request, jsonify, send_file
import requests
from dotenv import load_dotenv

# Load local .env if it exists (not used in Vercel)
load_dotenv()

app = Flask(__name__)

# Constants - using os.environ.get is safer and stripping removes trailing newlines
SARVAM_KEY = os.environ.get("SARVAM_KEY", "").strip() or None
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY", "").strip() or None

@app.route("/")
def home():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return send_file(os.path.join(current_dir, "index.html"))

@app.route("/api/translate", methods=["POST"])
def translate():
    if not SARVAM_KEY:
        return jsonify({"error": "SARVAM_KEY not configured"}), 500
    data = request.json
    url = "https://api.sarvam.ai/translate"
    headers = {"Content-Type": "application/json", "api-subscription-key": SARVAM_KEY}
    try:
        response = requests.post(url, json=data, headers=headers)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

SYSTEM_PROMPT = """You are Kapish, a friendly and helpful loan assistant for Finova Capital, an NBFC in India that gives small business loans (MSME loans) to micro entrepreneurs.

Your job is to answer questions from borrowers who are semi-literate small business owners in rural and semi-urban India. They may ask about:
- EMI, interest rates, loan tenure, processing fees
- Loan Against Property (LAP)
- CIBIL score
- How to apply for a loan
- What documents are needed
- General finance questions

Always answer in simple, clear English (it will be translated later). Use very simple language, short sentences, and relatable examples like "think of it like paying rent every month". Avoid jargon. Be warm, patient and encouraging. Keep answers under 4 sentences."""

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
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": question}]
    
    payload = {
        "model": "anthropic/claude-haiku-4.5",
        "max_tokens": 300,
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
    body = request.json
    raw_inputs = body.get('inputs', [])
    target_lang = body.get('target_language_code', 'hi-IN')
    speaker = body.get('speaker', 'ritu')

    # Sarvam TTS has a ~500 char per-input limit. Split long text into chunks.
    MAX_CHARS = 480
    chunked_inputs = []
    for text in raw_inputs:
        if len(text) <= MAX_CHARS:
            chunked_inputs.append(text)
        else:
            # Split at sentence boundaries (। or . or | followed by space)
            import re
            sentences = re.split(r'(?<=[।.।|])\s+', text)
            current_chunk = ''
            for sentence in sentences:
                if len(current_chunk) + len(sentence) + 1 <= MAX_CHARS:
                    current_chunk = (current_chunk + ' ' + sentence).strip()
                else:
                    if current_chunk:
                        chunked_inputs.append(current_chunk)
                    # If a single sentence is still too long, just add it as-is
                    current_chunk = sentence
            if current_chunk:
                chunked_inputs.append(current_chunk)

    all_audios = []
    for chunk in chunked_inputs:
        clean_body = {
            'inputs': [chunk],
            'target_language_code': target_lang,
            'speaker': speaker,
            'model': 'bulbul:v3',
            'speech_sample_rate': 22050,
            'enable_preprocessing': True,
            'pace': 0.9
        }
        try:
            resp = requests.post(
                'https://api.sarvam.ai/text-to-speech',
                headers={'Content-Type': 'application/json', 'api-subscription-key': SARVAM_KEY},
                json=clean_body,
                timeout=30
            )
            data = resp.json()
            if resp.status_code != 200:
                print(f"TTS error: {data}")
                return jsonify(data), resp.status_code
            if data.get('audios'):
                all_audios.extend(data['audios'])
        except requests.exceptions.Timeout:
            return jsonify({'error': 'Text-to-speech request timed out'}), 504
        except Exception as e:
            return jsonify({'error': f'Text-to-speech failed: {str(e)}'}), 500

    # Combine all audio chunks — client will play the first one
    # For simplicity, concatenate base64 WAV data (all same format)
    if all_audios:
        # Return all chunks; client plays first, we could concatenate but
        # returning the first chunk is simpler and works for auto-play
        import base64
        combined = b''
        for i, audio_b64 in enumerate(all_audios):
            raw = base64.b64decode(audio_b64)
            if i == 0:
                combined = raw  # first chunk includes WAV header
            else:
                combined += raw[44:]  # skip WAV header on subsequent chunks
        combined_b64 = base64.b64encode(combined).decode('utf-8')
        return jsonify({'audios': [combined_b64]}), 200
    else:
        return jsonify({'error': 'No audio generated'}), 500

@app.route("/api/stt", methods=["POST"])
def stt():
    if not SARVAM_KEY:
        return jsonify({"error": "SARVAM_KEY not configured"}), 500
    audio_file = request.files.get('file')
    lang = request.form.get('language_code', 'hi-IN')
    if not audio_file:
        return jsonify({"error": "No audio file provided"}), 400
    try:
        resp = requests.post(
            'https://api.sarvam.ai/speech-to-text',
            headers={'api-subscription-key': SARVAM_KEY},
            files={'file': (audio_file.filename, audio_file.read(), audio_file.content_type)},
            data={'language_code': lang, 'model': 'saarika:v2'},
            timeout=30
        )
        data = resp.json()
        print("STT status:", resp.status_code, "| response:", data)
        return jsonify(data), resp.status_code
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Speech-to-text request timed out'}), 504
    except Exception as e:
        return jsonify({'error': f'Speech-to-text failed: {str(e)}'}), 500

if __name__ == "__main__":
    app.run(port=5000)
