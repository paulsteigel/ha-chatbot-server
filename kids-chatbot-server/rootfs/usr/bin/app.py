#!/usr/bin/env python3
import os
import logging
import tempfile
import time
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, make_response, jsonify, send_from_directory, Response
from flask_cors import CORS
from openai import OpenAI
from pathlib import Path
import io
import struct
import json

# Import utilities
from utils.content_filter import is_safe_content
from utils.response_templates import get_response_template

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

# --- Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_VOICE = os.getenv("OPENAI_VOICE", "alloy")
PORT = int(os.getenv("PORT", "5000"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "500"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))

CONTEXT_ENABLED = os.getenv("CONTEXT_ENABLED", "true").lower() == "true"
CONTEXT_MAX_MESSAGES = int(os.getenv("CONTEXT_MAX_MESSAGES", "20"))
CONTEXT_TIMEOUT_MINUTES = int(os.getenv("CONTEXT_TIMEOUT_MINUTES", "30"))

BOT_LANGUAGE = os.getenv("BOT_LANGUAGE", "vi").lower()
CUSTOM_PROMPT_ADDITIONS = os.getenv("CUSTOM_PROMPT_ADDITIONS", "")

# Voice selection based on language
VOICE_MAP = {
    'vi': os.getenv("VOICE_VIETNAMESE", "alloy"),  # Nam cho tiếng Việt
    'en': os.getenv("VOICE_ENGLISH", "nova"),      # Nữ cho tiếng Anh
    'auto': OPENAI_VOICE
}

logger.info(f"Voice Map: VI={VOICE_MAP['vi']}, EN={VOICE_MAP['en']}")

logger.info(f"--- Yên Hoà ChatBot Server Starting ---")
logger.info(f"Model: {OPENAI_MODEL}")
logger.info(f"Voice: {OPENAI_VOICE}")
logger.info(f"Language: {BOT_LANGUAGE}")
logger.info(f"Context Enabled: {CONTEXT_ENABLED}")
logger.info(f"Port: {PORT}")
logger.info(f"------------------------------------")

# Validate and initialize OpenAI client
if not OPENAI_API_KEY:
    logger.error("CRITICAL: OPENAI_API_KEY is not set!")
    client = None
else:
    logger.info("OpenAI API key is configured")
    client = OpenAI(api_key=OPENAI_API_KEY)

# In-memory conversation storage
conversations = {}


class ConversationManager:
    """Quản lý context và preferences cho mỗi session"""
    
    @staticmethod
    def get_or_create_session(session_id=None, preferred_lang=None):
        """Lấy hoặc tạo session ID mới"""
        if session_id and session_id in conversations:
            conversations[session_id]['last_activity'] = datetime.now()
            # Cập nhật ngôn ngữ nếu có yêu cầu thay đổi
            if preferred_lang:
                conversations[session_id]['language'] = preferred_lang
            return session_id
        
        new_session_id = session_id or secrets.token_hex(16)
        lang = preferred_lang or BOT_LANGUAGE
        system_prompt_template = get_response_template('system', lang)
        final_system_prompt = system_prompt_template.replace("{{CUSTOM_INSTRUCTIONS}}", CUSTOM_PROMPT_ADDITIONS)
        
        conversations[new_session_id] = {
            'messages': [{"role": "system", "content": final_system_prompt}],
            'language': lang,  # Lưu ngôn ngữ hiện tại
            'created_at': datetime.now(),
            'last_activity': datetime.now()
        }
        logger.info(f"✅ Created new session: {new_session_id} (language: {lang})")
        return new_session_id
    
    @staticmethod
    def add_message(session_id, role, content):
        """Thêm tin nhắn vào lịch sử"""
        if session_id not in conversations:
            ConversationManager.get_or_create_session(session_id)
        
        conversations[session_id]['messages'].append({"role": role, "content": content})
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
    def get_language(session_id):
        """Lấy ngôn ngữ hiện tại của session"""
        if session_id in conversations:
            return conversations[session_id].get('language', BOT_LANGUAGE)
        return BOT_LANGUAGE
    
    @staticmethod
    def set_language(session_id, language):
        """Thay đổi ngôn ngữ của session và cập nhật system prompt"""
        if session_id in conversations:
            conversations[session_id]['language'] = language
            # Cập nhật system prompt với ngôn ngữ mới
            new_system_prompt = get_response_template('system', language)
            new_system_prompt = new_system_prompt.replace("{{CUSTOM_INSTRUCTIONS}}", CUSTOM_PROMPT_ADDITIONS)
            conversations[session_id]['messages'][0] = {"role": "system", "content": new_system_prompt}
            logger.info(f"🌐 Session {session_id} switched to language: {language}")
            return True
        return False
    
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

