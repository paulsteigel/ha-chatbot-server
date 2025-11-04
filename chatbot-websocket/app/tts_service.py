"""
Speech-to-Text Service using OpenAI Whisper API
Compatible with DeepSeek API
"""
import logging
from typing import Optional
from openai import AsyncOpenAI
import httpx

class STTService:
    """Speech-to-Text Service"""
    
    def __init__(self, api_key: str, base_url: str):
        self.logger = logging.getLogger('STTService')
        self.api_key = api_key
        self.base_url = base_url
        self.client = None
        
        self.logger.info(f"🎤 Initializing STT Service...")
        self.logger.info(f"   Base URL: {base_url}")
    
    async def initialize(self):
        """Initialize the STT service"""
        try:
            # Create httpx client with proper timeout
            http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
            
            # Initialize OpenAI client with custom http_client
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                http_client=http_client,
                max_retries=2
            )
            
            self.logger.info("✅ STT Service initialized")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize STT: {e}")
            raise
    
    async def transcribe(self, audio_data: bytes, language: str = None) -> Optional[str]:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Audio bytes (WAV format)
            language: Language code (optional, auto-detect if None)
        
        Returns:
            Transcribed text or None if failed
        """
        try:
            if not self.client:
                self.logger.error("❌ STT client not initialized")
                return None
            
            self.logger.info(f"🎤 Transcribing audio ({len(audio_data)} bytes)...")
            
            # Create file-like object
            audio_file = ("audio.wav", audio_data, "audio/wav")
            
            # Call Whisper API
            params = {
                "model": "whisper-1",
                "file": audio_file,
                "response_format": "text"
            }
            
            if language:
                params["language"] = language
            
            response = await self.client.audio.transcriptions.create(**params)
            
            # Get text
            text = response if isinstance(response, str) else response.text
            
            self.logger.info(f"✅ Transcribed: {text}")
            return text
            
        except Exception as e:
            self.logger.error(f"❌ STT transcription error: {e}", exc_info=True)
            return None
    
    async def test(self):
        """Test STT service"""
        self.logger.info("🧪 Testing STT service...")
        # Add test code if needed
