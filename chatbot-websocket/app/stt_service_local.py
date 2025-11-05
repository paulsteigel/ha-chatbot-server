"""
STT (Speech-to-Text) Service - Handles audio transcription using OpenAI Whisper API
"""

import os
import logging
from typing import Optional
from openai import AsyncOpenAI


class STTService:
    """Speech-to-Text Service using OpenAI Whisper API"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "whisper-1"
    ):
        """
        Initialize STT Service
        
        Args:
            api_key: OpenAI API key
            base_url: API base URL (default: OpenAI)
            model: Whisper model name (default: whisper-1)
        """
        self.logger = logging.getLogger('STTService')
        
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        
        self.logger.info("🎤 Initializing STT Service...")
        self.logger.info(f"   Base URL: {base_url}")
        self.logger.info(f"   Model: {model}")
        
        # Initialize OpenAI client
        try:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
            self.logger.info("✅ STT Service initialized")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize STT client: {e}")
            raise
    
    async def transcribe(self, audio_data: bytes, language: str = "auto") -> str:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Audio data in bytes (WAV/MP3/OGG format)
            language: Language code (e.g., "vi" for Vietnamese, "en" for English, "auto" for auto-detect)
        
        Returns:
            Transcribed text
        """
        try:
            self.logger.info(f"🎤 Transcribing audio ({len(audio_data)} bytes, language: {language})...")
            
            # Prepare audio file-like object
            from io import BytesIO
            audio_file = BytesIO(audio_data)
            audio_file.name = "audio.wav"  # OpenAI requires a filename
            
            # Call Whisper API
            kwargs = {
                "model": self.model,
                "file": audio_file
            }
            
            # Add language parameter if not auto-detect
            if language != "auto":
                kwargs["language"] = language
            
            response = await self.client.audio.transcriptions.create(**kwargs)
            
            # Extract transcribed text
            transcribed_text = response.text
            
            self.logger.info(f"✅ Transcription: {transcribed_text}")
            
            return transcribed_text
            
        except Exception as e:
            self.logger.error(f"❌ Transcription error: {e}", exc_info=True)
            return ""
    
    async def transcribe_file(self, file_path: str, language: str = "auto") -> str:
        """
        Transcribe audio file to text
        
        Args:
            file_path: Path to audio file
            language: Language code (default: auto-detect)
        
        Returns:
            Transcribed text
        """
        try:
            # Read audio file
            with open(file_path, 'rb') as f:
                audio_data = f.read()
            
            return await self.transcribe(audio_data, language)
            
        except Exception as e:
            self.logger.error(f"❌ File transcription error: {e}", exc_info=True)
            return ""
