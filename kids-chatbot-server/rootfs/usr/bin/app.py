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
import uuid

# Import utilities
from utils.content_filter import is_safe_content
from utils.response_templates import get_response_template
try:
    from utils.db_helper import DatabaseHelper
    db = DatabaseHelper
except ImportError:
    logger.warning("⚠️ Database helper not available, using in-memory only")
    db = None

# ============================================
# GLOBAL VARIABLES
# ============================================
client = None
db_helper = None
current_voice_mode = 'female'  # default: female voice
is_command_mode = False
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
CONTEXT_PERSIST = os.getenv("CONTEXT_PERSIST", "true").lower() == "true"  # ⬅️ THÊM MỚI
CONTEXT_STORAGE_DIR = os.getenv("CONTEXT_STORAGE_DIR", "/data/conversations")  # ⬅️ THÊM MỚI

BOT_LANGUAGE = os.getenv("BOT_LANGUAGE", "vi").lower()
CUSTOM_PROMPT_ADDITIONS = os.getenv("CUSTOM_PROMPT_ADDITIONS", "")

# Voice selection based on language
VOICE_MAP = {
    'vi': os.getenv("VOICE_VIETNAMESE", "alloy"),
    'en': os.getenv("VOICE_ENGLISH", "nova"),
    'auto': OPENAI_VOICE
}

logger.info(f"--- Yên Hoà ChatBot Server Starting ---")
logger.info(f"Model: {OPENAI_MODEL}")
logger.info(f"Voice: {OPENAI_VOICE}")
logger.info(f"Voice Map: VI={VOICE_MAP['vi']}, EN={VOICE_MAP['en']}")
logger.info(f"Language: {BOT_LANGUAGE}")
logger.info(f"Context Enabled: {CONTEXT_ENABLED}")
logger.info(f"Context Persist: {CONTEXT_PERSIST}")
logger.info(f"Custom Prompt: {CUSTOM_PROMPT_ADDITIONS[:50]}..." if CUSTOM_PROMPT_ADDITIONS else "Custom Prompt: (none)")
logger.info(f"Port: {PORT}")
logger.info(f"------------------------------------")

# Validate and initialize OpenAI client
if not OPENAI_API_KEY:
    logger.error("CRITICAL: OPENAI_API_KEY is not set!")
    client = None
else:
    logger.info("OpenAI API key is configured")
    client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize database connection
if CONTEXT_PERSIST and db:
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', '192.168.100.251'),
        'user': os.getenv('DB_USER', 'paulsteigel'),
        'password': os.getenv('DB_PASSWORD', 'D1ndh1sk'),
        'database': os.getenv('DB_NAME', 'homeassistant'),
        'charset': 'utf8mb4',
        'use_unicode': True
    }
    
    try:
        db.initialize(DB_CONFIG)
        logger.info("✅ Database connection established")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        logger.warning("⚠️ Falling back to in-memory storage")
        db = None
        
# Create storage directory if persist is enabled
if CONTEXT_PERSIST:
    Path(CONTEXT_STORAGE_DIR).mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 Context storage: {CONTEXT_STORAGE_DIR}")

# In-memory conversation storage
conversations = {}