def detect_language_switch_intent(user_message):
    """
    Phát hiện ý định chuyển ngôn ngữ
    Returns: (target_language, is_switch_request)
    """
    message_lower = user_message.lower().strip()
    
    # Yêu cầu chuyển sang tiếng Anh
    en_triggers = [
        'speak english', 'talk in english', 'use english', 'switch to english',
        'answer in english', 'reply in english', 'say it in english',
        'hãy nói tiếng anh', 'nói tiếng anh', 'chuyển sang tiếng anh', 
        'dùng tiếng anh', 'trả lời bằng tiếng anh'
    ]
    
    # Yêu cầu chuyển sang tiếng Việt
    vi_triggers = [
        'speak vietnamese', 'talk in vietnamese', 'use vietnamese', 
        'switch to vietnamese', 'answer in vietnamese', 'reply in vietnamese',
        'hãy nói tiếng việt', 'nói tiếng việt', 'chuyển sang tiếng việt', 
        'dùng tiếng việt', 'trả lời bằng tiếng việt'
    ]
    
    for trigger in en_triggers:
        if trigger in message_lower:
            return ('en', True)
    
    for trigger in vi_triggers:
        if trigger in message_lower:
            return ('vi', True)
    
    return (None, False)


def transcribe_audio(audio_data):
    """Transcribe audio using OpenAI Whisper API"""
    try:
        logger.info("🎤 Transcribing audio with Whisper...")
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.wav"
        lang_param = BOT_LANGUAGE if BOT_LANGUAGE != 'auto' else None
        
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=lang_param
        )
        
        text = transcript.text.strip()
        logger.info(f"✓ Transcription: {text}")
        return text
        
    except Exception as e:
        logger.error(f"❌ Transcription error: {str(e)}")
        raise


def detect_language_switch_intent(user_message):
    """
    Phát hiện ý định chuyển ngôn ngữ
    Returns: ('vi'|'en'|None, bool)
    """
    message_lower = user_message.lower().strip()
    
    # Yêu cầu chuyển sang tiếng Anh
    en_triggers = [
        'speak english', 'talk in english', 'use english', 'switch to english',
        'hãy nói tiếng anh', 'nói tiếng anh', 'chuyển sang tiếng anh', 'dùng tiếng anh'
    ]
    
    # Yêu cầu chuyển sang tiếng Việt
    vi_triggers = [
        'speak vietnamese', 'talk in vietnamese', 'use vietnamese', 'switch to vietnamese',
        'hãy nói tiếng việt', 'nói tiếng việt', 'chuyển sang tiếng việt', 'dùng tiếng việt'
    ]
    
    for trigger in en_triggers:
        if trigger in message_lower:
            return ('en', True)
    
    for trigger in vi_triggers:
        if trigger in message_lower:
            return ('vi', True)
    
    return (None, False)


