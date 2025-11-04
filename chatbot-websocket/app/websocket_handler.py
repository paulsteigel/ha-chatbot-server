"""
WebSocket Handler
Handles WebSocket connections and message routing
"""
import logging
import json
import asyncio
from typing import Optional
from aiohttp import web, WSMsgType
import base64


class WebSocketHandler:
    """WebSocket connection handler"""
    
    HEARTBEAT_INTERVAL = 30
    HEARTBEAT_TIMEOUT = 90
    
    def __init__(self, device_manager, ai_service, tts_service, stt_service):
        self.logger = logging.getLogger('app.websocket_handler')
        self.device_manager = device_manager
        self.ai_service = ai_service
        self.tts_service = tts_service
        self.stt_service = stt_service
        self.logger.info("🌐 WebSocket handler initialized")
    
    async def handle(self, request):
        """Handle WebSocket connection"""
        ws = web.WebSocketResponse(heartbeat=self.HEARTBEAT_INTERVAL)
        await ws.prepare(request)
        
        self.logger.info("🔌 New WebSocket connection")
        
        device_id = None
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        response = await self._process_message(data, device_id)
                        
                        # Update device_id if registered
                        if response and response.get('type') == 'registered':
                            device_id = response.get('device_id')
                        
                        if response:
                            await ws.send_json(response)
                            
                    except json.JSONDecodeError:
                        self.logger.error(f"❌ Invalid JSON: {msg.data}")
                        await ws.send_json({
                            'type': 'error',
                            'message': 'Invalid JSON format'
                        })
                    except Exception as e:
                        self.logger.error(f"❌ Error processing message: {e}", exc_info=True)
                        await ws.send_json({
                            'type': 'error',
                            'message': str(e)
                        })
                
                elif msg.type == WSMsgType.ERROR:
                    self.logger.error(f"❌ WebSocket error: {ws.exception()}")
        
        except Exception as e:
            self.logger.error(f"❌ WebSocket handler error: {e}", exc_info=True)
        
        finally:
            if device_id:
                self.device_manager.unregister_device(device_id)
                # Clear AI conversation history
                await self.ai_service.clear_conversation(device_id)
                self.logger.info(f"🔌 Device disconnected: {device_id}")
            
            self.logger.info("🔌 WebSocket connection closed")
        
        return ws
    
    async def _process_message(self, data: dict, device_id: Optional[str]) -> Optional[dict]:
        """Process incoming message"""
        msg_type = data.get('type')
        
        if msg_type == 'register':
            return await self._handle_register(data)
        
        elif msg_type == 'chat':
            return await self._handle_chat(data, device_id)
        
        elif msg_type == 'voice':
            return await self._handle_voice(data, device_id)
        
        elif msg_type == 'command':
            return await self._handle_command(data, device_id)
        
        elif msg_type == 'ping':
            return {'type': 'pong', 'timestamp': data.get('timestamp')}
        
        else:
            self.logger.warning(f"⚠️ Unknown message type: {msg_type}")
            return {'type': 'error', 'message': f'Unknown message type: {msg_type}'}
    
    async def _handle_register(self, data: dict) -> dict:
        """Handle device registration"""
        device_id = data.get('device_id')
        device_type = data.get('device_type', 'unknown')
        firmware_version = data.get('firmware_version', 'unknown')
        
        if not device_id:
            return {'type': 'error', 'message': 'device_id required'}
        
        self.device_manager.register_device(device_id, device_type)
        self.logger.info(f"✅ Device registered: {device_id} (Type: {device_type}, FW: {firmware_version})")
        
        return {
            'type': 'registered',
            'device_id': device_id,
            'message': 'Device registered successfully'
        }
    
    async def _handle_chat(self, data: dict, device_id: Optional[str]) -> dict:
        """Handle chat message"""
        # Support both 'text' and 'message' fields for compatibility
        text = data.get('text') or data.get('message', '')
        text = text.strip()
        language = data.get('language', 'auto')
        
        if not text:
            return {'type': 'error', 'message': 'text required'}
        
        if not device_id:
            return {'type': 'error', 'message': 'Device not registered'}
        
        self.logger.info(f"💬 Chat from {device_id}: {text}")
        
        # Get AI response
        ai_response = await self.ai_service.chat(text, language, device_id)
        
        if not ai_response:
            return {
                'type': 'chat_response',
                'text': 'Xin lỗi, mình không thể trả lời lúc này.',
                'language': language
            }
        
        self.logger.info(f"🤖 AI response: {ai_response}")
        
        # Generate TTS audio
        audio_data = await self.tts_service.synthesize(ai_response, language)
        
        response = {
            'type': 'chat_response',
            'text': ai_response,
            'language': language
        }
        
        # Add audio if available
        if audio_data:
            # Convert to base64 for JSON transmission
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            response['audio'] = audio_base64
            response['audio_format'] = 'mp3'
            self.logger.info(f"🔊 Sending audio: {len(audio_data)} bytes")
        else:
            self.logger.warning("⚠️ No audio generated")
        
        return response
    
    async def _handle_voice(self, data: dict, device_id: Optional[str]) -> dict:
        """Handle voice input"""
        if not device_id:
            return {'type': 'error', 'message': 'Device not registered'}
        
        audio_base64 = data.get('audio')
        audio_format = data.get('format', 'wav')
        language = data.get('language', 'auto')
        
        if not audio_base64:
            return {'type': 'error', 'message': 'audio required'}
        
        try:
            # Decode base64 audio
            audio_data = base64.b64decode(audio_base64)
            
            self.logger.info(f"🎤 Processing voice input from {device_id}: {len(audio_data)} bytes")
            
            # Transcribe audio to text
            text = await self.stt_service.transcribe(audio_data, language)
            
            if not text:
                return {
                    'type': 'voice_response',
                    'text': 'Xin lỗi, mình không nghe rõ.',
                    'language': language
                }
            
            self.logger.info(f"🎤 Transcribed: {text}")
            
            # Get AI response
            ai_response = await self.ai_service.chat(text, language, device_id)
            
            if not ai_response:
                return {
                    'type': 'voice_response',
                    'text': 'Xin lỗi, mình không thể trả lời lúc này.',
                    'transcribed_text': text,
                    'language': language
                }
            
            self.logger.info(f"🤖 AI response: {ai_response}")
            
            # Generate TTS audio
            audio_response = await self.tts_service.synthesize(ai_response, language)
            
            response = {
                'type': 'voice_response',
                'text': ai_response,
                'transcribed_text': text,
                'language': language
            }
            
            # Add audio if available
            if audio_response:
                audio_base64 = base64.b64encode(audio_response).decode('utf-8')
                response['audio'] = audio_base64
                response['audio_format'] = 'mp3'
                self.logger.info(f"🔊 Sending audio: {len(audio_response)} bytes")
            
            return response
            
        except Exception as e:
            self.logger.error(f"❌ Voice processing error: {e}", exc_info=True)
            return {'type': 'error', 'message': f'Voice processing failed: {str(e)}'}
    
    async def _handle_command(self, data: dict, device_id: Optional[str]) -> dict:
        """Handle device command"""
        if not device_id:
            return {'type': 'error', 'message': 'Device not registered'}
        
        command = data.get('command')
        params = data.get('params', {})
        
        if not command:
            return {'type': 'error', 'message': 'command required'}
        
        self.logger.info(f"🎮 Command from {device_id}: {command} with params: {params}")
        
        # Here you can add command handling logic
        # For example: volume control, LED control, etc.
        
        return {
            'type': 'command_response',
            'command': command,
            'status': 'success',
            'message': f'Command {command} executed successfully'
        }
