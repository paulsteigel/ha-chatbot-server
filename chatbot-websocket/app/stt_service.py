import logging
import numpy as np
import io
import wave
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class STTService:
    def __init__(self, api_key, base_url=None):
        """Initialize OpenAI Whisper API"""
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url if base_url else None
        )
        logger.info("🎤 Using OpenAI Whisper API for STT")
        
    async def initialize(self):
        """No model to load - using API"""
        logger.info("✅ STT service ready (API mode)")
    
    async def transcribe(self, audio_data, sample_rate=16000):
        """
        Transcribe audio using OpenAI API
        Args:
            audio_data: numpy array (int16)
            sample_rate: sample rate
        Returns:
            str: transcribed text
        """
        try:
            # Convert to WAV format
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_data.tobytes())
            
            wav_buffer.seek(0)
            wav_buffer.name = "audio.wav"
            
            # Call API
            transcript = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=wav_buffer,
                language="vi"
            )
            
            text = transcript.text.strip()
            logger.info(f"📝 Transcribed: {text}")
            return text
            
        except Exception as e:
            logger.error(f"❌ STT API error: {e}")
            return ""
    
    async def close(self):
        """Cleanup"""
        await self.client.close()