class ConversationManager:
    """Quản lý context, language, voice preferences với MySQL persistence"""
    
    @staticmethod
    def get_or_create_session(session_id=None, preferred_lang=None, preferred_voice=None):
        """Lấy hoặc tạo session ID mới"""
        if session_id and session_id in conversations:
            conversations[session_id]['last_activity'] = datetime.now()
            if preferred_lang:
                conversations[session_id]['language'] = preferred_lang
            if preferred_voice:
                conversations[session_id]['voice'] = preferred_voice
            
            # Lưu vào DB
            if CONTEXT_PERSIST and db:
                db.save_session(session_id, conversations[session_id])
            
            return session_id
        
        # Load từ database nếu tồn tại
        if session_id and CONTEXT_PERSIST and db:
            loaded_data = db.load_session(session_id)
            if loaded_data:
                conversations[session_id] = loaded_data
                conversations[session_id]['last_activity'] = datetime.now()
                logger.info(f"📂 Loaded session from database: {session_id}")
                return session_id
        
        # Tạo session mới
        new_session_id = session_id or secrets.token_hex(16)
        lang = preferred_lang or BOT_LANGUAGE
        voice = preferred_voice or VOICE_MAP.get(lang, OPENAI_VOICE)
        
        system_prompt_template = get_response_template('system', lang)
        final_system_prompt = system_prompt_template.replace("{{CUSTOM_INSTRUCTIONS}}", CUSTOM_PROMPT_ADDITIONS)
        
        greeting_message = get_response_template('greeting', lang)
        
        conversations[new_session_id] = {
            'messages': [{"role": "system", "content": final_system_prompt}],
            'language': lang,
            'voice': voice,
            'created_at': datetime.now(),
            'last_activity': datetime.now(),
            'metadata': {
                'title': f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                'initial_greeting': greeting_message
            }
        }
        
        logger.info(f"✅ Created new session: {new_session_id} (language: {lang}, voice: {voice})")
        
        # Lưu vào database
        if CONTEXT_PERSIST and db:
            db.save_session(new_session_id, conversations[new_session_id])
            db.save_message(new_session_id, 'system', final_system_prompt)
        
        return new_session_id
    
    @staticmethod
    def add_message(session_id, role, content, tokens_used=0):
        """Thêm tin nhắn vào lịch sử"""
        if session_id not in conversations:
            ConversationManager.get_or_create_session(session_id)
        
        conversations[session_id]['messages'].append({"role": role, "content": content})
        conversations[session_id]['last_activity'] = datetime.now()
        
        # Lưu vào database
        if CONTEXT_PERSIST and db:
            db.save_message(session_id, role, content, tokens_used)
            db.save_session(session_id, conversations[session_id])
        
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
    def get_voice(session_id):
        """Lấy voice hiện tại của session"""
        if session_id in conversations:
            return conversations[session_id].get('voice', OPENAI_VOICE)
        return OPENAI_VOICE
    
    @staticmethod
    def get_greeting(session_id):
        """Lấy greeting message của session"""
        if session_id in conversations:
            return conversations[session_id].get('metadata', {}).get('initial_greeting', '')
        return ''
    
    @staticmethod
    def set_language(session_id, language):
        """Thay đổi ngôn ngữ của session và cập nhật system prompt"""
        if session_id in conversations:
            conversations[session_id]['language'] = language
            new_system_prompt = get_response_template('system', language)
            new_system_prompt = new_system_prompt.replace("{{CUSTOM_INSTRUCTIONS}}", CUSTOM_PROMPT_ADDITIONS)
            conversations[session_id]['messages'][0] = {"role": "system", "content": new_system_prompt}
            
            if 'voice_override' not in conversations[session_id]:
                conversations[session_id]['voice'] = VOICE_MAP.get(language, OPENAI_VOICE)
            
            logger.info(f"🌐 Session {session_id} switched to language: {language}")
            
            if CONTEXT_PERSIST and db:
                db.save_session(session_id, conversations[session_id])
            
            return True
        return False
    
    @staticmethod
    def set_voice(session_id, voice):
        """Thay đổi giọng nói của session"""
        if session_id in conversations:
            conversations[session_id]['voice'] = voice
            conversations[session_id]['voice_override'] = True
            logger.info(f"🎤 Session {session_id} switched to voice: {voice}")
            
            if CONTEXT_PERSIST and db:
                db.save_session(session_id, conversations[session_id])
            
            return True
        return False
    
    @staticmethod
    def clear_session(session_id):
        """Xóa session"""
        if session_id in conversations:
            del conversations[session_id]
            logger.info(f"🗑️ Cleared session: {session_id}")
            
            if CONTEXT_PERSIST and db:
                db.delete_session(session_id)
            
            return True
        return False
    
    @staticmethod
    def cleanup_old_sessions():
        """Xóa các session không hoạt động"""
        now = datetime.now()
        timeout = timedelta(minutes=CONTEXT_TIMEOUT_MINUTES)
        
        # Cleanup in-memory
        expired_sessions = [
            sid for sid, data in conversations.items()
            if now - data['last_activity'] > timeout
        ]
        for sid in expired_sessions:
            del conversations[sid]
            logger.info(f"⏰ Auto-deleted expired session: {sid}")
        
        # Cleanup database
        if CONTEXT_PERSIST and db:
            db.cleanup_old_sessions(CONTEXT_TIMEOUT_MINUTES)
        
        return len(expired_sessions)