def get_chat_response(user_message, session_id='default'):
    """Get AI response with intelligent language handling and session management"""
    try:
        logger.info(f"🤖 Getting AI response for: {user_message}")
        
        # Content filtering
        detected_lang = detect_language(user_message)
        
        if not is_safe_content(user_message):
            return get_response_template('inappropriate', detected_lang)
        
        # Kiểm tra ý định chuyển ngôn ngữ
        (target_lang, is_lang_switch) = detect_language_switch_intent(user_message)
        
        if CONTEXT_ENABLED:
            # Tạo hoặc lấy session
            session_id = ConversationManager.get_or_create_session(session_id)
            current_lang = ConversationManager.get_language(session_id)
            
            # Nếu người dùng YÊU CẦU chuyển ngôn ngữ
            if is_lang_switch and target_lang:
                ConversationManager.set_language(session_id, target_lang)
                lang_name = "English" if target_lang == 'en' else "Tiếng Việt"
                confirmation = (
                    f"Okay! I'll speak {lang_name} from now on." 
                    if target_lang == 'en' 
                    else f"Được rồi! Mình sẽ nói {lang_name} từ bây giờ nhé."
                )
                ConversationManager.add_message(session_id, "user", user_message)
                ConversationManager.add_message(session_id, "assistant", confirmation)
                logger.info(f"🌐 Language switched to {target_lang} for session {session_id}")
                return confirmation
            
            # Tự động nhận diện ngôn ngữ input
            detected_input_lang = detect_language(user_message)
            
            # Chỉ cập nhật language nếu input RÕ RÀNG là ngôn ngữ khác (không phải 'auto')
            if detected_input_lang != 'auto' and detected_input_lang != current_lang:
                logger.info(f"🌐 Auto-switching language from {current_lang} to {detected_input_lang}")
                ConversationManager.set_language(session_id, detected_input_lang)
            
            # Thêm tin nhắn của user vào context
            ConversationManager.add_message(session_id, "user", user_message)
            messages = ConversationManager.get_messages(session_id)
            
        else:
            # Không có context - xử lý đơn giản
            session_id = ConversationManager.get_or_create_session()
            system_prompt_template = get_response_template('system', detected_lang if detected_lang != 'auto' else BOT_LANGUAGE)
            final_system_prompt = system_prompt_template.replace("{{CUSTOM_INSTRUCTIONS}}", CUSTOM_PROMPT_ADDITIONS)
            messages = [
                {"role": "system", "content": final_system_prompt},
                {"role": "user", "content": user_message}
            ]
        
        # Gọi OpenAI API
        logger.info(f"📝 Sending {len(messages)} messages to OpenAI (session: {session_id})")
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE
        )
        
        assistant_message = response.choices[0].message.content
        
        # Lưu phản hồi vào context
        if CONTEXT_ENABLED:
            ConversationManager.add_message(session_id, "assistant", assistant_message)
        
        logger.info(f"✓ AI Response: {assistant_message}")
        return assistant_message
        
    except Exception as e:
        logger.error(f"❌ AI error: {str(e)}")
        raise

def text_to_speech(text, format='mp3', language='auto'):
    """
    Convert text to speech with automatic voice selection
    
    Args:
        text: Text to convert
        format: 'mp3' for web, 'wav' for ESP32
        language: 'vi', 'en', or 'auto' to auto-detect
    """
    try:
        # Tự động chọn voice dựa trên ngôn ngữ
        if language == 'auto':
            detected_lang = detect_language(text)
            voice = VOICE_MAP.get(detected_lang, OPENAI_VOICE)
        else:
            voice = VOICE_MAP.get(language, OPENAI_VOICE)
        
        logger.info(f"🔊 Converting to speech ({format}, voice={voice}, lang={language}): {text[:50]}...")
        
        if format == 'wav':
            response = client.audio.speech.create(
                model="tts-1",
                voice=voice,  # Dynamic voice selection
                input=text,
                response_format="pcm"
            )
            
            pcm_data = response.content
            logger.info(f"✓ Received {len(pcm_data)} bytes of PCM audio")
            
            # Downsample from 24kHz to 16kHz for ESP32
            pcm_16bit = struct.unpack(f'<{len(pcm_data)//2}h', pcm_data)
            resampled = []
            position = 0.0
            step = 24000 / 16000
            
            while int(position) < len(pcm_16bit):
                resampled.append(pcm_16bit[int(position)])
                position += step
            
            resampled_pcm = struct.pack(f'<{len(resampled)}h', *resampled)
            logger.info(f"✓ Resampled to {len(resampled_pcm)} bytes at 16kHz")
            
            wav_header = create_wav_header(len(resampled_pcm), 16000, 1, 16)
            wav_file = wav_header + resampled_pcm
            
            logger.info(f"✓ Generated {len(wav_file)} bytes of WAV audio (voice: {voice})")
            return wav_file
            
        else:  # MP3 format
            response = client.audio.speech.create(
                model="tts-1",
                voice=voice,  # Dynamic voice selection
                input=text,
                response_format="mp3"
            )
            
            audio_bytes = response.content
            logger.info(f"✓ Generated {len(audio_bytes)} bytes of MP3 audio (voice: {voice})")
            return audio_bytes
        
    except Exception as e:
        logger.error(f"❌ TTS error: {str(e)}")
        raise

