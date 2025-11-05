"""
Text-to-Speech Service using OpenAI TTS API
Supports multiple voices and languages
"""
import logging
import base64
from typing import Optional
from openai import AsyncOpenAI
import httpx


class TTSService:
    """Text-to-Speech service using OpenAI TTS API"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        """
        Initialize TTS service
        
        Args:
            api_key: API key for OpenAI or compatible service
            base_url: Base URL for API (default: OpenAI)
        """
        self.logger = logging.getLogger('TTSService')
        self.api_key = api_key
        self.base_url = base_url
        self.client = None
        
        # Voice configuration
        import os
        self.voice_vi = os.getenv('TTS_VOICE_VI', 'nova')
        self.voice_en = os.getenv('TTS_VOICE_EN', 'alloy')
        
        self.logger.info("🔊 Initializing TTS Service...")
        self.logger.info(f"   Base URL: {base_url}")
        self.logger.info(f"   Vietnamese Voice: {self.voice_vi}")
        self.logger.info(f"   English Voice: {self.voice_en}")
    
    async def initialize(self):
        """Initialize the TTS client"""
        try:
            # Create httpx client
            http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
            
            # Initialize OpenAI client
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                http_client=http_client,
                max_retries=2
            )
            
            self.logger.info("✅ TTS Service initialized")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize TTS: {e}")
            raise
    
    async def synthesize(self, text: str, language: str = 'auto') -> Optional[str]:
    """
    Synthesize text to speech
    
    Args:
        text: Text to synthesize
        language: Language code ('vi', 'en', or 'auto')
    
    Returns:
        Base64 encoded MP3 audio or None if failed
    """
    if not self.client:
        self.logger.error("❌ TTS client not initialized")
        return None
    
    try:
        # VALID OpenAI TTS voices
        VALID_VOICES = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer', 'ash', 'sage', 'coral']
        
        # Determine voice based on language
        if language == 'vi':
            voice = self.voice_vi
        elif language == 'en':
            voice = self.voice_en
        else:
            # Auto-detect: use Vietnamese for text with Vietnamese characters
            has_vietnamese = any(ord(c) > 127 for c in text)
            voice = self.voice_vi if has_vietnamese else self.voice_en
        
        # VALIDATE voice (fallback to 'nova' if invalid)
        if voice not in VALID_VOICES:
            self.logger.warning(f"⚠️ Invalid voice '{voice}', falling back to 'nova'")
            voice = 'nova'
        
        self.logger.info(f"🔊 Synthesizing: {text[:50]}... (Voice: {voice})")
        
        # Call TTS API
        response = await self.client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="mp3"
        )
        
        # Read audio content
        audio_bytes = response.content
        
        # Convert to base64
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        self.logger.info(f"✅ TTS generated: {len(audio_bytes)} bytes")
        
        return audio_base64
        
    except Exception as e:
        self.logger.error(f"❌ TTS Error: {e}", exc_info=True)
        return None

    
    async def test(self):
        """Test TTS service"""
        self.logger.info("🧪 Testing TTS service...")
        
        test_text = "Xin chào, đây là bài kiểm tra hệ thống."
        result = await self.synthesize(test_text, 'vi')
        
        if result:
            self.logger.info(f"✅ TTS test successful ({len(result)} chars base64)")
        else:
            self.logger.warning("⚠️ TTS test failed")
