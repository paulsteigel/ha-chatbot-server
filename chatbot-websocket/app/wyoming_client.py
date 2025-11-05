# File: app/wyoming_client.py
"""
Wyoming Protocol Client for Piper TTS
"""
import asyncio
import logging
import struct
from typing import Optional
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.tts import Synthesize
from wyoming.event import Event, async_write_event, async_read_event

logger = logging.getLogger(__name__)

class WyomingTTSClient:
    """Client for Wyoming TTS protocol (Piper)."""
    
    def __init__(self, host: str = "addon_core_piper", port: int = 10200):
        """
        Initialize Wyoming TTS client.
        
        Args:
            host: Piper addon hostname
            port: Wyoming protocol port (default 10200)
        """
        self.host = host
        self.port = port
        self.timeout = 30
        
        logger.info(f"🔊 Wyoming TTS Client: {host}:{port}")
    
    async def synthesize(self, text: str, voice: str) -> bytes:
        """
        Synthesize text to speech using Wyoming protocol.
        
        Args:
            text: Text to synthesize
            voice: Voice name (e.g., "vi_VN-vais-medium")
            
        Returns:
            WAV audio bytes
        """
        try:
            logger.info(f"🔊 Wyoming TTS: voice={voice}, text='{text[:50]}...'")
            
            # Connect to Piper
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=5
            )
            
            try:
                # Send synthesize request
                synthesize_event = Synthesize(
                    text=text,
                    voice=voice
                )
                
                await async_write_event(synthesize_event.event(), writer)
                await writer.drain()
                
                # Receive audio chunks
                audio_bytes = bytearray()
                audio_started = False
                
                while True:
                    event = await asyncio.wait_for(
                        async_read_event(reader),
                        timeout=self.timeout
                    )
                    
                    if event is None:
                        break
                    
                    if AudioStart.is_type(event.type):
                        audio_started = True
                        logger.debug("Audio stream started")
                        
                    elif AudioChunk.is_type(event.type):
                        chunk = AudioChunk.from_event(event)
                        audio_bytes.extend(chunk.audio)
                        
                    elif AudioStop.is_type(event.type):
                        logger.debug("Audio stream stopped")
                        break
                
                if not audio_started or len(audio_bytes) == 0:
                    raise Exception("No audio data received")
                
                logger.info(f"✅ Wyoming TTS: {len(audio_bytes)} bytes (WAV)")
                return bytes(audio_bytes)
                
            finally:
                writer.close()
                await writer.wait_closed()
                
        except asyncio.TimeoutError:
            logger.error(f"❌ Wyoming TTS timeout after {self.timeout}s")
            raise Exception("TTS timeout")
            
        except Exception as e:
            logger.error(f"❌ Wyoming TTS error: {e}")
            raise
    
    async def test_connection(self) -> bool:
        """Test connection to Piper."""
        try:
            await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=2
            )
            return True
        except:
            return False
