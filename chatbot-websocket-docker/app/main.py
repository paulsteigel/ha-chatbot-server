"""
School Chatbot WebSocket Server
Main FastAPI application with WebSocket support for ESP32 devices
✅ WITH MUSIC SERVICE + AZURE AI INTEGRATION
"""
import secrets
import hashlib
from typing import Optional
import time
import aiomysql

from app.config_manager import ConfigManager
config_manager = None

import logging
import asyncio
import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Response, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, JSONResponse, RedirectResponse

# Import services
from app.ai_service import AIService
from app.tts_service import TTSService
from app.stt_service import STTService
from app.device_manager import DeviceManager
from app.ota_manager import OTAManager
from app.websocket_handler import WebSocketHandler
from app.conversation_logger import ConversationLogger
from app.music_service import MusicService
from app.config import SYSTEM_PROMPT, AI_CONFIG, TTS_CONFIG, STT_CONFIG, AI_MODELS

# ==============================================================================
# Configuration Helper - WITH NULL HANDLING
# ==============================================================================

def get_config(key: str, default=None):
    """Get configuration value from environment or Home Assistant options.json"""
    # ✅ PRIORITY 1: Environment variables (for Docker)
    env_key = key.upper()
    env_value = os.getenv(env_key)
    if env_value not in [None, "", "null", "None"]:
        return env_value
    
    # ✅ PRIORITY 2: HA options.json (for add-on compatibility)
    options_file = "/data/options.json"
    if os.path.exists(options_file):
        try:
            with open(options_file, 'r') as f:
                options = json.load(f)
                if key in options:
                    value = options[key]
                    if value not in [None, "", "null", "None"]:
                        return value
        except Exception:
            pass
    
    return default


def safe_int(value, default: int) -> int:
    """Safely convert value to int, handle null/None."""
    if value is None or value == "" or value == "null" or value == "None":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value, default: float) -> float:
    """Safely convert value to float, handle null/None."""
    if value is None or value == "" or value == "null" or value == "None":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_bool(value, default: bool = False) -> bool:
    """
    Safely convert value to bool, handle string/bool/None.
    
    Args:
        value: Can be bool, string, int, or None
        default: Default value if conversion fails
    
    Returns:
        Boolean value
    
    Examples:
        safe_bool(True) -> True
        safe_bool('true') -> True
        safe_bool('false') -> False
        safe_bool(1) -> True
        safe_bool(0) -> False
        safe_bool(None) -> False (default)
    """
    if value is None or value == "" or value == "null" or value == "None":
        return default
    
    # Already a boolean
    if isinstance(value, bool):
        return value
    
    # String conversion
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on', 'enabled')
    
    # Integer conversion (0 = False, non-zero = True)
    if isinstance(value, (int, float)):
        return bool(value)
    
    return default

# ═══════════════════════════════════════════════════════════════════
# AUTHENTICATION & SESSION MANAGEMENT
# ═══════════════════════════════════

# In-memory session storage (for simplicity)
# In production, use Redis or database
active_sessions = {}

def hash_password(password: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return hash_password(plain_password) == hashed_password

def create_session(username: str) -> str:
    """Create a new session and return session token"""
    session_token = secrets.token_urlsafe(32)
    active_sessions[session_token] = {
        'username': username,
        'created_at': time.time()
    }
    return session_token

def get_session(session_token: str) -> Optional[dict]:
    """Get session data from token"""
    return active_sessions.get(session_token)

def delete_session(session_token: str):
    """Delete a session"""
    if session_token in active_sessions:
        del active_sessions[session_token]

async def get_current_user(request: Request) -> dict:
    """Dependency to check if user is authenticated"""
    session_token = request.cookies.get('session_token')
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session = get_session(session_token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    # Check session age (24 hours)
    if time.time() - session['created_at'] > 86400:
        delete_session(session_token)
        raise HTTPException(status_code=401, detail="Session expired")
    
    return session

async def get_admin_credentials():
    """Get admin credentials from database or environment"""
    # Try database first (only if conversation_logger is initialized)
    if conversation_logger and hasattr(conversation_logger, 'pool') and conversation_logger.pool:
        try:
            async with conversation_logger.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("""
                        SELECT config_value FROM chatbot_config 
                        WHERE config_key = 'admin_username'
                    """)
                    username_row = await cursor.fetchone()
                    
                    await cursor.execute("""
                        SELECT config_value FROM chatbot_config 
                        WHERE config_key = 'admin_password_hash'
                    """)
                    password_row = await cursor.fetchone()
                    
                    if username_row and password_row:
                        return {
                            'username': username_row['config_value'],
                            'password_hash': password_row['config_value']
                        }
        except Exception as e:
            logger.warning(f"⚠️ Could not load admin credentials from DB: {e}")
    
    # Fallback to environment variables
    username = os.getenv('ADMIN_USERNAME', 'admin')
    password = os.getenv('ADMIN_PASSWORD', 'admin123')  # Default password
    
    return {
        'username': username,
        'password_hash': hash_password(password)
    }
# ==============================================================================
# Configuration - AFTER get_config() is defined
# ==============================================================================

# Logging setup first
LOG_LEVEL = get_config('log_level', 'INFO').upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('Main')

# Server configuration
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '5000'))

