#!/usr/bin/env python3
import os
import logging
import tempfile
import time
from datetime import datetime
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, make_response, jsonify, send_from_directory, Response
from flask_cors import CORS
from openai import OpenAI
from pathlib import Path
import gzip
import io
import wave
import struct
import json
from utils.content_filter import is_safe_content
from utils.response_templates import get_response_template # Đảm bảo có import này

SERVER_URL = os.getenv('SERVER_URL', 'https://school.sfdp.net')

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

# ✅ NEW: Custom command
BOT_LANGUAGE = os.getenv("BOT_LANGUAGE", "auto").lower()
CUSTOM_PROMPT_ADDITIONS = os.getenv("CUSTOM_PROMPT_ADDITIONS", "")

logger.info(f"Starting Yên Hoà ChatBot Server")
logger.info(f"Model: {OPENAI_MODEL}")
logger.info(f"Voice: {OPENAI_VOICE}")
logger.info(f"Language: {OPENAI_LANGUAGE}")
logger.info(f"Context Enabled: {CONTEXT_ENABLED}")
logger.info(f"Max Context Messages: {CONTEXT_MAX_MESSAGES}")
logger.info(f"Port: {PORT}")

logger.info(f"Default Language: {BOT_LANGUAGE}")
logger.info(f"Voice: {OPENAI_VOICE}")

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
        
        # Lấy template gốc
        system_prompt_template = get_response_template('system', BOT_LANGUAGE)
        
        # Chèn chỉ thị tùy chỉnh vào
        final_system_prompt = system_prompt_template.replace("{{CUSTOM_INSTRUCTIONS}}", CUSTOM_PROMPT_ADDITIONS)
        
        conversations[new_session_id] = {
            'messages': [
                {
                    "role": "system",
                    "content": final_system_prompt # Sử dụng prompt cuối cùng
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

def transcribe_audio(audio_data):
    """
    Transcribe audio using OpenAI Whisper API
    
    Args:
        audio_data: Raw audio bytes (WAV format)
    
    Returns:
        str: Transcribed text
    """
    try:
        logger.info("🎤 Transcribing audio with Whisper...")
        
        # Create a file-like object from bytes
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.wav"
        lang_param = BOT_LANGUAGE if BOT_LANGUAGE != 'auto' else None
        
        # Call Whisper API
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=lang_param # Sử dụng biến mớ
        )
        
        text = transcript.text.strip()
        logger.info(f"✓ Transcription: {text}")
        
        return text
        
    except Exception as e:
        logger.error(f"❌ Transcription error: {str(e)}")
        raise


def get_chat_response(user_message, session_id='default'):
    """
    Get AI response using OpenAI with conversation context
    
    Args:
        user_message: User's transcribed text
        session_id: Session identifier for conversation history
    
    Returns:
        str: AI response text
    """
    try:
        logger.info(f"🤖 Getting AI response for: {user_message}")
        
        # Detect language
        detected_lang = detect_language(user_message)
        
        # Content filtering
        if not is_safe_content(user_message):
            return get_response_template('inappropriate', detected_lang)
        
        # Get or create session with context
        if CONTEXT_ENABLED:
            session_id = ConversationManager.get_or_create_session(session_id)
            ConversationManager.add_message(session_id, "user", user_message)
            messages = ConversationManager.get_messages(session_id)
        else:
            system_prompt_template = get_response_template('system', BOT_LANGUAGE)
            final_system_prompt = system_prompt_template.replace("{{CUSTOM_INSTRUCTIONS}}", CUSTOM_PROMPT_ADDITIONS)
            messages = [
                {"role": "system", "content": final_system_prompt},
                {"role": "user", "content": user_message}
            ]        
        # Call OpenAI API
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE
        )
        
        assistant_message = response.choices[0].message.content
        
        # Add to context
        if CONTEXT_ENABLED:
            ConversationManager.add_message(session_id, "assistant", assistant_message)
        
        logger.info(f"✓ AI Response: {assistant_message}")
        
        return assistant_message
        
    except Exception as e:
        logger.error(f"❌ AI error: {str(e)}")
        raise


def old_text_to_speech(text):
    """
    Convert text to speech using OpenAI TTS
    
    Args:
        text: Text to convert
    
    Returns:
        bytes: Audio data (MP3 format)
    """
    try:
        logger.info(f"🔊 Converting to speech: {text[:50]}...")
        
        # Call OpenAI TTS API
        response = client.audio.speech.create(
            model="tts-1",
            voice=OPENAI_VOICE,
            input=text,
            speed=1.0
        )
        
        # Get audio bytes
        audio_bytes = response.content
        
        logger.info(f"✓ Generated {len(audio_bytes)} bytes of audio")
        
        return audio_bytes
        
    except Exception as e:
        logger.error(f"❌ TTS error: {str(e)}")
        raise
        
def text_to_speech(text, format='mp3'):
    """
    Convert text to speech using OpenAI TTS
    
    Args:
        text: Text to convert
        format: 'mp3' for web playback, 'wav' for ESP32
    
    Returns:
        bytes: Audio data in requested format
    """
    try:
        logger.info(f"🔊 Converting to speech ({format}): {text[:50]}...")
        
        if format == 'wav':
            # PCM format for ESP32
            response = client.audio.speech.create(
                model="tts-1",
                voice=OPENAI_VOICE,
                input=text,
                response_format="pcm"
            )
            
            pcm_data = response.content
            logger.info(f"✓ Received {len(pcm_data)} bytes of PCM audio")
            
            # Downsample from 24kHz to 16kHz
            pcm_16bit = struct.unpack(f'<{len(pcm_data)//2}h', pcm_data)
            
            resampled = []
            position = 0.0
            step = 24000 / 16000  # 1.5
            
            while int(position) < len(pcm_16bit):
                resampled.append(pcm_16bit[int(position)])
                position += step
            
            resampled_pcm = struct.pack(f'<{len(resampled)}h', *resampled)
            logger.info(f"✓ Resampled to {len(resampled_pcm)} bytes at 16kHz")
            
            # Create WAV header
            wav_header = create_wav_header(len(resampled_pcm), 16000, 1, 16)
            wav_file = wav_header + resampled_pcm
            
            logger.info(f"✓ Generated {len(wav_file)} bytes of WAV audio")
            return wav_file
            
        else:
            # MP3 format for web interface
            response = client.audio.speech.create(
                model="tts-1",
                voice=OPENAI_VOICE,
                input=text,
                response_format="mp3"
            )
            
            audio_bytes = response.content
            logger.info(f"✓ Generated {len(audio_bytes)} bytes of MP3 audio")
            
            return audio_bytes
        
    except Exception as e:
        logger.error(f"❌ TTS error: {str(e)}")
        raise

def create_wav_header(data_size, sample_rate=16000, channels=1, bits_per_sample=16):
    """
    Create a WAV file header
    
    Args:
        data_size: Size of PCM data in bytes
        sample_rate: Sample rate (Hz)
        channels: Number of channels (1=mono, 2=stereo)
        bits_per_sample: Bits per sample (8, 16, 24, 32)
    
    Returns:
        bytes: WAV header (44 bytes)
    """
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        data_size + 36,  # File size - 8
        b'WAVE',
        b'fmt ',
        16,  # fmt chunk size
        1,   # PCM format
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b'data',
        data_size
    )
    
    return header


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
        #response = client.audio.speech.create(
        #    model="tts-1",
        #    voice=voice,
        #    input=text
        #)
        speech_response = client.audio.speech.create(
            model="tts-1",
            voice=OPENAI_VOICE,
            input=text,
            response_format="mp3"
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
    """Handle voice chat with command recognition"""
    try:
        start_time = time.time()
        session_id = request.headers.get('X-Session-ID')
        
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_data = request.files['audio'].read()
        logger.info(f"📥 Received {len(audio_data)} bytes of audio.")

        # 1. Transcribe audio
        transcribed_text = transcribe_audio(audio_data)
        logger.info(f"📝 Transcribed: {transcribed_text}")

        # 2. Get raw response from AI
        raw_ai_response = get_chat_response(transcribed_text, session_id)
        logger.info(f"🤖 Raw AI Response: {raw_ai_response}")

        # 3. Prepare response headers and parse for commands
        response_headers = {
            'Content-Type': 'audio/wav',
            'X-Transcription': transcribed_text.encode('utf-8').decode('latin-1'),
            'X-Response-Text': raw_ai_response.encode('utf-8').decode('latin-1'),
            'X-Session-ID': session_id
        }
        
        text_for_tts = raw_ai_response

        # Check if the response is a command
        if raw_ai_response.strip().startswith('{'):
            try:
                command_data = json.loads(raw_ai_response)
                command = command_data.get("command")
                value = command_data.get("value")

                if command and value:
                    logger.info(f"✅ Parsed command: {command}, value: {value}")
                    response_headers['X-Device-Command'] = command
                    response_headers['X-Device-Value'] = str(value)
                    
                    # Create confirmation message for TTS
                    lang = BOT_LANGUAGE
                    if command == "set_volume":
                        text_for_tts = "Đã điều chỉnh âm lượng" if lang == 'vi' else "Volume adjusted"
                    elif command == "set_mic_gain":
                        text_for_tts = "Đã chỉnh độ nhạy mic" if lang == 'vi' else "Mic sensitivity adjusted"
                    elif command == "stop_conversation":
                        text_for_tts = "Tạm biệt" if lang == 'vi' else "Goodbye"
            except json.JSONDecodeError:
                logger.warning("Response looked like JSON but was not valid.")
                pass # Treat as a normal response

        # 4. Generate audio for the final text
        audio_response = text_to_speech(text_for_tts, format='wav')
        logger.info(f"🔊 Generated {len(audio_response)} bytes for TTS: '{text_for_tts}'")
        
        # 5. Send response with audio and headers
        return Response(
            audio_response,
            mimetype='audio/wav',
            headers=response_headers
        )

    except Exception as e:
        logger.error(f"❌ Error in voice_chat: {str(e)}", exc_info=True)
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

@app.route('/debug/audio/<filename>')
def serve_debug_audio(filename):
    """
    Serve debug audio files for quality checking
    
    Usage: https://school.sfdp.net/debug/audio/upload_default_20251030_220950.wav
    """
    try:
        debug_dir = os.path.abspath("debug_audio")
        
        # Security check - prevent directory traversal
        if '..' in filename or '/' in filename:
            return jsonify({'error': 'Invalid filename'}), 400
        
        file_path = os.path.join(debug_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        return send_from_directory(debug_dir, filename)
        
    except Exception as e:
        logger.error(f"Error serving debug audio: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/debug/audio')
def list_debug_audio():
    """
    List all debug audio files with playable links
    
    Usage: https://school.sfdp.net/debug/audio
    """
    try:
        debug_dir = "debug_audio"
        
        if not os.path.exists(debug_dir):
            return jsonify({
                'message': 'No debug files yet',
                'files': []
            })
        
        files = []
        for filename in sorted(os.listdir(debug_dir), reverse=True):
            if filename.endswith('.wav') or filename.endswith('.mp3'):
                file_path = os.path.join(debug_dir, filename)
                stat = os.stat(file_path)
                
                files.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'url': f"{SERVER_URL}/debug/audio/{filename}"
                })
        
        # Generate HTML player page
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Debug Audio Files</title>
            <style>
                body { font-family: Arial; margin: 20px; background: #f0f0f0; }
                .file { 
                    background: white; 
                    padding: 15px; 
                    margin: 10px 0; 
                    border-radius: 5px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }
                .file h3 { margin: 0 0 10px 0; color: #333; }
                .file .info { color: #666; font-size: 14px; margin: 5px 0; }
                audio { width: 100%; margin: 10px 0; }
                .no-files { text-align: center; color: #999; padding: 50px; }
            </style>
        </head>
        <body>
            <h1>🎧 Debug Audio Files</h1>
            <p>Total files: """ + str(len(files)) + """</p>
        """
        
        if files:
            for file in files:
                html += f"""
                <div class="file">
                    <h3>{file['filename']}</h3>
                    <div class="info">Size: {file['size']:,} bytes</div>
                    <div class="info">Created: {file['created']}</div>
                    <audio controls preload="metadata">
                        <source src="{file['url']}" type="audio/wav">
                        Your browser does not support audio playback.
                    </audio>
                    <a href="{file['url']}" download>⬇️ Download</a>
                </div>
                """
        else:
            html += '<div class="no-files">No audio files yet. Make a recording first!</div>'
        
        html += """
        </body>
        </html>
        """
        
        return html
        
    except Exception as e:
        logger.error(f"Error listing debug audio: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=(LOG_LEVEL == 'DEBUG'))
