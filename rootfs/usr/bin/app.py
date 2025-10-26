#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kids ChatBot Server for Home Assistant
Educational AI Voice Assistant with Content Filtering
"""

import os
import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI

from utils import ContentFilter, ResponseTemplates

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration file path (created by run.sh)
CONFIG_FILE = "/tmp/addon_config.json"

def load_config():
    """Load configuration from Home Assistant addon config"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            logging.warning(f"Config file not found: {CONFIG_FILE}")
            return {}
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        return {}

# Load configuration
config = load_config()

# Setup logging
log_level = config.get('log_level', 'info').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get configuration values
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
LISTENING_PORT = int(os.environ.get('LISTENING_PORT', 5000))
LANGUAGE = config.get('language', 'vi')
MAX_AUDIO_SIZE = config.get('max_audio_size_mb', 25) * 1024 * 1024  # Convert to bytes
RESPONSE_VOICE = config.get('response_voice', 'nova')
SAVE_CONVERSATIONS = config.get('save_conversations', False)

# Validate API key
if not OPENAI_API_KEY:
    logger.error("OpenAI API Key is missing!")
    raise ValueError("OpenAI API Key is required")

# Initialize OpenAI client
try:
    client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("OpenAI client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    raise

# Initialize content filter
content_filter = ContentFilter(
    enabled=config.get('enable_content_filter', True),
    bad_words=config.get('bad_words_list', [])
)

# Initialize response templates
response_templates = ResponseTemplates(
    personality=config.get('bot_personality', 'gentle_teacher'),
    educational_mode=config.get('educational_mode', True),
    language=LANGUAGE
)

# In-memory conversation storage
# Format: {user_id: [{"role": "user", "content": "..."}, ...]}
conversations = {}

# Temporary audio files storage
TEMP_AUDIO_DIR = "/tmp/chatbot_audio"
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_conversation_history(user_id, max_messages=10):
    """Get conversation history for a user"""
    if user_id not in conversations:
        conversations[user_id] = []
    return conversations[user_id][-max_messages:]


def add_to_conversation(user_id, role, content):
    """Add a message to conversation history"""
    if user_id not in conversations:
        conversations[user_id] = []
    
    conversations[user_id].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })
    
    # Keep only last 20 messages to prevent memory issues
    if len(conversations[user_id]) > 20:
        conversations[user_id] = conversations[user_id][-20:]


def save_conversation_log(user_id, user_text, response_text, filtered=False):
    """Save conversation to log file"""
    if not SAVE_CONVERSATIONS:
        return
    
    try:
        log_dir = "/share/chatbot_logs"
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"{user_id}.jsonl")
        
        with open(log_file, 'a', encoding='utf-8') as f:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "user_text": user_text,
                "response_text": response_text,
                "filtered": filtered
            }
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        
        logger.debug(f"Conversation saved for user {user_id}")
    
    except Exception as e:
        logger.error(f"Error saving conversation log: {e}")


def speech_to_text(audio_file_path):
    """Convert audio to text using OpenAI Whisper"""
    try:
        logger.info("Starting speech-to-text conversion...")
        
        with open(audio_file_path, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=LANGUAGE
            )
        
        logger.info(f"Transcription result: {transcript.text}")
        return transcript.text
    
    except Exception as e:
        logger.error(f"Speech-to-text error: {e}")
        raise


def generate_ai_response(user_text, user_id):
    """Generate AI response using OpenAI GPT"""
    try:
        logger.info(f"Generating AI response for user {user_id}...")
        
        # Get system prompt
        system_prompt = response_templates.get_system_prompt()
        
        # Build messages for API
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        history = get_conversation_history(user_id, max_messages=10)
        for msg in history:
            if msg['role'] in ['user', 'assistant']:
                messages.append({
                    "role": msg['role'],
                    "content": msg['content']
                })
        
        # Add current user message
        messages.append({"role": "user", "content": user_text})
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )
        
        assistant_message = response.choices[0].message.content
        logger.info(f"AI response: {assistant_message}")
        
        # Add politeness reminder if enabled
        if config.get('politeness_reminders', True):
            assistant_message = response_templates.add_politeness_reminder(assistant_message)
        
        return assistant_message
    
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return response_templates.get_error_response()


def text_to_speech(text):
    """Convert text to speech using OpenAI TTS"""
    try:
        logger.info("Converting text to speech...")
        
        response = client.audio.speech.create(
            model="tts-1",
            voice=RESPONSE_VOICE,
            input=text
        )
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix='.mp3',
            dir=TEMP_AUDIO_DIR
        )
        
        # Write audio content
        response.stream_to_file(temp_file.name)
        temp_file.close()
        
        logger.info(f"Audio file created: {temp_file.name}")
        return temp_file.name
    
    except Exception as e:
        logger.error(f"Text-to-speech error: {e}")
        raise


def cleanup_old_audio_files():
    """Clean up old temporary audio files (older than 1 hour)"""
    try:
        import time
        current_time = time.time()
        
        for filename in os.listdir(TEMP_AUDIO_DIR):
            file_path = os.path.join(TEMP_AUDIO_DIR, filename)
            
            # Check if file is older than 1 hour (3600 seconds)
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > 3600:
                    os.remove(file_path)
                    logger.debug(f"Cleaned up old audio file: {filename}")
    
    except Exception as e:
        logger.error(f"Error cleaning up audio files: {e}")


# ============================================
# API ENDPOINTS
# ============================================

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        "service": "Kids ChatBot Server",
        "version": "1.0.0",
        "status": "running"
    }), 200


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Kids ChatBot Server",
        "version": "1.0.0"
    }), 200