# ============================================
# LANGUAGE & VOICE DETECTION
# ============================================

def detect_language(text):
    """
    Nhận diện ngôn ngữ dựa trên bộ ký tự
    Improved version: Kiểm tra tỷ lệ thay vì chỉ có/không có
    """
    vietnamese_chars = 'àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ'
    text_lower = text.lower()
    
    # Đếm số lượng ký tự mỗi loại
    vi_char_count = sum(1 for char in text_lower if char in vietnamese_chars)
    en_char_count = sum(1 for char in text_lower if char.isalpha() and char.isascii())
    total_alpha = sum(1 for char in text_lower if char.isalpha())
    
    if total_alpha == 0:
        return 'auto'
    
    # Tính tỷ lệ
    vi_ratio = vi_char_count / total_alpha
    en_ratio = en_char_count / total_alpha
    
    # Quyết định dựa trên tỷ lệ
    if vi_ratio > 0.1:  # Nếu >10% là ký tự tiếng Việt → tiếng Việt
        return 'vi'
    elif en_ratio > 0.5:  # Nếu >50% là ký tự ASCII → tiếng Anh
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
        'dùng tiếng anh', 'trả lời bằng tiếng anh', 'đổi sang tiếng anh'
    ]
    
    # Yêu cầu chuyển sang tiếng Việt
    vi_triggers = [
        'speak vietnamese', 'talk in vietnamese', 'use vietnamese', 
        'switch to vietnamese', 'answer in vietnamese', 'reply in vietnamese',
        'hãy nói tiếng việt', 'nói tiếng việt', 'chuyển sang tiếng việt', 
        'dùng tiếng việt', 'trả lời bằng tiếng việt', 'đổi sang tiếng việt'
    ]
    
    for trigger in en_triggers:
        if trigger in message_lower:
            return ('en', True)
    
    for trigger in vi_triggers:
        if trigger in message_lower:
            return ('vi', True)
    
    return (None, False)


def detect_voice_change_intent(user_message):
    """
    Phát hiện ý định thay đổi giọng nói
    Returns: (voice_name, is_voice_change_request)
    """
    message_lower = user_message.lower().strip()
    
    voice_mappings = {
        'nova': [
            'giọng nữ', 'giọng gái', 'giọng con gái',
            'female voice', 'woman voice', 'girl voice', 
            'dùng giọng nữ', 'chuyển giọng nữ', 'đổi giọng nữ',
            'use female voice', 'switch to female', 'change to female voice',
            'giọng nova', 'voice nova', 'use nova'
        ],
        
        'shimmer': [
            'giọng nữ mềm', 'giọng nữ nhẹ nhàng',
            'soft female voice', 'gentle female voice',
            'giọng shimmer', 'voice shimmer', 'use shimmer'
        ],
        
        'onyx': [
            'giọng nam', 'giọng trai', 'giọng con trai',
            'male voice', 'man voice', 'boy voice',
            'dùng giọng nam', 'chuyển giọng nam', 'đổi giọng nam',
            'use male voice', 'switch to male', 'change to male voice',
            'giọng onyx', 'voice onyx', 'use onyx'
        ],
        
        'echo': [
            'giọng nam echo', 'giọng echo',
            'voice echo', 'use echo'
        ],
        
        'fable': [
            'giọng fable', 'voice fable', 'use fable'
        ],
        
        'alloy': [
            'giọng trung tính', 'giọng neutral',
            'neutral voice', 'default voice',
            'giọng alloy', 'voice alloy', 'use alloy'
        ]
    }
    
    for voice, triggers in voice_mappings.items():
        for trigger in triggers:
            if trigger in message_lower:
                return (voice, True)
    
    return (None, False)


# ============================================
# AUDIO PROCESSING
# ============================================

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


