# File: app/tts_service.py
"""
TTS Service - Multi-provider with Azure Speech REST API support
✅ Providers: azure_speech (REST), openai, piper
✅ Works on Alpine Linux!
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

# aiohttp for Azure Speech REST API
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

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
        # AZURE SPEECH REST API SETUP
        # ═══════════════════════════════════════════════════════════
        self.azure_speech_key = None
        self.azure_speech_region = None
        
        if self.provider == "azure_speech" and AIOHTTP_AVAILABLE:
            # ✅ Use separate Azure Speech key (strip whitespace!)
            self.azure_speech_key = (
                get_config("azure_speech_key", "") or api_key or ""
            ).strip()
            
            self.azure_speech_region = get_config("azure_speech_region", "eastus")
            
            if self.azure_speech_key:
                logger.info("✅ Azure Speech REST API configured")
                logger.info(f"   Region: {self.azure_speech_region}")
                logger.info(f"   Key length: {len(self.azure_speech_key)} chars")
            else:
                logger.error("❌ Azure Speech key not found!")
        
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
            logger.info(f"   API: REST (Alpine compatible!)")
        elif self.provider in ['openai', 'azure']:
            voice_vi = get_config("tts_voice_vi", "nova")
            voice_en = get_config("tts_voice_en", "alloy")
            logger.info(f"   OpenAI Voices: VI={voice_vi}, EN={voice_en}")
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
        """
        current_provider = get_config("tts_provider", self.provider)
        
        # ─────────────────────────────────────────────────────────
        # TRY PRIMARY PROVIDER
        # ─────────────────────────────────────────────────────────
        try:
            if current_provider == "azure_speech":
                # ✅ Azure Speech REST API
                wav_bytes = await self._synthesize_azure_speech_rest(
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
    # AZURE SPEECH REST API METHOD (FIXED!)
    # ═══════════════════════════════════════════════════════════════════
    async def _synthesize_azure_speech_rest(
        self, text: str, language: str
    ) -> bytes:
        """
        Synthesize using Azure Speech REST API.
        Returns WAV 16kHz bytes.
        
        Docs: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech
        """
        if not AIOHTTP_AVAILABLE:
            raise Exception("aiohttp not installed")
        
        if not self.azure_speech_key:
            raise Exception("Azure Speech key not configured")
        
        # Get voice name
        voice_vi = get_config("tts_voice_vi", "vi-VN-HoaiMyNeural")
        voice_en = get_config("tts_voice_en", "en-US-AvaMultilingualNeural")
        voice_name = voice_vi if language == "vi" else voice_en
        
        # Build URL - Standard format from Microsoft docs
        url = f"https://{self.azure_speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"
        
        # Build headers
        headers = {
            "Ocp-Apim-Subscription-Key": self.azure_speech_key.strip(),
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-16khz-16bit-mono-pcm",  # WAV 16kHz
            "User-Agent": "HomeAssistant-Chatbot"
        }
        
        # Build SSML (escape XML special characters)
        text_escaped = (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;")
        )
        
        # ✅ FIXED: Add xmlns namespace for proper voice recognition!
        ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='vi-VN'>
        <voice name='{voice_name}'>
            {text_escaped}
        </voice>
    </speak>"""
        
        # ✅ DEBUG LOGGING - Show full request details
        logger.info(f"🔊 Azure Speech REST API Request:")
        logger.info(f"   URL: {url}")
        logger.info(f"   Region: {self.azure_speech_region}")
        logger.info(f"   Voice: {voice_name}")
        logger.info(f"   Key length: {len(self.azure_speech_key)} chars")
        logger.info(f"   Key prefix: {self.azure_speech_key[:10]}...")
        logger.info(f"   Text: '{text[:100]}...'")
        logger.info(f"   SSML length: {len(ssml)} bytes")
        logger.debug(f"   Full SSML:\n{ssml}")
        
        # Make request
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, 
                    headers=headers, 
                    data=ssml.encode('utf-8'),
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        
                        # ✅ DETAILED ERROR LOGGING
                        logger.error(f"❌ Azure Speech API Response:")
                        logger.error(f"   Status: {response.status}")
                        logger.error(f"   Reason: {response.reason}")
                        logger.error(f"   Error Body: {error_text}")
                        logger.error(f"   Response Headers: {dict(response.headers)}")
                        logger.error(f"   Request URL: {url}")
                        logger.error(f"   Request Headers: {headers}")
                        
                        raise Exception(
                            f"Azure Speech API error {response.status}: {error_text}"
                        )
                    
                    wav_bytes = await response.read()
                    
                    logger.info(f"✅ Azure Speech REST: {len(wav_bytes)} bytes (WAV 16kHz)")
                    return wav_bytes
        
        except asyncio.TimeoutError:
            raise Exception("Azure Speech API timeout (10s)")
        except aiohttp.ClientError as e:
            logger.error(f"❌ Connection error: {e}")
            raise Exception(f"Azure Speech API connection error: {e}")
    
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
        
        return response.content
    
    # ═══════════════════════════════════
    # PIPER METHOD (EXISTING)
    # ═══════════════════════════════════════════════════════════════════
    async def _synthesize_piper_chunk(self, text: str, language: str) -> bytes:
        """Synthesize using Piper, return WAV bytes."""
        await self._init_wyoming_client()
        
        wav_bytes = await self.wyoming_client.synthesize(text, language)
        wav_bytes = convert_to_wav_16k(wav_bytes, source_format="wav")
        
        return wav_bytes
    
    # ═══════════════════════════════════════════════════════════════════
    # BACKWARD COMPATIBILITY
    # ═══════════════════════════════════════════════════════════════════
    async def synthesize(self, text: str, language: str = "vi") -> str:
        """Convert text to speech audio (backward compatible)."""
        try:
            wav_bytes, provider = await self.synthesize_chunk(text, text, language)
            audio_base64 = base64.b64encode(wav_bytes).decode("utf-8")
            logger.info(f"✅ TTS ({provider}): {len(wav_bytes)} bytes")
            return audio_base64
        except Exception as e:
            logger.error(f"❌ TTS error: {e}")
            return ""