@app.route('/api/info', methods=['GET'])
def get_info():
    """Get server information and configuration"""
    return jsonify({
        "name": "Kids ChatBot Server",
        "version": "1.0.0",
        "language": LANGUAGE,
        "voice": RESPONSE_VOICE,
        "content_filter_enabled": config.get('enable_content_filter', True),
        "educational_mode": config.get('educational_mode', True),
        "bot_personality": config.get('bot_personality', 'gentle_teacher'),
        "max_audio_size_mb": config.get('max_audio_size_mb', 25)
    }), 200


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Main chat endpoint for ESP32 communication
    
    Accepts:
        - Audio file (multipart/form-data)
        - Text input (JSON)
    
    Returns:
        - JSON response with text and audio URL
    """
    try:
        # Clean up old files periodically
        cleanup_old_audio_files()
        
        # Get user ID
        user_id = request.form.get('user_id', 'default') if request.form else \
                  request.json.get('user_id', 'default') if request.json else 'default'
        
        logger.info(f"Processing chat request from user: {user_id}")
        
        user_text = None
        
        # Handle audio input
        if 'audio' in request.files:
            audio_file = request.files['audio']
            
            # Check file size
            audio_file.seek(0, os.SEEK_END)
            file_size = audio_file.tell()
            audio_file.seek(0)
            
            if file_size > MAX_AUDIO_SIZE:
                logger.warning(f"Audio file too large: {file_size} bytes")
                return jsonify({
                    "error": "Audio file too large",
                    "max_size_mb": config.get('max_audio_size_mb', 25)
                }), 400
            
            # Save temporary audio file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
                audio_file.save(temp_audio.name)
                temp_audio_path = temp_audio.name
            
            logger.info(f"Audio file saved: {temp_audio_path}")
            
            # Speech to text
            try:
                user_text = speech_to_text(temp_audio_path)
            finally:
                # Clean up temporary file
                if os.path.exists(temp_audio_path):
                    os.unlink(temp_audio_path)
        
        # Handle text input
        elif request.json and 'text' in request.json:
            user_text = request.json['text']
        
        elif request.form and 'text' in request.form:
            user_text = request.form['text']
        
        else:
            logger.warning("No audio or text provided in request")
            return jsonify({
                "error": "No audio or text provided"
            }), 400
        
        logger.info(f"User input: {user_text}")
        
        # Content filtering
        filter_result = content_filter.check(user_text)
        
        if filter_result['is_inappropriate']:
            # Generate educational response for inappropriate content
            response_text = response_templates.get_inappropriate_response(
                detected_words=filter_result['detected_words']
            )
            logger.warning(f"Inappropriate content detected: {filter_result['detected_words']}")
            filtered = True
        
        else:
            # Add user message to history
            add_to_conversation(user_id, 'user', user_text)
            
            # Generate normal AI response
            response_text = generate_ai_response(user_text, user_id)
            
            # Add assistant message to history
            add_to_conversation(user_id, 'assistant', response_text)
            
            filtered = False
        
        # Convert response to speech
        audio_response_path = text_to_speech(response_text)
        audio_filename = Path(audio_response_path).name
        
        # Save conversation log
        save_conversation_log(user_id, user_text, response_text, filtered)
        
        # Return response
        return jsonify({
            "success": True,
            "user_id": user_id,
            "user_text": user_text,
            "response_text": response_text,
            "audio_url": f"/api/audio/{audio_filename}",
            "filtered": filtered,
            "detected_words": filter_result.get('detected_words', []) if filtered else []
        }), 200
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        return jsonify({
            "error": str(e),
            "success": False
        }), 500


@app.route('/api/audio/<filename>', methods=['GET'])
def get_audio(filename):
    """Serve audio file"""
    try:
        file_path = os.path.join(TEMP_AUDIO_DIR, filename)
        
        if not os.path.exists(file_path):
            logger.warning(f"Audio file not found: {filename}")
            return jsonify({"error": "File not found"}), 404
        
        return send_file(
            file_path,
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        logger.error(f"Error serving audio file: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    """Reset conversation history for a user"""
    try:
        data = request.json if request.json else {}
        user_id = data.get('user_id', 'default')
        
        if user_id in conversations:
            conversations[user_id] = []
            logger.info(f"Conversation history reset for user: {user_id}")
        
        return jsonify({
            "success": True,
            "message": f"Conversation history reset for user {user_id}"
        }), 200
    
    except Exception as e:
        logger.error(f"Error resetting conversation: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Get all active conversation user IDs"""
    try:
        return jsonify({
            "user_ids": list(conversations.keys()),
            "total_users": len(conversations)
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/history/<user_id>', methods=['GET'])
def get_history(user_id):
    """Get conversation history for a specific user"""
    try:
        history = get_conversation_history(user_id, max_messages=50)
        
        return jsonify({
            "user_id": user_id,
            "messages": history,
            "count": len(history)
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        "error": "Endpoint not found",
        "status": 404
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        "error": "Internal server error",
        "status": 500
    }), 500


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("Kids ChatBot Server Starting...")
    logger.info("=" * 60)
    logger.info(f"Port: {LISTENING_PORT}")
    logger.info(f"Language: {LANGUAGE}")
    logger.info(f"Voice: {RESPONSE_VOICE}")
    logger.info(f"Content Filter: {config.get('enable_content_filter', True)}")
    logger.info(f"Educational Mode: {config.get('educational_mode', True)}")
    logger.info(f"Bot Personality: {config.get('bot_personality', 'gentle_teacher')}")
    logger.info(f"Max Audio Size: {config.get('max_audio_size_mb', 25)} MB")
    logger.info(f"Save Conversations: {SAVE_CONVERSATIONS}")
    logger.info("=" * 60)
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=LISTENING_PORT,
        debug=False,
        threaded=True
    )