def get_chat_response(user_message, session_id='default', return_greeting=False):
    """
    Get AI response with intelligent language and voice handling
    
    Args:
        user_message: User's input text
        session_id: Session identifier
        return_greeting: If True and it's first message, return greeting instead
    """
    try:
        logger.info(f"🤖 Getting AI response for: {user_message}")
        
        detected_lang = detect_language(user_message)
        
        if not is_safe_content(user_message):
            return get_response_template('inappropriate', detected_lang)
        
        (target_voice, is_voice_change) = detect_voice_change_intent(user_message)
        (target_lang, is_lang_switch) = detect_language_switch_intent(user_message)
        
        if CONTEXT_ENABLED:
            session_id = ConversationManager.get_or_create_session(session_id)
            current_lang = ConversationManager.get_language(session_id)
            current_voice = ConversationManager.get_voice(session_id)
            
            # Nếu là lần đầu tiên và yêu cầu greeting
            messages = ConversationManager.get_messages(session_id)
            if return_greeting and len(messages) == 1:  # Chỉ có system message
                greeting = ConversationManager.get_greeting(session_id)
                if greeting:
                    ConversationManager.add_message(session_id, "assistant", greeting)
                    logger.info(f"👋 Returned initial greeting for session {session_id}")
                    return greeting
            
            # XỬ LÝ THAY ĐỔI GIỌNG NÓI
            if is_voice_change and target_voice:
                ConversationManager.set_voice(session_id, target_voice)
                voice_descriptions = {
                    'nova': 'giọng nữ Nova' if current_lang == 'vi' else 'female voice Nova',
                    'onyx': 'giọng nam Onyx' if current_lang == 'vi' else 'male voice Onyx',
                    'alloy': 'giọng Alloy' if current_lang == 'vi' else 'voice Alloy',
                    'echo': 'giọng Echo' if current_lang == 'vi' else 'voice Echo',
                    'fable': 'giọng Fable' if current_lang == 'vi' else 'voice Fable',
                    'shimmer': 'giọng Shimmer' if current_lang == 'vi' else 'voice Shimmer'
                }
                voice_desc = voice_descriptions.get(target_voice, target_voice)
                
                confirmation = (
                    f"Được rồi! Mình sẽ dùng {voice_desc} từ bây giờ nhé." 
                    if current_lang == 'vi' 
                    else f"Sure! I'll use {voice_desc} from now on."
                )
                ConversationManager.add_message(session_id, "user", user_message)
                ConversationManager.add_message(session_id, "assistant", confirmation)
                logger.info(f"🎤 Voice changed to {target_voice} for session {session_id}")
                return confirmation
            
            # XỬ LÝ THAY ĐỔI NGÔN NGỮ
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
            
            if detected_input_lang != 'auto' and detected_input_lang != current_lang:
                logger.info(f"🌐 Auto-switching language from {current_lang} to {detected_input_lang}")
                ConversationManager.set_language(session_id, detected_input_lang)
            
            ConversationManager.add_message(session_id, "user", user_message)
            messages = ConversationManager.get_messages(session_id)
            
        else:
            session_id = ConversationManager.get_or_create_session()
            system_prompt_template = get_response_template('system', detected_lang if detected_lang != 'auto' else BOT_LANGUAGE)
            final_system_prompt = system_prompt_template.replace("{{CUSTOM_INSTRUCTIONS}}", CUSTOM_PROMPT_ADDITIONS)
            messages = [
                {"role": "system", "content": final_system_prompt},
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
        
        logger.info(f"✓ AI Response: {assistant_message}")
        return assistant_message
        
    except Exception as e:
        logger.error(f"❌ AI error: {str(e)}")
        raise


def text_to_speech(text: str, format: str = "mp3", language: str = "auto") -> bytes:
    """
    Convert text to speech using OpenAI TTS API
    
    Args:
        text: Text to convert to speech
        format: Audio format (mp3, opus, aac, flac, wav, pcm)
        language: Language hint ('auto', 'vi', 'en')
    
    Returns:
        Audio bytes
    """
    global current_voice_mode
    
    try:
        # Detect language if auto
        detected_lang = language
        if language == "auto":
            detected_lang = detect_language(text)
        
        # Select voice based on current mode and language
        if detected_lang == "vi":
            voice = "nova" if current_voice_mode == "female" else "onyx"
        else:  # English
            voice = "nova" if current_voice_mode == "female" else "echo"
        
        logger.info(f"🎤 TTS: lang={detected_lang}, voice={voice}, mode={current_voice_mode}")
        logger.info(f"📝 Text: {text[:100]}...")
        
        # Generate speech
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format=format
        )
        
        audio_bytes = response.content
        
        logger.info(f"✅ Generated {len(audio_bytes)} bytes of audio")
        
        return audio_bytes
        
    except Exception as e:
        logger.error(f"❌ TTS Error: {str(e)}", exc_info=True)
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

