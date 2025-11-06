# File: app/wyoming_client.py
"""
Wyoming Protocol Client for Piper TTS
Compatible with Wyoming 1.5.2
"""
import asyncio
import logging
import io
import wave
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.tts import Synthesize, SynthesizeVoice
from wyoming.event import async_write_event, async_read_event

logger = logging.getLogger(__name__)

class WyomingTTSClient:
    """Client for Wyoming TTS protocol (Piper)."""
    
    def __init__(self, config: dict):
        """
        Initialize Wyoming TTS client
        
        Args:
            config: Configuration dict containing piper settings
        """
        piper_config = config.get('tts', {}).get('piper', {})
        self.host = piper_config.get('host', 'addon_core_piper')
        self.port = piper_config.get('port', 10200)
        self.timeout = 30
        
        # ✅ ĐỌC VOICES TỪ CONFIG
        self.voices = {
            'vi': config.get('piper_voice_vi', 'vi_VN-vais1000-medium'),
            'en': config.get('piper_voice_en', 'en_US-lessac-medium')
        }
        
        logger.info(f"🔊 Wyoming TTS Client: {self.host}:{self.port}")
        logger.info(f"🎤 Voices: VI={self.voices['vi']}, EN={self.voices['en']}")
    
    async def synthesize(self, text: str, language: str = 'vi') -> bytes:
        """
        Synthesize text to speech using Wyoming protocol.
        
        Args:
            text: Text to synthesize
            language: Language code ('vi' or 'en')
            
        Returns:
            WAV audio bytes
        """
        # ✅ CHỌN VOICE ĐÚNG THEO NGÔN NGỮ
        voice = self.voices.get(language, self.voices['vi'])
        
        try:
            logger.info(f"🔊 Wyoming TTS [{language}]: voice={voice}, text='{text[:50]}...'")
            
            # Connect to Piper
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=5
            )
            
            try:
                # ✅ CREATE PROPER SynthesizeVoice OBJECT
                voice_obj = SynthesizeVoice(name=voice)
                
                # ✅ CREATE SYNTHESIZE EVENT
                synthesize_event = Synthesize(
                    text=text,
                    voice=voice_obj  # ← Voice object với name đúng
                )
                
                # ✅ WRITE EVENT
                await async_write_event(synthesize_event.event(), writer)
                await writer.drain()
                
                # Receive audio chunks
                audio_bytes = bytearray()
                audio_started = False
                sample_rate = 22050  # Default
                sample_width = 2     # 16-bit
                channels = 1         # Mono
                
                while True:
                    event = await asyncio.wait_for(
                        async_read_event(reader),
                        timeout=self.timeout
                    )
                    
                    if event is None:
                        break
                    
                    if AudioStart.is_type(event.type):
                        audio_started = True
                        audio_start = AudioStart.from_event(event)
                        sample_rate = audio_start.rate
                        sample_width = audio_start.width
                        channels = audio_start.channels
                        logger.debug(f"Audio: {sample_rate}Hz, {sample_width}B, {channels}ch")
                        
                    elif AudioChunk.is_type(event.type):
                        chunk = AudioChunk.from_event(event)
                        audio_bytes.extend(chunk.audio)
                        
                    elif AudioStop.is_type(event.type):
                        logger.debug("Audio stream stopped")
                        break
                
                if not audio_started or len(audio_bytes) == 0:
                    raise Exception("No audio data received")
                
                # ✅ CREATE PROPER WAV FILE
                wav_bytes = self._create_wav(audio_bytes, sample_rate, sample_width, channels)
                
                logger.info(f"✅ Wyoming TTS [{language}]: {len(wav_bytes)} bytes (WAV)")
                return wav_bytes
                
            finally:
                writer.close()
                await writer.wait_closed()
                
        except asyncio.TimeoutError:
            logger.error(f"❌ Wyoming TTS timeout after {self.timeout}s")
            raise Exception("TTS timeout")
            
        except Exception as e:
            logger.error(f"❌ Wyoming TTS error: {e}", exc_info=True)
            raise
    
    def _create_wav(self, pcm_data: bytes, sample_rate: int, sample_width: int, channels: int) -> bytes:
        """Create WAV file with proper header from raw PCM data."""
        wav_buffer = io.BytesIO()
        
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        
        return wav_buffer.getvalue()
    
    async def test_connection(self) -> bool:
        """Test connection to Piper."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=2
            )
            writer.close()
            await writer.wait_closed()
            logger.info("✅ Wyoming connection OK")
            return True
        except Exception as e:
            logger.error(f"❌ Wyoming connection failed: {e}")
            return False