# ✅ AI CONFIGURATION
AI_PROVIDER = get_config('ai_provider', 'deepseek')

# ✅ Update AI_MODELS to include Azure
AI_MODELS_EXTENDED = {
    'openai': 'gpt-4o-mini',
    'deepseek': 'deepseek-chat',
    'azure': 'gpt-4o'
}

# API Keys
OPENAI_API_KEY = get_config('openai_api_key', '')
OPENAI_BASE_URL = get_config('openai_base_url', 'https://api.openai.com/v1')
DEEPSEEK_API_KEY = get_config('deepseek_api_key', '')
DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1')
GROQ_API_KEY = get_config('groq_api_key', '')

# ✅ Azure configuration
AZURE_API_KEY = get_config('azure_api_key', '')
AZURE_ENDPOINT = get_config('azure_endpoint', '')
AZURE_DEPLOYMENT = get_config('azure_deployment', '')
AZURE_API_VERSION = get_config('azure_api_version', '2024-02-15-preview')

# Azure Speech (optional)
#AZURE_SPEECH_KEY = get_config('azure_speech_key', '')
#AZURE_SPEECH_REGION = get_config('azure_speech_region', '')

# Auto-select correct model for provider
if AI_PROVIDER.lower() == 'openai':
    DEFAULT_MODEL = AI_MODELS_EXTENDED.get('openai', 'gpt-4o-mini')
elif AI_PROVIDER.lower() == 'deepseek':
    DEFAULT_MODEL = AI_MODELS_EXTENDED.get('deepseek', 'deepseek-chat')
elif AI_PROVIDER.lower() == 'azure':
    DEFAULT_MODEL = AZURE_DEPLOYMENT or AI_MODELS_EXTENDED.get('azure', 'gpt-4o')
else:
    DEFAULT_MODEL = 'gpt-4o-mini'

# Allow manual override
AI_MODEL = get_config('ai_model', DEFAULT_MODEL)

# MySQL configuration
MYSQL_URL = get_config('mysql_url', '')

# Music Service configuration
MUSIC_SERVICE_URL = get_config('music_service_url', 'https://music.sfdp.net')
ENABLE_MUSIC = get_config('enable_music_playback', True)

# System prompt
SYSTEM_PROMPT_OVERRIDE = get_config('system_prompt', None)
if SYSTEM_PROMPT_OVERRIDE and len(SYSTEM_PROMPT_OVERRIDE) > 50:
    FINAL_SYSTEM_PROMPT = SYSTEM_PROMPT_OVERRIDE
    logger.info("💬 Using CUSTOM system prompt from Home Assistant")
else:
    FINAL_SYSTEM_PROMPT = SYSTEM_PROMPT
    logger.info("💬 Using DEFAULT system prompt from config.py")

# Chat configuration
CHAT_TEMPERATURE = safe_float(
    get_config('temperature', AI_CONFIG.get("temperature", 0.7)),
    0.7
)
CHAT_MAX_TOKENS = safe_int(
    get_config('max_tokens', AI_CONFIG.get("max_tokens", 300)),
    300
)
CHAT_MAX_CONTEXT = safe_int(
    get_config('max_context_messages', AI_CONFIG.get("max_context_messages", 10)),
    10
)

# TTS configuration
TTS_VOICE = get_config('tts_voice_vi', TTS_CONFIG.get("vietnamese_voice", "nova"))

# ✅ LOG CONFIGURATION
logger.info("=" * 80)
logger.info("🤖 AI CONFIGURATION")
logger.info("=" * 80)
logger.info(f"   Provider: {AI_PROVIDER}")
if AI_PROVIDER.lower() == 'azure':
    logger.info(f"   Azure Endpoint: {AZURE_ENDPOINT}")
    logger.info(f"   Azure Deployment: {AZURE_DEPLOYMENT}")
    logger.info(f"   Azure API Version: {AZURE_API_VERSION}")
logger.info(f"   Model (auto): {DEFAULT_MODEL}")
logger.info(f"   Model (final): {AI_MODEL}")
if AI_MODEL != DEFAULT_MODEL:
    logger.warning(f"   ⚠️  Manual override detected!")
logger.info("=" * 80)

