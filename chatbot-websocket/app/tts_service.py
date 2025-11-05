"""
TTS Service - Text-to-Speech using OpenAI API
"""

import os
import logging
import base64
from typing import Optional
from openai import AsyncOpenAI


class TTSService:
    """Text-to-Speech Service using OpenAI TTS API"""
    
    def __init__(self):
        """Initialize TTS Service"""
        self.logger = logging.getLogger('TTSService')
        
        # Get configuration from environment
        base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
        api_key = os.getenv('OPENAI_API_KEY', '')
        
        self.voice_vi = os.getenv('TTS_VOICE_VI', 'nova')
        self.voice_en = os.getenv('TTS_VOICE_EN', 'alloy')
        
        self.logger.info("🔊 Initializing TTS Service...")
        self.logger.info(f"   Base URL: {base_url}")
        self.logger.info(f"   Vietnamese Voice: {self.voice_vi}")
        self.logger.info(f"   English Voice: {self.voice_en}")
        
        # Valid OpenAI TTS voices
        self.VALID_VOICES = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer', 'ash', 'sage', 'coral']
        
        # Validate and fallback voices
        if self.voice_vi not in self.VALID_VOICES:
            self.logger.warning(f"⚠️ Invalid Vietnamese voice '{self.voice_vi}', using 'nova'")
            self.voice_vi = 'nova'
        
        if self.voice_en not in self.VALID_VOICES:
            self.logger.warning(f"⚠️ Invalid English voice '{self.voice_en}', using 'alloy'")
            self.voice_en = 'alloy'
        
        # Initialize OpenAI client
        try:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
            self.logger.info("✅ TTS Service initialized")
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize TTS client: {e}")
            self.client = None
    
    async def synthesize(self, text: str, language: str = 'auto') -> Optional[str]:
        """
        Synthesize text to speech
        
        Args:
            text: Text to synthesize
            language: Language code ('vi', 'en', or 'auto')
        
        Returns:
            Base64 encoded MP3 audio or None if failed
        """
        if not self.client:
            self.logger.error("❌ TTS client not initialized")
            return None
        
        try:
            # Determine voice based on language
            if language == 'vi':
                voice = self.voice_vi
            elif language == 'en':
                voice = self.voice_en
            else:
                # Auto-detect: use Vietnamese for text with Vietnamese characters
                has_vietnamese = any(ord(c) > 127 for c in text)
                voice = self.voice_vi if has_vietnamese else self.voice_en
            
            # Validate voice (safety check)
            if voice not in self.VALID_VOICES:
                self.logger.warning(f"⚠️ Invalid voice '{voice}', falling back to 'nova'")
                voice = 'nova'
            
            self.logger.info(f"🔊 Synthesizing: {text[:50]}... (Voice: {voice})")
            
            # Call TTS API
            response = await self.client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                response_format="mp3"
            )
            
            # Read audio content
            audio_bytes = response.content
            
            # Convert to base64
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            self.logger.info(f"✅ TTS generated: {len(audio_bytes)} bytes")
            
            return audio_base64
            
        except Exception as e:
            self.logger.error(f"❌ TTS Error: {e}", exc_info=True)
            return None
    
    async def synthesize_vietnamese(self, text: str) -> Optional[str]:
        """Synthesize Vietnamese text"""
        return await self.synthesize(text, language='vi')
    
    async def synthesize_english(self, text: str) -> Optional[str]:
        """Synthesize English text"""
        return await self.synthesize(text, language='en')
