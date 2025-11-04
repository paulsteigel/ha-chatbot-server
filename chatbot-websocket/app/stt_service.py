import logging
import whisper
import numpy as np
import io
import soundfile as sf

logger = logging.getLogger(__name__)

class STTService:
    def __init__(self, model_name="base"):
        """Initialize Whisper STT"""
        self.model_name = model_name
        self.model = None
        logger.info(f"🎤 Initializing Whisper STT with model: {model_name}")
        
    async def initialize(self):
        """Load Whisper model"""
        try:
            self.model = whisper.load_model(self.model_name)
            logger.info(f"✅ Whisper model '{self.model_name}' loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load Whisper model: {e}")
            raise
    
    async def transcribe(self, audio_data, sample_rate=16000):
        """
        Transcribe audio to text
        Args:
            audio_data: numpy array of audio samples (int16)
            sample_rate: sample rate (default 16000)
        Returns:
            str: transcribed text
        """
        try:
            # Convert to float32 [-1, 1]
            if audio_data.dtype == np.int16:
                audio_float = audio_data.astype(np.float32) / 32768.0
            else:
                audio_float = audio_data
            
            # Transcribe
            result = self.model.transcribe(
                audio_float,
                language="vi",
                task="transcribe",
                fp16=False
            )
            
            text = result["text"].strip()
            logger.info(f"📝 Transcribed: {text}")
            return text
            
        except Exception as e:
            logger.error(f"❌ Transcription error: {e}", exc_info=True)
            return ""
