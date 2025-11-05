"""
WebSocket Handler - Handles WebSocket connections and messages
"""

import logging
import json
import base64
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect


class WebSocketHandler:
    """WebSocket handler for managing device connections and messages"""
    
    def __init__(self, device_manager, ota_manager, ai_service, tts_service, stt_service):
        """Initialize WebSocket Handler"""
        self.logger = logging.getLogger('WebSocketHandler')
        self.device_manager = device_manager
        self.ota_manager = ota_manager
        self.ai_service = ai_service
        self.tts_service = tts_service
        self.stt_service = stt_service
        self.logger.info("🔌 WebSocket Handler initialized")
    
    async def handle_connection(self, websocket: WebSocket, device_id: str):
        """Handle WebSocket connection"""
        try:
            await websocket.accept()
            self.logger.info(f"📱 New WebSocket connection: {device_id}")
            
            # Store connection
            await self.device_manager.add_connection(device_id, websocket)
            
            # Handle messages
            while True:
                try:
                    # Receive message
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    self.logger.info(f"📨 Message from {device_id}: {message.get('type', 'unknown')}")
                    
                    # Route message to appropriate handler
                    await self.route_message(device_id, message)
                    
                except WebSocketDisconnect:
                    self.logger.info(f"📱 WebSocket disconnected: {device_id}")
                    break
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"❌ JSON decode error: {e}")
                    await self.send_error(device_id, "Invalid JSON format")
                    
                except Exception as e:
                    self.logger.error(f"❌ Message handling error: {e}", exc_info=True)
                    await self.send_error(device_id, str(e))
                    
        except Exception as e:
            self.logger.error(f"❌ Connection error: {e}", exc_info=True)
            
        finally:
            # Remove connection
            await self.device_manager.remove_connection(device_id)
            self.logger.info(f"📱 Connection closed: {device_id}")
    
    async def route_message(self, device_id: str, message: Dict):
        """Route message to appropriate handler"""
        message_type = message.get("type")
        
        handlers = {
            "register": self.handle_register,
            "text": self.handle_text,
            "chat": self.handle_chat,  # ← THÊM HANDLER CHO "chat" TỪ WEB
            "voice": self.handle_voice,
            "ping": self.handle_ping,
            "get_devices": self.handle_get_devices,
            "clear_history": self.handle_clear_history,
        }
        
        handler = handlers.get(message_type)
        
        if handler:
            message["device_id"] = device_id
            await handler(message)
        else:
            self.logger.warning(f"⚠️ Unknown message type: {message_type}")
            await self.send_error(device_id, f"Unknown message type: {message_type}")
    
    async def handle_register(self, data: Dict):
        """Handle device registration"""
        try:
            device_id = data.get("device_id")
            device_type = data.get("device_type", "unknown")
            firmware_version = data.get("firmware_version", "unknown")
            
            self.logger.info(f"✅ Registering device: {device_id}")
            self.logger.info(f"   Type: {device_type}")
            self.logger.info(f"   Firmware: {firmware_version}")
            
            # Register device
            await self.device_manager.register_device(
                device_id=device_id,
                device_type=device_type,
                firmware_version=firmware_version
            )
            
            # Send registration confirmation
            await self.send_message(device_id, {
                "type": "registered",
                "device_id": device_id,
                "server_version": "1.0.0"
            })
            
        except Exception as e:
            self.logger.error(f"❌ Registration error: {e}", exc_info=True)
            await self.send_error(data.get("device_id"), f"Registration error: {e}")
    
    async def handle_chat(self, data: Dict):
        """Handle chat message from web interface"""
        try:
            device_id = data.get("device_id")
            text = data.get("text", "")
            language = data.get("language", "auto")
            
            if not text:
                await self.send_error(device_id, "Empty text message")
                return
            
            self.logger.info(f"💬 Chat from {device_id}: {text}")
            
            # Get AI response
            ai_response = await self.ai_service.chat(text)
            
            if not ai_response:
                await self.send_error(device_id, "AI service error")
                return
            
            # Generate TTS audio
            audio_base64 = await self.tts_service.synthesize(ai_response, language)
            
            # Send response
            await self.send_message(device_id, {
                "type": "chat_response",
                "text": ai_response,
                "audio": audio_base64,
                "audio_format": "mp3"
            })
            
        except Exception as e:
            self.logger.error(f"❌ Chat error: {e}", exc_info=True)
            await self.send_error(device_id, f"Chat error: {e}")
    
    async def handle_text(self, data: Dict):
        """Handle text message from ESP32"""
        try:
            device_id = data.get("device_id")
            text = data.get("text", "")
            
            if not text:
                await self.send_error(device_id, "Empty text message")
                return
            
            self.logger.info(f"💬 Text from {device_id}: {text}")
            
            # Get AI response
            ai_response = await self.ai_service.chat(text)
            
            if not ai_response:
                await self.send_error(device_id, "AI service error")
                return
            
            # Send text response
            await self.send_message(device_id, {
                "type": "text",
                "text": ai_response
            })
            
            # Generate audio response
            audio_base64 = await self.tts_service.synthesize(ai_response, "auto")
            
            if audio_base64:
                # Send audio response
                await self.send_message(device_id, {
                    "type": "audio",
                    "audio": audio_base64,
                    "format": "mp3"
                })
            
        except Exception as e:
            self.logger.error(f"❌ Text error: {e}", exc_info=True)
            await self.send_error(device_id, f"Text error: {e}")
    
    async def handle_voice(self, data: Dict):
    """Handle voice message"""
    try:
        device_id = data.get("device_id")
        audio_base64 = data.get("audio")
        audio_format = data.get("format", "webm")
        language = data.get("language", "auto")
        
        if not audio_base64:
            await self.send_error(device_id, "Missing audio data")
            return
        
        self.logger.info(f"🎤 Voice from {device_id} (format: {audio_format}, language: {language})")
        
        # Decode audio
        audio_data = base64.b64decode(audio_base64)
        
        # === STEP 1: TRANSCRIBE AUDIO ===
        text = await self.stt_service.transcribe(audio_data, language)
        
        if not text:
            await self.send_error(device_id, "Could not transcribe audio")
            return
        
        self.logger.info(f"📝 Transcription: {text}")
        
        # === STEP 2: SEND TRANSCRIPTION IMMEDIATELY! ===
        await self.send_message(device_id, {
            "type": "transcription",
            "text": text
        })
        
        # === STEP 3: GET AI RESPONSE ===
        ai_response = await self.ai_service.chat(text)
        
        if not ai_response:
            await self.send_error(device_id, "AI service error")
            return
        
        # === STEP 4: GENERATE TTS ===
        response_audio = await self.tts_service.synthesize(ai_response, language)
        
        # === STEP 5: SEND AI RESPONSE + AUDIO ===
        await self.send_message(device_id, {
            "type": "ai_response",
            "text": ai_response,
            "audio": response_audio,
            "audio_format": "mp3"
        })
        
    except Exception as e:
        self.logger.error(f"❌ Voice error: {e}", exc_info=True)
        await self.send_error(device_id, f"Voice error: {e}")

    
    async def handle_ping(self, data: Dict):
        """Handle ping message"""
        device_id = data.get("device_id")
        await self.send_message(device_id, {"type": "pong"})
    
    async def handle_get_devices(self, data: Dict):
        """Handle get devices request"""
        try:
            device_id = data.get("device_id")
            devices = self.device_manager.get_all_devices()
            
            await self.send_message(device_id, {
                "type": "devices",
                "devices": devices
            })
            
        except Exception as e:
            self.logger.error(f"❌ Get devices error: {e}", exc_info=True)
            await self.send_error(data.get("device_id"), f"Get devices error: {e}")
    
    async def handle_clear_history(self, data: Dict):
        """Handle clear history request"""
        try:
            device_id = data.get("device_id")
            self.ai_service.clear_history()
            
            await self.send_message(device_id, {
                "type": "history_cleared",
                "message": "Conversation history cleared"
            })
            
        except Exception as e:
            self.logger.error(f"❌ Clear history error: {e}", exc_info=True)
            await self.send_error(data.get("device_id"), f"Clear history error: {e}")
    
    async def send_message(self, device_id: str, message: Dict):
        """Send message to device"""
        try:
            websocket = self.device_manager.get_connection(device_id)
            if websocket:
                await websocket.send_text(json.dumps(message))
            else:
                self.logger.warning(f"⚠️ No connection for device: {device_id}")
                
        except Exception as e:
            self.logger.error(f"❌ Send message error: {e}", exc_info=True)
    
    async def send_error(self, device_id: str, error: str):
        """Send error message to device"""
        await self.send_message(device_id, {
            "type": "error",
            "message": error
        })
    
    async def broadcast(self, message: Dict, exclude_device: Optional[str] = None):
        """Broadcast message to all connected devices"""
        devices = self.device_manager.get_all_connections()
        
        for device_id, websocket in devices.items():
            if device_id != exclude_device:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    self.logger.error(f"❌ Broadcast error to {device_id}: {e}")
