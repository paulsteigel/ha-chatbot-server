import logging
import base64
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class STTService:
    """Speech-to-Text service using OpenAI Whisper"""
    
    def __init__(self, api_key, base_url):
        """Initialize STT service"""
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
        logger.info("🎤 STT Service initialized")
    
    async def initialize(self):
        """Initialize service"""
        logger.info("✅ STT Service ready")
    
    async def transcribe(self, audio_base64, language='vi'):
        """Transcribe audio to text"""
        try:
            # Decode base64 audio
            audio_data = base64.b64decode(audio_base64)
            
            # Create temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            # Transcribe
            with open(temp_path, 'rb') as audio_file:
                transcript = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language if language == 'vi' else 'en'
                )
            
            # Cleanup
            import os
            os.unlink(temp_path)
            
            text = transcript.text
            logger.info(f"🎤 Transcribed: {text}")
            return text
            
        except Exception as e:
            logger.error(f"❌ STT Error: {e}")
            return ""
