#!/usr/bin/env python3
import os
import logging
import tempfile
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
from pathlib import Path

# Set up logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
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
OPENAI_LANGUAGE = os.getenv("OPENAI_LANGUAGE", "auto")
PORT = int(os.getenv("PORT", "5000"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "500"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))

# ✅ NEW: Context management settings
CONTEXT_ENABLED = os.getenv("CONTEXT_ENABLED", "true").lower() == "true"
CONTEXT_MAX_MESSAGES = int(os.getenv("CONTEXT_MAX_MESSAGES", "20"))
CONTEXT_TIMEOUT_MINUTES = int(os.getenv("CONTEXT_TIMEOUT_MINUTES", "30"))

logger.info(f"Starting Yên Hoà ChatBot Server")
logger.info(f"Model: {OPENAI_MODEL}")
logger.info(f"Voice: {OPENAI_VOICE}")
logger.info(f"Language: {OPENAI_LANGUAGE}")
logger.info(f"Context Enabled: {CONTEXT_ENABLED}")
logger.info(f"Max Context Messages: {CONTEXT_MAX_MESSAGES}")
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

# ✅ NEW: In-memory conversation storage
conversations = {}

class ConversationManager:
    """Quản lý context cho mỗi session"""
    
    @staticmethod
    def get_or_create_session(session_id=None):
        """Lấy hoặc tạo session ID mới"""
        if session_id and session_id in conversations:
            # Update last activity
            conversations[session_id]['last_activity'] = datetime.now()
            return session_id
        
        # Tạo session mới
        new_session_id = session_id or secrets.token_hex(16)
        conversations[new_session_id] = {
            'messages': [
                {
                    "role": "system",
                    "content": get_response_template('system', 'auto')
                }
            ],
            'created_at': datetime.now(),
            'last_activity': datetime.now()
        }
        logger.info(f"✅ Created new session: {new_session_id}")
        return new_session_id
    
    @staticmethod
    def add_message(session_id, role, content):
        """Thêm tin nhắn vào lịch sử"""
        if session_id not in conversations:
            ConversationManager.get_or_create_session(session_id)
        
        conversations[session_id]['messages'].append({
            "role": role,
            "content": content
        })
        conversations[session_id]['last_activity'] = datetime.now()
        
        # Giới hạn số lượng tin nhắn (giữ system prompt + N tin nhắn gần nhất)
        messages = conversations[session_id]['messages']
        if len(messages) > CONTEXT_MAX_MESSAGES + 1:  # +1 cho system prompt
            # Giữ system prompt + tin nhắn gần nhất
            conversations[session_id]['messages'] = [messages[0]] + messages[-(CONTEXT_MAX_MESSAGES):]
            logger.info(f"🔄 Trimmed context for session {session_id}")
    
    @staticmethod
    def get_messages(session_id):
        """Lấy toàn bộ lịch sử tin nhắn"""
        if session_id not in conversations:
            ConversationManager.get_or_create_session(session_id)
        return conversations[session_id]['messages']
    
    @staticmethod
    def clear_session(session_id):
        """Xóa session"""
        if session_id in conversations:
            del conversations[session_id]
            logger.info(f"🗑️ Cleared session: {session_id}")
            return True
        return False
    
    @staticmethod
    def cleanup_old_sessions():
        """Xóa các session không hoạt động (chạy định kỳ)"""
        now = datetime.now()
        timeout = timedelta(minutes=CONTEXT_TIMEOUT_MINUTES)
        
        expired_sessions = [
            sid for sid, data in conversations.items()
            if now - data['last_activity'] > timeout
        ]
        
        for sid in expired_sessions:
            del conversations[sid]
            logger.info(f"⏰ Auto-deleted expired session: {sid}")
        
        return len(expired_sessions)

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
    """Handle chat requests WITH CONTEXT"""
    if not client:
        return jsonify({
            'error': 'OpenAI API key not configured'
        }), 500
    
    try:
        data = request.json
        user_message = data.get('message', '')
        session_id = data.get('session_id') or request.headers.get('X-Session-ID')
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        # ✅ Cleanup old sessions
        ConversationManager.cleanup_old_sessions()
        
        # ✅ Get or create session
        if CONTEXT_ENABLED:
            session_id = ConversationManager.get_or_create_session(session_id)
        else:
            # No context mode - always create new session
            session_id = ConversationManager.get_or_create_session()
        
        # Detect user's language
        detected_lang = detect_language(user_message)
        logger.info(f"Detected language: {detected_lang} for message: {user_message[:50]}")
        
        # Content filtering
        if not is_safe_content(user_message):
            response_text = get_response_template('inappropriate', detected_lang)
            if CONTEXT_ENABLED:
                ConversationManager.add_message(session_id, "user", user_message)
                ConversationManager.add_message(session_id, "assistant", response_text)
            return jsonify({
                'response': response_text,
                'session_id': session_id
            })
        
        # ✅ Add user message to context
        if CONTEXT_ENABLED:
            ConversationManager.add_message(session_id, "user", user_message)
        
        # ✅ Get full conversation history
        messages = ConversationManager.get_messages(session_id) if CONTEXT_ENABLED else [
            {"role": "system", "content": get_response_template('system', 'auto')},
            {"role": "user", "content": user_message}
        ]
        
        logger.info(f"📝 Sending {len(messages)} messages to OpenAI (session: {session_id})")
        
        # Create chat completion with context
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE
        )
        
        assistant_message = response.choices[0].message.content
        
        # ✅ Add assistant response to context
        if CONTEXT_ENABLED:
            ConversationManager.add_message(session_id, "assistant", assistant_message)
        
        return jsonify({
            'response': assistant_message,
            'model': OPENAI_MODEL,
            'detected_language': detected_lang,
            'session_id': session_id,
            'context_length': len(ConversationManager.get_messages(session_id)) if CONTEXT_ENABLED else 0
        })
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/api/context/clear', methods=['POST'])
def clear_context():
    """Clear conversation context for a session"""
    try:
        data = request.json or {}
        session_id = data.get('session_id') or request.headers.get('X-Session-ID')
        
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        
        if ConversationManager.clear_session(session_id):
            return jsonify({
                'message': 'Context cleared',
                'session_id': session_id
            })
        else:
            return jsonify({
                'message': 'Session not found',
                'session_id': session_id
            }), 404
    
    except Exception as e:
        logger.error(f"Error in clear_context: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/context/view', methods=['GET'])
def view_context():
    """View conversation context (for debugging)"""
    try:
        session_id = request.args.get('session_id') or request.headers.get('X-Session-ID')
        
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        
        if session_id not in conversations:
            return jsonify({
                'message': 'Session not found',
                'session_id': session_id
            }), 404
        
        messages = ConversationManager.get_messages(session_id)
        
        return jsonify({
            'session_id': session_id,
            'message_count': len(messages),
            'messages': messages,
            'created_at': conversations[session_id]['created_at'].isoformat(),
            'last_activity': conversations[session_id]['last_activity'].isoformat()
        })
    
    except Exception as e:
        logger.error(f"Error in view_context: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/context/stats', methods=['GET'])
def context_stats():
    """Get statistics about active sessions"""
    try:
        return jsonify({
            'active_sessions': len(conversations),
            'context_enabled': CONTEXT_ENABLED,
            'max_messages': CONTEXT_MAX_MESSAGES,
            'timeout_minutes': CONTEXT_TIMEOUT_MINUTES,
            'sessions': {
                sid: {
                    'message_count': len(data['messages']),
                    'created_at': data['created_at'].isoformat(),
                    'last_activity': data['last_activity'].isoformat()
                }
                for sid, data in conversations.items()
            }
        })
    
    except Exception as e:
        logger.error(f"Error in context_stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

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

@app.route('/api/voice-chat', methods=['POST'])
def voice_chat():
    """Handle voice chat - receive audio, return audio"""
    if not client:
        return jsonify({'error': 'OpenAI API key not configured'}), 500
    
    try:
        # Get session ID
        session_id = request.headers.get('X-Session-ID') or request.headers.get('X-User-ID')
        
        # Get audio data
        audio_data = request.data
        
        if len(audio_data) == 0:
            return jsonify({'error': 'No audio data'}), 400
        
        logger.info(f"📥 Received {len(audio_data)} bytes of audio")
        
        # Save to temp file for Whisper
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
            temp_audio.write(audio_data)
            temp_path = temp_audio.name
        
        try:
            # 1. Transcribe audio
            logger.info("🎤 Transcribing audio...")
            with open(temp_path, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )
            
            user_message = transcript.text
            logger.info(f"📝 Transcribed: {user_message}")
            
            if not user_message:
                return jsonify({'error': 'Could not transcribe audio'}), 400
            
            # 2. Get or create session
            if CONTEXT_ENABLED:
                session_id = ConversationManager.get_or_create_session(session_id)
                ConversationManager.add_message(session_id, "user", user_message)
                messages = ConversationManager.get_messages(session_id)
            else:
                messages = [
                    {"role": "system", "content": get_response_template('system', 'auto')},
                    {"role": "user", "content": user_message}
                ]
            
            # 3. Get ChatGPT response
            logger.info("🤖 Getting ChatGPT response...")
            chat_response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE
            )
            
            assistant_message = chat_response.choices[0].message.content
            logger.info(f"💬 Response: {assistant_message}")
            
            if CONTEXT_ENABLED:
                ConversationManager.add_message(session_id, "assistant", assistant_message)
            
            # 4. Convert response to speech
            logger.info("🔊 Converting to speech...")
            speech_response = client.audio.speech.create(
                model="tts-1",
                voice=OPENAI_VOICE,
                input=assistant_message
            )
            
            # Save speech to temp file
            speech_path = Path("/tmp/speech_response.mp3")
            speech_response.stream_to_file(speech_path)
            
            # Read audio file
            with open(speech_path, 'rb') as audio_file:
                audio_bytes = audio_file.read()
            
            logger.info(f"✅ Returning {len(audio_bytes)} bytes of audio")
            
            # Return audio with metadata in headers
            response = make_response(audio_bytes)
            response.headers['Content-Type'] = 'audio/mpeg'
            response.headers['X-Transcription'] = user_message
            response.headers['X-Response-Text'] = assistant_message
            response.headers['X-Session-ID'] = session_id
            
            return response
            
        finally:
            # Cleanup temp files
            os.unlink(temp_path)
            if os.path.exists(speech_path):
                os.unlink(speech_path)
    
    except Exception as e:
        logger.error(f"Error in voice_chat: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'model': OPENAI_MODEL,
        'voice': OPENAI_VOICE,
        'language': OPENAI_LANGUAGE,
        'api_key_configured': bool(OPENAI_API_KEY),
        'context_enabled': CONTEXT_ENABLED,
        'active_sessions': len(conversations)
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=(LOG_LEVEL == 'DEBUG'))
