import asyncio
import json
import logging
from aiohttp import web, WSMsgType
from audio_processor import AudioProcessor
from stt_service import STTService
from tts_service import TTSService
from ai_service import AIService

logger = logging.getLogger(__name__)

class WebSocketHandler:
    def __init__(self, device_manager):
        self.device_manager = device_manager
        self.stt = STTService()
        self.tts = TTSService()
        self.ai = AIService()
        
    async def handle_websocket(self, request):
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        
        device_id = None
        audio_processor = None
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self.handle_text_message(ws, msg.data, device_id, audio_processor)
                    
                elif msg.type == WSMsgType.BINARY:
                    if audio_processor:
                        await audio_processor.process_audio_chunk(msg.data, ws)
                    
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f'WebSocket error: {ws.exception()}')
                    
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            
        finally:
            if device_id:
                self.device_manager.disconnect_device(device_id)
                if audio_processor:
                    await audio_processor.cleanup()
            logger.info(f"Device {device_id} disconnected")
            
        return ws
    
    async def handle_text_message(self, ws, data, device_id, audio_processor):
        try:
            message = json.loads(data)
            msg_type = message.get('type')
            
            if msg_type == 'register':
                device_id = message.get('device_id')
                self.device_manager.register_device(device_id, ws)
                audio_processor = AudioProcessor(device_id, self.stt, self.tts, self.ai)
                
                await ws.send_json({
                    'type': 'registered',
                    'device_id': device_id,
                    'config': {
                        'sample_rate': 16000,
                        'channels': 1,
                        'format': 'pcm16'
                    }
                })
                logger.info(f"✅ Device {device_id} registered")
                
            elif msg_type == 'start_conversation':
                if audio_processor:
                    await audio_processor.start_conversation()
                    await ws.send_json({'type': 'conversation_started'})
                    
            elif msg_type == 'end_conversation':
                if audio_processor:
                    await audio_processor.end_conversation()
                    await ws.send_json({'type': 'conversation_ended'})
                    
            elif msg_type == 'command':
                await self.handle_command(ws, message.get('command'), audio_processor)
                
            elif msg_type == 'ping':
                await ws.send_json({'type': 'pong'})
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
            await ws.send_json({'type': 'error', 'message': 'Invalid JSON'})
    
    async def handle_command(self, ws, command, audio_processor):
        """Handle device commands (lights, volume, etc.)"""
        if not command:
            return
            
        cmd = command.get('action')
        
        if cmd == 'set_volume':
            volume = command.get('volume', 50)
            await ws.send_json({
                'type': 'command_response',
                'action': 'set_volume',
                'volume': volume
            })
            
        elif cmd == 'toggle_light':
            state = command.get('state', 'toggle')
            await ws.send_json({
                'type': 'command_response',
                'action': 'toggle_light',
                'state': state
            })
