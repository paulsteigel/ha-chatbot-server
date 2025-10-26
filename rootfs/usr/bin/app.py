#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from openai import OpenAI
import tempfile
from pathlib import Path
from utils.content_filter import ContentFilter
from utils.response_templates import ResponseTemplates

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Load configuration from Home Assistant
CONFIG_FILE = "/tmp/addon_config.json"

def load_config():
    """Load configuration from addon config file"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        return {}

config = load_config()

# Setup logging
log_level = config.get('log_level', 'info').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# Initialize content filter and response templates
content_filter = ContentFilter(
    enabled=config.get('enable_content_filter', True),
    bad_words=config.get('bad_words_list', [])
)

response_templates = ResponseTemplates(
    personality=config.get('bot_personality', 'gentle_teacher'),
    educational_mode=config.get('educational_mode', True),
    language=config.get('language', 'vi')
)

# Conversation history storage
conversations = {}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "Kids ChatBot Server"}), 200

@app.route('/api/info', methods=['GET'])
def get_info():
    """Get server information"""
    return jsonify({
        "name": "Kids ChatBot Server",
        "version": "1.0.0",
        "language": config.get('language', 'vi'),
        "content_filter": config.get('enable_content_filter', True),
        "educational_mode": config.get('educational_mode', True)
    }), 200

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Handle chat requests from ESP32
    Expects: audio file or text input
    Returns: text response + audio file URL
    """
    try:
        user_id = request.form.get('user_id', 'default')
        
        # Handle audio input
        if 'audio' in request.files:
            audio_file = request.files['audio']
            
            # Save temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
                audio_file.save(temp_audio.name)
                temp_audio_path = temp_audio.name
            
            # Speech to text
            logger.info("Transcribing audio...")
            with open(temp_audio_path, 'rb') as audio:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio,
                    language=config.get('language', 'vi')
                )
            
            user_text = transcript.text
            os.unlink(temp_audio_path)
        
        # Handle text input
        elif request.json and 'text' in request.json:
            user_text = request.json['text']
        else:
            return jsonify({"error": "No audio or text provided"}), 400
        
        logger.info(f"User input: {user_text}")
        
        # Content filtering
        filter_result = content_filter.check(user_text)
        
        if filter_result['is_inappropriate']:
            # Generate educational response for inappropriate content
            response_text = response_templates.get_inappropriate_response(
                detected_words=filter_result['detected_words']
            )
            logger.warning(f"Inappropriate content detected: {filter_result['detected_words']}")
        else:
            # Generate normal AI response
            response_text = generate_ai_response(user_text, user_id)
        
        # Text to speech
        logger.info("Generating audio response...")
        audio_response_path = text_to_speech(response_text)
        
        # Save conversation if enabled
        if config.get('save_conversations', False):
            save_conversation(user_id, user_text, response_text)
        
        return jsonify({
            "success": True,
            "user_text": user_text,
            "response_text": response_text,
            "audio_url": f"/api/audio/{Path(audio_response_path).name}",
            "filtered": filter_result['is_inappropriate']
        }), 200
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

def generate_ai_response(user_text, user_id):
    """Generate AI response using OpenAI GPT"""
    try:
        # Get or create conversation history
        if user_id not in conversations:
            conversations[user_id] = []
        
        # System prompt for educational chatbot
        system_prompt = response_templates.get_system_prompt()
        
        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversations[user_id][-10:])  # Last 10 messages
        messages.append({"role": "user", "content": user_text})
        
        # Call OpenAI
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=200
        )
        
        assistant_message = response.choices[0].message.content
        
        # Update conversation history
        conversations[user_id].append({"role": "user", "content": user_text})
        conversations[user_id].append({"role": "assistant", "content": assistant_message})
        
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
        response = client.audio.speech.create(
            model="tts-1",
            voice=config.get('response_voice', 'nova'),
            input=text
        )
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir='/tmp')
        response.stream_to_file(temp_file.name)
        
        return temp_file.name
    
    except Exception as e:
        logger.error(f"Error in text-to-speech: {e}")
        raise

@app.route('/api/audio/<filename>', methods=['GET'])
def get_audio(filename):
    """Serve audio file"""
    try:
        file_path = f"/tmp/{filename}"
        if os.path.exists(file_path):
            return send_file(file_path, mimetype='audio/mpeg')
        else:
            return jsonify({"error": "File not found"}), 404
    except Exception as e:
        logger.error(f"Error serving audio: {e}")
        return jsonify({"error": str(e)}), 500

def save_conversation(user_id, user_text, response_text):
    """Save conversation to file (optional)"""
    try:
        log_dir = "/share/chatbot_logs"
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = f"{log_dir}/{user_id}.jsonl"
        with open(log_file, 'a', encoding='utf-8') as f:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "user": user_text,
                "assistant": response_text
            }
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception as e:
        logger.error(f"Error saving conversation: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('LISTENING_PORT', 5000))
    logger.info(f"Starting Flask server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