def handle_home_automation_command(user_message: str):
    """
    Parse and execute home automation commands
    Supports:
    - Volume control (tăng/giảm âm lượng)
    - Mic gain control (tăng/giảm độ nhạy mic)
    - Device control (bật/tắt thiết bị)
    """
    lower_msg = user_message.lower()
    
    # ============================================
    # 1. VOLUME CONTROL
    # ============================================
    volume_increase = [
        'tăng âm lượng', 'to tiếng lên', 'increase volume',
        'louder', 'volume up', 'to hơn'
    ]
    volume_decrease = [
        'giảm âm lượng', 'nhỏ tiếng lại', 'decrease volume',
        'lower', 'volume down', 'nhỏ hơn'
    ]
    
    if any(pattern in lower_msg for pattern in volume_increase):
        # TODO: Gọi API Home Assistant để tăng volume
        # Ví dụ: call_service('media_player', 'volume_up', entity_id='media_player.living_room')
        logger.info("🔊 Volume UP")
        return "Đã tăng âm lượng lên rồi nè! 🔊"
    
    if any(pattern in lower_msg for pattern in volume_decrease):
        # TODO: Gọi API Home Assistant để giảm volume
        logger.info("🔉 Volume DOWN")
        return "Đã giảm âm lượng xuống rồi nè! 🔉"
    
    # ============================================
    # 2. MIC GAIN CONTROL
    # ============================================
    mic_increase = [
        'tăng độ nhạy mic', 'mic nhạy hơn', 'increase mic gain',
        'mic gain up', 'tăng mic'
    ]
    mic_decrease = [
        'giảm độ nhạy mic', 'mic kém nhạy', 'decrease mic gain',
        'mic gain down', 'giảm mic'
    ]
    
    if any(pattern in lower_msg for pattern in mic_increase):
        # TODO: Điều chỉnh mic gain (cần tích hợp với ESP32)
        logger.info("🎤 Mic gain UP")
        return "Đã tăng độ nhạy mic lên rồi nè! 🎤"
    
    if any(pattern in lower_msg for pattern in mic_decrease):
        # TODO: Điều chỉnh mic gain
        logger.info("🎤 Mic gain DOWN")
        return "Đã giảm độ nhạy mic xuống rồi nè! 🎤"
    
    # ============================================
    # 3. DEVICE CONTROL (BẬT/TẮT THIẾT BỊ)
    # ============================================
    
    # Device mapping
    device_map = {
        'light': ['đèn', 'light', 'lamp', 'ánh sáng'],
        'fan': ['quạt', 'fan'],
        'tv': ['tv', 'tivi', 'television'],
        'air_conditioner': ['điều hòa', 'air conditioner', 'ac', 'máy lạnh'],
        'door': ['cửa', 'door'],
        'window': ['cửa sổ', 'window']
    }
    
    # Action mapping
    action = None
    if any(word in lower_msg for word in ['bật', 'turn on', 'open', 'mở', 'on']):
        action = 'turn_on'
    elif any(word in lower_msg for word in ['tắt', 'turn off', 'close', 'đóng', 'off']):
        action = 'turn_off'
    
    # Find device
    device = None
    device_keywords = None
    for device_key, keywords in device_map.items():
        if any(keyword in lower_msg for keyword in keywords):
            device = device_key
            device_keywords = keywords
            break
    
    if not action or not device:
        return "Em chưa hiểu lệnh. Bé có thể nói rõ hơn được không?\n\nVí dụ:\n- Bật đèn phòng khách\n- Tăng âm lượng\n- Tăng độ nhạy mic"
    
    # Execute device command
    try:
        device_name_vi = {
            'light': 'đèn',
            'fan': 'quạt',
            'tv': 'TV',
            'air_conditioner': 'điều hòa',
            'door': 'cửa',
            'window': 'cửa sổ'
        }[device]
        
        action_name_vi = 'bật' if action == 'turn_on' else 'tắt'
        
        # TODO: Tích hợp Home Assistant API
        # Example:
        # ha_entity_id = f"{device}.living_room"
        # call_home_assistant_service(action, ha_entity_id)
        
        logger.info(f"🏠 Device command: {action_name_vi.upper()} {device_name_vi}")
        
        return f"Đã {action_name_vi} {device_name_vi} rồi nè! ✅"
    
    except Exception as e:
        logger.error(f"❌ Command execution error: {str(e)}")
        return f"Có lỗi khi {action_name_vi} {device_name_vi}. Bé thử lại nhé!"


