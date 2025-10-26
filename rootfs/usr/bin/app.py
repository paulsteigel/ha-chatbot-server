#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kids ChatBot Server for Home Assistant
Compatible with OpenAI 0.28.1
"""

import os
import json
import logging
import tempfile
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import openai

# ==================== CONFIGURATION ====================
# Load config from run.sh
CONFIG_FILE = '/tmp/addon_config.json'

def load_config():
    """Load configuration from file"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

config = load_config()

# OpenAI Configuration
OPENAI_API_KEY = config.get('openai_api_key', os.getenv('OPENAI_API_KEY', ''))
openai.api_key = OPENAI_API_KEY

# Server Configuration
LISTENING_PORT = config.get('listening_port', 5000)
LANGUAGE = config.get('language', 'vi')
LOG_LEVEL = config.get('log_level', 'info').upper()

# Features Configuration
MAX_AUDIO_SIZE = config.get('max_audio_size_mb', 25) * 1024 * 1024  # Convert to bytes
ENABLE_CONTENT_FILTER = config.get('enable_content_filter', True)
BAD_WORDS_LIST = config.get('bad_words_list', [])
RESPONSE_VOICE = config.get('response_voice', 'nova')
BOT_PERSONALITY = config.get('bot_personality', 'gentle_teacher')
EDUCATIONAL_MODE = config.get('educational_mode', True)
POLITENESS_REMINDERS = config.get('politeness_reminders', True)
SAVE_CONVERSATIONS = config.get('save_conversations', False)

# Temp directories
TEMP_DIR = '/tmp/chatbot_audio'
LOG_DIR = '/share/chatbot_logs'
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ==================== LOGGING ====================
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'{LOG_DIR}/chatbot.log')
    ]
)
logger = logging.getLogger(__name__)

# ==================== FLASK APP ====================
app = Flask(__name__)
CORS(app)

logger.info("✓ OpenAI API Key configured")
logger.info(f"✓ Server configured on port {LISTENING_PORT}")

# ==================== PERSONALITY PROMPTS ====================
PERSONALITY_PROMPTS = {
    'vi': {
        'gentle_teacher': """Bạn là một giáo viên thân thiện và kiên nhẫn dành cho trẻ em. 
        Hãy trả lời bằng tiếng Việt, sử dụng ngôn ngữ đơn giản, dễ hiểu.
        Luôn động viên, khuyến khích học hỏi và tò mò.
        Giải thích mọi thứ một cách vui vẻ, có thể dùng ví dụ sinh động.""",
        
        'friendly_companion': """Bạn là một người bạn thân thiện của trẻ em.
        Hãy trò chuyện vui vẻ, hỏi han và chia sẻ bằng tiếng Việt.
        Sử dụng ngôn ngữ gần gũi, dễ hiểu, có thể dùng emoji phù hợp.
        Luôn lắng nghe và thể hiện sự quan tâm.""",
        
        'strict_teacher': """Bạn là một giáo viên nghiêm khắc nhưng công bằng.
        Trả lời bằng tiếng Việt, rõ ràng và chính xác.
        Nhắc nhở về quy tắc, kỷ luật và học tập đúng cách.
        Luôn giải thích tại sao điều gì đó quan trọng."""
    },
    'en': {
        'gentle_teacher': """You are a friendly and patient teacher for children.
        Answer in English, use simple and understandable language.
        Always encourage learning and curiosity.
        Explain things in a fun way with vivid examples.""",
        
        'friendly_companion': """You are a friendly companion for children.
        Chat cheerfully, ask questions and share in English.
        Use approachable language, you can use appropriate emojis.
        Always listen and show care.""",
        
        'strict_teacher': """You are a strict but fair teacher.
        Answer in English, clearly and accurately.
        Remind about rules, discipline and proper learning.
        Always explain why something is important."""
    }
}

# ==================== CONTENT FILTER ====================
def contains_bad_words(text):
    """Check if text contains inappropriate words"""
    if not ENABLE_CONTENT_FILTER or not BAD_WORDS_LIST:
        return False
    
    text_lower = text.lower()
    for word in BAD_WORDS_LIST:
        if word.lower() in text_lower:
            logger.warning(f"Inappropriate word detected: {word}")
            return True
    return False

def get_content_filter_response():
    """Return appropriate response for filtered content"""
    if LANGUAGE == 'vi':
        return "Con ơi, chúng ta nên nói những điều lịch sự và tốt đẹp nhé. Bạn có câu hỏi khác không?"
    return "Let's use kind and polite words. Do you have another question?"

# ==================== OPENAI FUNCTIONS ====================
def transcribe_audio(audio_file_path):
    """Convert audio to text using Whisper"""
    try:
        with open(audio_file_path, 'rb') as audio_file:
            transcript = openai.Audio.transcribe(
                model="whisper-1",
                file=audio_file,
                language=LANGUAGE if LANGUAGE != 'zh' else 'zh-CN'
            )
        return transcript['text']
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise

