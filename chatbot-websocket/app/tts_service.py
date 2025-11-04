"""
Google Text-to-Speech Service (gTTS)
Free, unlimited, and supports Vietnamese well
"""
import logging
import io
import asyncio
from typing import Optional
from gtts import gTTS


class TTSService:
    """Google TTS Service using gTTS"""
    
    def __init__(self, voice_vi: str = 'vi', voice_en: str = 'en'):
        self.logger = logging.getLogger('TTSService')
        
        # Language mapping for gTTS
        self.lang_map = {
            'vi': 'vi',
            'en': 'en',
            'auto': 'vi'
        }
        
        self.logger.info("🔊 Initializing Google TTS Service (gTTS)...")
        self.logger.info("   Languages: Vietnamese (vi), English (en)")
        self.logger.info("   Status: FREE & UNLIMITED 🆓")
    
    async def initialize(self):
        """Initialize the TTS service"""
        try:
            # Test gTTS availability
            test_tts = gTTS(text="test", lang='en')
            self.logger.info("✅ Google TTS Service initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize TTS: {e}")
            raise
    
    def detect_language(self, text: str) -> str:
        """
        Detect language from text
        Returns 'vi' for Vietnamese, 'en' for English
        """
        # Vietnamese characters
        vietnamese_chars = 'àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ'
        
        # Check if text contains Vietnamese characters
        text_lower = text.lower()
        if any(char in text_lower for char in vietnamese_chars):
            return 'vi'
        
        return 'en'
    
    async def synthesize(self, text: str, language: str = 'auto', format: str = 'mp3') -> Optional[bytes]:
        """
        Synthesize speech from text using Google TTS
        
        Args:
            text: Text to synthesize
            language: Language code ('vi', 'en', 'auto')
            format: Audio format (only 'mp3' supported by gTTS)
        
        Returns:
            Audio bytes (MP3) or None if failed
        """
        try:
            # Auto-detect language if needed
            if language == 'auto':
                language = self.detect_language(text)
            
            # Get language code
            lang = self.lang_map.get(language, 'vi')
            
            self.logger.info("🔊 Synthesizing with Google TTS...")
            self.logger.info(f"   Text: {text[:50]}{'...' if len(text) > 50 else ''}")
            self.logger.info(f"   Language: {lang}")
            
            # Run TTS in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            audio_data = await loop.run_in_executor(
                None, 
                self._synthesize_sync, 
                text, 
                lang
            )
            
            if audio_data:
                self.logger.info(f"✅ Generated {len(audio_data)} bytes of MP3 audio")
                return audio_data
            else:
                self.logger.error("❌ TTS returned empty audio")
                return None
            
        except Exception as e:
            self.logger.error(f"❌ TTS synthesis error: {e}", exc_info=True)
            return None
    
    def _synthesize_sync(self, text: str, lang: str) -> Optional[bytes]:
        """
        Synchronous TTS synthesis (runs in thread pool)
        """
        try:
            # Create TTS object
            tts = gTTS(text=text, lang=lang, slow=False)
            
            # Save to BytesIO
            audio_fp = io.BytesIO()
            tts.write_to_fp(audio_fp)
            audio_fp.seek(0)
            
            # Read audio data
            audio_data = audio_fp.read()
            
            return audio_data
            
        except Exception as e:
            self.logger.error(f"❌ Sync TTS error: {e}")
            return None
    
    async def test(self):
        """Test TTS service"""
        self.logger.info("🧪 Testing Google TTS...")
        self.logger.info("=" * 60)
        
        # Test Vietnamese
        self.logger.info("📝 Test 1: Vietnamese...")
        audio = await self.synthesize("Xin chào! Mình là Yên Hoà, trợ lý AI của trường.", "vi")
        if audio:
            self.logger.info(f"   ✅ Vietnamese TTS OK: {len(audio)} bytes")
        else:
            self.logger.error("   ❌ Vietnamese TTS FAILED")
        
        # Test English
        self.logger.info("📝 Test 2: English...")
        audio = await self.synthesize("Hello! I am Yen Hoa, your AI assistant.", "en")
        if audio:
            self.logger.info(f"   ✅ English TTS OK: {len(audio)} bytes")
        else:
            self.logger.error("   ❌ English TTS FAILED")
        
        # Test auto-detect Vietnamese
        self.logger.info("📝 Test 3: Auto-detect (Vietnamese)...")
        audio = await self.synthesize("Hôm nay thời tiết thế nào?", "auto")
        if audio:
            self.logger.info(f"   ✅ Auto-detect Vietnamese OK: {len(audio)} bytes")
        else:
            self.logger.error("   ❌ Auto-detect Vietnamese FAILED")
        
        # Test auto-detect English
        self.logger.info("📝 Test 4: Auto-detect (English)...")
        audio = await self.synthesize("What is the weather today?", "auto")
        if audio:
            self.logger.info(f"   ✅ Auto-detect English OK: {len(audio)} bytes")
        else:
            self.logger.error("   ❌ Auto-detect English FAILED")
        
        self.logger.info("=" * 60)
        self.logger.info("✅ TTS testing completed!")
