import logging
import edge_tts
import io

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self, voice_vi="vi-VN-HoaiMyNeural", voice_en="en-US-AriaNeural"):
        """
        Initialize TTS service
        Args:
            voice_vi: Vietnamese voice
            voice_en: English voice
        """
        self.voice_vi = voice_vi
        self.voice_en = voice_en
        logger.info(f"🎵 TTS initialized: VI={voice_vi}, EN={voice_en}")
    
    async def initialize(self):
        """No initialization needed for edge-tts"""
        logger.info("✅ TTS service ready")
    
    async def synthesize(self, text, language="vi"):
        """
        Synthesize text to speech
        Args:
            text: Text to synthesize
            language: "vi" or "en"
        Returns:
            bytes: Audio data (MP3)
        """
        try:
            voice = self.voice_vi if language == "vi" else self.voice_en
            
            # Generate speech
            communicate = edge_tts.Communicate(text, voice)
            audio_buffer = io.BytesIO()
            
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])
            
            audio_data = audio_buffer.getvalue()
            logger.info(f"🔊 Synthesized {len(audio_data)} bytes for: {text[:50]}...")
            return audio_data
            
        except Exception as e:
            logger.error(f"❌ TTS error: {e}")
            return b""
    
    async def close(self):
        """Cleanup"""
        pass
