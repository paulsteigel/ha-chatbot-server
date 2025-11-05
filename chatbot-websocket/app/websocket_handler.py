"""
WebSocket Handler
Handles WebSocket connections and message routing
"""
import logging
import json
import base64
from typing import Optional, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect


class WebSocketHandler:
    """Handle WebSocket connections and messages"""
    
    def __init__(self, ai_service, tts_service, stt_service, device_manager, ota_manager):
        """
        Initialize WebSocket handler
        
        Args:
            ai_service: AI service instance
            tts_service: TTS service instance
            stt_service: STT service instance
            device_manager: Device manager instance
            ota_manager: OTA manager instance
        """
        self.logger = logging.getLogger('WebSocketHandler')
        self.ai_service = ai_service
        self.tts_service = tts_service
        self.stt_service = stt_service
        self.device_manager = device_manager
        self.ota_manager = ota_manager
        
        # Store active connections
        self.active_connections: Dict[str, WebSocket] = {}
        
        self.logger.info("🔌 WebSocket Handler initialized")
    
    async def handle_connection(self, websocket: WebSocket, device_id: Optional[str] = None):
        """
        Handle WebSocket connection lifecycle
        
        Args:
            websocket: FastAPI WebSocket instance
            device_id: Optional device identifier
        """
        # Accept connection
        await websocket.accept()
        
        # Generate device_id if not provided
        if not device_id:
            device_id = f"web-{id(websocket)}"
        
        self.logger.info(f"📱 New WebSocket connection: {device_id}")
        
        # Store connection
        self.active_connections[device_id] = websocket
        
        try:
            # Connection loop
            while True:
                # Receive message
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                    await self.handle_message(websocket, device_id, message)
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"❌ Invalid JSON from {device_id}: {e}")
                    await self.send_error(websocket, "Invalid JSON format")
                    
                except Exception as e:
                    self.logger.error(f"❌ Error handling message from {device_id}: {e}", exc_info=True)
                    await self.send_error(websocket, f"Server error: {str(e)}")
        
        except WebSocketDisconnect:
            self.logger.info(f"🔌 WebSocket disconnected: {device_id}")
        
        except Exception as e:
            self.logger.error(f"❌ WebSocket error for {device_id}: {e}", exc_info=True)
        
        finally:
            # Cleanup
            if device_id in self.active_connections:
                del self.active_connections[device_id]
            
            self.device_manager.unregister_device(device_id)
            self.logger.info(f"🧹 Cleaned up connection: {device_id}")
    
    async def handle_message(self, websocket: WebSocket, device_id: str, message: Dict[str, Any]):
        """
        Handle incoming WebSocket message
        
        Args:
            websocket: WebSocket connection
            device_id: Device identifier
            message: Parsed message dictionary
        """
        msg_type = message.get('type')
        
        self.logger.info(f"📨 Message from {device_id}: {msg_type}")
        self.logger.debug(f"   Data: {message}")
        
        # Route message based on type
        if msg_type == 'register':
            await self.handle_register(websocket, device_id, message)
        
        elif msg_type == 'chat':
            await self.handle_chat(websocket, device_id, message)
        
        elif msg_type == 'voice':
            await self.handle_voice(websocket, device_id, message)
        
        elif msg_type == 'ping':
            await self.handle_ping(websocket, device_id, message)
        
        elif msg_type == 'ota_check':
            await self.handle_ota_check(websocket, device_id, message)
        
        else:
            self.logger.warning(f"⚠️ Unknown message type from {device_id}: {msg_type}")
            await self.send_error(websocket, f"Unknown message type: {msg_type}")
    
    async def handle_register(self, websocket: WebSocket, device_id: str, message: Dict[str, Any]):
        """Handle device registration"""
        device_type = message.get('device_type', 'unknown')
        firmware_version = message.get('firmware_version', 'unknown')
        
        self.logger.info(f"✅ Registering device: {device_id}")
        self.logger.info(f"   Type: {device_type}")
        self.logger.info(f"   Firmware: {firmware_version}")
        
        # Register device
        self.device_manager.register_device(device_id, device_type)
        
        # Send confirmation
        await websocket.send_json({
            'type': 'registered',
            'device_id': device_id,
            'server_version': '1.0.0',
            'timestamp': self._get_timestamp()
        })
    
    async def handle_chat(self, websocket: WebSocket, device_id: str, message: Dict[str, Any]):
        """Handle text chat message"""
        text = message.get('text') or message.get('message', '')
        language = message.get('language', 'auto')
        
        if not text:
            await self.send_error(websocket, "No text provided")
            return
        
        self.logger.info(f"💬 Chat from {device_id}: {text}")
        
        # Update activity
        self.device_manager.update_activity(device_id, 'message')
        
        try:
            # Get AI response
            response_text = await self.ai_service.chat(text, language)
            
            if not response_text:
                await self.send_error(websocket, "Failed to generate response")
                return
            
            self.logger.info(f"🤖 AI Response: {response_text}")
            
            # Generate TTS audio
            audio_base64 = await self.tts_service.synthesize(response_text, language)
            
            # Send response
            await websocket.send_json({
                'type': 'chat_response',
                'text': response_text,
                'audio': audio_base64,
                'audio_format': 'mp3',
                'language': language,
                'timestamp': self._get_timestamp()
            })
            
        except Exception as e:
            self.logger.error(f"❌ Chat error: {e}", exc_info=True)
            await self.send_error(websocket, f"Chat error: {str(e)}")
    
    async def handle_voice(self, websocket: WebSocket, device_id: str, message: Dict[str, Any]):
        """Handle voice message"""
        audio_base64 = message.get('audio')
        audio_format = message.get('format', 'wav')
        language = message.get('language', 'auto')
        
        if not audio_base64:
            await self.send_error(websocket, "No audio data provided")
            return
        
        self.logger.info(f"🎤 Voice message from {device_id} (Format: {audio_format})")
        
        # Update activity
        self.device_manager.update_activity(device_id, 'voice')
        
        try:
            # Decode base64 audio
            audio_data = base64.b64decode(audio_base64)
            self.logger.info(f"   Audio size: {len(audio_data)} bytes")
            
            # Transcribe audio to text
            transcribed_text = await self.stt_service.transcribe(
                audio_data, 
                language if language != 'auto' else 'vi',
                audio_format
            )
            
            if not transcribed_text:
                await self.send_error(websocket, "Failed to transcribe audio")
                return
            
            self.logger.info(f"📝 Transcribed: {transcribed_text}")
            
            # Get AI response
            response_text = await self.ai_service.chat(transcribed_text, language)
            
            if not response_text:
                await self.send_error(websocket, "Failed to generate response")
                return
            
            self.logger.info(f"🤖 AI Response: {response_text}")
            
            # Generate TTS audio
            audio_response = await self.tts_service.synthesize(response_text, language)
            
            # Send response
            await websocket.send_json({
                'type': 'voice_response',
                'transcribed_text': transcribed_text,
                'text': response_text,
                'audio': audio_response,
                'audio_format': 'mp3',
                'language': language,
                'timestamp': self._get_timestamp()
            })
            
        except Exception as e:
            self.logger.error(f"❌ Voice processing error: {e}", exc_info=True)
            await self.send_error(websocket, f"Voice error: {str(e)}")
    
    async def handle_ping(self, websocket: WebSocket, device_id: str, message: Dict[str, Any]):
        """Handle ping message"""
        self.logger.debug(f"🏓 Ping from {device_id}")
        
        await websocket.send_json({
            'type': 'pong',
            'timestamp': self._get_timestamp()
        })
    
    async def handle_ota_check(self, websocket: WebSocket, device_id: str, message: Dict[str, Any]):
        """Handle OTA update check"""
        current_version = message.get('current_version', 'unknown')
        
        self.logger.info(f"📦 OTA check from {device_id} (Version: {current_version})")
        
        # Check for updates
        update_info = await self.ota_manager.check_update(device_id, current_version)
        
        await websocket.send_json({
            'type': 'ota_response',
            **update_info,
            'timestamp': self._get_timestamp()
        })
    
    async def send_error(self, websocket: WebSocket, error_message: str):
        """Send error message to client"""
        try:
            await websocket.send_json({
                'type': 'error',
                'message': error_message,
                'timestamp': self._get_timestamp()
            })
        except Exception as e:
            self.logger.error(f"❌ Failed to send error: {e}")
    
    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds"""
        from datetime import datetime
        return int(datetime.now().timestamp() * 1000)
    
    def get_active_connections_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)
    
    def get_active_devices(self) -> list:
        """Get list of active device IDs"""
        return list(self.active_connections.keys())
