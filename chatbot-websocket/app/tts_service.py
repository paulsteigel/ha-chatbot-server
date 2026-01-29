# File: app/tts_service.py
"""
TTS Service - Multi-provider with Azure Speech SDK support
✅ Providers: azure_speech, openai, piper
✅ Streaming support with fallback
✅ Always returns WAV 16kHz mono
"""
import logging
import base64
import os
import json
import asyncio
from io import BytesIO
from typing import Optional, Tuple

from openai import AsyncOpenAI
from app.utils.audio_converter import convert_to_wav_16k

# Azure Speech SDK (optional)
try:
    import azure.cognitiveservices.speech as speechsdk
    AZURE_SPEECH_AVAILABLE = True
except ImportError:
    AZURE_SPEECH_AVAILABLE = False

logger = logging.getLogger(__name__)


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


class TTSService:
    """Text-to-Speech service with multi-provider support."""
    
    def __init__(self, provider: str = None, api_key: str = None, base_url: str = None):
        """Initialize TTS service with dynamic config."""
        
        self.config = self._build_config()
        
        # Determine provider
        if provider:
            self.provider = provider
        else:
            self.provider = get_config("tts_provider", "openai")
        
        # ═══════════════════════════════════════════════════════════
        # AZURE SPEECH SDK SETUP
        # ═══════════════════════════════════════════════════════════
        self.azure_speech_config = None
        if self.provider == "azure_speech" and AZURE_SPEECH_AVAILABLE:
            azure_key = api_key or get_config("azure_api_key", "")
            azure_endpoint = get_config("azure_speech_endpoint", "")
            
            if azure_key and azure_endpoint:
                try:
                    self.azure_speech_config = speechsdk.SpeechConfig(
                        subscription=azure_key,
                        endpoint=azure_endpoint
                    )
                    # Set output format to WAV 16kHz
                    self.azure_speech_config.set_speech_synthesis_output_format(
                        speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
                    )
                    logger.info("✅ Azure Speech SDK configured")
                except Exception as e:
                    logger.error(f"❌ Azure Speech SDK init failed: {e}")
                    self.azure_speech_config = None
        
        # ═══════════════════════════════════════════════════════════
        # OPENAI CLIENT SETUP
        # ═══════════════════════════════════════════════════════════
        self.openai_client = None
        if self.provider in ['openai', 'azure']:
            if api_key and base_url:
                tts_api_key = api_key
                tts_base_url = base_url
            else:
                tts_api_key = get_config("openai_api_key", "")
                tts_base_url = get_config("openai_base_url", "https://api.openai.com/v1")
            
            if tts_api_key:
                try:
                    self.openai_client = AsyncOpenAI(
                        api_key=tts_api_key,
                        base_url=tts_base_url
                    )
                except Exception as e:
                    logger.warning(f"⚠️ OpenAI client init failed: {e}")
        
        # ═══════════════════════════════════════════════════════════
        # PIPER (WYOMING) SETUP
        # ═══════════════════════════════════════════════════════════
        self.wyoming_client = None
        
        # ═══════════════════════════════════════════════════════════
        # LOG CONFIGURATION
        # ═══════════════════════════════════════════════════════════
        logger.info(f"🔊 TTS Service initialized")
        logger.info(f"   Provider: {self.provider}")
        
        if self.provider == "azure_speech":
            voice_vi = get_config("tts_voice_vi", "vi-VN-HoaiMyNeural")
            voice_en = get_config("tts_voice_en", "en-US-AvaMultilingualNeural")
            logger.info(f"   Azure Voices: VI={voice_vi}, EN={voice_en}")
            if not self.azure_speech_config:
                logger.error(f"   ❌ Azure Speech not available!")
        elif self.provider in ['openai', 'azure']:
            voice_vi = get_config("tts_voice_vi", "nova")
            voice_en = get_config("tts_voice_en", "alloy")
            logger.info(f"   OpenAI Voices: VI={voice_vi}, EN={voice_en}")
            if not self.openai_client:
                logger.error(f"   ❌ OpenAI client not initialized!")
        elif self.provider == "piper":
            voice_vi = get_config("piper_voice_vi", "vi_VN-vais1000-medium")
            voice_en = get_config("piper_voice_en", "en_US-lessac-medium")
            logger.info(f"   Piper Voices: VI={voice_vi}, EN={voice_en}")
        
        logger.info(f"   Output: WAV 16kHz mono for ESP32")
    
    def _build_config(self) -> dict:
        """Build full config dict for Wyoming client."""
        return {
            'tts': {
                'piper': {
                    'host': get_config('piper_host', 'addon_core_piper'),
                    'port': int(get_config('piper_port', 10200))
                }
            },
            'piper_voice_vi': get_config('piper_voice_vi', 'vi_VN-vais1000-medium'),
            'piper_voice_en': get_config('piper_voice_en', 'en_US-lessac-medium')
        }
    
    async def _init_wyoming_client(self):
        """Initialize Wyoming client (lazy load)."""
        if self.wyoming_client:
            return
        
        from app.wyoming_client import WyomingTTSClient
        
        logger.info(f"🔍 Initializing Piper TTS (Wyoming)...")
        
        try:
            self.wyoming_client = WyomingTTSClient(self.config)
            
            if await self.wyoming_client.test_connection():
                host = self.config['tts']['piper']['host']
                port = self.config['tts']['piper']['port']
                logger.info(f"   ✅ Connected to Piper: {host}:{port}")
            else:
                raise Exception("Connection test failed")
                
        except Exception as e:
            logger.error(f"   ❌ Piper connection error: {e}")
            raise Exception("❌ Cannot connect to Piper. Is Piper addon running?")
    
    # ═══════════════════════════════════════════════════════════════════
    # MAIN STREAMING METHOD
    # ═══════════════════════════════════════════════════════════════════
    async def synthesize_chunk(
        self,
        original_text: str,
        cleaned_text: str,
        language: str = "vi"
    ) -> Tuple[bytes, str]:
        """
        Synthesize ONE chunk with fallback support.
        Always returns WAV 16kHz mono 16-bit for ESP32.
        
        Args:
            original_text: Original text with emoji (for OpenAI/Azure Speech)
            cleaned_text: Cleaned text without emoji (for Piper)
            language: "vi" or "en"
            
        Returns:
            tuple[wav_bytes, provider_used]
        """
        current_provider = get_config("tts_provider", self.provider)
        
        # ─────────────────────────────────────────────────────────
        # TRY PRIMARY PROVIDER
        # ─────────────────────────────────────────────────────────
        try:
            if current_provider == "azure_speech":
                # Azure Speech SDK (use original text)
                wav_bytes = await self._synthesize_azure_speech_chunk(
                    original_text, language
                )
                return wav_bytes, "azure_speech"
            
            elif current_provider == "piper":
                # Piper (use cleaned text)
                if not cleaned_text.strip():
                    raise ValueError("Empty text after cleaning")
                
                wav_bytes = await self._synthesize_piper_chunk(cleaned_text, language)
                return wav_bytes, "piper"
            
            else:  # openai or azure (OpenAI-compatible)
                # OpenAI API (use original text)
                mp3_bytes = await self._synthesize_openai_chunk(original_text, language)
                wav_bytes = convert_to_wav_16k(mp3_bytes, source_format="mp3")
                return wav_bytes, current_provider
        
        except Exception as primary_error:
            logger.warning(
                f"⚠️ Primary TTS ({current_provider}) failed: {primary_error}"
            )
            
            # ─────────────────────────────────────────────────────────
            # FALLBACK CHAIN
            # ─────────────────────────────────────────────────────────
            try:
                # Try OpenAI as first fallback
                if current_provider != "openai" and self.openai_client:
                    logger.info(f"🔄 Fallback: {current_provider} → OpenAI")
                    mp3_bytes = await self._synthesize_openai_chunk(
                        original_text, language
                    )
                    wav_bytes = convert_to_wav_16k(mp3_bytes, source_format="mp3")
                    return wav_bytes, "openai_fallback"
                
                # Try Piper as last resort
                if not cleaned_text.strip():
                    raise ValueError("Empty text for Piper fallback")
                
                logger.info(f"🔄 Fallback: {current_provider} → Piper")
                await self._init_wyoming_client()
                wav_bytes = await self._synthesize_piper_chunk(cleaned_text, language)
                return wav_bytes, "piper_fallback"
            
            except Exception as fallback_error:
                logger.error(f"❌ All TTS failed: {fallback_error}")
                raise Exception(
                    f"All TTS failed - Primary: {primary_error}, "
                    f"Fallback: {fallback_error}"
                )
    
    # ═══════════════════════════════════════════════════════════════════
    # AZURE SPEECH SDK METHOD (NEW!)
    # ═══════════════════════════════════════════════════════════════════
    async def _synthesize_azure_speech_chunk(
        self, text: str, language: str
    ) -> bytes:
        """
        Synthesize using Azure Speech SDK.
        Returns WAV 16kHz bytes.
        """
        if not self.azure_speech_config:
            raise Exception("Azure Speech SDK not configured")
        
        # Get voice name
        voice_vi = get_config("tts_voice_vi", "vi-VN-HoaiMyNeural")
        voice_en = get_config("tts_voice_en", "en-US-AvaMultilingualNeural")
        voice_name = voice_vi if language == "vi" else voice_en
        
        self.azure_speech_config.speech_synthesis_voice_name = voice_name
        
        logger.debug(f"🔊 Azure Speech: voice={voice_name}, text='{text[:50]}...'")
        
        # Azure SDK is SYNC - run in executor
        def _sync_synthesize():
            # Create synthesizer with null output (we'll get bytes)
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.azure_speech_config,
                audio_config=None  # No audio output, we want bytes
            )
            
            # Synthesize
            result = synthesizer.speak_text(text)
            
            # Check result
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                return result.audio_data  # WAV 16kHz bytes
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                raise Exception(
                    f"Azure Speech canceled: {cancellation.reason} - "
                    f"{cancellation.error_details}"
                )
            else:
                raise Exception(f"Azure Speech failed: {result.reason}")
        
        # Run in executor
        loop = asyncio.get_event_loop()
        wav_bytes = await loop.run_in_executor(None, _sync_synthesize)
        
        logger.debug(f"✅ Azure Speech: {len(wav_bytes)} bytes (WAV 16kHz)")
        return wav_bytes
    
    # ═══════════════════════════════════════════════════════════════════
    # OPENAI METHOD (EXISTING)
    # ═══════════════════════════════════════════════════════════════════
    async def _synthesize_openai_chunk(self, text: str, language: str) -> bytes:
        """Synthesize using OpenAI, return MP3 bytes."""
        if not self.openai_client:
            raise Exception("OpenAI client not initialized")
        
        voice_vi = get_config("tts_voice_vi", "nova")
        voice_en = get_config("tts_voice_en", "alloy")
        voice = voice_vi if language == "vi" else voice_en
        
        logger.debug(f"🔊 OpenAI chunk: voice={voice}, text='{text[:50]}...'")
        
        response = await self.openai_client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="mp3"
        )
        
        return response.content  # MP3 bytes
    
    # ═══════════════════════════════════════════════════════════════════
    # PIPER METHOD (EXISTING)
    # ═══════════════════════════════════════════════════════════════════
    async def _synthesize_piper_chunk(self, text: str, language: str) -> bytes:
        """Synthesize using Piper, return WAV bytes."""
        await self._init_wyoming_client()
        
        wav_bytes = await self.wyoming_client.synthesize(text, language)
        
        # Convert to 16kHz
        wav_bytes = convert_to_wav_16k(wav_bytes, source_format="wav")
        
        return wav_bytes  # WAV 16kHz bytes
    
    # ═══════════════════════════════════════════════════════════════════
    # BACKWARD COMPATIBILITY (DEPRECATED)
    # ═══════════════════════════════════════════════════════════════════
    async def synthesize(self, text: str, language: str = "vi") -> str:
        """
        Convert text to speech audio (backward compatible).
        
        ⚠️ DEPRECATED: Use synthesize_chunk() for streaming.
        
        Returns:
            Base64 encoded WAV audio (16kHz mono)
        """
        try:
            wav_bytes, provider = await self.synthesize_chunk(text, text, language)
            audio_base64 = base64.b64encode(wav_bytes).decode("utf-8")
            logger.info(f"✅ TTS ({provider}): {len(wav_bytes)} bytes")
            return audio_base64
        except Exception as e:
            logger.error(f"❌ TTS error: {e}")
            return ""
