import asyncio
import logging
import os
import numpy as np
from faster_whisper import WhisperModel
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class STTService:
    def __init__(self):
        model_name = os.getenv('STT_MODEL', 'base')
        logger.info(f"🎤 Loading Faster-Whisper model: {model_name}")
        
        # Use faster-whisper (optimized C++ implementation)
        self.model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8"  # Faster on CPU
        )
        
        self.executor = ThreadPoolExecutor(max_workers=2)
        logger.info("✅ Whisper model loaded")
        
    async def transcribe(self, audio_np: np.ndarray, sample_rate: int = 16000) -> str:
        """
        Transcribe audio using Faster-Whisper
        Args:
            audio_np: numpy array of int16 PCM samples
            sample_rate: sample rate (should be 16000)
        Returns:
            Transcribed text
        """
        try:
            # Convert to float32 and normalize
            audio_float = audio_np.astype(np.float32) / 32768.0
            
            # Run in thread pool
            loop = asyncio.get_event_loop()
            segments, info = await loop.run_in_executor(
                self.executor,
                lambda: self.model.transcribe(
                    audio_float,
                    language=None,  # Auto-detect
                    task='transcribe',
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500)
                )
            )
            
            # Combine segments
            text = " ".join([segment.text for segment in segments]).strip()
            
            logger.info(f"📝 Transcribed ({info.language}): {text}")
            
            return text
            
        except Exception as e:
            logger.error(f"STT error: {e}")
            return ""
