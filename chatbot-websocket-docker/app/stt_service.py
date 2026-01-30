# File: app/stt_service.py
"""
STT Service - Multi-provider with Azure Speech REST API support
✅ Providers: azure_speech, groq, openai
✅ Async support with fallback
"""

import os
import logging
import time
import json
from typing import Optional
from io import BytesIO
import asyncio

# Groq (optional)
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

from openai import AsyncOpenAI

# aiohttp for Azure Speech REST API
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


def get_config(key: str, default=None):
    """Get configuration from Home Assistant options.json or environment."""
    options_file = "/data/options.json"
    if os.path.exists(options_file):
        try:
            with open(options_file, 'r') as f:
                options = json.load(f)
                if key in options:
                    value = options[key]
                    if value not in [None, "", "null", "None"]:
                        return value
        except Exception:
            pass
    
    env_key = key.upper()
    env_value = os.getenv(env_key)
    if env_value not in [None, "", "null", "None"]:
        return env_value
    
    return default


class STTService:
    """Speech-to-Text Service with multi-provider support"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "whisper-1",
        provider: str = "openai"
    ):
        """Initialize STT Service"""
        self.logger = logging.getLogger('STTService')
        self.provider = provider.lower()
        self.api_key = api_key
        
        # ═══════════════════════════════════════════════════════════
        # AZURE SPEECH REST API SETUP
        # ═══════════════════════════════════════════════════════════
        if self.provider == "azure_speech" and AIOHTTP_AVAILABLE:
            self.azure_endpoint = get_config(
                "azure_speech_endpoint",
                ""
            )
            self.azure_api_version = "2025-10-15"
            
            if self.azure_endpoint:
                self.logger.info("🎤 Initializing STT Service...")
                self.logger.info(f"   Provider: Azure Speech REST API")
                self.logger.info(f"   Endpoint: {self.azure_endpoint}")
                self.logger.info(f"   API Version: {self.azure_api_version}")
            else:
                self.logger.error("❌ Azure Speech endpoint not configured!")
        
        # ═══════════════════════════════════════════════════════════
        # GROQ SETUP
        # ═══════════════════════════════════════════════════════════
        elif self.provider == "groq" and GROQ_AVAILABLE:
            self.use_groq = True
            self.client = Groq(api_key=api_key)
            self.model = "whisper-large-v3"
            
            self.logger.info("🎤 Initializing STT Service...")
            self.logger.info(f"   Provider: Groq Whisper (FAST! ⚡)")
            self.logger.info(f"   Model: {self.model}")
        
        # ═══════════════════════════════════════════════════════════
        # OPENAI SETUP
        # ═══════════════════════════════════════════════════════════
        else:
            self.use_groq = False
            self.base_url = base_url
            self.model = model
            
            self.logger.info("🎤 Initializing STT Service...")
            self.logger.info(f"   Provider: {self.provider.upper()} Whisper")
            self.logger.info(f"   Endpoint: {base_url}")
            self.logger.info(f"   Model: {model}")
            
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
        
        self.logger.info("✅ STT Service initialized")
    
    def _prepare_audio(self, audio_data: bytes) -> BytesIO:
        """Prepare audio data for transcription"""
        audio_file = BytesIO(audio_data)
        audio_file.name = "audio.webm"
        audio_file.seek(0)
        return audio_file
    
    async def transcribe(self, audio_data: bytes, language: str = "auto") -> str:
        """
        Transcribe audio to text with provider fallback.
        
        Args:
            audio_data: Audio bytes
            language: Language code (auto, vi, en, etc.)
        
        Returns:
            Transcribed text
        """
        start_time = time.time()
        
        try:
            self.logger.info(
                f"🎤 Transcribing audio ({len(audio_data)} bytes, "
                f"language: {language}, provider: {self.provider})..."
            )
            
            # ─────────────────────────────────────────────────────────
            # TRY PRIMARY PROVIDER
            # ─────────────────────────────────────────────────────────
            if self.provider == "azure_speech":
                text = await self._transcribe_azure_speech(audio_data, language)
            elif self.provider == "groq" and hasattr(self, 'use_groq') and self.use_groq:
                text = await self._transcribe_groq(audio_data, language)
            else:
                text = await self._transcribe_openai(audio_data, language)
            
            elapsed = time.time() - start_time
            
            self.logger.info(f"✅ Transcription ({self.provider}): {text}")
            self.logger.info(f"⏱️  Completed in {elapsed:.2f}s")
            
            return text
        
        except Exception as e:
            self.logger.error(f"❌ Transcription error ({self.provider}): {e}")
            
            # ─────────────────────────────────────────────────────────
            # FALLBACK TO GROQ (if available)
            # ─────────────────────────────────────────────────────────
            if self.provider != "groq" and GROQ_AVAILABLE:
                groq_key = get_config("groq_api_key", "")
                if groq_key:
                    try:
                        self.logger.info("🔄 Fallback: Azure/OpenAI → Groq")
                        fallback_service = STTService(
                            api_key=groq_key,
                            provider="groq"
                        )
                        return await fallback_service.transcribe(audio_data, language)
                    except Exception as groq_error:
                        self.logger.error(f"❌ Groq fallback failed: {groq_error}")
            
            return ""
    
    # ═══════════════════════════════════════════════════════════════════
    # AZURE SPEECH REST API METHOD (NEW!)
    # ═══════════════════════════════════
    async def _transcribe_azure_speech(
        self, audio_data: bytes, language: str
    ) -> str:
        """
        Transcribe using Azure Speech REST API.
        
        Endpoint: /speechtotext/transcriptions:transcribe
        """
        if not AIOHTTP_AVAILABLE:
            raise Exception("aiohttp not installed")
        
        if not self.azure_endpoint:
            raise Exception("Azure Speech endpoint not configured")
        
        # Build URL
        url = (
            f"{self.azure_endpoint}/speechtotext/transcriptions:transcribe"
            f"?api-version={self.azure_api_version}"
        )
        
        # Build headers
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key
        }
        
        # Build form data
        form = aiohttp.FormData()
        form.add_field(
            'audio',
            audio_data,
            filename='audio.webm',
            content_type='audio/webm'
        )
        
        # Build definition JSON
        definition = {
            "enhancedMode": {
                "enabled": True,
                "task": "transcribe"
            }
        }
        
        # Add language hint if specified
        if language != "auto":
            definition["locales"] = [language if language != "vi" else "vi-VN"]
        
        form.add_field(
            'definition',
            json.dumps(definition),
            content_type='application/json'
        )
        
        # Make request
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=form) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Azure Speech API error {response.status}: {error_text}"
                    )
                
                result = await response.json()
                
                # Extract text from response
                # Response format: {"text": "transcribed text", ...}
                text = result.get("text", "")
                
                if not text:
                    # Try alternative response formats
                    if "combinedPhrases" in result:
                        phrases = result["combinedPhrases"]
                        if phrases and len(phrases) > 0:
                            text = phrases[0].get("text", "")
                
                return text.strip()
    
    # ═══════════════════════════════════════════════════════════════════
    # GROQ METHOD (EXISTING)
    # ═══════════════════════════════════════════════════════════════════
    async def _transcribe_groq(self, audio_data: bytes, language: str) -> str:
        """Transcribe using Groq (fast!)"""
        audio_file = self._prepare_audio(audio_data)
        
        # Map language codes
        language_map = {
            "auto": None,
            "vi": "vi",
            "en": "en",
        }
        
        groq_language = language_map.get(language, None)
        
        # Groq is SYNC - run in executor
        def _groq_sync_call():
            audio_file.seek(0)
            
            kwargs = {
                "file": ("audio.webm", audio_file, "audio/webm"),
                "model": self.model,
                "response_format": "text"
            }
            
            if groq_language:
                kwargs["language"] = groq_language
            
            if language == "vi" or language == "auto":
                kwargs["prompt"] = "Đây là tiếng Việt."
            
            return self.client.audio.transcriptions.create(**kwargs)
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _groq_sync_call)
        
        text = response.strip() if isinstance(response, str) else response.text.strip()
        return text
    
    # ═══════════════════════════════════════════════════════════════════
    # OPENAI METHOD (EXISTING)
    # ═══════════════════════════════════════════════════════════════════
    async def _transcribe_openai(self, audio_data: bytes, language: str) -> str:
        """Transcribe using OpenAI API"""
        audio_file = self._prepare_audio(audio_data)
        
        kwargs = {
            "file": ("audio.webm", audio_file, "audio/webm"),
            "model": self.model
        }
        
        if language != "auto":
            kwargs["language"] = language
        
        if language == "vi" or language == "auto":
            kwargs["prompt"] = "Đây là tiếng Việt."
        
        response = await self.client.audio.transcriptions.create(**kwargs)
        
        text = response.text.strip() if hasattr(response, 'text') else str(response).strip()
        return text
    
    async def transcribe_file(self, file_path: str, language: str = "auto") -> str:
        """Transcribe audio file to text"""
        try:
            with open(file_path, 'rb') as f:
                audio_data = f.read()
            
            return await self.transcribe(audio_data, language)
            
        except Exception as e:
            self.logger.error(f"❌ File transcription error: {e}", exc_info=True)
            return ""
