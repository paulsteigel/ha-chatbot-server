import asyncio
import logging
import os
import edge_tts
from io import BytesIO

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        self.voice_vi = os.getenv('TTS_VOICE_VI', 'vi-VN-HoaiMyNeural')
        self.voice_en = os.getenv('TTS_VOICE_EN', 'en-US-AriaNeural')
        logger.info(f"🔊 TTS initialized: VI={self.voice_vi}, EN={self.voice_en}")
        
    async def synthesize(self, text: str, language: str = 'auto') -> list:
        """
        Synthesize text to speech
        Args:
            text: Text to synthesize
            language: 'vi', 'en', or 'auto'
        Returns:
            List of PCM audio chunks (16kHz, mono, 16-bit)
        """
        try:
            # Auto-detect language
            if language == 'auto':
                language = self._detect_language(text)
            
            voice = self.voice_vi if language == 'vi' else self.voice_en
            
            logger.info(f"🔊 Synthesizing ({language}): {text[:50]}...")
            
            # Use Edge TTS
            communicate = edge_tts.Communicate(text, voice)
            
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    # Edge TTS returns MP3, need to convert to PCM
                    pcm_chunk = await self._mp3_to_pcm(chunk["data"])
                    audio_chunks.append(pcm_chunk)
            
            logger.info(f"✅ TTS generated {len(audio_chunks)} chunks")
            return audio_chunks
            
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return []
    
    def _detect_language(self, text: str) -> str:
        """Simple language detection"""
        vietnamese_chars = set('àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ')
        
        text_lower = text.lower()
        has_vietnamese = any(char in vietnamese_chars for char in text_lower)
        
        return 'vi' if has_vietnamese else 'en'
    
    async def _mp3_to_pcm(self, mp3_data: bytes) -> bytes:
        """Convert MP3 to PCM 16kHz mono 16-bit"""
        try:
            from pydub import AudioSegment
            
            audio = AudioSegment.from_mp3(BytesIO(mp3_data))
            audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            
            return audio.raw_data
            
        except Exception as e:
            logger.error(f"MP3 to PCM conversion error: {e}")
            return b''
