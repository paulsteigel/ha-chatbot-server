#!/usr/bin/env python3
import os
import logging
import tempfile
import secrets
import wave
import time
from datetime import datetime, timedelta
from flask import Flask, request, make_response, jsonify, send_from_directory
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

# Context management settings
CONTEXT_ENABLED = os.getenv("CONTEXT_ENABLED", "true").lower() == "true"
CONTEXT_MAX_MESSAGES = int(os.getenv("CONTEXT_MAX_MESSAGES", "20"))
CONTEXT_TIMEOUT_MINUTES = int(os.getenv("CONTEXT_TIMEOUT_MINUTES", "30"))

# ✅ THÊM DÒNG NÀY - Audio storage directory
TEMP_AUDIO_DIR = os.getenv("TEMP_AUDIO_DIR", "/tmp/audio")
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

logger.info(f"Starting Yên Hoà ChatBot Server")
logger.info(f"Model: {OPENAI_MODEL}")
logger.info(f"Voice: {OPENAI_VOICE}")
logger.info(f"Language: {OPENAI_LANGUAGE}")
logger.info(f"Context Enabled: {CONTEXT_ENABLED}")
logger.info(f"Max Context Messages: {CONTEXT_MAX_MESSAGES}")
logger.info(f"Audio Directory: {TEMP_AUDIO_DIR}")
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

# In-memory conversation storage
conversations = {}

# ============================================================
# ConversationManager class
# ============================================================
class ConversationManager:
    """Quản lý context cho mỗi session"""
    
    @staticmethod
    def get_or_create_session(session_id=None):
        """Lấy hoặc tạo session ID mới"""
        if session_id and session_id in conversations:
            conversations[session_id]['last_activity'] = datetime.now()
            return session_id
        
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
        
        messages = conversations[session_id]['messages']
        if len(messages) > CONTEXT_MAX_MESSAGES + 1:
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
        """Xóa các session không hoạt động"""
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

# ============================================================
# Helper Functions
# ============================================================

def detect_language(text):
    """Simple language detection based on character set"""
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

# ============================================================
# ESP32 VOICE CHAT ENDPOINT
# ============================================================

@app.route('/api/voice-chat', methods=['POST'])
def voice_chat():
    """
    Xử lý voice chat từ ESP32
    Input: Raw audio data (8kHz, 16-bit, mono)
    Output: JSON với URL của file MP3 response
    """
    if not client:
        return jsonify({'error': 'OpenAI API key not configured'}), 500
    
    try:
        # 1. Lấy audio data từ request
        audio_data = request.data
        user_id = request.headers.get('X-User-ID', 'unknown')
        sample_rate = int(request.headers.get('X-Sample-Rate', '8000'))
        channels = int(request.headers.get('X-Channels', '1'))
        
        logger.info(f"📥 Received audio: {len(audio_data)} bytes from {user_id}")
        logger.info(f"   Sample rate: {sample_rate}Hz, Channels: {channels}")
        
        # 2. Lưu audio tạm để gửi OpenAI (cần WAV header)
        session_id = f"{user_id}_{int(time.time())}"
        input_filename = f"input_{session_id}.wav"
        input_path = os.path.join(TEMP_AUDIO_DIR, input_filename)
        
        # Tạo WAV header
        with wave.open(input_path, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)  # 16-bit = 2 bytes
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
        
        logger.info(f"💾 Saved input: {input_path}")
        
        # 3. Gửi lên OpenAI Whisper để transcribe
        logger.info("🎤 Transcribing...")
        with open(input_path, 'rb') as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="vi"  # Tiếng Việt
            )
        
        transcription_text = transcription.text
        logger.info(f"📝 Transcription: {transcription_text}")
        
        # 4. Gửi lên ChatGPT để có response text
        logger.info("💬 Getting response...")
        chat_response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Bạn là trợ lý AI thân thiện, trả lời ngắn gọn bằng tiếng Việt."},
                {"role": "user", "content": transcription_text}
            ],
            max_tokens=150
        )
        
        response_text = chat_response.choices[0].message.content
        logger.info(f"💭 Response: {response_text}")
        
        # 5. Chuyển response text thành MP3 (TTS)
        logger.info("🔊 Generating speech...")
        speech_response = client.audio.speech.create(
            model="tts-1",
            voice=OPENAI_VOICE,
            input=response_text,
            response_format="mp3"
        )
        
        # 6. Lưu MP3 response
        mp3_filename = f"response_{session_id}.mp3"
        mp3_path = os.path.join(TEMP_AUDIO_DIR, mp3_filename)
        
        with open(mp3_path, 'wb') as mp3_file:
            mp3_file.write(speech_response.content)
        
        logger.info(f"💾 Saved MP3: {mp3_path} ({len(speech_response.content)} bytes)")
        
        # 7. Tạo URL public cho MP3
        audio_url = f"{request.url_root}audio/{mp3_filename}"
        
        logger.info(f"✅ Done! Audio URL: {audio_url}")
        
        # 8. Cleanup input file
        try:
            os.unlink(input_path)
        except:
            pass
        
        # 9. Trả về JSON response
        return jsonify({
            'success': True,
            'audio_url': audio_url,
            'transcription': transcription_text,
            'response_text': response_text,
            'session_id': session_id,
            'audio_size': len(speech_response.content)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error in voice_chat: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/audio/<filename>')
def serve_audio(filename):
    """Serve audio files từ thư mục tạm"""
    try:
        return send_from_directory(
            TEMP_AUDIO_DIR, 
            filename, 
            mimetype='audio/mpeg',
            as_attachment=False
        )
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404


@app.route('/api/cleanup')
def cleanup_old_files():
    """Xóa các file audio cũ hơn 1 giờ"""
    try:
        current_time = time.time()
        deleted = 0
        
        for filename in os.listdir(TEMP_AUDIO_DIR):
            filepath = os.path.join(TEMP_AUDIO_DIR, filename)
            
            # Xóa file cũ hơn 3600 giây (1 giờ)
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > 3600:
                    os.remove(filepath)
                    deleted += 1
        
        return jsonify({
            'success': True,
            'deleted_files': deleted
        })
        
    except Exception as e:
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
        'active_sessions': len(conversations),
        'audio_directory': TEMP_AUDIO_DIR
    })

if __name__ == '__main__':
    logger.info("🚀 Starting Voice Chat Server...")
    logger.info(f"📁 Audio directory: {TEMP_AUDIO_DIR}")
    
    app.run(host='0.0.0.0', port=PORT, debug=(LOG_LEVEL == 'DEBUG'))
