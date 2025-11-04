import logging
import json
import asyncio
from aiohttp import web
import aiohttp

logger = logging.getLogger(__name__)

class WebSocketHandler:
    """Handle WebSocket connections from ESP32 devices"""
    
    def __init__(self, stt_service, tts_service, ai_service, device_manager, ota_manager):
        """Initialize WebSocket handler"""
        self.stt_service = stt_service
        self.tts_service = tts_service
        self.ai_service = ai_service
        self.device_manager = device_manager
        self.ota_manager = ota_manager
        self.silence_timeout = 10  # seconds
        logger.info("🌐 WebSocket handler initialized")
    
    async def handle(self, request):
        """Handle WebSocket connection"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        device_id = None
        silence_task = None
        
        try:
            logger.info("🔌 New WebSocket connection")
            
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        msg_type = data.get('type')
                        
                        logger.debug(f"📨 Received: {msg_type}")
                        
                        # Cancel silence timeout on activity
                        if silence_task:
                            silence_task.cancel()
                        
                        if msg_type == 'register':
                            device_id = data.get('device_id')
                            firmware_version = data.get('firmware_version', 'unknown')
                            
                            self.device_manager.register_device(device_id, ws)
                            
                            await ws.send_json({
                                'type': 'registered',
                                'device_id': device_id,
                                'server_version': '1.0.2'
                            })
                            logger.info(f"✅ Device registered: {device_id} (FW: {firmware_version})")
                        
                        elif msg_type == 'audio':
                            # Voice interaction flow
                            audio_data = data.get('data')
                            language = data.get('language', 'vi')
                            
                            # Step 1: STT
                            await ws.send_json({'type': 'status', 'message': 'transcribing'})
                            text = await self.stt_service.transcribe(audio_data, language)
                            
                            if not text:
                                await ws.send_json({
                                    'type': 'error',
                                    'message': 'Không nghe rõ, bạn nói lại được không?'
                                })
                                continue
                            
                            await ws.send_json({
                                'type': 'transcription',
                                'text': text
                            })
                            
                            # Step 2: AI Processing
                            await ws.send_json({'type': 'status', 'message': 'thinking'})
                            ai_response = await self.ai_service.chat(text, language, device_id)
                            
                            await ws.send_json({
                                'type': 'response',
                                'text': ai_response
                            })
                            
                            # Step 3: TTS
                            await ws.send_json({'type': 'status', 'message': 'speaking'})
                            audio_response = await self.tts_service.synthesize(ai_response, language)
                            
                            # Send audio in chunks if needed
                            await ws.send_json({
                                'type': 'audio_response',
                                'data': audio_response,
                                'format': 'mp3'
                            })
                            
                            await ws.send_json({'type': 'status', 'message': 'ready'})
                            
                            # Start silence timeout
                            silence_task = asyncio.create_task(
                                self._silence_timeout(ws, device_id)
                            )
                        
                        elif msg_type == 'chat':
                            # Text-only chat
                            text = data.get('text')
                            language = data.get('language', 'vi')
                            
                            ai_response = await self.ai_service.chat(text, language, device_id)
                            
                            await ws.send_json({
                                'type': 'response',
                                'text': ai_response
                            })
                        
                        elif msg_type == 'command':
                            # Handle device commands (LED, volume, etc.)
                            command = data.get('command')
                            await self._handle_command(ws, device_id, command, data)
                        
                        elif msg_type == 'check_update':
                            # OTA update check
                            current_version = data.get('version')
                            update_info = await self.ota_manager.check_update(
                                device_id, current_version
                            )
                            await ws.send_json({
                                'type': 'update_info',
                                **update_info
                            })
                        
                        elif msg_type == 'ping':
                            await ws.send_json({'type': 'pong'})
                            self.device_manager.update_activity(device_id)
                        
                        elif msg_type == 'clear_context':
                            # Clear conversation history
                            self.ai_service.clear_conversation(device_id)
                            await ws.send_json({
                                'type': 'context_cleared',
                                'message': 'Conversation history cleared'
                            })
                    
                    except json.JSONDecodeError:
                        logger.error("❌ Invalid JSON received")
                        await ws.send_json({
                            'type': 'error',
                            'message': 'Invalid JSON format'
                        })
                    except Exception as e:
                        logger.error(f"❌ Error processing message: {e}", exc_info=True)
                        await ws.send_json({
                            'type': 'error',
                            'message': str(e)
                        })
                
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"❌ WebSocket error: {ws.exception()}")
        
        finally:
            if silence_task:
                silence_task.cancel()
            
            if device_id:
                self.device_manager.unregister_device(device_id)
                self.ai_service.clear_conversation(device_id)
                logger.info(f"🔌 Device disconnected: {device_id}")
            
            logger.info("🔌 WebSocket connection closed")
        
        return ws
    
    async def _silence_timeout(self, ws, device_id):
        """Handle silence timeout"""
        try:
            await asyncio.sleep(self.silence_timeout)
            await ws.send_json({
                'type': 'timeout',
                'message': 'Conversation ended due to inactivity'
            })
            logger.info(f"⏱️ Silence timeout for {device_id}")
        except asyncio.CancelledError:
            pass
    
    async def _handle_command(self, ws, device_id, command, data):
        """Handle device commands"""
        try:
            if command == 'led_control':
                # Control RGB LED
                color = data.get('color', 'white')
                state = data.get('state', 'on')
                await ws.send_json({
                    'type': 'command_response',
                    'command': 'led_control',
                    'status': 'ok'
                })
            
            elif command == 'volume':
                # Control volume
                level = data.get('level', 50)
                await ws.send_json({
                    'type': 'command_response',
                    'command': 'volume',
                    'level': level,
                    'status': 'ok'
                })
            
            elif command == 'light_control':
                # Control connected light
                state = data.get('state', 'on')
                await ws.send_json({
                    'type': 'command_response',
                    'command': 'light_control',
                    'state': state,
                    'status': 'ok'
                })
            
            logger.info(f"🎮 Command executed: {command} for {device_id}")
        
        except Exception as e:
            logger.error(f"❌ Command error: {e}")
            await ws.send_json({
                'type': 'command_response',
                'command': command,
                'status': 'error',
                'message': str(e)
            })
    
    async def get_status(self, request):
        """Get server status"""
        return web.json_response({
            'status': 'ok',
            'connected_devices': self.device_manager.get_device_count(),
            'version': '1.0.2'
        })
