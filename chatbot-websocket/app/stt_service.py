"""
STT Service - Groq Whisper (Fast) with OpenAI fallback
"""

import os
import logging
import time
from typing import Optional
from io import BytesIO


# Try Groq first, fallback to OpenAI
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

from openai import AsyncOpenAI


class STTService:
    """Speech-to-Text Service"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "whisper-1"
    ):
        """Initialize STT Service"""
        self.logger = logging.getLogger('STTService')
        
        # Check for Groq API key
        groq_key = os.getenv("GROQ_API_KEY")
        
        # Decide which provider to use
        if GROQ_AVAILABLE and groq_key and groq_key.startswith("gsk_"):
            # Use Groq (FAST!)
            self.use_groq = True
            self.client = Groq(api_key=groq_key)
            self.model = "whisper-large-v3"
            self.provider = "Groq"
            
            self.logger.info("🎤 Initializing STT Service...")
            self.logger.info(f"   Provider: Groq Whisper (FAST! ⚡)")
            self.logger.info(f"   Model: {self.model}")
            self.logger.info(f"   Expected latency: ~0.2s")
        else:
            # Fallback to OpenAI
            self.use_groq = False
            self.api_key = api_key
            self.base_url = base_url
            self.model = model
            self.provider = "OpenAI"
            
            self.logger.info("🎤 Initializing STT Service...")
            self.logger.info(f"   Provider: OpenAI Whisper")
            self.logger.info(f"   Base URL: {base_url}")
            self.logger.info(f"   Model: {model}")
            
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
        
        self.logger.info("✅ STT Service initialized")
    
    def _prepare_audio(self, audio_data: bytes) -> BytesIO:
        """
        Prepare audio data for transcription
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            BytesIO object ready for upload
        """
        audio_file = BytesIO(audio_data)
        audio_file.name = "audio.webm"
        audio_file.seek(0)
        return audio_file

    async def transcribe(self, audio_data: bytes, language: str = "auto") -> str:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Audio bytes
            language: Language code (auto, vi, en, zh, etc.)
        
        Returns:
            Transcribed text
        """
        import time
        start_time = time.time()
        
        try:
            self.logger.info(f"🎤 Transcribing audio ({len(audio_data)} bytes, language: {language})...")
            
            # Convert to format Whisper likes
            audio_file = self._prepare_audio(audio_data)
            
            # GROQ API CALL WITH LANGUAGE HINT
            if self.use_groq:
                # Map language codes
                language_map = {
                    "auto": None,  # Let Groq decide
                    "vi": "vi",    # Vietnamese
                    "en": "en",    # English
                }
                
                groq_language = language_map.get(language, None)
                
                # Build request params
                request_params = {
                    "file": ("audio.webm", audio_file, "audio/webm"),
                    "model": self.model,
                    "response_format": "text"
                }
                
                # Add language if specified
                if groq_language:
                    request_params["language"] = groq_language
                    self.logger.info(f"🌍 Using language hint: {groq_language}")
                
                # Add prompt to help with Vietnamese
                if language == "vi" or language == "auto":
                    request_params["prompt"] = "Đây là tiếng Việt. This is Vietnamese language."
                
                response = await self.client.audio.transcriptions.create(**request_params)
                
            else:
                # OpenAI API
                response = await self.client.audio.transcriptions.create(
                    file=("audio.webm", audio_file, "audio/webm"),
                    model=self.model,
                    language=language if language != "auto" else None,
                    prompt="Đây là tiếng Việt." if language == "vi" else None
                )
            
            text = response.strip() if isinstance(response, str) else response.text.strip()
            
            elapsed = time.time() - start_time
            
            self.logger.info(f"✅ Transcription ({self.provider}): {text}")
            self.logger.info(f"⏱️  Completed in {elapsed:.2f}s")
            
            return text
            
        except Exception as e:
            self.logger.error(f"❌ Transcription error: {e}", exc_info=True)
            return ""

    
    async def _transcribe_groq(self, audio_data: bytes, language: str) -> str:
        """Transcribe using Groq (fast!)"""
        import asyncio
        
        # Save to temp file
        temp_file = f"/tmp/audio_{int(time.time() * 1000)}.webm"
        
        try:
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            
            # Groq is sync, run in executor
            def _sync_call():
                with open(temp_file, "rb") as audio_file:
                    transcription = self.client.audio.transcriptions.create(
                        file=audio_file,
                        model=self.model,
                        language=language if language != "auto" else None,
                        response_format="text",
                        temperature=0.0
                    )
                return transcription
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _sync_call)
            
            return result.strip()
            
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    async def _transcribe_openai(self, audio_data: bytes, language: str) -> str:
        """Transcribe using OpenAI (fallback)"""
        audio_file = BytesIO(audio_data)
        audio_file.name = "audio.wav"
        
        kwargs = {
            "model": self.model,
            "file": audio_file
        }
        
        if language != "auto":
            kwargs["language"] = language
        
        response = await self.client.audio.transcriptions.create(**kwargs)
        return response.text
    
    async def transcribe_file(self, file_path: str, language: str = "auto") -> str:
        """Transcribe audio file to text"""
        try:
            with open(file_path, 'rb') as f:
                audio_data = f.read()
            
            return await self.transcribe(audio_data, language)
            
        except Exception as e:
            self.logger.error(f"❌ File transcription error: {e}", exc_info=True)
            return ""
