# File: app/stt_service.py
"""
STT Service - Multi-provider with Azure Speech SDK support
✅ Providers: azure_speech (SDK + REST fallback), groq, openai
✅ SDK for speed (< 2s), REST as fallback
"""

import os
import logging
import time
import json
from typing import Optional
from io import BytesIO
import asyncio
import tempfile

# Azure Speech SDK (for Debian)
try:
    import azure.cognitiveservices.speech as speechsdk
    AZURE_SDK_AVAILABLE = True
except ImportError:
    AZURE_SDK_AVAILABLE = False
    speechsdk = None

# Groq (optional)
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

from openai import AsyncOpenAI

# aiohttp for Azure Speech REST API (fallback)
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
        # AZURE SPEECH SDK SETUP (PRIMARY)
        # ═══════════════════════════════════════════════════════════
        self.speech_config = None
        self.azure_region = None
        self.azure_endpoint = None
        
        if self.provider == "azure_speech":
            # Get region from config
            self.azure_region = get_config("azure_speech_region", "eastus")
            
            # ✅ TRY TO INITIALIZE SDK (if available)
            if AZURE_SDK_AVAILABLE:
                try:
                    self.speech_config = speechsdk.SpeechConfig(
                        subscription=api_key,
                        region=self.azure_region
                    )
                    
                    # Set recognition language (auto-detect or specific)
                    # For auto-detect, we'll set it per-request
                    
                    self.logger.info("🎤 Initializing STT Service...")
                    self.logger.info(f"   Provider: Azure Speech SDK")
                    self.logger.info(f"   Region: {self.azure_region}")
                    self.logger.info(f"   Method: SDK (FAST! < 2s)")
                    
                except Exception as e:
                    self.logger.warning(f"⚠️ Azure Speech SDK init failed: {e}")
                    self.logger.info("   Fallback: Will use REST API")
                    self.speech_config = None
            else:
                self.logger.info("⚠️ Azure Speech SDK not available (Alpine?)")
                self.logger.info("   Using REST API (slower)")
            
            # ✅ PREPARE REST API FALLBACK
            if AIOHTTP_AVAILABLE:
                self.azure_endpoint = (
                    f"https://{self.azure_region}.api.cognitive.microsoft.com"
                )
                self.azure_api_version = "2024-11-15"
                
                if not self.speech_config:
                    self.logger.info("🎤 Initializing STT Service...")
                    self.logger.info(f"   Provider: Azure Speech REST API")
                    self.logger.info(f"   Region: {self.azure_region}")
                    self.logger.info(f"   Endpoint: {self.azure_endpoint}")
        
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
                # ✅ TRY SDK FIRST (if available)
                if self.speech_config and AZURE_SDK_AVAILABLE:
                    try:
                        text = await self._transcribe_azure_speech_sdk(
                            audio_data, language
                        )
                        elapsed = time.time() - start_time
                        self.logger.info(f"✅ Transcription (Azure SDK): {text}")
                        self.logger.info(f"⏱️  Completed in {elapsed:.2f}s")
                        return text
                    except Exception as sdk_error:
                        self.logger.warning(
                            f"⚠️ SDK failed: {sdk_error}, trying REST API..."
                        )
                
                # ✅ FALLBACK TO REST API
                if AIOHTTP_AVAILABLE and self.azure_endpoint:
                    text = await self._transcribe_azure_speech_rest(
                        audio_data, language
                    )
                    elapsed = time.time() - start_time
                    self.logger.info(f"✅ Transcription (Azure REST): {text}")
                    self.logger.info(f"⏱️  Completed in {elapsed:.2f}s")
                    return text
                else:
                    raise Exception("Neither SDK nor REST API available")
            
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
    # ✅ NEW: AZURE SPEECH SDK METHOD (FAST!)
    # ═══════════════════════════════════════════════════════════════════
    async def _transcribe_azure_speech_sdk(
        self, audio_data: bytes, language: str
    ) -> str:
        """
        Transcribe using Azure Speech SDK (FAST! < 2s)
        Supports: WAV, MP3, OGG, WEBM
        """
        if not AZURE_SDK_AVAILABLE or not self.speech_config:
            raise Exception("Azure Speech SDK not available")
        
        # Map language codes
        language_map = {
            "auto": None,  # Auto-detect
            "vi": "vi-VN",
            "en": "en-US"
        }
        
        recognition_language = language_map.get(language, None)
        
        # Save audio to temp file (SDK needs file path)
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_path = temp_file.name
        
        try:
            # Create audio config from file
            audio_config = speechsdk.AudioConfig(filename=temp_path)
            
            # Create recognizer
            if recognition_language:
                # Specific language
                speech_recognizer = speechsdk.SpeechRecognizer(
                    speech_config=self.speech_config,
                    audio_config=audio_config,
                    language=recognition_language
                )
            else:
                # Auto-detect (vi-VN, en-US)
                auto_detect_config = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
                    languages=["vi-VN", "en-US"]
                )
                speech_recognizer = speechsdk.SpeechRecognizer(
                    speech_config=self.speech_config,
                    audio_config=audio_config,
                    auto_detect_source_language_config=auto_detect_config
                )
            
            self.logger.debug(
                f"🎤 Azure SDK: language={recognition_language or 'auto-detect'}"
            )
            
            # Recognize (FAST!)
            def _sync_recognize():
                return speech_recognizer.recognize_once()
            
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _sync_recognize)
            
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                text = result.text.strip()
                self.logger.info(f"✅ Azure Speech SDK: '{text}'")
                return text
            
            elif result.reason == speechsdk.ResultReason.NoMatch:
                self.logger.warning("⚠️ Azure Speech SDK: No speech detected")
                return ""
            
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                error_msg = f"Azure Speech SDK error: {cancellation.reason}"
                if cancellation.error_details:
                    error_msg += f" - {cancellation.error_details}"
                self.logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
            
            else:
                raise Exception(f"Azure Speech SDK failed: {result.reason}")
        
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except Exception:
                pass
    
    # ═══════════════════════════════════════════════════════════════════
    # AZURE SPEECH REST API METHOD (FALLBACK)
    # ═══════════════════════════════════
    async def _transcribe_azure_speech_rest(
        self, audio_data: bytes, language: str
    ) -> str:
        """
        Transcribe using Azure Speech REST API (SLOWER, 5-10s)
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
            "locales": ["vi-VN", "en-US"] if language == "auto" else [
                "vi-VN" if language == "vi" else "en-US"
            ]
        }
        
        form.add_field(
            'definition',
            json.dumps(definition),
            content_type='application/json'
        )
        
        # Make request
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    headers=headers, 
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(
                            f"Azure Speech API error {response.status}: {error_text}"
                        )
                    
                    result = await response.json()
                    
                    # Extract text from response
                    text = result.get("text", "")
                    
                    if not text and "combinedPhrases" in result:
                        phrases = result["combinedPhrases"]
                        if phrases and len(phrases) > 0:
                            text = phrases[0].get("text", "")
                    
                    return text.strip()
        
        except asyncio.TimeoutError:
            raise Exception("Azure Speech API timeout (10s)")
        except aiohttp.ClientError as e:
            raise Exception(f"Azure Speech API connection error: {e}")
    
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
