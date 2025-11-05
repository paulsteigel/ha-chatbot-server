"""
STT Service - Local Faster-Whisper (FREE + FAST)
"""

import os
import logging
import tempfile
from typing import Optional
from faster_whisper import WhisperModel


class STTService:
    """Speech-to-Text using Faster-Whisper (Local)"""
    
    def __init__(self):
        """Initialize STT Service"""
        self.logger = logging.getLogger('STTService')
        
        # Model configuration
        model_size = os.getenv('WHISPER_MODEL', 'small')  # tiny, base, small, medium, large-v3
        device = os.getenv('WHISPER_DEVICE', 'cpu')  # cpu or cuda
        compute_type = os.getenv('WHISPER_COMPUTE_TYPE', 'int8')  # int8, float16, float32
        
        self.logger.info(f"🎤 Initializing Faster-Whisper...")
        self.logger.info(f"   Model: {model_size}")
        self.logger.info(f"   Device: {device}")
        self.logger.info(f"   Compute: {compute_type}")
        
        try:
            # Load model
            self.model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                download_root=os.getenv('WHISPER_CACHE_DIR', '/app/models')
            )
            
            self.logger.info("✅ STT Service initialized (Faster-Whisper Local)")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to load Whisper model: {e}")
            self.model = None
    
    async def transcribe(self, audio_data: bytes, language: str = "auto") -> Optional[str]:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Audio bytes (webm, mp3, wav, etc.)
            language: Language code ('vi', 'en', 'auto')
        
        Returns:
            Transcribed text or None
        """
        if not self.model:
            self.logger.error("❌ Whisper model not loaded")
            return None
        
        tmp_path = None
        try:
            # Save audio to temp file
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name
            
            self.logger.info(f"🎤 Transcribing audio ({len(audio_data)} bytes)...")
            
            # Determine language
            lang = None if language == "auto" else language
            
            # Transcribe
            segments, info = self.model.transcribe(
                tmp_path,
                language=lang,
                vad_filter=True,  # Voice Activity Detection - remove silence
                vad_parameters={
                    "threshold": 0.5,
                    "min_speech_duration_ms": 250,
                    "min_silence_duration_ms": 100
                },
                beam_size=5,
                best_of=5,
                temperature=0.0
            )
            
            # Combine segments
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())
            
            text = " ".join(text_parts).strip()
            
            if text:
                self.logger.info(f"✅ Transcribed ({info.language}, {info.duration:.1f}s): {text[:100]}...")
            else:
                self.logger.warning("⚠️ No transcription result")
            
            return text if text else None
            
        except Exception as e:
            self.logger.error(f"❌ Transcription error: {e}", exc_info=True)
            return None
            
        finally:
            # Cleanup temp file
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except:
                    pass
    
    async def transcribe_vietnamese(self, audio_data: bytes) -> Optional[str]:
        """Transcribe Vietnamese audio"""
        return await self.transcribe(audio_data, language='vi')
    
    async def transcribe_english(self, audio_data: bytes) -> Optional[str]:
        """Transcribe English audio"""
        return await self.transcribe(audio_data, language='en')
    
    def get_available_models(self) -> list:
        """Get list of available Whisper models"""
        return ['tiny', 'base', 'small', 'medium', 'large-v3']
