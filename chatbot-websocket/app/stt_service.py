import asyncio
import logging
import os
import whisper
import numpy as np
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class STTService:
    def __init__(self):
        model_name = os.getenv('STT_MODEL', 'base')
        logger.info(f"🎤 Loading Whisper model: {model_name}")
        self.model = whisper.load_model(model_name)
        self.executor = ThreadPoolExecutor(max_workers=2)
        logger.info("✅ Whisper model loaded")
        
    async def transcribe(self, audio_np: np.ndarray, sample_rate: int = 16000) -> str:
        """
        Transcribe audio using Whisper
        Args:
            audio_np: numpy array of int16 PCM samples
            sample_rate: sample rate (should be 16000)
        Returns:
            Transcribed text
        """
        try:
            # Convert to float32 and normalize
            audio_float = audio_np.astype(np.float32) / 32768.0
            
            # Whisper expects 16kHz
            if sample_rate != 16000:
                logger.warning(f"Sample rate {sample_rate} != 16000, resampling needed")
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._transcribe_sync,
                audio_float
            )
            
            text = result['text'].strip()
            
            # Detect language
            lang = result.get('language', 'unknown')
            logger.info(f"📝 Transcribed ({lang}): {text}")
            
            return text
            
        except Exception as e:
            logger.error(f"STT error: {e}")
            return ""
    
    def _transcribe_sync(self, audio_float):
        """Synchronous transcription"""
        return self.model.transcribe(
            audio_float,
            language=None,  # Auto-detect
            task='transcribe',
            fp16=False,
            verbose=False
        )
