import asyncio
import io
import logging
import numpy as np
import webrtcvad
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self, device_id, stt, tts, ai):
        self.device_id = device_id
        self.stt = stt
        self.tts = tts
        self.ai = ai
        
        self.sample_rate = 16000
        self.frame_duration = 30  # ms
        self.frame_size = int(self.sample_rate * self.frame_duration / 1000)
        
        self.vad = webrtcvad.Vad(2)  # Aggressiveness 2
        self.audio_buffer = bytearray()
        self.is_speaking = False
        self.silence_start = None
        self.silence_timeout = timedelta(seconds=int(os.getenv('SILENCE_TIMEOUT', 8)))
        self.conversation_active = False
        
    async def start_conversation(self):
        """Start new conversation"""
        self.conversation_active = True
        self.audio_buffer.clear()
        self.is_speaking = False
        self.silence_start = None
        logger.info(f"🎙️ Conversation started for {self.device_id}")
        
    async def end_conversation(self):
        """End conversation"""
        self.conversation_active = False
        if self.audio_buffer:
            await self.process_final_audio()
        logger.info(f"🛑 Conversation ended for {self.device_id}")
        
    async def process_audio_chunk(self, audio_data, ws):
        """Process incoming PCM audio chunk"""
        if not self.conversation_active:
            return
            
        self.audio_buffer.extend(audio_data)
        
        # VAD check
        if len(audio_data) == self.frame_size * 2:  # 16-bit samples
            is_speech = self.vad.is_speech(audio_data, self.sample_rate)
            
            if is_speech:
                self.is_speaking = True
                self.silence_start = None
                await ws.send_json({'type': 'vad', 'speaking': True})
                
            elif self.is_speaking:
                if self.silence_start is None:
                    self.silence_start = datetime.now()
                elif datetime.now() - self.silence_start > self.silence_timeout:
                    # Silence detected, process audio
                    await self.process_final_audio(ws)
                    await ws.send_json({'type': 'vad', 'speaking': False})
                    
    async def process_final_audio(self, ws):
        """Transcribe audio and get AI response"""
        try:
            # Convert buffer to numpy array
            audio_np = np.frombuffer(bytes(self.audio_buffer), dtype=np.int16)
            
            # STT
            logger.info(f"🎤 Transcribing {len(audio_np)} samples...")
            text = await self.stt.transcribe(audio_np, self.sample_rate)
            
            if not text or len(text.strip()) < 3:
                logger.info("No speech detected")
                self.audio_buffer.clear()
                return
                
            logger.info(f"📝 User: {text}")
            await ws.send_json({
                'type': 'transcript',
                'text': text,
                'role': 'user'
            })
            
            # AI Response
            response_text = await self.ai.get_response(self.device_id, text)
            logger.info(f"🤖 AI: {response_text}")
            
            await ws.send_json({
                'type': 'transcript',
                'text': response_text,
                'role': 'assistant'
            })
            
            # TTS
            audio_chunks = await self.tts.synthesize(response_text)
            
            for chunk in audio_chunks:
                await ws.send_bytes(chunk)
                await asyncio.sleep(0.01)  # Rate limiting
                
            await ws.send_json({'type': 'audio_complete'})
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            await ws.send_json({'type': 'error', 'message': str(e)})
            
        finally:
            self.audio_buffer.clear()
            self.is_speaking = False
            self.silence_start = None
    
    async def cleanup(self):
        """Cleanup resources"""
        self.audio_buffer.clear()