# ============================================
# API ENDPOINTS
# ============================================

@app.route('/')
def index():
    """Serve the test interface"""
    return send_from_directory('/usr/bin/static', 'index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat requests with context management"""
    global current_voice_mode, is_command_mode
    
    if not client:
        return jsonify({'error': 'OpenAI API key not configured'}), 500
    
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        logger.info(f"📩 Message: '{user_message[:50]}...' | Session: {session_id or 'NEW'}")
        
        lower_msg = user_message.lower()
        
        # ============================================
        # 1. DETECT COMMAND MODE ACTIVATION/DEACTIVATION
        # ============================================
        activate_triggers = [
            'chế độ điều khiển', 'command mode',
            'bật chế độ điều khiển', 'enter command mode',
            'sang chế độ điều khiển', 'switch to command mode'
        ]
        
        deactivate_triggers = [
            'stop command mode', 'dừng điều khiển',
            'thoát chế độ điều khiển', 'exit command mode',
            'kết thúc điều khiển', 'end command mode'
        ]
        
        # Activate command mode
        if any(trigger in lower_msg for trigger in activate_triggers):
            is_command_mode = True
            logger.info("🎮 COMMAND MODE: ACTIVATED")
            return jsonify({
                'response': 'Đã bật chế độ điều khiển. Em có thể nhận lệnh điều chỉnh âm lượng, mic và điều khiển thiết bị.',
                'command_mode': True,
                'voice_mode': current_voice_mode
            })
        
        # Deactivate command mode
        if any(trigger in lower_msg for trigger in deactivate_triggers):
            is_command_mode = False
            logger.info("🎮 COMMAND MODE: DEACTIVATED")
            return jsonify({
                'response': 'Đã tắt chế độ điều khiển. Em sẵn sàng chat lại!',
                'command_mode': False,
                'voice_mode': current_voice_mode
            })
        
        # ============================================
        # 2. HANDLE COMMAND MODE REQUESTS
        # ============================================
        if is_command_mode:
            command_result = handle_home_automation_command(user_message)
            return jsonify({
                'response': command_result,
                'command_mode': True,
                'voice_mode': current_voice_mode
            })
        
        # ============================================
        # 3. DETECT VOICE CHANGE COMMANDS (OUTSIDE COMMAND MODE)
        # ============================================
        voice_change_detected = False
        voice_change_response = ""
        
        # Vietnamese voice patterns
        vi_female_patterns = [
            'chuyển sang giọng nữ', 'dùng giọng nữ', 'giọng nữ đi',
            'nói giọng nữ', 'đổi sang giọng nữ', 'sang giọng nữ'
        ]
        vi_male_patterns = [
            'chuyển sang giọng nam', 'dùng giọng nam', 'giọng nam đi',
            'nói giọng nam', 'đổi sang giọng nam', 'sang giọng nam'
        ]
        
        # English voice patterns
        en_female_patterns = [
            'change to female voice', 'switch to female voice',
            'use female voice', 'female voice please',
            'change voice to female', 'switch voice to female'
        ]
        en_male_patterns = [
            'change to male voice', 'switch to male voice',
            'use male voice', 'male voice please',
            'change voice to male', 'switch voice to male'
        ]
        
        if any(pattern in lower_msg for pattern in vi_female_patterns):
            current_voice_mode = 'female'
            voice_change_detected = True
            voice_change_response = "Dạ, em đã chuyển sang giọng nữ rồi ạ!"
            logger.info("🎤 Voice → FEMALE (Vietnamese)")
        
        elif any(pattern in lower_msg for pattern in vi_male_patterns):
            current_voice_mode = 'male'
            voice_change_detected = True
            voice_change_response = "Dạ, em đã chuyển sang giọng nam rồi ạ!"
            logger.info("🎤 Voice → MALE (Vietnamese)")
        
        elif any(pattern in lower_msg for pattern in en_female_patterns):
            current_voice_mode = 'female'
            voice_change_detected = True
            voice_change_response = "Sure! I've switched to female voice."
            logger.info("🎤 Voice → FEMALE (English)")
        
        elif any(pattern in lower_msg for pattern in en_male_patterns):
            current_voice_mode = 'male'
            voice_change_detected = True
            voice_change_response = "Sure! I've switched to male voice."
            logger.info("🎤 Voice → MALE (English)")
        
        # Return immediately if voice change command
        if voice_change_detected:
            return jsonify({
                'response': voice_change_response,
                'session_id': session_id or str(uuid.uuid4()),
                'voice_mode': current_voice_mode
            })
        
        # ============================================
        # 4. REGULAR CHAT FLOW
        # ============================================
        
        # Get or create session
        if session_id:
            session_data = db_helper.get_session(session_id)
            if not session_data:
                logger.warning(f"Session {session_id} not found, creating new one")
                session_id = None
        else:
            session_data = None
        
        is_new_session = False
        
        if not session_id:
            session_id = str(uuid.uuid4())
            user_id = data.get('user_id', f'web_{uuid.uuid4().hex[:8]}')
            
            db_helper.create_session(
                session_id=session_id,
                user_id=user_id,
                context=[]
            )
            is_new_session = True
            logger.info(f"✅ New session created: {session_id}")
        
        # Load conversation history
        if session_data:
            context_messages = session_data.get('context', [])
        else:
            context_messages = []
        
        # ============================================
        # 5. SYSTEM PROMPT (CHỈ CHO NEW SESSION)
        # ============================================
        system_prompt = {
            "role": "system",
            "content": """Bạn là một trợ lý học tập thông minh tên là Yên Hoà ChatBot, được thiết kế đặc biệt để hỗ trợ học sinh tiểu học.

**TÍNH CÁCH VÀ PHONG CÁCH:**
- Luôn vui vẻ, nhiệt tình và kiên nhẫn
- Nói chuyện thân thiện như một người chị/anh lớn
- Dùng ngôn ngữ đơn giản, dễ hiểu phù hợp với trẻ em
- Khuyến khích em tự suy nghĩ trước khi đưa ra câu trả lời
- Khen ngợi khi em làm đúng, động viên khi em chưa hiểu

**NHIỆM VỤ CHÍNH:**
1. Giải đáp thắc mắc về bài học (Toán, Tiếng Việt, Khoa học...)
2. Hướng dẫn làm bài tập theo phương pháp gợi mở
3. Kể chuyện giáo dục, giải trí
4. Trò chuyện về cuộc sống, sở thích
5. Khuyến khích thói quen học tập tốt

**NGUYÊN TẮC QUAN TRỌNG:**
- KHÔNG đưa ra đáp án trực tiếp cho bài tập, mà hướng dẫn cách làm
- KHÔNG sử dụng thuật ngữ phức tạp
- KHÔNG nói về chủ đề không phù hợp với trẻ em
- CÓ THỂ chuyển đổi giữa tiếng Việt và tiếng Anh theo yêu cầu

**CÁCH TRẢ LỜI:**
- Câu trả lời ngắn gọn, rõ ràng (2-4 câu)
- Dùng emoji phù hợp 😊📚✨ (không lạm dụng)
- Hỏi lại để kiểm tra hiểu biết của em

Hãy là người bạn học tập đáng tin cậy của các em!"""
        }
        
        # ============================================
        # 6. BUILD MESSAGES FOR GPT
        # ============================================
        messages = []
        
        if is_new_session:
            # Chỉ thêm system prompt cho session mới
            messages.append(system_prompt)
        else:
            # Session cũ: load từ context (đã có system prompt từ trước)
            if context_messages:
                # Lấy 10 messages gần nhất
                messages = context_messages[-10:]
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        # ============================================
        # 7. GREETING FOR NEW SESSIONS
        # ============================================
        greeting_message = ""
        if is_new_session:
            greetings = [
                "Chào bé yêu! Hôm nay bé khỏe không? Em là Yên Hoà ChatBot, sẵn sàng giúp bé học tập vui vẻ nè! 😊",
                "Xin chào bé! Em rất vui được làm quen với bé. Có câu hỏi gì về bài học không? 📚",
                "Hi bé! Em là trợ lý học tập Yên Hoà. Hôm nay bé muốn học gì nhỉ? ✨",
                "Chào bé ngoan! Em sẵn sàng giúp bé giải đáp thắc mắc rồi nè! 🎓",
                "Xin chào! Em là Yên Hoà ChatBot - người bạn học tập của bé. Bé cần giúp gì không? 😄"
            ]
            greeting_message = random.choice(greetings) + "\n\n"
        
        # ============================================
        # 8. CALL GPT-4
        # ============================================
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.8,
            max_tokens=500
        )
        
        assistant_response = completion.choices[0].message.content.strip()
        full_response = greeting_message + assistant_response
        
        # ============================================
        # 9. SAVE TO DATABASE
        # ============================================
        # Build new context
        if is_new_session:
            new_context = [
                system_prompt,
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": full_response}
            ]
        else:
            new_context = messages + [
                {"role": "assistant", "content": full_response}
            ]
        
        # Keep only last 20 messages
        if len(new_context) > 20:
            new_context = new_context[-20:]
        
        db_helper.update_session(
            session_id=session_id,
            context=new_context
        )
        
        # Save individual messages
        db_helper.save_message(
            session_id=session_id,
            role='user',
            content=user_message
        )
        
        db_helper.save_message(
            session_id=session_id,
            role='assistant',
            content=full_response
        )
        
        logger.info(f"✅ Response generated | Voice: {current_voice_mode} | Session: {session_id[:8]}...")
        
        return jsonify({
            'response': full_response,
            'session_id': session_id,
            'is_new_session': is_new_session,
            'voice_mode': current_voice_mode
        })
    
    except Exception as e:
        logger.error(f"❌ Chat error: {str(e)}", exc_info=True)
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
    """Handle voice chat - MAIN ENDPOINT FOR ESP32"""
    if not client:
        return jsonify({'error': 'OpenAI API key not configured'}), 500
    
    try:
        session_id = request.headers.get('X-Session-ID')
        if not session_id:
            session_id = secrets.token_hex(16)
            logger.info(f"🆕 Created new session for ESP32: {session_id}")
        
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_data = request.files['audio'].read()
        logger.info(f"📥 Received {len(audio_data)} bytes of audio (session: {session_id})")

        transcribed_text = transcribe_audio(audio_data)
        logger.info(f"📝 Transcribed: {transcribed_text}")

        # Kiểm tra nếu là lần đầu tiên gọi → trả greeting
        messages = ConversationManager.get_messages(session_id) if session_id in conversations else []
        is_first_message = len(messages) <= 1  # Chỉ có system prompt
        
        raw_ai_response = get_chat_response(transcribed_text, session_id, return_greeting=is_first_message)
        logger.info(f"🤖 Raw AI Response: {raw_ai_response}")

        current_lang = ConversationManager.get_language(session_id) if CONTEXT_ENABLED else detect_language(raw_ai_response)

        response_headers = {
            'Content-Type': 'audio/wav',
            'X-Transcription': transcribed_text.encode('utf-8').decode('latin-1'),
            'X-Response-Text': raw_ai_response.encode('utf-8').decode('latin-1'),
            'X-Session-ID': session_id,
            'X-Language': current_lang
        }
        
        text_for_tts = raw_ai_response

        if raw_ai_response.strip().startswith('{'):
            try:
                command_data = json.loads(raw_ai_response)
                command = command_data.get("command")
                value = command_data.get("value")

                if command and value:
                    logger.info(f"✅ Parsed command: {command}, value: {value}")
                    response_headers['X-Device-Command'] = command
                    response_headers['X-Device-Value'] = str(value)
                    
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

        audio_response = text_to_speech(text_for_tts, format='wav', language=current_lang, session_id=session_id)
        logger.info(f"🔊 Generated TTS: '{text_for_tts}' (lang={current_lang}, session={session_id})")
        
        return Response(
            audio_response,
            mimetype='audio/wav',
            headers=response_headers
        )

    except Exception as e:
        logger.error(f"❌ Error in voice_chat: {str(e)}", exc_info=True)
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


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'model': OPENAI_MODEL,
        'voice': OPENAI_VOICE,
        'language': BOT_LANGUAGE,
        'api_key_configured': bool(OPENAI_API_KEY),
        'context_enabled': CONTEXT_ENABLED,
        'context_persist': CONTEXT_PERSIST,
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
