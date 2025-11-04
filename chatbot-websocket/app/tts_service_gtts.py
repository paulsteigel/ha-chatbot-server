"""
Google Text-to-Speech Service
Sử dụng gTTS thay vì Edge TTS
"""
import logging
from typing import Optional
from gtts import gTTS
import io

class TTSService:
    """Google TTS Service"""
    
    def __init__(self):
        self.logger = logging.getLogger('TTSService')
        self.logger.info("🔊 Initializing Google TTS Service...")
        
        # Language mapping
        self.lang_map = {
            'vi': 'vi',
            'en': 'en'
        }
    
    async def synthesize(self, text: str, language: str = 'vi') -> Optional[bytes]:
        """Synthesize speech from text using Google TTS"""
        try:
            self.logger.info(f"🔊 Synthesizing with gTTS: {text[:50]}...")
            
            # Get language code
            lang = self.lang_map.get(language, 'vi')
            
            # Create TTS object
            tts = gTTS(text=text, lang=lang, slow=False)
            
            # Save to BytesIO
            audio_fp = io.BytesIO()
            tts.write_to_fp(audio_fp)
            audio_fp.seek(0)
            audio_data = audio_fp.read()
            
            self.logger.info(f"✅ Synthesized {len(audio_data)} bytes")
            
            if len(audio_data) == 0:
                self.logger.error("❌ TTS returned empty audio!")
                return None
            
            return audio_data
            
        except Exception as e:
            self.logger.error(f"❌ TTS synthesis error: {e}", exc_info=True)
            return None
    
    async def test(self):
        """Test TTS"""
        self.logger.info("🧪 Testing Google TTS...")
        
        # Test Vietnamese
        audio = await self.synthesize("Xin chào! Mình là Yên Hoà.", "vi")
        if audio:
            self.logger.info(f"✅ Vietnamese TTS OK: {len(audio)} bytes")
        else:
            self.logger.error("❌ Vietnamese TTS failed")
        
        # Test English
        audio = await self.synthesize("Hello! I am Yen Hoa.", "en")
        if audio:
            self.logger.info(f"✅ English TTS OK: {len(audio)} bytes")
        else:
            self.logger.error("❌ English TTS failed")
