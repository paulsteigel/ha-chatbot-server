# File: app/tts_service.py
"""
TTS Service - Multi-provider with Wyoming protocol support
Dynamically reads config from Home Assistant
"""
import logging
import base64
import os
import json
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

def get_config(key: str, default=None):
    """
    Get configuration from Home Assistant options.json or environment.
    Priority: HA options.json > Environment > Default
    """
    # Try Home Assistant options first
    options_file = "/data/options.json"
    if os.path.exists(options_file):
        try:
            with open(options_file, 'r') as f:
                options = json.load(f)
                if key in options:
                    value = options[key]
                    # Handle null/None/empty
                    if value not in [None, "", "null", "None"]:
                        return value
        except Exception:
            pass
    
    # Fallback to environment variable
    env_key = key.upper()
    env_value = os.getenv(env_key)
    if env_value not in [None, "", "null", "None"]:
        return env_value
    
    return default


class TTSService:
    """Text-to-Speech service with multi-provider support."""
    
    def __init__(self):
        """Initialize TTS service with dynamic config."""
        
        # ✅ BUILD FULL CONFIG DICT
        self.config = self._build_config()
        
        # ✅ READ TTS PROVIDER FROM CONFIG (DYNAMIC)
        self.provider = get_config("tts_provider", "openai")
        
        # ✅ READ API KEYS FROM CONFIG
        openai_api_key = get_config("openai_api_key", "")
        openai_base_url = get_config("openai_base_url", "https://api.openai.com/v1")
        
        # Initialize OpenAI client (for fallback even if using Piper)
        self.openai_client = None
        if openai_api_key:
            try:
                self.openai_client = AsyncOpenAI(
                    api_key=openai_api_key,
                    base_url=openai_base_url
                )
            except Exception as e:
                logger.warning(f"⚠️ OpenAI client init failed: {e}")
        
        # Wyoming client for Piper (lazy init)
        self.wyoming_client = None
        
        # ✅ LOG CONFIGURATION
        logger.info(f"🔊 TTS Service initialized")
        logger.info(f"   Provider: {self.provider}")
        if self.provider == "openai":
            tts_voice_vi = get_config("tts_voice_vi", "nova")
            tts_voice_en = get_config("tts_voice_en", "alloy")
            logger.info(f"   OpenAI voices: VI={tts_voice_vi}, EN={tts_voice_en}")
            if not self.openai_client:
                logger.error(f"   ❌ OpenAI client not initialized! Check OPENAI_API_KEY")
        elif self.provider == "piper":
            piper_voice_vi = get_config("piper_voice_vi", "vi_VN-vais1000-medium")
            piper_voice_en = get_config("piper_voice_en", "en_US-lessac-medium")
            logger.info(f"   Piper voices: VI={piper_voice_vi}, EN={piper_voice_en}")
            logger.info(f"   Will auto-fallback to OpenAI if Piper fails")
    
    def _build_config(self) -> dict:
        """Build full config dict for Wyoming client."""
        return {
            'tts': {
                'piper': {
                    'host': get_config('piper_host', '172.30.32.1'),
                    'port': get_config('piper_port', 10200)
                }
            },
            'piper_voice_vi': get_config('piper_voice_vi', 'vi_VN-vais1000-medium'),
            'piper_voice_en': get_config('piper_voice_en', 'en_US-lessac-medium')
        }
    
    async def _init_wyoming_client(self):
        """Initialize Wyoming client (lazy load)."""
        if self.wyoming_client:
            return
        
        from app.wyoming_client import WyomingTTSClient
        
        logger.info(f"🔍 Initializing Piper TTS (Wyoming)...")
        
        try:
            # ✅ PASS FULL CONFIG DICT
            self.wyoming_client = WyomingTTSClient(self.config)
            
            # ✅ TEST CONNECTION
            if await self.wyoming_client.test_connection():
                host = self.config['tts']['piper']['host']
                port = self.config['tts']['piper']['port']
                logger.info(f"   ✅ Connected to Piper: {host}:{port}")
            else:
                raise Exception("Connection test failed")
                
        except Exception as e:
            logger.error(f"   ❌ Piper connection error: {e}")
            raise Exception("❌ Cannot connect to Piper. Is Piper addon running?")
    
    async def synthesize(self, text: str, language: str = "vi") -> str:
        """
        Convert text to speech audio.
        
        Args:
            text: Text to synthesize
            language: "vi" or "en"
            
        Returns:
            Base64 encoded audio (MP3 for OpenAI, WAV for Piper)
        """
        # ✅ RE-READ PROVIDER FROM CONFIG (FOR RUNTIME CHANGES)
        current_provider = get_config("tts_provider", self.provider)
        
        if current_provider != self.provider:
            logger.info(f"🔄 TTS provider changed: {self.provider} → {current_provider}")
            self.provider = current_provider
            # Reset Wyoming client if switching away from Piper
            if current_provider != "piper":
                self.wyoming_client = None
        
        try:
            if self.provider == "piper":
                return await self._synthesize_piper(text, language)
            else:
                return await self._synthesize_openai(text, language)
                
        except Exception as e:
            logger.error(f"❌ TTS error with {self.provider}: {e}")
            
            # ✅ SMART FALLBACK
            if self.provider == "piper" and self.openai_client:
                logger.info("🔄 Falling back to OpenAI TTS...")
                try:
                    return await self._synthesize_openai(text, language)
                except Exception as e2:
                    logger.error(f"❌ OpenAI fallback failed: {e2}")
            
            return ""
    
    async def _synthesize_openai(self, text: str, language: str) -> str:
        """Synthesize using OpenAI TTS."""
        if not self.openai_client:
            raise Exception("OpenAI client not initialized. Check OPENAI_API_KEY")
        
        try:
            # ✅ RE-READ VOICES FROM CONFIG
            voice_vi = get_config("tts_voice_vi", "nova")
            voice_en = get_config("tts_voice_en", "alloy")
            voice = voice_vi if language == "vi" else voice_en
            
            logger.info(f"🔊 OpenAI TTS: voice={voice}, text='{text[:50]}...'")
            
            response = await self.openai_client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                response_format="mp3"
            )
            
            audio_bytes = response.content
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
            
            logger.info(f"✅ OpenAI TTS: {len(audio_bytes)} bytes (MP3)")
            return audio_base64
            
        except Exception as e:
            logger.error(f"❌ OpenAI TTS error: {e}")
            raise
    
    async def _synthesize_piper(self, text: str, language: str) -> str:
        """Synthesize using Piper via Wyoming protocol."""
        try:
            # Initialize Wyoming client if needed
            await self._init_wyoming_client()
            
            # ✅ CALL WITH LANGUAGE (wyoming_client tự chọn voice)
            audio_bytes = await self.wyoming_client.synthesize(text, language)
            
            # Convert to base64
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
            
            logger.info(f"✅ Piper TTS (Wyoming): {len(audio_bytes)} bytes (WAV)")
            return audio_base64
            
        except Exception as e:
            logger.error(f"❌ Piper TTS (Wyoming) error: {e}")
            raise