def create_wav_header(data_size, sample_rate=16000, channels=1, bits_per_sample=16):
    """Create a WAV file header"""
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        data_size + 36,
        b'WAVE',
        b'fmt ',
        16,
        1,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b'data',
        data_size
    )
    return header


# --- API Endpoints ---

@app.route('/')
def index():
    """Serve the test interface"""
    return send_from_directory('/usr/bin/static', 'index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat requests WITH CONTEXT"""
    if not client:
        return jsonify({'error': 'OpenAI API key not configured'}), 500
    
    try:
        data = request.json
        user_message = data.get('message', '')
        session_id = data.get('session_id') or request.headers.get('X-Session-ID')
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        ConversationManager.cleanup_old_sessions()
        
        if CONTEXT_ENABLED:
            session_id = ConversationManager.get_or_create_session(session_id)
        else:
            session_id = ConversationManager.get_or_create_session()
        
        detected_lang = detect_language(user_message)
        logger.info(f"Detected language: {detected_lang} for message: {user_message[:50]}")
        
        if not is_safe_content(user_message):
            response_text = get_response_template('inappropriate', detected_lang)
            if CONTEXT_ENABLED:
                ConversationManager.add_message(session_id, "user", user_message)
                ConversationManager.add_message(session_id, "assistant", response_text)
            return jsonify({'response': response_text, 'session_id': session_id})
        
        if CONTEXT_ENABLED:
            ConversationManager.add_message(session_id, "user", user_message)
        
        messages = ConversationManager.get_messages(session_id) if CONTEXT_ENABLED else [
            {"role": "system", "content": get_response_template('system', BOT_LANGUAGE)},
            {"role": "user", "content": user_message}
        ]
        
        logger.info(f"📝 Sending {len(messages)} messages to OpenAI (session: {session_id})")
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE
        )
        
        assistant_message = response.choices[0].message.content
        
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
        return jsonify({'error': str(e)}), 500