def generate_response(user_message, conversation_history=None):
    """Generate AI response using GPT"""
    try:
        # Get personality prompt
        personality_key = BOT_PERSONALITY if BOT_PERSONALITY in PERSONALITY_PROMPTS[LANGUAGE] else 'gentle_teacher'
        system_prompt = PERSONALITY_PROMPTS[LANGUAGE][personality_key]
        
        # Add educational mode instructions
        if EDUCATIONAL_MODE:
            if LANGUAGE == 'vi':
                system_prompt += "\n\nLuôn giải thích thêm kiến thức liên quan để con học thêm được điều mới."
            else:
                system_prompt += "\n\nAlways provide additional related knowledge to help children learn something new."
        
        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        
        if conversation_history:
            messages.extend(conversation_history)
        
        messages.append({"role": "user", "content": user_message})
        
        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        answer = response['choices'][0]['message']['content']
        
        # Add politeness reminder if needed
        if POLITENESS_REMINDERS and LANGUAGE == 'vi':
            if not any(word in user_message.lower() for word in ['cảm ơn', 'xin', 'chào', 'ạ']):
                answer += "\n\n(Nhớ nói 'cảm ơn' và 'xin' nhé con!)"
        
        return answer
        
    except Exception as e:
        logger.error(f"Response generation error: {e}")
        raise

def text_to_speech(text, output_path):
    """Convert text to speech using OpenAI TTS"""
    try:
        response = openai.Audio.speech.create(
            model="tts-1",
            voice=RESPONSE_VOICE,
            input=text
        )
        
        # Write audio to file
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"✓ Audio file created: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise

# ==================== CONVERSATION STORAGE ====================
conversation_store = {}

def save_conversation(session_id, message, response):
    """Save conversation if enabled"""
    if not SAVE_CONVERSATIONS:
        return
    
    if session_id not in conversation_store:
        conversation_store[session_id] = []
    
    conversation_store[session_id].append({
        'timestamp': datetime.now().isoformat(),
        'user': message,
        'bot': response
    })
    
    # Keep only last 50 messages
    if len(conversation_store[session_id]) > 50:
        conversation_store[session_id] = conversation_store[session_id][-50:]

# ==================== API ENDPOINTS ====================
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.3'
    }), 200

@app.route('/chat', methods=['POST'])
def chat():
    """Main chat endpoint - receives audio, returns audio response"""
    try:
        # Check if audio file exists
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        
        if audio_file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400
        
        # Check file size
        audio_file.seek(0, os.SEEK_END)
        file_size = audio_file.tell()
        audio_file.seek(0)
        
        if file_size > MAX_AUDIO_SIZE:
            return jsonify({'error': f'File too large. Max: {MAX_AUDIO_SIZE/1024/1024}MB'}), 413
        
        # Get session ID
        session_id = request.form.get('session_id', 'default')
        
        # Save uploaded audio
        temp_audio_path = os.path.join(TEMP_DIR, f"input_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav")
        audio_file.save(temp_audio_path)
        logger.info(f"✓ Audio saved: {temp_audio_path}")
        
        # Step 1: Transcribe audio to text
        logger.info("🎤 Transcribing audio...")
        user_message = transcribe_audio(temp_audio_path)
        logger.info(f"📝 Transcribed: {user_message}")
        
        # Step 2: Content filter
        if contains_bad_words(user_message):
            response_text = get_content_filter_response()
            logger.warning("⚠️ Inappropriate content filtered")
        else:
            # Step 3: Generate AI response
            logger.info("🤖 Generating response...")
            conversation_history = conversation_store.get(session_id, [])[-10:]  # Last 10 messages
            response_text = generate_response(user_message, conversation_history)
            logger.info(f"💬 Response: {response_text[:100]}...")
        
        # Step 4: Convert response to speech
        logger.info("🔊 Converting to speech...")
        output_audio_path = os.path.join(TEMP_DIR, f"output_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3")
        text_to_speech(response_text, output_audio_path)
        
        # Save conversation
        save_conversation(session_id, user_message, response_text)
        
        # Clean up input file
        try:
            os.remove(temp_audio_path)
        except:
            pass
        
        # Return audio file
        return send_file(
            output_audio_path,
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name='response.mp3'
        )
        
    except Exception as e:
        logger.error(f"❌ Chat endpoint error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/text-chat', methods=['POST'])
def text_chat():
    """Text-only chat endpoint"""
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({'error': 'No message provided'}), 400
        
        user_message = data['message']
        session_id = data.get('session_id', 'default')
        
        logger.info(f"📝 Text chat: {user_message}")
        
        # Content filter
        if contains_bad_words(user_message):
            response_text = get_content_filter_response()
        else:
            conversation_history = conversation_store.get(session_id, [])[-10:]
            response_text = generate_response(user_message, conversation_history)
        
        save_conversation(session_id, user_message, response_text)
        
        return jsonify({
            'response': response_text,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Text chat error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    return jsonify({
        'language': LANGUAGE,
        'voice': RESPONSE_VOICE,
        'personality': BOT_PERSONALITY,
        'educational_mode': EDUCATIONAL_MODE,
        'content_filter': ENABLE_CONTENT_FILTER,
        'politeness_reminders': POLITENESS_REMINDERS
    }), 200

# ==================== MAIN ====================
if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("🚀 Kids ChatBot Server Starting...")
    logger.info(f"   Port: {LISTENING_PORT}")
    logger.info(f"   Language: {LANGUAGE}")
    logger.info(f"   Voice: {RESPONSE_VOICE}")
    logger.info(f"   Personality: {BOT_PERSONALITY}")
    logger.info("=" * 50)
    
    app.run(
        host='0.0.0.0',
        port=LISTENING_PORT,
        debug=(LOG_LEVEL == 'DEBUG')
    )
