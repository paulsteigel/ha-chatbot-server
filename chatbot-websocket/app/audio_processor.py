import logging
import numpy as np
import asyncio
from collections import deque

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self, stt_service, tts_service, ai_service, device_id):
        self.stt = stt_service
        self.tts = tts_service
        self.ai = ai_service
        self.device_id = device_id
        
        # Audio buffer
        self.audio_buffer = deque(maxlen=100)
        self.is_recording = False
        self.silence_counter = 0
        
        logger.info(f"🎙️  Audio processor initialized for {device_id}")
    
    async def process_audio(self, audio_data, ws):
        """Process incoming audio data"""
        try:
            # Convert bytes to numpy array (assuming 16-bit PCM)
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Add to buffer
            self.audio_buffer.append(audio_array)
            
            # Detect voice activity (simple threshold)
            rms = np.sqrt(np.mean(audio_array**2))
            
            if rms > 500:  # Voice detected
                self.is_recording = True
                self.silence_counter = 0
            else:
                self.silence_counter += 1
            
            # If silence for 8 frames (configurable), process
            if self.is_recording and self.silence_counter > 8:
                await self.finalize_recording(ws)
                
        except Exception as e:
            logger.error(f"❌ Audio processing error: {e}", exc_info=True)
    
    async def finalize_recording(self, ws):
        """Process complete audio recording"""
        try:
            self.is_recording = False
            
            # Concatenate audio buffer
            if not self.audio_buffer:
                return
                
            audio = np.concatenate(list(self.audio_buffer))
            self.audio_buffer.clear()
            
            logger.info(f"🎤 Processing {len(audio)} samples")
            
            # STT
            text = await self.stt.transcribe(audio)
            
            if not text:
                await ws.send_json({'type': 'error', 'message': 'Không nghe rõ'})
                return
            
            # Send transcription
            await ws.send_json({'type': 'transcription', 'text': text})
            
            # Get AI response
            response = await self.ai.get_response(text, self.device_id)
            
            # Send AI text
            await ws.send_json({'type': 'ai_response', 'text': response})
            
            # Generate TTS
            audio_data = await self.tts.synthesize(response)
            
            # Send audio (chunked)
            chunk_size = 4096
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                await ws.send_bytes(chunk)
            
            # Signal end of audio
            await ws.send_json({'type': 'audio_complete'})
            
        except Exception as e:
            logger.error(f"❌ Finalization error: {e}", exc_info=True)
            await ws.send_json({'type': 'error', 'message': str(e)})
