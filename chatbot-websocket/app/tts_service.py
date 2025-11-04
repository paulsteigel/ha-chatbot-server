import logging
import base64
import edge_tts

logger = logging.getLogger(__name__)

class TTSService:
    """Text-to-Speech service using Edge TTS"""
    
    def __init__(self, voice_vi, voice_en):
        """Initialize TTS service"""
        self.voice_vi = voice_vi
        self.voice_en = voice_en
        logger.info(f"🔊 TTS Service initialized (VI: {voice_vi}, EN: {voice_en})")
    
    async def initialize(self):
        """Initialize service"""
        logger.info("✅ TTS Service ready")
    
    async def synthesize(self, text, language='vi'):
        """Convert text to speech"""
        try:
            voice = self.voice_vi if language == 'vi' else self.voice_en
            
            # Create temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Generate speech
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(temp_path)
            
            # Read and encode
            with open(temp_path, 'rb') as audio_file:
                audio_data = audio_file.read()
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # Cleanup
            import os
            os.unlink(temp_path)
            
            logger.info(f"🔊 Synthesized: {text[:50]}...")
            return audio_base64
            
        except Exception as e:
            logger.error(f"❌ TTS Error: {e}")
            return ""
