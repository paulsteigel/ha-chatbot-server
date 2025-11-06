# File: app/tts_service.py
"""
TTS Service - Multi-provider with Wyoming protocol support
✅ UPDATED: Add synthesize_chunk() for streaming, always return WAV 16kHz
"""
import logging
import base64
import os
import json
from openai import AsyncOpenAI
from app.utils.audio_converter import convert_to_wav_16k  # ← NEW IMPORT

logger = logging.getLogger(__name__)

def get_config(key: str, default=None):
    """
    Get configuration from Home Assistant options.json or environment.
    Priority: HA options.json > Environment > Default
    """
    # ← KEEP: This function stays exactly the same
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
    
    def __init__(self):
        """Initialize TTS service with dynamic config."""
        
        # ← KEEP: All __init__ code stays the same
        self.config = self._build_config()
        self.provider = get_config("tts_provider", "openai")
        
        openai_api_key = get_config("openai_api_key", "")
        openai_base_url = get_config("openai_base_url", "https://api.openai.com/v1")
        
        self.openai_client = None
        if openai_api_key:
            try:
                self.openai_client = AsyncOpenAI(
                    api_key=openai_api_key,
                    base_url=openai_base_url
                )
            except Exception as e:
                logger.warning(f"⚠️ OpenAI client init failed: {e}")
        
        self.wyoming_client = None
        
        logger.info(f"🔊 TTS Service initialized")
        logger.info(f"   Provider: {self.provider}")
        if self.provider == "openai":
            tts_voice_vi = get_config("tts_voice_vi", "nova")
            tts_voice_en = get_config("tts_voice_en", "alloy")
            logger.info(f"   OpenAI voices: VI={tts_voice_vi}, EN={tts_voice_en}")
            if not self.openai_client:
                logger.error(f"   ❌ OpenAI client not initialized! Check OPENAI_API_KEY")
        elif self.provider == "piper":
            piper_voice_vi = get_config("piper_voice_vi", "vi_VN-vais1000-medium")
            piper_voice_en = get_config("piper_voice_en", "en_US-lessac-medium")
            logger.info(f"   Piper voices: VI={piper_voice_vi}, EN={piper_voice_en}")
            logger.info(f"   Will auto-fallback to OpenAI if Piper fails")
        logger.info(f"   Output: WAV 16kHz mono for ESP32")  # ← NEW LOG
    
    def _build_config(self) -> dict:
        """Build full config dict for Wyoming client."""
        # ← KEEP: This stays the same
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
        # ← KEEP: This stays exactly the same
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
    # ← KEEP: OLD synthesize() method for backward compatibility
    # ═══════════════════════════════════════════════════════════════════
    async def synthesize(self, text: str, language: str = "vi") -> str:
        """
        Convert text to speech audio (backward compatible).
        
        ⚠️ DEPRECATED: Use synthesize_chunk() for streaming.
        
        Args:
            text: Text to synthesize
            language: "vi" or "en"
            
        Returns:
            Base64 encoded WAV audio (16kHz mono)
        """
        current_provider = get_config("tts_provider", self.provider)
        
        if current_provider != self.provider:
            logger.info(f"🔄 TTS provider changed: {self.provider} → {current_provider}")
            self.provider = current_provider
            if current_provider != "piper":
                self.wyoming_client = None
        
        try:
            if self.provider == "piper":
                return await self._synthesize_piper(text, language)
            else:
                return await self._synthesize_openai(text, language)
                
        except Exception as e:
            logger.error(f"❌ TTS error with {self.provider}: {e}")
            
            if self.provider == "piper" and self.openai_client:
                logger.info("🔄 Falling back to OpenAI TTS...")
                try:
                    return await self._synthesize_openai(text, language)
                except Exception as e2:
                    logger.error(f"❌ OpenAI fallback failed: {e2}")
            
            return ""
    
    # ═══════════════════════════════════════════════════════════════════
    # ← NEW: synthesize_chunk() for streaming with fallback
    # ═══════════════════════════════════════════════════════════════════
    async def synthesize_chunk(
        self,
        original_text: str,
        cleaned_text: str,
        language: str = "vi"
    ) -> tuple[bytes, str]:
        """
        Synthesize ONE chunk with fallback support.
        Always returns WAV 16kHz mono 16-bit for ESP32.
        
        Args:
            original_text: Original text with emoji (for OpenAI fallback)
            cleaned_text: Cleaned text without emoji (for Piper)
            language: "vi" or "en"
            
        Returns:
            tuple[wav_bytes, provider_used]
            - wav_bytes: WAV 16kHz audio
            - provider_used: "piper", "openai", or "openai_fallback"
        """
        current_provider = get_config("tts_provider", self.provider)
        
        # ─────────────────────────────────────────────────────────
        # TRY PRIMARY PROVIDER
        # ─────────────────────────────────────────────────────────
        try:
            if current_provider == "piper":
                # Use cleaned text (no emoji)
                if not cleaned_text.strip():
                    raise ValueError("Empty text after cleaning")
                
                wav_bytes = await self._synthesize_piper_chunk(cleaned_text, language)
                return wav_bytes, "piper"
                
            else:  # openai
                # Use original text (with emoji)
                mp3_bytes = await self._synthesize_openai_chunk(original_text, language)
                wav_bytes = convert_to_wav_16k(mp3_bytes, source_format="mp3")
                return wav_bytes, "openai"
        
        except Exception as primary_error:
            logger.warning(
                f"⚠️ Primary TTS ({current_provider}) failed: {primary_error}"
            )
            
            # ─────────────────────────────────────────────────────────
            # FALLBACK TO SECONDARY PROVIDER
            # ─────────────────────────────────────────────────────────
            try:
                if current_provider == "piper":
                    # Piper failed → OpenAI (use ORIGINAL text with emoji!)
                    logger.info("🔄 Fallback: Piper → OpenAI (with emoji)")
                    
                    if not self.openai_client:
                        raise Exception("OpenAI not available for fallback")
                    
                    mp3_bytes = await self._synthesize_openai_chunk(
                        original_text,  # ← Use original with emoji!
                        language
                    )
                    wav_bytes = convert_to_wav_16k(mp3_bytes, source_format="mp3")
                    return wav_bytes, "openai_fallback"
                    
                else:
                    # OpenAI failed → Piper (use cleaned text)
                    logger.info("🔄 Fallback: OpenAI → Piper (cleaned)")
                    
                    if not cleaned_text.strip():
                        raise ValueError("Empty text after cleaning")
                    
                    await self._init_wyoming_client()
                    wav_bytes = await self._synthesize_piper_chunk(
                        cleaned_text,
                        language
                    )
                    return wav_bytes, "piper_fallback"
            
            except Exception as fallback_error:
                logger.error(f"❌ Fallback also failed: {fallback_error}")
                raise Exception(
                    f"All TTS failed - Primary: {primary_error}, "
                    f"Fallback: {fallback_error}"
                )
    
    # ═══════════════════════════════════════════════════════════════════
    # ← MODIFIED: Return base64 WAV (not MP3) for backward compatibility
    # ═══════════════════════════════════════════════════════════════════
    async def _synthesize_openai(self, text: str, language: str) -> str:
        """Synthesize using OpenAI TTS, return base64 WAV (not MP3)."""
        if not self.openai_client:
            raise Exception("OpenAI client not initialized. Check OPENAI_API_KEY")
        
        try:
            voice_vi = get_config("tts_voice_vi", "nova")
            voice_en = get_config("tts_voice_en", "alloy")
            voice = voice_vi if language == "vi" else voice_en
            
            logger.info(f"🔊 OpenAI TTS: voice={voice}, text='{text[:50]}...'")
            
            response = await self.openai_client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                response_format="mp3"
            )
            
            mp3_bytes = response.content
            
            # ← NEW: Convert to WAV 16kHz
            wav_bytes = convert_to_wav_16k(mp3_bytes, source_format="mp3")
            audio_base64 = base64.b64encode(wav_bytes).decode("utf-8")
            
            logger.info(f"✅ OpenAI TTS: {len(wav_bytes)} bytes (WAV 16kHz)")
            return audio_base64
            
        except Exception as e:
            logger.error(f"❌ OpenAI TTS error: {e}")
            raise
    
    # ═══════════════════════════════════════════════════════════════════
    # ← MODIFIED: Convert to 16kHz if needed
    # ═══════════════════════════════════════════════════════════════════
    async def _synthesize_piper(self, text: str, language: str) -> str:
        """Synthesize using Piper via Wyoming protocol, return base64 WAV 16kHz."""
        try:
            await self._init_wyoming_client()
            
            wav_bytes = await self.wyoming_client.synthesize(text, language)
            
            # ← NEW: Convert to 16kHz if Piper returns 22050Hz
            wav_bytes = convert_to_wav_16k(wav_bytes, source_format="wav")
            
            audio_base64 = base64.b64encode(wav_bytes).decode("utf-8")
            
            logger.info(f"✅ Piper TTS: {len(wav_bytes)} bytes (WAV 16kHz)")
            return audio_base64
            
        except Exception as e:
            logger.error(f"❌ Piper TTS (Wyoming) error: {e}")
            raise
    
    # ═══════════════════════════════════════════════════════════════════
    # ← NEW: Internal methods for chunk synthesis
    # ═══════════════════════════════════════════════════════════════════
    async def _synthesize_openai_chunk(self, text: str, language: str) -> bytes:
        """Synthesize using OpenAI, return MP3 bytes (will be converted later)."""
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
    
    async def _synthesize_piper_chunk(self, text: str, language: str) -> bytes:
        """Synthesize using Piper, return WAV bytes."""
        await self._init_wyoming_client()
        
        wav_bytes = await self.wyoming_client.synthesize(text, language)
        
        # Convert to 16kHz
        wav_bytes = convert_to_wav_16k(wav_bytes, source_format="wav")
        
        return wav_bytes  # WAV 16kHz bytes
