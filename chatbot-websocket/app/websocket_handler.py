import logging
import json
import asyncio
from aiohttp import web
import aiohttp

logger = logging.getLogger(__name__)

class WebSocketHandler:
    """Handle WebSocket connections from ESP32 devices"""
    
    def __init__(self, stt_service, tts_service, ai_service, device_manager, ota_manager):
        """Initialize WebSocket handler with services"""
        self.stt_service = stt_service
        self.tts_service = tts_service
        self.ai_service = ai_service
        self.device_manager = device_manager
        self.ota_manager = ota_manager
        self.active_connections = {}
        logger.info("✅ WebSocket handler initialized")
    
    async def handle(self, request):
        """Handle WebSocket connection"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        device_id = None
        
        try:
            logger.info("🔌 New WebSocket connection")
            
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        msg_type = data.get('type')
                        
                        logger.info(f"📨 Received: {msg_type}")
                        
                        if msg_type == 'register':
                            device_id = data.get('device_id')
                            self.active_connections[device_id] = ws
                            await ws.send_json({
                                'type': 'registered',
                                'device_id': device_id
                            })
                            logger.info(f"✅ Device registered: {device_id}")
                        
                        elif msg_type == 'audio':
                            # STT processing
                            audio_data = data.get('data')
                            language = data.get('language', 'vi')
                            
                            text = await self.stt_service.transcribe(audio_data, language)
                            
                            await ws.send_json({
                                'type': 'transcription',
                                'text': text
                            })
                            
                            # ✅ FIX: Use correct method with device_id
                            ai_response = await self.ai_service.get_response(text, device_id)
                            
                            await ws.send_json({
                                'type': 'response',
                                'text': ai_response
                            })
                            
                            # TTS processing
                            audio_response = await self.tts_service.synthesize(
                                ai_response, 
                                language
                            )
                            
                            await ws.send_json({
                                'type': 'audio_response',
                                'data': audio_response
                            })
                        
                        elif msg_type == 'chat':
                            # Text chat
                            text = data.get('text')
                            language = data.get('language', 'vi')
                            
                            # ✅ FIX: Use correct method with device_id
                            if device_id is None:
                                await ws.send_json({
                                    'type': 'error',
                                    'message': 'Device not registered. Send register message first.'
                                })
                                continue
                            
                            ai_response = await self.ai_service.get_response(text, device_id)
                            
                            await ws.send_json({
                                'type': 'response',
                                'text': ai_response
                            })
                        
                        elif msg_type == 'ping':
                            await ws.send_json({'type': 'pong'})
                        
                    except json.JSONDecodeError:
                        logger.error("❌ Invalid JSON received")
                        await ws.send_json({
                            'type': 'error',
                            'message': 'Invalid JSON'
                        })
                    except Exception as e:
                        logger.error(f"❌ Error processing message: {e}")
                        await ws.send_json({
                            'type': 'error',
                            'message': str(e)
                        })
                
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"❌ WebSocket error: {ws.exception()}")
        
        finally:
            if device_id and device_id in self.active_connections:
                del self.active_connections[device_id]
                logger.info(f"🔌 Device disconnected: {device_id}")
            logger.info("🔌 WebSocket connection closed")
        
        return ws
