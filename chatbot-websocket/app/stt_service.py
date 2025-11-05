"""
Speech-to-Text Service using OpenAI Whisper API
Supports audio transcription from various formats
"""
import logging
import base64
import tempfile
import os
from typing import Optional
from openai import AsyncOpenAI
import httpx


class STTService:
    """Speech-to-Text service using OpenAI Whisper API"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        """
        Initialize STT service
        
        Args:
            api_key: API key for OpenAI or compatible service
            base_url: Base URL for API (default: OpenAI)
        """
        self.logger = logging.getLogger('STTService')
        self.api_key = api_key
        self.base_url = base_url
        self.client = None
        
        self.logger.info("🎤 Initializing STT Service...")
        self.logger.info(f"   Base URL: {base_url}")
    
    async def initialize(self):
        """Initialize the STT client"""
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
            
            self.logger.info("✅ STT Service initialized")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize STT: {e}")
            raise
    
    async def transcribe(self, audio_data: bytes, language: str = 'vi', 
                        audio_format: str = 'wav') -> Optional[str]:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Raw audio bytes (NOT base64 encoded)
            language: Language code ('vi' or 'en')
            audio_format: Audio format (wav, mp3, webm, etc.)
        
        Returns:
            Transcribed text or None if failed
        """
        if not self.client:
            self.logger.error("❌ STT client not initialized")
            return None
        
        temp_path = None
        
        try:
            # Detect if audio_data is base64 encoded (for backward compatibility)
            if isinstance(audio_data, str):
                self.logger.warning("⚠️ Received base64 string, decoding...")
                audio_data = base64.b64decode(audio_data)
            
            self.logger.info(f"🎤 Transcribing audio: {len(audio_data)} bytes, format: {audio_format}")
            
            # Create temporary file with appropriate extension
            suffix = f'.{audio_format}' if not audio_format.startswith('.') else audio_format
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            self.logger.info(f"   Temp file: {temp_path}")
            
            # Transcribe using Whisper API
            with open(temp_path, 'rb') as audio_file:
                transcript = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language if language in ['vi', 'en'] else None,
                    response_format="text"
                )
            
            # Get transcribed text
            if isinstance(transcript, str):
                text = transcript
            else:
                text = transcript.text if hasattr(transcript, 'text') else str(transcript)
            
            text = text.strip()
            
            if text:
                self.logger.info(f"✅ Transcribed: {text}")
                return text
            else:
                self.logger.warning("⚠️ Empty transcription result")
                return None
            
        except Exception as e:
            self.logger.error(f"❌ STT Error: {e}", exc_info=True)
            return None
            
        finally:
            # Cleanup temporary file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    self.logger.debug(f"🗑️ Deleted temp file: {temp_path}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to delete temp file: {e}")
    
    async def test(self):
        """Test STT service"""
        self.logger.info("🧪 Testing STT service...")
        
        # Create a simple test audio (silence)
        test_audio = b'\x00' * 16000  # 1 second of silence at 16kHz
        
        result = await self.transcribe(test_audio, 'vi', 'wav')
        
        if result is not None:
            self.logger.info(f"✅ STT test completed (result: '{result}')")
        else:
            self.logger.warning("⚠️ STT test returned None (this is expected for silence)")
