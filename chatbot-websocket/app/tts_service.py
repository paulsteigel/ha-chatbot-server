# File: app/tts_service.py
"""
TTS Service - Multi-provider with Wyoming protocol support
Compatible with dict-based config
"""
import logging
import base64
import os
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class TTSService:
    """Text-to-Speech service with multi-provider support."""
    
    def __init__(self):
        """Initialize TTS service."""
        # Read TTS provider from environment (not in config dict)
        self.provider = os.getenv("TTS_PROVIDER", "openai")
        
        # OpenAI config
        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        
        self.openai_client = AsyncOpenAI(
            api_key=openai_api_key,
            base_url=openai_base_url
        )
        
        # TTS voices - Try to import from config, fallback to env
        try:
            from app.config import TTS_CONFIG
            self.tts_voice_vi = TTS_CONFIG.get("vietnamese_voice", "nova")
            self.tts_voice_en = TTS_CONFIG.get("english_voice", "alloy")
        except:
            self.tts_voice_vi = os.getenv("TTS_VOICE_VI", "nova")
            self.tts_voice_en = os.getenv("TTS_VOICE_EN", "alloy")
        
        # Piper voices (from env only, not in config)
        self.piper_voice_vi = os.getenv("PIPER_VOICE_VI", "vi_VN-vais-medium")
        self.piper_voice_en = os.getenv("PIPER_VOICE_EN", "en_US-lessac-medium")
        
        # Wyoming client for Piper (lazy init)
        self.wyoming_client = None
        self.piper_hosts = [
            "addon_core_piper",
            "core-piper", 
            "172.30.33.6",
        ]
        
        logger.info(f"🔊 TTS Service initialized")
        logger.info(f"   Provider: {self.provider}")
        logger.info(f"   OpenAI voices: VI={self.tts_voice_vi}, EN={self.tts_voice_en}")
        if self.provider == "piper":
            logger.info(f"   Piper voices: VI={self.piper_voice_vi}, EN={self.piper_voice_en}")
    
    async def _init_wyoming_client(self):
        """Initialize Wyoming client (lazy load)."""
        if self.wyoming_client:
            return
        
        # Import here to avoid circular import
        from app.wyoming_client import WyomingTTSClient
        
        logger.info(f"🔍 Searching for Piper addon...")
        
        for host in self.piper_hosts:
            try:
                logger.debug(f"   Trying {host}...")
                client = WyomingTTSClient(host=host, port=10200)
                if await client.test_connection():
                    self.wyoming_client = client
                    logger.info(f"   ✅ Connected to Piper: {host}:10200")
                    return
            except Exception as e:
                logger.debug(f"   ❌ {host}: {e}")
                continue
        
        raise Exception("❌ Cannot connect to Piper on any known host")
    
    async def synthesize(self, text: str, language: str = "vi") -> str:
        """
        Convert text to speech audio.
        
        Args:
            text: Text to synthesize
            language: "vi" or "en"
            
        Returns:
            Base64 encoded audio (MP3/WAV)
        """
        try:
            if self.provider == "piper":
                return await self._synthesize_piper(text, language)
            else:
                return await self._synthesize_openai(text, language)
                
        except Exception as e:
            logger.error(f"❌ TTS error with {self.provider}: {e}")
            
            # Fallback to OpenAI if Piper fails
            if self.provider == "piper":
                logger.info("🔄 Falling back to OpenAI TTS...")
                try:
                    return await self._synthesize_openai(text, language)
                except Exception as e2:
                    logger.error(f"❌ OpenAI fallback failed: {e2}")
            
            return ""
    
    async def _synthesize_openai(self, text: str, language: str) -> str:
        """Synthesize using OpenAI TTS."""
        try:
            voice = self.tts_voice_vi if language == "vi" else self.tts_voice_en
            
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
            
            voice = self.piper_voice_vi if language == "vi" else self.piper_voice_en
            
            logger.info(f"🔊 Piper TTS: voice={voice}, text='{text[:50]}...'")
            
            # Call Piper via Wyoming
            audio_bytes = await self.wyoming_client.synthesize(text, voice)
            
            # Convert to base64
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
            
            logger.info(f"✅ Piper TTS (Wyoming): {len(audio_bytes)} bytes (WAV)")
            return audio_base64
            
        except Exception as e:
            logger.error(f"❌ Piper TTS (Wyoming) error: {e}")
            raise
