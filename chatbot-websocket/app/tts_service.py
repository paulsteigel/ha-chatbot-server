# File: app/tts_service.py
"""
TTS Service - Multi-provider with Wyoming protocol support
"""
import logging
import base64
from openai import AsyncOpenAI
from app.config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    TTS_PROVIDER,
    TTS_VOICE_VI,
    TTS_VOICE_EN,
    PIPER_VOICE_VI,
    PIPER_VOICE_EN,
)
from app.wyoming_client import WyomingTTSClient

logger = logging.getLogger(__name__)

class TTSService:
    """Text-to-Speech service with multi-provider support."""
    
    def __init__(self):
        """Initialize TTS service."""
        self.provider = TTS_PROVIDER
        
        # OpenAI client
        self.openai_client = AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL
        )
        
        # Wyoming client for Piper
        # Try multiple hostnames
        piper_hosts = [
            "addon_core_piper",           # Official addon hostname
            "core-piper",                 # Container hostname
            "172.30.33.6",                # Direct IP (from your inspect)
        ]
        
        self.wyoming_client = None
        self.piper_host = piper_hosts[0]  # Default
        
        logger.info(f"🔊 TTS Service initialized")
        logger.info(f"   Provider: {self.provider}")
        logger.info(f"   OpenAI voices: VI={TTS_VOICE_VI}, EN={TTS_VOICE_EN}")
        logger.info(f"   Piper voices: VI={PIPER_VOICE_VI}, EN={PIPER_VOICE_EN}")
        logger.info(f"   Piper hosts to try: {piper_hosts}")
    
    async def _init_wyoming_client(self):
        """Initialize Wyoming client (lazy load)."""
        if self.wyoming_client:
            return
        
        # Auto-detect working Piper host
        piper_hosts = [
            "addon_core_piper",
            "core-piper",
            "172.30.33.6",
        ]
        
        for host in piper_hosts:
            try:
                client = WyomingTTSClient(host=host, port=10200)
                if await client.test_connection():
                    self.wyoming_client = client
                    self.piper_host = host
                    logger.info(f"✅ Connected to Piper: {host}:10200")
                    return
            except:
                continue
        
        raise Exception("Cannot connect to Piper on any known host")
    
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
            voice = TTS_VOICE_VI if language == "vi" else TTS_VOICE_EN
            
            logger.info(f"🔊 OpenAI TTS: voice={voice}")
            
            response = await self.openai_client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                response_format="mp3"
            )
            
            audio_bytes = response.content
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
            
            logger.info(f"✅ OpenAI TTS: {len(audio_bytes)} bytes")
            return audio_base64
            
        except Exception as e:
            logger.error(f"❌ OpenAI TTS error: {e}")
            raise
    
    async def _synthesize_piper(self, text: str, language: str) -> str:
        """Synthesize using Piper via Wyoming protocol."""
        try:
            # Initialize Wyoming client if needed
            await self._init_wyoming_client()
            
            voice = PIPER_VOICE_VI if language == "vi" else PIPER_VOICE_EN
            
            # Call Piper via Wyoming
            audio_bytes = await self.wyoming_client.synthesize(text, voice)
            
            # Convert to base64
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
            
            logger.info(f"✅ Piper TTS (Wyoming): {len(audio_bytes)} bytes")
            return audio_base64
            
        except Exception as e:
            logger.error(f"❌ Piper TTS (Wyoming) error: {e}")
            raise
