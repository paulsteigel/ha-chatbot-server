#!/usr/bin/env python3
import os
import logging
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
from pathlib import Path
from werkzeug.utils import secure_filename

# Set up logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
# Validate log level
if LOG_LEVEL not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
    LOG_LEVEL = "INFO"

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder='/usr/bin/static')
CORS(app)

# Get configuration from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_VOICE = os.getenv("OPENAI_VOICE", "alloy")
OPENAI_LANGUAGE = os.getenv("OPENAI_LANGUAGE", "auto")  # Changed to 'auto'
PORT = int(os.getenv("PORT", "5000"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "500"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))

logger.info(f"Starting Yên Hoà ChatBot Server")
logger.info(f"Model: {OPENAI_MODEL}")
logger.info(f"Voice: {OPENAI_VOICE}")
logger.info(f"Language: {OPENAI_LANGUAGE}")
logger.info(f"Port: {PORT}")

# Validate API key
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY is not set!")
else:
    logger.info("OpenAI API key is configured")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Import utilities
from utils.content_filter import is_safe_content
from utils.response_templates import get_response_template

def detect_language(text):
    """
    Simple language detection based on character set
    Returns 'vi' for Vietnamese, 'en' for English, 'auto' for mixed/unknown
    """
    vietnamese_chars = 'àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ'
    
    text_lower = text.lower()
    has_vietnamese = any(char in vietnamese_chars for char in text_lower)
    has_english = any(char.isalpha() and char.isascii() for char in text_lower)
    
    if has_vietnamese and not has_english:
        return 'vi'
    elif has_english and not has_vietnamese:
        return 'en'
    else:
        return 'auto'

@app.route('/')
def index():
    """Serve the test interface"""
    return send_from_directory('/usr/bin/static', 'index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat requests"""
    if not client:
        return jsonify({
            'error': 'OpenAI API key not configured'
        }), 500
    
    try:
        data = request.json
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Detect user's language
        detected_lang = detect_language(user_message)
        logger.info(f"Detected language: {detected_lang} for message: {user_message[:50]}")
        
        # Content filtering
        if not is_safe_content(user_message):
            return jsonify({
                'response': get_response_template('inappropriate', detected_lang)
            })
        
        # Create chat completion with auto language detection
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": get_response_template('system', 'auto')
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE
        )
        
        assistant_message = response.choices[0].message.content
        
        return jsonify({
            'response': assistant_message,
            'model': OPENAI_MODEL,
            'detected_language': detected_lang
        })
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/api/transcribe', methods=['POST'])
def transcribe():
    """Handle audio transcription requests"""
    if not client:
        return jsonify({
            'error': 'OpenAI API key not configured'
        }), 500
    
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_audio:
            audio_file.save(temp_audio.name)
            
            # Transcribe using Whisper - let it auto-detect language
            with open(temp_audio.name, 'rb') as audio_data:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_data,
                    # Don't specify language - let Whisper detect it automatically
                )
            
            # Clean up
            os.unlink(temp_audio.name)
            
            logger.info(f"Transcribed text: {transcript.text}")
            
            return jsonify({
                'text': transcript.text
            })
    
    except Exception as e:
        logger.error(f"Error in transcribe endpoint: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/api/voice', methods=['POST'])
def voice():
    """Handle voice requests with language detection"""
    if not client:
        return jsonify({
            'error': 'OpenAI API key not configured'
        }), 500
    
    try:
        data = request.json
        text = data.get('text', '')
        
        if not text:
            return jsonify({'error': 'Text is required'}), 400
        
        # Detect language to choose appropriate voice
        detected_lang = detect_language(text)
        
        # Choose voice based on language (optional - you can keep same voice)
        voice = OPENAI_VOICE
        
        # Generate speech
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        
        # Save to temporary file
        output_path = Path("/tmp/speech.mp3")
        response.stream_to_file(output_path)
        
        return send_from_directory('/tmp', 'speech.mp3', mimetype='audio/mpeg')
    
    except Exception as e:
        logger.error(f"Error in voice endpoint: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'model': OPENAI_MODEL,
        'voice': OPENAI_VOICE,
        'language': OPENAI_LANGUAGE,
        'api_key_configured': bool(OPENAI_API_KEY)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=(LOG_LEVEL == 'DEBUG'))