@app.route('/api/context/clear', methods=['POST'])
def clear_context():
    """Clear conversation context for a session"""
    try:
        data = request.json or {}
        session_id = data.get('session_id') or request.headers.get('X-Session-ID')
        
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        
        if ConversationManager.clear_session(session_id):
            return jsonify({'message': 'Context cleared', 'session_id': session_id})
        else:
            return jsonify({'message': 'Session not found', 'session_id': session_id}), 404
    
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
            return jsonify({'message': 'Session not found', 'session_id': session_id}), 404
        
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
        return jsonify({'error': 'OpenAI API key not configured'}), 500
    
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_audio:
            audio_file.save(temp_audio.name)
            
            with open(temp_audio.name, 'rb') as audio_data:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_data,
                )
            
            os.unlink(temp_audio.name)
            logger.info(f"Transcribed text: {transcript.text}")
            
            return jsonify({'text': transcript.text})
    
    except Exception as e:
        logger.error(f"Error in transcribe endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/voice', methods=['POST'])
def voice():
    """Handle voice requests with automatic voice selection"""
    if not client:
        return jsonify({'error': 'OpenAI API key not configured'}), 500
    
    try:
        data = request.json
        text = data.get('text', '')
        language = data.get('language', 'auto')  # Client có thể chỉ định ngôn ngữ
        
        if not text:
            return jsonify({'error': 'Text is required'}), 400
        
        # Generate speech với voice tự động chọn
        audio_bytes = text_to_speech(text, format='mp3', language=language)
        
        # Save to temp file
        output_path = Path("/tmp/speech.mp3")
        with open(output_path, 'wb') as f:
            f.write(audio_bytes)
        
        return send_from_directory('/tmp', 'speech.mp3', mimetype='audio/mpeg')
    
    except Exception as e:
        logger.error(f"Error in voice endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/voice-chat', methods=['POST'])
def voice_chat():
    """Handle voice chat with intelligent language/voice switching - MAIN ENDPOINT FOR ESP32"""
    if not client:
        return jsonify({'error': 'OpenAI API key not configured'}), 500
    
    try:
        # Lấy hoặc tạo session_id
        session_id = request.headers.get('X-Session-ID')
        if not session_id:
            session_id = secrets.token_hex(16)
            logger.info(f"🆕 Created new session for ESP32: {session_id}")
        
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_data = request.files['audio'].read()
        logger.info(f"📥 Received {len(audio_data)} bytes of audio (session: {session_id})")

        # Transcribe audio
        transcribed_text = transcribe_audio(audio_data)
        logger.info(f"📝 Transcribed: {transcribed_text}")

        # Get AI response (with automatic language handling)
        raw_ai_response = get_chat_response(transcribed_text, session_id)
        logger.info(f"🤖 Raw AI Response: {raw_ai_response}")

        # Lấy ngôn ngữ hiện tại của session
        current_lang = ConversationManager.get_language(session_id) if CONTEXT_ENABLED else detect_language(raw_ai_response)

        response_headers = {
            'Content-Type': 'audio/wav',
            'X-Transcription': transcribed_text.encode('utf-8').decode('latin-1'),
            'X-Response-Text': raw_ai_response.encode('utf-8').decode('latin-1'),
            'X-Session-ID': session_id,
            'X-Language': current_lang  # Trả về ngôn ngữ hiện tại cho ESP32
        }
        
        text_for_tts = raw_ai_response

        # Check if the response is a device command
        if raw_ai_response.strip().startswith('{'):
            try:
                command_data = json.loads(raw_ai_response)
                command = command_data.get("command")
                value = command_data.get("value")

                if command and value:
                    logger.info(f"✅ Parsed command: {command}, value: {value}")
                    response_headers['X-Device-Command'] = command
                    response_headers['X-Device-Value'] = str(value)
                    
                    # Confirmation message based on current language
                    confirmations = {
                        'set_volume': {
                            'vi': 'Đã điều chỉnh âm lượng',
                            'en': 'Volume adjusted'
                        },
                        'set_mic_gain': {
                            'vi': 'Đã chỉnh độ nhạy mic',
                            'en': 'Mic sensitivity adjusted'
                        },
                        'stop_conversation': {
                            'vi': 'Tạm biệt',
                            'en': 'Goodbye'
                        }
                    }
                    text_for_tts = confirmations.get(command, {}).get(current_lang, raw_ai_response)
            except json.JSONDecodeError:
                logger.warning("Response looked like JSON but was not valid.")

        # Generate audio với voice phù hợp với ngôn ngữ
        audio_response = text_to_speech(text_for_tts, format='wav', language=current_lang)
        logger.info(f"🔊 Generated TTS: '{text_for_tts}' (lang={current_lang})")
        
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
        'language': BOT_LANGUAGE,  # ✅ SỬA: dùng BOT_LANGUAGE thay vì OPENAI_LANGUAGE
        'api_key_configured': bool(OPENAI_API_KEY),
        'context_enabled': CONTEXT_ENABLED,
        'active_sessions': len(conversations)
    })


@app.route('/debug/audio/<filename>')
def serve_debug_audio(filename):
    """Serve debug audio files for quality checking"""
    try:
        debug_dir = os.path.abspath("debug_audio")
        
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
    """List all debug audio files with playable links"""
    try:
        debug_dir = "debug_audio"
        
        if not os.path.exists(debug_dir):
            return jsonify({'message': 'No debug files yet', 'files': []})
        
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