config_source = "Home Assistant" if os.path.exists("/data/options.json") else "Environment"
logger.info("=" * 80)
logger.info("📋 FULL CONFIGURATION")
logger.info("=" * 80)
logger.info(f"📂 Config Source: {config_source}")
logger.info(f"🤖 AI Provider: {AI_PROVIDER}")
logger.info(f"🧠 AI Model: {AI_MODEL}")
logger.info(f"💬 System Prompt: {FINAL_SYSTEM_PROMPT[:80]}...")
logger.info(f"🌡️  Temperature: {CHAT_TEMPERATURE}")
logger.info(f"📏 Max Tokens: {CHAT_MAX_TOKENS}")
logger.info(f"💬 Max Context: {CHAT_MAX_CONTEXT}")
logger.info(f"💾 MySQL: {'✅' if MYSQL_URL else '❌'}")
logger.info(f"🎵 Music Service: {'✅' if ENABLE_MUSIC else '❌'} ({MUSIC_SERVICE_URL})")
logger.info(f"📊 Log Level: {LOG_LEVEL}")
logger.info("=" * 80)


# ==============================================================================
# Service Instances (Global)
# ==============================================================================

ai_service = None
tts_service = None
stt_service = None
device_manager = None
ota_manager = None
ws_handler = None
conversation_logger = None
music_service = None

# ==============================================================================
# Service Reload Function
# ==============================================================================
async def reload_services():
    """Reload all services with new configuration from database"""
    global ai_service, tts_service, stt_service, music_service
    
    logger.info("=" * 80)
    logger.info("🔄 RELOADING SERVICES WITH NEW CONFIGURATION")
    logger.info("=" * 80)
    
    try:
        # ============================================================
        # STEP 1: Load fresh config
        # ============================================================
        config = await config_manager.load_config()
        logger.info(f"✅ Loaded {len(config)} config items from database")
        
        # ============================================================
        # STEP 2: Close old services gracefully
        # ============================================================
        if music_service:
            try:
                await music_service.close()
                logger.info("🎵 Old music service closed")
            except Exception as e:
                logger.warning(f"⚠️ Error closing music service: {e}")
        
        # ============================================================
        # STEP 3: Reload AI Service
        # ============================================================
        ai_provider = config.get('ai_provider', 'azure').lower()
        logger.info(f"🤖 Reloading AI Service (provider: {ai_provider})...")
        
        if ai_provider == 'azure':
            api_key = config.get('azure_api_key')
            base_url = config.get('azure_endpoint')
            model = config.get('ai_model') or config.get('azure_deployment')
            azure_api_version = config.get('azure_api_version', '2024-12-01-preview')
        elif ai_provider == 'deepseek':
            api_key = config.get('deepseek_api_key')
            base_url = config.get('deepseek_base_url', 'https://api.deepseek.com/v1')
            model = config.get('ai_model', 'deepseek-chat')
            azure_api_version = None
        else:  # openai
            api_key = config.get('openai_api_key')
            base_url = config.get('openai_base_url', 'https://api.openai.com/v1')
            model = config.get('ai_model', 'gpt-4')
            azure_api_version = None
        
        system_prompt = config.get('system_prompt', FINAL_SYSTEM_PROMPT)
        
        ai_service = AIService(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            temperature=float(config.get('temperature', 0.7)),
            max_tokens=int(config.get('max_tokens', 500)),
            max_context=int(config.get('max_context', 10)),
            provider=ai_provider,
            azure_api_version=azure_api_version
        )
        logger.info(f"✅ AI Service reloaded: {model}")
        
        # ============================================================
        # STEP 4: Reload TTS Service
        # ============================================================
        tts_provider = config.get('tts_provider', 'azure_speech').lower()
        logger.info(f"🔊 Reloading TTS Service (provider: {tts_provider})...")
        
        if tts_provider == 'azure_speech':
            azure_speech_key = config.get('azure_speech_key')
            azure_speech_region = config.get('azure_speech_region', 'eastus')
            
            if not azure_speech_key:
                logger.warning("⚠️ azure_speech_key not found, falling back to Piper")
                tts_provider = 'piper'
            else:
                tts_service = TTSService(
                    provider='azure_speech',
                    api_key=azure_speech_key,
                    region=azure_speech_region,
                    base_url=None
                )
        
        if tts_provider == 'piper':
            piper_host = config.get('piper_host', 'addon_core_piper')
            piper_port = int(config.get('piper_port', 10200))
            tts_service = TTSService(
                provider='piper',
                piper_host=piper_host,
                piper_port=piper_port
            )
        
        elif tts_provider == 'openai':
            openai_key = config.get('openai_api_key')
            openai_url = config.get('openai_base_url', 'https://api.openai.com/v1')
            tts_service = TTSService(
                provider='openai',
                api_key=openai_key,
                base_url=openai_url
            )
        
        logger.info(f"✅ TTS Service reloaded: {tts_provider}")
        
        # ============================================================
        # STEP 5: Reload STT Service
        # ============================================================
        stt_provider = config.get('stt_provider', 'azure_speech').lower()
        logger.info(f"🎤 Reloading STT Service (provider: {stt_provider})...")
        
        if stt_provider == 'azure_speech':
            azure_speech_key = config.get('azure_speech_key')
            if not azure_speech_key:
                logger.warning("⚠️ azure_speech_key not found, falling back to Groq")
                stt_provider = 'groq'
            else:
                stt_service = STTService(
                    api_key=azure_speech_key,
                    model="whisper-1",
                    provider='azure_speech'
                )
        
        if stt_provider == 'groq':
            groq_key = config.get('groq_api_key')
            if not groq_key:
                logger.warning("⚠️ groq_api_key not found, falling back to OpenAI")
                stt_provider = 'openai'
            else:
                stt_service = STTService(
                    api_key=groq_key,
                    base_url="https://api.groq.com/openai/v1",
                    model="whisper-large-v3",
                    provider='groq'
                )
        
        if stt_provider == 'openai':
            openai_key = config.get('openai_api_key')
            openai_url = config.get('openai_base_url', 'https://api.openai.com/v1')
            stt_service = STTService(
                api_key=openai_key,
                base_url=openai_url,
                model="whisper-1",
                provider='openai'
            )
        
        logger.info(f"✅ STT Service reloaded: {stt_provider}")
        
        # ============================================================
        # STEP 6: Reload Music Service
        # ============================================================
        enable_music = safe_bool(config.get('enable_music_playback', True))
        music_url = config.get('music_service_url', 'http://music.sfdp.net')
        
        if enable_music:
            music_service = MusicService(music_url)
            logger.info(f"✅ Music Service reloaded: {music_url}")
        else:
            music_service = None
            logger.info("⚠️ Music Service disabled")
        
        # ============================================================
        # STEP 7: Update WebSocket Handler (for NEW connections)
        # ============================================================
        if ws_handler:
            ws_handler.ai_service = ai_service
            ws_handler.tts_service = tts_service
            ws_handler.stt_service = stt_service
            ws_handler.music_service = music_service
            logger.info("✅ WebSocket handler updated")
            
            # ✅ Notify all active connections
            notification = {
                "type": "system",
                "message": "⚠️ Services reloaded. Please refresh if you experience issues.",
                "timestamp": time.time()
            }
            
            disconnected = []
            for device_id, ws in list(ws_handler.active_connections.items()):
                try:
                    await ws.send_json(notification)
                    logger.info(f"📢 Notified {device_id} about reload")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to notify {device_id}: {e}")
                    disconnected.append(device_id)
            
            # Clean up disconnected clients
            for device_id in disconnected:
                ws_handler.active_connections.pop(device_id, None)
        
        logger.info("=" * 80)
        logger.info("✅ ALL SERVICES RELOADED SUCCESSFULLY")
        logger.info(f"   AI: {ai_provider} ({model})")
        logger.info(f"   TTS: {tts_provider}")
        logger.info(f"   STT: {stt_provider}")
        logger.info(f"   Music: {'enabled' if music_service else 'disabled'}")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Service reload failed: {e}", exc_info=True)
        raise
# ==============================================================================
# Lifespan Context Manager
# ==============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for application startup and shutdown"""
    global config_manager, device_manager, ota_manager, ai_service, tts_service, stt_service, ws_handler, conversation_logger, music_service
    
    logger.info("=" * 80)
    logger.info("🚀 SCHOOL CHATBOT WEBSOCKET SERVER")
    logger.info("=" * 80)
    
    try:
        # ============================================================
        # STEP 1: Initialize Config Manager & Load from MySQL
        # ============================================================
        MYSQL_URL = os.getenv('MYSQL_URL')
        if not MYSQL_URL:
            raise Exception("❌ MYSQL_URL not set in environment!")
        
        logger.info("🔐 Initializing Config Manager...")
        config_manager = ConfigManager(MYSQL_URL)
        await config_manager.connect()
        
        # Load all configuration from MySQL
        config = await config_manager.load_config()
        logger.info(f"✅ Loaded {len(config)} config items from MySQL")
        
        # ============================================================
        # STEP 2: Initialize Device Manager
        # ============================================================
        logger.info("📱 Initializing Device Manager...")
        device_manager = DeviceManager()
        
        # ============================================================
        # STEP 3: Initialize OTA Manager
        # ============================================================
        logger.info("📦 Initializing OTA Manager...")
        ota_manager = OTAManager()
        
        # ============================================================
        # STEP 4: Initialize Music Service
        # ============================================================
        # ✅ FIXED: Handle both string and boolean
        enable_music = safe_bool(config.get('enable_music_playback', True))
        music_url = config.get('music_service_url', 'http://music.sfdp.net')

        if enable_music:
            try:
                logger.info("🎵 Initializing Music Service...")
                music_service = MusicService(music_url)
                logger.info(f"✅ Music Service ready: {music_url}")
            except Exception as e:
                logger.warning(f"⚠️ Music Service disabled: {e}")
                music_service = None
        else:
            logger.info("⚠️ Music playback disabled in config")
            music_service = None

        
        # ============================================================
        # STEP 5: Initialize AI Service
        # ============================================================
        ai_provider = config.get('ai_provider', 'azure').lower()
        logger.info(f"🤖 Initializing AI Service (provider: {ai_provider})...")
        
        # Get provider-specific config
        if ai_provider == 'azure':
            api_key = config.get('azure_api_key')
            base_url = config.get('azure_endpoint')
            model = config.get('ai_model') or config.get('azure_deployment')
            azure_api_version = config.get('azure_api_version', '2024-12-01-preview')
            
            if not api_key:
                raise Exception("❌ azure_api_key not found in config!")
            if not base_url:
                raise Exception("❌ azure_endpoint not found in config!")
                
        elif ai_provider == 'deepseek':
            api_key = config.get('deepseek_api_key')
            base_url = config.get('deepseek_base_url', 'https://api.deepseek.com/v1')
            model = config.get('ai_model', 'deepseek-chat')
            azure_api_version = None
            
            if not api_key:
                raise Exception("❌ deepseek_api_key not found in config!")
                
        else:  # openai
            api_key = config.get('openai_api_key')
            base_url = config.get('openai_base_url', 'https://api.openai.com/v1')
            model = config.get('ai_model', 'gpt-4')
            azure_api_version = None
            
            if not api_key:
                raise Exception("❌ openai_api_key not found in config!")
        
        # Get system prompt (use default if not in config)
        system_prompt = config.get('system_prompt', FINAL_SYSTEM_PROMPT)
        
        ai_service = AIService(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_prompt=system_prompt,
            temperature=float(config.get('temperature', 0.7)),
            max_tokens=int(config.get('max_tokens', 500)),
            max_context=int(config.get('max_context', 10)),
            provider=ai_provider,
            azure_api_version=azure_api_version
        )
        
        logger.info(f"✅ AI Service initialized: {model}")
        
        # ============================================================
        # STEP 6: Initialize TTS Service
        # ============================================================
        tts_provider = config.get('tts_provider', 'azure_speech').lower()
        logger.info(f"🔊 Initializing TTS Service (provider: {tts_provider})...")
        
        if tts_provider == 'azure_speech':
            azure_speech_key = config.get('azure_speech_key')
            azure_speech_region = config.get('azure_speech_region', 'eastus')
            
            if not azure_speech_key:
                logger.warning("⚠️ azure_speech_key not found, falling back to Piper")
                tts_provider = 'piper'
            else:
                logger.info("🔊 Using Azure Speech REST API")
                tts_service = TTSService(
                    provider='azure_speech',
                    api_key=azure_speech_key,
                    region=azure_speech_region,
                    base_url=None
                )
        
        if tts_provider == 'piper':
            piper_host = config.get('piper_host', 'addon_core_piper')
            piper_port = int(config.get('piper_port', 10200))
            logger.info(f"🔊 Using Piper TTS: {piper_host}:{piper_port}")
            tts_service = TTSService(
                provider='piper',
                piper_host=piper_host,
                piper_port=piper_port
            )
        
        elif tts_provider == 'openai':
            openai_key = config.get('openai_api_key')
            openai_url = config.get('openai_base_url', 'https://api.openai.com/v1')
            
            if not openai_key:
                raise Exception("❌ openai_api_key not found for TTS!")
            
            logger.info("🔊 Using OpenAI TTS")
            tts_service = TTSService(
                provider='openai',
                api_key=openai_key,
                base_url=openai_url
            )
        
        logger.info(f"✅ TTS Service initialized: {tts_provider}")
        
        # ============================================================
        # STEP 7: Initialize STT Service
        # ============================================================
        stt_provider = config.get('stt_provider', 'azure_speech').lower()
        logger.info(f"🎤 Initializing STT Service (provider: {stt_provider})...")

        if stt_provider == 'azure_speech':
            azure_speech_key = config.get('azure_speech_key')
            
            if not azure_speech_key:
                logger.warning("⚠️ azure_speech_key not found, falling back to Groq")
                stt_provider = 'groq'
            else:
                logger.info("🎤 Using Azure Speech STT")
                # ✅ FIXED: Don't pass region - service gets it from config!
                stt_service = STTService(
                    api_key=azure_speech_key,
                    model="whisper-1",
                    provider='azure_speech'
                )

        if stt_provider == 'groq':
            groq_key = config.get('groq_api_key')
            
            if not groq_key:
                logger.warning("⚠️ groq_api_key not found, falling back to OpenAI")
                stt_provider = 'openai'
            else:
                logger.info("🎤 Using Groq STT (Whisper)")
                stt_service = STTService(
                    api_key=groq_key,
                    base_url="https://api.groq.com/openai/v1",
                    model="whisper-large-v3",
                    provider='groq'
                )

        if stt_provider == 'openai':
            openai_key = config.get('openai_api_key')
            openai_url = config.get('openai_base_url', 'https://api.openai.com/v1')
            
            if not openai_key:
                raise Exception("❌ openai_api_key not found for STT!")
            
            logger.info("🎤 Using OpenAI STT (Whisper)")
            stt_service = STTService(
                api_key=openai_key,
                base_url=openai_url,
                model="whisper-1",
                provider='openai'
            )

        logger.info(f"✅ STT Service initialized: {stt_provider}")

        
        # ============================================================
        # STEP 8: Initialize Conversation Logger
        # ============================================================
        try:
            logger.info("💾 Initializing Conversation Logger...")
            conversation_logger = ConversationLogger(MYSQL_URL)
            await conversation_logger.connect()
            logger.info("✅ Conversation Logger ready")
        except Exception as e:
            logger.warning(f"⚠️ MySQL logger disabled: {e}")
            conversation_logger = None
        
        # ============================================================
        # STEP 9: Initialize WebSocket Handler
        # ============================================================
        logger.info("🔌 Initializing WebSocket Handler...")
        ws_handler = WebSocketHandler(
            device_manager=device_manager,
            ota_manager=ota_manager,
            ai_service=ai_service,
            tts_service=tts_service,
            stt_service=stt_service,
            conversation_logger=conversation_logger,
            music_service=music_service
        )
        
        # ============================================================
        # STARTUP COMPLETE
        # ============================================================
        logger.info("=" * 80)
        logger.info("✅ ALL SERVICES INITIALIZED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"🌐 Server listening on: {os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', 5000)}")
        logger.info(f"📡 WebSocket endpoint: ws://{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', 5000)}/ws")
        logger.info(f"🌍 Web interface: http://{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', 5000)}/")
        logger.info(f"🤖 AI Provider: {ai_provider} ({model})")
        logger.info(f"🔊 TTS Provider: {tts_provider}")
        logger.info(f"🎤 STT Provider: {stt_provider}")
        if music_service:
            logger.info(f"🎵 Music Service: {music_url}")
        logger.info("=" * 80)
        
        yield
        
    except Exception as e:
        logger.error(f"❌ STARTUP FAILED: {e}", exc_info=True)
        raise
    
    finally:
        logger.info("🛑 Shutting down services...")
        
        if music_service:
            try:
                await music_service.close()
                logger.info("🎵 Music Service closed")
            except Exception as e:
                logger.error(f"❌ Music Service close error: {e}")
        
        if conversation_logger:
            try:
                await conversation_logger.close()
                logger.info("💾 MySQL connection closed")
            except Exception as e:
                logger.error(f"❌ MySQL close error: {e}")
        
        if config_manager:
            try:
                await config_manager.close()
                logger.info("🔐 Config Manager closed")
            except Exception as e:
                logger.error(f"❌ Config Manager close error: {e}")
        
        logger.info("✅ Shutdown complete")

# ==============================================================================
# FastAPI Application
# ==============================================================================

app = FastAPI(
    title="School Chatbot WebSocket Server",
    description="WebSocket server for ESP32-based school chatbot with music playback and Azure AI",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files
if os.path.exists('/app/static'):
    app.mount("/static", StaticFiles(directory="/app/static"), name="static")
    logger.info("📁 Static files mounted at /static")


# ==============================================================================
# HTTP Endpoints
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web interface"""
    index_path = "/app/static/index.html"
    
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(
            content="""
            <html>
                <head><title>School Chatbot Server</title></head>
                <body style="font-family: Arial; padding: 50px; text-align: center;">
                    <h1>🤖 School Chatbot WebSocket Server</h1>
                    <p>WebSocket endpoint: <code>ws://&lt;host&gt;:5000/ws</code></p>
                    <p>Status: <strong style="color: green;">Running ✅</strong></p>
                    <hr>
                    <p><em>Web interface not available (index.html not found)</em></p>
                </body>
            </html>
            """
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Get device count safely
    device_count = 0
    if device_manager and hasattr(device_manager, 'get_device_count'):
        device_count = device_manager.get_device_count()
    elif device_manager and hasattr(device_manager, 'devices'):
        device_count = len(device_manager.devices)
    
    # Get active connections count safely
    active_connections = 0
    if ws_handler and hasattr(ws_handler, 'get_active_connections_count'):
        active_connections = ws_handler.get_active_connections_count()
    elif ws_handler and hasattr(ws_handler, 'active_connections'):
        active_connections = len(ws_handler.active_connections)
    
    return JSONResponse({
        "status": "healthy",
        "services": {
            "ai": ai_service is not None,
            "tts": tts_service is not None,
            "stt": stt_service is not None,
            "device_manager": device_manager is not None,
            "ota_manager": ota_manager is not None,
            "websocket_handler": ws_handler is not None,
            "conversation_logger": conversation_logger is not None,
            "music_service": music_service is not None  # ✅ ADD THIS
        },
        "devices": device_count,
        "active_connections": active_connections
    })


@app.get("/api/mysql/status")
async def mysql_status():
    """
    ✅ CHECK MYSQL LOGGING STATUS
    Endpoint để monitor MySQL logging health
    """
    if not conversation_logger:
        return JSONResponse({
            "status": "disabled",
            "message": "MySQL logging not configured",
            "help": "Set MYSQL_URL in Home Assistant config"
        })
    
    try:
        # Get stats
        stats = conversation_logger.get_stats()
        
        # Test connection
        pool_info = {
            "available": False,
            "size": 0,
            "freesize": 0,
            "maxsize": 0
        }
        
        if conversation_logger.pool:
            try:
                # Quick connection test
                async with asyncio.timeout(3):
                    async with conversation_logger.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute("SELECT 1")
                            await cursor.fetchone()
                
                pool_info = {
                    "available": True,
                    "size": conversation_logger.pool.size,
                    "freesize": conversation_logger.pool.freesize,
                    "maxsize": conversation_logger.pool.maxsize
                }
            except Exception as e:
                logger.error(f"MySQL status check failed: {e}")
        
        return JSONResponse({
            "status": stats.get('health', 'unknown'),
            "pool": pool_info,
            "stats": {
                "total_attempts": stats.get('total_attempts', 0),
                "successful_logs": stats.get('successful_logs', 0),
                "failed_logs": stats.get('failed_logs', 0),
                "success_rate": f"{stats.get('success_rate', 0):.1f}%",
                "consecutive_failures": stats.get('consecutive_failures', 0)
            },
            "last_success": stats.get('last_success'),
            "last_error": stats.get('last_error'),
            "last_error_time": stats.get('last_error_time'),
            "recommendation": _get_recommendation(stats)
        })
    
    except Exception as e:
        logger.error(f"MySQL status endpoint error: {e}")
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


def _get_recommendation(stats: dict) -> str:
    """Get recommendation based on stats"""
    health = stats.get('health', 'unknown')
    failures = stats.get('consecutive_failures', 0)
    success_rate = stats.get('success_rate', 100)
    
    if health == 'disconnected':
        return "❌ MySQL disconnected. Check MySQL addon is running."
    
    if health == 'critical':
        return f"🚨 {failures} consecutive failures! MySQL may be down or overloaded."
    
    if health == 'degraded':
        return f"⚠️ {failures} recent failures. Monitor closely."
    
    if success_rate < 95:
        return f"⚠️ Low success rate ({success_rate:.1f}%). Check MySQL performance."
    
    return "✅ All systems operational."


@app.get("/status")
async def get_status():
    """Get detailed server status"""
    if not device_manager:
        return JSONResponse({"error": "Device manager not initialized"}, status_code=503)
    
    # Get statistics safely
    stats = {}
    if hasattr(device_manager, 'get_statistics'):
        stats = device_manager.get_statistics()
    elif hasattr(device_manager, 'devices'):
        stats = {
            "total_devices": len(device_manager.devices),
            "devices": list(device_manager.devices.keys())
        }
    
    # Get active connections
    active_connections = 0
    active_devices = []
    if ws_handler:
        if hasattr(ws_handler, 'get_active_connections_count'):
            active_connections = ws_handler.get_active_connections_count()
        elif hasattr(ws_handler, 'active_connections'):
            active_connections = len(ws_handler.active_connections)
        
        if hasattr(ws_handler, 'get_active_devices'):
            active_devices = ws_handler.get_active_devices()
        elif hasattr(ws_handler, 'active_connections'):
            active_devices = list(ws_handler.active_connections.keys())
    
    return JSONResponse({
        "server": {
            "version": "1.0.0",
            "ai_provider": AI_PROVIDER,
            "ai_model": AI_MODEL,
            "mysql_logging": conversation_logger is not None,
            "music_service": music_service is not None,  # ✅ ADD THIS
            "music_url": MUSIC_SERVICE_URL if music_service else None  # ✅ ADD THIS
        },
        "devices": stats,
        "active_connections": active_connections,
        "active_device_ids": active_devices
    })


@app.get("/api/conversations")
async def get_conversations(device_id: str = None, limit: int = 50):
    """Get conversation history from MySQL"""
    if not conversation_logger:
        return JSONResponse({
            "error": "Conversation logging not enabled"
        }, status_code=503)
    
    try:
        history = await conversation_logger.get_history(device_id, limit)
        return JSONResponse({
            "conversations": history,
            "count": len(history)
        })
    except Exception as e:
        logger.error(f"❌ Get conversations error: {e}")
        return JSONResponse({
            "error": str(e)
        }, status_code=500)


# ==============================================================================
# WebSocket Endpoint
# ==============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for device connections"""
    await ws_handler.handle_connection(websocket)

# ═══════════════════════════════════════════════════════════════════
# AUTHENTICATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.get("/login")
async def login_page():
    """Serve login page"""
    return FileResponse("static/login.html")

@app.post("/api/auth/login")
async def login(request: Request, response: Response):
    """Login endpoint"""
    try:
        data = await request.json()
        username = data.get('username', '')
        password = data.get('password', '')
        
        # ✅ ADD DEBUG LOGGING
        logger.info(f"🔐 Login attempt:")
        logger.info(f"   Username from form: '{username}'")
        logger.info(f"   Password length: {len(password)}")
        
        # Get admin credentials
        admin_creds = await get_admin_credentials()
        
        # ✅ ADD DEBUG LOGGING
        logger.info(f"🔐 Loaded credentials:")
        logger.info(f"   Expected username: '{admin_creds['username']}'")
        logger.info(f"   Expected hash: {admin_creds['password_hash'][:20]}...")
        
        # Hash the input password
        input_hash = hash_password(password)
        logger.info(f"   Input hash: {input_hash[:20]}...")
        logger.info(f"   Hashes match: {input_hash == admin_creds['password_hash']}")
        
        # Verify credentials
        if username == admin_creds['username'] and \
           verify_password(password, admin_creds['password_hash']):
            
            # Create session
            session_token = create_session(username)
            
            # Set cookie
            response = JSONResponse({'success': True, 'username': username})
            response.set_cookie(
                key='session_token',
                value=session_token,
                httponly=True,
                max_age=86400,  # 24 hours
                samesite='lax'
            )
            
            logger.info(f"✅ Admin login successful: {username}")
            return response
        else:
            logger.warning(f"⚠️ Failed login attempt: {username}")
            logger.warning(f"   Username match: {username == admin_creds['username']}")
            logger.warning(f"   Password match: {verify_password(password, admin_creds['password_hash'])}")
            raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    """Logout endpoint"""
    session_token = request.cookies.get('session_token')
    if session_token:
        delete_session(session_token)
    
    response = JSONResponse({'success': True})
    response.delete_cookie('session_token')
    return response

@app.get("/api/auth/check")
async def check_auth(user: dict = Depends(get_current_user)):
    """Check if user is authenticated"""
    return {'authenticated': True, 'username': user['username']}

# ═══════════════════════════════════════════════════════════════════
# PROTECTED ADMIN ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@app.get("/admin")
async def admin_page(request: Request):
    """Serve admin configuration page (protected)"""
    # Check if authenticated
    session_token = request.cookies.get('session_token')
    if not session_token or not get_session(session_token):
        return RedirectResponse(url='/login')
    
    return FileResponse("static/admin.html")

@app.get("/api/config")
async def get_all_config(user: dict = Depends(get_current_user)):
    """Get all configuration (protected)"""
    try:
        async with conversation_logger.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT id, config_key, config_value, category, 
                           description, is_secret, updated_at
                    FROM chatbot_config
                    ORDER BY category, config_key
                """)
                rows = await cursor.fetchall()
                
                # Convert to dict
                result = {}
                for row in rows:
                    key = row['config_key']
                    result[key] = {
                        'config_value': row['config_value'],
                        'category': row['category'],
                        'description': row['description'],
                        'is_secret': row['is_secret'],
                        'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
                    }
                
                return result
    except Exception as e:
        logger.error(f"❌ Get config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/config/{key}")
async def update_config(key: str, data: dict, user: dict = Depends(get_current_user)):
    """Update a configuration value (protected)"""
    try:
        value = data.get('value', '')
        
        # ✅ TRIM whitespace for API keys
        if 'api_key' in key.lower() or 'password' in key.lower():
            value = value.strip()
        
        async with conversation_logger.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    UPDATE chatbot_config 
                    SET config_value = %s, updated_at = NOW()
                    WHERE config_key = %s
                """, (value, key))
                
                await conn.commit()
                
                if cursor.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Config key not found")
                
                logger.info(f"✅ Config updated by {user['username']}: {key} = {value[:20]}...")
                
                return {"success": True, "key": key, "value": value}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Update config error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@app.post("/api/reload")
async def reload_services_endpoint(user: dict = Depends(get_current_user)):
    """Reload all services with new configuration (protected)"""
    try:
        await reload_services()
        
        logger.info(f"✅ Services reloaded by {user['username']}")
        
        return JSONResponse({
            "success": True,
            "message": "Services reloaded successfully",
            "services": {
                "ai": ai_service is not None,
                "tts": tts_service is not None,
                "stt": stt_service is not None,
                "music": music_service is not None
            }
        })
    except Exception as e:
        logger.error(f"❌ Reload endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==============================================================================
# Main Entry Point
# ==============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("🚀 Starting Uvicorn server...")
    
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level=LOG_LEVEL.lower(),
        access_log=True
    )
